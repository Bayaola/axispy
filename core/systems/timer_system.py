from core.ecs import System, Entity
from core.components.timer import TimerComponent


class TimerSystem(System):
    """Ticks all TimerComponent instances each frame."""
    required_components = (TimerComponent,)

    def update(self, dt: float, entities: list[Entity]):
        if self.world:
            target_entities = self.world.get_entities_with(TimerComponent)
        else:
            target_entities = entities
        for entity in target_entities:
            timer = entity.get_component(TimerComponent)
            if timer:
                timer.tick(dt)
