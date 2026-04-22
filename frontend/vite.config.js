// vite.config.js
// Vite build configuration.
// Proxies all /api/* requests to the FastAPI backend during development
// so the frontend never has to hard-code the backend port.

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
    plugins: [react()],

    server: {
        port: 5173,
        proxy: {
            // Proxy all backend routes to FastAPI
            '/assistant': { target: 'http://127.0.0.1:8000', changeOrigin: true },
            '/deals':      { target: 'http://127.0.0.1:8000', changeOrigin: true },
            '/engines':    { target: 'http://127.0.0.1:8000', changeOrigin: true },
            '/health':     { target: 'http://127.0.0.1:8000', changeOrigin: true },
        },
    },

    build: {
        outDir:    'dist',
        sourcemap: true,
    },
})
