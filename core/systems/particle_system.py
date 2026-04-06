from __future__ import annotations
import array
import math
import random
from core.ecs import System, Entity
from core.components.transform import Transform
from core.components.particle_emitter import ParticleEmitterComponent


class ParticleSystem(System):
    required_components = (ParticleEmitterComponent,)

    def __init__(self):
        super().__init__()
        self._random = random.Random()

    def update(self, dt: float, entities: list[Entity]):
        if self.world:
            target_entities = self.world.get_entities_with(Transform, ParticleEmitterComponent)
        else:
            target_entities = entities
        for entity in target_entities:
            transform = entity.get_component(Transform)
            emitter = entity.get_component(ParticleEmitterComponent)
            if not transform or not emitter:
                continue
            state = self._ensure_state(emitter)
            self._update_emitter(dt, transform, emitter, state)

    def _ensure_state(self, emitter: ParticleEmitterComponent):
        if emitter._particle_state:
            return emitter._particle_state
        max_particles = max(1, int(emitter.max_particles))
        _f = lambda n, v=0.0: array.array('f', [v] * n)
        _i = lambda n, v=0: array.array('i', [v] * n)
        emitter._particle_state = {
            "alive": 0,
            "max": max_particles,
            "rate_carry": 0.0,
            "burst_timer": 0.0,
            "elapsed": 0.0,
            "x": _f(max_particles),
            "y": _f(max_particles),
            "vx": _f(max_particles),
            "vy": _f(max_particles),
            "age": _f(max_particles),
            "life": _f(max_particles, 1.0),
            "size0": _f(max_particles, 1.0),
            "size1": _f(max_particles, 1.0),
            "r0": _i(max_particles, 255),
            "g0": _i(max_particles, 255),
            "b0": _i(max_particles, 255),
            "a0": _i(max_particles, 255),
            "r1": _i(max_particles, 255),
            "g1": _i(max_particles, 255),
            "b1": _i(max_particles, 255),
            "a1": _i(max_particles, 0),
            "angle": _f(max_particles),
            "ang_vel": _f(max_particles),
        }
        return emitter._particle_state

    def _update_emitter(self, dt: float, transform: Transform, emitter: ParticleEmitterComponent, state: dict):
        if state["max"] != emitter.max_particles:
            emitter._particle_state = None
            state = self._ensure_state(emitter)

        state["elapsed"] += dt
        if emitter.emitting and emitter.emitter_lifetime >= 0.0 and state["elapsed"] >= emitter.emitter_lifetime:
            emitter.emitting = False

        if emitter.emitting:
            spawn_count = 0
            if emitter.emission_rate > 0.0:
                state["rate_carry"] += emitter.emission_rate * dt
                spawn_count += int(state["rate_carry"])
                state["rate_carry"] -= int(state["rate_carry"])

            if emitter.burst_count > 0 and not emitter.one_shot:
                state["burst_timer"] += dt
                while state["burst_timer"] >= emitter.burst_interval:
                    state["burst_timer"] -= emitter.burst_interval
                    spawn_count += emitter.burst_count

            if emitter._pending_bursts > 0 and emitter.burst_count > 0:
                spawn_count += emitter.burst_count * emitter._pending_bursts
                emitter._pending_bursts = 0

            if spawn_count > 0:
                self._spawn_particles(spawn_count, transform, emitter, state)
            if emitter.one_shot and state["alive"] > 0 and emitter._pending_bursts == 0:
                emitter.emitting = False

        self._integrate_particles(dt, emitter, state)

    def _spawn_particles(self, spawn_count: int, transform: Transform, emitter: ParticleEmitterComponent, state: dict):
        alive = state["alive"]
        max_particles = state["max"]
        free_slots = max_particles - alive
        count = min(spawn_count, free_slots)
        if count <= 0:
            return

        for i in range(count):
            idx = alive + i
            speed = self._random.uniform(emitter.speed_min, emitter.speed_max)
            angle_deg = emitter.direction_degrees + self._random.uniform(
                -emitter.spread_degrees * 0.5,
                emitter.spread_degrees * 0.5
            )
            angle_rad = math.radians(angle_deg)
            radial_dist = self._random.uniform(emitter.radial_offset_min, emitter.radial_offset_max)
            radial_ang = self._random.uniform(0.0, 360.0)
            radial_rad = math.radians(radial_ang)
            offset_x = math.cos(radial_rad) * radial_dist
            offset_y = math.sin(radial_rad) * radial_dist

            if emitter.local_space:
                state["x"][idx] = offset_x
                state["y"][idx] = offset_y
            else:
                state["x"][idx] = transform.x + offset_x
                state["y"][idx] = transform.y + offset_y

            state["vx"][idx] = math.cos(angle_rad) * speed
            state["vy"][idx] = math.sin(angle_rad) * speed
            state["age"][idx] = 0.0
            state["life"][idx] = self._random.uniform(emitter.lifetime_min, emitter.lifetime_max)
            state["size0"][idx] = self._random.uniform(emitter.start_size_min, emitter.start_size_max)
            state["size1"][idx] = self._random.uniform(emitter.end_size_min, emitter.end_size_max)
            state["r0"][idx] = int(emitter.start_color[0])
            state["g0"][idx] = int(emitter.start_color[1])
            state["b0"][idx] = int(emitter.start_color[2])
            state["a0"][idx] = int(emitter.start_color[3])
            state["r1"][idx] = int(emitter.end_color[0])
            state["g1"][idx] = int(emitter.end_color[1])
            state["b1"][idx] = int(emitter.end_color[2])
            state["a1"][idx] = int(emitter.end_color[3])
            state["angle"][idx] = self._random.uniform(0.0, 360.0)
            state["ang_vel"][idx] = self._random.uniform(emitter.angular_velocity_min, emitter.angular_velocity_max)

        state["alive"] += count

    def _integrate_particles(self, dt: float, emitter: ParticleEmitterComponent, state: dict):
        alive = state["alive"]
        if alive <= 0:
            return

        damping_factor = max(0.0, 1.0 - (emitter.damping * dt))
        i = alive - 1
        while i >= 0:
            state["age"][i] += dt
            if state["age"][i] >= state["life"][i]:
                alive = self._remove_index(i, state, alive)
                i -= 1
                continue

            state["vx"][i] *= damping_factor
            state["vy"][i] *= damping_factor
            state["vx"][i] += emitter.gravity_x * dt
            state["vy"][i] += emitter.gravity_y * dt
            state["x"][i] += state["vx"][i] * dt
            state["y"][i] += state["vy"][i] * dt
            state["angle"][i] += state["ang_vel"][i] * dt
            i -= 1

        state["alive"] = alive

    def _remove_index(self, idx: int, state: dict, alive: int):
        last = alive - 1
        if idx != last:
            for field in (
                "x", "y", "vx", "vy", "age", "life", "size0", "size1",
                "r0", "g0", "b0", "a0", "r1", "g1", "b1", "a1",
                "angle", "ang_vel"
            ):
                state[field][idx] = state[field][last]
        return last
