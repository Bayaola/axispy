Physics & Colliders Tutorial
============================

This tutorial covers 2D physics in AxisPy: rigidbodies, colliders, collision handling, and physics queries (raycasts/overlaps). It is based on the actual engine components and the `PhysicsSystem` that the runtime attaches to every scene.

.. contents:: On this page
   :local:
   :depth: 2

Overview
--------

- :class:`~core.components.rigidbody.Rigidbody2D` — motion, gravity, forces, damping.
- :class:`~core.components.colliders.BoxCollider2D`, :class:`~core.components.colliders.CircleCollider2D`, :class:`~core.components.colliders.PolygonCollider2D` — shapes for collision.
- :class:`~core.systems.physics_system.PhysicsSystem` — simulation, collision detection/response, queries.

The runtime adds a single `PhysicsSystem` per world. Default gravity is `(0, 980)` in pixels/s².

Editor workflow (no code)
-------------------------

- **Add physics components (Inspector)**
  - Select an entity → Add Component → Physics → ``Rigidbody 2D``.
  - Add a collider: ``Box Collider 2D``, ``Circle Collider 2D``, or ``Polygon Collider 2D``.
  - Box/Circle sizes can be inferred from ``SpriteRenderer``. Adjust Width/Height/Radius, ``Offset X/Y``, ``Rotation``, and toggle ``Is Trigger``.
  - For Polygon, click "Start Adding New Point" in the Inspector to place points in the Scene viewport; per‑point X/Y editing and delete are available (3+ points required).

- **Configure Rigidbody in Inspector**
  - ``Body Type``: Dynamic / Kinematic / Static.
  - ``Use Gravity``, ``Gravity Scale``, ``Mass``, ``Friction``, ``Elasticity``, ``Linear/Angular Damping``, ``Freeze Rotation``.
  - Optional initial ``Velocity X/Y`` and ``Angular Velocity``.

- **Groups and Collision Matrix**
  - Project → Project Settings → Layers/Groups.
  - Define logical groups (e.g., Player, Enemy, Environment).
  - In "Physics Collision Matrix", tick which groups collide. The runtime loads this into ``world.physics_group_order`` and ``world.physics_collision_matrix`` when the project opens.
  - Assign entities to groups via the Inspector (Groups) or the Groups dock.

- **Visualize and edit colliders**
  - In the Scene viewport toolbar, enable "Physics Debug Mode" (bug icon) to show collider outlines and handles. Drag handles to resize; polygon point add/remove integrates with this mode.

Getting Started: Rigidbody + Collider
-------------------------------------

.. code-block:: python

   from core.components import Transform, Rigidbody2D, BoxCollider2D

   class PlayerSetup:
       def on_start(self):
           # Ensure a Transform exists
           if not self.entity.get_component(Transform):
               self.entity.add_component(Transform())

           # Add a dynamic rigidbody
           rb = self.entity.get_component(Rigidbody2D)
           if not rb:
               rb = Rigidbody2D(mass=1.0, use_gravity=True, linear_damping=0.05)
               self.entity.add_component(rb)

           # Add a box collider (auto-sizes from sprite if width/height=None)
           col = self.entity.get_component(BoxCollider2D)
           if not col:
               col = BoxCollider2D(width=None, height=None, is_trigger=False)
               self.entity.add_component(col)

Rigidbody2D Body Types
----------------------

`Rigidbody2D` supports three body types via `body_type`:

- ``"dynamic"`` — affected by forces and gravity (default).
- ``"kinematic"`` — moved by setting velocity directly; not affected by forces.
- ``"static"`` — immovable; used for the environment.

.. code-block:: python

   rb = self.entity.get_component(Rigidbody2D)
   rb.body_type = Rigidbody2D.BODY_TYPE_STATIC
   # or kinematic
   rb.body_type = Rigidbody2D.BODY_TYPE_KINEMATIC

Forces, Impulses, and Rotation
------------------------------

.. code-block:: python

   from core.components import Rigidbody2D

   class Thrust:
       def on_update(self, dt: float):
           rb = self.entity.get_component(Rigidbody2D)
           if not rb or not rb.is_dynamic:
               return
           # Continuous force (applied this frame only)
           rb.apply_force(500.0, 0.0)
           # One-shot velocity change
           # rb.apply_impulse(50.0, 0.0)
           # Spin
           # rb.apply_torque(10.0)
           # rb.apply_angular_impulse(1.0)

   # Damping and friction
   # rb.linear_damping = 0.05
   # rb.angular_damping = 0.1
   # rb.friction = 0.5
   # Elasticity (alias: rb.elasticity)
   # rb.restitution = 0.2

Colliders: Shapes, Offsets, Triggers, Masks
-------------------------------------------

- Box: `BoxCollider2D(width=None, height=None, offset_x=0, offset_y=0, rotation=0)`
- Circle: `CircleCollider2D(radius=None, offset_x=0, offset_y=0)`
- Polygon: `PolygonCollider2D(points=[(x,y),...], offset_x=0, offset_y=0, rotation=0)`

Notes:

- If width/height (box) or radius (circle) is ``None``, sizes are inferred from a `SpriteRenderer` if present, else reasonable defaults are used.
- Set ``is_trigger=True`` for overlap-only detection (no physical resolution).
- Use bitmasks to filter collisions per body: ``category_mask`` (what I am) and ``collision_mask`` (what I collide with).

