# Agentic Financial Platform

A multi-agent deal pricing and scenario analysis system built with Google ADK 1.31.1, FastAPI, and React. Banking professionals upload loan scenarios as CSV files and receive ranked recommendations powered by a six-agent pipeline with real-time streaming and animated agent tracing.


## Interface
<img width="1530" height="952" alt="boot" src="https://github.com/user-attachments/assets/5df5c268-6a21-4091-be4f-1ac359966836" />
<br>
<img width="1530" height="952" alt="conversation" src="https://github.com/user-attachments/assets/42e12e84-8e17-4922-94f3-f2f53ab9ba12" />


## Architecture

```
User
  |
IRIS (interface agent, gemini-3-flash)
  |
  |-- answers directly: greetings, acronyms, platform questions
  |-- transfers to FAO for pipeline tasks (sub_agents)
        |
        FAO (orchestrator, gemini-3-flash)
          |-- AgentTool -> ARIA   (gemini-3.1-flash-lite)  risk-weighted assets
          |-- AgentTool -> PRISM  (gemini-3.1-flash-lite)  revenue modelling
          |-- AgentTool -> APEX   (gemini-3.1-flash-lite)  scoring and selection
          |-- AgentTool -> NEXUS  (gemini-3.1-flash-lite)  deal persistence
```

IRIS handles conversation and routes pipeline requests to FAO via ADK's `sub_agents` mechanism (`transfer_to_agent`). FAO delegates to four specialist agents via `AgentTool`. This design gives real-time visibility into sub-agent execution in the SSE event stream while keeping conversation handling separate from pipeline logic.

Two model tiers are used: `gemini-3-flash-preview` for orchestrators (IRIS, FAO) and `gemini-3.1-flash-lite-preview` for leaf agents (ARIA, PRISM, APEX, NEXUS).


## Agents

| Agent | Role | Model Tier |
|-------|------|------------|
| IRIS  | Front-door router. Answers simple queries directly, delegates analysis to FAO. | Standard |
| FAO   | Financial Assistance Orchestrator. Runs the ARIA-PRISM-APEX pipeline for each scenario set. | Standard |
| ARIA  | Asset Risk and Impact Analyzer. Calculates RWA and capital charges using Basel III rules. | Lite |
| PRISM | Pricing and Revenue Impact Scenario Modeler. Computes NII, cost of capital, return on RWA. | Lite |
| APEX  | Assessment and Pricing EXpert. Scores and ranks scenarios, selects the best deal. | Lite |
| NEXUS | Deal and Scenario Persistence Layer. Saves and retrieves deals from SQLite. | Lite |


## Engines

ARIA and PRISM wrap deterministic calculation engines (no LLM calls):

- `backend/engines/aria.py` -- Basel III standardised approach: rating-based risk weights, collateral modifiers, product-type modifiers, tenor scaling.
- `backend/engines/prism.py` -- Revenue model: NII, cost of capital (12% hurdle), operating costs (20% of NII), return on RWA, revenue score.


## Backend

FastAPI application serving three routers:

- `POST /assistant/chat` -- SSE streaming endpoint. Accepts JSON or multipart (CSV upload). Streams progress stages and text tokens to the frontend.
- `GET /deals` and `GET /deals/{id}` -- REST endpoints for querying saved deals.
- `POST /engines/aria` and `POST /engines/prism` -- Direct engine access for testing.

Key backend components:

- `backend/config.py` -- Model configuration (STD_MODEL, LITE_MODEL).
- `backend/database.py` -- SQLite with tables: deals, scenario_runs, agent_sessions, traces, logs.
- `backend/session_service.py` -- ADK-compatible SQLiteSessionService with full BaseSessionService contract.
- `backend/telemetry.py` -- OpenTelemetry spans and Python log records written to SQLite.
- `backend/agents/csv_parser.py` -- Validates and parses uploaded CSV/Excel files into Scenario objects.


## Frontend

React/Vite single-page application with:

- Real-time SSE streaming with token-by-token text rendering.
- Animated agent trace panel showing pipeline progress (IRIS, FAO, ARIA, PRISM, APEX, NEXUS).
- CSV/Excel file upload with drag-and-drop staging.
- Markdown rendering via Streamdown with table support and CSV download.
- IBM Carbon-inspired dark theme with IBM Plex Mono/Sans typography.
- Carbon-style tooltips on agent nodes and controls.


## Project Structure

```
agentic-financial-platform/
  .env                              GOOGLE_API_KEY
  backend/
    main.py                         FastAPI entry point, telemetry init
    config.py                       STD_MODEL + LITE_MODEL
    database.py                     SQLite tables and helpers
    telemetry.py                    OpenTelemetry + logging to SQLite
    session_service.py              ADK SQLiteSessionService
    schemas.py                      Pydantic request/response models
    agents/
      interface_agent.py            IRIS
      fao_agent.py                  FAO orchestrator
      aria_agent.py                 ARIA risk agent
      prism_agent.py                PRISM revenue agent
      apex_agent.py                 APEX scoring agent
      nexus_agent.py                NEXUS persistence agent
      csv_parser.py                 CSV/Excel parser
    engines/
      aria.py                       Deterministic RWA calculator
      prism.py                      Deterministic revenue modeler
    routers/
      assistant.py                  SSE streaming endpoint
      deals.py                      REST deal queries
      engines.py                    Direct engine endpoints
  frontend/
    src/
      components/AssistantPanel.jsx Main chat and agent panel
      api.js                        SSE client
      App.jsx                       Root component
      main.jsx                      Entry point
      styles/theme.css              Design tokens
    vite.config.js                  Dev server with backend proxy
```


## Setup

Prerequisites: Python 3.11+, Node.js 18+, a Google API key with Gemini access.

Backend:

```bash
conda create -n adk-env python=3.13
conda activate adk-env
pip install google-adk fastapi uvicorn python-dotenv pandas openpyxl opentelemetry-api opentelemetry-sdk
echo "GOOGLE_API_KEY=your-key" > .env
uvicorn backend.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on localhost:5173 and proxies API requests to localhost:8000.


## Usage

1. Open localhost:5173 in a browser.
2. Ask a question ("What does ARIA stand for?") to test IRIS direct responses.
3. Upload a CSV file with columns: scenario_id, loan_amount, tenor_years, interest_rate, collateral_type, client_rating, product_type.
4. Type "Analyse all scenarios and recommend the best deal" to trigger the full pipeline.
5. Watch the agent panel animate as IRIS, FAO, ARIA, PRISM, and APEX activate in sequence.
6. Type "Save the best deal to NEXUS" to persist the result.
7. Type "Show me all saved deals" to retrieve from the database.


## CSV Format

```csv
scenario_id,loan_amount,tenor_years,interest_rate,collateral_type,client_rating,product_type
S1,5000000,5,0.045,secured,BBB,term_loan
S2,5000000,5,0.038,real_estate,A,term_loan
S3,5000000,5,0.052,unsecured,BB,revolving
```

Valid collateral types: secured, unsecured, real_estate.
Valid client ratings: AAA, AA, A, BBB, BB, B, CCC.
Valid product types: term_loan, revolving, bond.


## Telemetry

OpenTelemetry tracing and Python logging are written to the SQLite database on startup. Two tables:

- `traces` -- span ID, trace ID, parent span, name, duration, attributes, events.
- `logs` -- timestamp, level, logger, message, correlated trace/span IDs.

Query traces:

```bash
sqlite3 backend/cse_platform.db "SELECT name, duration_ms FROM traces ORDER BY recorded_at DESC LIMIT 10;"
```
