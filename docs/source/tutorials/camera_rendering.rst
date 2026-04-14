Camera & Rendering Tutorial
===========================

This tutorial explains cameras, world/screen conversion, layer ordering, design resolution and stretching, sprites and UI rendering, plus lights and shadows. It follows the actual `RenderSystem` and `CameraComponent` APIs.

.. contents:: On this page
   :local:
   :depth: 2

Overview
--------

- :class:`~core.components.camera.CameraComponent` — camera position/zoom/rotation, split viewports, follow, shake.
- :class:`~core.systems.render_system.RenderSystem` — draws sprites/tilemaps/UI, manages cameras, world↔screen helpers.
- :class:`~core.components.sprite_renderer.SpriteRenderer` — basic sprite/rect rendering with transform-driven scale/rotation.
- :class:`~core.systems.lighting_system.LightingSystem` with :class:`~core.components.light.PointLight2D`, :class:`~core.components.light.SpotLight2D`, :class:`~core.components.light.LightOccluder2D` — optional light/shadow overlay.

Editor workflow (no code)
-------------------------

- **Add a camera**
  - Select an entity in the Hierarchy (e.g., "Main Camera" or create a new one).
  - Inspector → Add Component → Camera Component.
  - Adjust ``Zoom``, ``Rotation``, and the ``Viewport X/Y/W/H`` for split‑screen.
  - To follow a target, use the "Camera Follow" list to pick an entity. Toggle ``Follow Rotation`` if desired.

- **Split‑screen**
  - Add a Camera Component to two different entities.
  - Set viewports, e.g., top: X=0, Y=0, W=1, H=0.5; bottom: X=0, Y=0.5, W=1, H=0.5.
  - Use ``Priority`` to control draw order when viewports overlap (lower draws first).

- **Add a sprite**
  - Select an entity, Inspector → Add Component → Sprite Renderer.
  - Click "Browse Image…" to pick a texture. Width/Height reflect Transform scale; negative scale flips.

- **Order with layers**
  - Select any entity with a Transform; use the "Layer" dropdown.
  - Click "Edit Layers" to add/reorder global ``world.layers`` used for render order (first entry draws behind).
  - You can also manage layers from Project Settings → Layers/Groups.

- **Design resolution & stretching** (Project Settings)
  - Project → Project Settings → Display tab.
  - Set Game Width/Height (virtual resolution) and Window Width/Height.
  - Choose Stretch Mode (fit/stretch/crop), Aspect (keep/ignore), and Scale (fractional/integer).
  - Save settings; the runtime applies them on launch.

- **Lights and shadows**
  - Select or create an entity, Inspector → Add Component → Lighting → Point Light 2D or Spot Light 2D.
  - Add occluders: Inspector → Add Component → Lighting → Light Occluder 2D. For box/circle, sizes can derive from SpriteRenderer.
  - Shadow range is configurable in Project Settings → Lighting → Shadow Extend.

Cameras: Single, Split-screen, Follow, Shake
--------------------------------------------

Create a camera by adding :class:`~core.components.camera.CameraComponent` to an entity that has a :class:`~core.components.transform.Transform`.

.. code-block:: python

   from core.components import Transform, CameraComponent

   class CameraSetup:
       def on_start(self):
           if not self.entity.get_component(Transform):
               self.entity.add_component(Transform(x=400, y=300))
           cam = self.entity.get_component(CameraComponent) or CameraComponent(zoom=1.0)
           if not self.entity.get_component(CameraComponent):
               self.entity.add_component(cam)

- Fields:
  - ``zoom`` (float ≥0.01)
  - ``rotation`` (deg)
  - ``viewport_x/y/width/height`` (0..1 fractions of the render surface) for split-screen.
  - ``priority`` (lower renders first behind higher-priority cameras).
  - ``follow_target_id`` (entity ID to follow), ``follow_rotation``.

Split-screen example (two cameras):

.. code-block:: python

   # Top camera (upper half)
   top = top_entity.add_component(CameraComponent(viewport_x=0, viewport_y=0, viewport_width=1, viewport_height=0.5))
   # Bottom camera (lower half)
   bot = bot_entity.add_component(CameraComponent(viewport_x=0, viewport_y=0.5, viewport_width=1, viewport_height=0.5))

Follow a target by ID:

.. code-block:: python

   # Find player and set follow_target_id
   player = self.find("Player")
   if player:
       cam = self.entity.get_component(CameraComponent)
       cam.follow_target_id = player.id
       cam.follow_rotation = True  # or False to keep camera's own rotation

Camera shake:

.. code-block:: python

   cam = self.entity.get_component(CameraComponent)
   cam.shake(intensity=6.0, duration=0.25, decay=CameraComponent.DECAY_EXPONENTIAL)

World ↔ Screen Conversion
-------------------------

Use :class:`~core.systems.render_system.RenderSystem` helpers to convert between world and screen coordinates for the current primary camera.

.. code-block:: python

   from core.systems.render_system import RenderSystem

   rs = self.entity.world.get_system(RenderSystem)
   # World to screen (pixels in the camera viewport)
   sx, sy = rs.world_to_screen( world_x, world_y, entities=self.entity.world.entities )
   # Screen (viewport pixels) to world
   wx, wy = rs.screen_to_world( screen_x, screen_y, entities=self.entity.world.entities )

