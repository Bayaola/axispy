Animation Tutorial
==================

This tutorial shows how to author clips and controllers in the AxisPy editor UI, attach them to an entity, and drive animations from scripts using triggers and state changes.

.. contents:: On this page
   :local:
   :depth: 2

What you will build
-------------------

- A looping Idle and Run clip from a spritesheet.
- A controller with states and transitions.
- An entity that plays Idle on start and switches to Run while a key is held.

Requirements
------------

- :class:`~core.components.sprite_renderer.SpriteRenderer` to draw frames.
- :class:`~core.components.animator.AnimatorComponent` to manage state/frames.
- Runtime already includes :class:`~core.systems.animation_system.AnimationSystem`.

Create clips in the Editor (Clip Editor)
----------------------------------------

1) Open the Animation Editor tab

- Main Window → “Animation Editor” tab (or Asset Manager → right‑click a clip → Open Animation Clip).

2) Create a new clip file (.anim)

- Asset Manager → right‑click a folder → “New Animation Clip”.
- Name it e.g. ``idle.anim`` or ``run.anim``.

3) Configure the clip

- In the Clip Editor:

  - Set ``FPS`` and ``Loop``.
  - Choose ``Type``:
    - Spritesheet: set ``sheet_path``, ``frame_width/height``, ``margin`` and ``spacing``.
    - Image Sequence: add ``image_paths`` (one per frame).
  - Preview updates live; click “Save” to write the .anim via the editor.

Create a controller (.actrl) and add states/transitions
-------------------------------------------------------

1) Create controller

- Asset Manager → right‑click a folder → “New Animation Controller”. Name it e.g. ``player.actrl``.
- Double‑click to open it in the Controller view.

2) Add states (nodes) and assign clips

- Click “Add Node”. Select the node to edit its properties.
- Click the “...” next to “Clip (.anim)” and choose your clip (e.g. ``idle.anim``).
- The node’s preview plays in the right panel.
- Repeat for ``run.anim``.

3) Set default state

- Draw a transition from ``Root`` to your default node (double‑click a node, then click the target node). The editor stores a single Root→Default edge.

4) Add transitions between states

- Double‑click a node, then click another to connect.
- Select the arrow (edge) to edit properties:
  - ``Trigger``: a string (e.g. ``start_run``) you’ll fire from scripts.
  - ``On Finish``: when checked, transition fires after the source clip reaches its last frame (non‑looping).
- Save the controller (toolbar “Save”).

Attach to an entity (Inspector)
-------------------------------

- Ensure the entity has a :class:`~core.components.transform.Transform` and a :class:`~core.components.sprite_renderer.SpriteRenderer`.
- Add :class:`~core.components.animator.AnimatorComponent`.
  - Set ``controller_path`` to your ``.actrl`` (relative to the project folder works; the engine also resolves by controller/clip folder and ``AXISPY_PROJECT_PATH``).
  - Optional: set ``play_on_start`` and ``speed``.

Drive animation from a script (Script Editor)
---------------------------------------------

Use the script editor tab to add logic. The :class:`~core.systems.animation_system.AnimationSystem` will hot‑reload controller/clip files while the game runs.

.. code-block:: python

   from core.components import AnimatorComponent
   import pygame
   from core.input import Input

   class PlayerAnim:
       def on_start(self):
           self.anim = self.entity.get_component(AnimatorComponent)
           # Optionally force a state at startup
           if self.anim and self.anim.controller:
               default = self.anim.controller.get_default_state()
               if default:
                   self.anim.play(default, restart=True)

       def on_update(self, dt: float):
           if not self.anim:
               return
           # Fire a trigger defined on a transition from the current state
           if Input.get_key(pygame.K_LSHIFT):
               self.anim.set_trigger("start_run")
           else:
               self.anim.set_trigger("stop_run")

Control API quick reference
---------------------------

- ``anim.play(state_name, restart=False)`` — jump to a node by name.
- ``anim.set_trigger(name)`` — enqueue a trigger; consumed by the system if a matching transition exists.
- ``anim.pause()`` / ``anim.resume()`` / ``anim.stop(reset=False)`` — playback control.
- ``anim.speed`` — global speed multiplier (affects FPS).
- ``anim.current_state`` / ``anim.is_playing`` / ``anim.is_paused`` — status.

How transitions resolve (runtime)
---------------------------------

- On each frame, the system:
  - Reloads controller if the file changed (hot reload).
  - If no current state, uses the controller’s Root→Default.
  - Checks transitions out of the current state. If a transition has ``trigger`` and that trigger was set (and not yet consumed), it switches immediately.
  - When a non‑looping clip reaches its last frame, any transition from the current state with ``on_finish`` is taken.
  - The current frame is assigned to the entity’s :class:`~core.components.sprite_renderer.SpriteRenderer`.

Tips and troubleshooting
------------------------

- If you don’t see frames: ensure the entity has a SpriteRenderer, and your .anim clip resolves its images/spritesheet correctly (paths are project‑relative in the editor; engine resolves via controller/clip folder, project root, or CWD).
- To flip sprites, use negative :class:`~core.components.transform.Transform` scale values.
- To keep multiple triggers around, call ``set_trigger`` each frame you need them. Triggers are “consumed” the next time the system sees a matching transition.
- Editor previews do not require the game to be running; runtime playback will match FPS/loop/segment settings.
