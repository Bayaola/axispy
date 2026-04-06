from core.ecs import System, Entity


class EventDispatchSystem(System):
    required_components = ()

    def update(self, dt: float, entities: list[Entity]):
        if not self.world:
            return
        self.world.events.dispatch_pending()
        for entity in entities:
            events = getattr(entity, "_events", None)
            if events is not None:
                events.dispatch_pending()
