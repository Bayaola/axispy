from __future__ import annotations
from collections import OrderedDict
import math
import pygame
from core.ecs import System, Entity
from core.components.transform import Transform
from core.components.camera import CameraComponent
from core.components.sprite_renderer import SpriteRenderer
from core.components.animator import AnimatorComponent
from core.components.particle_emitter import ParticleEmitterComponent
from core.components.tilemap import TilemapComponent
from core.components.ui import (
    TextRenderer, ButtonComponent, TextInputComponent, SliderComponent,
    ProgressBarComponent, CheckBoxComponent, ImageRenderer,
    HBoxContainerComponent, VBoxContainerComponent, GridBoxContainerComponent
)


class RenderSystem(System):
    def __init__(self, surface: pygame.Surface):
        super().__init__()
        self.update_phase = "render"
        self.surface = surface
        self.use_camera_components = True
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.camera_zoom = 1.0
        self.camera_rotation = 0.0
        self.design_size = None  # (width, height) of the game design resolution
        self.skip_ui_render = False  # When True, update() won't call render_ui()
        self._particle_surface_cache = OrderedDict()
        self._particle_cache_max = 1024
        self.interpolation_alpha = 1.0
        self._sorted_entities_cache = None
        self._sort_entity_count: int = -1
        self._sort_layer_snapshot: list | None = None
        self._ui_entity_cache: set | None = None
        self._ui_cache_entity_count: int = -1
        self._cached_surface_size = self._surface_size()
        self._font_cache: dict[tuple, pygame.font.Font] = {}
        self._sprite_scale_cache: OrderedDict[tuple, pygame.Surface] = OrderedDict()
        self._sprite_scale_cache_max: int = 512
        self.smooth_present = True

    def _get_font(self, font_path, font_size: int) -> pygame.font.Font:
        """Return a cached pygame.font.Font for the given path and size."""
        key = (font_path, font_size)
        cached = self._font_cache.get(key)
        if cached is not None:
            return cached
        font = pygame.font.Font(font_path, font_size)
        self._font_cache[key] = font
        return font

    def _get_sorted_entities(self, entities: list[Entity]) -> list[Entity]:
        """Return entities sorted by layer order, cached until entity list or layers change."""
        current_count = len(entities)
        current_layers = getattr(self.world, "layers", None) if self.world else None
        if (
            self._sorted_entities_cache is not None
            and current_count == self._sort_entity_count
            and current_layers is self._sort_layer_snapshot
        ):
            return self._sorted_entities_cache
        if current_layers:
            layer_indices = {name: i for i, name in enumerate(current_layers)}
            self._sorted_entities_cache = sorted(entities, key=lambda e: layer_indices.get(e.layer, 0))
        else:
            self._sorted_entities_cache = list(entities)
        self._sort_entity_count = current_count
        self._sort_layer_snapshot = current_layers
        return self._sorted_entities_cache

    def update(self, dt: float, entities: list[Entity]):
        self.interpolation_alpha = max(0.0, min(1.0, float(self.interpolation_alpha)))
        self._cached_surface_size = self._surface_size()
        for camera_view in self.get_camera_views(entities, dt):
            self._render_camera_view(camera_view, entities)
        
        if not self.skip_ui_render:
            self.render_ui(entities)

    # UI component types for targeted iteration
    _UI_TYPES = (
        ImageRenderer, ButtonComponent, TextInputComponent,
        SliderComponent, ProgressBarComponent, CheckBoxComponent, TextRenderer,
    )

    def render_ui(self, entities: list[Entity], viewport_rect=None):
        # Render UI components in screen space (overlay)
        # Using Transform as screen coordinates (pixels)
        # When viewport_rect is provided, UI is mapped into that rect (editor WYSIWYG)
        if not pygame.font.get_init():
            pygame.font.init()

        # P9-5: Collect UI entities via aggregate cache — only rebuild when
        # entity count changes, avoiding 7 set unions every frame.
        if self.world:
            current_count = len(entities)
            if self._ui_entity_cache is not None and current_count == self._ui_cache_entity_count:
                ui_entity_set = self._ui_entity_cache
            else:
                ui_entity_set = set()
                _cache = self.world._component_cache
                for ui_type in self._UI_TYPES:
                    cached = _cache.get(ui_type)
                    if cached:
                        ui_entity_set.update(cached)
                self._ui_entity_cache = ui_entity_set
                self._ui_cache_entity_count = current_count
            if not ui_entity_set:
                return
            sorted_all = self._get_sorted_entities(entities)
            sorted_entities = [e for e in sorted_all if e in ui_entity_set]
        else:
            sorted_entities = self._get_sorted_entities(entities)

        if not sorted_entities:
            return

        # Compute mapping factors
        design_w, design_h = self._get_design_size()
        if viewport_rect:
            sx = viewport_rect.width / max(1, design_w)
            sy = viewport_rect.height / max(1, design_h)
            ox, oy = viewport_rect.x, viewport_rect.y
            clip_backup = self.surface.get_clip()
            self.surface.set_clip(viewport_rect)
        else:
            sx, sy = 1.0, 1.0
            ox, oy = 0, 0

        for entity in sorted_entities:
            if not entity.is_visible():
                continue
            comps = entity.components
            transform = comps.get(Transform)
            if not transform:
                continue
            transform_values = self._get_entity_transform_values(entity, transform)
            x = ox + transform_values[0] * sx
            y = oy + transform_values[1] * sy
            rotation = transform_values[2]
            scale_x = transform_values[3]
            scale_y = transform_values[4]
            
            # 1. ImageRenderer (UI)
            ui_image = comps.get(ImageRenderer)
            if ui_image and ui_image.image:
                w = ui_image.width * scale_x * sx
                h = ui_image.height * scale_y * sy
                if w > 0 and h > 0:
                    scaled_img = pygame.transform.scale(ui_image.image, (int(w), int(h)))
                    if rotation != 0:
                        scaled_img = pygame.transform.rotate(scaled_img, -rotation)
                    self.surface.blit(scaled_img, (x, y))

            # 2. ButtonComponent
            btn = comps.get(ButtonComponent)
            if btn:
                w = btn.width * scale_x * sx
                h = btn.height * scale_y * sy
                rect = pygame.Rect(x, y, w, h)
                color = btn.normal_color
                if btn.is_pressed: color = btn.pressed_color
                elif btn.is_hovered: color = btn.hover_color
                
                pygame.draw.rect(self.surface, color, rect)
                
                if btn.text:
                    font_size = max(8, int(24 * min(sx, sy)))
                    font = self._get_font(None, font_size)
                    text_surf = font.render(btn.text, True, btn.text_color)
                    text_rect = text_surf.get_rect(center=rect.center)
                    self.surface.blit(text_surf, text_rect)

            # 3. TextInputComponent
            inp = comps.get(TextInputComponent)
            if inp:
                w = inp.width * scale_x * sx
                h = inp.height * scale_y * sy
                rect = pygame.Rect(x, y, w, h)
                pygame.draw.rect(self.surface, inp.bg_color, rect)
                pygame.draw.rect(self.surface, (0, 0, 0), rect, 1)
                
                text_str = inp.text
                color = inp.text_color
                if not text_str and inp.placeholder:
                    text_str = inp.placeholder
                    color = (150, 150, 150)
                
                font_size = max(8, int(24 * min(sx, sy)))
                font = self._get_font(None, font_size)
                surf = font.render(text_str, True, color)
                self.surface.blit(surf, (x + 5 * sx, y + (h - surf.get_height()) // 2))

            # 4. SliderComponent
            slider = comps.get(SliderComponent)
            if slider:
                w = slider.width * scale_x * sx
                h = slider.height * scale_y * sy
                rect = pygame.Rect(x, y, w, h)
                pygame.draw.rect(self.surface, slider.track_color, rect)
                
                val_range = slider.max_value - slider.min_value
                if val_range == 0: val_range = 1
                pct = (slider.value - slider.min_value) / val_range
                pct = max(0.0, min(1.0, pct))
                
                handle_w = 10 * sx
                handle_x = x + (pct * w) - (handle_w / 2)
                handle_rect = pygame.Rect(handle_x, y - 5 * sy, handle_w, h + 10 * sy)
                pygame.draw.rect(self.surface, slider.handle_color, handle_rect)

            # 5. ProgressBarComponent
            pbar = comps.get(ProgressBarComponent)
            if pbar:
                w = pbar.width * scale_x * sx
                h = pbar.height * scale_y * sy
                rect = pygame.Rect(x, y, w, h)
                pygame.draw.rect(self.surface, pbar.bg_color, rect)
                
                val_range = pbar.max_value - pbar.min_value
                if val_range == 0: val_range = 1
                pct = (pbar.value - pbar.min_value) / val_range
                pct = max(0.0, min(1.0, pct))
                
                fill_rect = pygame.Rect(x, y, w * pct, h)
                pygame.draw.rect(self.surface, pbar.fill_color, fill_rect)

            # 6. CheckBoxComponent
            chk = comps.get(CheckBoxComponent)
            if chk:
                size = chk.size * scale_x * min(sx, sy)
                rect = pygame.Rect(x, y, size, size)
                color = chk.checked_color if chk.checked else chk.unchecked_color
                pygame.draw.rect(self.surface, color, rect)
                pygame.draw.rect(self.surface, (0, 0, 0), rect, 1)
                
                if chk.checked:
                    inner_rect = rect.inflate(-4, -4)
                    pygame.draw.rect(self.surface, (255, 255, 255), inner_rect)

            # 7. TextRenderer
            txt = comps.get(TextRenderer)
            if txt:
                font_size = max(8, int(txt.font_size * min(sx, sy)))
                font = self._get_font(txt.font_path, font_size)
                surf = font.render(txt.text, True, txt.color)
                
                if scale_x != 1.0 or scale_y != 1.0:
                    w = surf.get_width() * scale_x
                    h = surf.get_height() * scale_y
                    surf = pygame.transform.scale(surf, (int(w), int(h)))
                
                if rotation != 0:
                    surf = pygame.transform.rotate(surf, -rotation)
                
                self.surface.blit(surf, (x, y))

        if viewport_rect:
            self.surface.set_clip(clip_backup)

    def _get_design_size(self):
        if self.design_size:
            return self.design_size
        return self._cached_surface_size

    def get_camera_views(self, entities: list[Entity], dt: float = 0.0):
        surface_w, surface_h = self._cached_surface_size
        camera_entities = []
        if self.use_camera_components:
            if self.world:
                cam_entities = self.world.get_entities_with(CameraComponent)
            else:
                cam_entities = entities
            for entity in cam_entities:
                camera = entity.get_component(CameraComponent)
                if not camera or not camera.active or camera.viewport_width <= 0 or camera.viewport_height <= 0:
                    continue
                transform = entity.get_component(Transform)
                if not transform:
                    continue
                camera_entities.append((entity, camera))

        if not camera_entities:
            viewport = pygame.Rect(0, 0, surface_w, surface_h)
            return [{
                "entity": None,
                "transform": None,
                "camera": None,
                "x": self.camera_x,
                "y": self.camera_y,
                "zoom": max(0.01, self.camera_zoom),
                "rotation": self.camera_rotation,
                "viewport": viewport
            }]

        # Build transforms only for camera entities and their follow targets
        transforms_by_id = {}
        needed_ids = set()
        for entity, camera in camera_entities:
            needed_ids.add(entity.id)
            target_id = getattr(camera, "follow_target_id", "")
            if target_id:
                needed_ids.add(target_id)
        for entity in entities:
            if entity.id in needed_ids:
                transform = entity.get_component(Transform)
                if transform:
                    transforms_by_id[entity.id] = self._get_entity_transform_values(entity, transform)

        camera_entities.sort(key=lambda item: item[1].priority)
        views = []
        for entity, camera in camera_entities:
            camera_state = self._resolve_followed_camera_state(entity, camera, transforms_by_id)
            if camera_state is None:
                continue
            viewport = self._resolve_camera_viewport(camera, surface_w, surface_h)
            if viewport.width <= 0 or viewport.height <= 0:
                continue
            # P11-1: Update camera shake and apply offset
            cam_x = camera_state[0]
            cam_y = camera_state[1]
            if dt > 0.0:
                camera.update_shake(dt)
            shake_ox, shake_oy = camera.shake_offset
            views.append({
                "entity": entity,
                "transform": camera_state,
                "camera": camera,
                "x": cam_x + shake_ox,
                "y": cam_y + shake_oy,
                "zoom": max(0.01, camera.zoom),
                "rotation": camera_state[2] + camera.rotation,
                "viewport": viewport
            })
        return views

    def get_primary_camera_view(self, entities: list[Entity]):
        views = self.get_camera_views(entities)
        if not views:
            surface_w, surface_h = self._surface_size()
            viewport = pygame.Rect(0, 0, surface_w, surface_h)
            return {
                "entity": None,
                "transform": None,
                "camera": None,
                "x": self.camera_x,
                "y": self.camera_y,
                "zoom": max(0.01, self.camera_zoom),
                "rotation": self.camera_rotation,
                "viewport": viewport
            }
        return views[0]

    def world_to_screen(self, world_x: float, world_y: float, entities: list[Entity] = None, camera_view: dict = None):
        view = camera_view or self.get_primary_camera_view(entities or [])
        dx = world_x - view["x"]
        dy = world_y - view["y"]
        theta = math.radians(view["rotation"])
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        cam_x = (dx * cos_t) + (dy * sin_t)
        cam_y = (-dx * sin_t) + (dy * cos_t)
        viewport = view["viewport"]
        center_x = viewport.x + (viewport.width * 0.5)
        center_y = viewport.y + (viewport.height * 0.5)
        return (
            center_x + (cam_x * view["zoom"]),
            center_y + (cam_y * view["zoom"])
        )

    def screen_to_world(self, screen_x: float, screen_y: float, entities: list[Entity] = None, camera_view: dict = None):
        view = camera_view or self.get_primary_camera_view(entities or [])
        viewport = view["viewport"]
        center_x = viewport.x + (viewport.width * 0.5)
        center_y = viewport.y + (viewport.height * 0.5)
        cam_x = (screen_x - center_x) / view["zoom"]
        cam_y = (screen_y - center_y) / view["zoom"]
        theta = math.radians(view["rotation"])
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        world_dx = (cam_x * cos_t) - (cam_y * sin_t)
        world_dy = (cam_x * sin_t) + (cam_y * cos_t)
        return (
            view["x"] + world_dx,
            view["y"] + world_dy
        )

    def _resolve_camera_viewport(self, camera: CameraComponent, surface_w: int, surface_h: int):
        x = int(max(0.0, min(1.0, camera.viewport_x)) * surface_w)
        y = int(max(0.0, min(1.0, camera.viewport_y)) * surface_h)
        w = int(max(0.0, min(1.0, camera.viewport_width)) * surface_w)
        h = int(max(0.0, min(1.0, camera.viewport_height)) * surface_h)
        if x + w > surface_w:
            w = max(0, surface_w - x)
        if y + h > surface_h:
            h = max(0, surface_h - y)
        return pygame.Rect(x, y, w, h)

    def _surface_size(self):
        if self.surface is None:
            return (800, 600)
        if hasattr(self.surface, "get_size"):
            size = self.surface.get_size()
            if isinstance(size, (tuple, list)) and len(size) == 2:
                return int(size[0]), int(size[1])
        width = 800
        height = 600
        if hasattr(self.surface, "get_width"):
            width = int(self.surface.get_width())
        if hasattr(self.surface, "get_height"):
            height = int(self.surface.get_height())
        return width, height

    def _resolve_followed_camera_state(self, entity: Entity, camera: CameraComponent, transforms_by_id: dict):
        camera_state = transforms_by_id.get(entity.id)
        if camera_state is None:
            return None
        camera_transform = entity.get_component(Transform)
        target_id = getattr(camera, "follow_target_id", "")
        if not target_id or target_id == entity.id:
            if camera_transform:
                camera_transform.x = camera_state[0]
                camera_transform.y = camera_state[1]
                camera_transform.rotation = camera_state[2]
            return camera_state
        target_state = transforms_by_id.get(target_id)
        if target_state is None:
            if camera_transform:
                camera_transform.x = camera_state[0]
                camera_transform.y = camera_state[1]
                camera_transform.rotation = camera_state[2]
            return camera_state
        target_rotation = target_state[2] if getattr(camera, "follow_rotation", True) else camera_state[2]
        if camera_transform:
            camera_transform.x = target_state[0]
            camera_transform.y = target_state[1]
            camera_transform.rotation = target_rotation
        return (target_state[0], target_state[1], target_rotation, camera_state[3], camera_state[4])

    def _get_entity_transform_values(self, entity: Entity, transform: Transform = None):
        if transform is None:
            transform = entity.get_component(Transform)
        if not transform:
            return None
        if self.world and hasattr(self.world, "get_interpolated_transform"):
            interpolated = self.world.get_interpolated_transform(entity, self.interpolation_alpha)
            if interpolated is not None:
                return interpolated
        return (
            float(transform.x),
            float(transform.y),
            float(transform.rotation),
            float(transform.scale_x),
            float(transform.scale_y)
        )

    def _render_camera_view(self, camera_view: dict, entities: list[Entity]):
        viewport = camera_view["viewport"]
        if viewport.width <= 0 or viewport.height <= 0:
            return
        clip_backup = self.surface.get_clip()
        self.surface.set_clip(viewport)
        self._render_particles_layer(camera_view, entities, ParticleEmitterComponent.LAYER_BEHIND)
        
        sorted_entities = self._get_sorted_entities(entities)

        # Pre-compute camera transform constants for frustum culling
        cam_zoom = camera_view["zoom"]
        vp_cx = viewport.x + viewport.width * 0.5
        vp_cy = viewport.y + viewport.height * 0.5
        cam_rotation = camera_view["rotation"]
        theta = math.radians(cam_rotation)
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        cam_x = camera_view["x"]
        cam_y = camera_view["y"]
        # Frustum half-extents with generous margin
        half_w = viewport.width * 0.5 + 200
        half_h = viewport.height * 0.5 + 200

        # P11-5: Collect blit pairs for batching via surface.blits()
        _blit_sequence: list[tuple] = []

        for entity in sorted_entities:
            if not entity.is_visible():
                continue
            comps = entity.components
            transform = comps.get(Transform)
            if not transform:
                continue

            tilemap = comps.get(TilemapComponent)
            if tilemap:
                self._render_tilemap_entity(entity, transform, tilemap, camera_view)
                continue
                
            sprite = comps.get(SpriteRenderer)
            animator = comps.get(AnimatorComponent)
            if not sprite and not animator:
                continue
                
            transform_values = self._get_entity_transform_values(entity, transform)
            if transform_values is None:
                continue
                
            # Inline world_to_screen for frustum culling
            dx = transform_values[0] - cam_x
            dy = transform_values[1] - cam_y
            scr_x = vp_cx + ((dx * cos_t) + (dy * sin_t)) * cam_zoom
            scr_y = vp_cy + ((-dx * sin_t) + (dy * cos_t)) * cam_zoom

            image_to_draw = None
            width = 0
            height = 0
            
            # Check animator first
            if animator:
                frame = animator.get_current_frame()
                if frame is not None:
                    image_to_draw = frame
                    width = frame.get_width() * abs(transform_values[3])
                    height = frame.get_height() * abs(transform_values[4])
                    
            # Fallback to sprite if no animation frame
            if image_to_draw is None and sprite:
                image_to_draw = sprite.image
                width = sprite.width
                height = sprite.height
                
            if image_to_draw is None:
                continue

            scaled_w = int(width * cam_zoom)
            scaled_h = int(height * cam_zoom)
            if scaled_w <= 0 or scaled_h <= 0:
                continue

            # RO-8: Frustum culling — skip if fully off-screen
            half_sprite = max(scaled_w, scaled_h) * 0.75
            if (scr_x + half_sprite < viewport.x or scr_x - half_sprite > viewport.x + viewport.width or
                scr_y + half_sprite < viewport.y or scr_y - half_sprite > viewport.y + viewport.height):
                continue

            # RO-3: Cached sprite scaling (P9-6: LRU eviction instead of per-frame flush)
            img_id = id(image_to_draw)
            scale_key = (img_id, scaled_w, scaled_h)
            image = self._sprite_scale_cache.get(scale_key)
            if image is not None:
                self._sprite_scale_cache.move_to_end(scale_key)
            else:
                image = pygame.transform.scale(image_to_draw, (scaled_w, scaled_h))
                self._sprite_scale_cache[scale_key] = image
                if len(self._sprite_scale_cache) > self._sprite_scale_cache_max:
                    self._sprite_scale_cache.popitem(last=False)

            flip_x = transform_values[3] < 0
            flip_y = transform_values[4] < 0
            if flip_x or flip_y:
                image = pygame.transform.flip(image, flip_x, flip_y)
            relative_rotation = transform_values[2] - cam_rotation
            if relative_rotation != 0:
                image = pygame.transform.rotate(image, -relative_rotation)
            rect = image.get_rect(center=(int(scr_x), int(scr_y)))
            _blit_sequence.append((image, rect))

        # P11-5: Batch all sprite blits in a single call
        if _blit_sequence:
            self.surface.blits(_blit_sequence, doreturn=False)
        self._render_particles_layer(camera_view, entities, ParticleEmitterComponent.LAYER_FRONT)
        self.surface.set_clip(clip_backup)

    def _render_tilemap_entity(self, entity: Entity, transform: Transform, tilemap: TilemapComponent, camera_view: dict):
        frames = tilemap.get_tileset_frames()
        if not frames:
            return
        tilemap.ensure_layer_sizes()

        cell_w = max(1, int(getattr(tilemap, "cell_width", tilemap.tileset.tile_width)))
        cell_h = max(1, int(getattr(tilemap, "cell_height", tilemap.tileset.tile_height)))

        # Treat tilemap transform as top-left anchor in world space.
        origin_x = float(transform.x)
        origin_y = float(transform.y)

        # Culling: compute visible tile bounds based on camera view and viewport size.
        viewport = camera_view["viewport"]
        top_left = self.screen_to_world(float(viewport.left), float(viewport.top), camera_view=camera_view)
        bottom_right = self.screen_to_world(float(viewport.right), float(viewport.bottom), camera_view=camera_view)
        min_x = min(top_left[0], bottom_right[0])
        max_x = max(top_left[0], bottom_right[0])
        min_y = min(top_left[1], bottom_right[1])
        max_y = max(top_left[1], bottom_right[1])

        # For infinite tilemap, no bounds checking
        start_tx = int((min_x - origin_x) // cell_w) - 1
        end_tx = int((max_x - origin_x) // cell_w) + 1
        start_ty = int((min_y - origin_y) // cell_h) - 1
        end_ty = int((max_y - origin_y) // cell_h) + 1

        zoom = max(0.01, float(camera_view["zoom"]))
        scaled_cell_w = max(1, int(cell_w * zoom))
        scaled_cell_h = max(1, int(cell_h * zoom))

        # Cache scaled frames per zoom bucket to reduce repeated scaling.
        if not hasattr(tilemap, "_scaled_frame_cache"):
            tilemap._scaled_frame_cache = {}
        scale_key = (scaled_cell_w, scaled_cell_h)
        scaled_frames = tilemap._scaled_frame_cache.get(scale_key)
        if scaled_frames is None:
            scaled_frames = []
            for frame in frames:
                try:
                    scaled_frames.append(pygame.transform.scale(frame, (scaled_cell_w, scaled_cell_h)))
                except Exception:
                    scaled_frames.append(frame)
            # Keep cache bounded
            if len(tilemap._scaled_frame_cache) > 12:
                tilemap._scaled_frame_cache.clear()
            tilemap._scaled_frame_cache[scale_key] = scaled_frames

        # P9-4: Precompute affine transform constants once instead of
        # calling world_to_screen() per tile (avoids per-tile trig + dict lookups).
        cam_vx = float(camera_view["x"])
        cam_vy = float(camera_view["y"])
        cam_rot = math.radians(camera_view["rotation"])
        cos_t = math.cos(cam_rot)
        sin_t = math.sin(cam_rot)
        cam_zoom = float(camera_view["zoom"])
        vp = camera_view["viewport"]
        vp_cx = vp.x + vp.width * 0.5
        vp_cy = vp.y + vp.height * 0.5
        blit = self.surface.blit

        for layer in tilemap.layers:
            if not getattr(layer, "visible", True):
                continue
            for ty in range(start_ty, end_ty + 1):
                world_y = origin_y + (ty * cell_h) + (cell_h * 0.5)
                dy = world_y - cam_vy
                for tx in range(start_tx, end_tx + 1):
                    tile_id = layer.get_world(tx, ty)
                    if not tile_id:
                        continue
                    frame_index = int(tile_id) - 1
                    if frame_index < 0 or frame_index >= len(scaled_frames):
                        continue
                    world_x = origin_x + (tx * cell_w) + (cell_w * 0.5)
                    dx = world_x - cam_vx
                    sx = vp_cx + (dx * cos_t + dy * sin_t) * cam_zoom
                    sy = vp_cy + (-dx * sin_t + dy * cos_t) * cam_zoom
                    img = scaled_frames[frame_index]
                    rect = img.get_rect(center=(sx, sy))
                    blit(img, rect)

    def _render_particles_layer(self, camera_view: dict, entities: list[Entity], layer: str):
        if self.world:
            particle_entities = self.world.get_entities_with(Transform, ParticleEmitterComponent)
        else:
            particle_entities = entities

        # Pre-compute camera constants once for all particles
        cam_x = camera_view["x"]
        cam_y = camera_view["y"]
        cam_zoom = max(0.01, camera_view["zoom"])
        viewport = camera_view["viewport"]
        vp_cx = viewport.x + viewport.width * 0.5
        vp_cy = viewport.y + viewport.height * 0.5
        theta = math.radians(camera_view["rotation"])
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        surf_w = self._cached_surface_size[0]
        surf_h = self._cached_surface_size[1]
        surface = self.surface
        blit = surface.blit

        for entity in particle_entities:
            if not entity.is_visible():
                continue
            comps = entity.components
            transform = comps.get(Transform)
            emitter = comps.get(ParticleEmitterComponent)
            if not transform or not emitter or emitter.render_layer != layer:
                continue
            transform_values = self._get_entity_transform_values(entity, transform)
            if transform_values is None:
                continue
            state = emitter._particle_state
            if not state:
                continue
            alive = state["alive"]
            if alive <= 0:
                continue

            # Local refs for hot loop
            s_x = state["x"]; s_y = state["y"]
            s_age = state["age"]; s_life = state["life"]
            s_size0 = state["size0"]; s_size1 = state["size1"]
            s_r0 = state["r0"]; s_g0 = state["g0"]; s_b0 = state["b0"]; s_a0 = state["a0"]
            s_r1 = state["r1"]; s_g1 = state["g1"]; s_b1 = state["b1"]; s_a1 = state["a1"]
            local_space = emitter.local_space
            tx_0 = transform_values[0] if local_space else 0.0
            ty_0 = transform_values[1] if local_space else 0.0
            shape = emitter.shape
            blend_add = emitter.blend_additive
            SHAPE_PIXEL = ParticleEmitterComponent.SHAPE_PIXEL
            SHAPE_SQUARE = ParticleEmitterComponent.SHAPE_SQUARE

            for i in range(alive):
                life = s_life[i]
                if life <= 0:
                    continue
                t = s_age[i] / life
                if t > 1.0: t = 1.0
                size = s_size0[i] + ((s_size1[i] - s_size0[i]) * t)
                radius = int(size * cam_zoom * 0.5)
                if radius < 1:
                    radius = 1
                a = int(s_a0[i] + ((s_a1[i] - s_a0[i]) * t))
                if a <= 0:
                    continue
                # Inline world_to_screen
                px = s_x[i] + tx_0 - cam_x
                py = s_y[i] + ty_0 - cam_y
                ix = int(vp_cx + (px * cos_t + py * sin_t) * cam_zoom)
                iy = int(vp_cy + (-px * sin_t + py * cos_t) * cam_zoom)

                if shape == SHAPE_PIXEL:
                    if 0 <= ix < surf_w and 0 <= iy < surf_h:
                        surface.set_at((ix, iy), (
                            int(s_r0[i] + ((s_r1[i] - s_r0[i]) * t)),
                            int(s_g0[i] + ((s_g1[i] - s_g0[i]) * t)),
                            int(s_b0[i] + ((s_b1[i] - s_b0[i]) * t)),
                            a))
                    continue

                r = int(s_r0[i] + ((s_r1[i] - s_r0[i]) * t))
                g = int(s_g0[i] + ((s_g1[i] - s_g0[i]) * t))
                b = int(s_b0[i] + ((s_b1[i] - s_b0[i]) * t))

                if shape == SHAPE_SQUARE:
                    w = max(1, radius * 2)
                    pygame.draw.rect(surface, (r, g, b, a), (ix - radius, iy - radius, w, w))
                    continue

                particle_surface = self._get_particle_surface(radius, r, g, b, a)
                pos = (ix - radius, iy - radius)
                if blend_add:
                    blit(particle_surface, pos, special_flags=pygame.BLEND_RGBA_ADD)
                else:
                    blit(particle_surface, pos)

    def _get_particle_surface(self, radius: int, r: int, g: int, b: int, a: int):
        key = (
            int(max(1, min(96, radius))),
            int(max(0, min(255, (r // 8) * 8))),
            int(max(0, min(255, (g // 8) * 8))),
            int(max(0, min(255, (b // 8) * 8))),
            int(max(0, min(255, (a // 8) * 8)))
        )
        cached = self._particle_surface_cache.get(key)
        if cached is not None:
            self._particle_surface_cache.move_to_end(key)
            return cached

        radius = key[0]
        diameter = radius * 2
        surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        center = radius
        steps = max(2, radius)
        for step in range(steps, 0, -1):
            t = step / steps
            alpha = int(key[4] * (t * t))
            if alpha <= 0:
                continue
            pygame.draw.circle(surface, (key[1], key[2], key[3], alpha), (center, center), max(1, int(radius * t)))
        self._particle_surface_cache[key] = surface
        while len(self._particle_surface_cache) > self._particle_cache_max:
            self._particle_surface_cache.popitem(last=False)
        return surface
