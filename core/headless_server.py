"""
Headless server runner for AxisPy Engine.

Runs the game loop without any display, rendering, or audio.
Only processes physics, scripts, and networking systems.
Designed for dedicated game servers on Linux and Windows.

Usage:
    python -m core.headless_server <scene_path>
    python core/headless_server.py <scene_path>
"""
import os
import sys
import json
import time
import signal
import argparse

# Set environment to suppress pygame display before importing it
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame


def run_headless(scene_path: str, tick_rate: float = 60.0, verbose: bool = False):
    """
    Run the engine in headless mode (no display, no rendering, no audio).

    Args:
        scene_path: Path to the .scn scene file to load.
        tick_rate: Server tick rate in Hz (default 60).
        verbose: If True, print periodic status info.
    """
    project_dir = ""
    project_config = {}

    if scene_path:
        scene_abs_path = os.path.abspath(scene_path)
        env_project_dir = os.environ.get("AXISPY_PROJECT_PATH", "").strip()
        if env_project_dir and os.path.exists(env_project_dir):
            project_dir = os.path.abspath(env_project_dir)
        else:
            scene_parent = os.path.dirname(scene_abs_path)
            if os.path.basename(scene_parent).lower() == "scenes":
                project_dir = os.path.dirname(scene_parent)
            else:
                project_dir = scene_parent
        if project_dir not in sys.path:
            sys.path.insert(0, project_dir)
        os.chdir(project_dir)
        from core.resources import ResourceManager
        ResourceManager.set_headless(True)
        ResourceManager.set_base_path(project_dir)

    # Read project config
    if scene_path:
        config_path = os.path.join(project_dir, "project.config")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    project_config = json.load(f)
            except Exception as e:
                print(f"[Server] Failed to read project.config: {e}")

    # Initialize pygame in minimal mode (no display, no audio)
    pygame.init()
    # Create a tiny hidden surface so pygame doesn't complain
    screen = pygame.display.set_mode((1, 1), pygame.NOFRAME)
    pygame.display.set_caption("AxisPy Headless Server")

    from core.scene import Scene
    from core.systems.physics_system import PhysicsSystem
    from core.systems.script_system import ScriptSystem
    from core.systems.network_system import NetworkSystem
    from core.systems.timer_system import TimerSystem
    from core.systems.event_dispatch_system import EventDispatchSystem
    from core.serializer import SceneSerializer
    from core.input import Input

    # Load scene
    def load_scene(target_path: str) -> Scene:
        if target_path and os.path.exists(target_path):
            try:
                with open(target_path, "r") as f:
                    loaded = SceneSerializer.from_json(f.read())
                return loaded
            except Exception as e:
                print(f"[Server] Failed to load scene: {e}")
        fallback = Scene()
        fallback.setup_default()
        return fallback

    def apply_world_settings(target_scene: Scene):
        """Apply project config to world (layers, groups, collision matrix)."""
        config_layers = project_config.get("layers", ["Default"])
        normalized_layers = []
        seen = set()
        if isinstance(config_layers, list):
            for layer in config_layers:
                name = str(layer).strip()
                if not name:
                    continue
                low = name.lower()
                if low in seen:
                    continue
                seen.add(low)
                normalized_layers.append(name)
        if "default" in seen:
            normalized_layers = [l for l in normalized_layers if l.lower() != "default"]
        normalized_layers.insert(0, "Default")
        target_scene.world.layers = normalized_layers

        config_groups = project_config.get("groups", [])
        normalized_groups = []
        seen_groups = set()
        if isinstance(config_groups, list):
            for g in config_groups:
                text = str(g).strip()
                if not text:
                    continue
                low = text.lower()
                if low in seen_groups:
                    continue
                seen_groups.add(low)
                normalized_groups.append(text)
        world = target_scene.world
        for gn in list(world.groups.keys()):
            if gn not in normalized_groups:
                members = list(world.groups.get(gn, set()))
                for entity in members:
                    entity.remove_group(gn)
        for gn in normalized_groups:
            world.groups.setdefault(gn, set())

        raw_matrix = project_config.get("physics_collision_matrix", {})
        if not isinstance(raw_matrix, dict):
            raw_matrix = {}
        normalized_matrix = {}
        for row in normalized_groups:
            targets = raw_matrix.get(row, normalized_groups)
            if not isinstance(targets, list):
                targets = normalized_groups
            allowed = []
            seen_t = set()
            for t in targets:
                tn = str(t).strip()
                if tn not in normalized_groups:
                    continue
                lt = tn.lower()
                if lt in seen_t:
                    continue
                seen_t.add(lt)
                allowed.append(tn)
            normalized_matrix[row] = allowed
        for row in normalized_groups:
            for target in list(normalized_matrix.get(row, [])):
                peer = normalized_matrix.setdefault(target, [])
                if row not in peer:
                    peer.append(row)
        world.physics_group_order = list(normalized_groups)
        world.physics_collision_matrix = normalized_matrix

    current_scene_path = os.path.abspath(scene_path) if scene_path and os.path.exists(scene_path) else ""
    scene = load_scene(current_scene_path)
    apply_world_settings(scene)

    # Add headless systems (no render, no audio, no animation, no particles, no UI)
    physics_system = PhysicsSystem()
    scene.world.add_system(physics_system)

    script_system = ScriptSystem()
    scene.world.add_system(script_system)

    network_system = NetworkSystem()
    scene.world.add_system(network_system)

    timer_system = TimerSystem()
    scene.world.add_system(timer_system)
    event_dispatch_system = EventDispatchSystem()
    scene.world.add_system(event_dispatch_system)

    def attach_systems(target_scene: Scene):
        target_scene.world.add_system(physics_system)
        target_scene.world.add_system(script_system)
        target_scene.world.add_system(network_system)
        target_scene.world.add_system(timer_system)
        target_scene.world.add_system(event_dispatch_system)

    def resolve_scene_change(scene_name: str, current_path: str) -> str:
        requested = str(scene_name or "").strip()
        if not requested:
            return ""
        requested = os.path.normpath(requested)
        has_ext = bool(os.path.splitext(requested)[1])
        variants = [requested] if has_ext else [requested, requested + ".scn"]
        candidates = []
        for variant in variants:
            if os.path.isabs(variant):
                candidates.append(variant)
                continue
            if project_dir:
                candidates.append(os.path.normpath(os.path.join(project_dir, variant)))
                candidates.append(os.path.normpath(os.path.join(project_dir, "scenes", variant)))
            if current_path:
                candidates.append(os.path.normpath(os.path.join(os.path.dirname(current_path), variant)))
        for c in candidates:
            if c and os.path.exists(c):
                return os.path.abspath(c)
        return ""

    def teardown_scene(target_scene: Scene):
        if not target_scene:
            return
        for entity in list(target_scene.world.entities):
            target_scene.world.destroy_entity(entity)

    scene.world.sync_interpolation_state()

    # Server loop
    fixed_dt = 1.0 / tick_rate
    max_substeps = 8
    running = True
    tick_count = 0
    start_time = time.time()

    def signal_handler(sig, frame):
        nonlocal running
        print(f"\n[Server] Received signal {sig}, shutting down...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print(f"[Server] Headless server started")
    print(f"[Server] Scene: {current_scene_path}")
    print(f"[Server] Tick rate: {tick_rate} Hz (dt={fixed_dt:.4f}s)")
    print(f"[Server] Press Ctrl+C to stop")

    last_time = time.perf_counter()
    accumulator = 0.0
    status_interval = 10.0
    last_status_time = time.time()

    while running:
        now = time.perf_counter()
        frame_dt = now - last_time
        last_time = now

        # Cap frame delta to avoid spiral of death
        if frame_dt > 0.25:
            frame_dt = 0.25

        accumulator += frame_dt

        # Process pygame events (minimal — just to keep pygame happy)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Handle scene changes
        requested_scene = getattr(scene.world, "_requested_scene_name", "")
        if requested_scene:
            scene.world._requested_scene_name = ""
            resolved = resolve_scene_change(requested_scene, current_scene_path)
            if resolved:
                teardown_scene(scene)
                scene = load_scene(resolved)
                current_scene_path = resolved
                apply_world_settings(scene)
                attach_systems(scene)
                physics_system._active_collisions.clear()
                scene.world.sync_interpolation_state()
                accumulator = 0.0
                print(f"[Server] Scene changed to: {resolved}")
            else:
                print(f"[Server] Scene change failed: {requested_scene}")

        # Fixed timestep simulation
        step_count = 0
        while accumulator >= fixed_dt and step_count < max_substeps:
            scene.world.simulate(fixed_dt)
            accumulator -= fixed_dt
            step_count += 1
            tick_count += 1

        if step_count == max_substeps and accumulator >= fixed_dt:
            accumulator = min(accumulator, fixed_dt)

        # Periodic status output
        if verbose:
            now_wall = time.time()
            if now_wall - last_status_time >= status_interval:
                elapsed = now_wall - start_time
                entity_count = len(scene.world.entities)
                print(f"[Server] Uptime: {elapsed:.0f}s | Ticks: {tick_count} | Entities: {entity_count}")
                last_status_time = now_wall

        # Sleep to avoid busy-waiting (target slightly under tick interval)
        sleep_time = fixed_dt - (time.perf_counter() - last_time)
        if sleep_time > 0.001:
            time.sleep(sleep_time * 0.9)

    # Shutdown
    print(f"[Server] Shutting down...")
    teardown_scene(scene)
    pygame.quit()
    elapsed = time.time() - start_time
    print(f"[Server] Server stopped after {elapsed:.1f}s ({tick_count} ticks)")


def main():
    parser = argparse.ArgumentParser(description="AxisPy Engine - Headless Server")
    parser.add_argument("scene", nargs="?", default=None, help="Path to the .scn scene file")
    parser.add_argument("--tick-rate", type=float, default=60.0, help="Server tick rate in Hz (default: 60)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print periodic status info")
    args = parser.parse_args()

    if not args.scene:
        print("[Server] Error: No scene path provided.")
        print("[Server] Usage: python -m core.headless_server <scene_path>")
        sys.exit(1)

    run_headless(args.scene, tick_rate=args.tick_rate, verbose=args.verbose)


if __name__ == "__main__":
    main()
