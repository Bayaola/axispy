Scripting Tutorial
==================

This tutorial walks through writing Python scripts in AxisPy — from attaching a script to an entity up to advanced patterns like coroutines, tweens and events.

.. contents:: On this page
   :local:
   :depth: 2

Overview
--------

Scripts in AxisPy are plain Python classes attached to an entity via a :class:`~core.components.script.ScriptComponent`.  The engine automatically injects useful attributes and helper methods into every script instance so you rarely need to import anything beyond what you actively use.

**Automatically injected attributes**

- ``self.entity`` — the :class:`~core.ecs.Entity` this script is attached to.
- ``self.logger`` — a :class:`~core.logger` instance named ``script.<ClassName>``.

**Automatically injected helper methods** (forwarded from :class:`~core.components.script.ScriptComponent`)

- Navigation: ``find``, ``get_children``
- Lifecycle: ``destroy``, ``hide``, ``show``, ``process_physics``, ``change_scene``
- Groups: ``call_group``
- Prefabs: ``instantiate_prefab`` / ``spawn_prefab``
- Coroutines: ``start_coroutine``, ``stop_coroutines``
- Tweens: ``tween``, ``cancel_tweens``
- Events: ``subscribe_to_event``, ``unsubscribe_from_event``, ``emit_global_event``, ``emit_local_event``, ``emit_global_event_immediate``, ``emit_local_event_immediate``

Editor workflow (no code)
-------------------------

- **Attach a script to an entity (Inspector)**
  - Select an entity in the Hierarchy.
  - Inspector → Add Component → Script Component.
  - In the Script section:
    - Click the pencil button to open the current script in the Scripts Editor.
    - Click the folder button → choose “Select Existing Script” to pick a ``.py`` file, or “Create New Script” to generate a template file under your project (the class name is auto‑filled).
    - The “Class Name” label reflects the top‑level class the engine will instantiate.

- **Open and edit scripts (Scripts Editor tab)**
  - Asset Manager: select a ``.py`` file → right‑click → “Edit Script”; or use the Inspector’s pencil button.
  - Save in the Scripts Editor; the runtime hot‑reloads your script automatically.
  - Shortcuts: Ctrl+F/H (find/replace), Ctrl+G (go to line), Ctrl+/ (toggle comment), Ctrl+D (duplicate line).
  - The editor provides autocompletion for common engine APIs (``Input``, components, and injected ``self.*`` helpers).

- **See logs while iterating**
  - Use ``self.logger.info/debug/warning/error`` in your script.
  - View output in the Console dock.

Your First Script
-----------------

Create a file, e.g. ``my_scripts/hello.py``, and define a class:

.. code-block:: python

   class Hello:
       def on_start(self):
           self.logger.info("Hello from", entity=self.entity.name)

       def on_update(self, dt: float):
           pass

Then attach it to an entity in the editor by setting the ``ScriptComponent``'s *Script Path* to ``my_scripts/hello.py`` and *Class Name* to ``Hello``.

Lifecycle Methods
-----------------

The :class:`~core.systems.script_system.ScriptSystem` calls the following methods when they exist on the class.

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Method
     - When it is called
   * - ``on_start(self)``
     - Once, the first frame the script is active.
   * - ``on_update(self, dt)``
     - Every frame.  ``dt`` is the elapsed time in seconds since the last frame.
   * - ``on_enable(self)``
     - Called when the entity becomes visible (via ``show()``).
   * - ``on_disable(self)``
     - Called when the entity is hidden (via ``hide()``).

Reading Input
-------------

Import :class:`~core.input.Input` to poll keyboard and mouse state, or :class:`~core.input_map.InputMap` for named rebindable actions.

.. code-block:: python

   import pygame
   from core.input import Input

   class PlayerController:
       SPEED = 200  # pixels per second

       def on_update(self, dt: float):
           from core.components import Transform
           transform = self.entity.get_component(Transform)
           if transform is None:
               return

           if Input.get_key(pygame.K_RIGHT):
               transform.x += self.SPEED * dt
           if Input.get_key(pygame.K_LEFT):
               transform.x -= self.SPEED * dt
           if Input.get_key(pygame.K_UP):
               transform.y -= self.SPEED * dt
           if Input.get_key(pygame.K_DOWN):
               transform.y += self.SPEED * dt

.. note::

   ``Input.get_key(keycode)`` returns ``True`` every frame the key is held.
   For named actions (rebindable), prefer :class:`~core.input_map.InputMap`.

For named actions, use :class:`~core.input_map.InputMap`:

.. code-block:: python

   import pygame
   from core.input_map import InputMap

   InputMap.register("jump", [pygame.K_SPACE])

   class Jumper:
       def on_update(self, dt: float):
           if InputMap.is_just_pressed("jump"):
               pass  # single-frame trigger
           if InputMap.is_pressed("jump"):
               pass  # held every frame
           if InputMap.is_just_released("jump"):
               pass  # release detection

For analogue movement (keyboard + joystick merged), use ``Input.get_axis``:

