import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from core.ecs import World, Entity
from core.components.transform import Transform
from core.components.ui import (
    ButtonComponent, TextInputComponent, SliderComponent,
    CheckBoxComponent, UIComponent, HBoxContainerComponent,
    VBoxContainerComponent, GridBoxContainerComponent,
    TextRenderer, ProgressBarComponent,
)


# ---------------------------------------------------------------------------
# UI Component unit tests
# ---------------------------------------------------------------------------

class TestButtonComponent:
    def test_defaults(self):
        b = ButtonComponent()
        assert b.text == "Button"
        assert b.width == 100.0
        assert b.height == 40.0
        assert b.is_hovered is False
        assert b.is_pressed is False

    def test_custom_colors(self):
        b = ButtonComponent(
            normal_color=(10, 20, 30),
            hover_color=(40, 50, 60),
            pressed_color=(70, 80, 90),
        )
        assert b.normal_color == (10, 20, 30)
        assert b.hover_color == (40, 50, 60)
        assert b.pressed_color == (70, 80, 90)


class TestTextInputComponent:
    def test_defaults(self):
        t = TextInputComponent()
        assert t.text == ""
        assert t.placeholder == "Enter text..."
        assert t.is_focused is False
        assert t.cursor_visible is False

    def test_custom_text(self):
        t = TextInputComponent(text="hello", placeholder="type here")
        assert t.text == "hello"
        assert t.placeholder == "type here"


class TestSliderComponent:
    def test_defaults(self):
        s = SliderComponent()
        assert s.value == 0.0
        assert s.min_value == 0.0
        assert s.max_value == 1.0
        assert s.is_dragging is False

    def test_custom_range(self):
        s = SliderComponent(value=5, min_value=0, max_value=10)
        assert s.value == 5
        assert s.max_value == 10


class TestCheckBoxComponent:
    def test_defaults(self):
        c = CheckBoxComponent()
        assert c.checked is False
        assert c.size == 20.0

    def test_checked_true(self):
        c = CheckBoxComponent(checked=True)
        assert c.checked is True


class TestProgressBarComponent:
    def test_defaults(self):
        p = ProgressBarComponent()
        assert p.value == 0.5
        assert p.min_value == 0.0
        assert p.max_value == 1.0

    def test_custom_value(self):
        p = ProgressBarComponent(value=0.75)
        assert p.value == 0.75


class TestTextRenderer:
    def test_defaults(self):
        t = TextRenderer()
        assert t.text == "Text"
        assert t.font_size == 24


class TestHBoxContainerComponent:
    def test_defaults(self):
        h = HBoxContainerComponent()
        assert h.spacing == 5.0


class TestVBoxContainerComponent:
    def test_defaults(self):
        v = VBoxContainerComponent()
        assert v.spacing == 5.0


class TestGridBoxContainerComponent:
    def test_defaults(self):
        g = GridBoxContainerComponent()
        assert g.columns == 2


# ---------------------------------------------------------------------------
# UISystem tests (requires pygame)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _init_pygame():
    import pygame
    if not pygame.get_init():
        pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()
    yield


@pytest.fixture
def ui_world():
    from core.systems.ui_system import UISystem
    world = World()
    world.add_system(UISystem())
    return world


class TestUISystemCreation:
    def test_required_components(self):
        from core.systems.ui_system import UISystem
        s = UISystem()
        assert ButtonComponent in s.required_components
        assert TextInputComponent in s.required_components
        assert SliderComponent in s.required_components
        assert CheckBoxComponent in s.required_components

    def test_initial_state(self):
        from core.systems.ui_system import UISystem
        s = UISystem()
        assert s.focused_entity is None
        assert s.dragging_entity is None


class TestUISystemButtonHandling:
    @patch("core.systems.ui_system.Input")
    def test_button_hover(self, mock_input, ui_world):
        entity = ui_world.create_entity("Btn")
        entity.add_component(Transform(x=100, y=100))
        btn = ButtonComponent(width=100, height=40)
        entity.add_component(btn)
        mock_input.get_game_mouse_position.return_value = (100, 100)
        mock_input.get_mouse_button.return_value = False
        mock_input.get_events.return_value = []
        ui_world.update(0.016)
        assert btn.is_hovered is True

    @patch("core.systems.ui_system.Input")
    def test_button_not_hovered_when_far(self, mock_input, ui_world):
        entity = ui_world.create_entity("Btn")
        entity.add_component(Transform(x=100, y=100))
        btn = ButtonComponent(width=100, height=40)
        entity.add_component(btn)
        mock_input.get_game_mouse_position.return_value = (999, 999)
        mock_input.get_mouse_button.return_value = False
        mock_input.get_events.return_value = []
        ui_world.update(0.016)
        assert btn.is_hovered is False

    @patch("core.systems.ui_system.Input")
    def test_button_press(self, mock_input, ui_world):
        entity = ui_world.create_entity("Btn")
        entity.add_component(Transform(x=100, y=100))
        btn = ButtonComponent(width=100, height=40)
        entity.add_component(btn)
        mock_input.get_game_mouse_position.return_value = (100, 100)
        mock_input.get_mouse_button.return_value = True
        mock_input.get_events.return_value = []
        ui_world.update(0.016)
        assert btn.is_pressed is True


