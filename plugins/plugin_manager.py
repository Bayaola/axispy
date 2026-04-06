import importlib
import json
import os
import sys
from dataclasses import dataclass
from core.logger import get_logger


@dataclass
class PluginManifest:
    name: str
    version: str
    module: str
    engine_api_min: str
    engine_api_max: str
    permissions: set[str]
    enabled: bool
    path: str

class PluginManager:
    def __init__(self, plugins_dir="plugins", engine_version="1.0.0"):
        self.plugins_dir = self._resolve_plugins_dir(plugins_dir)
        self.engine_version = engine_version
        self.loaded_plugins = {}
        self._plugin_manifests = {}
        self._allowed_permissions = {
            "filesystem:read",
            "filesystem:write",
            "project:read",
            "project:write",
            "runtime:launch",
            "ui:extend",
            "network:outbound"
        }
        self._logger = get_logger("plugins")
        
    def load_all_plugins(self):
        if not os.path.exists(self.plugins_dir):
            return

        plugins_root = os.path.abspath(self.plugins_dir)
        if plugins_root not in sys.path:
            sys.path.insert(0, plugins_root)
        for item in os.listdir(self.plugins_dir):
            if os.path.isdir(os.path.join(self.plugins_dir, item)) and not item.startswith("__"):
                self.load_plugin(item)
                
    def load_plugin(self, plugin_name: str):
        plugin_path = os.path.join(self.plugins_dir, plugin_name)
        try:
            manifest = self._load_manifest(plugin_name, plugin_path)
            if manifest is None:
                return
            if not manifest.enabled:
                self._logger.info("Plugin disabled by manifest", plugin=plugin_name)
                return
            if not self._is_engine_version_compatible(manifest):
                self._logger.warning(
                    "Plugin incompatible with engine version",
                    plugin=plugin_name,
                    engine_version=self.engine_version,
                    required_min=manifest.engine_api_min,
                    required_max=manifest.engine_api_max
                )
                return
            denied_permissions = [perm for perm in manifest.permissions if perm not in self._allowed_permissions]
            if denied_permissions:
                self._logger.warning("Plugin has unsupported permissions", plugin=plugin_name, denied=denied_permissions)
                return

            module_name = manifest.module or plugin_name
            module = self._import_plugin_module(module_name, plugin_path)
            context = self._build_context(manifest)
            if hasattr(module, "register_plugin"):
                module.register_plugin(self)
            if hasattr(module, "on_load"):
                module.on_load(context)
            self.loaded_plugins[plugin_name] = module
            self._plugin_manifests[plugin_name] = manifest
            self._logger.info(
                "Plugin loaded",
                plugin=plugin_name,
                version=manifest.version,
                module=module.__name__,
                permissions=sorted(list(manifest.permissions))
            )
        except Exception as e:
            self._logger.error("Failed to load plugin", plugin=plugin_name, error=str(e))

    def unload_plugin(self, plugin_name: str):
        module = self.loaded_plugins.get(plugin_name)
        manifest = self._plugin_manifests.get(plugin_name)
        if not module:
            return
        try:
            if hasattr(module, "on_unload"):
                module.on_unload()
        except Exception as error:
            self._logger.error("Plugin unload hook failed", plugin=plugin_name, error=str(error))
        self.loaded_plugins.pop(plugin_name, None)
        self._plugin_manifests.pop(plugin_name, None)
        try:
            if module.__name__ in sys.modules:
                del sys.modules[module.__name__]
        except Exception:
            pass
        self._logger.info("Plugin unloaded", plugin=plugin_name, version=manifest.version if manifest else "")

    def notify_project_open(self, project_path: str):
        for plugin_name, module in list(self.loaded_plugins.items()):
            try:
                if hasattr(module, "on_project_open"):
                    module.on_project_open(project_path)
            except Exception as error:
                self._logger.error("Plugin project-open hook failed", plugin=plugin_name, project_path=project_path, error=str(error))
            
    def get_plugin(self, plugin_name: str):
        return self.loaded_plugins.get(plugin_name)

    def get_plugin_manifest(self, plugin_name: str):
        return self._plugin_manifests.get(plugin_name)

    def _build_context(self, manifest: PluginManifest):
        manager = self

        class PluginContext:
            def has_permission(self, permission: str):
                return permission in manifest.permissions

            @property
            def permissions(self):
                return set(manifest.permissions)

            @property
            def plugin_name(self):
                return manifest.name

            @property
            def plugin_version(self):
                return manifest.version

            @property
            def engine_version(self):
                return manager.engine_version

        return PluginContext()

    def _import_plugin_module(self, module_name: str, plugin_path: str):
        full_module = importlib.import_module(module_name)
        return full_module

    def _load_manifest(self, plugin_name: str, plugin_path: str):
        manifest_path = os.path.join(plugin_path, "plugin.json")
        if not os.path.exists(manifest_path):
            return PluginManifest(
                name=plugin_name,
                version="0.0.0",
                module=plugin_name,
                engine_api_min="0.0.0",
                engine_api_max="9999.0.0",
                permissions=set(),
                enabled=True,
                path=plugin_path
            )
        try:
            with open(manifest_path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except Exception as error:
            self._logger.error("Invalid plugin manifest", plugin=plugin_name, path=manifest_path, error=str(error))
            return None

        if not isinstance(data, dict):
            self._logger.error("Invalid plugin manifest schema", plugin=plugin_name, path=manifest_path)
            return None

        permissions = data.get("permissions", [])
        if not isinstance(permissions, list):
            permissions = []
        manifest = PluginManifest(
            name=str(data.get("name", plugin_name)),
            version=str(data.get("version", "0.0.0")),
            module=str(data.get("module", plugin_name)),
            engine_api_min=str(data.get("engine_api_min", "0.0.0")),
            engine_api_max=str(data.get("engine_api_max", "9999.0.0")),
            permissions={str(item) for item in permissions if isinstance(item, str)},
            enabled=bool(data.get("enabled", True)),
            path=plugin_path
        )
        return manifest

    def _parse_version(self, value: str):
        parts = []
        for token in str(value).split("."):
            try:
                parts.append(int(token))
            except Exception:
                parts.append(0)
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])

    def _is_engine_version_compatible(self, manifest: PluginManifest):
        current = self._parse_version(self.engine_version)
        min_required = self._parse_version(manifest.engine_api_min)
        max_allowed = self._parse_version(manifest.engine_api_max)
        return min_required <= current <= max_allowed

    def _resolve_plugins_dir(self, plugins_dir: str):
        input_dir = str(plugins_dir or "").strip() or "plugins"
        candidate_paths = []
        if os.path.isabs(input_dir):
            candidate_paths.append(input_dir)
        else:
            candidate_paths.append(os.path.abspath(input_dir))
            package_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            candidate_paths.append(os.path.join(package_root, input_dir))
            if getattr(sys, "frozen", False):
                meipass = getattr(sys, "_MEIPASS", "")
                if meipass:
                    candidate_paths.append(os.path.join(meipass, input_dir))
                executable_dir = os.path.dirname(os.path.abspath(sys.executable))
                candidate_paths.append(os.path.join(executable_dir, input_dir))
                candidate_paths.append(os.path.join(executable_dir, "_internal", input_dir))
        seen = set()
        for path in candidate_paths:
            normalized = os.path.abspath(os.path.normpath(path))
            if normalized in seen:
                continue
            seen.add(normalized)
            if os.path.isdir(normalized):
                return normalized
        return os.path.abspath(os.path.normpath(input_dir))
