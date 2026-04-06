import pygame
import math
from PyQt6.QtWidgets import QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QSize
import qtawesome as qta
from core.scene import Scene
from core.systems import RenderSystem, AnimationSystem, ParticleSystem
from core.systems.physics_system import PhysicsSystem
from core.systems.script_system import ScriptSystem
from core.systems.ui_system import UISystem
from core.systems.timer_system import TimerSystem
from core.systems.event_dispatch_system import EventDispatchSystem
from core.systems.lighting_system import LightingSystem
from core.serializer import SceneSerializer
from core.components import Transform, CameraComponent, SpriteRenderer, BoxCollider2D, CircleCollider2D, PolygonCollider2D, TilemapComponent
from core.components.light import PointLight2D, SpotLight2D, LightOccluder2D
from core.vector import Vector2
from core.input import Input
from editor.ui.gizmo import Gizmo
from editor.undo_manager import TransformCommand, DeleteEntitiesCommand, PropertyChangeCommand, MultiPropertyChangeCommand, TilemapEditCommand

class PygameViewport(QWidget):
    entity_modified = pyqtSignal(object)
    entity_selected = pyqtSignal(object)
    entity_deleted = pyqtSignal(object)

    def __init__(self, scene: Scene, parent=None, project_config: dict | None = None):
        super().__init__(parent)
        self.scene = scene
        self.project_config = project_config or {}
        self.setMinimumSize(320, 240)
        self.bg_color = (33, 33, 33)
        self.game_resolution = (800, 600)  # Default, will be updated by load_project_settings
        
        # Accept focus so we can receive key events (Delete, Escape)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # Initialize pygame explicitly for off-screen rendering
        if not pygame.get_init():
            pygame.init()
            
        self.surface = pygame.Surface((320, 240))
        self.physics_system = PhysicsSystem()
        self.animation_system = AnimationSystem()
        self.particle_system = ParticleSystem()
        self.ui_system = UISystem()
        self.render_system = RenderSystem(self.surface)
        self.render_system.use_camera_components = False
        self.lighting_system = LightingSystem(self.surface, self.project_config)
        self.lighting_system.enabled = True
        
        # Shadow preview settings
        self.shadow_extend = 2000  # Default, will be updated from project config
        self._update_shadow_extend_from_config()
        
        # Gizmo
        self.gizmo = Gizmo()
        
        # Use a QTimer to simulate the game loop for the editor preview
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(16)  # ~60 FPS
        
        # Interaction variables
        self.dragging = False
        self.selected_entities = []
        self.transform_start_states = []
        self.gizmo_interaction_active = False
        self.physics_debug_mode = False
        self.collider_drag_state = None
        self.collider_handle_size = 18
        self.collider_handle_min_screen_distance = 88
        self.polygon_point_add_entity = None
        self._occ_point_add_entity = None  # LightOccluder2D polygon point add mode
        
        # Camera
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.camera_zoom = 1.0
        self.panning = False
        self.last_mouse_pos = None

        # Enable mouse tracking to receive mouse move events even without button press
        self.setMouseTracking(True)

        # Play-in-editor state (P11-10)
        self.simulating = False
        self._saved_scene_json: str | None = None
        self._sim_physics_system: PhysicsSystem | None = None
        self._sim_script_system: ScriptSystem | None = None
        self._sim_timer_system: TimerSystem | None = None
        self._sim_event_dispatch: EventDispatchSystem | None = None
        self._sim_accumulator: float = 0.0
        self._sim_fixed_dt: float = 1.0 / 60.0

        # Tilemap edit state
        self.tilemap_edit_mode = False
        self.tilemap_tool = "paint"
        self.tilemap_selected_tile = 1
        self.tilemap_active_layer = 0
        self.tilemap_entity = None  # Direct reference when using component UI
        self._tilemap_stroke_changes = None  # dict[(x,y)] = (old,new)
        self._tilemap_rect_start = None  # (tx, ty)

        self.setup_ui()
        self.bind_scene(self.scene)

    # --- Tilemap editor API (called by MainWindow dock) ---

    def set_tilemap_edit_mode(self, enabled: bool):
        self.tilemap_edit_mode = bool(enabled)
        if not self.tilemap_edit_mode:
            self._tilemap_stroke_changes = None
            self._tilemap_rect_start = None

    def set_tilemap_tool(self, tool_name: str):
        self.tilemap_tool = str(tool_name or "paint")

    def set_tilemap_selected_tile(self, tile_id: int):
        try:
            self.tilemap_selected_tile = int(tile_id)
        except (ValueError, TypeError):
            self.tilemap_selected_tile = 1

    def set_tilemap_entity(self, entity):
        """Set the tilemap entity for editing (used by component UI)"""
        self.tilemap_entity = entity

    def set_tilemap_active_layer(self, layer_index: int):
        try:
            self.tilemap_active_layer = max(0, int(layer_index))
        except (ValueError, TypeError):
            self.tilemap_active_layer = 0

    def bind_scene(self, scene: Scene):
        self.scene = scene
        self.render_system.surface = self.surface
        self.lighting_system.surface = self.surface
        scene.world.systems = [
            system for system in scene.world.systems
            if not isinstance(system, (PhysicsSystem, AnimationSystem, ParticleSystem, RenderSystem, UISystem, LightingSystem))
        ]
        scene.world.add_system(self.animation_system)
        scene.world.add_system(self.particle_system)
        scene.world.add_system(self.ui_system)
        scene.world.add_system(self.render_system)
        scene.world.add_system(self.lighting_system)
        self.apply_scene_view_state(getattr(scene, "editor_view_state", {}))

    def _update_shadow_extend_from_config(self):
        """Update shadow_extend from project config."""
        if self.project_config:
            lighting_cfg = self.project_config.get("lighting", {})
            self.shadow_extend = int(lighting_cfg.get("shadow_extend", 2000))
        else:
            self.shadow_extend = 2000

    def update_project_config(self, config: dict):
        """Update project config and refresh shadow_extend setting."""
        self.project_config = config or {}
        self._update_shadow_extend_from_config()
        # Also update lighting system's shadow_extend
        if self.lighting_system:
            self.lighting_system.shadow_extend = self.shadow_extend

    def setup_ui(self):
        # Create an overlay layout for the toolbar
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Top toolbar layout
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        
        # Style for toolbar buttons
        btn_style = """
            QPushButton {
                background-color: rgba(50, 50, 50, 180);
                color: white;
                border: 1px solid rgba(100, 100, 100, 180);
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(80, 80, 80, 200);
            }
            QPushButton:pressed {
                background-color: rgba(30, 30, 30, 200);
            }
            QPushButton:checked {
                background-color: rgba(60, 170, 90, 220);
                border: 1px solid rgba(120, 230, 150, 230);
            }
            QPushButton:checked:hover {
                background-color: rgba(70, 190, 100, 220);
            }
        """
        
        _icon_size = QSize(16, 16)

        # Zoom In Button
        self.btn_zoom_in = QPushButton()
        self.btn_zoom_in.setIcon(qta.icon("fa5s.search-plus", color="white"))
        self.btn_zoom_in.setIconSize(_icon_size)
        self.btn_zoom_in.setToolTip("Zoom In")
        self.btn_zoom_in.setFixedSize(30, 30)
        self.btn_zoom_in.setStyleSheet(btn_style)
        self.btn_zoom_in.clicked.connect(lambda: self.apply_zoom(1.2))
        
        # Zoom Out Button
        self.btn_zoom_out = QPushButton()
        self.btn_zoom_out.setIcon(qta.icon("fa5s.search-minus", color="white"))
        self.btn_zoom_out.setIconSize(_icon_size)
        self.btn_zoom_out.setToolTip("Zoom Out")
        self.btn_zoom_out.setFixedSize(30, 30)
        self.btn_zoom_out.setStyleSheet(btn_style)
        self.btn_zoom_out.clicked.connect(lambda: self.apply_zoom(1.0 / 1.2))
        
        # Reset View Button
        self.btn_reset_view = QPushButton()
        self.btn_reset_view.setIcon(qta.icon("fa5s.compress-arrows-alt", color="white"))
        self.btn_reset_view.setIconSize(_icon_size)
        self.btn_reset_view.setToolTip("Reset Zoom and Pan")
        self.btn_reset_view.setFixedSize(30, 30)
        self.btn_reset_view.setStyleSheet(btn_style)
        self.btn_reset_view.clicked.connect(self.reset_camera)
        
        # Gizmo Modes
        self.btn_translate = QPushButton()
        self.btn_translate.setIcon(qta.icon("fa5s.arrows-alt", color="white"))
        self.btn_translate.setIconSize(_icon_size)
        self.btn_translate.setToolTip("Translate Mode")
        self.btn_translate.setFixedSize(30, 30)
        self.btn_translate.setStyleSheet(btn_style)
        self.btn_translate.setCheckable(True)
        self.btn_translate.clicked.connect(lambda: self.set_gizmo_mode(Gizmo.MODE_TRANSLATE))

        self.btn_rotate = QPushButton()
        self.btn_rotate.setIcon(qta.icon("fa5s.sync-alt", color="white"))
        self.btn_rotate.setIconSize(_icon_size)
        self.btn_rotate.setToolTip("Rotate Mode")
        self.btn_rotate.setFixedSize(30, 30)
        self.btn_rotate.setStyleSheet(btn_style)
        self.btn_rotate.setCheckable(True)
        self.btn_rotate.clicked.connect(lambda: self.set_gizmo_mode(Gizmo.MODE_ROTATE))
        
        self.btn_scale = QPushButton()
        self.btn_scale.setIcon(qta.icon("fa5s.expand-alt", color="white"))
        self.btn_scale.setIconSize(_icon_size)
        self.btn_scale.setToolTip("Scale Mode")
        self.btn_scale.setFixedSize(30, 30)
        self.btn_scale.setStyleSheet(btn_style)
        self.btn_scale.setCheckable(True)
        self.btn_scale.clicked.connect(lambda: self.set_gizmo_mode(Gizmo.MODE_SCALE))

        self.btn_physics_debug = QPushButton()
        self.btn_physics_debug.setIcon(qta.icon("fa5s.bug", color="white"))
        self.btn_physics_debug.setIconSize(_icon_size)
        self.btn_physics_debug.setToolTip("Physics Debug Mode")
        self.btn_physics_debug.setFixedSize(30, 30)
        self.btn_physics_debug.setStyleSheet(btn_style)
        self.btn_physics_debug.setCheckable(True)
        self.btn_physics_debug.clicked.connect(self.set_physics_debug_mode)
        
        # Zoom Label
        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet("color: white; background-color: rgba(50, 50, 50, 180); border-radius: 4px; padding: 4px;")
        
        toolbar_layout.addWidget(self.btn_translate)
        toolbar_layout.addWidget(self.btn_rotate)
        toolbar_layout.addWidget(self.btn_scale)
        toolbar_layout.addWidget(self.btn_physics_debug)

        # Play-in-editor button (P11-10)
        self.btn_play = QPushButton()
        self.btn_play.setIcon(qta.icon("fa5s.play", color="white"))
        self.btn_play.setIconSize(_icon_size)
        self.btn_play.setToolTip("Play / Stop Simulation")
        self.btn_play.setFixedSize(30, 30)
        self.btn_play.setStyleSheet(btn_style)
        self.btn_play.setCheckable(True)
        self.btn_play.clicked.connect(self._toggle_simulation)
        toolbar_layout.addWidget(self.btn_play)

        toolbar_layout.addSpacing(10)
        toolbar_layout.addWidget(self.btn_zoom_out)
        toolbar_layout.addWidget(self.btn_zoom_in)
        toolbar_layout.addWidget(self.btn_reset_view)
        toolbar_layout.addWidget(self.zoom_label)
        
        main_layout.addLayout(toolbar_layout)
        main_layout.addStretch()
        self._sync_toolbar_mode_buttons()

    def update_zoom_label(self):
        if hasattr(self, 'zoom_label'):
            self.zoom_label.setText(f"{int(self.camera_zoom * 100)}%")

    def _sync_toolbar_mode_buttons(self):
        mode = self.gizmo.mode
        self.btn_translate.setChecked(mode == Gizmo.MODE_TRANSLATE)
        self.btn_rotate.setChecked(mode == Gizmo.MODE_ROTATE)
        self.btn_scale.setChecked(mode == Gizmo.MODE_SCALE)

    def set_gizmo_mode(self, mode):
        self.gizmo.set_mode(mode)
        self._sync_toolbar_mode_buttons()

    def set_physics_debug_mode(self, enabled):
        self.physics_debug_mode = bool(enabled)
        if not self.physics_debug_mode:
            self.collider_drag_state = None
        if hasattr(self, 'btn_physics_debug'):
            self.btn_physics_debug.setChecked(self.physics_debug_mode)

    def toggle_physics_debug(self):
        self.set_physics_debug_mode(not self.physics_debug_mode)

    def get_scene_view_state(self):
        return {
            "gizmo_mode": self.gizmo.mode,
            "physics_debug_mode": bool(self.physics_debug_mode),
            "camera_zoom": float(self.camera_zoom),
            "camera_x": float(self.camera_x),
            "camera_y": float(self.camera_y)
        }

    def apply_scene_view_state(self, state):
        if not isinstance(state, dict):
            return
        mode = state.get("gizmo_mode", self.gizmo.mode)
        try:
            mode = int(mode)
        except (TypeError, ValueError):
            mode = self.gizmo.mode
        if mode not in (Gizmo.MODE_TRANSLATE, Gizmo.MODE_ROTATE, Gizmo.MODE_SCALE):
            mode = Gizmo.MODE_TRANSLATE
        self.set_gizmo_mode(mode)

        zoom = state.get("camera_zoom", self.camera_zoom)
        cam_x = state.get("camera_x", self.camera_x)
        cam_y = state.get("camera_y", self.camera_y)
        try:
            zoom = float(zoom)
        except (TypeError, ValueError):
            zoom = self.camera_zoom
        try:
            cam_x = float(cam_x)
        except (TypeError, ValueError):
            cam_x = self.camera_x
        try:
            cam_y = float(cam_y)
        except (TypeError, ValueError):
            cam_y = self.camera_y

        self.camera_zoom = max(0.1, min(zoom, 10.0))
        self.camera_x = cam_x
        self.camera_y = cam_y
        if self.render_system:
            self.render_system.camera_zoom = self.camera_zoom
            self.render_system.camera_x = self.camera_x
            self.render_system.camera_y = self.camera_y
        self.update_zoom_label()

        self.set_physics_debug_mode(bool(state.get("physics_debug_mode", self.physics_debug_mode)))

    def is_polygon_point_add_active(self, entity=None):
        if entity is None:
            return self.polygon_point_add_entity is not None
        return self.polygon_point_add_entity == entity

    def start_polygon_point_add_mode(self, entity):
        if not entity:
            self.polygon_point_add_entity = None
            return
        polygon = entity.get_component(PolygonCollider2D)
        transform = entity.get_component(Transform)
        if polygon is None or transform is None:
            self.polygon_point_add_entity = None
            return
        self.polygon_point_add_entity = entity
        if entity not in self.selected_entities:
            self.selected_entities = [entity]
            self.gizmo.set_targets(self.selected_entities)
            self.entity_selected.emit(self.selected_entities)

    def stop_polygon_point_add_mode(self):
        self.polygon_point_add_entity = None

    def _add_polygon_point_from_screen(self, screen_x, screen_y):
        entity = self.polygon_point_add_entity
        if not entity:
            return False
        transform = entity.get_component(Transform)
        polygon = entity.get_component(PolygonCollider2D)
        if not transform or not polygon:
            self.stop_polygon_point_add_mode()
            return False
        world_x, world_y = self._screen_to_world(screen_x, screen_y)
        old_points = [Vector2(point.x, point.y) for point in polygon.points]
        local_x = world_x - transform.x - polygon.offset_x
        local_y = world_y - transform.y - polygon.offset_y
        new_points = [Vector2(point.x, point.y) for point in polygon.points]
        new_points.append(Vector2(local_x, local_y))
        polygon.points = new_points
        mw = self.window()
        if hasattr(mw, "undo_manager"):
            mw.undo_manager.push(PropertyChangeCommand(
                [entity],
                PolygonCollider2D,
                "points",
                [old_points],
                [Vector2(point.x, point.y) for point in new_points]
            ))
        self.entity_modified.emit(entity)
        return True

    def _add_occ_polygon_point_from_screen(self, screen_x, screen_y):
        entity = self._occ_point_add_entity
        if not entity:
            return False
        transform = entity.get_component(Transform)
        occluder = entity.get_component(LightOccluder2D)
        if not transform or not occluder or occluder.shape != "polygon":
            self._occ_point_add_entity = None
            return False
        world_x, world_y = self._screen_to_world(screen_x, screen_y)
        old_points = [Vector2(p.x, p.y) for p in occluder.points]
        local_x = world_x - transform.x - occluder.offset_x
        local_y = world_y - transform.y - occluder.offset_y
        new_points = [Vector2(p.x, p.y) for p in occluder.points]
        new_points.append(Vector2(local_x, local_y))
        occluder.points = new_points
        mw = self.window()
        if hasattr(mw, "undo_manager"):
            mw.undo_manager.push(PropertyChangeCommand(
                [entity],
                LightOccluder2D,
                "points",
                [old_points],
                [Vector2(p.x, p.y) for p in new_points]
            ))
        self.entity_modified.emit(entity)
        return True

    def apply_zoom(self, factor):
        # Zoom towards center of viewport
        center_x = self.width() / 2
        center_y = self.height() / 2
        
        world_x_before, world_y_before = self._screen_to_world(center_x, center_y)
        
        self.camera_zoom *= factor
        self.camera_zoom = max(0.1, min(self.camera_zoom, 10.0))
        
        if self.render_system:
            self.render_system.camera_zoom = self.camera_zoom
            self.render_system.camera_x = self.camera_x
            self.render_system.camera_y = self.camera_y

        world_x_after, world_y_after = self._screen_to_world(center_x, center_y)
        
        self.camera_x += (world_x_before - world_x_after)
        self.camera_y += (world_y_before - world_y_after)
        
        if self.render_system:
            self.render_system.camera_zoom = self.camera_zoom
            self.render_system.camera_x = self.camera_x
            self.render_system.camera_y = self.camera_y
            
        self.update_zoom_label()

    def reset_camera(self):
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.camera_zoom = 1.0
        
        if self.render_system:
            self.render_system.camera_zoom = self.camera_zoom
            self.render_system.camera_x = self.camera_x
            self.render_system.camera_y = self.camera_y
            
        self.update_zoom_label()

    def _toggle_simulation(self):
        if self.simulating:
            self.stop_simulation()
        else:
            self.start_simulation()

    def start_simulation(self):
        """Snapshot the scene, attach runtime systems, and begin simulating."""
        if self.simulating or not self.scene:
            return
        # Save current scene state
        self._saved_scene_json = SceneSerializer.to_json(self.scene)
        # Attach runtime systems for simulation
        self._sim_physics_system = PhysicsSystem()
        self._sim_script_system = ScriptSystem()
        self._sim_timer_system = TimerSystem()
        self._sim_event_dispatch = EventDispatchSystem()
        self.scene.world.add_system(self._sim_physics_system)
        self.scene.world.add_system(self._sim_script_system)
        self.scene.world.add_system(self._sim_timer_system)
        self.scene.world.add_system(self._sim_event_dispatch)
        # Switch render system to use camera components
        self.render_system.use_camera_components = True
        self.render_system.skip_ui_render = False
        # Clear editor camera override so lighting uses camera components
        self.lighting_system.editor_camera_x = None
        self.lighting_system.editor_camera_y = None
        self.lighting_system.editor_camera_zoom = None
        self._sim_accumulator = 0.0
        self.simulating = True
        if hasattr(self, 'btn_play'):
            self.btn_play.setChecked(True)
            self.btn_play.setIcon(qta.icon("fa5s.stop", color="#ff5555"))
            self.btn_play.setToolTip("Stop Simulation")

    def stop_simulation(self):
        """Stop simulating and restore the scene to its pre-play state."""
        if not self.simulating:
            return
        self.simulating = False
        # Remove runtime systems
        for sys in (self._sim_physics_system, self._sim_script_system,
                     self._sim_timer_system, self._sim_event_dispatch):
            if sys is not None:
                self.scene.world.remove_system(sys)
        self._sim_physics_system = None
        self._sim_script_system = None
        self._sim_timer_system = None
        self._sim_event_dispatch = None
        # Restore scene from snapshot
        if self._saved_scene_json:
            restored = SceneSerializer.from_json(self._saved_scene_json)
            self._saved_scene_json = None
            self.bind_scene(restored)
            # Notify editor to refresh
            mw = self.window()
            if mw and hasattr(mw, 'scene'):
                mw.scene = self.scene
                if hasattr(mw, 'hierarchy_dock'):
                    mw.hierarchy_dock.scene = self.scene
                    mw.hierarchy_dock.refresh()
                if hasattr(mw, 'inspector_dock'):
                    mw.inspector_dock.set_entity(None)
        # Restore editor render mode
        self.render_system.use_camera_components = False
        self.render_system.skip_ui_render = True
        self.selected_entities = []
        if hasattr(self, 'btn_play'):
            self.btn_play.setChecked(False)
            self.btn_play.setIcon(qta.icon("fa5s.play", color="white"))
            self.btn_play.setToolTip("Play Simulation")

    def update_frame(self):
        # Clear with background color
        self.surface.fill(self.bg_color)

        # P11-10: Simulation mode — run full game loop
        if self.simulating and self.scene:
            dt = 1.0 / 60.0
            self._sim_accumulator += dt
            step_count = 0
            while self._sim_accumulator >= self._sim_fixed_dt and step_count < 4:
                self.scene.world.simulate(self._sim_fixed_dt)
                self._sim_accumulator -= self._sim_fixed_dt
                step_count += 1
            self.render_system.design_size = self.game_resolution if hasattr(self, 'game_resolution') and self.game_resolution else None
            self.scene.world.render(dt, 1.0)
            self.update()
            return
        
        # Update scene (with UI rendering deferred)
        self.render_system.skip_ui_render = True
        self.render_system.design_size = self.game_resolution if hasattr(self, 'game_resolution') and self.game_resolution else None
        # Sync lighting system with editor camera
        self.lighting_system.editor_camera_x = self.camera_x
        self.lighting_system.editor_camera_y = self.camera_y
        self.lighting_system.editor_camera_zoom = self.camera_zoom
        if self.scene:
            self.scene.update(1/60.0)
            
        # Draw game resolution boundary and render UI inside it
        if hasattr(self, 'game_resolution') and self.game_resolution:
            tl_x, tl_y = self._world_to_screen(0.0, 0.0)
            br_x, br_y = self._world_to_screen(float(self.game_resolution[0]), float(self.game_resolution[1]))
            rect = pygame.Rect(
                int(min(tl_x, br_x)),
                int(min(tl_y, br_y)),
                max(1, int(abs(br_x - tl_x))),
                max(1, int(abs(br_y - tl_y)))
            )
            pygame.draw.rect(self.surface, (255, 255, 255), rect, max(1, int(2 * self.camera_zoom)))
            
            # Render UI entities inside the game resolution rect (WYSIWYG)
            if self.scene:
                self.render_system.render_ui(self.scene.world.entities, viewport_rect=rect)

        primary_capture_polygon = self._get_primary_camera_capture_polygon()
        if primary_capture_polygon:
            pygame.draw.polygon(self.surface, (255, 210, 80), primary_capture_polygon, 2)

        # Draw selection bounding box
        for entity in self.selected_entities:
            if not entity:
                continue
            transform = entity.get_component(Transform)
            sprite = entity.get_component(SpriteRenderer)
            if transform:
                # Use sprite size or default 50x50
                if sprite:
                    # sprite.width/height are already scaled (world size)
                    scaled_w = abs(sprite.width * self.camera_zoom)
                    scaled_h = abs(sprite.height * self.camera_zoom)
                else:
                    # Default 50x50 needs scaling
                    scaled_w = abs(50 * transform.scale_x * self.camera_zoom)
                    scaled_h = abs(50 * transform.scale_y * self.camera_zoom)
                
                # Calculate rotated AABB dimensions
                if transform.rotation != 0:
                    rad = math.radians(transform.rotation)
                    sin_a = abs(math.sin(rad))
                    cos_a = abs(math.cos(rad))
                    final_w = scaled_w * cos_a + scaled_h * sin_a
                    final_h = scaled_w * sin_a + scaled_h * cos_a
                else:
                    final_w = scaled_w
                    final_h = scaled_h
                
                # Screen position (center)
                screen_x, screen_y = self._world_to_screen(transform.x, transform.y)
                
                # Calculate color blending from green (0, 255, 0) to white (255, 255, 255)
                # Oscilate factor between 0.0 and 1.0
                t = pygame.time.get_ticks() / 200.0  # Adjust speed
                factor = (math.sin(t) + 1) / 2
                val = int(255 * factor)
                color = (val, 255, val)
                
                # Draw rect centered at screen_x, screen_y
                rect = pygame.Rect(0, 0, int(final_w), int(final_h))
                rect.center = (int(screen_x), int(screen_y))
                pygame.draw.rect(self.surface, color, rect, 2)

        if self.physics_debug_mode:
            self._draw_physics_debug()

        # Draw Gizmo
        gizmo_cam_x, gizmo_cam_y, gizmo_zoom = self._get_gizmo_camera()
        self.gizmo.render(self.surface, gizmo_cam_x, gizmo_cam_y, gizmo_zoom)

        # Tilemap overlays (grid + hover) in editor mode
        if self.tilemap_edit_mode:
            self._draw_tilemap_overlay()
        
        # Trigger PyQt repaint
        self.update()

    def _get_selected_tilemap_target(self):
        # First check if we have a direct tilemap entity reference (from component UI)
        if self.tilemap_entity:
            entity = self.tilemap_entity
            tilemap = entity.get_component(TilemapComponent)
            transform = entity.get_component(Transform)
            if not tilemap or not transform:
                return None
            if not tilemap.layers:
                return None
            layer_index = max(0, min(int(self.tilemap_active_layer), len(tilemap.layers) - 1))
            return entity, transform, tilemap, tilemap.layers[layer_index], layer_index
        
        # Fall back to selected entities
        if not self.selected_entities:
            return None
        if len(self.selected_entities) != 1:
            return None
        entity = self.selected_entities[0]
        if not entity:
            return None
        tilemap = entity.get_component(TilemapComponent)
        transform = entity.get_component(Transform)
        if not tilemap or not transform:
            return None
        if not tilemap.layers:
            return None
        layer_index = max(0, min(int(self.tilemap_active_layer), len(tilemap.layers) - 1))
        return entity, transform, tilemap, tilemap.layers[layer_index], layer_index

    def _world_to_tile(self, world_x: float, world_y: float, transform: Transform, tilemap: TilemapComponent):
        cell_w = max(1, int(getattr(tilemap, "cell_width", tilemap.tileset.tile_width)))
        cell_h = max(1, int(getattr(tilemap, "cell_height", tilemap.tileset.tile_height)))
        origin_x = float(transform.x)
        origin_y = float(transform.y)
        tx = int((world_x - origin_x) // cell_w)
        ty = int((world_y - origin_y) // cell_h)
        return tx, ty

    def _apply_tile_at(self, layer, tx: int, ty: int, value: int):
        # Use infinite expansion - no bounds checking needed
        old_value = layer.get_world(tx, ty)
        if int(old_value) == int(value):
            return False
        if self._tilemap_stroke_changes is None:
            self._tilemap_stroke_changes = {}
        key = (int(tx), int(ty))
        if key in self._tilemap_stroke_changes:
            old = self._tilemap_stroke_changes[key][0]
            self._tilemap_stroke_changes[key] = (old, int(value))
        else:
            self._tilemap_stroke_changes[key] = (int(old_value), int(value))
        layer.set_world(tx, ty, int(value))
        return True

    def _commit_tilemap_stroke(self, entity, layer_index: int):
        if not self._tilemap_stroke_changes:
            self._tilemap_stroke_changes = None
            return
        changes = [(x, y, old, new) for (x, y), (old, new) in self._tilemap_stroke_changes.items() if int(old) != int(new)]
        self._tilemap_stroke_changes = None
        if not changes:
            return
        mw = self.window()
        if hasattr(mw, "undo_manager"):
            mw.undo_manager.push(TilemapEditCommand(entity, layer_index, changes))

    def _flood_fill(self, layer, start_x: int, start_y: int, new_value: int):
        start_x = int(start_x)
        start_y = int(start_y)
        # Use world coordinates for infinite expansion
        target = layer.get_world(start_x, start_y)
        if int(target) == int(new_value):
            return
        stack = [(start_x, start_y)]
        visited = set()
        while stack:
            x, y = stack.pop()
            if (x, y) in visited:
                continue
            visited.add((x, y))
            if layer.get_world(x, y) != target:
                continue
            self._apply_tile_at(layer, x, y, new_value)
            # Expand in all four directions
            stack.append((x - 1, y))
            stack.append((x + 1, y))
            stack.append((x, y - 1))
            stack.append((x, y + 1))

    def _draw_tilemap_overlay(self):
        target = self._get_selected_tilemap_target()
        if not target:
            return
        entity, transform, tilemap, layer, _layer_index = target
        cell_w = max(1, int(getattr(tilemap, "cell_width", tilemap.tileset.tile_width)))
        cell_h = max(1, int(getattr(tilemap, "cell_height", tilemap.tileset.tile_height)))
        origin_x = float(transform.x)
        origin_y = float(transform.y)

        # Visible bounds in world space (approx)
        left_world, top_world = self._screen_to_world(0, 0)
        right_world, bottom_world = self._screen_to_world(self.surface.get_width(), self.surface.get_height())
        min_x = min(left_world, right_world)
        max_x = max(left_world, right_world)
        min_y = min(top_world, bottom_world)
        max_y = max(top_world, bottom_world)

        # For infinite tilemap, draw grid within visible bounds
        start_tx = int((min_x - origin_x) // cell_w) - 1
        end_tx = int((max_x - origin_x) // cell_w) + 1
        start_ty = int((min_y - origin_y) // cell_h) - 1
        end_ty = int((max_y - origin_y) // cell_h) + 1

        # Grid lines
        grid_color = (255, 255, 255, 70)
        line_w = max(1, int(1 * self.camera_zoom))
        for tx in range(start_tx, end_tx + 2):
            wx = origin_x + (tx * cell_w)
            x1, y1 = self._world_to_screen(wx, origin_y + start_ty * cell_h)
            x2, y2 = self._world_to_screen(wx, origin_y + (end_ty + 1) * cell_h)
            pygame.draw.line(self.surface, grid_color, (int(x1), int(y1)), (int(x2), int(y2)), line_w)
        for ty in range(start_ty, end_ty + 2):
            wy = origin_y + (ty * cell_h)
            x1, y1 = self._world_to_screen(origin_x + start_tx * cell_w, wy)
            x2, y2 = self._world_to_screen(origin_x + (end_tx + 1) * cell_w, wy)
            pygame.draw.line(self.surface, grid_color, (int(x1), int(y1)), (int(x2), int(y2)), line_w)

        # Hover cell highlight
        if self.last_mouse_pos:
            world_x, world_y = self._screen_to_world(self.last_mouse_pos.x(), self.last_mouse_pos.y())
            tx, ty = self._world_to_tile(world_x, world_y, transform, tilemap)
            wx0 = origin_x + tx * cell_w
            wy0 = origin_y + ty * cell_h
            sx0, sy0 = self._world_to_screen(wx0, wy0)
            sx1, sy1 = self._world_to_screen(wx0 + cell_w, wy0 + cell_h)
            rect = pygame.Rect(
                int(min(sx0, sx1)),
                int(min(sy0, sy1)),
                max(1, int(abs(sx1 - sx0))),
                max(1, int(abs(sy1 - sy0))),
            )
            hover_color = (255, 255, 100, 40)
            pygame.draw.rect(self.surface, hover_color, rect, max(1, int(2 * self.camera_zoom)))

    def _get_primary_camera_capture_polygon(self):
        if not self.scene or not self.scene.world:
            return None
        camera_entries = []
        for entity in self.scene.world.entities:
            transform = entity.get_component(Transform)
            camera = entity.get_component(CameraComponent)
            if not transform or not camera or not camera.active:
                continue
            if camera.viewport_width <= 0 or camera.viewport_height <= 0:
                continue
            camera_entries.append((transform, camera))
        if not camera_entries:
            return None
        camera_entries.sort(key=lambda item: item[1].priority)
        transform, camera = camera_entries[0]

        render_w = int(self.game_resolution[0]) if self.game_resolution else self.surface.get_width()
        render_h = int(self.game_resolution[1]) if self.game_resolution else self.surface.get_height()
        viewport_w_px = max(1.0, float(render_w) * max(0.0, min(1.0, float(camera.viewport_width))))
        viewport_h_px = max(1.0, float(render_h) * max(0.0, min(1.0, float(camera.viewport_height))))
        camera_zoom = max(0.01, float(camera.zoom))

        world_w = viewport_w_px / camera_zoom
        world_h = viewport_h_px / camera_zoom
        half_w = world_w * 0.5
        half_h = world_h * 0.5

        angle_rad = math.radians(float(transform.rotation) + float(camera.rotation))
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        center_x = float(transform.x)
        center_y = float(transform.y)
        local_corners = [
            (-half_w, -half_h),
            (half_w, -half_h),
            (half_w, half_h),
            (-half_w, half_h)
        ]
        screen_points = []
        for local_x, local_y in local_corners:
            world_x = center_x + (local_x * cos_a) - (local_y * sin_a)
            world_y = center_y + (local_x * sin_a) + (local_y * cos_a)
            screen_x, screen_y = self._world_to_screen(world_x, world_y)
            screen_points.append((int(screen_x), int(screen_y)))
        if len(screen_points) != 4:
            return None
        return screen_points

    def _get_gizmo_camera(self):
        zoom = max(0.1, float(self.camera_zoom))
        center_x = self.surface.get_width() * 0.5
        center_y = self.surface.get_height() * 0.5
        return (
            self.camera_x - (center_x / zoom),
            self.camera_y - (center_y / zoom),
            zoom
        )

    def resizeEvent(self, event):
        # Resize internal pygame surface
        w, h = event.size().width(), event.size().height()
        if w > 0 and h > 0:
            self.surface = pygame.Surface((w, h))
            # Update the render system and lighting system with the new surface
            if self.render_system:
                self.render_system.surface = self.surface
            if self.lighting_system:
                self.lighting_system.surface = self.surface
        super().resizeEvent(event)

    def paintEvent(self, event):
        # Convert pygame surface to QImage
        w, h = self.surface.get_width(), self.surface.get_height()
        # Use tostring to ensure consistent format
        data = pygame.image.tostring(self.surface, 'RGB')
        # QImage needs bytesPerLine for packed RGB data (width * 3)
        image = QImage(data, w, h, w * 3, QImage.Format.Format_RGB888)
        
        # Draw onto the widget
        painter = QPainter(self)
        painter.drawImage(0, 0, image)

    def _screen_to_world(self, screen_x, screen_y):
        if self.render_system and self.scene and self.scene.world:
            return self.render_system.screen_to_world(
                screen_x,
                screen_y,
                entities=self.scene.world.entities
            )
        return (
            (screen_x / self.camera_zoom) + self.camera_x,
            (screen_y / self.camera_zoom) + self.camera_y
        )

    def _world_to_screen(self, world_x, world_y):
        if self.render_system and self.scene and self.scene.world:
            return self.render_system.world_to_screen(
                world_x,
                world_y,
                entities=self.scene.world.entities
            )
        return (
            (world_x - self.camera_x) * self.camera_zoom,
            (world_y - self.camera_y) * self.camera_zoom
        )

    def _build_collider_handles(self):
        handles = []
        for entity in self.selected_entities:
            transform = entity.get_component(Transform)
            if not transform:
                continue

            box = entity.get_component(BoxCollider2D)
            circle = entity.get_component(CircleCollider2D)
            polygon = entity.get_component(PolygonCollider2D)
            occluder = entity.get_component(LightOccluder2D)
            spot_light = entity.get_component(SpotLight2D)
            if not box and not circle and not polygon and not occluder and not spot_light:
                continue

            # Detect if both collider and occluder exist on same entity to offset handles
            has_collider = box or circle or polygon
            has_occluder = occluder is not None
            collider_offset_angle = 45 if (has_collider and has_occluder) else 0
            occluder_offset_angle = 225 if (has_collider and has_occluder) else 0
            collider_offset_dist = 12 if (has_collider and has_occluder) else 0
            occluder_offset_dist = 12 if (has_collider and has_occluder) else 0

            if box:
                center_x = transform.x + box.offset_x
                center_y = transform.y + box.offset_y
                half_w = max(0.5, abs(box.width) * 0.5)
                half_h = max(0.5, abs(box.height) * 0.5)
                handle_defs = [
                    ("width", 1, center_x + half_w, center_y),
                    ("width", -1, center_x - half_w, center_y),
                    ("height", 1, center_x, center_y + half_h),
                    ("height", -1, center_x, center_y - half_h),
                ]
                for attr, direction, world_x, world_y in handle_defs:
                    screen_x, screen_y = self._world_to_screen(world_x, world_y)
                    center_screen_x, center_screen_y = self._world_to_screen(center_x, center_y)
                    dx = screen_x - center_screen_x
                    dy = screen_y - center_screen_y
                    distance = math.hypot(dx, dy)
                    if distance < self.collider_handle_min_screen_distance:
                        if distance == 0:
                            if attr == "width":
                                dx = direction
                                dy = 0
                            else:
                                dx = 0
                                dy = direction
                            distance = 1.0
                        scale = self.collider_handle_min_screen_distance / distance
                        screen_x = center_screen_x + (dx * scale)
                        screen_y = center_screen_y + (dy * scale)
                    # Apply collider offset if both collider and occluder exist
                    if collider_offset_dist > 0:
                        offset_rad = math.radians(collider_offset_angle)
                        screen_x += math.cos(offset_rad) * collider_offset_dist
                        screen_y += math.sin(offset_rad) * collider_offset_dist
                    handles.append({
                        "entity": entity,
                        "component": box,
                        "component_type": BoxCollider2D,
                        "attr": attr,
                        "direction": direction,
                        "center_x": center_x,
                        "center_y": center_y,
                        "screen_x": screen_x,
                        "screen_y": screen_y
                    })
                center_screen_x, center_screen_y = self._world_to_screen(center_x, center_y)
                move_offset = self.collider_handle_min_screen_distance * 0.75
                offset_sx = center_screen_x - move_offset
                offset_sy = center_screen_y - move_offset
                # Apply collider offset if both collider and occluder exist
                if collider_offset_dist > 0:
                    offset_rad = math.radians(collider_offset_angle)
                    offset_sx += math.cos(offset_rad) * collider_offset_dist
                    offset_sy += math.sin(offset_rad) * collider_offset_dist
                handles.append({
                    "entity": entity,
                    "transform": transform,
                    "component": box,
                    "component_type": BoxCollider2D,
                    "attr": "offset",
                    "direction": 0,
                    "center_x": center_x,
                    "center_y": center_y,
                    "screen_x": offset_sx,
                    "screen_y": offset_sy
                })
                # Rotation handle for box
                rot_offset = self.collider_handle_min_screen_distance * 1.2
                rot_sx = center_screen_x + rot_offset
                rot_sy = center_screen_y
                # Apply collider offset if both collider and occluder exist
                if collider_offset_dist > 0:
                    offset_rad = math.radians(collider_offset_angle)
                    rot_sx += math.cos(offset_rad) * collider_offset_dist
                    rot_sy += math.sin(offset_rad) * collider_offset_dist
                handles.append({
                    "entity": entity,
                    "transform": transform,
                    "component": box,
                    "component_type": BoxCollider2D,
                    "attr": "rotation",
                    "direction": 0,
                    "center_x": center_x,
                    "center_y": center_y,
                    "screen_x": rot_sx,
                    "screen_y": rot_sy
                })

            if circle:
                center_x = transform.x + circle.offset_x
                center_y = transform.y + circle.offset_y
                radius = max(0.5, abs(circle.radius))
                handle_defs = [
                    ("radius", 1, center_x + radius, center_y),
                    ("radius", -1, center_x - radius, center_y),
                    ("radius", 1, center_x, center_y + radius),
                    ("radius", -1, center_x, center_y - radius),
                ]
                for _, direction, world_x, world_y in handle_defs:
                    screen_x, screen_y = self._world_to_screen(world_x, world_y)
                    center_screen_x, center_screen_y = self._world_to_screen(center_x, center_y)
                    dx = screen_x - center_screen_x
                    dy = screen_y - center_screen_y
                    distance = math.hypot(dx, dy)
                    if distance < self.collider_handle_min_screen_distance:
                        if distance == 0:
                            dx = direction
                            dy = 0
                            distance = 1.0
                        scale = self.collider_handle_min_screen_distance / distance
                        screen_x = center_screen_x + (dx * scale)
                        screen_y = center_screen_y + (dy * scale)
                    # Apply collider offset if both collider and occluder exist
                    if collider_offset_dist > 0:
                        offset_rad = math.radians(collider_offset_angle)
                        screen_x += math.cos(offset_rad) * collider_offset_dist
                        screen_y += math.sin(offset_rad) * collider_offset_dist
                    handles.append({
                        "entity": entity,
                        "component": circle,
                        "component_type": CircleCollider2D,
                        "attr": "radius",
                        "direction": direction,
                        "center_x": center_x,
                        "center_y": center_y,
                        "screen_x": screen_x,
                        "screen_y": screen_y
                    })
                center_screen_x, center_screen_y = self._world_to_screen(center_x, center_y)
                move_offset = self.collider_handle_min_screen_distance * 0.75
                offset_sx = center_screen_x - move_offset
                offset_sy = center_screen_y - move_offset
                # Apply collider offset if both collider and occluder exist
                if collider_offset_dist > 0:
                    offset_rad = math.radians(collider_offset_angle)
                    offset_sx += math.cos(offset_rad) * collider_offset_dist
                    offset_sy += math.sin(offset_rad) * collider_offset_dist
                handles.append({
                    "entity": entity,
                    "transform": transform,
                    "component": circle,
                    "component_type": CircleCollider2D,
                    "attr": "offset",
                    "direction": 0,
                    "center_x": center_x,
                    "center_y": center_y,
                    "screen_x": offset_sx,
                    "screen_y": offset_sy
                })
                # Rotation handle for circle
                rot_offset = self.collider_handle_min_screen_distance * 1.2
                rot_sx = center_screen_x + rot_offset
                rot_sy = center_screen_y
                # Apply collider offset if both collider and occluder exist
                if collider_offset_dist > 0:
                    offset_rad = math.radians(collider_offset_angle)
                    rot_sx += math.cos(offset_rad) * collider_offset_dist
                    rot_sy += math.sin(offset_rad) * collider_offset_dist
                handles.append({
                    "entity": entity,
                    "transform": transform,
                    "component": circle,
                    "component_type": CircleCollider2D,
                    "attr": "rotation",
                    "direction": 0,
                    "center_x": center_x,
                    "center_y": center_y,
                    "screen_x": rot_sx,
                    "screen_y": rot_sy
                })
            if polygon:
                points = polygon.points
                if len(points) >= 3:
                    world_points = [
                        (transform.x + polygon.offset_x + point.x, transform.y + polygon.offset_y + point.y)
                        for point in points
                    ]
                    center_x = sum(point[0] for point in world_points) / len(world_points)
                    center_y = sum(point[1] for point in world_points) / len(world_points)
                    for index, (world_x, world_y) in enumerate(world_points):
                        screen_x, screen_y = self._world_to_screen(world_x, world_y)
                        # Apply collider offset if both collider and occluder exist
                        if collider_offset_dist > 0:
                            offset_rad = math.radians(collider_offset_angle)
                            screen_x += math.cos(offset_rad) * collider_offset_dist
                            screen_y += math.sin(offset_rad) * collider_offset_dist
                        handles.append({
                            "entity": entity,
                            "transform": transform,
                            "component": polygon,
                            "component_type": PolygonCollider2D,
                            "attr": "point",
                            "point_index": index,
                            "direction": 0,
                            "center_x": center_x,
                            "center_y": center_y,
                            "screen_x": screen_x,
                            "screen_y": screen_y
                        })
                    center_screen_x, center_screen_y = self._world_to_screen(center_x, center_y)
                    move_offset = self.collider_handle_min_screen_distance * 0.75
                    offset_sx = center_screen_x - move_offset
                    offset_sy = center_screen_y - move_offset
                    # Apply collider offset if both collider and occluder exist
                    if collider_offset_dist > 0:
                        offset_rad = math.radians(collider_offset_angle)
                        offset_sx += math.cos(offset_rad) * collider_offset_dist
                        offset_sy += math.sin(offset_rad) * collider_offset_dist
                    handles.append({
                        "entity": entity,
                        "transform": transform,
                        "component": polygon,
                        "component_type": PolygonCollider2D,
                        "attr": "offset",
                        "direction": 0,
                        "center_x": center_x,
                        "center_y": center_y,
                        "screen_x": offset_sx,
                        "screen_y": offset_sy
                    })
                    # Rotation handle for polygon
                    rot_offset = self.collider_handle_min_screen_distance * 1.2
                    rot_sx = center_screen_x + rot_offset
                    rot_sy = center_screen_y
                    # Apply collider offset if both collider and occluder exist
                    if collider_offset_dist > 0:
                        offset_rad = math.radians(collider_offset_angle)
                        rot_sx += math.cos(offset_rad) * collider_offset_dist
                        rot_sy += math.sin(offset_rad) * collider_offset_dist
                    handles.append({
                        "entity": entity,
                        "transform": transform,
                        "component": polygon,
                        "component_type": PolygonCollider2D,
                        "attr": "rotation",
                        "direction": 0,
                        "center_x": center_x,
                        "center_y": center_y,
                        "screen_x": rot_sx,
                        "screen_y": rot_sy
                    })

            # LightOccluder2D handles
            occluder = entity.get_component(LightOccluder2D)
            if occluder:
                center_x = transform.x + occluder.offset_x
                center_y = transform.y + occluder.offset_y
                if occluder.shape == "box":
                    half_w = max(0.5, abs(occluder.width) * 0.5)
                    half_h = max(0.5, abs(occluder.height) * 0.5)
                    handle_defs = [
                        ("width", 1, center_x + half_w, center_y),
                        ("width", -1, center_x - half_w, center_y),
                        ("height", 1, center_x, center_y + half_h),
                        ("height", -1, center_x, center_y - half_h),
                    ]
                    for attr, direction, world_x, world_y in handle_defs:
                        screen_x, screen_y = self._world_to_screen(world_x, world_y)
                        center_screen_x, center_screen_y = self._world_to_screen(center_x, center_y)
                        dx = screen_x - center_screen_x
                        dy = screen_y - center_screen_y
                        distance = math.hypot(dx, dy)
                        if distance < self.collider_handle_min_screen_distance:
                            if distance == 0:
                                if attr == "width":
                                    dx = direction
                                    dy = 0
                                else:
                                    dx = 0
                                    dy = direction
                                distance = 1.0
                            scale = self.collider_handle_min_screen_distance / distance
                            screen_x = center_screen_x + (dx * scale)
                            screen_y = center_screen_y + (dy * scale)
                        # Apply occluder offset if both collider and occluder exist
                        if occluder_offset_dist > 0:
                            offset_rad = math.radians(occluder_offset_angle)
                            screen_x += math.cos(offset_rad) * occluder_offset_dist
                            screen_y += math.sin(offset_rad) * occluder_offset_dist
                        handles.append({
                            "entity": entity,
                            "component": occluder,
                            "component_type": LightOccluder2D,
                            "attr": attr,
                            "direction": direction,
                            "center_x": center_x,
                            "center_y": center_y,
                            "screen_x": screen_x,
                            "screen_y": screen_y
                        })
                elif occluder.shape == "circle":
                    occ_radius = max(0.5, abs(occluder.radius))
                    handle_defs = [
                        ("radius", 1, center_x + occ_radius, center_y),
                        ("radius", -1, center_x - occ_radius, center_y),
                        ("radius", 1, center_x, center_y + occ_radius),
                        ("radius", -1, center_x, center_y - occ_radius),
                    ]
                    for _, direction, world_x, world_y in handle_defs:
                        screen_x, screen_y = self._world_to_screen(world_x, world_y)
                        center_screen_x, center_screen_y = self._world_to_screen(center_x, center_y)
                        dx = screen_x - center_screen_x
                        dy = screen_y - center_screen_y
                        distance = math.hypot(dx, dy)
                        if distance < self.collider_handle_min_screen_distance:
                            if distance == 0:
                                dx = direction
                                dy = 0
                                distance = 1.0
                            scale = self.collider_handle_min_screen_distance / distance
                            screen_x = center_screen_x + (dx * scale)
                            screen_y = center_screen_y + (dy * scale)
                        # Apply occluder offset if both collider and occluder exist
                        if occluder_offset_dist > 0:
                            offset_rad = math.radians(occluder_offset_angle)
                            screen_x += math.cos(offset_rad) * occluder_offset_dist
                            screen_y += math.sin(offset_rad) * occluder_offset_dist
                        handles.append({
                            "entity": entity,
                            "component": occluder,
                            "component_type": LightOccluder2D,
                            "attr": "radius",
                            "direction": direction,
                            "center_x": center_x,
                            "center_y": center_y,
                            "screen_x": screen_x,
                            "screen_y": screen_y
                        })
                elif occluder.shape == "polygon" and len(occluder.points) >= 3:
                    world_points = [
                        (transform.x + occluder.offset_x + p.x, transform.y + occluder.offset_y + p.y)
                        for p in occluder.points
                    ]
                    center_x = sum(p[0] for p in world_points) / len(world_points)
                    center_y = sum(p[1] for p in world_points) / len(world_points)
                    for index, (world_x, world_y) in enumerate(world_points):
                        screen_x, screen_y = self._world_to_screen(world_x, world_y)
                        # Apply occluder offset if both collider and occluder exist
                        if occluder_offset_dist > 0:
                            offset_rad = math.radians(occluder_offset_angle)
                            screen_x += math.cos(offset_rad) * occluder_offset_dist
                            screen_y += math.sin(offset_rad) * occluder_offset_dist
                        handles.append({
                            "entity": entity,
                            "transform": transform,
                            "component": occluder,
                            "component_type": LightOccluder2D,
                            "attr": "point",
                            "point_index": index,
                            "direction": 0,
                            "center_x": center_x,
                            "center_y": center_y,
                            "screen_x": screen_x,
                            "screen_y": screen_y
                        })

                # Offset handle for all occluder shapes
                center_screen_x, center_screen_y = self._world_to_screen(center_x, center_y)
                move_offset = self.collider_handle_min_screen_distance * 0.75
                offset_sx = center_screen_x - move_offset
                offset_sy = center_screen_y - move_offset
                # Apply occluder offset if both collider and occluder exist
                if occluder_offset_dist > 0:
                    offset_rad = math.radians(occluder_offset_angle)
                    offset_sx += math.cos(offset_rad) * occluder_offset_dist
                    offset_sy += math.sin(offset_rad) * occluder_offset_dist
                handles.append({
                    "entity": entity,
                    "transform": transform,
                    "component": occluder,
                    "component_type": LightOccluder2D,
                    "attr": "offset",
                    "direction": 0,
                    "center_x": center_x,
                    "center_y": center_y,
                    "screen_x": offset_sx,
                    "screen_y": offset_sy
                })
                # Rotation handle for occluder
                rot_offset = self.collider_handle_min_screen_distance * 1.2
                rot_sx = center_screen_x + rot_offset
                rot_sy = center_screen_y
                # Apply occluder offset if both collider and occluder exist
                if occluder_offset_dist > 0:
                    offset_rad = math.radians(occluder_offset_angle)
                    rot_sx += math.cos(offset_rad) * occluder_offset_dist
                    rot_sy += math.sin(offset_rad) * occluder_offset_dist
                handles.append({
                    "entity": entity,
                    "transform": transform,
                    "component": occluder,
                    "component_type": LightOccluder2D,
                    "attr": "rotation",
                    "direction": 0,
                    "center_x": center_x,
                    "center_y": center_y,
                    "screen_x": rot_sx,
                    "screen_y": rot_sy
                })

            # SpotLight2D handles: angle, cone_angle, offset
            if spot_light:
                sl_cx = transform.x + spot_light.offset_x
                sl_cy = transform.y + spot_light.offset_y
                sl_screen_cx, sl_screen_cy = self._world_to_screen(sl_cx, sl_cy)
                sl_radius_screen = max(self.collider_handle_min_screen_distance, spot_light.radius * self.camera_zoom)

                # Angle handle — placed at the tip of the direction vector
                angle_rad = math.radians(spot_light.angle)
                angle_hx = sl_screen_cx + math.cos(angle_rad) * sl_radius_screen
                angle_hy = sl_screen_cy + math.sin(angle_rad) * sl_radius_screen
                handles.append({
                    "entity": entity,
                    "transform": transform,
                    "component": spot_light,
                    "component_type": SpotLight2D,
                    "attr": "angle",
                    "direction": 0,
                    "center_x": sl_cx,
                    "center_y": sl_cy,
                    "screen_x": angle_hx,
                    "screen_y": angle_hy
                })

                # Cone angle handles — placed at the edges of the cone
                half_cone = spot_light.cone_angle
                for cone_dir in (1, -1):
                    cone_edge_rad = math.radians(spot_light.angle + half_cone * cone_dir)
                    cone_dist = sl_radius_screen * 0.7
                    cone_hx = sl_screen_cx + math.cos(cone_edge_rad) * cone_dist
                    cone_hy = sl_screen_cy + math.sin(cone_edge_rad) * cone_dist
                    handles.append({
                        "entity": entity,
                        "transform": transform,
                        "component": spot_light,
                        "component_type": SpotLight2D,
                        "attr": "cone_angle",
                        "direction": cone_dir,
                        "center_x": sl_cx,
                        "center_y": sl_cy,
                        "screen_x": cone_hx,
                        "screen_y": cone_hy
                    })

                # Offset handle — at the center of the light
                move_offset = self.collider_handle_min_screen_distance * 0.75
                handles.append({
                    "entity": entity,
                    "transform": transform,
                    "component": spot_light,
                    "component_type": SpotLight2D,
                    "attr": "offset",
                    "direction": 0,
                    "center_x": sl_cx,
                    "center_y": sl_cy,
                    "screen_x": sl_screen_cx - move_offset,
                    "screen_y": sl_screen_cy - move_offset
                })

        return handles

    def _draw_physics_debug(self):
        selected_collider_color = (255, 230, 80)
        handle_color = (255, 130, 80)
        move_handle_color = (90, 245, 120)
        rotation_handle_color = (255, 200, 100)

        handles = self._build_collider_handles()

        for entity in self.selected_entities:
            transform = entity.get_component(Transform)
            if not transform:
                continue

            box = entity.get_component(BoxCollider2D)
            circle = entity.get_component(CircleCollider2D)
            polygon = entity.get_component(PolygonCollider2D)
            occluder = entity.get_component(LightOccluder2D)
            spot_light = entity.get_component(SpotLight2D)
            if not box and not circle and not polygon and not occluder and not spot_light:
                continue

            color = selected_collider_color

            if box:
                center_x = transform.x + box.offset_x
                center_y = transform.y + box.offset_y
                half_w = max(0.5, abs(box.width) * 0.5)
                half_h = max(0.5, abs(box.height) * 0.5)
                # Apply component rotation
                total_rot = (transform.rotation + box.rotation) % 360
                if abs(total_rot) < 0.001 or abs(total_rot - 360) < 0.001:
                    # Axis-aligned
                    left_top = self._world_to_screen(center_x - half_w, center_y - half_h)
                    right_bottom = self._world_to_screen(center_x + half_w, center_y + half_h)
                    rect = pygame.Rect(
                        int(min(left_top[0], right_bottom[0])),
                        int(min(left_top[1], right_bottom[1])),
                        max(1, int(abs(right_bottom[0] - left_top[0]))),
                        max(1, int(abs(right_bottom[1] - left_top[1])))
                    )
                    pygame.draw.rect(self.surface, color, rect, 2)
                else:
                    # Rotated box
                    rad = math.radians(total_rot)
                    cos_a = math.cos(rad)
                    sin_a = math.sin(rad)
                    corners = [(-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h)]
                    screen_pts = []
                    for lx, ly in corners:
                        rx = lx * cos_a - ly * sin_a + center_x
                        ry = lx * sin_a + ly * cos_a + center_y
                        sx, sy = self._world_to_screen(rx, ry)
                        screen_pts.append((int(sx), int(sy)))
                    if len(screen_pts) >= 3:
                        pygame.draw.polygon(self.surface, color, screen_pts, 2)

            if circle:
                center_x = transform.x + circle.offset_x
                center_y = transform.y + circle.offset_y
                screen_x, screen_y = self._world_to_screen(center_x, center_y)
                screen_radius = max(1, int(abs(circle.radius) * self.camera_zoom))
                pygame.draw.circle(self.surface, color, (int(screen_x), int(screen_y)), screen_radius, 2)
            if polygon and len(polygon.points) >= 3:
                screen_points = []
                for point in polygon.points:
                    world_x = transform.x + polygon.offset_x + point.x
                    world_y = transform.y + polygon.offset_y + point.y
                    screen_x, screen_y = self._world_to_screen(world_x, world_y)
                    screen_points.append((int(screen_x), int(screen_y)))
                if len(screen_points) >= 3:
                    pygame.draw.polygon(self.surface, color, screen_points, 2)

            if occluder:
                occ_color = (200, 180, 60)  # Distinct from collider yellow
                cx = transform.x + occluder.offset_x
                cy = transform.y + occluder.offset_y
                if occluder.shape == "box":
                    hw = max(0.5, abs(occluder.width) * 0.5)
                    hh = max(0.5, abs(occluder.height) * 0.5)
                    # Apply component rotation
                    total_rot = (transform.rotation + occluder.rotation) % 360
                    if abs(total_rot) < 0.001 or abs(total_rot - 360) < 0.001:
                        # Axis-aligned
                        lt = self._world_to_screen(cx - hw, cy - hh)
                        rb = self._world_to_screen(cx + hw, cy + hh)
                        r = pygame.Rect(
                            int(min(lt[0], rb[0])), int(min(lt[1], rb[1])),
                            max(1, int(abs(rb[0] - lt[0]))), max(1, int(abs(rb[1] - lt[1])))
                        )
                        pygame.draw.rect(self.surface, occ_color, r, 2)
                    else:
                        # Rotated box
                        rad = math.radians(total_rot)
                        cos_a = math.cos(rad)
                        sin_a = math.sin(rad)
                        corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
                        screen_pts = []
                        for lx, ly in corners:
                            rx = lx * cos_a - ly * sin_a + cx
                            ry = lx * sin_a + ly * cos_a + cy
                            sx, sy = self._world_to_screen(rx, ry)
                            screen_pts.append((int(sx), int(sy)))
                        if len(screen_pts) >= 3:
                            pygame.draw.polygon(self.surface, occ_color, screen_pts, 2)
                elif occluder.shape == "circle":
                    sx, sy = self._world_to_screen(cx, cy)
                    sr = max(1, int(abs(occluder.radius) * self.camera_zoom))
                    pygame.draw.circle(self.surface, occ_color, (int(sx), int(sy)), sr, 2)
                elif occluder.shape == "polygon" and len(occluder.points) >= 3:
                    pts = []
                    for p in occluder.points:
                        wx = transform.x + occluder.offset_x + p.x
                        wy = transform.y + occluder.offset_y + p.y
                        sx, sy = self._world_to_screen(wx, wy)
                        pts.append((int(sx), int(sy)))
                    if len(pts) >= 3:
                        pygame.draw.polygon(self.surface, occ_color, pts, 2)

                # Draw shadow preview for occluder
                self._draw_shadow_preview_for_occluder(occluder, transform)

            if spot_light:
                sl_color = (120, 200, 255)  # Light blue for spot light
                sl_cx = transform.x + spot_light.offset_x
                sl_cy = transform.y + spot_light.offset_y
                sl_scx, sl_scy = self._world_to_screen(sl_cx, sl_cy)
                sl_sr = max(1, int(spot_light.radius * self.camera_zoom))
                # Draw outer radius circle (dashed feel via thinner line)
                pygame.draw.circle(self.surface, sl_color, (int(sl_scx), int(sl_scy)), sl_sr, 1)
                # Draw cone edges
                angle_rad = math.radians(spot_light.angle)
                half_cone = spot_light.cone_angle
                for cone_dir in (1, -1):
                    edge_rad = math.radians(spot_light.angle + half_cone * cone_dir)
                    ex = sl_scx + math.cos(edge_rad) * sl_sr
                    ey = sl_scy + math.sin(edge_rad) * sl_sr
                    pygame.draw.line(self.surface, sl_color, (int(sl_scx), int(sl_scy)), (int(ex), int(ey)), 2)
                # Draw direction line
                dir_ex = sl_scx + math.cos(angle_rad) * sl_sr
                dir_ey = sl_scy + math.sin(angle_rad) * sl_sr
                pygame.draw.line(self.surface, sl_color, (int(sl_scx), int(sl_scy)), (int(dir_ex), int(dir_ey)), 1)
                # Draw cone arc
                n_arc = 20
                start_angle = spot_light.angle - half_cone
                end_angle = spot_light.angle + half_cone
                arc_pts = []
                for i in range(n_arc + 1):
                    t = start_angle + (end_angle - start_angle) * i / n_arc
                    r = math.radians(t)
                    arc_pts.append((int(sl_scx + math.cos(r) * sl_sr), int(sl_scy + math.sin(r) * sl_sr)))
                if len(arc_pts) >= 2:
                    pygame.draw.lines(self.surface, sl_color, False, arc_pts, 2)

        spot_angle_color = (100, 180, 255)   # Blue for spot angle handle
        spot_cone_color = (160, 120, 255)    # Purple for spot cone handles

        for handle in handles:
            is_spot = handle.get("component_type") is SpotLight2D
            if handle["attr"] == "offset":
                color = move_handle_color
                handle_size = self.collider_handle_size + 4
            elif handle["attr"] == "rotation":
                color = rotation_handle_color
                handle_size = self.collider_handle_size
            elif is_spot and handle["attr"] == "angle":
                color = spot_angle_color
                handle_size = self.collider_handle_size + 2
            elif is_spot and handle["attr"] == "cone_angle":
                color = spot_cone_color
                handle_size = self.collider_handle_size
            else:
                color = handle_color
                handle_size = self.collider_handle_size
            rect = pygame.Rect(
                int(handle["screen_x"]) - (handle_size // 2),
                int(handle["screen_y"]) - (handle_size // 2),
                handle_size,
                handle_size
            )
            if handle["attr"] == "offset":
                pygame.draw.circle(self.surface, color, rect.center, handle_size // 2)
                pygame.draw.circle(self.surface, (20, 20, 20), rect.center, handle_size // 2, 1)
            elif handle["attr"] == "rotation":
                pygame.draw.circle(self.surface, color, rect.center, handle_size // 2)
                pygame.draw.circle(self.surface, (20, 20, 20), rect.center, handle_size // 2, 2)
            elif is_spot and handle["attr"] == "angle":
                # Diamond shape for angle handle
                cx, cy = rect.center
                hs = handle_size // 2
                diamond = [(cx, cy - hs), (cx + hs, cy), (cx, cy + hs), (cx - hs, cy)]
                pygame.draw.polygon(self.surface, color, diamond)
                pygame.draw.polygon(self.surface, (20, 20, 20), diamond, 1)
            elif is_spot and handle["attr"] == "cone_angle":
                # Triangle shape for cone handles
                cx, cy = rect.center
                hs = handle_size // 2
                triangle = [(cx, cy - hs), (cx + hs, cy + hs), (cx - hs, cy + hs)]
                pygame.draw.polygon(self.surface, color, triangle)
                pygame.draw.polygon(self.surface, (20, 20, 20), triangle, 1)
            else:
                pygame.draw.rect(self.surface, color, rect)
                pygame.draw.rect(self.surface, (20, 20, 20), rect, 1)

    def _draw_shadow_preview_for_occluder(self, occluder: LightOccluder2D, transform: Transform):
        """Draw shadow preview extending from occluder using shadow_extend setting."""
        shadow_color = (50, 30, 80, 100)  # Semi-transparent purple for shadow preview
        
        # Get occluder polygon in world space
        occluder_poly = []
        cx = transform.x + occluder.offset_x
        cy = transform.y + occluder.offset_y
        
        if occluder.shape == "box":
            hw = max(0.5, abs(occluder.width) * 0.5)
            hh = max(0.5, abs(occluder.height) * 0.5)
            total_rot = (transform.rotation + occluder.rotation) % 360
            rad = math.radians(total_rot)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
            for lx, ly in corners:
                rx = lx * cos_a - ly * sin_a + cx
                ry = lx * sin_a + ly * cos_a + cy
                occluder_poly.append((rx, ry))
        elif occluder.shape == "circle":
            # For circle, draw a simple shadow cone extending outward
            sr = max(0.5, abs(occluder.radius))
            for i in range(8):
                angle = (i / 8) * 2 * math.pi
                x = cx + sr * math.cos(angle)
                y = cy + sr * math.sin(angle)
                occluder_poly.append((x, y))
        elif occluder.shape == "polygon" and len(occluder.points) >= 3:
            for p in occluder.points:
                wx = cx + p.x
                wy = cy + p.y
                occluder_poly.append((wx, wy))
        
        if len(occluder_poly) < 2:
            return
        
        # Draw shadow volume extending from each edge
        shadow_color_rgb = shadow_color[:3]
        for i in range(len(occluder_poly)):
            p1 = occluder_poly[i]
            p2 = occluder_poly[(i + 1) % len(occluder_poly)]
            
            # Calculate edge midpoint and direction
            mid_x = (p1[0] + p2[0]) * 0.5
            mid_y = (p1[1] + p2[1]) * 0.5
            
            # Direction from center to edge midpoint
            dx = mid_x - cx
            dy = mid_y - cy
            dist = math.hypot(dx, dy)
            if dist < 0.001:
                continue
            
            # Normalize and extend
            nx = dx / dist
            ny = dy / dist
            
            # Shadow volume extends outward
            shadow_end_x = mid_x + nx * self.shadow_extend
            shadow_end_y = mid_y + ny * self.shadow_extend
            
            # Convert to screen coordinates
            screen_mid = self._world_to_screen(mid_x, mid_y)
            screen_end = self._world_to_screen(shadow_end_x, shadow_end_y)
            
            # Draw shadow line (thin, semi-transparent)
            pygame.draw.line(self.surface, shadow_color_rgb, 
                           (int(screen_mid[0]), int(screen_mid[1])),
                           (int(screen_end[0]), int(screen_end[1])), 1)

    def _hit_test_collider_handle(self, mouse_pos):
        x, y = mouse_pos
        best = None
        best_dist = float("inf")
        for handle in self._build_collider_handles():
            if handle["attr"] == "offset":
                hit_radius = ((self.collider_handle_size + 4) * 0.5) + 4
            else:
                hit_radius = (self.collider_handle_size * 0.5) + 4
            dx = handle["screen_x"] - x
            dy = handle["screen_y"] - y
            dist = math.hypot(dx, dy)
            if dist <= hit_radius and dist < best_dist:
                best = handle
                best_dist = dist
        return best

    def _begin_collider_resize(self, handle, mouse_pos):
        entity = handle["entity"]
        if entity not in self.selected_entities:
            self.selected_entities = [entity]
            self.gizmo.set_targets(self.selected_entities)
            self.entity_selected.emit(self.selected_entities)

        comp = handle["component"]
        attr = handle["attr"]
        state = {
            "entity": entity,
            "component": comp,
            "component_type": handle["component_type"],
            "attr": attr,
            "direction": handle["direction"],
            "center_x": handle["center_x"],
            "center_y": handle["center_y"],
        }
        if attr == "offset":
            transform = entity.get_component(Transform)
            if not transform:
                return
            mouse_world_x, mouse_world_y = self._screen_to_world(mouse_pos[0], mouse_pos[1])
            state["transform"] = transform
            state["grab_dx"] = mouse_world_x - handle["center_x"]
            state["grab_dy"] = mouse_world_y - handle["center_y"]
            state["old_offset_x"] = comp.offset_x
            state["old_offset_y"] = comp.offset_y
        elif attr == "rotation":
            comp = handle["component"]
            state["old_rotation"] = comp.rotation
            mouse_world_x, mouse_world_y = self._screen_to_world(mouse_pos[0], mouse_pos[1])
            state["initial_angle"] = math.atan2(
                mouse_world_y - handle["center_y"],
                mouse_world_x - handle["center_x"]
            )
        elif attr == "angle" and handle["component_type"] is SpotLight2D:
            state["old_value"] = comp.angle
        elif attr == "cone_angle" and handle["component_type"] is SpotLight2D:
            state["old_value"] = comp.cone_angle
        elif attr == "point":
            transform = entity.get_component(Transform)
            if not transform:
                return
            state["transform"] = transform
            state["point_index"] = handle.get("point_index", -1)
            state["old_points"] = [Vector2(point.x, point.y) for point in comp.points]
        else:
            state["old_value"] = getattr(comp, attr)
        self.collider_drag_state = state

    def _update_collider_resize(self, mouse_pos):
        if not self.collider_drag_state:
            return
        world_x, world_y = self._screen_to_world(mouse_pos[0], mouse_pos[1])
        state = self.collider_drag_state
        comp = state["component"]
        attr = state["attr"]
        direction = state["direction"]
        cx = state["center_x"]
        cy = state["center_y"]

        if attr == "width":
            if direction > 0:
                new_width = max(1.0, (world_x - cx) * 2.0)
            else:
                new_width = max(1.0, (cx - world_x) * 2.0)
            comp.width = new_width
        elif attr == "height":
            if direction > 0:
                new_height = max(1.0, (world_y - cy) * 2.0)
            else:
                new_height = max(1.0, (cy - world_y) * 2.0)
            comp.height = new_height
        elif attr == "radius":
            dx = world_x - cx
            dy = world_y - cy
            comp.radius = max(0.5, math.hypot(dx, dy))
        elif attr == "rotation":
            comp = state["component"]
            current_angle = math.atan2(
                world_y - cy,
                world_x - cx
            )
            angle_delta = current_angle - state["initial_angle"]
            comp.rotation = state["old_rotation"] + math.degrees(angle_delta)
        elif attr == "angle" and state["component_type"] is SpotLight2D:
            # Angle = direction from center to mouse in degrees
            screen_cx, screen_cy = self._world_to_screen(cx, cy)
            mouse_sx, mouse_sy = mouse_pos
            comp.angle = math.degrees(math.atan2(mouse_sy - screen_cy, mouse_sx - screen_cx))
        elif attr == "cone_angle" and state["component_type"] is SpotLight2D:
            # Cone angle = angular distance from direction to mouse
            screen_cx, screen_cy = self._world_to_screen(cx, cy)
            mouse_sx, mouse_sy = mouse_pos
            mouse_angle = math.degrees(math.atan2(mouse_sy - screen_cy, mouse_sx - screen_cx))
            delta = abs(mouse_angle - comp.angle)
            if delta > 180:
                delta = 360 - delta
            comp.cone_angle = max(1.0, min(180.0, delta))
        elif attr == "offset":
            transform = state["transform"]
            center_x = world_x - state["grab_dx"]
            center_y = world_y - state["grab_dy"]
            comp.offset_x = center_x - transform.x
            comp.offset_y = center_y - transform.y
        elif attr == "point":
            transform = state["transform"]
            point_index = state["point_index"]
            if point_index < 0 or point_index >= len(comp.points):
                return
            new_points = [Vector2(point.x, point.y) for point in comp.points]
            new_points[point_index] = Vector2(
                world_x - transform.x - comp.offset_x,
                world_y - transform.y - comp.offset_y
            )
            comp.points = new_points

    def _commit_collider_resize(self):
        state = self.collider_drag_state
        if not state:
            return

        comp = state["component"]
        attr = state["attr"]
        mw = self.window()
        if not hasattr(mw, "undo_manager"):
            return

        if attr == "rotation":
            comp = state["component"]
            old_rotation = state["old_rotation"]
            new_rotation = comp.rotation
            if abs(new_rotation - old_rotation) > 1e-6:
                mw.undo_manager.push(PropertyChangeCommand(
                    [state["entity"]],
                    state["component_type"],
                    "rotation",
                    [old_rotation],
                    new_rotation
                ))
            return
        if attr == "offset":
            old_offset_x = state["old_offset_x"]
            old_offset_y = state["old_offset_y"]
            new_offset_x = comp.offset_x
            new_offset_y = comp.offset_y
            if abs(new_offset_x - old_offset_x) > 1e-6 or abs(new_offset_y - old_offset_y) > 1e-6:
                mw.undo_manager.push(MultiPropertyChangeCommand(
                    [state["entity"]],
                    state["component_type"],
                    ["offset_x", "offset_y"],
                    [[old_offset_x], [old_offset_y]],
                    [new_offset_x, new_offset_y]
                ))
            return
        if attr == "point":
            old_points = state["old_points"]
            new_points = [Vector2(point.x, point.y) for point in comp.points]
            if len(old_points) != len(new_points):
                changed = True
            else:
                changed = any(
                    abs(old_points[index].x - new_points[index].x) > 1e-6
                    or abs(old_points[index].y - new_points[index].y) > 1e-6
                    for index in range(len(new_points))
                )
            if changed:
                mw.undo_manager.push(PropertyChangeCommand(
                    [state["entity"]],
                    state["component_type"],
                    "points",
                    [old_points],
                    new_points
                ))
            return

        old_value = state["old_value"]
        new_value = getattr(comp, attr)
        if abs(new_value - old_value) <= 1e-6:
            return
        mw.undo_manager.push(PropertyChangeCommand(
            [state["entity"]],
            state["component_type"],
            attr,
            [old_value],
            new_value
        ))

    def mousePressEvent(self, event):
        mouse_pos = (event.position().x(), event.position().y())

        # Tilemap edit interaction (takes precedence over selection/gizmo when enabled)
        if event.button() == Qt.MouseButton.LeftButton and self.tilemap_edit_mode:
            target = self._get_selected_tilemap_target()
            if target:
                entity, transform, tilemap, layer, layer_index = target
                world_x, world_y = self._screen_to_world(mouse_pos[0], mouse_pos[1])
                tx, ty = self._world_to_tile(world_x, world_y, transform, tilemap)
                tool = str(self.tilemap_tool)
                if tool in ("paint", "erase"):
                    value = self.tilemap_selected_tile if tool == "paint" else 0
                    self._tilemap_stroke_changes = {}
                    if self._apply_tile_at(layer, tx, ty, value):
                        self.entity_modified.emit(entity)
                    self.last_mouse_pos = event.position()
                    return
                if tool == "picker":
                    picked = layer.get_world(tx, ty)
                    mw = self.window()
                    if mw and hasattr(mw, "tilemap_editor_dock"):
                        mw.tilemap_editor_dock.preview._selected_tile_id = int(picked)
                        mw.tilemap_editor_dock.selected_tile_changed.emit(int(picked))
                        mw.tilemap_editor_dock.preview.update()
                    self.last_mouse_pos = event.position()
                    return
                if tool == "rect":
                    self._tilemap_stroke_changes = {}
                    self._tilemap_rect_start = (tx, ty)
                    self.last_mouse_pos = event.position()
                    return
                if tool == "fill":
                    self._tilemap_stroke_changes = {}
                    self._flood_fill(layer, tx, ty, int(self.tilemap_selected_tile))
                    self._commit_tilemap_stroke(entity, layer_index)
                    self.entity_modified.emit(entity)
                    self.last_mouse_pos = event.position()
                    return
        if event.button() == Qt.MouseButton.LeftButton and self.polygon_point_add_entity:
            if self._add_polygon_point_from_screen(mouse_pos[0], mouse_pos[1]):
                self.last_mouse_pos = event.position()
                return

        if event.button() == Qt.MouseButton.LeftButton and self._occ_point_add_entity:
            if self._add_occ_polygon_point_from_screen(mouse_pos[0], mouse_pos[1]):
                self.last_mouse_pos = event.position()
                return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.physics_debug_mode:
                handle = self._hit_test_collider_handle(mouse_pos)
                if handle:
                    self._begin_collider_resize(handle, mouse_pos)
                    self.last_mouse_pos = event.position()
                    return

            gizmo_cam_x, gizmo_cam_y, gizmo_zoom = self._get_gizmo_camera()
            if self.gizmo.handle_event("MOUSEBUTTONDOWN", mouse_pos, gizmo_cam_x, gizmo_cam_y, gizmo_zoom):
                self.gizmo_interaction_active = True
                self.capture_start_states()
                return

        if event.button() == Qt.MouseButton.LeftButton:
            
            # Picking logic
            x, y = mouse_pos
            world_x, world_y = self._screen_to_world(x, y)
            
            clicked_entity = None
            
            # Iterate in reverse order to select top-most entity first
            for entity in reversed(self.scene.world.entities):
                transform = entity.get_component(Transform)
                if transform:
                    sprite = entity.get_component(SpriteRenderer)
                    
                    if sprite:
                        # sprite.width/height are already scaled (world size)
                        w = abs(sprite.width)
                        h = abs(sprite.height)
                    else:
                        # Default 50x50 needs scaling
                        w = abs(50 * transform.scale_x)
                        h = abs(50 * transform.scale_y)
                    
                    # Rotate AABB
                    if transform.rotation != 0:
                        rad = math.radians(transform.rotation)
                        sin_a = abs(math.sin(rad))
                        cos_a = abs(math.cos(rad))
                        final_w = w * cos_a + h * sin_a
                        final_h = w * sin_a + h * cos_a
                    else:
                        final_w = w
                        final_h = h
                        
                    left = transform.x - final_w / 2
                    right = transform.x + final_w / 2
                    top = transform.y - final_h / 2
                    bottom = transform.y + final_h / 2
                    
                    if left <= world_x <= right and top <= world_y <= bottom:
                        clicked_entity = entity
                        break
            
            modifiers = event.modifiers()
            ctrl_pressed = modifiers & Qt.KeyboardModifier.ControlModifier
            
            if clicked_entity:
                if ctrl_pressed:
                    if clicked_entity in self.selected_entities:
                        self.selected_entities.remove(clicked_entity)
                    else:
                        self.selected_entities.append(clicked_entity)
                else:
                    self.selected_entities = [clicked_entity]
                    
                # If we clicked an entity (even if already selected), start dragging
                # Only if not Ctrl-click (which toggles selection)
                if not ctrl_pressed:
                    self.dragging = True
                    self.capture_start_states()
            else:
                if not ctrl_pressed:
                    self.selected_entities = []
            
            self.gizmo.set_targets(self.selected_entities)
            self.entity_selected.emit(self.selected_entities)
                
        elif event.button() == Qt.MouseButton.MiddleButton or event.button() == Qt.MouseButton.RightButton:
            self.panning = True
            self.last_mouse_pos = event.position()
            
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        mouse_pos = (event.position().x(), event.position().y())

        if self.tilemap_edit_mode and self._tilemap_stroke_changes is not None:
            target = self._get_selected_tilemap_target()
            if target:
                entity, transform, tilemap, layer, _layer_index = target
                tool = str(self.tilemap_tool)
                if tool in ("paint", "erase"):
                    world_x, world_y = self._screen_to_world(mouse_pos[0], mouse_pos[1])
                    tx, ty = self._world_to_tile(world_x, world_y, transform, tilemap)
                    value = self.tilemap_selected_tile if tool == "paint" else 0
                    if self._apply_tile_at(layer, tx, ty, value):
                        self.entity_modified.emit(entity)
                    self.last_mouse_pos = event.position()
                    return

        if self.collider_drag_state:
            self._update_collider_resize(mouse_pos)
            if self.selected_entities:
                self.entity_modified.emit(self.selected_entities[0])
            self.last_mouse_pos = event.position()
            return

        # Handle Gizmo hover/drag
        gizmo_cam_x, gizmo_cam_y, gizmo_zoom = self._get_gizmo_camera()
        if self.gizmo.handle_event("MOUSEMOTION", mouse_pos, gizmo_cam_x, gizmo_cam_y, gizmo_zoom):
            if self.gizmo.active_axis != Gizmo.AXIS_NONE and self.selected_entities:
                if self.selected_entities:
                    self.entity_modified.emit(self.selected_entities[0])
            # Even if gizmo handled it, update last_mouse_pos for next frame consistency
            self.last_mouse_pos = event.position()
            return

        if self.panning and self.last_mouse_pos:
            dx = event.position().x() - self.last_mouse_pos.x()
            dy = event.position().y() - self.last_mouse_pos.y()
            self.camera_x -= dx / self.camera_zoom
            self.camera_y -= dy / self.camera_zoom
            
            if self.render_system:
                self.render_system.camera_x = self.camera_x
                self.render_system.camera_y = self.camera_y
                
        elif self.dragging and self.selected_entities and self.last_mouse_pos:
            dx = (event.position().x() - self.last_mouse_pos.x()) / self.camera_zoom
            dy = (event.position().y() - self.last_mouse_pos.y()) / self.camera_zoom
            
            for entity in self.selected_entities:
                transform = entity.get_component(Transform)
                if transform:
                    transform.x += dx
                    transform.y += dy
            
            if self.selected_entities:
                self.entity_modified.emit(self.selected_entities[0])
                
        self.last_mouse_pos = event.position()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        mouse_pos = (event.position().x(), event.position().y())
        if event.button() == Qt.MouseButton.LeftButton:
            if self.tilemap_edit_mode:
                target = self._get_selected_tilemap_target()
                if target:
                    entity, transform, tilemap, layer, layer_index = target
                    tool = str(self.tilemap_tool)
                    if tool == "rect" and self._tilemap_rect_start is not None:
                        world_x, world_y = self._screen_to_world(mouse_pos[0], mouse_pos[1])
                        end_tx, end_ty = self._world_to_tile(world_x, world_y, transform, tilemap)
                        start_tx, start_ty = self._tilemap_rect_start
                        self._tilemap_rect_start = None
                        # No bounds checking for infinite tilemap
                        x0 = min(start_tx, end_tx)
                        x1 = max(start_tx, end_tx)
                        y0 = min(start_ty, end_ty)
                        y1 = max(start_ty, end_ty)
                        value = int(self.tilemap_selected_tile)
                        for ty in range(y0, y1 + 1):
                            for tx in range(x0, x1 + 1):
                                self._apply_tile_at(layer, tx, ty, value)
                    self._commit_tilemap_stroke(entity, layer_index)
                    if self.selected_entities:
                        self.entity_modified.emit(self.selected_entities[0])
                    super().mouseReleaseEvent(event)
                    return

            if self.collider_drag_state:
                self._commit_collider_resize()
                self.collider_drag_state = None
                super().mouseReleaseEvent(event)
                return

            # Check if we need to commit changes
            if self.gizmo_interaction_active or self.dragging:
                 self.commit_transform()
            
            gizmo_cam_x, gizmo_cam_y, gizmo_zoom = self._get_gizmo_camera()
            self.gizmo.handle_event("MOUSEBUTTONUP", mouse_pos, gizmo_cam_x, gizmo_cam_y, gizmo_zoom)
            self.gizmo_interaction_active = False
            self.dragging = False
            
        elif event.button() == Qt.MouseButton.MiddleButton or event.button() == Qt.MouseButton.RightButton:
            self.panning = False
            # Don't clear last_mouse_pos here as move event needs it for continuity? 
            # Actually standard practice is clear on release if dragging ended.
            # But we set it on move.
            pass
            
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        zoom_factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        
        mouse_x = event.position().x()
        mouse_y = event.position().y()
        
        world_x_before, world_y_before = self._screen_to_world(mouse_x, mouse_y)
        
        self.camera_zoom *= zoom_factor
        # clamp zoom
        self.camera_zoom = max(0.1, min(self.camera_zoom, 10.0))

        if self.render_system:
            self.render_system.camera_zoom = self.camera_zoom
            self.render_system.camera_x = self.camera_x
            self.render_system.camera_y = self.camera_y
        
        world_x_after, world_y_after = self._screen_to_world(mouse_x, mouse_y)
        
        self.camera_x += (world_x_before - world_x_after)
        self.camera_y += (world_y_before - world_y_after)
        
        if self.render_system:
            self.render_system.camera_zoom = self.camera_zoom
            self.render_system.camera_x = self.camera_x
            self.render_system.camera_y = self.camera_y
            
        self.update_zoom_label()
        super().wheelEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F3:
            self.toggle_physics_debug()
        elif event.key() == Qt.Key.Key_Delete:
            if self.selected_entities:
                deletable_entities = [entity for entity in self.selected_entities if not self._is_protected_entity(entity)]
                if not deletable_entities:
                    super().keyPressEvent(event)
                    return
                mw = self.window()
                if hasattr(mw, 'undo_manager'):
                    cmd = DeleteEntitiesCommand(self.scene.world, deletable_entities)
                    # Execute first, then push? Or push executes?
                    # Command pattern usually: create, execute, push.
                    # But UndoManager.push doesn't execute.
                    # DeleteEntitiesCommand.execute() does the deletion.
                    cmd.execute()
                    mw.undo_manager.push(cmd)
                else:
                    # Fallback
                    for entity in deletable_entities:
                        self.scene.world.destroy_entity(entity)
                
                # Deselect and hide gizmo
                self.selected_entities = []
                self.gizmo.set_targets([])
                self.entity_selected.emit([])
                
                # Notify main window to refresh hierarchy
                self.entity_deleted.emit(None)
                
        elif event.key() == Qt.Key.Key_Escape:
            if self.polygon_point_add_entity:
                self.stop_polygon_point_add_mode()
            if self._occ_point_add_entity:
                self._occ_point_add_entity = None
            if self.selected_entities:
                # Deselect and hide gizmo
                self.selected_entities = []
                self.gizmo.set_targets([])
                self.entity_selected.emit([])
                
        elif event.key() == Qt.Key.Key_T:
            self.set_gizmo_mode(Gizmo.MODE_TRANSLATE)
        elif event.key() == Qt.Key.Key_R:
            self.set_gizmo_mode(Gizmo.MODE_ROTATE)
        elif event.key() == Qt.Key.Key_S:
            self.set_gizmo_mode(Gizmo.MODE_SCALE)
                
        super().keyPressEvent(event)

    def _is_protected_entity(self, entity):
        if not entity:
            return False
        if entity.name != "Main Camera":
            return False
        return entity.get_component(CameraComponent) is not None

    def capture_start_states(self):
        self.transform_start_states = []
        for entity in self.selected_entities:
            t = entity.get_component(Transform)
            if t:
                self.transform_start_states.append({
                    'x': t.x,
                    'y': t.y,
                    'rotation': t.rotation,
                    'scale_x': t.scale_x,
                    'scale_y': t.scale_y
                })
            else:
                self.transform_start_states.append(None)

    def commit_transform(self):
        if not self.transform_start_states:
            return
            
        final_states = []
        changed = False
        
        for i, entity in enumerate(self.selected_entities):
            t = entity.get_component(Transform)
            if t:
                state = {
                    'x': t.x,
                    'y': t.y,
                    'rotation': t.rotation,
                    'scale_x': t.scale_x,
                    'scale_y': t.scale_y
                }
                final_states.append(state)
                
                # Check if changed
                if i < len(self.transform_start_states):
                    start = self.transform_start_states[i]
                    if start and state != start:
                        changed = True
            else:
                final_states.append(None)
        
        if changed:
            mw = self.window()
            if hasattr(mw, 'undo_manager'):
                cmd = TransformCommand(self.selected_entities, self.transform_start_states, final_states)
                mw.undo_manager.push(cmd)
                
        self.transform_start_states = []
