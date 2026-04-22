// App.jsx
// Root application component.
// Renders a full-viewport charcoal dotted grid background with the
// AssistantPanel layered on top. No routing -- this is a single-page tool.

import AssistantPanel from './components/AssistantPanel.jsx'

// -- Global background style -- injected once at module load, never in render
;(() => {
    if (typeof document === 'undefined') return
    const el       = document.createElement('style')
    el.textContent = `
        html, body, #root {
            width    : 100%;
            height   : 100%;
            overflow : hidden;
        }

        /* Charcoal dotted grid -- the canvas behind the panel */
        .app-grid-bg {
            width      : 100vw;
            height     : 100vh;
            position   : relative;
            overflow   : hidden;
            background-color  : #111111;
            background-image  : radial-gradient(circle, #2a2a2a 1px, transparent 1px);
            background-size   : 22px 22px;
        }

        /* Vignette to fade the grid toward the edges */
        .app-grid-bg::before {
            content    : '';
            position   : absolute;
            inset      : 0;
            background : radial-gradient(ellipse at center,
                            transparent 40%,
                            rgba(10, 10, 10, 0.85) 100%);
            pointer-events : none;
            z-index        : 0;
        }

        /* Panel sits above the grid layer */
        .app-panel-layer {
            position : relative;
            z-index  : 1;
            width    : 100%;
            height   : 100%;
        }
    `
    document.head.appendChild(el)
})()


// -----------------------------------------------------------------------------
// App
// -----------------------------------------------------------------------------
export default function App() {
    return (
        <div className="app-grid-bg">
            <div className="app-panel-layer">
                <AssistantPanel />
            </div>
        </div>
    )
}
