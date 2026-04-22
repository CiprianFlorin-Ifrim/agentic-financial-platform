# backend/main.py
# FastAPI application entry point.
# Responsible for app initialisation, middleware configuration and router registration.
# Run with: uvicorn backend.main:app --reload  (from project root)

import os
from contextlib import asynccontextmanager
from fastapi                            import FastAPI
from fastapi.middleware.cors            import CORSMiddleware
from fastapi.middleware.gzip            import GZipMiddleware
from fastapi.openapi.docs               import get_swagger_ui_html
from fastapi.responses                  import HTMLResponse
from dotenv                             import load_dotenv

from backend.database                   import init_db
from backend.telemetry                  import init_telemetry, shutdown_telemetry
from backend.routers                    import assistant, deals, engines


# -----------------------------------------------------------------------------
# Environment
# -----------------------------------------------------------------------------

load_dotenv()


# -----------------------------------------------------------------------------
# Lifespan  (Startup / Shutdown)
# -----------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_telemetry()  # Must run before ADK agents are instantiated
    init_db()         # Create tables if they do not exist -- safe on every boot
    yield
    shutdown_telemetry()


# -----------------------------------------------------------------------------
# Application Instance
# -----------------------------------------------------------------------------

app = FastAPI(
    title     = "FAO Platform API",
    version   = "1.0.0",
    lifespan  = lifespan,
    docs_url  = None,    # Custom dark-mode docs registered below
    redoc_url = None,
)


# -----------------------------------------------------------------------------
# Middleware
# -----------------------------------------------------------------------------

# Allow the Vite dev server (port 5173) and preview (port 4173) to make
# cross-origin requests.  Tighten to a real domain in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins     = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


# -----------------------------------------------------------------------------
# Router Registration
# -----------------------------------------------------------------------------

app.include_router(assistant.router, prefix="/assistant", tags=["Assistant"])
app.include_router(deals.router,     prefix="/deals",     tags=["Deals"])
app.include_router(engines.router,   prefix="/engines",   tags=["Engines"])


# -----------------------------------------------------------------------------
# Health Check
# -----------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
def health_check():
    """Confirm the API is reachable and the database connection is alive."""
    return {"status": "ok", "service": "fao-platform"}


# -----------------------------------------------------------------------------
# Dark-Mode Swagger UI
# -----------------------------------------------------------------------------

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui():
    html = get_swagger_ui_html(
        openapi_url                  = app.openapi_url,
        title                        = app.title + " -- API Docs",
        oauth2_redirect_url          = app.swagger_ui_oauth2_redirect_url,
        swagger_js_url               = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url              = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )
    dark_css = """
    <style>
        body { background-color: #0f0f0f !important; color: #f4f4f4 !important; }
        .swagger-ui { filter: invert(88%) hue-rotate(180deg); background-color: #fafafa !important; }
        .swagger-ui .topbar { display: none; }
        #swagger-ui { background-color: #0f0f0f !important; }
    </style>
    """
    content = html.body.decode().replace("</body>", f"{dark_css}</body>")
    return HTMLResponse(content=content)
