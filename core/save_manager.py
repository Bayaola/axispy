"""Runtime save/load system for game state (save slots).

Usage from a user script::

    from core.save_manager import SaveManager

    class MyScript:
        def on_start(self):
            # Save the current world state to slot 1
            SaveManager.save(self.entity.world, "slot1")

            # Load from slot 1 (returns a new Scene)
            scene = SaveManager.load("slot1")

            # List available saves
            saves = SaveManager.list_saves()

            # Delete a save
            SaveManager.delete("slot1")

Save files are stored under ``<project_dir>/saves/<slot_name>.sav``
as JSON, using the same codec system as ``SceneSerializer``.
"""
from __future__ import annotations
import json
import os
import time
from core.logger import get_logger

_save_logger = get_logger("save_manager")


class SaveManager:
    """Static save/load manager for runtime game state."""

    save_directory: str = "saves"

    @classmethod
    def _ensure_dir(cls, project_dir: str = ""):
        """Ensure the save directory exists."""
        save_dir = os.path.join(project_dir, cls.save_directory) if project_dir else cls.save_directory
        os.makedirs(save_dir, exist_ok=True)
        return save_dir

    @classmethod
    def save(cls, world, slot_name: str, project_dir: str = "",
             extra_data: dict | None = None) -> bool:
        """Serialize the current world state and write it to a save file.

        Args:
            world: The World instance to save.
            slot_name: Name of the save slot (used as filename).
            project_dir: Base project directory (for resolving save path).
            extra_data: Optional dict of custom game data to include.

        Returns:
            True on success, False on failure.
        """
        try:
            from core.serializer import SceneSerializer
            from core.scene import Scene

            # Build a temporary scene wrapper for the world
            scene = Scene(getattr(world, "name", "SavedScene"))
            scene.world = world

            scene_json_str = SceneSerializer.to_json(scene)
            scene_data = json.loads(scene_json_str)

            save_data = {
                "version": 1,
                "timestamp": time.time(),
                "slot": slot_name,
                "scene": scene_data,
            }
            if extra_data and isinstance(extra_data, dict):
                save_data["extra"] = extra_data

            save_dir = cls._ensure_dir(project_dir)
            file_path = os.path.join(save_dir, f"{slot_name}.sav")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2)

            _save_logger.info("Game saved", slot=slot_name, path=file_path)
            return True
        except Exception as e:
            _save_logger.error("Failed to save game", slot=slot_name, error=str(e))
            return False

    @classmethod
    def load(cls, slot_name: str, project_dir: str = ""):
        """Load a save file and return a reconstructed Scene.

        Args:
            slot_name: Name of the save slot.
            project_dir: Base project directory.

        Returns:
            A Scene object on success, or None on failure.
        """
        try:
            from core.serializer import SceneSerializer

            save_dir = cls._ensure_dir(project_dir)
            file_path = os.path.join(save_dir, f"{slot_name}.sav")
            if not os.path.exists(file_path):
                _save_logger.warning("Save file not found", slot=slot_name, path=file_path)
                return None

            with open(file_path, "r", encoding="utf-8") as f:
                save_data = json.load(f)

            scene_data = save_data.get("scene")
            if scene_data is None:
                _save_logger.error("Invalid save file — no scene data", slot=slot_name)
                return None

            scene_json_str = json.dumps(scene_data)
            scene = SceneSerializer.from_json(scene_json_str)

            _save_logger.info("Game loaded", slot=slot_name, path=file_path)
            return scene
        except Exception as e:
            _save_logger.error("Failed to load game", slot=slot_name, error=str(e))
            return None

    @classmethod
    def load_extra(cls, slot_name: str, project_dir: str = "") -> dict | None:
        """Load only the extra_data from a save file without reconstructing the scene.

        Returns:
            The extra data dict, or None if not found.
        """
        try:
            save_dir = cls._ensure_dir(project_dir)
            file_path = os.path.join(save_dir, f"{slot_name}.sav")
            if not os.path.exists(file_path):
                return None
            with open(file_path, "r", encoding="utf-8") as f:
                save_data = json.load(f)
            return save_data.get("extra")
        except Exception:
            return None

    @classmethod
    def exists(cls, slot_name: str, project_dir: str = "") -> bool:
        """Check if a save slot exists."""
        save_dir = os.path.join(project_dir, cls.save_directory) if project_dir else cls.save_directory
        return os.path.exists(os.path.join(save_dir, f"{slot_name}.sav"))

    @classmethod
    def delete(cls, slot_name: str, project_dir: str = "") -> bool:
        """Delete a save slot file.

        Returns:
            True if deleted, False if not found or error.
        """
        try:
            save_dir = os.path.join(project_dir, cls.save_directory) if project_dir else cls.save_directory
            file_path = os.path.join(save_dir, f"{slot_name}.sav")
            if os.path.exists(file_path):
                os.remove(file_path)
                _save_logger.info("Save deleted", slot=slot_name)
                return True
            return False
        except Exception as e:
            _save_logger.error("Failed to delete save", slot=slot_name, error=str(e))
            return False

    @classmethod
    def list_saves(cls, project_dir: str = "") -> list[dict]:
        """Return info about all save files in the save directory.

        Returns:
            List of dicts with ``slot``, ``timestamp``, and ``path`` keys,
            sorted by most recent first.
        """
        save_dir = os.path.join(project_dir, cls.save_directory) if project_dir else cls.save_directory
        if not os.path.isdir(save_dir):
            return []
        results = []
        for filename in os.listdir(save_dir):
            if not filename.endswith(".sav"):
                continue
            file_path = os.path.join(save_dir, filename)
            slot = filename[:-4]
            timestamp = 0.0
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                timestamp = data.get("timestamp", 0.0)
            except Exception:
                timestamp = os.path.getmtime(file_path)
            results.append({"slot": slot, "timestamp": timestamp, "path": file_path})
        results.sort(key=lambda r: r["timestamp"], reverse=True)
        return results
