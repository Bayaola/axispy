import math

class CollisionInfo:
    def __init__(self, normal, penetration):
        self.normal = normal
        self.penetration = penetration

from core.ecs import System, Entity
from core.vector import Vector2
from core.logger import get_logger
from core.components import (
    Transform,
    SpriteRenderer,
    ScriptComponent,
    Rigidbody2D,
    BoxCollider2D,
    CircleCollider2D,
    PolygonCollider2D
)

_physics_logger = get_logger("physics")


class _Body:
    """Lightweight struct for a physics body. Uses __slots__ to avoid per-instance dict overhead."""
    __slots__ = (
        "entity", "transform", "rigidbody", "collider",
        "category_mask", "collision_mask",
        "shape", "center", "radius", "half_w", "half_h",
        "points", "convex_parts", "aabb",
    )

    def __init__(self):
        self.entity = None
        self.transform = None
        self.rigidbody = None
        self.collider = None
        self.category_mask = 1
        self.collision_mask = 0xFFFFFFFF
        self.shape = ""
        self.center = None
        self.radius = 0.0
        self.half_w = 0.0
        self.half_h = 0.0
        self.points = None
        self.convex_parts = None
        self.aabb = (0.0, 0.0, 0.0, 0.0)


class SpatialHashGrid:
    def __init__(self, cell_size: float = 128.0):
        self.cell_size = max(1.0, cell_size)
        self.cells: dict[tuple, set] = {}
        self._entity_cells: dict[Entity, list[tuple]] = {}

    def clear(self):
        self.cells.clear()
        self._entity_cells.clear()

    def _cell_coord(self, x: float, y: float):
        return (int(math.floor(x / self.cell_size)), int(math.floor(y / self.cell_size)))

    def insert(self, entity: Entity, min_x: float, min_y: float, max_x: float, max_y: float):
        min_cx, min_cy = self._cell_coord(min_x, min_y)
        max_cx, max_cy = self._cell_coord(max_x, max_y)
        keys = []
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                key = (cx, cy)
                keys.append(key)
                if key not in self.cells:
                    self.cells[key] = set()
                self.cells[key].add(entity)
        self._entity_cells[entity] = keys

    def remove(self, entity: Entity):
        """Remove *entity* from all cells it currently occupies."""
        keys = self._entity_cells.pop(entity, None)
        if keys is None:
            return
        for key in keys:
            bucket = self.cells.get(key)
            if bucket is not None:
                bucket.discard(entity)
                if not bucket:
                    del self.cells[key]

    def move(self, entity: Entity, min_x: float, min_y: float, max_x: float, max_y: float):
        """Re-insert *entity* only if its cell footprint changed."""
        min_cx, min_cy = self._cell_coord(min_x, min_y)
        max_cx, max_cy = self._cell_coord(max_x, max_y)
        new_keys = []
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                new_keys.append((cx, cy))
        old_keys = self._entity_cells.get(entity)
        if old_keys is not None and new_keys == old_keys:
            return  # No cell change — skip
        # Remove from old cells
        if old_keys is not None:
            for key in old_keys:
                bucket = self.cells.get(key)
                if bucket is not None:
                    bucket.discard(entity)
                    if not bucket:
                        del self.cells[key]
        # Insert into new cells
        for key in new_keys:
            if key not in self.cells:
                self.cells[key] = set()
            self.cells[key].add(entity)
        self._entity_cells[entity] = new_keys

    def query(self, min_x: float, min_y: float, max_x: float, max_y: float):
        results = set()
        min_cx, min_cy = self._cell_coord(min_x, min_y)
        max_cx, max_cy = self._cell_coord(max_x, max_y)

        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                key = (cx, cy)
                if key in self.cells:
                    results |= self.cells[key]
        return results

