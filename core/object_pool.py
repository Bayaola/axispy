"""Object pool for reusing deactivated entities instead of destroy/create churn."""
from __future__ import annotations
from typing import Dict, List, Callable, Optional
from core.ecs import Entity, World
from core.logger import get_logger

_pool_logger = get_logger("object_pool")


class ObjectPool:
    """A per-World pool that recycles entities by a string tag.

    Usage from scripts::

        pool = ObjectPool(world, prefill={"bullet": (create_bullet, 20)})
        bullet = pool.acquire("bullet")      # re-use or create
        pool.release("bullet", bullet)        # deactivate and return to pool

    Entities returned by ``acquire`` are shown (``entity.show()``) and have
    physics re-enabled.  Entities passed to ``release`` are hidden and have
    physics disabled so they cost almost nothing while pooled.
    """

    def __init__(self, world: World,
                 prefill: Dict[str, tuple[Callable[[], Entity], int]] | None = None):
        self.world = world
        self._pools: Dict[str, List[Entity]] = {}
        self._factories: Dict[str, Callable[[], Entity]] = {}

        if prefill:
            for tag, (factory, count) in prefill.items():
                self.register(tag, factory, count)

    def register(self, tag: str, factory: Callable[[], Entity], prefill_count: int = 0):
        """Register a factory for *tag* and optionally pre-create entities."""
        self._factories[tag] = factory
        if tag not in self._pools:
            self._pools[tag] = []
        for _ in range(prefill_count):
            entity = factory()
            self._deactivate(entity)
            self._pools[tag].append(entity)

    def acquire(self, tag: str) -> Optional[Entity]:
        """Get an entity from the pool, or create one via the registered factory."""
        pool = self._pools.get(tag)
        if pool:
            entity = pool.pop()
            self._activate(entity)
            return entity
        factory = self._factories.get(tag)
        if factory:
            entity = factory()
            self._activate(entity)
            return entity
        _pool_logger.warning("No factory registered for pool tag", tag=tag)
        return None

    def release(self, tag: str, entity: Entity):
        """Return an entity to the pool for later reuse."""
        if tag not in self._pools:
            self._pools[tag] = []
        self._deactivate(entity)
        self._pools[tag].append(entity)

    def pool_size(self, tag: str) -> int:
        """Number of currently pooled (inactive) entities for *tag*."""
        return len(self._pools.get(tag, []))

    def clear(self, tag: str | None = None):
        """Destroy all pooled entities.  If *tag* is None, clear every tag."""
        tags = [tag] if tag else list(self._pools.keys())
        for t in tags:
            pool = self._pools.pop(t, [])
            for entity in pool:
                if entity.world:
                    entity.destroy()

    # -- internal helpers --

    @staticmethod
    def _deactivate(entity: Entity):
        entity.hide()
        entity.process_physics(False)

    @staticmethod
    def _activate(entity: Entity):
        entity.show()
        entity.process_physics(True)
