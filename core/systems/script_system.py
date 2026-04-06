import importlib.util
import hashlib
import os
import sys
from core.ecs import System, Entity
from core.components.script import ScriptComponent
from core.logger import get_logger

class ScriptSystem(System):
    required_components = (ScriptComponent,)
    _logger = get_logger("script_system")

    def _normalize_script_path(self, script_path: str) -> str:
        return os.path.normcase(os.path.abspath(os.path.normpath(script_path)))

    def _build_module_key(self, script_path: str) -> str:
        normalized = self._normalize_script_path(script_path)
        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]
        module_base = os.path.splitext(os.path.basename(normalized))[0]
        return f"axispy_script_{module_base}_{digest}"

    def _unload_module(self, module_key: str):
        if module_key and module_key in sys.modules:
            del sys.modules[module_key]

    def unload_script(self, component: ScriptComponent):
        self._unload_module(getattr(component, "_module_key", ""))
        component.instance = None
        component.started = False
        component._module_key = ""
        component._loaded_script_path = ""
        component._loaded_class_name = ""
        component._loaded_mtime = None

    def resolve_script_path(self, script_path: str) -> str:
        if not script_path:
            return script_path
        script_path = script_path.replace("\\", os.sep).replace("/", os.sep)
        
        if os.path.isabs(script_path):
            return self._normalize_script_path(script_path)
        
        candidates = []
        
        candidates.append(os.path.normpath(os.path.join(os.getcwd(), script_path)))
        
        project_root = os.environ.get("AXISPY_PROJECT_PATH")
        if project_root:
            candidates.append(os.path.normpath(os.path.join(project_root, script_path)))
        
        engine_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        candidates.append(os.path.normpath(os.path.join(engine_root, script_path)))
        
        for candidate in candidates:
            if os.path.exists(candidate):
                return self._normalize_script_path(candidate)
        
        return script_path

    def update(self, dt: float, entities: list[Entity]):
        if self.world:
            target_entities = self.world.get_entities_with(ScriptComponent)
        else:
            target_entities = entities

        for entity in target_entities:
            script_comp = entity.get_component(ScriptComponent)
            if not script_comp:
                continue
            if not script_comp.script_path or not script_comp.class_name:
                if script_comp.instance:
                    self.unload_script(script_comp)
                continue

            resolved_path = self.resolve_script_path(script_comp.script_path)
            if not os.path.exists(resolved_path):
                if script_comp.instance:
                    self.unload_script(script_comp)
                self._logger.warning("Script file not found", script_path=script_comp.script_path, entity_id=entity.id, entity_name=entity.name)
                continue

            script_comp.script_path = resolved_path
            module_key = self._build_module_key(resolved_path)
            file_mtime = os.path.getmtime(resolved_path)
            signature_changed = (
                script_comp._loaded_script_path != resolved_path
                or script_comp._loaded_class_name != script_comp.class_name
                or script_comp._module_key != module_key
            )
            file_changed = script_comp._loaded_mtime is not None and script_comp._loaded_mtime != file_mtime
            missing_module = bool(script_comp._module_key) and script_comp._module_key not in sys.modules
            needs_load = script_comp.instance is None or signature_changed or file_changed or missing_module
            if needs_load:
                if script_comp.instance or script_comp._module_key:
                    self.unload_script(script_comp)
                self.instantiate_script(script_comp, entity, resolved_path, module_key, file_mtime)

            # Run lifecycle methods immediately after ensuring script is loaded
            if script_comp.instance:
                if not script_comp.started:
                    if hasattr(script_comp.instance, 'on_start'):
                        try:
                            script_comp.instance.on_start()
                        except Exception as e:
                            self._logger.error("Error in script on_start", script_class=script_comp.class_name, script_path=script_comp.script_path, entity_id=entity.id, error=str(e))
                    script_comp.started = True
                
                if hasattr(script_comp.instance, 'on_update'):
                    try:
                        script_comp.instance.on_update(dt)
                    except Exception as e:
                        self._logger.error("Error in script on_update", script_class=script_comp.class_name, script_path=script_comp.script_path, entity_id=entity.id, error=str(e))

                # Tick coroutines
                script_comp.tick_coroutines(dt)
                # Tick tweens
                script_comp.tick_tweens(dt)

    def instantiate_script(
        self,
        component: ScriptComponent,
        entity: Entity,
        resolved_path: str = None,
        module_key: str = None,
        file_mtime: float = None
    ):
        try:
            resolved_path = resolved_path or self.resolve_script_path(component.script_path)
            if not os.path.exists(resolved_path):
                self._logger.warning("Script file not found during instantiate", script_path=component.script_path, entity_id=entity.id, entity_name=entity.name)
                return
            
            component.script_path = resolved_path
            module_key = module_key or self._build_module_key(component.script_path)
            file_mtime = file_mtime if file_mtime is not None else os.path.getmtime(component.script_path)
            self._unload_module(module_key)
            spec = importlib.util.spec_from_file_location(module_key, component.script_path)
            if spec is None or spec.loader is None:
                self._logger.error("Failed to build script module spec", script_path=component.script_path, entity_id=entity.id)
                return
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_key] = module
            spec.loader.exec_module(module)
            
            # Get class
            if hasattr(module, component.class_name):
                cls = getattr(module, component.class_name)
                # Instantiate
                component.instance = cls()
                component.started = False
                # Inject entity reference
                component.instance.entity = entity
                # Inject logger with script name
                from core.logger import get_logger
                script_logger_name = f"script.{component.class_name}"
                component.instance.logger = get_logger(script_logger_name)
                # Inject helper methods from ScriptComponent
                component._inject_methods_to_instance()
                component._module_key = module_key
                component._loaded_script_path = component.script_path
                component._loaded_class_name = component.class_name
                component._loaded_mtime = file_mtime
                # Inject other core systems if needed? 
                # Ideally script uses 'from core.input import Input' etc.
            else:
                self._unload_module(module_key)
                self._logger.error("Script class not found", script_class=component.class_name, script_path=component.script_path, entity_id=entity.id)
                
        except Exception as e:
            self._unload_module(module_key or "")
            self._logger.error("Failed to instantiate script", script_class=component.class_name, script_path=component.script_path, entity_id=entity.id, error=str(e))