Tip: To convert the game mouse to world, combine with ``Input.get_game_mouse_position()`` from the Advanced Input tutorial.

Layer Ordering
--------------

Render order follows ``world.layers`` (first name is drawn first, i.e., behind). Entities carry a string ``entity.layer``; use ``entity.set_layer(name)`` to set the entity and all its children.

.. code-block:: python

   # Configure once (e.g., in a manager script)
   self.entity.world.layers = ["Background", "Middleground", "Foreground", "UI"]

   # Place entities on layers
   self.entity.set_layer("Foreground")

Design Resolution, Stretching, and Present Smoothing
----------------------------------------------------

The runtime uses a virtual render surface (design resolution) and then presents it to the window according to stretch settings.

- Design size comes from the player's config; also set on ``RenderSystem.design_size``.
- Stretch options (from RuntimePlayer): ``stretch_mode`` (``"fit"`` | ``"stretch"`` | ``"crop"``), ``stretch_aspect`` (``"keep"`` | ``"ignore"``), ``stretch_scale`` (``"integer"`` | ``"fractional"``).
- Present smoothing (bilinear vs. nearest): ``RenderSystem.smooth_present`` controls scaling quality.

Toggle crisp pixel-art scaling at runtime:

.. code-block:: python

   from core.systems.render_system import RenderSystem
   rs = self.entity.world.get_system(RenderSystem)
   rs.smooth_present = False  # nearest-neighbor when the runtime scales the frame

Sprites and Animation
---------------------

:class:`~core.components.sprite_renderer.SpriteRenderer` draws either a loaded image or a colored rectangle. Width/height reflect the entity's scale (negative scale flips).

.. code-block:: python

   from core.components import Transform, SpriteRenderer

   class SpriteSetup:
       def on_start(self):
           if not self.entity.get_component(Transform):
               self.entity.add_component(Transform(x=200, y=200))
           spr = self.entity.get_component(SpriteRenderer)
           if not spr:
               spr = SpriteRenderer(image_path="assets/hero.png")  # or omit for a colored rect
               self.entity.add_component(spr)

UI Overlay
----------

UI components (``TextRenderer``, ``ButtonComponent``, etc.) are rendered in screen space after world cameras. Their :class:`~core.components.transform.Transform` coordinates are pixels in the design resolution. When a camera uses a sub-viewport, UI can also be drawn inside that viewport (editor workflows use this).

Lights and Shadows (Optional)
-----------------------------

The :class:`~core.systems.lighting_system.LightingSystem` composites an ambient + light overlay using multiply blending. RuntimePlayer already adds it after the :class:`~core.systems.render_system.RenderSystem`.

.. code-block:: python

   from core.components import Transform
   from core.components.light import PointLight2D, SpotLight2D, LightOccluder2D

   class LightsExample:
       def on_start(self):
           # Torch
           torch = self.find("Torch")
           if torch is None:
               torch = self.entity.world.create_entity("Torch")
               torch.add_component(Transform(x=300, y=200))
           torch.add_component(PointLight2D(color=(255, 200, 120), radius=300, intensity=1.0))

           # Spotlight
           spot = self.entity.world.create_entity("Spot")
           spot.add_component(Transform(x=500, y=300))
           spot.add_component(SpotLight2D(color=(200, 220, 255), radius=400, intensity=1.0, angle=0.0, cone_angle=40))

           # Wall occluder (casts shadows)
           wall = self.entity.world.create_entity("Wall")
           wall.add_component(Transform(x=400, y=280))
           wall.add_component(LightOccluder2D(shape="box", width=200, height=40))

- Ambient color and global enable are on the system: ``LightingSystem.ambient_color`` and ``LightingSystem.enabled``.
- Occluder flags per object: ``receive_light`` and ``receive_shadow``.

Script Editor snippets you may need
-----------------------------------

- **Toggle crisp scale filter at present time**

.. code-block:: python

   from core.systems.render_system import RenderSystem
   rs = self.entity.world.get_system(RenderSystem)
   if rs:
       rs.smooth_present = False  # nearest-neighbor scale on present

- **World ↔ screen mouse conversion**

.. code-block:: python

   from core.systems.render_system import RenderSystem
   from core.input import Input
   rs = self.entity.world.get_system(RenderSystem)
   if rs:
       gx, gy = Input.get_game_mouse_position()  # mapped to virtual surface
       wx, wy = rs.screen_to_world(gx, gy, entities=self.entity.world.entities)

- **Trigger a quick camera shake**

.. code-block:: python

   from core.components import CameraComponent
   cam = self.entity.get_component(CameraComponent)
   if cam:
       cam.shake(intensity=6.0, duration=0.25, decay=CameraComponent.DECAY_EXPONENTIAL)

Notes
-----

- If no active :class:`~core.components.camera.CameraComponent` exists, the renderer uses its internal camera fields (``camera_x/y/zoom/rotation``) to draw a single full-screen view.
- Render order is also affected by visibility (``entity.hide()`` / ``show()``) and negative transform scale flips.
