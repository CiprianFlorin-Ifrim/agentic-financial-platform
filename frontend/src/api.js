// api.js
// Frontend API client.
// Handles all communication with the FastAPI backend.
//
// chatWithAssistant -- POSTs to /assistant/chat and reads the SSE stream,
//   calling onEvent(event) for each parsed server-sent event object.
//   Accepts either a plain object (JSON) or FormData (file + message).

// -----------------------------------------------------------------------------
// chatWithAssistant
// -----------------------------------------------------------------------------
// payload  -- plain object { message, chat_history, session_id } OR
//             FormData    { file, data: JSON.stringify(payload) }
// onEvent  -- callback invoked for each SSE event:
//               { type: 'progress', stage: string }
//               { type: 'token',    content: string }
//               { type: 'done' }
//               { type: 'error',    message: string }
export async function chatWithAssistant(payload, onEvent) {
    const isFormData = payload instanceof FormData

    const response = await fetch('/assistant/chat', {
        method  : 'POST',
        headers : isFormData ? {} : { 'Content-Type': 'application/json' },
        body    : isFormData ? payload : JSON.stringify(payload),
    })

    if (!response.ok) {
        const text = await response.text().catch(() => 'Unknown error')
        onEvent({ type: 'error', message: `Server error ${response.status}: ${text}` })
        return
    }

    // -- SSE stream parsing ---------------------------------------------------
    const reader  = response.body.getReader()
    const decoder = new TextDecoder()
    let   buffer  = ''

    while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // SSE lines end with \n\n -- split on double newline to get complete events
        const parts = buffer.split('\n\n')
        buffer      = parts.pop()    // Keep any incomplete trailing chunk

        for (const part of parts) {
            const line = part.trim()
            if (!line.startsWith('data: ')) continue

            const raw = line.slice(6).trim()
            if (!raw || raw === '[DONE]') continue

            try {
                onEvent(JSON.parse(raw))
            } catch {
                // Malformed JSON from stream -- skip silently
            }
        }
    }
}
