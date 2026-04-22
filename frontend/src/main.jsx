// main.jsx
// React application entry point.
// Mounts the root App component into the #root div defined in index.html.

import { StrictMode }    from 'react'
import { createRoot }    from 'react-dom/client'
import './index.css'
import './styles/theme.css'
import App               from './App.jsx'

createRoot(document.getElementById('root')).render(
    <StrictMode>
        <App />
    </StrictMode>
)
