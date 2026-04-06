"""Session manager for AI chat conversations — save/load to .axispy/project.ai"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any

from core.logger import get_logger

_logger = get_logger("ai.sessions")


@dataclass
class ChatSession:
    """A single conversation session."""
    id: str
    name: str
    created_at: float
    updated_at: float
    messages: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def create(cls, name: str = "New Session") -> "ChatSession":
        now = time.time()
        return cls(
            id=str(uuid.uuid4())[:8],
            name=name,
            created_at=now,
            updated_at=now,
            messages=[]
        )

    def add_message(self, role: str, content: str, **kwargs):
        """Add a message to the session."""
        msg = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
            **kwargs
        }
        self.messages.append(msg)
        self.updated_at = time.time()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ChatSession":
        return cls(**data)


class SessionManager:
    """Manages chat sessions persistence to .axispy/project.ai"""

    def __init__(self, project_path: str = ""):
        self.project_path = project_path
        self.sessions: Dict[str, ChatSession] = {}
        self.active_session_id: Optional[str] = None
        self._file_path: Optional[str] = None
        if project_path:
            self.set_project_path(project_path)

    def set_project_path(self, path: str):
        """Set the project path and compute the sessions file path."""
        self.project_path = path or ""
        if self.project_path:
            axispy_dir = os.path.join(self.project_path, ".axispy")
            self._file_path = os.path.join(axispy_dir, "project.ai")
        else:
            self._file_path = None

    def load(self) -> bool:
        """Load sessions from disk. Returns True if loaded successfully."""
        if not self._file_path or not os.path.exists(self._file_path):
            # No existing sessions — create default
            default = ChatSession.create("Default Session")
            self.sessions[default.id] = default
            self.active_session_id = default.id
            return False

        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.sessions = {}
            for sess_data in data.get("sessions", []):
                session = ChatSession.from_dict(sess_data)
                self.sessions[session.id] = session

            self.active_session_id = data.get("active_session_id")
            if not self.active_session_id or self.active_session_id not in self.sessions:
                # Fallback to first session
                if self.sessions:
                    self.active_session_id = next(iter(self.sessions.keys()))
                else:
                    default = ChatSession.create("Default Session")
                    self.sessions[default.id] = default
                    self.active_session_id = default.id

            _logger.info(f"Loaded {len(self.sessions)} chat sessions")
            return True
        except Exception as e:
            _logger.error("Failed to load sessions", error=str(e))
            # Create default on error
            default = ChatSession.create("Default Session")
            self.sessions = {default.id: default}
            self.active_session_id = default.id
            return False

    def save(self) -> bool:
        """Save sessions to disk. Returns True if saved successfully."""
        if not self._file_path:
            return False

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self._file_path), exist_ok=True)

            data = {
                "version": 1,
                "active_session_id": self.active_session_id,
                "sessions": [s.to_dict() for s in self.sessions.values()]
            }

            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return True
        except Exception as e:
            _logger.error("Failed to save sessions", error=str(e))
            return False

    # ------------------------------------------------------------------
    # Session CRUD
    # ------------------------------------------------------------------

    def create_session(self, name: str = "") -> ChatSession:
        """Create a new session and make it active."""
        if not name:
            name = f"Session {len(self.sessions) + 1}"
        session = ChatSession.create(name)
        self.sessions[session.id] = session
        self.active_session_id = session.id
        self.save()
        _logger.info(f"Created new session: {name} ({session.id})")
        return session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if deleted."""
        if session_id not in self.sessions:
            return False

        del self.sessions[session_id]

        # If we deleted the active session, switch to another
        if self.active_session_id == session_id:
            if self.sessions:
                self.active_session_id = next(iter(self.sessions.keys()))
            else:
                # Create default if none left
                default = ChatSession.create("Default Session")
                self.sessions[default.id] = default
                self.active_session_id = default.id

        self.save()
        _logger.info(f"Deleted session: {session_id}")
        return True

    def rename_session(self, session_id: str, new_name: str) -> bool:
        """Rename a session."""
        if session_id not in self.sessions:
            return False
        self.sessions[session_id].name = new_name
        self.sessions[session_id].updated_at = time.time()
        self.save()
        return True

    def switch_session(self, session_id: str) -> bool:
        """Switch to a different session."""
        if session_id not in self.sessions:
            return False
        self.active_session_id = session_id
        self.save()
        return True

    def get_active_session(self) -> Optional[ChatSession]:
        """Get the currently active session."""
        if not self.active_session_id:
            return None
        return self.sessions.get(self.active_session_id)

    def get_session_list(self) -> List[ChatSession]:
        """Get all sessions sorted by updated_at (newest first)."""
        return sorted(self.sessions.values(), key=lambda s: s.updated_at, reverse=True)

    # ------------------------------------------------------------------
    # Message operations
    # ------------------------------------------------------------------

    def add_message_to_active(self, role: str, content: str, **kwargs):
        """Add a message to the active session."""
        session = self.get_active_session()
        if not session:
            # Create default if needed
            session = self.create_session("Default Session")
        session.add_message(role, content, **kwargs)
        self.save()

    def clear_active_session(self):
        """Clear all messages from the active session."""
        session = self.get_active_session()
        if session:
            session.messages.clear()
            session.updated_at = time.time()
            self.save()

    def get_active_messages(self) -> List[Dict[str, Any]]:
        """Get messages from the active session."""
        session = self.get_active_session()
        return session.messages if session else []
