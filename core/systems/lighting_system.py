"""2D Lighting system — renders an ambient + light overlay.

The system draws onto a separate light map surface using additive blending,
then composites it on top of the game surface with BLEND_MULT (multiply mode).
This produces a simple but effective 2D lighting effect.

Supports ``LightOccluder2D`` components for shadow casting: for each light,
shadow volumes are projected from the light centre through occluder edges,
creating proper directional shadows that extend beyond the occluder.

Add the system to the world **after** the RenderSystem so it composites
after all sprites are drawn::

    world.add_system(LightingSystem(render_system.surface))
"""
from __future__ import annotations
import math
import pygame
from core.ecs import System, Entity
from core.components.transform import Transform
from core.components.light import PointLight2D, SpotLight2D, LightOccluder2D

class LightingSystem(System):
    """Renders 2D point and spot lights via a multiply-blended light map."""

    def __init__(self, surface: pygame.Surface, project_config: dict | None = None):
        super().__init__()
        self.update_phase = "render"
        self.priority = 100  # Run after RenderSystem (default priority 0)
        self.surface = surface
        self.ambient_color: tuple = (30, 30, 30)  # Base ambient light RGB
        self.enabled: bool = True
        self._light_map: pygame.Surface | None = None
        self._light_cache: dict[tuple, pygame.Surface] = {}
        self._light_cache_max: int = 64
        # Editor camera override (set externally when use_camera_components=False)
        self.editor_camera_x: float | None = None
        self.editor_camera_y: float | None = None
        self.editor_camera_zoom: float | None = None
        # Read shadow_extend from project config
        self.shadow_extend = 10000  # Default value
        if project_config:
            lighting_cfg = project_config.get("lighting", {})
            self.shadow_extend = int(lighting_cfg.get("shadow_extend", 2000))

    def _ensure_light_map(self):
        """Create or resize the light map to match the target surface."""
        w, h = self.surface.get_size()
        if self._light_map is None or self._light_map.get_size() != (w, h):
            self._light_map = pygame.Surface((w, h))
        return self._light_map

    def _get_point_light_surface(self, radius: int, color: tuple,
                                  intensity: float, falloff: float) -> pygame.Surface:
        """Return a cached radial gradient surface for a point light."""
        key = (radius, color, int(intensity * 100), int(falloff * 100))
        cached = self._light_cache.get(key)
        if cached is not None:
            return cached

        diameter = radius * 2
        surf = pygame.Surface((diameter, diameter))
        surf.fill((0, 0, 0))

        # Draw concentric circles for gradient falloff
        r, g, b = color[:3]
        steps = min(radius, 64)
        for i in range(steps, 0, -1):
            t = i / steps  # 1.0 at edge, ~0 at center
            atten = (1.0 - t ** falloff) * intensity
            atten = max(0.0, min(1.0, atten))
            cr = int(r * atten)
            cg = int(g * atten)
            cb = int(b * atten)
            circle_r = int(radius * (i / steps))
            if circle_r > 0:
                pygame.draw.circle(surf, (cr, cg, cb), (radius, radius), circle_r)

        self._light_cache[key] = surf
        if len(self._light_cache) > self._light_cache_max:
            oldest = next(iter(self._light_cache))
            del self._light_cache[oldest]
        return surf

    def _get_spot_light_surface(self, radius: int, color: tuple,
                                 intensity: float, falloff: float,
                                 cone_angle: float) -> pygame.Surface:
        """Return a cached spot light surface (point light masked by cone)."""
        base = self._get_point_light_surface(radius, color, intensity, falloff).copy()
        diameter = radius * 2

        half_cone = math.radians(cone_angle)
        cx, cy = radius, radius
        points = [(cx, cy)]
        arc_steps = max(8, int(cone_angle / 2))
        for step in range(arc_steps + 1):
            a = -half_cone + (2.0 * half_cone * step / arc_steps)
            px = cx + radius * math.cos(a)
            py = cy + radius * math.sin(a)
            points.append((int(px), int(py)))

        # Fast mask: multiply base by a B/W polygon mask
        mask_rgb = pygame.Surface((diameter, diameter))
        mask_rgb.fill((0, 0, 0))
        if len(points) >= 3:
            pygame.draw.polygon(mask_rgb, (255, 255, 255), points)
        base.blit(mask_rgb, (0, 0), special_flags=pygame.BLEND_MULT)
        return base

    def _resolve_camera(self, entities: list[Entity]):
        """Return (cam_x, cam_y, cam_zoom, cam_rotation) from editor override or render system."""
        # Editor camera override
        if self.editor_camera_x is not None:
            return (
                self.editor_camera_x,
                self.editor_camera_y or 0.0,
                self.editor_camera_zoom or 1.0,
                0.0,
            )
        # Runtime: query the render system's primary camera view
        if self.world:
            for sys in self.world.systems:
                if hasattr(sys, "get_primary_camera_view"):
                    view = sys.get_primary_camera_view(entities)
                    if view:
                        return view["x"], view["y"], view["zoom"], view["rotation"]
        return 0.0, 0.0, 1.0, 0.0

    def update(self, dt: float, entities: list[Entity]):
        if not self.enabled:
            return
        # Only render if there are any lights in the scene
        has_lights = False
        if self.world:
            for lt in (PointLight2D, SpotLight2D):
                if self.world._component_cache.get(lt):
                    has_lights = True
                    break
        if not has_lights:
            return

        light_map = self._ensure_light_map()
        light_map.fill(self.ambient_color)

        cam_x, cam_y, cam_zoom, cam_rotation = self._resolve_camera(entities)

        vp_w, vp_h = self.surface.get_size()
        vp_cx = vp_w * 0.5
        vp_cy = vp_h * 0.5
        theta = math.radians(cam_rotation)
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)

        # Collect lights
        light_entities: list[tuple] = []
        if self.world:
            for light_type in (PointLight2D, SpotLight2D):
                cached = self.world._component_cache.get(light_type)
                if cached:
                    for ent in cached:
                        light = ent.get_component(light_type)
                        transform = ent.get_component(Transform)
                        if light and transform and ent.is_visible():
                            light_entities.append((ent, transform, light))

        # Pre-collect occluder data in screen space.
        # Each entry: (screen_poly, receive_light, receive_shadow)
        occluder_data: list[tuple[list[tuple[float, float]], bool, bool]] = []
        if self.world:
            occluder_cache = self.world._component_cache.get(LightOccluder2D)
            if occluder_cache:
                for ent in occluder_cache:
                    occ = ent.get_component(LightOccluder2D)
                    tr = ent.get_component(Transform)
                    if not occ or not tr or not ent.is_visible():
                        continue
                    odx = (tr.x + occ.offset_x) - cam_x
                    ody = (tr.y + occ.offset_y) - cam_y
                    osx = vp_cx + ((odx * cos_t) + (ody * sin_t)) * cam_zoom
                    osy = vp_cy + ((-odx * sin_t) + (ody * cos_t)) * cam_zoom
                    poly: list[tuple[float, float]] | None = None
                    if occ.shape == "box":
                        hw = occ.width * 0.5 * cam_zoom
                        hh = occ.height * 0.5 * cam_zoom
                        # Apply component rotation
                        total_rot = (tr.rotation + occ.rotation) % 360
                        if abs(total_rot) < 0.001 or abs(total_rot - 360) < 0.001:
                            # Axis-aligned
                            poly = [
                                (osx - hw, osy - hh),
                                (osx + hw, osy - hh),
                                (osx + hw, osy + hh),
                                (osx - hw, osy + hh),
                            ]
                        else:
                            # Rotated box
                            rad = math.radians(total_rot)
                            cos_a = math.cos(rad)
                            sin_a = math.sin(rad)
                            corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
                            poly = []
                            for lx, ly in corners:
                                rx = lx * cos_a - ly * sin_a + osx
                                ry = lx * sin_a + ly * cos_a + osy
                                poly.append((rx, ry))
                    elif occ.shape == "circle":
                        sr = max(1.0, occ.radius * cam_zoom)
                        n_segs = 16
                        poly = []
                        for i in range(n_segs):
                            a = 2.0 * math.pi * i / n_segs
                            poly.append((osx + sr * math.cos(a), osy + sr * math.sin(a)))
                    elif occ.shape == "polygon" and len(occ.points) >= 3:
                        poly = []
                        for p in occ.points:
                            pdx = (tr.x + occ.offset_x + p.x) - cam_x
                            pdy = (tr.y + occ.offset_y + p.y) - cam_y
                            px = vp_cx + ((pdx * cos_t) + (pdy * sin_t)) * cam_zoom
                            py = vp_cy + ((-pdx * sin_t) + (pdy * cos_t)) * cam_zoom
                            poly.append((px, py))
                    if poly:
                        occluder_data.append((poly, occ.receive_light, occ.receive_shadow))

        # Shadow-casting polys (all occluders cast shadows regardless of flags)
        occluder_polys = [od[0] for od in occluder_data]

        # Build an unshadowed light map for occluders with receive_shadow=False.
        # Only created if at least one occluder needs it.
        need_unshadowed = any(not od[2] for od in occluder_data)
        light_map_unshadowed: pygame.Surface | None = None
        if need_unshadowed:
            light_map_unshadowed = pygame.Surface((vp_w, vp_h))
            light_map_unshadowed.fill(self.ambient_color)

        for ent, transform, light in light_entities:
            # World to screen (apply offset for SpotLight2D)
            lx = transform.x
            ly = transform.y
            if isinstance(light, SpotLight2D):
                lx += light.offset_x
                ly += light.offset_y
            dx = lx - cam_x
            dy = ly - cam_y
            scr_x = vp_cx + ((dx * cos_t) + (dy * sin_t)) * cam_zoom
            scr_y = vp_cy + ((-dx * sin_t) + (dy * cos_t)) * cam_zoom

            scaled_radius = int(light.radius * cam_zoom)
            if scaled_radius <= 0:
                continue

            # Frustum cull
            if (scr_x + scaled_radius < 0 or scr_x - scaled_radius > vp_w or
                scr_y + scaled_radius < 0 or scr_y - scaled_radius > vp_h):
                continue

            if isinstance(light, SpotLight2D):
                light_surf = self._get_spot_light_surface(
                    scaled_radius, light.color, light.intensity,
                    light.falloff, light.cone_angle
                )
                total_angle = light.angle - cam_rotation + transform.rotation
                if total_angle != 0:
                    light_surf = pygame.transform.rotate(light_surf, -total_angle)
            else:
                light_surf = self._get_point_light_surface(
                    scaled_radius, light.color, light.intensity, light.falloff
                )

            lw, lh = light_surf.get_size()
            blit_x = int(scr_x - lw * 0.5)
            blit_y = int(scr_y - lh * 0.5)

            # Blit unshadowed light contribution (before shadow stamping)
            if light_map_unshadowed is not None:
                light_map_unshadowed.blit(light_surf, (blit_x, blit_y),
                                          special_flags=pygame.BLEND_ADD)

            # Project shadow volumes from each occluder and stamp them
            # onto the light surface so light is blocked behind occluders.
            if occluder_polys:
                copied = False
                for poly in occluder_polys:
                    shadow_poly = self._build_shadow_polygon(
                        scr_x, scr_y, poly, self.shadow_extend
                    )
                    if shadow_poly is None:
                        continue
                    # Convert to light-surface-local coords
                    local_poly = [(px - blit_x, py - blit_y) for px, py in shadow_poly]
                    # Quick AABB cull
                    xs = [p[0] for p in local_poly]
                    ys = [p[1] for p in local_poly]
                    if max(xs) < 0 or min(xs) > lw or max(ys) < 0 or min(ys) > lh:
                        continue
                    if not copied:
                        light_surf = light_surf.copy()
                        copied = True
                    pygame.draw.polygon(light_surf, (0, 0, 0), local_poly)

            # Additive blit onto light map (with shadows)
            light_map.blit(light_surf, (blit_x, blit_y), special_flags=pygame.BLEND_ADD)

        # Post-process: apply per-occluder receive_light / receive_shadow flags.
        #   receive_light=False  → fill polygon with ambient (no illumination)
        #   receive_shadow=False → replace polygon region with unshadowed lighting
        # receive_light=False takes priority.
        for poly, recv_light, recv_shadow in occluder_data:
            int_poly = [(int(px), int(py)) for px, py in poly]
            if not recv_light:
                pygame.draw.polygon(light_map, self.ambient_color, int_poly)
            elif not recv_shadow and light_map_unshadowed is not None:
                xs = [p[0] for p in int_poly]
                ys = [p[1] for p in int_poly]
                min_x = max(0, min(xs))
                min_y = max(0, min(ys))
                max_x = min(vp_w, max(xs))
                max_y = min(vp_h, max(ys))
                rw = max_x - min_x
                rh = max_y - min_y
                if rw > 0 and rh > 0:
                    local_pts = [(px - min_x, py - min_y) for px, py in int_poly]
                    # Stencil: white polygon on black = multiply mask
                    stencil = pygame.Surface((rw, rh))
                    stencil.fill((0, 0, 0))
                    pygame.draw.polygon(stencil, (255, 255, 255), local_pts)
                    # Get unshadowed patch, mask it to the polygon shape
                    patch = light_map_unshadowed.subsurface(
                        pygame.Rect(min_x, min_y, rw, rh)
                    ).copy()
                    patch.blit(stencil, (0, 0), special_flags=pygame.BLEND_MULT)
                    # Erase polygon region on light_map (fill black)
                    pygame.draw.polygon(light_map, (0, 0, 0), int_poly)
                    # Add the masked unshadowed patch back
                    light_map.blit(patch, (min_x, min_y), special_flags=pygame.BLEND_ADD)

        # Composite: multiply game surface by light map
        self.surface.blit(light_map, (0, 0), special_flags=pygame.BLEND_MULT)

    @staticmethod
    def _build_shadow_polygon(
        lx: float, ly: float,
        occluder_verts: list[tuple[float, float]],
        extend: float,
    ) -> list[tuple[int, int]] | None:
        """Build a shadow polygon projected from a light source through an occluder.

        Returns a polygon that covers the occluder AND the shadow area behind it
        relative to the light. Returns None if the occluder has no visible silhouette
        edges facing the light.

        Algorithm:
        1. Find the two silhouette edges of the occluder polygon relative to the
           light (the leftmost and rightmost vertices when viewed from the light).
        2. Project those two edge vertices away from the light by ``extend`` pixels.
        3. Build a polygon: [near_left, ...occluder..., near_right, far_right, far_left].
        """
        n = len(occluder_verts)
        if n < 2:
            return None

        # Find the two extreme vertices by angle relative to light
        angles = []
        for vx, vy in occluder_verts:
            angles.append(math.atan2(vy - ly, vx - lx))

        # Handle angle wrapping: find the pair with the largest angular span
        # that represents the silhouette from the light's perspective.
        indexed = sorted(range(n), key=lambda i: angles[i])

        # Find the largest gap in the sorted angles — the two vertices
        # adjacent to this gap are the silhouette edges.
        max_gap = -1.0
        gap_idx = 0
        for i in range(n):
            j = (i + 1) % n
            gap = angles[indexed[j]] - angles[indexed[i]]
            if i == n - 1:
                gap = (angles[indexed[0]] + 2.0 * math.pi) - angles[indexed[-1]]
            if gap > max_gap:
                max_gap = gap
                gap_idx = i

        # right_idx is the vertex at the start of the largest gap (rightmost)
        # left_idx is the vertex at the end of the largest gap (leftmost)
        right_sorted_idx = gap_idx
        left_sorted_idx = (gap_idx + 1) % n
        right_vi = indexed[right_sorted_idx]
        left_vi = indexed[left_sorted_idx]

        # Walk from left_vi to right_vi in the sorted-by-angle order
        # (these are the vertices facing the light).
        # The shadow polygon is: far_left, near-side verts (left→right), far_right
        # where the near-side verts are the occluder edges facing the light,
        # and far_left/far_right are projected outward.

        # Collect the "front" vertices in angle order (from left to right)
        front_indices = []
        i = left_sorted_idx
        while True:
            front_indices.append(indexed[i])
            if i == right_sorted_idx:
                break
            i = (i + 1) % n

        if len(front_indices) < 2:
            return None

        # Project the two extremes outward
        lv = occluder_verts[front_indices[0]]
        rv = occluder_verts[front_indices[-1]]

        def _project(vx, vy):
            pdx = vx - lx
            pdy = vy - ly
            dist = math.hypot(pdx, pdy)
            if dist < 0.001:
                return (int(vx), int(vy))
            scale = extend / dist
            return (int(vx + pdx * scale), int(vy + pdy * scale))

        far_left = _project(lv[0], lv[1])
        far_right = _project(rv[0], rv[1])

        # Build the shadow polygon:
        # far_left → near_left → ...front occluder verts... → near_right → far_right
        shadow = [far_left]
        for fi in front_indices:
            v = occluder_verts[fi]
            shadow.append((int(v[0]), int(v[1])))
        shadow.append(far_right)

        if len(shadow) < 3:
            return None
        return shadow
