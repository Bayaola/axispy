Advanced Input Tutorial
=======================

This page dives into AxisPy's input systems beyond basics: rebindable actions, merged axes, gamepad APIs, mouse coordinate mapping, multitouch, and gestures. It uses the actual `Input` and `InputMap` APIs called each frame by the runtime player.

.. contents:: On this page
   :local:
   :depth: 2

Overview
--------

- :class:`~core.input.Input` — low-level keyboard, mouse, gamepad, touch and gesture access.
- :class:`~core.input_map.InputMap` — high-level, rebindable actions with per-frame edge detection.

The runtime `RuntimePlayer` calls ``Input.update()`` and ``InputMap.update()`` once per frame. If embedding AxisPy differently, call both in your main loop before querying input.

Editor workflow (no code)
-------------------------

- **Configure Input Actions (Project Settings)**
  - Project → Project Settings → Input Actions tab.
  - Click "Add Action" to create a named action (e.g., "jump", "fire", "move_left").
  - Select the action row → click "Add Key" to bind keys (e.g., Space, Arrow keys, gamepad buttons by name).
  - The table shows Action Name and bound Keys. These are saved in ``project.config`` and auto-loaded by ``InputMap`` at runtime.

- **Using InputMap in scripts (Script Editor)**
  - The Input Actions you define in Project Settings map to ``InputMap.register()`` calls internally.
  - In the Script Editor, use ``InputMap.is_pressed("action_name")``, ``is_just_pressed()``, or ``is_just_released()`` to respond to your configured actions.
  - No need to hardcode keycodes in scripts—reference the action names you defined.

- **Testing input in the editor**
  - Enter Play Mode; Input and InputMap update automatically per frame.
  - Use ``self.logger.info()`` to verify actions trigger in the Console dock.
  - Gamepad input works when a controller is connected; check ``Input.get_joystick_count()`` to confirm detection.

Rebindable Actions with InputMap
--------------------------------

Map semantic actions ("jump", "fire") to one or more keys. Query held/edge states per frame.

.. code-block:: python

   import pygame
   from core.input_map import InputMap

   class ActionSetup:
       def on_start(self):
           # One-time bindings (could also load from config)
           InputMap.register("jump", [pygame.K_SPACE, pygame.K_w])
           InputMap.register("dash", [pygame.K_LSHIFT])

       def on_update(self, dt: float):
           if InputMap.is_just_pressed("jump"):
               self.logger.info("Jump!")
           if InputMap.is_pressed("dash"):
               self.logger.debug("Dashing...")
           if InputMap.is_just_released("dash"):
               self.logger.debug("Dash released")

Load from config at startup:

.. code-block:: python

   # Example config dict (e.g. from project file)
   cfg = {"input_actions": {"jump": [32, 119], "fire": [102]}}  # 32=SPACE, 119='w', 102='f'
   InputMap.load_from_config(cfg)

Merged Axes (Keyboard + Gamepad)
--------------------------------

Use :meth:`~core.input.Input.get_axis` to read continuous axes that merge keyboard and the first gamepad's left stick.

- ``Input.get_axis("Horizontal")`` → -1..1 (left=-1, right=+1; or left-stick X)
- ``Input.get_axis("Vertical")`` → -1..1 (up=+1, down=-1; merges W/S, arrow keys, and left-stick Y inverted so up is +)

.. code-block:: python

   from core.input import Input

   class AnalogMove:
       SPEED = 240
       def on_update(self, dt: float):
           from core.components import Transform
           t = self.entity.get_component(Transform)
           if not t:
               return
           t.x += Input.get_axis("Horizontal") * self.SPEED * dt
           t.y -= Input.get_axis("Vertical") * self.SPEED * dt

Gamepad API
-----------

Use the direct gamepad helpers for buttons, axes, and D-pad (hat). Deadzone can be tuned globally.

.. code-block:: python

   import pygame
   from core.input import Input

   class GamepadExample:
       def on_start(self):
           # Optional: tweak deadzone used by get_joy_axis()
           Input.set_joystick_deadzone(0.20)

       def on_update(self, dt: float):
           # Detect connected pads and names
           count = Input.get_joystick_count()
           if count > 0:
               jid = Input.get_joystick_ids()[0]
               name = Input.get_joystick_name(jid)
               self.logger.info("Pad", id=jid, name=name)

           # Buttons: held / edge detection
           if Input.get_joy_button(Input.JOY_A):
               self.logger.debug("A held")
           if Input.get_joy_button_down(Input.JOY_START):
               self.logger.info("Start pressed")
           if Input.get_joy_button_up(Input.JOY_B):
               self.logger.info("B released")

           # Sticks and triggers (normalized with deadzone)
           lx = Input.get_joy_axis(Input.JOY_LEFT_X)
           ly = Input.get_joy_axis(Input.JOY_LEFT_Y)  # Note: up is negative here
           # D-pad (hat) returns a tuple (-1..1, -1..1)
           hx, hy = Input.get_joy_hat()

