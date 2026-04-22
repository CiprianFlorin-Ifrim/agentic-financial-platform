# backend/routers/assistant.py
# Assistant router.
# Exposes POST /assistant/chat -- the single endpoint the frontend calls.
#
# Accepts either:
#   -- application/json  { message, chat_history, session_id }
#   -- multipart/form-data  { file: <CSV/Excel>, data: <JSON string above> }
#
# Streams server-sent events (SSE) back to the client in the format:
#   data: {"type": "progress", "stage": "<stage_key>"}
#   data: {"type": "token",    "content": "<text chunk>"}
#   data: {"type": "done"}
#   data: {"type": "error",    "message": "<description>"}
#
# Stage keys match STAGE_ORDER in the frontend AssistantPanel:
#   fao_parse     -- CSV parsed, scenarios validated
#   aria_calc     -- ARIA agent activated
#   prism_model   -- PRISM agent activated
#   apex_evaluate -- APEX agent evaluating
#   nexus_store   -- NEXUS agent persisting  (only if user requests save)

import json
import asyncio
from typing import AsyncGenerator

from fastapi               import APIRouter, UploadFile, File, Form, Request
from fastapi.responses     import StreamingResponse

from google.adk.runners    import Runner
from google.genai          import types as genai_types

from backend.agents.interface_agent import iris_agent
from backend.agents.csv_parser      import parse_scenarios
from backend.schemas                import ChatMessage
from backend.session_service        import SQLiteSessionService


# -----------------------------------------------------------------------------
# Router
# -----------------------------------------------------------------------------

router = APIRouter()


# -----------------------------------------------------------------------------
# ADK session service  (SQLite-backed -- persists across server restarts)
# -----------------------------------------------------------------------------

_session_service = SQLiteSessionService()
_APP_NAME        = "fao-platform"


# -----------------------------------------------------------------------------
# SSE helper
# -----------------------------------------------------------------------------

class _SafeEncoder(json.JSONEncoder):
    """Fallback encoder -- converts bytes and other non-serialisable types to strings."""
    def default(self, obj):
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)


def _sse(payload: dict) -> str:
    """Format a dict as a single SSE data line, safely handling bytes values."""
    return f"data: {json.dumps(payload, cls=_SafeEncoder)}\n\n"


# -----------------------------------------------------------------------------
# Stream generator
# -----------------------------------------------------------------------------

async def _stream_response(
    message    : str,
    history    : list[ChatMessage],
    session_id : str,
) -> AsyncGenerator[str, None]:
    """
    Drive the Interface Agent via ADK Runner and yield SSE events.
    Progress events are emitted at key pipeline boundaries by inspecting
    the agent event stream for author transitions.
    """
    # -- Build the full user message ----------------------------------------
    # Prepend chat history so the LLM has conversational context across
    # turns. The session service does not round-trip ADK events, so without
    # this the agent has no memory of previous exchanges.
    history_block = ""
    if history:
        lines = []
        for msg in history[-10:]:    # Last 10 turns to stay within context
            role = msg.role.upper()
            lines.append(f"[{role}]: {msg.content}")
        history_block = "== CONVERSATION HISTORY ==\n" + "\n".join(lines) + "\n\n"

    user_content = history_block + message

    # -- ADK session setup ---------------------------------------------------
    try:
        session = await _session_service.get_session(
            app_name   = _APP_NAME,
            user_id    = session_id,
            session_id = session_id,
        )
    except Exception:
        session = await _session_service.create_session(
            app_name   = _APP_NAME,
            user_id    = session_id,
            session_id = session_id,
        )

    runner = Runner(
        agent           = iris_agent,
        app_name        = _APP_NAME,
        session_service = _session_service,
    )

    # -- Track which progress events have been emitted ----------------------
    emitted_stages = set()

    # -- ADK event loop ------------------------------------------------------
    full_text   = ""
    last_author = ""

    try:
        async for event in runner.run_async(
            user_id    = session_id,
            session_id = session_id,
            new_message = genai_types.Content(
                role  = "user",
                parts = [genai_types.Part(text=user_content)],
            ),
        ):
            # -- Emit stage progress -----------------------------------------
            # FAO is a sub_agent (transfer_to_agent), so it becomes the
            # author when active. Its tool calls to ARIA/PRISM/APEX/NEXUS
            # are visible as function_call names in the event stream.

            # Detect FAO by author transition
            author = getattr(event, "author", "") or ""
            if author != last_author:
                last_author = author
                if "fao" in author and "fao_parse" not in emitted_stages:
                    yield _sse({"type": "progress", "stage": "fao_parse"})
                    emitted_stages.add("fao_parse")
                    await asyncio.sleep(0)

            # Detect sub-agents by function_call names (AgentTool calls)
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "function_call") and part.function_call:
                        fn = part.function_call.name or ""
                        if "aria"  in fn and "aria_calc"     not in emitted_stages:
                            yield _sse({"type": "progress", "stage": "aria_calc"})
                            emitted_stages.add("aria_calc")
                            await asyncio.sleep(0)
                        elif "prism" in fn and "prism_model"  not in emitted_stages:
                            yield _sse({"type": "progress", "stage": "prism_model"})
                            emitted_stages.add("prism_model")
                            await asyncio.sleep(0)
                        elif "apex"  in fn and "apex_evaluate" not in emitted_stages:
                            yield _sse({"type": "progress", "stage": "apex_evaluate"})
                            emitted_stages.add("apex_evaluate")
                            await asyncio.sleep(0)
                        elif "nexus" in fn and "nexus_store"  not in emitted_stages:
                            yield _sse({"type": "progress", "stage": "nexus_store"})
                            emitted_stages.add("nexus_store")
                            await asyncio.sleep(0)

            # -- Stream text tokens ------------------------------------------
            # Emit text from any event that has text parts, skipping tool
            # calls and tool responses (those are agent-internal).
            content = event.content
            if content and content.parts:
                has_tool = any(
                    hasattr(p, "function_call") and p.function_call
                    or hasattr(p, "function_response") and p.function_response
                    for p in content.parts
                )
                if not has_tool:
                    for part in content.parts:
                        if hasattr(part, "text") and part.text:
                            text = part.text
                            for i in range(0, len(text), 4):
                                chunk = text[i : i + 4]
                                full_text += chunk
                                yield _sse({"type": "token", "content": chunk})
                                await asyncio.sleep(0.01)

    except GeneratorExit:
        # Client disconnected mid-stream -- exit silently
        return

    except Exception as exc:
        yield _sse({"type": "error", "message": str(exc)})
        return

    yield _sse({"type": "done"})


