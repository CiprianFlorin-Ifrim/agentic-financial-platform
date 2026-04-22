// AssistantPanel.jsx
// FAO Deal Pricing & Scenario Analysis — chat interface with agent trace panel.
// Left column: live agent/engine trace (FAO → ARIA → PRISM → APEX → NEXUS).
// Right column: multi-turn chat with streaming token output + CSV upload.
//
// Removed from original: TTS pipeline, mic/voice recording, appearance settings,
//   navbar accents, exam/stats/results context modes.
// Added: CSV upload, agent acronym tooltips, red/black theme, full-width layout,
//   financial suggestion chips.

import { useState, useRef, useEffect, useCallback, memo } from 'react'
import { chatWithAssistant } from '../api'
import { Streamdown } from 'streamdown'


// --- Design tokens -----------------------------------------------------------
const SANS = 'IBM Plex Sans, system-ui, sans-serif'
const MONO = 'IBM Plex Mono, monospace'

const C = {
    bg           : '#0a0a0a',
    bgCard       : '#0f0f0f',
    bg02         : '#161616',
    bg03         : '#222222',
    bg04         : '#2a2a2a',
    border       : '#2e2e2e',
    borderSubtle : '#1e1e1e',
    textPrimary  : '#f4f4f4',
    textSecondary: '#c6c6c6',
    textHelper   : '#6f6f6f',
    red          : '#da1e28',
    redBright    : '#ff4d56',
    redDim       : 'rgba(218, 30, 40, 0.12)',
    redGlow      : 'rgba(218, 30, 40, 0.35)',
    green        : '#42be65',
    amber        : '#f1c21b',
    teal         : '#3ddbd9',
}

// --- Agent / engine definitions ----------------------------------------------
const AGENT_INFO = {
    iris    : { name: 'IRIS',    full: 'Intelligent Routing & Interface System',  role: 'Front-door router',            color: C.textSecondary },
    fao     : { name: 'FAO',     full: 'Financial Assistance Orchestrator',       role: 'Orchestrator Agent',           color: C.red           },
    aria    : { name: 'ARIA',    full: 'Asset Risk & Impact Analyzer',            role: 'RWA Calculation Engine',       color: '#ff832b'      },
    prism   : { name: 'PRISM',   full: 'Pricing & Revenue Impact Scenario Modeler', role: 'Revenue Modelling Engine',  color: C.amber         },
    apex    : { name: 'APEX',    full: 'Assessment & Pricing EXpert',             role: 'Scenario Scoring & Selection', color: '#78a9ff'      },
    nexus   : { name: 'NEXUS',   full: 'Deal & Scenario Persistence Layer',       role: 'Database Engine',             color: C.teal          },
}

// --- Stage keys emitted by the backend SSE stream ----------------------------
// Maps SSE stage keys to the agent they belong to.
const STAGE_AGENT_MAP = {
    fao_parse    : 'fao',
    aria_calc    : 'aria',
    prism_model  : 'prism',
    apex_evaluate: 'apex',
    nexus_store  : 'nexus',
}

// Sub-agents of FAO -- rendered as independent branches, not sequential steps
const FAO_SUB_AGENTS = ['aria', 'prism', 'apex', 'nexus']

// --- Suggestion chips --------------------------------------------------------
const SUGGESTIONS = [
    'Upload a CSV to analyse deal scenarios',
    'What was the best scenario from the last run?',
    'Explain the RWA impact across all scenarios',
    'Show me the last deal saved to NEXUS',
    'Compare revenue impact across scenarios',
    'Which scenario has the lowest capital cost?',
]