class TestUISystemCheckboxHandling:
    @patch("core.systems.ui_system.Input")
    def test_checkbox_toggle(self, mock_input, ui_world):
        entity = ui_world.create_entity("Chk")
        entity.add_component(Transform(x=100, y=100))
        chk = CheckBoxComponent(size=20)
        entity.add_component(chk)
        assert chk.checked is False
        # Simulate click: mouse pressed this frame, not last frame
        ui_sys = ui_world.get_system(type(ui_world.systems[-1]))
        ui_sys.last_mouse_pressed = False
        mock_input.get_game_mouse_position.return_value = (100, 100)
        mock_input.get_mouse_button.return_value = True
        mock_input.get_events.return_value = []
        ui_world.update(0.016)
        assert chk.checked is True


class TestUISystemSliderHandling:
    @patch("core.systems.ui_system.Input")
    def test_slider_drag(self, mock_input, ui_world):
        entity = ui_world.create_entity("Slider")
        entity.add_component(Transform(x=100, y=100))
        slider = SliderComponent(value=0.0, width=200, height=20)
        entity.add_component(slider)
        ui_sys = ui_world.get_system(type(ui_world.systems[-1]))
        ui_sys.last_mouse_pressed = False
        # Click on slider track midpoint
        mock_input.get_game_mouse_position.return_value = (200, 100)
        mock_input.get_mouse_button.return_value = True
        mock_input.get_events.return_value = []
        ui_world.update(0.016)
        # Value should have changed from initial 0.0
        assert slider.value != 0.0 or slider.is_dragging is True


class TestUISystemLayoutHBox:
    @patch("core.systems.ui_system.Input")
    def test_hbox_layout(self, mock_input, ui_world):
        container = ui_world.create_entity("HBox")
        container.add_component(Transform(x=0, y=0))
        hbox = HBoxContainerComponent(spacing=10)
        container.add_component(hbox)

        child1 = ui_world.create_entity("C1")
        child1.add_component(Transform(x=0, y=0))
        child1.add_component(ButtonComponent(width=50, height=30))
        container.add_child(child1)

        child2 = ui_world.create_entity("C2")
        child2.add_component(Transform(x=0, y=0))
        child2.add_component(ButtonComponent(width=50, height=30))
        container.add_child(child2)

        mock_input.get_game_mouse_position.return_value = (0, 0)
        mock_input.get_mouse_button.return_value = False
        mock_input.get_events.return_value = []
        ui_world.update(0.016)

        t1 = child1.get_component(Transform)
        t2 = child2.get_component(Transform)
        # Children should be laid out horizontally with spacing
        assert t2.x > t1.x


class TestUISystemLayoutVBox:
    @patch("core.systems.ui_system.Input")
    def test_vbox_layout(self, mock_input, ui_world):
        container = ui_world.create_entity("VBox")
        container.add_component(Transform(x=0, y=0))
        vbox = VBoxContainerComponent(spacing=10)
        container.add_component(vbox)

        child1 = ui_world.create_entity("C1")
        child1.add_component(Transform(x=0, y=0))
        child1.add_component(ButtonComponent(width=50, height=30))
        container.add_child(child1)

        child2 = ui_world.create_entity("C2")
        child2.add_component(Transform(x=0, y=0))
        child2.add_component(ButtonComponent(width=50, height=30))
        container.add_child(child2)

        mock_input.get_game_mouse_position.return_value = (0, 0)
        mock_input.get_mouse_button.return_value = False
        mock_input.get_events.return_value = []
        ui_world.update(0.016)

        t1 = child1.get_component(Transform)
        t2 = child2.get_component(Transform)
        # Children should be laid out vertically with spacing
        assert t2.y > t1.y


class TestUISystemTextInput:
    @patch("core.systems.ui_system.Input")
    def test_focus_on_click(self, mock_input, ui_world):
        entity = ui_world.create_entity("TI")
        entity.add_component(Transform(x=100, y=100))
        ti = TextInputComponent(width=200, height=30)
        entity.add_component(ti)
        ui_sys = ui_world.get_system(type(ui_world.systems[-1]))
        ui_sys.last_mouse_pressed = False
        mock_input.get_game_mouse_position.return_value = (100, 100)
        mock_input.get_mouse_button.return_value = True
        mock_input.get_events.return_value = []
        ui_world.update(0.016)
        assert ti.is_focused is True

    @patch("core.systems.ui_system.Input")
    def test_unfocus_on_click_outside(self, mock_input, ui_world):
        entity = ui_world.create_entity("TI")
        entity.add_component(Transform(x=100, y=100))
        ti = TextInputComponent(width=200, height=30)
        entity.add_component(ti)
        ti.is_focused = True
        ui_sys = ui_world.get_system(type(ui_world.systems[-1]))
        ui_sys.focused_entity = entity
        ui_sys.last_mouse_pressed = False
        mock_input.get_game_mouse_position.return_value = (999, 999)
        mock_input.get_mouse_button.return_value = True
        mock_input.get_events.return_value = []
        ui_world.update(0.016)
        assert ti.is_focused is False


class TestUISystemEmptyWorld:
    @patch("core.systems.ui_system.Input")
    def test_no_crash_empty_entities(self, mock_input, ui_world):
        mock_input.get_game_mouse_position.return_value = (0, 0)
        mock_input.get_mouse_button.return_value = False
        mock_input.get_events.return_value = []
        ui_world.update(0.016)  # Should not crash