# -----------------------------------------------------------------------------
# Endpoint
# -----------------------------------------------------------------------------

@router.post("/chat")
async def chat(
    request: Request,
    file   : UploadFile | None = File(default=None),
    data   : str               = Form(default=None),
):
    """
    Stream a response from the Interface Agent as SSE.

    Accepts multipart/form-data when a CSV file is attached, or
    application/json for plain text messages.
    """
    # -- Parse incoming payload ----------------------------------------------
    session_id   = "default"
    chat_history : list[ChatMessage] = []
    message      = ""

    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        # File upload path
        if data:
            try:
                parsed   = json.loads(data)
                message  = parsed.get("message", "")
                session_id = parsed.get("session_id", "default")
                raw_hist = parsed.get("chat_history", [])
                chat_history = [ChatMessage(**m) for m in raw_hist]
            except (json.JSONDecodeError, Exception):
                message = "Analyse the uploaded scenarios."

        if file:
            file_bytes = await file.read()
            try:
                scenarios = parse_scenarios(file_bytes, file.filename)
                scenario_json = json.dumps([s.model_dump() for s in scenarios])
                # Inject parsed scenario data into the message for the agent
                message = (
                    f"{message}\n\nscenario_data: {scenario_json}\n\n"
                    f"File: {file.filename} -- {len(scenarios)} scenario(s) parsed. "
                    "Please analyse all scenarios and recommend the best deal."
                )
            except ValueError as exc:
                # Return the parse error as an SSE error event
                async def _err():
                    yield _sse({"type": "progress", "stage": "fao_parse"})
                    yield _sse({"type": "error", "message": str(exc)})
                    yield _sse({"type": "done"})
                return StreamingResponse(_err(), media_type="text/event-stream")
    else:
        # JSON path
        try:
            body       = await request.json()
            message    = body.get("message", "")
            session_id = body.get("session_id", "default")
            raw_hist   = body.get("chat_history", [])
            chat_history = [ChatMessage(**m) for m in raw_hist]
        except Exception:
            message = ""

    if not message.strip():
        async def _empty():
            yield _sse({"type": "error", "message": "Empty message received."})
            yield _sse({"type": "done"})
        return StreamingResponse(_empty(), media_type="text/event-stream")

    return StreamingResponse(
        _stream_response(message, chat_history, session_id),
        media_type = "text/event-stream",
        headers    = {
            "Cache-Control"              : "no-cache",
            "X-Accel-Buffering"          : "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
