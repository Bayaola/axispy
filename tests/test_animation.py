"""Regression tests for animation module bugs.

Covers the 5 failures that were present in the original (deleted) test_animation.py:
  1. rename_node transition update
  2. from_data losing "Idle" node
  3. play() same state without restart (frame index behaviour)
  4. frame advance in AnimationSystem
  5. SpriteRenderer missing `image` attr in headless mode
"""
import pytest
from unittest.mock import MagicMock
from core.ecs import World
from core.animation import AnimationClip, AnimationController, AnimationTransition
from core.components.animator import AnimatorComponent
from core.components.sprite_renderer import SpriteRenderer
from core.resources import ResourceManager
from core.systems.animation_system import AnimationSystem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_clip(name, fps=10, loop=True, n_frames=4):
    clip = AnimationClip(name)
    clip.fps = fps
    clip.loop = loop
    clip.frames = [MagicMock(get_width=lambda: 32, get_height=lambda: 32)
                   for _ in range(n_frames)]
    return clip


def _make_controller():
    ctrl = AnimationController()
    ctrl.add_node("Idle", "idle.json")
    ctrl.add_node("Walk", "walk.json")
    ctrl.nodes["Idle"].clip = _make_clip("Idle", n_frames=1)
    ctrl.nodes["Walk"].clip = _make_clip("Walk", n_frames=4)
    ctrl.add_transition(AnimationController.ROOT_NODE_NAME, "Idle", trigger="start")
    ctrl.add_transition("Idle", "Walk", trigger="walk")
    return ctrl


# ---------------------------------------------------------------------------
# Bug 1 – rename_node should update transitions
# ---------------------------------------------------------------------------

class TestRenameNode:
    def test_rename_node_updates_from_transition(self):
        ctrl = AnimationController()
        ctrl.add_node("OldName", "clip.json")
        ctrl.add_node("Target", "target.json")
        # Transition FROM OldName TO Target (not to Root, which is rejected)
        ctrl.add_transition("OldName", "Target")
        result = ctrl.rename_node("OldName", "NewName")
        assert result is True
        assert "OldName" not in ctrl.nodes
        assert "NewName" in ctrl.nodes
        assert any(t.from_node == "NewName" for t in ctrl.transitions)

    def test_rename_node_updates_to_transition(self):
        ctrl = AnimationController()
        ctrl.add_node("Source", "src.json")
        ctrl.add_node("OldTarget", "tgt.json")
        ctrl.add_transition("Source", "OldTarget")
        ctrl.rename_node("OldTarget", "NewTarget")
        assert any(t.to_node == "NewTarget" for t in ctrl.transitions)

    def test_cannot_add_transition_to_root(self):
        ctrl = AnimationController()
        ctrl.add_node("A", "a.json")
        result = ctrl.add_transition("A", AnimationController.ROOT_NODE_NAME)
        assert result is False


# ---------------------------------------------------------------------------
# Bug 2 – from_data should preserve "Idle" when Root already exists
# ---------------------------------------------------------------------------

class TestFromDataIdleNode:
    def test_idle_preserved_when_root_exists(self):
        data = {
            "nodes": [
                {"name": "Root", "clip_path": "", "position": [0, 0]},
                {"name": "Idle", "clip_path": "idle.json", "position": [100, 100]},
                {"name": "Walk", "clip_path": "walk.json", "position": [200, 200]},
            ],
            "transitions": [
                {"from": "Root", "to": "Idle", "trigger": "start"},
                {"from": "Idle", "to": "Walk", "on_finish": True},
            ],
            "parameters": {"speed": 2.0},
        }
        controller = AnimationController.from_data(data)
        assert "Idle" in controller.nodes
        assert "Walk" in controller.nodes
        assert controller.nodes["Idle"].clip_path == "idle.json"

    def test_idle_migrated_to_root_when_no_root(self):
        """Legacy format: only 'Idle' exists, no 'Root' node."""
        data = {
            "nodes": [
                {"name": "Idle", "clip_path": "idle.json", "position": [100, 100]},
                {"name": "Walk", "clip_path": "walk.json", "position": [200, 200]},
            ],
            "transitions": [
                {"from": "Idle", "to": "Walk", "on_finish": True},
            ],
        }
        controller = AnimationController.from_data(data)
        assert "Idle" not in controller.nodes
        assert AnimationController.ROOT_NODE_NAME in controller.nodes
        assert "Walk" in controller.nodes

    def test_normalize_preserves_idle_when_root_exists(self):
        ctrl = AnimationController()
        ctrl.add_node("Idle", "idle.json")
        ctrl.add_node("Walk", "walk.json")
        ctrl.add_transition(AnimationController.ROOT_NODE_NAME, "Idle", trigger="start")
        ctrl.add_transition("Idle", "Walk", trigger="walk")
        ctrl._normalize()
        assert "Idle" in ctrl.nodes
        assert AnimationController.ROOT_NODE_NAME in ctrl.nodes

    def test_normalize_migrates_idle_when_no_root(self):
        ctrl = AnimationController()
        # Remove Root and add Idle as the only "root-like" node
        ctrl.nodes.pop(AnimationController.ROOT_NODE_NAME)
        ctrl.nodes["Idle"] = ctrl.__class__.__new__(ctrl.__class__)
        from core.animation import AnimationNode
        ctrl.nodes = {"Idle": AnimationNode("Idle", "idle.json")}
        ctrl.transitions = [AnimationTransition("Idle", "Walk")]
        ctrl.nodes["Walk"] = AnimationNode("Walk", "walk.json")
        ctrl._normalize()
        assert AnimationController.ROOT_NODE_NAME in ctrl.nodes
        assert "Idle" not in ctrl.nodes


