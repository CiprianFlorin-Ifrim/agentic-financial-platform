# backend/telemetry.py
# OpenTelemetry + Python logging integration for the FAO Platform.
# Captures OTel spans and Python log records to the SQLite database.
#
# Must be initialised BEFORE any ADK imports -- ADK checks for an active
# TracerProvider at import time and emits spans into it automatically.
#
# Usage (in main.py lifespan):
#     from backend.telemetry import init_telemetry, shutdown_telemetry
#     init_telemetry()
#     ...
#     shutdown_telemetry()

import json
import sqlite3
import logging
from datetime import datetime

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.resources import Resource

from backend.database import DB_PATH


# -----------------------------------------------------------------------------
# Custom SQLite Span Exporter
# -----------------------------------------------------------------------------

class SQLiteSpanExporter(SpanExporter):
    """Exports OpenTelemetry spans to the traces table in SQLite."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def export(self, spans):
        """Write a batch of spans to the traces table."""
        try:
            conn = sqlite3.connect(self.db_path)
            for span in spans:
                duration_ms = (span.end_time - span.start_time) / 1_000_000

                attrs = dict(span.attributes) if span.attributes else {}
                events = [
                    {
                        "name": e.name,
                        "timestamp": str(e.timestamp),
                        "attributes": dict(e.attributes) if e.attributes else {},
                    }
                    for e in span.events
                ] if span.events else []

                resource = dict(span.resource.attributes) if span.resource else {}

                conn.execute(
                    """INSERT INTO traces
                       (trace_id, span_id, parent_span_id, name, kind,
                        start_time, end_time, duration_ms, status,
                        attributes, events, resource)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        format(span.context.trace_id, "032x"),
                        format(span.context.span_id, "016x"),
                        format(span.parent.span_id, "016x") if span.parent else None,
                        span.name,
                        str(span.kind),
                        str(span.start_time),
                        str(span.end_time),
                        duration_ms,
                        span.status.status_code.name if span.status else "UNSET",
                        json.dumps(attrs, default=str),
                        json.dumps(events, default=str),
                        json.dumps(resource, default=str),
                    ),
                )
            conn.commit()
            conn.close()
            return SpanExportResult.SUCCESS
        except Exception:
            return SpanExportResult.FAILURE

    def shutdown(self):
        pass


# -----------------------------------------------------------------------------
# Custom SQLite Log Handler
# -----------------------------------------------------------------------------

class SQLiteLogHandler(logging.Handler):
    """Writes Python log records to the logs table with OTel trace correlation."""

    def __init__(self, db_path: str):
        super().__init__()
        self.db_path = db_path

    def emit(self, record):
        """Write one log record to the logs table."""
        try:
            current_span = trace.get_current_span()
            ctx = current_span.get_span_context() if current_span else None
            trace_id = format(ctx.trace_id, "032x") if ctx and ctx.trace_id else None
            span_id = format(ctx.span_id, "016x") if ctx and ctx.span_id else None

            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """INSERT INTO logs
                   (timestamp, level, logger, message, trace_id, span_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    datetime.fromtimestamp(record.created).isoformat(),
                    record.levelname,
                    record.name,
                    self.format(record),
                    trace_id,
                    span_id,
                ),
            )
            conn.commit()
            conn.close()
        except Exception:
            self.handleError(record)


# -----------------------------------------------------------------------------
# Module-level state
# -----------------------------------------------------------------------------

_provider: TracerProvider | None = None
_log_handler: SQLiteLogHandler | None = None


# -----------------------------------------------------------------------------
# Public interface
# -----------------------------------------------------------------------------

def init_telemetry() -> None:
    """
    Configure OpenTelemetry tracing and Python logging to write to SQLite.
    Call this once at application startup, before any ADK agent is instantiated.
    """
    global _provider, _log_handler

    resource = Resource.create({"service.name": "fao-platform"})
    _provider = TracerProvider(resource=resource)
    _provider.add_span_processor(
        BatchSpanProcessor(SQLiteSpanExporter(DB_PATH))
    )
    trace.set_tracer_provider(_provider)

    _log_handler = SQLiteLogHandler(DB_PATH)
    _log_handler.setFormatter(
        logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
    )
    logging.getLogger().addHandler(_log_handler)

    logging.getLogger(__name__).info("telemetry initialised (traces + logs -> %s)", DB_PATH)


def shutdown_telemetry() -> None:
    """Flush remaining spans and clean up. Call on application shutdown."""
    global _provider, _log_handler

    if _provider:
        _provider.force_flush()
        _provider.shutdown()

    if _log_handler:
        logging.getLogger().removeHandler(_log_handler)

    logging.getLogger(__name__).info("telemetry shut down")
