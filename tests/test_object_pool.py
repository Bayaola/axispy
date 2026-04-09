from core.ecs import World, Entity
from core.object_pool import ObjectPool

def create_mock_entity(world: World):
    return world.create_entity("mock")

def test_object_pool_initialization():
    world = World()
    # Test prefill parameter
    prefill = {"bullet": (lambda: create_mock_entity(world), 5)}
    pool = ObjectPool(world, prefill=prefill)
    
    assert "bullet" in pool._pools
    assert pool.pool_size("bullet") == 5

def test_object_pool_register_and_acquire():
    world = World()
    pool = ObjectPool(world)
    
    pool.register("enemy", lambda: create_mock_entity(world), prefill_count=2)
    assert pool.pool_size("enemy") == 2
    
    # Acquire from prefilled pool
    entity1 = pool.acquire("enemy")
    assert entity1 is not None
    assert pool.pool_size("enemy") == 1
    
    # Acquire the second one
    entity2 = pool.acquire("enemy")
    assert pool.pool_size("enemy") == 0
    
    # Acquire when empty (should create new one)
    entity3 = pool.acquire("enemy")
    assert entity3 is not None
    assert pool.pool_size("enemy") == 0

def test_object_pool_release():
    world = World()
    pool = ObjectPool(world)
    pool.register("item", lambda: create_mock_entity(world), prefill_count=0)
    
    # Acquire a new entity since pool is empty
    entity = pool.acquire("item")
    assert pool.pool_size("item") == 0
    
    # Release puts it back into pool
    pool.release("item", entity)
    assert pool.pool_size("item") == 1

def test_object_pool_clear():
    world = World()
    pool = ObjectPool(world)
    pool.register("A", lambda: create_mock_entity(world), prefill_count=2)
    pool.register("B", lambda: create_mock_entity(world), prefill_count=3)
    
    assert pool.pool_size("A") == 2
    assert pool.pool_size("B") == 3
    
    pool.clear("A")
    assert pool.pool_size("A") == 0
    assert pool.pool_size("B") == 3
    
    pool.clear() # clear all
    assert pool.pool_size("B") == 0

def test_acquire_unregistered():
    world = World()
    pool = ObjectPool(world)
    # Trying to acquire an unregistered tag should return None and log
    entity = pool.acquire("non_existent")
    assert entity is None
