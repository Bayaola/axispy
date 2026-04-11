"""Chat manager that orchestrates AI conversations with engine context."""
from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, List, Optional

from core.ai.api_index import get_engine_api_reference
from core.ai.context_builder import ContextBuilder
from core.ai.providers.base import AIProvider
from core.ai.tools import ENGINE_TOOLS, ToolExecutor
from core.ai.session_manager import SessionManager
from core.ai.action_tracker import AIActionTracker
from core.logger import get_logger

_logger = get_logger("ai.chat")

_SYSTEM_PROMPT = """You are an AI assistant integrated into the AxisPy 2D game engine editor.
Your role is to help users script their games, understand the engine API, debug issues, and suggest best practices.

Rules:
- Always provide code that is compatible with the AxisPy engine API.
- Scripts are plain Python classes. Do NOT use import statements for engine components inside scripts — they are injected automatically.
- Use `self.entity`, `self.logger`, `self.find()`, `self.tween()`, etc. — these are injected into script instances.
- When accessing components, use: `self.entity.get_component(Transform)` — the component classes are available globally in the script runtime.
- For Input, use the static class: `Input.get_key("space")`, `Input.get_axis("horizontal")`, etc.
- Keep answers concise but complete. Show working code examples.
- When the user asks about their project, use the provided project context to give specific answers.
- You have access to tools to inspect the user's project (list entities, read scripts, get entity info, etc.). Use them when the user asks about their specific project.
- When the user asks you to "script" or "create a script", use the `write_script` tool to create the actual .py file directly instead of writing code in the chat.
- When the user asks you to "create an entity" or "add a component", use the `create_entity` or `add_component_to_entity` tools to edit the scene file directly. This will make changes appear in the hierarchy/inspector panels.
- Use `modify_component` to change existing component properties on entities.
- Format code in ```python blocks.
- you have access to tool to find entities, find components, edit components, etc use them!
"""

_TOOL_CALL_MARKER = "__TOOL_CALLS__"


class ChatMessage:
    """A single message in the conversation."""
    __slots__ = ("role", "content", "timestamp", "tool_call_id", "name")

    def __init__(self, role: str, content: str, tool_call_id: str = "", name: str = ""):
        self.role = role  # "system", "user", "assistant", "tool"
        self.content = content
        self.timestamp = time.time()
        self.tool_call_id = tool_call_id
        self.name = name


