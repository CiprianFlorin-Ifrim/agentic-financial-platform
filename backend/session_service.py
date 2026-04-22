# backend/session_service.py
# SQLiteSessionService -- ADK-compatible session service backed by SQLite.
# Replaces InMemorySessionService so conversation state survives server restarts.
#
# ADK's BaseSessionService contract requires:
#   create_session(app_name, user_id, session_id, state) -> Session
#   get_session(app_name, user_id, session_id)           -> Session
#   update_session(session)                              -> None
#   delete_session(app_name, user_id, session_id)        -> None
#
# State and events are serialised as JSON and stored in the agent_sessions table.
# On get_session, if no row exists a new empty session is created automatically.

from __future__ import annotations

import json
import base64
from typing import Any

from google.adk.sessions import BaseSessionService, Session
from backend.database    import upsert_agent_session, load_agent_session, get_connection


# -----------------------------------------------------------------------------
# Safe JSON encoder -- handles bytes and any other non-serialisable ADK types
# -----------------------------------------------------------------------------

class _SafeEncoder(json.JSONEncoder):
    """Converts bytes to base64 strings and falls back to str() for anything else."""
    def default(self, obj):
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode("ascii")
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)


# -----------------------------------------------------------------------------
# SQLiteSessionService
# -----------------------------------------------------------------------------

class SQLiteSessionService(BaseSessionService):
    """
    Persistent ADK session service using the project SQLite database.
    Thread-safe for concurrent async requests because each call opens
    its own connection via get_connection().
    """

    # -- Serialisation helpers ------------------------------------------------

    @staticmethod
    def _session_to_row(session: Session) -> tuple[str, str]:
        """Serialise a Session's state and events to JSON strings."""
        try:
            state_json = json.dumps(dict(session.state or {}), cls=_SafeEncoder)
        except (TypeError, ValueError):
            state_json = "{}"

        try:
            events = []
            for ev in (session.events or []):
                try:
                    events.append(ev.model_dump() if hasattr(ev, "model_dump") else {})
                except Exception:
                    events.append({})
            events_json = json.dumps(events, cls=_SafeEncoder)
        except (TypeError, ValueError):
            events_json = "[]"

        return state_json, events_json

    @staticmethod
    def _row_to_session(
        app_name   : str,
        user_id    : str,
        session_id : str,
        row        : dict,
    ) -> Session:
        """Reconstruct a Session from a stored database row."""
        try:
            state = json.loads(row["state_json"])
        except (json.JSONDecodeError, KeyError):
            state = {}

        # Events are not fully round-tripped (ADK event objects are complex);
        # we restore an empty list and rely on ADK to replay from the LLM.
        return Session(
            app_name   = app_name,
            user_id    = user_id,
            id         = session_id,
            state      = state,
            events     = [],
        )

    # -- BaseSessionService interface -----------------------------------------

    async def create_session(
        self,
        app_name   : str,
        user_id    : str,
        session_id : str,
        state      : dict[str, Any] | None = None,
        **kwargs,
    ) -> Session:
        """Create and persist a new session. Returns the new Session object."""
        session = Session(
            app_name = app_name,
            user_id  = user_id,
            id       = session_id,
            state    = state or {},
            events   = [],
        )
        state_json, events_json = self._session_to_row(session)
        upsert_agent_session(app_name, user_id, session_id, state_json, events_json)
        return session

    async def get_session(
        self,
        app_name   : str,
        user_id    : str,
        session_id : str,
        **kwargs,
    ) -> Session:
        """
        Retrieve a session from the database.
        Creates a new empty session if none exists (upsert semantics).
        """
        row = load_agent_session(app_name, user_id, session_id)
        if row:
            return self._row_to_session(app_name, user_id, session_id, row)

        # Auto-create on first access
        return await self.create_session(app_name, user_id, session_id)

    async def update_session(self, session: Session, **kwargs) -> None:
        """Persist updated session state after each agent turn."""
        state_json, events_json = self._session_to_row(session)
        upsert_agent_session(
            session.app_name,
            session.user_id,
            session.id,
            state_json,
            events_json,
        )

    async def delete_session(
        self,
        app_name   : str,
        user_id    : str,
        session_id : str,
        **kwargs,
    ) -> None:
        """Remove a session record from the database."""
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM agent_sessions WHERE app_name=? AND user_id=? AND session_id=?",
                (app_name, user_id, session_id),
            )

    async def list_sessions(
        self,
        app_name : str,
        user_id  : str,
        **kwargs,
    ):
        """Return all session ids for a given app and user."""
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT session_id FROM agent_sessions WHERE app_name=? AND user_id=?",
                (app_name, user_id),
            ).fetchall()
        # Return a lightweight object ADK expects -- a list of session stubs
        sessions = []
        for row in rows:
            try:
                s = await self.get_session(app_name, user_id, row["session_id"])
                sessions.append(s)
            except Exception:
                pass
        return sessions