Example:

.. code-block:: python

   from core.components import BoxCollider2D

   # Player belongs to category bit 1, collides with bits 1 and 2
   player_col = BoxCollider2D(
       category_mask=(1 << 0),
       collision_mask=(1 << 0) | (1 << 1)
   )
   self.entity.add_component(player_col)

Layered Filtering via World Groups
----------------------------------

Instead of hardcoding bitmasks, you can derive effective masks from entity groups using world-level settings (read by the `PhysicsSystem`).

.. code-block:: python

   from core.systems.physics_system import PhysicsSystem

   class GameManager:
       def on_start(self):
           # Define physics groups (order = bit position)
           self.entity.world.physics_group_order = ["Player", "Enemy", "Environment"]

           # Define which groups collide with which
           self.entity.world.physics_collision_matrix = {
               "Player": ["Environment", "Enemy"],
               "Enemy": ["Environment", "Player"],
               "Environment": ["Player", "Enemy"],
           }

   # Mark entities with groups; `PhysicsSystem` converts groups to masks
   self.entity.add_group("Player")

Collision Handling
------------------

You can handle collisions either via script callbacks on the attached script class or by subscribing to events.

- Script callbacks recognized by the engine:
  - ``on_collision_enter(other, info)``
  - ``on_collision_exit(other)``

``info`` is a lightweight object with ``normal`` (Vector2) and ``penetration`` (float).

.. code-block:: python

   class DamageOnHit:
       def on_collision_enter(self, other, info):
           self.logger.info("Hit", other=other.name, normal=(info.normal.x, info.normal.y))

   # Or via events (immediate dispatch within the same frame):
   class EventListener:
       def on_start(self):
           # Subscribe to this entity's local collision events
           self.subscribe_to_event("collision_enter", self._on_enter, target_entity=self.entity)
           self.subscribe_to_event("collision_exit", self._on_exit, target_entity=self.entity)

       def _on_enter(self, other, info):
           self.logger.debug("collision_enter", other=other.name)

       def _on_exit(self, other):
           self.logger.debug("collision_exit", other=other.name)

Physics Queries: Raycasts and Overlaps
--------------------------------------

Access the `PhysicsSystem` from the world and use queries for detection.

.. code-block:: python

   from core.vector import Vector2
   from core.components import Transform
   from core.systems.physics_system import PhysicsSystem

   class Sensor:
       def on_update(self, dt: float):
           phys = self.entity.world.get_system(PhysicsSystem)
           if not phys:
               return
           # Raycast forward 500 px from this entity's position
           t = self.entity.get_component(Transform)
           origin = t.position if t else Vector2(0, 0)
           hit = phys.raycast_first(origin, Vector2(1, 0), 500)
           if hit:
               self.logger.info("Ray hit", entity=hit["entity"].name, dist=hit["distance"]) 

           # Overlap box centered on entity (100x50 half extents)
           center = origin
           overlaps = phys.overlap_box(center, Vector2(100, 50))
           for e in overlaps:
               self.logger.debug("Overlap", entity=e.name)

Adjusting Gravity
-----------------

Change global gravity via the `PhysicsSystem`.

.. code-block:: python

   from core.systems.physics_system import PhysicsSystem
   from core.vector import Vector2

   class GravitySetup:
       def on_start(self):
           phys = self.entity.world.get_system(PhysicsSystem)
           if phys:
               phys.gravity = Vector2(0, 1200)  # stronger downward gravity

Disabling Physics Processing per Entity
---------------------------------------

Temporarily opt an entity out of physics (integration and collisions):

.. code-block:: python

   # Pause/resume physics on this entity and its children
   self.entity.process_physics(False)
   # ... later ...
   self.entity.process_physics(True)

Script Editor snippets you may need
-----------------------------------

- **Apply a force while a key is held**

.. code-block:: python

   import pygame
   from core.input import Input
   from core.components import Rigidbody2D

   class Thruster:
       def on_update(self, dt: float):
           rb = self.entity.get_component(Rigidbody2D)
           if rb and rb.is_dynamic and Input.get_key(pygame.K_RIGHT):
               rb.apply_force(800.0, 0.0)

- **Raycast from the mouse**

.. code-block:: python

   from core.input import Input
   from core.systems.render_system import RenderSystem
   from core.systems.physics_system import PhysicsSystem
   from core.vector import Vector2

   class MouseProbe:
       def on_update(self, dt: float):
           rs = self.entity.world.get_system(RenderSystem)
           phys = self.entity.world.get_system(PhysicsSystem)
           if not rs or not phys:
               return
           mx, my = Input.get_game_mouse_position()
           wx, wy = rs.screen_to_world(mx, my, entities=self.entity.world.entities)
           hit = phys.raycast_first(Vector2(wx, wy), Vector2(1, 0), 600)
           if hit:
               self.logger.info("hit", target=hit["entity"].name, dist=hit["distance"])

- **Toggle a collider's trigger flag at runtime**

.. code-block:: python

   from core.components import BoxCollider2D

   class Toggle:
       def on_update(self, dt: float):
           col = self.entity.get_component(BoxCollider2D)
           if col:
               col.is_trigger = not col.is_trigger
               self.logger.info("trigger", value=col.is_trigger)