class ChatManager:
    """Manages AI chat conversations with engine and project context.

    Supports an agentic tool-calling loop: when the AI returns tool calls,
    the manager executes them and feeds results back, up to max_steps.
    """

    MAX_TOOL_STEPS = 5

    def __init__(self):
        self.provider: Optional[AIProvider] = None
        self.context_builder = ContextBuilder()
        self.tool_executor = ToolExecutor()
        self.session_manager = SessionManager()
        self.action_tracker = AIActionTracker()
        self.tool_executor.action_tracker = self.action_tracker
        self.tools_enabled = True
        self.history: List[ChatMessage] = []
        self.max_history = 40  # Keep last N messages for context window
        self._prompt_index = 0  # Monotonic counter for revert tracking
        self._on_chunk: Optional[Callable[[str], None]] = None
        self._on_complete: Optional[Callable[[str], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None
        self._on_tool_call: Optional[Callable[[str, dict], None]] = None
        self._on_tool_result: Optional[Callable[[str, str], None]] = None
        self._on_session_changed: Optional[Callable[[], None]] = None

    def set_provider(self, provider: AIProvider):
        self.provider = provider

    def set_callbacks(self,
                      on_chunk: Callable[[str], None] = None,
                      on_complete: Callable[[str], None] = None,
                      on_error: Callable[[str], None] = None,
                      on_tool_call: Callable[[str, dict], None] = None,
                      on_tool_result: Callable[[str, str], None] = None,
                      on_session_changed: Callable[[], None] = None):
        """Set streaming callbacks."""
        self._on_chunk = on_chunk
        self._on_complete = on_complete
        self._on_error = on_error
        self._on_tool_call = on_tool_call
        self._on_tool_result = on_tool_result
        self._on_session_changed = on_session_changed

    def set_project_path(self, path: str):
        """Set project path for session persistence and context."""
        self.session_manager.set_project_path(path)
        self.session_manager.load()  # Load sessions from disk
        self.context_builder.set_project_path(path)
        self.tool_executor.set_project_path(path)
        self._load_from_active_session()

    def clear_history(self):
        """Clear history and active session messages."""
        self.history.clear()
        self.session_manager.clear_active_session()
        if self._on_session_changed:
            self._on_session_changed()

    def _load_from_active_session(self):
        """Load history from the active session."""
        self.history.clear()
        messages = self.session_manager.get_active_messages()
        for msg in messages:
            self.history.append(ChatMessage(
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
                tool_call_id=msg.get("tool_call_id", ""),
                name=msg.get("name", "")
            ))

    def _save_to_active_session(self):
        """Save current history to the active session."""
        if not self.session_manager.active_session_id:
            return
        self.session_manager.sessions[self.session_manager.active_session_id].messages = [
            {"role": m.role, "content": m.content, "timestamp": m.timestamp,
             "tool_call_id": m.tool_call_id, "name": m.name}
            for m in self.history
        ]
        self.session_manager.save()

    def create_new_session(self, name: str = "") -> str:
        """Create a new session and switch to it."""
        session = self.session_manager.create_session(name)
        self._load_from_active_session()
        if self._on_session_changed:
            self._on_session_changed()
        return session.id

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        result = self.session_manager.delete_session(session_id)
        if result:
            self._load_from_active_session()
            if self._on_session_changed:
                self._on_session_changed()
        return result

    def switch_session(self, session_id: str) -> bool:
        """Switch to a different session."""
        result = self.session_manager.switch_session(session_id)
        if result:
            self._load_from_active_session()
            if self._on_session_changed:
                self._on_session_changed()
        return result

    def rename_session(self, session_id: str, name: str) -> bool:
        """Rename a session."""
        return self.session_manager.rename_session(session_id, name)

    def _supports_tools(self) -> bool:
        """Check if current provider supports tool calling."""
        return self.tools_enabled and hasattr(self.provider, 'chat_with_tools')

    def send_message(self, user_message: str) -> str:
        """Send a message and get a complete response (blocking)."""
        if not self.provider:
            return "[Error] No AI provider configured. Set your API key in Project Settings > AI."
        if not self.provider.is_available():
            return "[Error] AI provider is not available. Check your API key and connection."

        self.history.append(ChatMessage("user", user_message))
        messages = self._build_messages()

        try:
            if self._supports_tools():
                return self._send_with_tool_loop(messages)

            response = self.provider.chat(messages)
            self.history.append(ChatMessage("assistant", response))
            self._trim_history()
            self._save_to_active_session()
            return response
        except Exception as e:
            error_msg = f"[Error] {e}"
            _logger.error("Chat error", error=str(e))
            return error_msg

    def _send_with_tool_loop(self, messages: List[Dict]) -> str:
        """Agentic loop: send, execute tool calls, feed results back."""
        for step in range(self.MAX_TOOL_STEPS):
            result = self.provider.chat_with_tools(messages, ENGINE_TOOLS)
            content = result.get("content", "")
            tool_calls = result.get("tool_calls")

            if not tool_calls:
                # No tool calls — final response
                self.history.append(ChatMessage("assistant", content))
                self._trim_history()
                self._save_to_active_session()
                return content

            # Append assistant message with tool calls to messages
            assistant_msg: Dict[str, Any] = {"role": "assistant", "content": content or ""}
            assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)

            # Execute each tool call and append results
            for tc in tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name", "")
                try:
                    fn_args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    fn_args = {}
                tc_id = tc.get("id", "")

                _logger.info(f"Tool call: {fn_name}({fn_args})")
                if self._on_tool_call:
                    self._on_tool_call(fn_name, fn_args)

                tool_result = self.tool_executor.execute(fn_name, fn_args)

                if self._on_tool_result:
                    self._on_tool_result(fn_name, tool_result)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": tool_result,
                })

        # Max steps exhausted
        self.history.append(ChatMessage("assistant", content))
        self._trim_history()
        self._save_to_active_session()
        return content

    def send_message_stream(self, user_message: str):
        """Send a message and stream the response via callbacks.
        Returns the full response when complete."""
        if not self.provider:
            err = "[Error] No AI provider configured. Set your API key in Project Settings > AI."
            if self._on_error:
                self._on_error(err)
            return err
        if not self.provider.is_available():
            err = "[Error] AI provider is not available. Check your API key and connection."
            if self._on_error:
                self._on_error(err)
            return err

        self._prompt_index += 1
        self.action_tracker.begin_prompt(self._prompt_index)

        self.history.append(ChatMessage("user", user_message))
        messages = self._build_messages()
        tools = ENGINE_TOOLS if self._supports_tools() else None

        result = self._stream_with_tool_loop(messages, tools)
        self.action_tracker.end_prompt()
        return result

    @property
    def current_prompt_index(self) -> int:
        """The prompt index of the most recent (or in-progress) prompt."""
        return self._prompt_index

    def revert_prompt(self, prompt_index: int) -> Dict[str, str]:
        """Revert all file changes from a specific prompt."""
        return self.action_tracker.revert(prompt_index)

    def _stream_with_tool_loop(self, messages: List[Dict], tools: Optional[List[Dict]]) -> str:
        """Stream response, handle tool calls if present, loop back."""
        for step in range(self.MAX_TOOL_STEPS):
            full_response = []
            tool_calls_json = None

            try:
                for chunk in self.provider.chat_stream(messages, tools=tools):
                    # Check for tool call marker from OpenRouter provider
                    if _TOOL_CALL_MARKER in chunk:
                        marker_idx = chunk.index(_TOOL_CALL_MARKER)
                        text_before = chunk[:marker_idx]
                        if text_before:
                            full_response.append(text_before)
                            if self._on_chunk:
                                self._on_chunk(text_before)
                        tc_data = chunk[marker_idx + len(_TOOL_CALL_MARKER):]
                        try:
                            tool_calls_json = json.loads(tc_data)
                        except json.JSONDecodeError:
                            pass
                    else:
                        full_response.append(chunk)
                        if self._on_chunk:
                            self._on_chunk(chunk)
            except Exception as e:
                error_msg = f"[Error] {e}"
                _logger.error("Chat stream error", error=str(e))
                if self._on_error:
                    self._on_error(error_msg)
                return error_msg

            content = "".join(full_response)

            if not tool_calls_json:
                # No tool calls — final response
                self.history.append(ChatMessage("assistant", content))
                self._trim_history()
                self._save_to_active_session()
                if self._on_complete:
                    self._on_complete(content)
                return content

            # Tool calls detected — execute them
            assistant_msg: Dict[str, Any] = {"role": "assistant", "content": content or ""}
            assistant_msg["tool_calls"] = tool_calls_json
            messages.append(assistant_msg)

            for tc in tool_calls_json:
                fn = tc.get("function", {})
                fn_name = fn.get("name", "")
                try:
                    fn_args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    fn_args = {}
                tc_id = tc.get("id", "")

                _logger.info(f"Tool call: {fn_name}({fn_args})")
                if self._on_tool_call:
                    self._on_tool_call(fn_name, fn_args)

                # Notify UI about tool execution
                if self._on_chunk:
                    self._on_chunk(f"\n🔧 *Using tool: {fn_name}*\n")

                tool_result = self.tool_executor.execute(fn_name, fn_args)

                if self._on_tool_result:
                    self._on_tool_result(fn_name, tool_result)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": tool_result,
                })

        # Max steps exhausted — return last content
        complete = "".join(full_response) if full_response else ""
        self.history.append(ChatMessage("assistant", complete))
        self._trim_history()
        self._save_to_active_session()
        if self._on_complete:
            self._on_complete(complete)
        return complete

    def _build_messages(self) -> List[Dict[str, str]]:
        """Build the message list with system prompt, context, and history."""
        messages = []

        # System prompt with engine API reference
        api_ref = get_engine_api_reference()
        system_content = _SYSTEM_PROMPT + "\n\n" + api_ref

        # Add project context
        project_context = self.context_builder.build_context()
        if project_context:
            system_content += "\n\n# User's Current Project Context\n" + project_context

        messages.append({"role": "system", "content": system_content})

        # Conversation history
        for msg in self.history[-self.max_history:]:
            if msg.role in ("user", "assistant"):
                messages.append({"role": msg.role, "content": msg.content})

        return messages

    def _trim_history(self):
        """Keep history within limits."""
        if len(self.history) > self.max_history * 2:
            self.history = self.history[-self.max_history:]
