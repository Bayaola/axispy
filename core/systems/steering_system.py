"""Steering Behaviors System — composable autonomous movement."""
from __future__ import annotations

import math
import random
from typing import List

from core.ecs import System, Entity
from core.vector import Vector2
from core.components.transform import Transform
from core.components.steering import (
    SteeringAgentComponent,
    SeekBehavior,
    FleeBehavior,
    ArriveBehavior,
    WanderBehavior,
    SeparationBehavior,
    CohesionBehavior,
    AlignmentBehavior,
)
from core.logger import get_logger

_steer_logger = get_logger("steering")


class SteeringSystem(System):
    """Evaluates all steering behaviour components on each entity that has a
    SteeringAgentComponent, sums the weighted forces, and applies the
    resulting velocity to the entity's Transform."""

    required_components = (SteeringAgentComponent,)

    def __init__(self):
        super().__init__()

    def update(self, dt: float, entities: List[Entity]):
        if not self.world or dt <= 0.0:
            return

        agents = self.world.get_entities_with(SteeringAgentComponent)
        if not agents:
            return

        # Pre-collect positions + velocities for flocking queries
        agent_data: list[tuple[Entity, Vector2, SteeringAgentComponent]] = []
        for entity in agents:
            agent = entity.get_component(SteeringAgentComponent)
            t = entity.get_component(Transform)
            if agent and t:
                agent_data.append((entity, Vector2(t.x, t.y), agent))

        for entity, pos, agent in agent_data:
            comps = entity.components
            total_force = Vector2.zero()

            # Seek
            seek = comps.get(SeekBehavior)
            if seek and seek.enabled:
                total_force += self._seek(pos, seek.target, agent.max_speed) * seek.weight

            # Flee
            flee = comps.get(FleeBehavior)
            if flee and flee.enabled:
                total_force += self._flee(pos, flee.target, agent.max_speed, flee.panic_distance) * flee.weight

            # Arrive
            arrive = comps.get(ArriveBehavior)
            if arrive and arrive.enabled:
                total_force += self._arrive(pos, arrive.target, agent.max_speed, arrive.slow_radius, agent._velocity) * arrive.weight

            # Wander
            wander = comps.get(WanderBehavior)
            if wander and wander.enabled:
                force, new_angle = self._wander(
                    pos, agent._velocity, agent.max_speed,
                    wander.circle_distance, wander.circle_radius,
                    wander._wander_angle, wander.angle_change,
                )
                wander._wander_angle = new_angle
                total_force += force * wander.weight

            # Separation
            sep = comps.get(SeparationBehavior)
            if sep and sep.enabled:
                total_force += self._separation(entity, pos, agent_data, sep.neighbor_radius) * sep.weight

            # Cohesion
            coh = comps.get(CohesionBehavior)
            if coh and coh.enabled:
                total_force += self._cohesion(entity, pos, agent_data, coh.neighbor_radius, agent.max_speed) * coh.weight

            # Alignment
            ali = comps.get(AlignmentBehavior)
            if ali and ali.enabled:
                total_force += self._alignment(entity, agent_data, ali.neighbor_radius) * ali.weight

            # Clamp total force
            if total_force.sqr_magnitude() > agent.max_force * agent.max_force:
                total_force = total_force.normalize() * agent.max_force

            # Apply force -> acceleration -> velocity
            accel = total_force * (1.0 / agent.mass)
            agent._velocity += accel * dt

            # Drag
            if agent.drag > 0.0:
                damping = max(0.0, 1.0 - agent.drag * dt)
                agent._velocity *= damping

            # Clamp speed
            spd_sq = agent._velocity.sqr_magnitude()
            if spd_sq > agent.max_speed * agent.max_speed:
                agent._velocity = agent._velocity.normalize() * agent.max_speed

            # Move transform
            t = entity.get_component(Transform)
            if t:
                t.x += agent._velocity.x * dt
                t.y += agent._velocity.y * dt

    # -- Individual behaviour calculations ----------------------------------

    @staticmethod
    def _seek(pos: Vector2, target: Vector2, max_speed: float) -> Vector2:
        desired = target - pos
        if desired.sqr_magnitude() < 0.0001:
            return Vector2.zero()
        return desired.normalize() * max_speed

    @staticmethod
    def _flee(pos: Vector2, target: Vector2, max_speed: float, panic_dist: float) -> Vector2:
        diff = pos - target
        dist_sq = diff.sqr_magnitude()
        if panic_dist > 0 and dist_sq > panic_dist * panic_dist:
            return Vector2.zero()
        if dist_sq < 0.0001:
            return Vector2(random.uniform(-1, 1), random.uniform(-1, 1)).normalize() * max_speed
        return diff.normalize() * max_speed

    @staticmethod
    def _arrive(pos: Vector2, target: Vector2, max_speed: float,
                slow_radius: float, current_vel: Vector2) -> Vector2:
        diff = target - pos
        dist = diff.magnitude()
        if dist < 0.5:
            return -current_vel
        if dist < slow_radius:
            desired_speed = max_speed * (dist / slow_radius)
        else:
            desired_speed = max_speed
        desired = diff.normalize() * desired_speed
        return desired - current_vel

    @staticmethod
    def _wander(pos: Vector2, velocity: Vector2, max_speed: float,
                circle_dist: float, circle_rad: float,
                wander_angle: float, angle_change: float):
        speed = velocity.magnitude()
        if speed < 0.001:
            heading = Vector2(1.0, 0.0)
        else:
            heading = velocity.normalize()

        circle_center = heading * circle_dist
        displacement = Vector2(
            math.cos(math.radians(wander_angle)) * circle_rad,
            math.sin(math.radians(wander_angle)) * circle_rad,
        )
        new_angle = wander_angle + random.uniform(-angle_change, angle_change)
        force = circle_center + displacement
        return force, new_angle

    @staticmethod
    def _separation(self_entity: Entity, pos: Vector2,
                    agent_data: list, neighbor_radius: float) -> Vector2:
        force = Vector2.zero()
        r_sq = neighbor_radius * neighbor_radius
        for entity, other_pos, _ in agent_data:
            if entity is self_entity:
                continue
            diff = pos - other_pos
            dist_sq = diff.sqr_magnitude()
            if 0.0 < dist_sq < r_sq:
                dist = math.sqrt(dist_sq)
                force += diff.normalize() * (1.0 / max(dist, 0.001))
        return force

    @staticmethod
    def _cohesion(self_entity: Entity, pos: Vector2,
                  agent_data: list, neighbor_radius: float,
                  max_speed: float) -> Vector2:
        center = Vector2.zero()
        count = 0
        r_sq = neighbor_radius * neighbor_radius
        for entity, other_pos, _ in agent_data:
            if entity is self_entity:
                continue
            if pos.distance_to_squared(other_pos) < r_sq:
                center += other_pos
                count += 1
        if count == 0:
            return Vector2.zero()
        center *= (1.0 / count)
        desired = center - pos
        if desired.sqr_magnitude() < 0.0001:
            return Vector2.zero()
        return desired.normalize() * max_speed

    @staticmethod
    def _alignment(self_entity: Entity,
                   agent_data: list, neighbor_radius: float) -> Vector2:
        avg_vel = Vector2.zero()
        count = 0
        self_pos = None
        for entity, other_pos, agent in agent_data:
            if entity is self_entity:
                self_pos = other_pos
                break
        if self_pos is None:
            return Vector2.zero()
        r_sq = neighbor_radius * neighbor_radius
        for entity, other_pos, agent in agent_data:
            if entity is self_entity:
                continue
            if self_pos.distance_to_squared(other_pos) < r_sq:
                avg_vel += agent._velocity
                count += 1
        if count == 0:
            return Vector2.zero()
        avg_vel *= (1.0 / count)
        return avg_vel