class PhysicsSystem(System):
    required_components = (Rigidbody2D, BoxCollider2D, CircleCollider2D, PolygonCollider2D)

    def __init__(self, gravity_x: float = 0.0, gravity_y: float = 980.0, cell_size: float = 128.0):
        super().__init__()
        self.gravity = Vector2(gravity_x, gravity_y)
        self.grid = SpatialHashGrid(cell_size)
        self._active_collisions = set()
        self._cached_bodies: list[_Body] | None = None
        self._cached_body_map: dict[Entity, _Body] | None = None
        self._body_frame_id: int = -1
        self._frame_counter: int = 0

    def _get_bodies(self, entities: list[Entity]) -> tuple[list[_Body], dict[Entity, _Body]]:
        """Return cached bodies for this frame, rebuilding only once per tick."""
        if self._body_frame_id == self._frame_counter and self._cached_bodies is not None:
            return self._cached_bodies, self._cached_body_map
        bodies = self._collect_bodies(entities)
        body_map = {b.entity: b for b in bodies}
        self._cached_bodies = bodies
        self._cached_body_map = body_map
        self._body_frame_id = self._frame_counter
        return bodies, body_map

    def update(self, dt: float, entities: list[Entity]):
        if dt <= 0:
            return
        self._frame_counter += 1

        self._integrate_rigidbodies(dt, entities)
        bodies, body_map = self._get_bodies(entities)

        # P9-2: Use incremental grid.move() instead of clear+insert
        # Track which entities are still present so we can remove stale ones
        current_body_entities = set()
        for body in bodies:
            current_body_entities.add(body.entity)
            min_x, min_y, max_x, max_y = body.aabb
            self.grid.move(body.entity, min_x, min_y, max_x, max_y)
        # Remove entities no longer in the body list
        for stale_entity in list(self.grid._entity_cells.keys()):
            if stale_entity not in current_body_entities:
                self.grid.remove(stale_entity)

        seen_pairs = set()
        current_collisions = set()
        id_to_entity = {entity.id: entity for entity in entities}

        for body in bodies:
            min_x, min_y, max_x, max_y = body.aabb
            candidates = self.grid.query(min_x, min_y, max_x, max_y)
            for other_entity in candidates:
                if other_entity is body.entity:
                    continue

                pair_key = tuple(sorted((body.entity.id, other_entity.id)))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                other_body = body_map.get(other_entity)
                if not other_body:
                    continue

                contact = self._check_collision(body, other_body)
                if not contact:
                    continue

                current_collisions.add(pair_key)
                self._resolve_collision(body, other_body, contact)

        entered_collisions = current_collisions - self._active_collisions
        for pair in entered_collisions:
            entity_a = id_to_entity.get(pair[0])
            entity_b = id_to_entity.get(pair[1])
            if entity_a and entity_b:
                # We need to get the contact info for this pair to pass to enter callbacks
                body_a = body_map.get(entity_a)
                body_b = body_map.get(entity_b)
                contact = None
                if body_a and body_b:
                    contact = self._check_collision(body_a, body_b)
                
                if contact:
                    info_a = CollisionInfo(contact["normal"], contact["penetration"])
                    info_b = CollisionInfo(contact["normal"] * -1.0, contact["penetration"])
                else:
                    info_a = CollisionInfo(Vector2(0, 0), 0.0)
                    info_b = CollisionInfo(Vector2(0, 0), 0.0)
                    
                self._notify_collision_enter(entity_a, entity_b, info_a)
                self._notify_collision_enter(entity_b, entity_a, info_b)

        exited_collisions = self._active_collisions - current_collisions
        for pair in exited_collisions:
            entity_a = id_to_entity.get(pair[0])
            entity_b = id_to_entity.get(pair[1])
            if entity_a and entity_b:
                self._notify_collision_exit(entity_a, entity_b)
                self._notify_collision_exit(entity_b, entity_a)

        # Purge stale pairs involving destroyed entities so exit callbacks
        # fire correctly for the surviving entity next frame.
        self._active_collisions = {
            pair for pair in current_collisions
            if pair[0] in id_to_entity and pair[1] in id_to_entity
        }
        # Invalidate body cache at end of physics step
        self._cached_bodies = None
        self._cached_body_map = None

    def _integrate_rigidbodies(self, dt: float, entities: list[Entity]):
        if self.world:
            dynamic_entities = self.world.get_entities_with(Transform, Rigidbody2D)
        else:
            dynamic_entities = [e for e in entities if e.get_component(Transform) and e.get_component(Rigidbody2D)]

        for entity in dynamic_entities:
            if not entity.is_physics_processing():
                continue
            transform = entity.get_component(Transform)
            rigidbody = entity.get_component(Rigidbody2D)
            if not transform or not rigidbody:
                continue

            if rigidbody.is_static:
                rigidbody.velocity.x = 0.0
                rigidbody.velocity.y = 0.0
                rigidbody.angular_velocity = 0.0
                rigidbody.clear_forces()
                continue

            if rigidbody.is_kinematic:
                if rigidbody.freeze_rotation:
                    rigidbody.angular_velocity = 0.0
                transform.x += rigidbody.velocity.x * dt
                transform.y += rigidbody.velocity.y * dt
                transform.rotation += rigidbody.angular_velocity * dt
                rigidbody.clear_forces()
                continue

            acceleration = Vector2(0.0, 0.0)
            if rigidbody.use_gravity:
                acceleration.x += self.gravity.x * rigidbody.gravity_scale
                acceleration.y += self.gravity.y * rigidbody.gravity_scale

            if rigidbody.mass > 0.0:
                acceleration.x += rigidbody.force_x / rigidbody.mass
                acceleration.y += rigidbody.force_y / rigidbody.mass

            rigidbody.velocity.x += acceleration.x * dt
            rigidbody.velocity.y += acceleration.y * dt

            if rigidbody.linear_damping > 0.0:
                damping_factor = max(0.0, 1.0 - rigidbody.linear_damping * dt)
                rigidbody.velocity.x *= damping_factor
                rigidbody.velocity.y *= damping_factor

            if rigidbody.freeze_rotation:
                rigidbody.angular_velocity = 0.0
            else:
                if rigidbody.mass > 0.0:
                    angular_acceleration = rigidbody.torque / rigidbody.mass
                    rigidbody.angular_velocity += angular_acceleration * dt
                if rigidbody.angular_damping > 0.0:
                    angular_damping_factor = max(0.0, 1.0 - rigidbody.angular_damping * dt)
                    rigidbody.angular_velocity *= angular_damping_factor

            transform.x += rigidbody.velocity.x * dt
            transform.y += rigidbody.velocity.y * dt
            transform.rotation += rigidbody.angular_velocity * dt
            rigidbody.clear_forces()

    def _collect_bodies(self, entities: list[Entity]):
        if self.world:
            # Build candidate set by iterating cached lists directly — avoids
            # three set() copies and two union operations.
            _cache = self.world._component_cache
            candidate_entities: set[Entity] = set()
            for collider_type in (BoxCollider2D, CircleCollider2D, PolygonCollider2D):
                s = _cache.get(collider_type)
                if s:
                    candidate_entities.update(s)
            # Intersect with Transform owners (cheap: discard those without Transform)
            transform_set = _cache.get(Transform)
            if transform_set is not None:
                candidate_entities &= transform_set
            else:
                candidate_entities.clear()
        else:
            candidate_entities = set()
            for entity in entities:
                has_transform = entity.get_component(Transform) is not None
                has_box = entity.get_component(BoxCollider2D) is not None
                has_circle = entity.get_component(CircleCollider2D) is not None
                has_polygon = entity.get_component(PolygonCollider2D) is not None
                if has_transform and (has_box or has_circle or has_polygon):
                    candidate_entities.add(entity)

        bodies: list[_Body] = []
        for entity in candidate_entities:
            if not entity.is_physics_processing():
                continue
            transform = entity.get_component(Transform)
            rigidbody = entity.get_component(Rigidbody2D)
            sprite = entity.get_component(SpriteRenderer)
            box = entity.get_component(BoxCollider2D)
            circle = entity.get_component(CircleCollider2D)
            polygon = entity.get_component(PolygonCollider2D)

            if circle:
                radius = circle.radius
                if radius is None:
                    if sprite:
                        radius = min(sprite.width, sprite.height) * 0.5
                    else:
                        radius = 25.0 * (abs(transform.scale_x) + abs(transform.scale_y)) * 0.5
                cx = transform.x + circle.offset.x
                cy = transform.y + circle.offset.y
                b = _Body()
                b.entity = entity
                b.transform = transform
                b.rigidbody = rigidbody
                b.collider = circle
                b.category_mask = self._get_effective_category_mask(entity, circle)
                b.collision_mask = self._get_effective_collision_mask(entity, circle)
                b.shape = "circle"
                b.center = Vector2(cx, cy)
                b.radius = radius
                b.aabb = (cx - radius, cy - radius, cx + radius, cy + radius)
                bodies.append(b)
            elif polygon:
                world_points = self._polygon_world_points(transform, polygon)
                if len(world_points) < 3:
                    continue
                convex_parts = self._decompose_polygon(world_points)
                min_x = min(point.x for point in world_points)
                min_y = min(point.y for point in world_points)
                max_x = max(point.x for point in world_points)
                max_y = max(point.y for point in world_points)
                b = _Body()
                b.entity = entity
                b.transform = transform
                b.rigidbody = rigidbody
                b.collider = polygon
                b.category_mask = self._get_effective_category_mask(entity, polygon)
                b.collision_mask = self._get_effective_collision_mask(entity, polygon)
                b.shape = "polygon"
                b.center = self._compute_polygon_center(world_points)
                b.points = world_points
                b.convex_parts = convex_parts
                b.aabb = (min_x, min_y, max_x, max_y)
                bodies.append(b)
            elif box:
                width = box.width
                height = box.height
                if width is None:
                    width = sprite.width if sprite else 50.0 * abs(transform.scale_x)
                if height is None:
                    height = sprite.height if sprite else 50.0 * abs(transform.scale_y)
                cx = transform.x + box.offset.x
                cy = transform.y + box.offset.y
                half_w = abs(width) * 0.5
                half_h = abs(height) * 0.5

                rot = (transform.rotation + box.rotation) % 360
                if abs(rot) < 0.001 or abs(rot - 360) < 0.001:
                    # Axis-aligned fast path
                    b = _Body()
                    b.entity = entity
                    b.transform = transform
                    b.rigidbody = rigidbody
                    b.collider = box
                    b.category_mask = self._get_effective_category_mask(entity, box)
                    b.collision_mask = self._get_effective_collision_mask(entity, box)
                    b.shape = "box"
                    b.center = Vector2(cx, cy)
                    b.half_w = half_w
                    b.half_h = half_h
                    b.aabb = (cx - half_w, cy - half_h, cx + half_w, cy + half_h)
                    bodies.append(b)
                else:
                    # Rotated box → emit as polygon
                    rad = math.radians(rot)
                    cos_a = math.cos(rad)
                    sin_a = math.sin(rad)
                    corners = [(-half_w, -half_h), (half_w, -half_h),
                               (half_w, half_h), (-half_w, half_h)]
                    world_points = []
                    for lx, ly in corners:
                        rx = lx * cos_a - ly * sin_a + cx
                        ry = lx * sin_a + ly * cos_a + cy
                        world_points.append(Vector2(rx, ry))
                    min_x = min(p.x for p in world_points)
                    min_y = min(p.y for p in world_points)
                    max_x = max(p.x for p in world_points)
                    max_y = max(p.y for p in world_points)
                    b = _Body()
                    b.entity = entity
                    b.transform = transform
                    b.rigidbody = rigidbody
                    b.collider = box
                    b.category_mask = self._get_effective_category_mask(entity, box)
                    b.collision_mask = self._get_effective_collision_mask(entity, box)
                    b.shape = "polygon"
                    b.center = Vector2(cx, cy)
                    b.points = world_points
                    b.convex_parts = [world_points]
                    b.aabb = (min_x, min_y, max_x, max_y)
                    bodies.append(b)
        return bodies

    def _get_effective_category_mask(self, entity: Entity, collider):
        default_category = getattr(collider, "category_mask", 1)
        group_order = getattr(self.world, "physics_group_order", None)
        if not group_order:
            return default_category
        mask = 0
        entity_groups = getattr(entity, "groups", set()) or set()
        for index, group_name in enumerate(group_order):
            if group_name in entity_groups:
                mask |= (1 << index)
        return mask if mask else default_category

    def _get_effective_collision_mask(self, entity: Entity, collider):
        default_mask = getattr(collider, "collision_mask", 0xFFFFFFFF)
        group_order = getattr(self.world, "physics_group_order", None)
        collision_matrix = getattr(self.world, "physics_collision_matrix", None)
        if not group_order or not isinstance(collision_matrix, dict):
            return default_mask
        group_to_index = {name: index for index, name in enumerate(group_order)}
        entity_groups = [name for name in group_order if name in (getattr(entity, "groups", set()) or set())]
        if not entity_groups:
            return default_mask
        mask = 0
        for group_name in entity_groups:
            allowed_groups = collision_matrix.get(group_name, group_order)
            if not isinstance(allowed_groups, list):
                continue
            for target_name in allowed_groups:
                target_index = group_to_index.get(target_name)
                if target_index is None:
                    continue
                mask |= (1 << target_index)
        return mask

    def _check_collision(self, body_a, body_b):
        # Collision Mask filtering
        # Check if A's category is in B's mask AND B's category is in A's mask
        # Masks are integers (bitmasks)
        cat_a = body_a.category_mask
        mask_a = body_a.collision_mask
        cat_b = body_b.category_mask
        mask_b = body_b.collision_mask
        
        if not (cat_a & mask_b) or not (cat_b & mask_a):
            return None

        shape_a = body_a.shape
        shape_b = body_b.shape

        if shape_a == "box" and shape_b == "box":
            return self._box_box_collision(body_a, body_b)
        if shape_a == "circle" and shape_b == "circle":
            return self._circle_circle_collision(body_a, body_b)
        if shape_a == "circle" and shape_b == "box":
            return self._circle_box_collision(body_a, body_b)
        if shape_a == "box" and shape_b == "circle":
            contact = self._circle_box_collision(body_b, body_a)
            if not contact:
                return None
            return {"normal": contact["normal"] * -1.0, "penetration": contact["penetration"]}
        if shape_a == "polygon" and shape_b == "polygon":
            return self._polygon_polygon_collision(body_a, body_b)
        if shape_a == "polygon" and shape_b == "box":
            return self._polygon_polygon_collision(body_a, self._polygon_like_box(body_b))
        if shape_a == "box" and shape_b == "polygon":
            contact = self._polygon_polygon_collision(self._polygon_like_box(body_a), body_b)
            if not contact:
                return None
            return contact
        if shape_a == "polygon" and shape_b == "circle":
            return self._polygon_circle_collision(body_a, body_b)
        if shape_a == "circle" and shape_b == "polygon":
            contact = self._polygon_circle_collision(body_b, body_a)
            if not contact:
                return None
            return {"normal": contact["normal"] * -1.0, "penetration": contact["penetration"]}
        return None

    def _box_box_collision(self, body_a, body_b):
        delta_x = body_b.center.x - body_a.center.x
        overlap_x = (body_a.half_w + body_b.half_w) - abs(delta_x)
        if overlap_x <= 0:
            return None

        delta_y = body_b.center.y - body_a.center.y
        overlap_y = (body_a.half_h + body_b.half_h) - abs(delta_y)
        if overlap_y <= 0:
            return None

        if overlap_x < overlap_y:
            normal = Vector2(1.0, 0.0) if delta_x >= 0 else Vector2(-1.0, 0.0)
            penetration = overlap_x
        else:
            normal = Vector2(0.0, 1.0) if delta_y >= 0 else Vector2(0.0, -1.0)
            penetration = overlap_y
        return {"normal": normal, "penetration": penetration}

    def _circle_circle_collision(self, body_a, body_b):
        delta = body_b.center - body_a.center
        distance = delta.magnitude()
        radius_sum = body_a.radius + body_b.radius

        if distance >= radius_sum:
            return None

        if distance == 0:
            normal = Vector2(1.0, 0.0)
        else:
            normal = delta / distance

        penetration = radius_sum - distance
        return {"normal": normal, "penetration": penetration}

    def _circle_box_collision(self, circle_body, box_body):
        cx = circle_body.center.x
        cy = circle_body.center.y
        bx = box_body.center.x
        by = box_body.center.y
        half_w = box_body.half_w
        half_h = box_body.half_h

        min_x = bx - half_w
        max_x = bx + half_w
        min_y = by - half_h
        max_y = by + half_h

        closest_x = max(min_x, min(cx, max_x))
        closest_y = max(min_y, min(cy, max_y))
        dx = cx - closest_x
        dy = cy - closest_y
        dist_sq = dx * dx + dy * dy
        radius = circle_body.radius

        if dist_sq > radius * radius:
            return None

        if dist_sq > 0:
            distance = math.sqrt(dist_sq)
            normal = Vector2(-dx / distance, -dy / distance)
            penetration = radius - distance
            return {"normal": normal, "penetration": penetration}

        distances = [
            (Vector2(-1.0, 0.0), cx - min_x),
            (Vector2(1.0, 0.0), max_x - cx),
            (Vector2(0.0, -1.0), cy - min_y),
            (Vector2(0.0, 1.0), max_y - cy)
        ]
        normal, min_distance = min(distances, key=lambda item: item[1])
        penetration = radius + min_distance
        return {"normal": normal, "penetration": penetration}

    def _polygon_world_points(self, transform: Transform, polygon: PolygonCollider2D):
        if not polygon.points:
            return []
        return [
            Vector2(
                transform.x + polygon.offset.x + point.x,
                transform.y + polygon.offset.y + point.y
            )
            for point in polygon.points
        ]

    def _compute_polygon_center(self, points: list[Vector2]):
        if not points:
            return Vector2(0.0, 0.0)
        sum_x = 0.0
        sum_y = 0.0
        for point in points:
            sum_x += point.x
            sum_y += point.y
        inv_count = 1.0 / len(points)
        return Vector2(sum_x * inv_count, sum_y * inv_count)

    def _polygon_like_box(self, body):
        center = body.center
        half_w = body.half_w
        half_h = body.half_h
        points = [
            Vector2(center.x - half_w, center.y - half_h),
            Vector2(center.x + half_w, center.y - half_h),
            Vector2(center.x + half_w, center.y + half_h),
            Vector2(center.x - half_w, center.y + half_h)
        ]
        converted = _Body()
        converted.entity = body.entity
        converted.transform = body.transform
        converted.rigidbody = body.rigidbody
        converted.collider = body.collider
        converted.category_mask = body.category_mask
        converted.collision_mask = body.collision_mask
        converted.shape = "polygon"
        converted.center = center
        converted.points = points
        converted.convex_parts = [points]
        converted.aabb = body.aabb
        return converted

    def _polygon_signed_area(self, points: list[Vector2]):
        if len(points) < 3:
            return 0.0
        area = 0.0
        for index in range(len(points)):
            current = points[index]
            nxt = points[(index + 1) % len(points)]
            area += (current.x * nxt.y) - (nxt.x * current.y)
        return area * 0.5

    def _point_in_triangle(self, point: Vector2, a: Vector2, b: Vector2, c: Vector2):
        ab = self._cross_2d(b - a, point - a)
        bc = self._cross_2d(c - b, point - b)
        ca = self._cross_2d(a - c, point - c)
        has_negative = (ab < -1e-8) or (bc < -1e-8) or (ca < -1e-8)
        has_positive = (ab > 1e-8) or (bc > 1e-8) or (ca > 1e-8)
        return not (has_negative and has_positive)

    def _is_polygon_convex(self, points: list[Vector2]):
        if len(points) < 4:
            return True
        sign = 0
        for index in range(len(points)):
            a = points[index]
            b = points[(index + 1) % len(points)]
            c = points[(index + 2) % len(points)]
            cross_value = self._cross_2d(b - a, c - b)
            if abs(cross_value) <= 1e-8:
                continue
            current_sign = 1 if cross_value > 0.0 else -1
            if sign == 0:
                sign = current_sign
            elif sign != current_sign:
                return False
        return True

    def _decompose_polygon(self, points: list[Vector2]):
        if len(points) < 3:
            return []
        if len(points) == 3:
            return [[Vector2(point.x, point.y) for point in points]]
        if self._is_polygon_convex(points):
            return [[Vector2(point.x, point.y) for point in points]]

        polygon = [Vector2(point.x, point.y) for point in points]
        area = self._polygon_signed_area(polygon)
        if abs(area) <= 1e-8:
            return [[Vector2(point.x, point.y) for point in polygon]]

        if area < 0.0:
            polygon.reverse()

        indices = list(range(len(polygon)))
        triangles = []
        guard = 0

        while len(indices) > 3 and guard < len(polygon) * len(polygon):
            ear_found = False
            for i in range(len(indices)):
                prev_index = indices[(i - 1) % len(indices)]
                curr_index = indices[i]
                next_index = indices[(i + 1) % len(indices)]
                a = polygon[prev_index]
                b = polygon[curr_index]
                c = polygon[next_index]

                cross_value = self._cross_2d(b - a, c - b)
                if cross_value <= 1e-8:
                    continue

                contains_point = False
                for other_index in indices:
                    if other_index in (prev_index, curr_index, next_index):
                        continue
                    if self._point_in_triangle(polygon[other_index], a, b, c):
                        contains_point = True
                        break
                if contains_point:
                    continue

                triangles.append([Vector2(a.x, a.y), Vector2(b.x, b.y), Vector2(c.x, c.y)])
                del indices[i]
                ear_found = True
                break

            if not ear_found:
                break
            guard += 1

        if len(indices) == 3:
            a = polygon[indices[0]]
            b = polygon[indices[1]]
            c = polygon[indices[2]]
            triangles.append([Vector2(a.x, a.y), Vector2(b.x, b.y), Vector2(c.x, c.y)])

        if triangles:
            return triangles
        return [[Vector2(point.x, point.y) for point in polygon]]

    def _polygon_axes(self, points: list[Vector2]):
        axes = []
        point_count = len(points)
        for i in range(point_count):
            current = points[i]
            nxt = points[(i + 1) % point_count]
            edge = nxt - current
            axis = Vector2(-edge.y, edge.x)
            magnitude = axis.magnitude()
            if magnitude <= 1e-8:
                continue
            axes.append(axis / magnitude)
        return axes

    def _project_points(self, points: list[Vector2], axis: Vector2):
        first = self._dot(points[0], axis)
        min_proj = first
        max_proj = first
        for point in points[1:]:
            projection = self._dot(point, axis)
            if projection < min_proj:
                min_proj = projection
            if projection > max_proj:
                max_proj = projection
        return min_proj, max_proj

    def _interval_overlap(self, min_a: float, max_a: float, min_b: float, max_b: float):
        return min(max_a, max_b) - max(min_a, min_b)

    def _convex_polygon_polygon_collision(self, points_a: list[Vector2], points_b: list[Vector2], center_a: Vector2, center_b: Vector2):
        axes = self._polygon_axes(points_a) + self._polygon_axes(points_b)
        if not axes:
            return None

        min_overlap = float("inf")
        best_axis = None

        for axis in axes:
            min_a, max_a = self._project_points(points_a, axis)
            min_b, max_b = self._project_points(points_b, axis)
            overlap = self._interval_overlap(min_a, max_a, min_b, max_b)
            if overlap <= 0.0:
                return None
            if overlap < min_overlap:
                min_overlap = overlap
                best_axis = axis

        if best_axis is None:
            return None

        center_delta = center_b - center_a
        if self._dot(center_delta, best_axis) < 0.0:
            best_axis = best_axis * -1.0

        return {"normal": best_axis, "penetration": min_overlap}

    def _polygon_polygon_collision(self, body_a, body_b):
        parts_a = body_a.convex_parts or [body_a.points]
        parts_b = body_b.convex_parts or [body_b.points]
        best_contact = None

        for points_a in parts_a:
            center_a = self._compute_polygon_center(points_a)
            for points_b in parts_b:
                center_b = self._compute_polygon_center(points_b)
                contact = self._convex_polygon_polygon_collision(points_a, points_b, center_a, center_b)
                if not contact:
                    continue
                if best_contact is None or contact["penetration"] < best_contact["penetration"]:
                    best_contact = contact
        return best_contact

    def _convex_polygon_circle_collision(self, polygon_points: list[Vector2], polygon_center: Vector2, circle_body):
        if not polygon_points:
            return None
        circle_center = circle_body.center
        circle_radius = circle_body.radius
        axes = self._polygon_axes(polygon_points)

        closest_point = min(
            polygon_points,
            key=lambda point: (point.x - circle_center.x) ** 2 + (point.y - circle_center.y) ** 2
        )
        center_to_point = closest_point - circle_center
        closest_distance = center_to_point.magnitude()
        if closest_distance > 1e-8:
            axes.append(center_to_point / closest_distance)

        if not axes:
            return None

        min_overlap = float("inf")
        best_axis = None

        for axis in axes:
            poly_min, poly_max = self._project_points(polygon_points, axis)
            center_projection = self._dot(circle_center, axis)
            circle_min = center_projection - circle_radius
            circle_max = center_projection + circle_radius
            overlap = self._interval_overlap(poly_min, poly_max, circle_min, circle_max)
            if overlap <= 0.0:
                return None
            if overlap < min_overlap:
                min_overlap = overlap
                best_axis = axis

        if best_axis is None:
            return None

        center_delta = circle_center - polygon_center
        if self._dot(center_delta, best_axis) < 0.0:
            best_axis = best_axis * -1.0

        return {"normal": best_axis, "penetration": min_overlap}

    def _polygon_circle_collision(self, polygon_body, circle_body):
        parts = polygon_body.convex_parts or [polygon_body.points]
        best_contact = None
        for polygon_points in parts:
            polygon_center = self._compute_polygon_center(polygon_points)
            contact = self._convex_polygon_circle_collision(polygon_points, polygon_center, circle_body)
            if not contact:
                continue
            if best_contact is None or contact["penetration"] < best_contact["penetration"]:
                best_contact = contact
        return best_contact

    def _resolve_collision(self, body_a, body_b, contact):
        collider_a = body_a.collider
        collider_b = body_b.collider
        if getattr(collider_a, "is_trigger", False) or getattr(collider_b, "is_trigger", False):
            return

        rigidbody_a = body_a.rigidbody
        rigidbody_b = body_b.rigidbody
        dynamic_a = rigidbody_a is not None and rigidbody_a.is_dynamic
        dynamic_b = rigidbody_b is not None and rigidbody_b.is_dynamic
        inv_mass_a = self._inverse_mass(rigidbody_a, dynamic_a)
        inv_mass_b = self._inverse_mass(rigidbody_b, dynamic_b)

        if inv_mass_a + inv_mass_b <= 0.0:
            return

        normal = contact["normal"]
        penetration = max(0.0, contact["penetration"])
        restitution_values = []
        if rigidbody_a:
            restitution_values.append(rigidbody_a.elasticity)
        if rigidbody_b:
            restitution_values.append(rigidbody_b.elasticity)
        restitution = min(restitution_values) if restitution_values else 0.0

        total_inverse_mass = inv_mass_a + inv_mass_b
        if penetration > 0.0:
            slop = 0.01
            percent = 0.8
            correction_magnitude = (max(penetration - slop, 0.0) / total_inverse_mass) * percent
            correction = normal * correction_magnitude
            if inv_mass_a > 0.0:
                body_a.transform.x -= correction.x * inv_mass_a
                body_a.transform.y -= correction.y * inv_mass_a
            if inv_mass_b > 0.0:
                body_b.transform.x += correction.x * inv_mass_b
                body_b.transform.y += correction.y * inv_mass_b

        velocity_a = rigidbody_a.velocity if rigidbody_a else Vector2(0.0, 0.0)
        velocity_b = rigidbody_b.velocity if rigidbody_b else Vector2(0.0, 0.0)
        relative_velocity = velocity_b - velocity_a
        velocity_along_normal = self._dot(relative_velocity, normal)
        if velocity_along_normal > 0.0:
            return

        impulse_scalar = -(1.0 + restitution) * velocity_along_normal
        impulse_scalar /= total_inverse_mass
        impulse = normal * impulse_scalar

        if inv_mass_a > 0.0 and rigidbody_a:
            rigidbody_a.velocity -= impulse * inv_mass_a
        if inv_mass_b > 0.0 and rigidbody_b:
            rigidbody_b.velocity += impulse * inv_mass_b

        # Coulomb friction: tangential impulse clamped by mu * |normal impulse|
        mu_a = float(getattr(rigidbody_a, "friction", 0.0)) if rigidbody_a else 0.0
        mu_b = float(getattr(rigidbody_b, "friction", 0.0)) if rigidbody_b else 0.0
        mu = min(max(0.0, mu_a), max(0.0, mu_b))
        if mu <= 0.0 or total_inverse_mass <= 0.0:
            return

        velocity_a = rigidbody_a.velocity if rigidbody_a else Vector2(0.0, 0.0)
        velocity_b = rigidbody_b.velocity if rigidbody_b else Vector2(0.0, 0.0)
        relative_velocity = velocity_b - velocity_a
        tangent = Vector2(-normal.y, normal.x)
        vt = self._dot(relative_velocity, tangent)
        if abs(vt) < 1e-8:
            return

        j_t_raw = -vt / total_inverse_mass
        j_n_mag = abs(impulse_scalar)
        max_f = mu * j_n_mag
        j_t = max(-max_f, min(max_f, j_t_raw))
        friction_impulse = tangent * j_t

        if inv_mass_a > 0.0 and rigidbody_a:
            rigidbody_a.velocity -= friction_impulse * inv_mass_a
        if inv_mass_b > 0.0 and rigidbody_b:
            rigidbody_b.velocity += friction_impulse * inv_mass_b

    def _notify_collision_enter(self, entity: Entity, other: Entity, collision_info: CollisionInfo):
        script_component = entity.get_component(ScriptComponent)
        if script_component and script_component.instance and hasattr(script_component.instance, "on_collision_enter"):
            try:
                script_component.instance.on_collision_enter(other, collision_info)
            except Exception as e:
                _physics_logger.error("Error in collision callback", entity=entity.name, error=str(e))
        entity.events.emit_immediate("collision_enter", other, collision_info)

    def _notify_collision_exit(self, entity: Entity, other: Entity):
        script_component = entity.get_component(ScriptComponent)
        if script_component and script_component.instance and hasattr(script_component.instance, "on_collision_exit"):
            try:
                script_component.instance.on_collision_exit(other)
            except Exception as e:
                _physics_logger.error("Error in collision_exit callback", entity=entity.name, error=str(e))
        entity.events.emit_immediate("collision_exit", other)

    # ------------------------------------------------------------------
    # Area query / trigger zone API
    # ------------------------------------------------------------------

    def overlap_box(self, center: Vector2, half_extents: Vector2,
                    category_mask: int = 0xFFFFFFFF) -> list[Entity]:
        """Return all entities whose colliders overlap an axis-aligned box.

        Args:
            center: World-space centre of the query box.
            half_extents: Half-width and half-height as a Vector2.
            category_mask: Bitmask filter — only bodies whose category_mask
                           overlaps this value are returned.

        Returns:
            List of overlapping entities (unordered).
        """
        qx, qy = center.x, center.y
        hw, hh = abs(half_extents.x), abs(half_extents.y)
        q_min_x, q_min_y = qx - hw, qy - hh
        q_max_x, q_max_y = qx + hw, qy + hh

        # Broadphase via spatial hash
        candidates = self.grid.query(q_min_x, q_min_y, q_max_x, q_max_y)
        bodies, body_map = self._get_bodies(self.world.entities if self.world else [])

        results: list[Entity] = []
        for entity in candidates:
            body = body_map.get(entity)
            if body is None:
                continue
            if not (body.category_mask & category_mask):
                continue
            # AABB overlap test (narrowphase for box query)
            b_min_x, b_min_y, b_max_x, b_max_y = body.aabb
            if b_max_x < q_min_x or b_min_x > q_max_x:
                continue
            if b_max_y < q_min_y or b_min_y > q_max_y:
                continue
            results.append(entity)
        return results

    def overlap_circle(self, center: Vector2, radius: float,
                       category_mask: int = 0xFFFFFFFF) -> list[Entity]:
        """Return all entities whose colliders overlap a circle.

        Args:
            center: World-space centre of the query circle.
            radius: Radius of the query circle.
            category_mask: Bitmask filter.

        Returns:
            List of overlapping entities (unordered).
        """
        r = abs(radius)
        q_min_x, q_min_y = center.x - r, center.y - r
        q_max_x, q_max_y = center.x + r, center.y + r

        candidates = self.grid.query(q_min_x, q_min_y, q_max_x, q_max_y)
        bodies, body_map = self._get_bodies(self.world.entities if self.world else [])

        results: list[Entity] = []
        r_sq = r * r
        for entity in candidates:
            body = body_map.get(entity)
            if body is None:
                continue
            if not (body.category_mask & category_mask):
                continue
            # Circle-vs-AABB overlap: find closest point on AABB to circle centre
            b_min_x, b_min_y, b_max_x, b_max_y = body.aabb
            closest_x = max(b_min_x, min(center.x, b_max_x))
            closest_y = max(b_min_y, min(center.y, b_max_y))
            dx = center.x - closest_x
            dy = center.y - closest_y
            if dx * dx + dy * dy <= r_sq:
                results.append(entity)
        return results

    # ------------------------------------------------------------------
    # Raycasting API
    # ------------------------------------------------------------------

    def raycast(self, origin: Vector2, direction: Vector2, max_distance: float = float("inf"),
                category_mask: int = 0xFFFFFFFF) -> list[dict]:
        """Cast a ray and return all intersecting collider bodies sorted by distance.

        Args:
            origin: World-space start point of the ray.
            direction: Direction vector (does not need to be normalized).
            max_distance: Maximum ray length in world units.
            category_mask: Bitmask — only bodies whose category_mask overlaps
                           this value are tested.

        Returns:
            A list of hit dicts sorted by ascending distance, each containing:
                - entity: the hit Entity
                - point: Vector2 world-space hit point
                - normal: Vector2 surface normal at hit
                - distance: float distance from origin
        """
        mag = direction.magnitude()
        if mag < 1e-12:
            return []
        d = Vector2(direction.x / mag, direction.y / mag)
        end = Vector2(origin.x + d.x * max_distance, origin.y + d.y * max_distance)

        bodies, _ = self._get_bodies(self.world.entities if self.world else [])
        hits: list[dict] = []

        for body in bodies:
            # Mask filter
            cat = body.category_mask
            if not (cat & category_mask):
                continue

            shape = body.shape
            hit = None

            if shape == "circle":
                hit = self._ray_circle(origin, d, max_distance, body.center, body.radius)
            elif shape == "box":
                hit = self._ray_aabb(origin, d, max_distance, body.center, body.half_w, body.half_h)
            elif shape == "polygon":
                hit = self._ray_polygon(origin, d, max_distance, body.points or [])

            if hit is not None:
                hit["entity"] = body.entity
                hits.append(hit)

        hits.sort(key=lambda h: h["distance"])
        return hits

    def raycast_first(self, origin: Vector2, direction: Vector2, max_distance: float = float("inf"),
                      category_mask: int = 0xFFFFFFFF):
        """Convenience: return only the closest hit, or None."""
        results = self.raycast(origin, direction, max_distance, category_mask)
        return results[0] if results else None

    # --- Ray vs shape helpers ---

    def _ray_circle(self, origin: Vector2, d: Vector2, max_dist: float,
                    center: Vector2, radius: float):
        oc = Vector2(origin.x - center.x, origin.y - center.y)
        a = d.x * d.x + d.y * d.y
        b = 2.0 * (oc.x * d.x + oc.y * d.y)
        c = oc.x * oc.x + oc.y * oc.y - radius * radius
        disc = b * b - 4.0 * a * c
        if disc < 0:
            return None
        sqrt_disc = math.sqrt(disc)
        t = (-b - sqrt_disc) / (2.0 * a)
        if t < 0:
            t = (-b + sqrt_disc) / (2.0 * a)
        if t < 0 or t > max_dist:
            return None
        px = origin.x + d.x * t
        py = origin.y + d.y * t
        nx = px - center.x
        ny = py - center.y
        nm = math.sqrt(nx * nx + ny * ny)
        if nm > 1e-12:
            nx /= nm
            ny /= nm
        return {"point": Vector2(px, py), "normal": Vector2(nx, ny), "distance": t}

    def _ray_aabb(self, origin: Vector2, d: Vector2, max_dist: float,
                  center: Vector2, half_w: float, half_h: float):
        min_x = center.x - half_w
        max_x = center.x + half_w
        min_y = center.y - half_h
        max_y = center.y + half_h

        if abs(d.x) < 1e-12:
            if origin.x < min_x or origin.x > max_x:
                return None
            tx_min, tx_max = -1e30, 1e30
        else:
            tx1 = (min_x - origin.x) / d.x
            tx2 = (max_x - origin.x) / d.x
            tx_min = min(tx1, tx2)
            tx_max = max(tx1, tx2)

        if abs(d.y) < 1e-12:
            if origin.y < min_y or origin.y > max_y:
                return None
            ty_min, ty_max = -1e30, 1e30
        else:
            ty1 = (min_y - origin.y) / d.y
            ty2 = (max_y - origin.y) / d.y
            ty_min = min(ty1, ty2)
            ty_max = max(ty1, ty2)

        t_enter = max(tx_min, ty_min)
        t_exit = min(tx_max, ty_max)
        if t_enter > t_exit or t_exit < 0:
            return None
        t = t_enter if t_enter >= 0 else t_exit
        if t > max_dist:
            return None
        px = origin.x + d.x * t
        py = origin.y + d.y * t
        # Compute normal from which face was hit
        eps = 1e-4
        if abs(px - min_x) < eps:
            normal = Vector2(-1, 0)
        elif abs(px - max_x) < eps:
            normal = Vector2(1, 0)
        elif abs(py - min_y) < eps:
            normal = Vector2(0, -1)
        else:
            normal = Vector2(0, 1)
        return {"point": Vector2(px, py), "normal": normal, "distance": t}

    def _ray_polygon(self, origin: Vector2, d: Vector2, max_dist: float,
                     points: list[Vector2]):
        if len(points) < 3:
            return None
        best_t = float("inf")
        best_normal = None
        n = len(points)
        for i in range(n):
            a = points[i]
            b = points[(i + 1) % n]
            ex = b.x - a.x
            ey = b.y - a.y
            denom = d.x * ey - d.y * ex
            if abs(denom) < 1e-12:
                continue
            ox = a.x - origin.x
            oy = a.y - origin.y
            t = (ox * ey - oy * ex) / denom
            u = (ox * d.y - oy * d.x) / denom
            if t >= 0 and t <= max_dist and 0 <= u <= 1 and t < best_t:
                best_t = t
                # Edge normal (outward)
                nm = math.sqrt(ey * ey + ex * ex)
                if nm > 1e-12:
                    best_normal = Vector2(-ey / nm, ex / nm)
                else:
                    best_normal = Vector2(0, 0)
                # Ensure normal faces the ray origin
                if best_normal.x * d.x + best_normal.y * d.y > 0:
                    best_normal = Vector2(-best_normal.x, -best_normal.y)
        if best_normal is None:
            return None
        px = origin.x + d.x * best_t
        py = origin.y + d.y * best_t
        return {"point": Vector2(px, py), "normal": best_normal, "distance": best_t}

    def _dot(self, a: Vector2, b: Vector2):
        return (a.x * b.x) + (a.y * b.y)

    def _cross_2d(self, a: Vector2, b: Vector2):
        return (a.x * b.y) - (a.y * b.x)

    def _inverse_mass(self, rigidbody: Rigidbody2D | None, is_dynamic: bool):
        if not rigidbody or not is_dynamic:
            return 0.0
        if rigidbody.mass <= 0.0:
            return 0.0
        return 1.0 / rigidbody.mass
