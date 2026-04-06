from __future__ import annotations
from core.ecs import System, Entity
from core.components.animator import AnimatorComponent
from core.components.sprite_renderer import SpriteRenderer


class AnimationSystem(System):
    required_components = (AnimatorComponent,)

    def update(self, dt: float, entities: list[Entity]):
        if self.world:
            target_entities = self.world.get_entities_with(AnimatorComponent)
        else:
            target_entities = entities
        for entity in target_entities:
            animator = entity.get_component(AnimatorComponent)
            sprite = entity.get_component(SpriteRenderer)
            if not animator or not sprite:
                continue
            animator.reload_controller_if_changed()

            if animator.controller and not animator.current_state:
                default_state = animator.controller.get_default_state()
                if default_state:
                    animator.play(default_state, restart=True)

            if animator.controller and animator.current_state:
                valid_triggers = {
                    transition.trigger
                    for transition in animator.controller.transitions
                    if transition.from_node == animator.current_state and transition.trigger
                }
                animator.keep_only_triggers(valid_triggers)
                for transition in animator.controller.transitions:
                    if transition.from_node != animator.current_state:
                        continue
                    if transition.trigger and animator.consume_trigger(transition.trigger):
                        animator.play(transition.to_node, restart=True)
                        break

            if not animator.is_playing or animator.is_paused:
                frame = animator.get_current_frame()
                if frame:
                    sprite.image = frame
                    sprite._local_width = frame.get_width()
                    sprite._local_height = frame.get_height()
                continue

            if not animator.current_clip:
                continue

            frames = animator.current_clip.frames
            if not frames:
                continue

            fps = max(0.001, float(animator.current_clip.fps) * float(animator.speed))
            frame_duration = 1.0 / fps

            animator._frame_timer += dt
            reached_end_non_loop = False
            while animator._frame_timer >= frame_duration:
                animator._frame_timer -= frame_duration
                animator.current_frame_index += 1

                if animator.current_frame_index >= len(frames):
                    if animator.current_clip.loop:
                        animator.current_frame_index = 0
                    else:
                        animator.current_frame_index = len(frames) - 1
                        reached_end_non_loop = True
                        break

            if reached_end_non_loop:
                transitioned = False
                if animator.controller and animator.current_state:
                    for transition in animator.controller.transitions:
                        if transition.from_node == animator.current_state and transition.on_finish:
                            animator.play(transition.to_node, restart=True)
                            transitioned = True
                            break
                if not transitioned:
                    animator.is_playing = False

            frame = animator.get_current_frame()
            if not frame:
                continue
            sprite.image = frame
            sprite._local_width = frame.get_width()
            sprite._local_height = frame.get_height()
