"""Tracks AI assistant file actions for revert support."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class FileSnapshot:
    """Snapshot of a file before AI modification."""
    path: str           # Absolute path
    content: Optional[str]  # Original content, or None if file didn't exist
    existed: bool       # Whether the file existed before the action


@dataclass
class PromptActionGroup:
    """All file actions from a single AI prompt."""
    prompt_index: int
    snapshots: Dict[str, FileSnapshot] = field(default_factory=dict)
    reverted: bool = False

    @property
    def has_actions(self) -> bool:
        return len(self.snapshots) > 0


class AIActionTracker:
    """Records file snapshots before AI tool executions for revert support.

    Usage:
        tracker.begin_prompt(index)   # Before tool loop starts
        tracker.snapshot_file(path)   # Before each file write
        tracker.end_prompt()          # After tool loop completes
        tracker.revert(index)         # Restore files from prompt snapshot
    """

    def __init__(self):
        self._groups: Dict[int, PromptActionGroup] = {}
        self._current: Optional[PromptActionGroup] = None

    def begin_prompt(self, prompt_index: int):
        """Start tracking actions for a new prompt."""
        self._current = PromptActionGroup(prompt_index=prompt_index)

    def end_prompt(self):
        """Finish tracking. Store the group only if it has actions."""
        if self._current and self._current.has_actions:
            self._groups[self._current.prompt_index] = self._current
        self._current = None

    def snapshot_file(self, abs_path: str):
        """Capture file content before modification. Only snapshots once per file per prompt."""
        if self._current is None:
            return

        # Normalize path
        abs_path = os.path.normpath(abs_path)

        # Don't re-snapshot the same file within the same prompt
        if abs_path in self._current.snapshots:
            return

        if os.path.exists(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self._current.snapshots[abs_path] = FileSnapshot(
                    path=abs_path, content=content, existed=True
                )
            except Exception:
                pass
        else:
            self._current.snapshots[abs_path] = FileSnapshot(
                path=abs_path, content=None, existed=False
            )

    def revert(self, prompt_index: int) -> Dict[str, str]:
        """Revert all file changes from a prompt. Returns dict of path -> status."""
        group = self._groups.get(prompt_index)
        if not group:
            return {"error": "No actions found for this prompt."}
        if group.reverted:
            return {"error": "Already reverted."}

        results = {}
        for abs_path, snap in group.snapshots.items():
            try:
                if snap.existed:
                    # Restore original content
                    with open(abs_path, "w", encoding="utf-8") as f:
                        f.write(snap.content)
                    results[abs_path] = "restored"
                else:
                    # File was created by AI — delete it
                    if os.path.exists(abs_path):
                        os.remove(abs_path)
                        results[abs_path] = "deleted"
                    else:
                        results[abs_path] = "already_gone"
            except Exception as e:
                results[abs_path] = f"error: {e}"

        group.reverted = True
        return results

    def has_actions(self, prompt_index: int) -> bool:
        """Check if a prompt had any file-modifying actions."""
        group = self._groups.get(prompt_index)
        return group is not None and group.has_actions

    def is_reverted(self, prompt_index: int) -> bool:
        """Check if a prompt's actions have been reverted."""
        group = self._groups.get(prompt_index)
        return group is not None and group.reverted

    def get_modified_files(self, prompt_index: int) -> List[str]:
        """Get list of files modified by a prompt."""
        group = self._groups.get(prompt_index)
        if not group:
            return []
        return list(group.snapshots.keys())

    def clear(self):
        """Clear all tracked actions."""
        self._groups.clear()
        self._current = None
