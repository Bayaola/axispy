from __future__ import annotations
import json
from typing import Callable
from core.ecs import Entity, World
from core.animation import AnimationController, AnimationClip
import os
from core.logger import get_logger

_serializer_logger = get_logger("serializer")
from core.components import (
    Transform,
    CameraComponent,
    SpriteRenderer,
    AnimatorComponent,
    ScriptComponent,
    SoundComponent,
    WebSocketComponent,
    HTTPClientComponent,
    HTTPRequestComponent,
    WebviewComponent,
    WebRTCComponent,
    MultiplayerComponent,
    NetworkIdentityComponent,
    BoxCollider2D,
    CircleCollider2D,
    PolygonCollider2D,
    Rigidbody2D,
    TextRenderer,
    ButtonComponent,
    TextInputComponent,
    SliderComponent,
    ProgressBarComponent,
    CheckBoxComponent,
    UIImageRenderer,
    HBoxContainerComponent,
    VBoxContainerComponent,
    GridBoxContainerComponent,
    ParticleEmitterComponent,
    TilemapComponent,
    TileLayer,
    Tileset,
    TimerComponent,
    SteeringAgentComponent,
    SeekBehavior, FleeBehavior, ArriveBehavior, WanderBehavior,
    SeparationBehavior, CohesionBehavior, AlignmentBehavior,
)
from core.components.light import PointLight2D, SpotLight2D, LightOccluder2D