Mouse Coordinates and Mapping
-----------------------------

- ``Input.get_mouse_position()`` returns raw window coordinates from the OS.
- ``Input.get_game_mouse_position()`` returns coordinates mapped to the engine's design/render surface.

The runtime sets a window→render mapper every frame, so use ``get_game_mouse_position`` for gameplay/UI picking.

.. code-block:: python

   from core.input import Input

   class MousePick:
       def on_update(self, dt: float):
           wx, wy = Input.get_mouse_position()
           gx, gy = Input.get_game_mouse_position()
           self.logger.debug("mouse", window=(wx, wy), game=(gx, gy))

If you run AxisPy in a custom loop, you can provide your own mapper:

.. code-block:: python

   from core.input import Input

   def my_mapper(window_x, window_y):
       # Convert to your game-space (return None to indicate out of bounds)
       return (window_x * 0.5, window_y * 0.5)

   Input.set_mouse_mapper(my_mapper)

Multitouch and Gestures
-----------------------

Read current touches and frame-specific changes, or use the high-level gesture recognizer.

.. code-block:: python

   from core.input import Input

   class TouchAndGestures:
       def on_update(self, dt: float):
           # Touch points
           touches = Input.get_touches()
           for fid, tp in touches.items():
               self.logger.debug("touch", id=fid, pos=(tp.x, tp.y), pressure=tp.pressure)

           for tp in Input.get_touches_started():
               self.logger.info("touch start", id=tp.finger_id)
           for tp in Input.get_touches_moved():
               self.logger.debug("touch move", id=tp.finger_id)
           for tp in Input.get_touches_ended():
               self.logger.info("touch end", id=tp.finger_id)

           # Gestures (recognized this frame)
           g = Input.get_gesture()
           if g.tap:
               self.logger.info("tap")
           if g.double_tap:
               self.logger.info("double_tap")
           if g.long_press:
               self.logger.info("long_press")
           if g.swipe:
               self.logger.info("swipe", dir=g.swipe_direction, vel=g.swipe_velocity)
           if g.pinch:
               self.logger.info("pinch", scale=g.pinch_scale, center=g.pinch_center)
           if g.rotate:
               self.logger.info("rotate", angle=g.rotate_angle, center=g.rotate_center)

Raw Pygame Events (Advanced)
----------------------------

For uncommon cases, you can read raw SDL/pygame events captured this frame.

.. code-block:: python

   import pygame
   from core.input import Input

   class RawEvents:
       def on_update(self, dt: float):
           for event in Input.get_events():
               if event.type == pygame.MOUSEWHEEL:
                   self.logger.info("wheel", x=event.x, y=event.y)

Testing with a Provider Stub
----------------------------

Inject a provider to override input for tests or headless runs. Any methods you implement will override `Input` behavior; others fall back to defaults.

.. code-block:: python

   class TestProvider:
       def __init__(self):
           self._pressed = set()
       def get_key(self, key_code):
           import pygame
           return key_code in self._pressed
       def update(self):
           self._pressed.add(32)  # pretend SPACE is held

   from core.input import Input
   Input.set_provider(TestProvider())
   # ... run a few frames ...
   Input.clear_provider()

Script Editor snippets you may need
-----------------------------------

- **Quick WASD + Space movement**

.. code-block:: python

   import pygame
   from core.input import Input
   from core.components import Transform

   class WASDMove:
       SPEED = 300
       def on_update(self, dt: float):
           t = self.entity.get_component(Transform)
           if not t:
               return
           dx = (Input.get_key(pygame.K_d) - Input.get_key(pygame.K_a))
           dy = (Input.get_key(pygame.K_s) - Input.get_key(pygame.K_w))
           t.x += dx * self.SPEED * dt
           t.y += dy * self.SPEED * dt

- **Mouse click to spawn**

.. code-block:: python

   import pygame
   from core.input import Input
   from core.components import Transform

   class ClickSpawner:
       def on_update(self, dt: float):
           if Input.get_mouse_button_down(pygame.BUTTON_LEFT):
               mx, my = Input.get_game_mouse_position()
               bullet = self.spawn_prefab("prefabs/bullet.json", x=mx, y=my)
               self.logger.info("spawned", at=(mx, my))

- **Toggle pause with a key**

.. code-block:: python

   import pygame
   from core.input_map import InputMap

   class PauseToggle:
       def on_start(self):
           InputMap.register("pause", [pygame.K_ESCAPE, pygame.K_p])
           self._paused = False

       def on_update(self, dt: float):
           if InputMap.is_just_pressed("pause"):
               self._paused = not self._paused
               self.logger.info("paused" if self._paused else "resumed")