// --- Global style injection --------------------------------------------------
;(() => {
    if (typeof document === 'undefined') return
    const el = document.createElement('style')
    el.textContent = `
        @keyframes ap-pulse {
            0%   { box-shadow: 0 0 0 0   currentColor; }
            70%  { box-shadow: 0 0 0 8px transparent;   }
            100% { box-shadow: 0 0 0 0   transparent;   }
        }
        @keyframes ap-fade-up {
            from { opacity: 0; transform: translateY(4px); }
            to   { opacity: 1; transform: translateY(0);   }
        }
        @keyframes ap-spin {
            from { transform: rotate(0deg);   }
            to   { transform: rotate(360deg); }
        }
        @keyframes ap-flicker {
            0%, 100% { opacity: 1; }
            50%      { opacity: 0.6; }
        }
        .ap-md { font-size: 0.875rem; }
        .ap-md p              { margin: 0 0 0.5rem; font-size: 0.875rem; }
        .ap-md p:last-child   { margin-bottom: 0; }
        .ap-md ul             { list-style-type: square; padding-left: 1.5rem; margin: 0 0 0.5rem; }
        .ap-md ol             { list-style-type: decimal; padding-left: 1.5rem; margin: 0 0 0.5rem; }
        .ap-md li             { display: list-item; margin-bottom: 0.2rem; color: #c6c6c6; font-size: 0.8125rem; line-height: 1.65; }
        .ap-md li *           { font-size: 0.8125rem; line-height: 1.65; }
        .ap-md strong         { color: #f4f4f4; font-weight: 600; }
        .ap-md code           { background: #1a1a1a; padding: 0.1rem 0.35rem; font-family: IBM Plex Mono, monospace; font-size: 0.8125rem; border: 1px solid #2e2e2e; }
        .ap-md pre            { background: #161616; padding: 0.75rem 1rem; margin: 0.5rem 0; overflow-x: auto; border-left: 2px solid #da1e28; }
        .ap-md pre code       { background: none; padding: 0; border: none; }
        .ap-md h1, .ap-md h2, .ap-md h3 { color: #f4f4f4; font-weight: 600; margin: 0.5rem 0 0.25rem; }
        .ap-md hr             { border: none; border-top: 1px solid #2e2e2e; margin: 0.5rem 0; }
        .ap-md table          { width: 100%; border-collapse: collapse; font-size: 0.8125rem; margin: 0.5rem 0; }
        .ap-md th             { background: #1a1a1a; color: #f4f4f4; padding: 0.4rem 0.75rem; text-align: left; border: 1px solid #2e2e2e; font-weight: 600; }
        .ap-md td             { padding: 0.35rem 0.75rem; border: 1px solid #222; color: #c6c6c6; }
        .ap-md tr:nth-child(even) td { background: #141414; }
        /* Position .ap-md as relative anchor for absolute button placement */
        .ap-md:has(table)  { position: relative; padding-bottom: 1.75rem !important; }

        /* Hide copy button (first wrapper) */
        .ap-md div:has(> button):first-child  { display: none !important; }

        /* Hide any other button wrappers (format selectors etc) */
        .ap-md div:has(> button)  { display: none !important; }

        /* Show ONLY the download button (second wrapper) at bottom-right */
        .ap-md div:has(> button):nth-child(2)  { display: block !important; position: absolute !important; bottom: 0; right: 0; z-index: 2; }
        .ap-md div:has(> button):nth-child(2) button  { background: none !important; color: #a8a8a8 !important; border: 1px solid #2e2e2e !important; border-radius: 0 !important; cursor: pointer !important; transition: all 0.15s !important; font-family: IBM Plex Mono, monospace !important; font-size: 0 !important; padding: 0.25rem 0.625rem !important; }
        .ap-md div:has(> button):nth-child(2) button > *  { display: none !important; }
        .ap-md div:has(> button):nth-child(2) button::after  { content: 'DOWNLOAD'; font-size: 0.625rem; letter-spacing: 0.06em; }
        .ap-md div:has(> button):nth-child(2) button:hover  { border-color: #da1e28 !important; color: #da1e28 !important; }
        .ap-chip:hover        { border-color: #da1e28 !important; color: #f4f4f4 !important; background: rgba(218,30,40,0.08) !important; }
        .ap-upload:hover      { border-color: #da1e28 !important; background: rgba(218,30,40,0.1) !important; }
        ::-webkit-scrollbar               { width: 4px; height: 4px; }
        ::-webkit-scrollbar-track         { background: #0f0f0f; }
        ::-webkit-scrollbar-thumb         { background: #2e2e2e; border-radius: 2px; }
        ::-webkit-scrollbar-thumb:hover   { background: #da1e28; }
    `
    document.head.appendChild(el)

    // Direct CSV download -- bypasses Streamdown's format selection entirely
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.ap-md div:nth-child(2) button')
        if (!btn) return
        e.stopPropagation()
        e.preventDefault()

        const md = btn.closest('.ap-md')
        const table = md?.querySelector('table')
        if (!table) return

        const rows = []
        table.querySelectorAll('tr').forEach(tr => {
            const cells = []
            tr.querySelectorAll('th, td').forEach(cell => {
                let text = cell.textContent.replace(/"/g, '""')
                cells.push('"' + text + '"')
            })
            rows.push(cells.join(','))
        })

        const csv = rows.join('\n')
        const blob = new Blob([csv], { type: 'text/csv' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'table.csv'
        a.click()
        URL.revokeObjectURL(url)
    }, true)
})()

// =============================================================================
// Custom hooks
// =============================================================================

// --- useDragResize -----------------------------------------------------------
function useDragResize() {
    const getInitial = () => window.innerHeight - 48  // fill viewport minus top bar
    const [panelHeight, setPanelHeight] = useState(getInitial)
    const isDragging    = useRef(false)
    const dragStartY    = useRef(0)
    const dragStartH    = useRef(0)
    const lastMouseY    = useRef(0)
    const rafRef        = useRef(null)
    const panelRef      = useRef(null)
    const heightRef     = useRef(panelHeight)
    useEffect(() => { heightRef.current = panelHeight }, [panelHeight])

    // Keep full height on window resize
    useEffect(() => {
        const onResize = () => setPanelHeight(window.innerHeight - 48)
        window.addEventListener('resize', onResize)
        return () => window.removeEventListener('resize', onResize)
    }, [])

    const onDragMove = useCallback((e) => {
        if (!isDragging.current) return
        lastMouseY.current = e.clientY
        if (rafRef.current) return
        rafRef.current = requestAnimationFrame(() => {
            rafRef.current = null
            const delta = lastMouseY.current - dragStartY.current
            setPanelHeight(Math.max(320, dragStartH.current + delta))
        })
    }, [])

    const onDragEnd = useCallback(() => {
        if (!isDragging.current) return
        isDragging.current             = false
        document.body.style.cursor     = ''
        document.body.style.userSelect = ''
        document.removeEventListener('mousemove', onDragMove)
        document.removeEventListener('mouseup',   onDragEnd)
    }, [onDragMove])

    const onDragStart = useCallback((e) => {
        e.preventDefault()
        isDragging.current             = true
        dragStartY.current             = e.clientY
        dragStartH.current             = heightRef.current
        lastMouseY.current             = e.clientY
        document.body.style.cursor     = 'ns-resize'
        document.body.style.userSelect = 'none'
        if (panelRef.current) panelRef.current.style.transition = 'none'
        document.addEventListener('mousemove', onDragMove)
        document.addEventListener('mouseup',   onDragEnd)
    }, [onDragMove, onDragEnd])

    return { panelHeight, panelRef, onDragStart, isDragging }
}

// --- useAgentStages ----------------------------------------------------------
// Tracks the visual status of each agent in the side panel.
// Status lifecycle: (absent) -> 'active' -> 'done' -> 'fading' -> (deleted)
//
// Flow:
//   1. reset() on send: IRIS becomes active
//   2. fao_parse:       IRIS -> done, FAO -> active
//   3. aria_calc:       ARIA -> active
//   4. prism_model:     ARIA -> done, PRISM -> active
//   5. apex_evaluate:   PRISM -> done, APEX -> active
//   6. nexus_store:     APEX -> done, NEXUS -> active
//   7. onStreamComplete: all remaining active -> done, then fade out

// Sub-agent activation order -- used to mark the previous one as done
const SUB_AGENT_ORDER = ['aria', 'prism', 'apex', 'nexus']

function useAgentStages() {
    const [statuses, setStatuses] = useState({})

    const onStageArrived = useCallback((stage) => {
        const agentKey = STAGE_AGENT_MAP[stage]
        if (!agentKey) return

        setStatuses(prev => {
            const next = { ...prev }

            // When FAO activates, mark IRIS as done
            if (agentKey === 'fao') {
                if (next['iris'] === 'active') next['iris'] = 'done'
            }

            // When a sub-agent activates, mark the previous sub-agent as done
            const subIdx = SUB_AGENT_ORDER.indexOf(agentKey)
            if (subIdx > 0) {
                const prevSub = SUB_AGENT_ORDER[subIdx - 1]
                if (next[prevSub] === 'active') next[prevSub] = 'done'
            }

            next[agentKey] = 'active'
            return next
        })
    }, [])

    const onStreamComplete = useCallback(() => {
        // Mark all remaining active agents as done
        setStatuses(prev => {
            const next = { ...prev }
            Object.keys(next).forEach(k => {
                if (next[k] === 'active') next[k] = 'done'
            })
            return next
        })

        // Fade out only agents that were activated, in order
        const allKeys = ['iris', 'fao', ...SUB_AGENT_ORDER]
        allKeys.forEach((key, i) => {
            const delay = 1200 + i * 200
            setTimeout(() => setStatuses(p => {
                if (!p[key]) return p   // skip agents that were never activated
                return { ...p, [key]: 'fading' }
            }), delay)
            setTimeout(() => setStatuses(p => {
                const n = { ...p }; delete n[key]; return n
            }), delay + 300)
        })
    }, [])

    const reset     = useCallback(() => setStatuses({ iris: 'active' }), [])
    const getStatus = useCallback((key) => statuses[key] ?? 'pending', [statuses])

    return { getStatus, onStageArrived, onStreamComplete, reset }
}

// =============================================================================
// Sub-components
// =============================================================================

// --- StageIcon ---------------------------------------------------------------
const StageIcon = memo(function StageIcon({ status, color }) {
    if (status === 'done') return (
        <div style={{
            width: 18, height: 18, borderRadius: '50%',
            background: C.green, display: 'flex',
            alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            animation: 'ap-fade-up 0.2s ease both',
        }}>
            <svg width="9" height="7" viewBox="0 0 10 8" fill="none">
                <path d="M1 4L3.8 7L9 1" stroke="#000" strokeWidth="1.8"
                    strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
        </div>
    )

    if (status === 'active' || status === 'fading') return (
        <div style={{
            width: 18, height: 18, borderRadius: '50%',
            border: `2px solid ${color || C.red}`, position: 'relative', flexShrink: 0,
            color: color || C.red,
            animation: 'ap-pulse 1.4s ease-in-out infinite',
        }}>
            <div style={{
                width: 7, height: 7, borderRadius: '50%', background: color || C.red,
                position: 'absolute', top: '50%', left: '50%',
                transform: 'translate(-50%, -50%)',
                animation: 'ap-flicker 1.4s ease-in-out infinite',
            }} />
        </div>
    )

    return (
        <div style={{
            width: 18, height: 18, borderRadius: '50%',
            border: `1px solid ${C.border}`, flexShrink: 0,
        }} />
    )
})

// --- AgentPanel --------------------------------------------------------------
// Left column -- clean angular tree layout.
// Vertical trunk connects IRIS -> FAO, then FAO branches to sub-agents
// with right-angle connectors (matching the SVG diagram style).
const AgentPanel = memo(function AgentPanel({ getStatus, hasStarted }) {
    const [tooltip, setTooltip] = useState(null)

    const showTooltip = useCallback((e, key) => {
        setTooltip({ key, x: e.clientX + 12, y: e.clientY - 10 })
    }, [])

    const hideTooltip = useCallback(() => setTooltip(null), [])

    // -- Layout constants --------------------------------------------------
    const ROW_H  = 36
    const R      = 9      // icon radius (StageIcon is 18x18)
    const TX     = 16     // trunk x position
    const L0_IX  = 16     // IRIS/FAO icon center x (on trunk)
    const L1_IX  = 40     // sub-agent icon center x (indented)
    const SVG_W  = 54

    const ALL = ['iris', 'fao', ...FAO_SUB_AGENTS]
    const yOf = (idx) => idx * ROW_H + ROW_H / 2

    const irisY    = yOf(0)
    const faoY     = yOf(1)
    const firstSubY = yOf(2)
    const subYs    = FAO_SUB_AGENTS.map((_, i) => yOf(2 + i))
    const lastSubY = subYs[subYs.length - 1]
    const totalH   = ALL.length * ROW_H

    const LINE = C.borderSubtle

    return (
        <div style={{
            width: '200px', height: '100%',
            padding: '1.25rem 0.875rem 1.25rem 1.125rem',
            display: 'flex', flexDirection: 'column',
            borderRight: `1px solid ${C.borderSubtle}`,
        }}>
            {/* Header */}
            <div style={{
                fontSize: '0.625rem', color: C.textHelper, letterSpacing: '0.08em',
                textTransform: 'uppercase', marginBottom: '1rem', fontFamily: MONO,
                display: 'flex', alignItems: 'center', gap: '0.5rem',
            }}>
                Agents
            </div>

            {/* Tree */}
            <div style={{ position: 'relative', height: totalH, flexShrink: 0 }}>

                {/* SVG lines */}
                <svg
                    width={SVG_W} height={totalH}
                    style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'none', overflow: 'visible' }}
                >
                    {/* Vertical trunk: IRIS down to FAO */}
                    <line x1={TX} y1={irisY + R} x2={TX} y2={faoY - R} stroke={LINE} strokeWidth="1" />

                    {/* Vertical trunk: FAO down to last sub-agent */}
                    <line x1={TX} y1={faoY + R} x2={TX} y2={lastSubY} stroke={LINE} strokeWidth="1" />

                    {/* Horizontal elbows from trunk to each sub-agent */}
                    {subYs.map((y, i) => (
                        <line key={i} x1={TX} y1={y} x2={L1_IX - R} y2={y} stroke={LINE} strokeWidth="1" />
                    ))}
                </svg>

                {/* Rows */}
                {ALL.map((key, idx) => {
                    const agent  = AGENT_INFO[key]
                    const status = getStatus(key)
                    const dimmed = !hasStarted
                    const isL0   = key === 'iris' || key === 'fao'
                    const iconX  = isL0 ? L0_IX : L1_IX
                    const textL  = iconX + R + 6

                    return (
                        <div
                            key={key}
                            style={{
                                position   : 'absolute',
                                top        : idx * ROW_H,
                                left       : 0,
                                right      : 0,
                                height     : ROW_H,
                                display    : 'flex',
                                alignItems : 'center',
                            }}
                            onMouseEnter={e => showTooltip(e, key)}
                            onMouseLeave={hideTooltip}
                        >
                            {/* Icon */}
                            <div style={{
                                position : 'absolute',
                                left     : iconX - R,
                                top      : ROW_H / 2 - R,
                                width    : R * 2,
                                height   : R * 2,
                            }}>
                                <StageIcon status={dimmed ? 'pending' : status} color={agent.color} />
                            </div>

                            {/* Label */}
                            <div style={{
                                paddingLeft: textL,
                                opacity    : dimmed ? 0.3 : status === 'fading' ? 0.4 : 1,
                                transition : 'opacity 0.3s',
                                minWidth   : 0,
                            }}>
                                <div style={{
                                    fontSize  : '0.75rem', fontFamily: MONO, fontWeight: 700, lineHeight: 1,
                                    color     : status === 'done'   ? C.textSecondary
                                               : status === 'active' ? agent.color : C.textHelper,
                                    transition: 'color 0.25s',
                                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                                    ...(status === 'active' && { animation: 'ap-fade-up 0.2s ease both' }),
                                }}>
                                    {agent.name}
                                </div>
                            </div>
                        </div>
                    )
                })}
            </div>

            {/* Hint */}
            <div style={{
                marginTop: 'auto',
                paddingTop: '1rem',
                fontSize: '0.625rem', color: C.textHelper,
                fontFamily: SANS, lineHeight: 1.7, opacity: 0.6,
            }}>
                Hover any agent to see its role. Sub-agents activate independently.
            </div>

            {/* Tooltip */}
            {tooltip && (() => {
                const agent = AGENT_INFO[tooltip.key]
                return (
                    <div style={{
                        position: 'fixed', left: tooltip.x, top: tooltip.y,
                        zIndex: 9999, background: C.bg03,
                        border: `1px solid ${C.border}`,
                        borderLeft: `2px solid ${agent.color}`,
                        padding: '0.5rem 0.75rem', minWidth: '180px',
                        pointerEvents: 'none',
                        animation: 'ap-fade-up 0.15s ease both',
                    }}>
                        <div style={{ fontFamily: MONO, fontSize: '0.6875rem', color: agent.color, fontWeight: 700, marginBottom: '0.2rem' }}>{agent.name}</div>
                        <div style={{ fontFamily: SANS, fontSize: '0.6875rem', color: C.textPrimary, fontWeight: 600, marginBottom: '0.15rem' }}>{agent.full}</div>
                        <div style={{ fontFamily: SANS, fontSize: '0.625rem', color: C.textHelper }}>{agent.role}</div>
                    </div>
                )
            })()}
        </div>
    )
})
// --- SuggestionChips ---------------------------------------------------------
const SuggestionChips = memo(function SuggestionChips({ onSelect }) {
    return (
        <div style={{
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            height: '100%', gap: '1rem',
        }}>
            {/* Logo mark */}
            <div style={{ marginBottom: '1.5rem' }}>
                <div style={{
                    width: 72, height: 72,
                    background: C.redDim,
                    border: `1px solid ${C.redGlow}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                    <svg width="34" height="34" viewBox="0 0 16 16" fill="none">
                        <rect x="2" y="2" width="5" height="5" fill={C.red} opacity="0.9"/>
                        <rect x="9" y="2" width="5" height="5" fill={C.red} opacity="0.5"/>
                        <rect x="2" y="9" width="5" height="5" fill={C.red} opacity="0.5"/>
                        <rect x="9" y="9" width="5" height="5" fill={C.red} opacity="0.9"/>
                    </svg>
                </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', width: '100%', maxWidth: '300px' }}>
                {SUGGESTIONS.map(prompt => (
                    <button
                        key={prompt}
                        className="ap-chip"
                        onClick={() => onSelect(prompt)}
                        style={{
                            background : C.bg02,
                            border     : `1px solid ${C.border}`,
                            color      : C.textHelper,
                            fontFamily : SANS,
                            fontSize   : '0.8125rem',
                            padding    : '0.5rem 1rem',
                            cursor     : 'pointer',
                            transition : 'all 0.15s',
                            width      : '100%',
                            textAlign  : 'left',
                        }}
                    >
                        {prompt}
                    </button>
                ))}
            </div>
        </div>
    )
})

// --- MessageBubble -----------------------------------------------------------
const MessageBubble = memo(function MessageBubble({ msg }) {
    const isUser = msg.role === 'user'
    return (
        <div style={{
            display: 'flex',
            justifyContent: isUser ? 'flex-end' : 'flex-start',
            animation: isUser ? 'ap-fade-up 0.2s ease both' : 'none',
        }}>
            <div style={{
                maxWidth   : '78%',
                padding    : '0.75rem 1rem',
                background : isUser ? 'rgba(218,30,40,0.07)' : C.bg02,
                borderLeft : !isUser ? `2px solid ${C.red}`  : 'none',
                borderRight: isUser  ? `2px solid ${C.red}`  : 'none',
                fontSize   : '0.875rem',
                color      : isUser ? C.textPrimary : C.textSecondary,
                fontFamily : SANS,
                lineHeight : 1.65,
                wordBreak  : 'break-word',
            }}>
                {isUser
                    ? msg.content
                    : <div className="ap-md"><Streamdown isAnimating={false}>{msg.content}</Streamdown></div>
                }
                {isUser && msg.fileName && (
                    <div style={{
                        marginTop  : '0.5rem',
                        padding    : '0.3rem 0.625rem',
                        background : 'rgba(218,30,40,0.06)',
                        border     : `1px solid rgba(218,30,40,0.2)`,
                        display    : 'flex',
                        alignItems : 'center',
                        gap        : '0.375rem',
                    }}>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke={C.red} strokeWidth="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                            <polyline points="14,2 14,8 20,8"/>
                        </svg>
                        <span style={{ fontFamily: MONO, fontSize: '0.6875rem', color: C.textSecondary }}>{msg.fileName}</span>
                    </div>
                )}
            </div>
        </div>
    )
})

// --- MessageList -------------------------------------------------------------
const MessageList = memo(function MessageList({ chatHistory }) {
    return (
        <>
            {chatHistory.map((msg, i) => (
                <MessageBubble key={i} msg={msg} />
            ))}
        </>
    )
})

// --- StreamingBubble ---------------------------------------------------------
const StreamingBubble = memo(function StreamingBubble({ text, isStreaming }) {
    const bubbleRef    = useRef(null)
    const minHeightRef = useRef(0)

    useEffect(() => {
        if (!bubbleRef.current) return
        const h = bubbleRef.current.scrollHeight
        if (h > minHeightRef.current) {
            minHeightRef.current                  = h
            bubbleRef.current.style.minHeight     = `${h}px`
        }
    }, [text])

    if (!text) return null
    return (
        <div style={{ display: 'flex', animation: 'ap-fade-up 0.2s ease both' }}>
            <div ref={bubbleRef} style={{
                maxWidth  : '78%',
                padding   : '0.75rem 1rem',
                background: C.bg02,
                borderLeft: `2px solid ${C.red}`,
                fontSize  : '0.875rem',
                color     : C.textSecondary,
                fontFamily: SANS,
                lineHeight: 1.65,
                wordBreak : 'break-word',
            }}>
                <div className="ap-md"><Streamdown isAnimating={isStreaming}>{text}</Streamdown></div>
            </div>
        </div>
    )
})

// --- UploadBanner ------------------------------------------------------------
// Shows the attached file name above the input when a CSV is staged.
const UploadBanner = memo(function UploadBanner({ file, onClear }) {
    if (!file) return null
    return (
        <div style={{
            display   : 'flex', alignItems: 'center', gap: '0.625rem',
            padding   : '0.5rem 1.25rem',
            background: 'rgba(218,30,40,0.06)',
            borderTop : `1px solid rgba(218,30,40,0.2)`,
            flexShrink: 0,
        }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={C.red} strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14,2 14,8 20,8"/>
            </svg>
            <span style={{ fontFamily: MONO, fontSize: '0.75rem', color: C.textSecondary, flex: 1 }}>{file.name}</span>
            <span style={{ fontFamily: SANS, fontSize: '0.6875rem', color: C.textHelper }}>{(file.size / 1024).toFixed(1)} KB</span>
            <button
                onClick={onClear}
                style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: C.textHelper, padding: '0 0.25rem', lineHeight: 1,
                    fontSize: '1rem',
                }}
                title="Remove file"
            >×</button>
        </div>
    )
})

// =============================================================================
// AssistantPanel
// =============================================================================
export default function AssistantPanel() {
    // -- Chat state -----------------------------------------------------------
    const [chatHistory,   setChatHistory  ] = useState([])
    const [streaming,     setStreaming    ] = useState(false)
    const [streamingText, setStreamingText] = useState('')
    const [hasStarted,    setHasStarted   ] = useState(false)
    const [error,         setError        ] = useState(null)
    const [pipelineOpen,  setPipelineOpen ] = useState(true)

    const streamingRef = useRef(streaming)
    useEffect(() => { streamingRef.current = streaming }, [streaming])

    // -- File upload ----------------------------------------------------------
    const [stagedFile, setStagedFile] = useState(null)
    const fileInputRef = useRef(null)

    const handleFileChange = useCallback((e) => {
        const file = e.target.files?.[0]
        if (!file) return
        const ext = file.name.split('.').pop().toLowerCase()
        if (!['csv', 'xlsx', 'xls'].includes(ext)) {
            setError('Please upload a CSV or Excel file (.csv, .xlsx, .xls).')
            return
        }
        setStagedFile(file)
        setError(null)
        // Reset so same file can be re-uploaded
        e.target.value = ''
    }, [])

    // -- Input ----------------------------------------------------------------
    const [inputDisplay,  setInputDisplay] = useState('')
    const inputValueRef  = useRef('')
    const inputFieldRef  = useRef(null)
    const handleInputChange = useCallback((e) => {
        inputValueRef.current = e.target.value
        setInputDisplay(e.target.value)
    }, [])

    // -- Abort ----------------------------------------------------------------
    const abortRef = useRef(false)

    // -- Scroll ---------------------------------------------------------------
    const messagesEndRef = useRef(null)
    const scrollTimerRef = useRef(null)
    useEffect(() => {
        if (scrollTimerRef.current) return
        scrollTimerRef.current = setTimeout(() => {
            scrollTimerRef.current = null
            requestAnimationFrame(() => {
                messagesEndRef.current?.scrollIntoView({ behavior: streamingText ? 'auto' : 'smooth' })
            })
        }, streamingText ? 80 : 0)
    }, [chatHistory, streamingText])

    // -- Sub-hooks ------------------------------------------------------------
    const { panelHeight, panelRef, onDragStart } = useDragResize()
    const { getStatus, onStageArrived, onStreamComplete, reset: resetStages } = useAgentStages()

    // -- handleSend -----------------------------------------------------------
    const handleSend = useCallback(async (forcedText = null) => {
        const text = (typeof forcedText === 'string' ? forcedText : inputValueRef.current).trim()
        if (!text || streaming) return

        if (!forcedText) {
            inputValueRef.current = ''
            setInputDisplay('')
        }

        setError(null)
        abortRef.current = false
        setHasStarted(true)
        resetStages()
        setStreamingText('')
        setStreaming(true)

        const newHistory = [...chatHistory, { role: 'user', content: text, ...(stagedFile && { fileName: stagedFile.name }) }]
        setChatHistory(newHistory)

        // Build payload — attach file info if staged
        const payload = {
            message     : text,
            chat_history: chatHistory,
            ...(stagedFile && { file_name: stagedFile.name }),
        }

        // If there's a staged file, send it via FormData
        let requestPayload = payload
        if (stagedFile) {
            const fd = new FormData()
            fd.append('file', stagedFile)
            fd.append('data', JSON.stringify(payload))
            requestPayload = fd
            setStagedFile(null)
        }

        let assistantText = ''

        try {
            await chatWithAssistant(requestPayload, (event) => {
                if (abortRef.current) return

                if (event.type === 'progress') {
                    onStageArrived(event.stage)
                    // if (event.stage === 'apex_evaluate') setStreaming(true)

                } else if (event.type === 'token') {
                    assistantText += event.content
                    setStreamingText(assistantText)

                } else if (event.type === 'done') {
                    setStreaming(false)
                    onStreamComplete()
                    setStreamingText('')
                    setChatHistory(prev => [...prev, { role: 'assistant', content: assistantText }])
                    requestAnimationFrame(() => setStreamingText(''))

                } else if (event.type === 'error') {
                    setError(event.message ?? 'An error occurred.')
                    setStreaming(false)
                }
            })
        } catch {
            setError('Could not reach the backend. Make sure the FastAPI server is running.')
            setStreaming(false)
        }
    }, [streaming, chatHistory, stagedFile, resetStages, onStageArrived, onStreamComplete])

    const handleKeyDown = useCallback((e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
    }, [handleSend])

    // -- Collapse toggle refs -------------------------------------------------
    const pipelineOpenRef = useRef(pipelineOpen)
    useEffect(() => { pipelineOpenRef.current = pipelineOpen }, [pipelineOpen])

    // -- Render ---------------------------------------------------------------
    return (
        <div style={{ width: '100vw', height: '100vh', background: C.bg, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>

            {/* Top bar */}
            <div style={{
                height     : 48,
                flexShrink : 0,
                background : C.bgCard,
                borderBottom: `1px solid ${C.border}`,
                display    : 'flex',
                alignItems : 'center',
                padding    : '0 1.5rem',
                gap        : '1rem',
            }}>
                {/* Logo */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                    <div style={{
                        width: 26, height: 26,
                        background: C.redDim,
                        border: `1px solid ${C.redGlow}`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                        <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                            <rect x="2" y="2" width="5" height="5" fill={C.red}/>
                            <rect x="9" y="2" width="5" height="5" fill={C.red} opacity="0.5"/>
                            <rect x="2" y="9" width="5" height="5" fill={C.red} opacity="0.5"/>
                            <rect x="9" y="9" width="5" height="5" fill={C.red}/>
                        </svg>
                    </div>
                    <span style={{ fontFamily: MONO, fontSize: '0.75rem', fontWeight: 700, color: C.textPrimary, letterSpacing: '0.06em', textTransform: 'uppercase', lineHeight: 1 }}>
                        Agentic Financial Platform
                    </span>
                </div>

                {/* Spacer */}
                <div style={{ flex: 1 }} />

                {/* Status badge */}
                {streaming && (
                    <div style={{
                        display: 'flex', alignItems: 'center', gap: '0.375rem',
                        padding: '0.25rem 0.625rem',
                        background: C.redDim,
                        border: `1px solid ${C.redGlow}`,
                        lineHeight: 1,
                        height: '24px',
                        boxSizing: 'border-box',
                    }}>
                        <div style={{
                            width: 6, height: 6, borderRadius: '50%', background: C.red,
                            animation: 'ap-flicker 0.8s ease-in-out infinite',
                        }} />
                        <span style={{ fontFamily: MONO, fontSize: '0.625rem', color: C.red, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                            Processing
                        </span>
                    </div>
                )}
                {!streaming && hasStarted && (
                    <span style={{ fontFamily: MONO, fontSize: '0.625rem', color: C.textHelper, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                        Ready
                    </span>
                )}

                {/* Collapse toggle with Carbon tooltip */}
                <div style={{ position: 'relative' }}>
                    <button
                        onClick={() => setPipelineOpen(p => !p)}
                        onMouseEnter={(e) => {
                            const tip = e.currentTarget.parentElement.querySelector('.ap-carbon-tip')
                            if (tip) tip.style.opacity = '1'
                        }}
                        onMouseLeave={(e) => {
                            const tip = e.currentTarget.parentElement.querySelector('.ap-carbon-tip')
                            if (tip) tip.style.opacity = '0'
                        }}
                        style={{
                            background: 'none', border: `1px solid ${C.border}`,
                            color: pipelineOpen ? C.red : C.textHelper,
                            fontFamily: MONO, fontSize: '0.625rem', letterSpacing: '0.06em',
                            textTransform: 'uppercase', padding: '0.25rem 0.625rem',
                            height: '24px', boxSizing: 'border-box',
                            cursor: 'pointer', transition: 'all 0.15s',
                            display: 'flex', alignItems: 'center', gap: '0.375rem',
                        }}
                    >
                        <span style={{ lineHeight: 1 }}>{pipelineOpen ? '<' : '>'}</span>
                        <span>Agents</span>
                    </button>
                    <div className="ap-carbon-tip" style={{
                        position: 'absolute', top: '100%', left: '50%',
                        transform: 'translateX(-50%)', marginTop: '6px',
                        background: C.bg03, border: `1px solid ${C.border}`,
                        borderLeft: `2px solid ${C.red}`,
                        padding: '0.5rem 0.75rem', whiteSpace: 'nowrap',
                        fontFamily: SANS, fontSize: '0.6875rem', color: C.textSecondary,
                        pointerEvents: 'none', opacity: 0,
                        transition: 'opacity 0.15s ease',
                        zIndex: 100,
                    }}>
                        {pipelineOpen ? 'Hide agent panel' : 'Show agent panel'}
                    </div>
                </div>
            </div>

            {/* Main panel */}
            <div
                ref={panelRef}
                style={{
                    flex: 1, display: 'flex',
                    height: `${panelHeight}px`,
                }}
            >
                {/* Agent panel -- collapsible */}
                <div style={{
                    width     : pipelineOpen ? '200px' : '0px',
                    flexShrink: 0,
                    overflow  : pipelineOpen ? 'visible' : 'hidden',
                    transition: 'width 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
                    background: C.bgCard,
                    position  : 'relative',
                    zIndex    : 10,
                }}>
                    <AgentPanel getStatus={getStatus} hasStarted={hasStarted} />
                </div>

                {/* Chat column */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden', background: C.bg }}>

                    {/* Message list */}
                    <div style={{
                        flex         : 1,
                        overflowY    : 'auto',
                        padding      : '1.5rem',
                        display      : 'flex',
                        flexDirection: 'column',
                        gap          : '0.875rem',
                        minHeight    : 0,
                    }}>
                        {chatHistory.length === 0 && !streamingText && (
                            <SuggestionChips onSelect={handleSend} />
                        )}

                        <MessageList chatHistory={chatHistory} />

                        {streamingText && !chatHistory.some(m => m.content === streamingText) && (
                            <StreamingBubble text={streamingText} isStreaming={streaming} />
                        )}

                        {error && (
                            <div style={{
                                padding   : '0.625rem 0.875rem',
                                background: 'rgba(218,30,40,0.08)',
                                borderLeft: `2px solid ${C.red}`,
                                fontSize  : '0.8125rem',
                                color     : C.red,
                                fontFamily: SANS,
                                lineHeight: 1.5,
                                animation : 'ap-fade-up 0.2s ease both',
                            }}>
                                {error}
                            </div>
                        )}

                        <div ref={messagesEndRef} />
                    </div>

                    {/* Staged file banner */}
                    <UploadBanner file={stagedFile} onClear={() => setStagedFile(null)} />

                    {/* Input area */}
                    <div style={{
                        background  : C.bgCard,
                        borderTop   : `1px solid ${C.border}`,
                        padding     : '0.875rem 1.25rem',
                        flexShrink  : 0,
                    }}>
                        <div style={{ display: 'flex', alignItems: 'stretch', gap: 0 }}>

                            {/* Upload button */}
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept=".csv,.xlsx,.xls"
                                onChange={handleFileChange}
                                style={{ display: 'none' }}
                            />
                            <button
                                className="ap-upload"
                                onClick={() => fileInputRef.current?.click()}
                                disabled={streaming}
                                title="Upload CSV or Excel file"
                                style={{
                                    background  : stagedFile ? C.redDim : C.bg02,
                                    border      : `1px solid ${stagedFile ? C.red : C.border}`,
                                    color       : stagedFile ? C.red : C.textHelper,
                                    padding     : '0 1rem',
                                    cursor      : 'pointer',
                                    display     : 'flex',
                                    alignItems  : 'center',
                                    gap         : '0.375rem',
                                    flexShrink  : 0,
                                    transition  : 'all 0.15s',
                                    opacity     : streaming ? 0.4 : 1,
                                    position    : 'relative',
                                    zIndex      : 2,
                                }}
                            >
                                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                                    <polyline points="17 8 12 3 7 8"/>
                                    <line x1="12" y1="3" x2="12" y2="15"/>
                                </svg>
                                <span style={{ fontFamily: MONO, fontSize: '0.6875rem', letterSpacing: '0.04em', whiteSpace: 'nowrap' }}>
                                    {stagedFile ? 'Ready' : 'CSV / XLS'}
                                </span>
                            </button>

                            {/* Text input */}
                            <textarea
                                ref={inputFieldRef}
                                value={inputDisplay}
                                onChange={handleInputChange}
                                onKeyDown={handleKeyDown}
                                disabled={streaming}
                                placeholder="Describe a scenario, ask about a deal, or send a message…"
                                rows={2}
                                style={{
                                    flex         : 1,
                                    background   : C.bg02,
                                    borderTop    : `1px solid ${C.border}`,
                                    borderBottom : `1px solid ${C.border}`,
                                    borderLeft   : 'none',
                                    borderRight  : 'none',
                                    color        : C.textPrimary,
                                    fontFamily   : SANS,
                                    fontSize     : '0.875rem',
                                    padding      : '0.625rem 1rem',
                                    outline      : 'none',
                                    resize       : 'none',
                                    lineHeight   : 1.5,
                                    opacity      : streaming ? 0.5 : 1,
                                    display      : 'block',
                                    position     : 'relative',
                                    zIndex       : 0,
                                }}
                            />

                            {/* Send button */}
                            <button
                                onClick={() => handleSend()}
                                disabled={(!inputDisplay.trim() && !stagedFile) || streaming}
                                style={{
                                    background  : (!inputDisplay.trim() && !stagedFile) || streaming ? C.bg03 : C.red,
                                    border      : `1px solid ${(!inputDisplay.trim() && !stagedFile) || streaming ? C.border : C.red}`,
                                    color       : '#fff',
                                    fontFamily  : MONO,
                                    fontSize    : '0.8125rem',
                                    fontWeight  : 700,
                                    letterSpacing: '0.04em',
                                    padding     : '0 1.5rem',
                                    cursor      : 'pointer',
                                    display     : 'flex',
                                    alignItems  : 'center',
                                    transition  : 'background 0.15s, border-color 0.15s',
                                    flexShrink  : 0,
                                }}
                            >
                                {streaming ? (
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ animation: 'ap-spin 1s linear infinite' }}>
                                        <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
                                    </svg>
                                ) : 'SEND'}
                            </button>
                        </div>

                        <div style={{
                            display: 'flex', justifyContent: 'flex-start', alignItems: 'center',
                            marginTop: '0.5rem',
                        }}>
                            <span style={{ fontFamily: SANS, fontSize: '0.6875rem', color: C.textHelper }}>
                                Enter to send · Shift+Enter for new line · Accepts .csv, .xlsx, .xls
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Drag-to-resize handle */}
            <div
                onMouseDown={(e) => { if (!streamingRef.current) onDragStart(e) }}
                style={{
                    height    : 6,
                    background: C.bgCard,
                    borderTop : `1px solid ${C.border}`,
                    cursor    : streaming ? 'not-allowed' : 'ns-resize',
                    display   : 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                }}
            >
                <div style={{ width: 28, height: 2, background: C.bg04, borderRadius: 1 }} />
            </div>
        </div>
    )
}