class SceneSerializer:
    _component_codecs_by_name = {}
    _component_codecs_by_type = {}
    _default_codecs_registered = False

    def __init__(self):
        """Create an instance with its own codec registries, seeded from class defaults."""
        type(self)._ensure_default_component_codecs()
        self._instance_codecs_by_name: dict = dict(type(self)._component_codecs_by_name)
        self._instance_codecs_by_type: dict = dict(type(self)._component_codecs_by_type)

    def register_codec(
        self,
        component_type,
        to_data: Callable[[object], dict],
        from_data: Callable[[dict], object],
        component_name: str = None
    ):
        """Register a codec on this instance only (does not mutate class-level registry)."""
        name = component_name or component_type.__name__
        codec = {
            "name": name,
            "component_type": component_type,
            "to_data": to_data,
            "from_data": from_data
        }
        self._instance_codecs_by_name[name] = codec
        self._instance_codecs_by_type[component_type] = codec

    @classmethod
    def register_component_codec(
        cls,
        component_type,
        to_data: Callable[[object], dict],
        from_data: Callable[[dict], object],
        component_name: str = None
    ):
        name = component_name or component_type.__name__
        codec = {
            "name": name,
            "component_type": component_type,
            "to_data": to_data,
            "from_data": from_data
        }
        cls._component_codecs_by_name[name] = codec
        cls._component_codecs_by_type[component_type] = codec

    @classmethod
    def register_component_codec_alias(cls, alias_name: str, target_component_name: str):
        cls._ensure_default_component_codecs()
        codec = cls._component_codecs_by_name.get(target_component_name)
        if codec is None:
            return
        cls._component_codecs_by_name[alias_name] = codec

    @classmethod
    def _ensure_default_component_codecs(cls):
        if cls._default_codecs_registered:
            return
        cls._default_codecs_registered = True
        cls.register_component_codec(Transform, cls._transform_to_data, cls._transform_from_data)
        cls.register_component_codec(CameraComponent, cls._camera_to_data, cls._camera_from_data)
        cls.register_component_codec(SpriteRenderer, cls._sprite_to_data, cls._sprite_from_data)
        cls.register_component_codec(AnimatorComponent, cls._animator_to_data, cls._animator_from_data)
        cls.register_component_codec(ScriptComponent, cls._script_to_data, cls._script_from_data)
        cls.register_component_codec(SoundComponent, cls._sound_to_data, cls._sound_from_data)
        cls.register_component_codec(WebSocketComponent, cls._websocket_to_data, cls._websocket_from_data)
        cls.register_component_codec(HTTPClientComponent, cls._http_client_to_data, cls._http_client_from_data)
        cls.register_component_codec(HTTPRequestComponent, cls._http_request_to_data, cls._http_request_from_data)
        cls.register_component_codec(WebviewComponent, cls._webview_to_data, cls._webview_from_data)
        cls.register_component_codec(WebRTCComponent, cls._webrtc_to_data, cls._webrtc_from_data)
        cls.register_component_codec(MultiplayerComponent, cls._multiplayer_to_data, cls._multiplayer_from_data)
        cls.register_component_codec(NetworkIdentityComponent, cls._network_identity_to_data, cls._network_identity_from_data)
        cls.register_component_codec(Rigidbody2D, cls._rigidbody_to_data, cls._rigidbody_from_data)
        cls.register_component_codec(BoxCollider2D, cls._box_collider_to_data, cls._box_collider_from_data)
        cls.register_component_codec(CircleCollider2D, cls._circle_collider_to_data, cls._circle_collider_from_data)
        cls.register_component_codec(PolygonCollider2D, cls._polygon_collider_to_data, cls._polygon_collider_from_data)
        cls.register_component_codec(ParticleEmitterComponent, cls._particle_emitter_to_data, cls._particle_emitter_from_data)
        cls.register_component_codec(TextRenderer, cls._text_renderer_to_data, cls._text_renderer_from_data)
        cls.register_component_codec(ButtonComponent, cls._button_to_data, cls._button_from_data)
        cls.register_component_codec(TextInputComponent, cls._text_input_to_data, cls._text_input_from_data)
        cls.register_component_codec(SliderComponent, cls._slider_to_data, cls._slider_from_data)
        cls.register_component_codec(ProgressBarComponent, cls._progress_bar_to_data, cls._progress_bar_from_data)
        cls.register_component_codec(CheckBoxComponent, cls._checkbox_to_data, cls._checkbox_from_data)
        cls.register_component_codec(UIImageRenderer, cls._ui_image_to_data, cls._ui_image_from_data)
        cls.register_component_codec(HBoxContainerComponent, cls._hbox_to_data, cls._hbox_from_data)
        cls.register_component_codec(VBoxContainerComponent, cls._vbox_to_data, cls._vbox_from_data)
        cls.register_component_codec(GridBoxContainerComponent, cls._gridbox_to_data, cls._gridbox_from_data)
        cls.register_component_codec(TilemapComponent, cls._tilemap_to_data, cls._tilemap_from_data)
        cls.register_component_codec(TimerComponent, cls._timer_to_data, cls._timer_from_data)

        cls.register_component_codec(SteeringAgentComponent, cls._steering_agent_to_data, cls._steering_agent_from_data)
        cls.register_component_codec(SeekBehavior, cls._seek_to_data, cls._seek_from_data)
        cls.register_component_codec(FleeBehavior, cls._flee_to_data, cls._flee_from_data)
        cls.register_component_codec(ArriveBehavior, cls._arrive_to_data, cls._arrive_from_data)
        cls.register_component_codec(WanderBehavior, cls._wander_to_data, cls._wander_from_data)
        cls.register_component_codec(SeparationBehavior, cls._separation_to_data, cls._separation_from_data)
        cls.register_component_codec(CohesionBehavior, cls._cohesion_to_data, cls._cohesion_from_data)
        cls.register_component_codec(AlignmentBehavior, cls._alignment_to_data, cls._alignment_from_data)
        cls.register_component_codec(PointLight2D, cls._point_light_to_data, cls._point_light_from_data)
        cls.register_component_codec(SpotLight2D, cls._spot_light_to_data, cls._spot_light_from_data)
        cls.register_component_codec(LightOccluder2D, cls._light_occluder_to_data, cls._light_occluder_from_data)

    @staticmethod
    def save_animation_controller(path: str, controller: AnimationController):
        with open(path, "w") as f:
            json.dump(controller.to_data(), f, indent=4)

    @staticmethod
    def load_animation_controller(path: str) -> AnimationController:
        with open(path, "r") as f:
            return AnimationController.from_data(json.load(f))

    @staticmethod
    def save_animation_clip(path: str, clip: AnimationClip):
        with open(path, "w") as f:
            json.dump(clip.to_data(), f, indent=4)

    @staticmethod
    def load_animation_clip(path: str) -> AnimationClip:
        name = os.path.splitext(os.path.basename(path))[0]
        with open(path, "r") as f:
            return AnimationClip.from_data(name, json.load(f))

    @staticmethod
    def _animator_to_data(component: AnimatorComponent) -> dict:
        return {
            "controller_path": component.controller_path,
            "play_on_start": component.play_on_start,
            "speed": component.speed
        }

    @staticmethod
    def _animator_from_data(anim_data: dict) -> AnimatorComponent:
        return AnimatorComponent(
            controller_path=anim_data.get("controller_path"),
            play_on_start=anim_data.get("play_on_start", True),
            speed=anim_data.get("speed", 1.0)
        )

    @staticmethod
    def to_json(scene: Scene) -> str:
        SceneSerializer._ensure_default_component_codecs()
        data = {
            "name": scene.name,
            "layers": scene.world.layers if hasattr(scene.world, "layers") else ["Default"],
            "entities": []
        }
        editor_view_state = getattr(scene, "editor_view_state", None)
        if isinstance(editor_view_state, dict):
            data["editor_view_state"] = dict(editor_view_state)

        for entity in scene.world.entities:
            entity_data = {
                "id": entity.id,
                "name": entity.name,
                "layer": entity.layer,
                "groups": list(entity.groups),
                "tags": list(entity.tags),
                "parent": entity.parent.id if entity.parent else None,
                "visible": entity.is_visible(),
                "process_physics": entity.is_physics_processing(),
                "components": SceneSerializer._serialize_entity_components(entity)
            }

            data["entities"].append(entity_data)

        return json.dumps(data, indent=4)

    @staticmethod
    def from_json(json_str: str) -> Scene:
        SceneSerializer._ensure_default_component_codecs()
        from core.scene import Scene
        data = json.loads(json_str)
        scene = Scene(data.get("name", "LoadedScene"))
        scene.world.layers = data.get("layers", ["Default"])
        raw_editor_view_state = data.get("editor_view_state", {})
        if isinstance(raw_editor_view_state, dict):
            scene.editor_view_state = dict(raw_editor_view_state)
        else:
            scene.editor_view_state = {}

        id_to_entity = {}
        entities_data = data.get("entities", [])

        for entity_data in entities_data:
            entity = scene.world.create_entity(entity_data.get("name", "GameObject"))
            entity.id = entity_data.get("id", entity.id)
            if not entity_data.get("visible", True):
                entity.hide()
            entity.process_physics(entity_data.get("process_physics", True))
            
            entity.set_layer(entity_data.get("layer", "Default"))
            for group in entity_data.get("groups", []):
                entity.add_group(group)
            for tag in entity_data.get("tags", []):
                entity.add_tag(tag)

            id_to_entity[entity.id] = entity
            SceneSerializer._deserialize_entity_components(entity, entity_data.get("components", {}), ensure_transform=False)

        for entity_data in entities_data:
            entity_id = entity_data.get("id")
            parent_id = entity_data.get("parent")

            if parent_id and parent_id in id_to_entity and entity_id in id_to_entity:
                parent = id_to_entity[parent_id]
                child = id_to_entity[entity_id]
                parent.add_child(child)

        return scene
                
    @staticmethod
    def entity_to_json(entity: Entity) -> str:
        SceneSerializer._ensure_default_component_codecs()

        def serialize_entity_recursive(ent):
            ent_data = {
                "name": ent.name,
                "layer": ent.layer,
                "groups": list(ent.groups),
                "tags": list(ent.tags),
                "visible": ent.is_visible(),
                "process_physics": ent.is_physics_processing(),
                "components": SceneSerializer._serialize_entity_components(ent),
                "children": []
            }

            for child in ent.children:
                ent_data["children"].append(serialize_entity_recursive(child))

            return ent_data

        return json.dumps(serialize_entity_recursive(entity), indent=4)

    @staticmethod
    def entity_from_json(json_str: str, world: World) -> Entity:
        SceneSerializer._ensure_default_component_codecs()

        def create_entity_recursive(ent_data, parent=None):
            entity = world.create_entity(ent_data.get("name", "Prefab"))
            if not ent_data.get("visible", True):
                entity.hide()
            entity.process_physics(ent_data.get("process_physics", True))
            
            entity.set_layer(ent_data.get("layer", "Default"))
            for group in ent_data.get("groups", []):
                entity.add_group(group)
            for tag in ent_data.get("tags", []):
                entity.add_tag(tag)

            SceneSerializer._deserialize_entity_components(entity, ent_data.get("components", {}), ensure_transform=True)

            if parent:
                parent.add_child(entity)

            for child_data in ent_data.get("children", []):
                create_entity_recursive(child_data, entity)

            return entity

        try:
            data = json.loads(json_str)
            return create_entity_recursive(data)
        except json.JSONDecodeError as e:
            _serializer_logger.error("Error decoding JSON for prefab", error=str(e))
            return None
        except Exception as e:
            _serializer_logger.error("Error instantiating prefab", error=str(e))
            return None

    @classmethod
    def _serialize_entity_components(cls, entity: Entity) -> dict:
        components_data = {}
        for comp_type, component in entity.components.items():
            codec = cls._component_codecs_by_type.get(comp_type)
            if codec is None:
                continue
            components_data[codec["name"]] = codec["to_data"](component)
        return components_data

    @classmethod
    def _deserialize_entity_components(cls, entity: Entity, components_data: dict, ensure_transform: bool):
        if not isinstance(components_data, dict):
            components_data = {}
        if "Transform" in components_data:
            codec = cls._component_codecs_by_name.get("Transform")
            if codec:
                entity.add_component(codec["from_data"](components_data.get("Transform", {})))
        elif ensure_transform:
            entity.add_component(Transform())

        for comp_name, comp_data in components_data.items():
            if comp_name == "Transform":
                continue
            codec = cls._component_codecs_by_name.get(comp_name)
            if codec is None:
                continue
            entity.add_component(codec["from_data"](comp_data or {}))

    @staticmethod
    def _transform_to_data(component: Transform) -> dict:
        return {
            "x": component.x,
            "y": component.y,
            "rotation": component.rotation,
            "scale_x": component.scale_x,
            "scale_y": component.scale_y
        }

    @staticmethod
    def _transform_from_data(data: dict) -> Transform:
        return Transform(
            x=data.get("x", 0),
            y=data.get("y", 0),
            rotation=data.get("rotation", 0),
            scale_x=data.get("scale_x", 1.0),
            scale_y=data.get("scale_y", 1.0)
        )

    @staticmethod
    def _camera_to_data(component: CameraComponent) -> dict:
        return {
            "active": component.active,
            "priority": component.priority,
            "zoom": component.zoom,
            "rotation": component.rotation,
            "viewport_x": component.viewport_x,
            "viewport_y": component.viewport_y,
            "viewport_width": component.viewport_width,
            "viewport_height": component.viewport_height,
            "follow_target_id": component.follow_target_id,
            "follow_rotation": component.follow_rotation
        }

    @staticmethod
    def _camera_from_data(data: dict) -> CameraComponent:
        return CameraComponent(
            active=data.get("active", True),
            priority=data.get("priority", 0),
            zoom=data.get("zoom", 1.0),
            rotation=data.get("rotation", 0.0),
            viewport_x=data.get("viewport_x", 0.0),
            viewport_y=data.get("viewport_y", 0.0),
            viewport_width=data.get("viewport_width", 1.0),
            viewport_height=data.get("viewport_height", 1.0),
            follow_target_id=data.get("follow_target_id", ""),
            follow_rotation=data.get("follow_rotation", True)
        )

    @staticmethod
    def _sprite_to_data(component: SpriteRenderer) -> dict:
        return {
            "color": component.color,
            "width": component.width,
            "height": component.height,
            "image_path": getattr(component, "image_path", None)
        }

    @staticmethod
    def _sprite_from_data(data: dict) -> SpriteRenderer:
        return SpriteRenderer(
            color=tuple(data.get("color", (255, 255, 255))),
            width=data.get("width", 50),
            height=data.get("height", 50),
            image_path=data.get("image_path", None)
        )

    @staticmethod
    def _script_to_data(component: ScriptComponent) -> dict:
        return {
            "script_path": component.script_path,
            "class_name": component.class_name
        }

    @staticmethod
    def _script_from_data(data: dict) -> ScriptComponent:
        return ScriptComponent(
            script_path=data.get("script_path", ""),
            class_name=data.get("class_name", "")
        )

    @staticmethod
    def _sound_to_data(component: SoundComponent) -> dict:
        return {
            "file_path": component.file_path,
            "volume": component.volume,
            "loop": component.loop,
            "is_music": component.is_music,
            "autoplay": component.autoplay,
            "spatialize": component.spatialize,
            "min_distance": component.min_distance,
            "max_distance": component.max_distance,
            "pan_distance": component.pan_distance
        }

    @staticmethod
    def _sound_from_data(data: dict) -> SoundComponent:
        return SoundComponent(
            file_path=data.get("file_path", ""),
            volume=data.get("volume", 1.0),
            loop=data.get("loop", False),
            is_music=data.get("is_music", False),
            autoplay=data.get("autoplay", False),
            spatialize=data.get("spatialize", True),
            min_distance=data.get("min_distance", 0.0),
            max_distance=data.get("max_distance", 600.0),
            pan_distance=data.get("pan_distance", 300.0)
        )

    @staticmethod
    def _rigidbody_to_data(component: Rigidbody2D) -> dict:
        return {
            "velocity_x": component.velocity.x,
            "velocity_y": component.velocity.y,
            "mass": component.mass,
            "angular_velocity": component.angular_velocity,
            "gravity_scale": component.gravity_scale,
            "use_gravity": component.use_gravity,
            "body_type": component.body_type,
            "is_kinematic": component.is_kinematic,
            "restitution": component.restitution,
            "friction": component.friction,
            "linear_damping": component.linear_damping,
            "angular_damping": component.angular_damping,
            "freeze_rotation": component.freeze_rotation
        }

    @staticmethod
    def _rigidbody_from_data(data: dict) -> Rigidbody2D:
        body_type = data.get("body_type")
        if body_type is None:
            body_type = Rigidbody2D.BODY_TYPE_KINEMATIC if data.get("is_kinematic", False) else Rigidbody2D.BODY_TYPE_DYNAMIC
        return Rigidbody2D(
            velocity_x=data.get("velocity_x", 0.0),
            velocity_y=data.get("velocity_y", 0.0),
            mass=data.get("mass", 1.0),
            angular_velocity=data.get("angular_velocity", 0.0),
            gravity_scale=data.get("gravity_scale", 1.0),
            use_gravity=data.get("use_gravity", True),
            body_type=body_type,
            restitution=data.get("restitution", 0.0),
            friction=data.get("friction", 0.0),
            linear_damping=data.get("linear_damping", 0.0),
            angular_damping=data.get("angular_damping", 0.0),
            freeze_rotation=data.get("freeze_rotation", False)
        )

    @staticmethod
    def _box_collider_to_data(component: BoxCollider2D) -> dict:
        return {
            "width": component.width,
            "height": component.height,
            "offset_x": component.offset.x,
            "offset_y": component.offset.y,
            "is_trigger": component.is_trigger,
            "category_mask": component.category_mask,
            "collision_mask": component.collision_mask,
            "rotation": component.rotation
        }

    @staticmethod
    def _box_collider_from_data(data: dict) -> BoxCollider2D:
        return BoxCollider2D(
            width=data.get("width", None),
            height=data.get("height", None),
            offset_x=data.get("offset_x", 0.0),
            offset_y=data.get("offset_y", 0.0),
            is_trigger=data.get("is_trigger", False),
            category_mask=data.get("category_mask", 1),
            collision_mask=data.get("collision_mask", 0xFFFFFFFF),
            rotation=data.get("rotation", 0.0)
        )

    @staticmethod
    def _circle_collider_to_data(component: CircleCollider2D) -> dict:
        return {
            "radius": component.radius,
            "offset_x": component.offset.x,
            "offset_y": component.offset.y,
            "is_trigger": component.is_trigger,
            "category_mask": component.category_mask,
            "collision_mask": component.collision_mask,
            "rotation": component.rotation
        }

    @staticmethod
    def _circle_collider_from_data(data: dict) -> CircleCollider2D:
        return CircleCollider2D(
            radius=data.get("radius", None),
            offset_x=data.get("offset_x", 0.0),
            offset_y=data.get("offset_y", 0.0),
            rotation=data.get("rotation", 0.0),
            is_trigger=data.get("is_trigger", False),
            category_mask=data.get("category_mask", 1),
            collision_mask=data.get("collision_mask", 0xFFFFFFFF)
        )

    @staticmethod
    def _polygon_collider_to_data(component: PolygonCollider2D) -> dict:
        return {
            "points": [[point.x, point.y] for point in component.points],
            "offset_x": component.offset.x,
            "offset_y": component.offset.y,
            "is_trigger": component.is_trigger,
            "category_mask": component.category_mask,
            "collision_mask": component.collision_mask,
            "rotation": component.rotation
        }

    @staticmethod
    def _polygon_collider_from_data(data: dict) -> PolygonCollider2D:
        points = data.get("points", None)
        return PolygonCollider2D(
            points=points,
            offset_x=data.get("offset_x", 0.0),
            offset_y=data.get("offset_y", 0.0),
            rotation=data.get("rotation", 0.0),
            is_trigger=data.get("is_trigger", False),
            category_mask=data.get("category_mask", 1),
            collision_mask=data.get("collision_mask", 0xFFFFFFFF)
        )

    @staticmethod
    def _particle_emitter_to_data(component: ParticleEmitterComponent) -> dict:
        return {
            "emitting": component.emitting,
            "one_shot": component.one_shot,
            "local_space": component.local_space,
            "render_layer": component.render_layer,
            "blend_additive": component.blend_additive,
            "max_particles": component.max_particles,
            "emission_rate": component.emission_rate,
            "burst_count": component.burst_count,
            "burst_interval": component.burst_interval,
            "lifetime_min": component.lifetime_min,
            "lifetime_max": component.lifetime_max,
            "speed_min": component.speed_min,
            "speed_max": component.speed_max,
            "direction_degrees": component.direction_degrees,
            "spread_degrees": component.spread_degrees,
            "gravity_x": component.gravity_x,
            "gravity_y": component.gravity_y,
            "damping": component.damping,
            "radial_offset_min": component.radial_offset_min,
            "radial_offset_max": component.radial_offset_max,
            "angular_velocity_min": component.angular_velocity_min,
            "angular_velocity_max": component.angular_velocity_max,
            "start_size_min": component.start_size_min,
            "start_size_max": component.start_size_max,
            "end_size_min": component.end_size_min,
            "end_size_max": component.end_size_max,
            "start_color": component.start_color,
            "end_color": component.end_color,
            "emitter_lifetime": component.emitter_lifetime,
            "shape": component.shape
        }

    @staticmethod
    def _particle_emitter_from_data(data: dict) -> ParticleEmitterComponent:
        return ParticleEmitterComponent(
            emitting=data.get("emitting", True),
            one_shot=data.get("one_shot", False),
            local_space=data.get("local_space", False),
            render_layer=data.get("render_layer", ParticleEmitterComponent.LAYER_FRONT),
            blend_additive=data.get("blend_additive", False),
            max_particles=data.get("max_particles", 512),
            emission_rate=data.get("emission_rate", 0.0),
            burst_count=data.get("burst_count", 0),
            burst_interval=data.get("burst_interval", 1.0),
            lifetime_min=data.get("lifetime_min", 0.25),
            lifetime_max=data.get("lifetime_max", 0.75),
            speed_min=data.get("speed_min", 30.0),
            speed_max=data.get("speed_max", 90.0),
            direction_degrees=data.get("direction_degrees", 270.0),
            spread_degrees=data.get("spread_degrees", 360.0),
            gravity_x=data.get("gravity_x", 0.0),
            gravity_y=data.get("gravity_y", 0.0),
            damping=data.get("damping", 0.0),
            radial_offset_min=data.get("radial_offset_min", 0.0),
            radial_offset_max=data.get("radial_offset_max", 0.0),
            angular_velocity_min=data.get("angular_velocity_min", 0.0),
            angular_velocity_max=data.get("angular_velocity_max", 0.0),
            start_size_min=data.get("start_size_min", 4.0),
            start_size_max=data.get("start_size_max", 10.0),
            end_size_min=data.get("end_size_min", 0.0),
            end_size_max=data.get("end_size_max", 2.0),
            start_color=tuple(data.get("start_color", (255, 180, 80, 255))),
            end_color=tuple(data.get("end_color", (200, 60, 10, 0))),
            emitter_lifetime=data.get("emitter_lifetime", -1.0),
            shape=data.get("shape", ParticleEmitterComponent.SHAPE_CIRCLE)
        )

    @staticmethod
    def _text_renderer_to_data(component: TextRenderer) -> dict:
        return {
            "text": component.text,
            "font_size": component.font_size,
            "color": component.color,
            "font_path": component.font_path
        }

    @staticmethod
    def _text_renderer_from_data(data: dict) -> TextRenderer:
        return TextRenderer(
            text=data.get("text", "Text"),
            font_size=data.get("font_size", 24),
            color=tuple(data.get("color", (255, 255, 255))),
            font_path=data.get("font_path", None)
        )

    @staticmethod
    def _button_to_data(component: ButtonComponent) -> dict:
        return {
            "text": component.text,
            "width": component.width,
            "height": component.height,
            "normal_color": component.normal_color,
            "hover_color": component.hover_color,
            "pressed_color": component.pressed_color,
            "text_color": component.text_color
        }

    @staticmethod
    def _button_from_data(data: dict) -> ButtonComponent:
        return ButtonComponent(
            text=data.get("text", "Button"),
            width=data.get("width", 100.0),
            height=data.get("height", 40.0),
            normal_color=tuple(data.get("normal_color", (100, 100, 100))),
            hover_color=tuple(data.get("hover_color", (150, 150, 150))),
            pressed_color=tuple(data.get("pressed_color", (50, 50, 50))),
            text_color=tuple(data.get("text_color", (255, 255, 255)))
        )

    @staticmethod
    def _text_input_to_data(component: TextInputComponent) -> dict:
        return {
            "text": component.text,
            "placeholder": component.placeholder,
            "width": component.width,
            "height": component.height,
            "bg_color": component.bg_color,
            "text_color": component.text_color
        }

    @staticmethod
    def _text_input_from_data(data: dict) -> TextInputComponent:
        return TextInputComponent(
            text=data.get("text", ""),
            placeholder=data.get("placeholder", "Enter text..."),
            width=data.get("width", 200.0),
            height=data.get("height", 30.0),
            bg_color=tuple(data.get("bg_color", (255, 255, 255))),
            text_color=tuple(data.get("text_color", (0, 0, 0)))
        )

    @staticmethod
    def _slider_to_data(component: SliderComponent) -> dict:
        return {
            "value": component.value,
            "min_value": component.min_value,
            "max_value": component.max_value,
            "width": component.width,
            "height": component.height,
            "track_color": component.track_color,
            "handle_color": component.handle_color
        }

    @staticmethod
    def _slider_from_data(data: dict) -> SliderComponent:
        return SliderComponent(
            value=data.get("value", 0.0),
            min_value=data.get("min_value", 0.0),
            max_value=data.get("max_value", 1.0),
            width=data.get("width", 200.0),
            height=data.get("height", 20.0),
            track_color=tuple(data.get("track_color", (100, 100, 100))),
            handle_color=tuple(data.get("handle_color", (200, 200, 200)))
        )

    @staticmethod
    def _progress_bar_to_data(component: ProgressBarComponent) -> dict:
        return {
            "value": component.value,
            "min_value": component.min_value,
            "max_value": component.max_value,
            "width": component.width,
            "height": component.height,
            "bg_color": component.bg_color,
            "fill_color": component.fill_color
        }

    @staticmethod
    def _progress_bar_from_data(data: dict) -> ProgressBarComponent:
        return ProgressBarComponent(
            value=data.get("value", 0.5),
            min_value=data.get("min_value", 0.0),
            max_value=data.get("max_value", 1.0),
            width=data.get("width", 200.0),
            height=data.get("height", 20.0),
            bg_color=tuple(data.get("bg_color", (100, 100, 100))),
            fill_color=tuple(data.get("fill_color", (0, 200, 0)))
        )

    @staticmethod
    def _checkbox_to_data(component: CheckBoxComponent) -> dict:
        return {
            "checked": component.checked,
            "size": component.size,
            "checked_color": component.checked_color,
            "unchecked_color": component.unchecked_color
        }

    @staticmethod
    def _checkbox_from_data(data: dict) -> CheckBoxComponent:
        return CheckBoxComponent(
            checked=data.get("checked", False),
            size=data.get("size", 20.0),
            checked_color=tuple(data.get("checked_color", (0, 200, 0))),
            unchecked_color=tuple(data.get("unchecked_color", (200, 200, 200)))
        )

    @staticmethod
    def _ui_image_to_data(component: UIImageRenderer) -> dict:
        return {
            "image_path": component.image_path,
            "color": component.color,
            "width": component.width,
            "height": component.height
        }

    @staticmethod
    def _ui_image_from_data(data: dict) -> UIImageRenderer:
        return UIImageRenderer(
            image_path=data.get("image_path", None),
            color=tuple(data.get("color", (255, 255, 255))),
            width=data.get("width", 50.0),
            height=data.get("height", 50.0)
        )

    @staticmethod
    def _hbox_to_data(component: HBoxContainerComponent) -> dict:
        return {"spacing": component.spacing}

    @staticmethod
    def _hbox_from_data(data: dict) -> HBoxContainerComponent:
        return HBoxContainerComponent(
            spacing=data.get("spacing", 5.0)
        )

    @staticmethod
    def _vbox_to_data(component: VBoxContainerComponent) -> dict:
        return {"spacing": component.spacing}

    @staticmethod
    def _vbox_from_data(data: dict) -> VBoxContainerComponent:
        return VBoxContainerComponent(
            spacing=data.get("spacing", 5.0)
        )

    @staticmethod
    def _gridbox_to_data(component: GridBoxContainerComponent) -> dict:
        return {
            "columns": component.columns,
            "spacing_x": component.spacing_x,
            "spacing_y": component.spacing_y
        }

    @staticmethod
    def _gridbox_from_data(data: dict) -> GridBoxContainerComponent:
        return GridBoxContainerComponent(
            columns=data.get("columns", 2),
            spacing_x=data.get("spacing_x", 5.0),
            spacing_y=data.get("spacing_y", 5.0)
        )

    @staticmethod
    def _tilemap_to_data(component: TilemapComponent) -> dict:
        tileset = component.tileset or Tileset()
        layers_data = []
        for layer in component.layers or []:
            tiles = list(layer.tiles or [])
            expected = int(layer.width) * int(layer.height)
            if expected > 0 and len(tiles) != expected:
                # Normalize on serialize to avoid corrupt saves
                normalized = TileLayer(
                    name=layer.name, 
                    width=layer.width, 
                    height=layer.height, 
                    tiles=tiles, 
                    visible=getattr(layer, "visible", True),
                    offset_x=getattr(layer, "offset_x", 0),
                    offset_y=getattr(layer, "offset_y", 0)
                )
                normalized.ensure_size(layer.width, layer.height)
                tiles = list(normalized.tiles or [])
            layers_data.append({
                "name": layer.name,
                "width": int(layer.width),
                "height": int(layer.height),
                "tiles": tiles,
                "visible": bool(getattr(layer, "visible", True)),
                "offset_x": int(getattr(layer, "offset_x", 0)),
                "offset_y": int(getattr(layer, "offset_y", 0))
            })
        return {
            "map_width": int(component.map_width),
            "map_height": int(component.map_height),
            "cell_width": int(getattr(component, "cell_width", tileset.tile_width)),
            "cell_height": int(getattr(component, "cell_height", tileset.tile_height)),
            "tileset": {
                "image_path": str(getattr(tileset, "image_path", "") or ""),
                "tile_width": int(getattr(tileset, "tile_width", 32)),
                "tile_height": int(getattr(tileset, "tile_height", 32)),
                "spacing": int(getattr(tileset, "spacing", 0)),
                "margin": int(getattr(tileset, "margin", 0))
            },
            "layers": layers_data
        }

    @staticmethod
    def _tilemap_from_data(data: dict) -> TilemapComponent:
        if not isinstance(data, dict):
            data = {}
        ts_data = data.get("tileset", {})
        if not isinstance(ts_data, dict):
            ts_data = {}
        tileset = Tileset(
            image_path=str(ts_data.get("image_path", "") or ""),
            tile_width=int(ts_data.get("tile_width", 32)),
            tile_height=int(ts_data.get("tile_height", 32)),
            spacing=int(ts_data.get("spacing", 0)),
            margin=int(ts_data.get("margin", 0))
        )
        map_width = int(data.get("map_width", 20))
        map_height = int(data.get("map_height", 15))
        cell_width = data.get("cell_width", None)
        cell_height = data.get("cell_height", None)
        if cell_width is not None:
            cell_width = int(cell_width)
        if cell_height is not None:
            cell_height = int(cell_height)

        layers = []
        raw_layers = data.get("layers", [])
        if isinstance(raw_layers, list):
            for layer_data in raw_layers:
                if not isinstance(layer_data, dict):
                    continue
                name = str(layer_data.get("name", "Layer"))
                width = int(layer_data.get("width", map_width))
                height = int(layer_data.get("height", map_height))
                tiles = layer_data.get("tiles", [])
                if not isinstance(tiles, list):
                    tiles = []
                tiles = [int(v) if v is not None else 0 for v in tiles]
                layer = TileLayer(
                    name=name,
                    width=width,
                    height=height,
                    tiles=tiles,
                    visible=bool(layer_data.get("visible", True)),
                    offset_x=int(layer_data.get("offset_x", 0)),
                    offset_y=int(layer_data.get("offset_y", 0))
                )
                layer.ensure_size(width, height)
                layers.append(layer)

        component = TilemapComponent(
            map_width=map_width,
            map_height=map_height,
            tileset=tileset,
            cell_width=cell_width,
            cell_height=cell_height,
            layers=layers if layers else None
        )
        component.ensure_layer_sizes()
        return component

    @staticmethod
    def _websocket_to_data(component: WebSocketComponent) -> dict:
        return {
            "mode": component.mode,
            "host": component.host,
            "port": component.port,
            "url": component.url,
            "autostart": component.autostart,
            "max_queue_size": component.max_queue_size
        }

    @staticmethod
    def _websocket_from_data(data: dict) -> WebSocketComponent:
        return WebSocketComponent(
            mode=data.get("mode", "client"),
            host=data.get("host", "localhost"),
            port=data.get("port", 8765),
            url=data.get("url", ""),
            autostart=data.get("autostart", False),
            max_queue_size=data.get("max_queue_size", 1024)
        )

    @staticmethod
    def _http_client_to_data(component: HTTPClientComponent) -> dict:
        return {
            "base_url": component.base_url,
            "timeout": component.timeout,
            "max_concurrent": component.max_concurrent
        }

    @staticmethod
    def _http_client_from_data(data: dict) -> HTTPClientComponent:
        return HTTPClientComponent(
            base_url=data.get("base_url", ""),
            timeout=data.get("timeout", 30.0),
            max_concurrent=data.get("max_concurrent", 4)
        )

    @staticmethod
    def _http_request_to_data(component: HTTPRequestComponent) -> dict:
        return {
            "url": component.url,
            "method": component.method,
            "request_body": component.request_body,
            "content_type": component.content_type,
            "timeout": component.timeout,
            "send_on_start": component.send_on_start
        }

    @staticmethod
    def _http_request_from_data(data: dict) -> HTTPRequestComponent:
        return HTTPRequestComponent(
            url=data.get("url", ""),
            method=data.get("method", "GET"),
            request_body=data.get("request_body", ""),
            content_type=data.get("content_type", "application/json"),
            timeout=data.get("timeout", 30.0),
            send_on_start=data.get("send_on_start", False)
        )

    @staticmethod
    def _webview_to_data(component: WebviewComponent) -> dict:
        return {
            "url": component.url,
            "title": component.title,
            "width": component.width,
            "height": component.height,
            "resizable": component.resizable,
            "frameless": component.frameless,
            "autoopen": component.autoopen
        }

    @staticmethod
    def _webview_from_data(data: dict) -> WebviewComponent:
        return WebviewComponent(
            url=data.get("url", ""),
            title=data.get("title", "Webview"),
            width=data.get("width", 800),
            height=data.get("height", 600),
            resizable=data.get("resizable", True),
            frameless=data.get("frameless", False),
            autoopen=data.get("autoopen", False)
        )

    @staticmethod
    def _webrtc_to_data(component: WebRTCComponent) -> dict:
        return {
            "ice_servers": component.ice_servers,
            "data_channel_label": component.data_channel_label,
            "ordered": component.ordered,
            "max_retransmits": component.max_retransmits,
            "autostart": component.autostart,
            "max_queue_size": component.max_queue_size
        }

    @staticmethod
    def _webrtc_from_data(data: dict) -> WebRTCComponent:
        return WebRTCComponent(
            ice_servers=data.get("ice_servers", "stun:stun.l.google.com:19302"),
            data_channel_label=data.get("data_channel_label", "game"),
            ordered=data.get("ordered", True),
            max_retransmits=data.get("max_retransmits", -1),
            autostart=data.get("autostart", False),
            max_queue_size=data.get("max_queue_size", 1024)
        )

    @staticmethod
    def _multiplayer_to_data(component: MultiplayerComponent) -> dict:
        return {
            "player_name": component.player_name,
            "max_players": component.max_players,
            "sync_rate": component.sync_rate,
            "port": component.port
        }

    @staticmethod
    def _multiplayer_from_data(data: dict) -> MultiplayerComponent:
        return MultiplayerComponent(
            player_name=data.get("player_name", "Player"),
            max_players=data.get("max_players", 8),
            sync_rate=data.get("sync_rate", 20.0),
            port=data.get("port", 8765)
        )

    @staticmethod
    def _network_identity_to_data(component: NetworkIdentityComponent) -> dict:
        return {
            "network_id": component.network_id,
            "owner_id": component.owner_id,
            "sync_transform": component.sync_transform,
            "sync_interval": component.sync_interval,
            "interpolate": component.interpolate
        }

    @staticmethod
    def _network_identity_from_data(data: dict) -> NetworkIdentityComponent:
        return NetworkIdentityComponent(
            network_id=data.get("network_id", ""),
            owner_id=data.get("owner_id", ""),
            sync_transform=data.get("sync_transform", True),
            sync_interval=data.get("sync_interval", 0.05),
            interpolate=data.get("interpolate", True)
        )

    @staticmethod
    def _timer_to_data(component: TimerComponent) -> dict:
        return {
            "duration": component.duration,
            "one_shot": component.one_shot,
            "autostart": component._running,
        }

    @staticmethod
    def _timer_from_data(data: dict) -> TimerComponent:
        return TimerComponent(
            duration=data.get("duration", 1.0),
            one_shot=data.get("one_shot", True),
            autostart=data.get("autostart", False),
        )

    # -- Steering ------------------------------------------------------------

    @staticmethod
    def _steering_agent_to_data(c: SteeringAgentComponent) -> dict:
        return {
            "max_speed": c.max_speed,
            "max_force": c.max_force,
            "mass": c.mass,
            "drag": c.drag,
        }

    @staticmethod
    def _steering_agent_from_data(d: dict) -> SteeringAgentComponent:
        return SteeringAgentComponent(
            max_speed=d.get("max_speed", 150.0),
            max_force=d.get("max_force", 300.0),
            mass=d.get("mass", 1.0),
            drag=d.get("drag", 0.0),
        )

    @staticmethod
    def _seek_to_data(c: SeekBehavior) -> dict:
        return {"target_x": c.target_x, "target_y": c.target_y, "weight": c.weight, "enabled": c.enabled}

    @staticmethod
    def _seek_from_data(d: dict) -> SeekBehavior:
        b = SeekBehavior(target_x=d.get("target_x", 0.0), target_y=d.get("target_y", 0.0), weight=d.get("weight", 1.0))
        b.enabled = d.get("enabled", True)
        return b

    @staticmethod
    def _flee_to_data(c: FleeBehavior) -> dict:
        return {"target_x": c.target_x, "target_y": c.target_y, "weight": c.weight,
                "panic_distance": c.panic_distance, "enabled": c.enabled}

    @staticmethod
    def _flee_from_data(d: dict) -> FleeBehavior:
        b = FleeBehavior(target_x=d.get("target_x", 0.0), target_y=d.get("target_y", 0.0),
                         weight=d.get("weight", 1.0), panic_distance=d.get("panic_distance", 200.0))
        b.enabled = d.get("enabled", True)
        return b

    @staticmethod
    def _arrive_to_data(c: ArriveBehavior) -> dict:
        return {"target_x": c.target_x, "target_y": c.target_y, "weight": c.weight,
                "slow_radius": c.slow_radius, "enabled": c.enabled}

    @staticmethod
    def _arrive_from_data(d: dict) -> ArriveBehavior:
        b = ArriveBehavior(target_x=d.get("target_x", 0.0), target_y=d.get("target_y", 0.0),
                           weight=d.get("weight", 1.0), slow_radius=d.get("slow_radius", 100.0))
        b.enabled = d.get("enabled", True)
        return b

    @staticmethod
    def _wander_to_data(c: WanderBehavior) -> dict:
        return {"weight": c.weight, "circle_distance": c.circle_distance,
                "circle_radius": c.circle_radius, "angle_change": c.angle_change, "enabled": c.enabled}

    @staticmethod
    def _wander_from_data(d: dict) -> WanderBehavior:
        b = WanderBehavior(weight=d.get("weight", 1.0), circle_distance=d.get("circle_distance", 60.0),
                           circle_radius=d.get("circle_radius", 30.0), angle_change=d.get("angle_change", 30.0))
        b.enabled = d.get("enabled", True)
        return b

    @staticmethod
    def _separation_to_data(c: SeparationBehavior) -> dict:
        return {"weight": c.weight, "neighbor_radius": c.neighbor_radius, "enabled": c.enabled}

    @staticmethod
    def _separation_from_data(d: dict) -> SeparationBehavior:
        b = SeparationBehavior(weight=d.get("weight", 1.0), neighbor_radius=d.get("neighbor_radius", 50.0))
        b.enabled = d.get("enabled", True)
        return b

    @staticmethod
    def _cohesion_to_data(c: CohesionBehavior) -> dict:
        return {"weight": c.weight, "neighbor_radius": c.neighbor_radius, "enabled": c.enabled}

    @staticmethod
    def _cohesion_from_data(d: dict) -> CohesionBehavior:
        b = CohesionBehavior(weight=d.get("weight", 1.0), neighbor_radius=d.get("neighbor_radius", 100.0))
        b.enabled = d.get("enabled", True)
        return b

    @staticmethod
    def _alignment_to_data(c: AlignmentBehavior) -> dict:
        return {"weight": c.weight, "neighbor_radius": c.neighbor_radius, "enabled": c.enabled}

    @staticmethod
    def _alignment_from_data(d: dict) -> AlignmentBehavior:
        b = AlignmentBehavior(weight=d.get("weight", 1.0), neighbor_radius=d.get("neighbor_radius", 100.0))
        b.enabled = d.get("enabled", True)
        return b

    # --- Light codecs ---

    @staticmethod
    def _point_light_to_data(c: PointLight2D) -> dict:
        return {
            "color": list(c.color[:3]),
            "radius": c.radius,
            "intensity": c.intensity,
            "falloff": c.falloff,
        }

    @staticmethod
    def _point_light_from_data(d: dict) -> PointLight2D:
        return PointLight2D(
            color=tuple(d.get("color", [255, 255, 255])),
            radius=d.get("radius", 200.0),
            intensity=d.get("intensity", 1.0),
            falloff=d.get("falloff", 2.0),
        )

    @staticmethod
    def _spot_light_to_data(c: SpotLight2D) -> dict:
        return {
            "color": list(c.color[:3]),
            "radius": c.radius,
            "intensity": c.intensity,
            "falloff": c.falloff,
            "angle": c.angle,
            "cone_angle": c.cone_angle,
            "offset_x": c.offset_x,
            "offset_y": c.offset_y,
        }

    @staticmethod
    def _spot_light_from_data(d: dict) -> SpotLight2D:
        return SpotLight2D(
            color=tuple(d.get("color", [255, 255, 255])),
            radius=d.get("radius", 300.0),
            intensity=d.get("intensity", 1.0),
            falloff=d.get("falloff", 2.0),
            angle=d.get("angle", 0.0),
            cone_angle=d.get("cone_angle", 45.0),
            offset_x=d.get("offset_x", 0.0),
            offset_y=d.get("offset_y", 0.0),
        )

    @staticmethod
    def _light_occluder_to_data(c: LightOccluder2D) -> dict:
        data: dict = {
            "shape": c.shape,
            "offset_x": c.offset_x,
            "offset_y": c.offset_y,
            "receive_light": c.receive_light,
            "receive_shadow": c.receive_shadow,
            "rotation": c.rotation,
        }
        if c.shape == "box":
            data["width"] = c.width
            data["height"] = c.height
        elif c.shape == "circle":
            data["radius"] = c.radius
        elif c.shape == "polygon":
            data["points"] = [[p.x, p.y] for p in c.points]
        return data

    @staticmethod
    def _light_occluder_from_data(d: dict) -> LightOccluder2D:
        return LightOccluder2D(
            shape=d.get("shape", "box"),
            width=d.get("width", 50.0),
            height=d.get("height", 50.0),
            radius=d.get("radius", 25.0),
            points=d.get("points", None),
            offset_x=d.get("offset_x", 0.0),
            offset_y=d.get("offset_y", 0.0),
            receive_light=d.get("receive_light", False),
            receive_shadow=d.get("receive_shadow", False),
            rotation=d.get("rotation", 0.0),
        )