# ---------------------------------------------------------------------------
# Bug 3 – play() same state without restart keeps frame index
# ---------------------------------------------------------------------------

class TestPlaySameState:
    def test_play_same_state_no_restart_keeps_frame_index(self):
        ctrl = _make_controller()
        animator = AnimatorComponent.__new__(AnimatorComponent)
        animator.entity = None
        animator.controller_path = None
        animator.play_on_start = True
        animator.speed = 1.0
        animator.controller = ctrl
        animator.current_state = "Idle"
        animator.current_clip = ctrl.nodes["Idle"].clip
        animator.current_frame_index = 0
        animator._frame_timer = 0.0
        animator.is_playing = True
        animator.is_paused = False
        animator._trigger_events = set()
        animator._controller_file_path = ""
        animator._controller_mtime = None

        animator.current_frame_index = 2
        animator._frame_timer = 0.5
        animator.play("Idle", restart=False)
        # play() should NOT reset frame index when restart=False and state unchanged
        assert animator.current_frame_index == 2
        # But get_current_frame() clamps at read-time
        frame = animator.get_current_frame()
        assert frame is not None  # clamped to last valid frame


# ---------------------------------------------------------------------------
# Bug 4 – AnimationSystem frame advance
# ---------------------------------------------------------------------------

class TestAnimationSystemFrameAdvance:
    def test_frame_advances_with_time(self):
        world = World()
        system = AnimationSystem()
        world.add_system(system)

        ctrl = _make_controller()
        entity = world.create_entity("Animated")

        animator = AnimatorComponent.__new__(AnimatorComponent)
        animator.entity = None
        animator.controller_path = None
        animator.play_on_start = True
        animator.speed = 1.0
        animator.controller = ctrl
        animator.current_state = "Walk"
        animator.current_clip = ctrl.nodes["Walk"].clip
        animator.current_frame_index = 0
        animator._frame_timer = 0.0
        animator.is_playing = True
        animator.is_paused = False
        animator._trigger_events = set()
        animator._controller_file_path = ""
        animator._controller_mtime = None

        sprite = MagicMock(spec=SpriteRenderer)
        sprite.image = None
        sprite._local_width = 32
        sprite._local_height = 32
        entity.add_component(animator)
        entity.components[SpriteRenderer] = sprite
        sprite.entity = entity

        # Walk clip: 4 frames at 10fps → 0.1s per frame
        # After 0.25s should advance at least 2 frames
        system.update(0.25, world.entities)
        assert animator.current_frame_index >= 2

    def test_frame_does_not_advance_when_paused(self):
        world = World()
        system = AnimationSystem()
        world.add_system(system)

        ctrl = _make_controller()
        entity = world.create_entity("Animated")

        animator = AnimatorComponent.__new__(AnimatorComponent)
        animator.entity = None
        animator.controller_path = None
        animator.play_on_start = True
        animator.speed = 1.0
        animator.controller = ctrl
        animator.current_state = "Walk"
        animator.current_clip = ctrl.nodes["Walk"].clip
        animator.current_frame_index = 0
        animator._frame_timer = 0.0
        animator.is_playing = True
        animator.is_paused = True
        animator._trigger_events = set()
        animator._controller_file_path = ""
        animator._controller_mtime = None

        sprite = MagicMock(spec=SpriteRenderer)
        sprite.image = None
        sprite._local_width = 32
        sprite._local_height = 32
        entity.add_component(animator)
        entity.components[SpriteRenderer] = sprite
        sprite.entity = entity

        system.update(0.5, world.entities)
        assert animator.current_frame_index == 0


# ---------------------------------------------------------------------------
# Bug 5 – SpriteRenderer.image should exist in headless mode
# ---------------------------------------------------------------------------

class TestSpriteRendererHeadless:
    def test_image_attribute_exists_in_headless(self):
        old = ResourceManager._headless
        ResourceManager._headless = True
        try:
            sprite = SpriteRenderer(color=(255, 0, 0), width=32, height=32)
            assert hasattr(sprite, "image")
            # image is None (no pygame surface), but the attribute exists
            assert sprite.image is None
        finally:
            ResourceManager._headless = old

    def test_image_attribute_exists_no_image_path(self):
        old = ResourceManager._headless
        ResourceManager._headless = True
        try:
            sprite = SpriteRenderer()
            assert hasattr(sprite, "image")
        finally:
            ResourceManager._headless = old