.. code-block:: python

   import pygame
   from core.input import Input

   class Mover:
       SPEED = 200

       def on_update(self, dt: float):
           from core.components import Transform
           transform = self.entity.get_component(Transform)
           if transform:
               transform.x += Input.get_axis("Horizontal") * self.SPEED * dt
               transform.y -= Input.get_axis("Vertical") * self.SPEED * dt

Working with the Transform
--------------------------

Retrieve a component with :meth:`~core.ecs.Entity.get_component`:

.. code-block:: python

   from core.components import Transform

   class Spinner:
       ROTATION_SPEED = 90  # degrees per second

       def on_update(self, dt: float):
           transform = self.entity.get_component(Transform)
           if transform:
               transform.rotation += self.ROTATION_SPEED * dt

:class:`~core.components.transform.Transform` exposes ``x``, ``y``, ``rotation``, ``scale_x``, ``scale_y`` as read/write properties.
It also provides convenience methods ``translate``, ``rotate``, and ``scale``.

Finding Other Entities
----------------------

Use ``self.find(name)`` to look up another entity in the same world by name:

.. code-block:: python

   class CameraFollow:
       def on_update(self, dt: float):
           player = self.find("Player")
           if player is None:
               return
           from core.components import Transform
           player_t = player.get_component(Transform)
           my_t = self.entity.get_component(Transform)
           if player_t and my_t:
               my_t.x = player_t.x
               my_t.y = player_t.y

Scene Management
----------------

Call ``self.change_scene(scene_name)`` to queue a scene transition at the end of the current frame:

.. code-block:: python

   import pygame
   from core.input import Input

   class MainMenu:
       def on_update(self, dt: float):
           if Input.get_key(pygame.K_SPACE):
               self.change_scene("game_scene")

Coroutines
----------

Coroutines let you write time-based logic as a generator function.
Yield :class:`~core.coroutine_manager.Wait` to pause for a number of seconds or :class:`~core.coroutine_manager.WaitFrames` to pause for a number of frames.

.. code-block:: python

   from core.coroutine_manager import Wait, WaitFrames

   class Blinker:
       def on_start(self):
           self.start_coroutine(self._blink())

       def _blink(self):
           while True:
               self.hide()
               yield Wait(0.3)
               self.show()
               yield Wait(0.3)

Cancel all running coroutines on this script with ``self.stop_coroutines()``.

Tweens
------

Tweens smoothly interpolate a numeric property over time.

.. code-block:: python

   from core.tween import ease_out_quad

   class SlideIn:
       def on_start(self):
           self.tween(
               self.entity,
               "transform.x",
               target=400.0,
               start=0.0,
               duration=1.0,
               easing=ease_out_quad,
           )

Cancel tweens with ``self.cancel_tweens()`` or ``self.cancel_tweens(entity)`` to target a specific entity.

Events
------

The event system allows decoupled communication between scripts.

**Subscribing to an event**

.. code-block:: python

   class ScoreDisplay:
       def on_start(self):
           self.subscribe_to_event("score_changed", self._on_score_changed)

       def _on_score_changed(self, new_score: int):
           self.logger.info("Score updated", score=new_score)

**Emitting an event**

.. code-block:: python

   class ScoreManager:
       _score = 0

       def add_points(self, points: int):
           self._score += points
           self.emit_global_event("score_changed", self._score)

- ``emit_global_event`` / ``emit_local_event`` — queued, dispatched next frame.
- ``emit_global_event_immediate`` / ``emit_local_event_immediate`` — dispatched synchronously (zero-latency).

Group Calls
-----------

``call_group`` broadcasts a method call to every entity that belongs to a named group and has a script with that method:

.. code-block:: python

   import pygame
   from core.input import Input

   class GameManager:
       def on_update(self, dt: float):
           if Input.get_key(pygame.K_p):
               self.call_group("enemies", "pause")

Entities are added to a group with :meth:`~core.ecs.Entity.add_group`:

.. code-block:: python

   self.entity.add_group("enemies")

Spawning Prefabs
----------------

``instantiate_prefab`` (alias: ``spawn_prefab``) loads a saved entity from a ``.json`` prefab file and adds it to the world:

.. code-block:: python

   from core.components import Transform

   class Spawner:
       def on_start(self):
           t = self.entity.get_component(Transform)
           bullet = self.spawn_prefab(
               "prefabs/bullet.json",
               x=t.x if t else 0.0,
               y=t.y if t else 0.0,
           )

The path is resolved relative to the script file, ``AXISPY_PROJECT_PATH``, or the current working directory (whichever exists first).

Logging
-------

The injected ``self.logger`` is a structured logger.  Pass extra context as keyword arguments:

.. code-block:: python

   self.logger.debug("Entity moved", x=transform.x, y=transform.y)
   self.logger.info("Scene loaded")
   self.logger.warning("Missing component", component="Rigidbody")
   self.logger.error("Critical failure", reason=str(e))

Hot Reloading
-------------

The :class:`~core.systems.script_system.ScriptSystem` monitors each script file's modification time.
Saving the file while the game is running in the editor automatically reloads the script and calls ``on_start`` again on the next frame — no restart required.
