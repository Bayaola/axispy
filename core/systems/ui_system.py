import pygame
from core.ecs import System, Entity
from core.components import Transform
from core.components.ui import (
    ButtonComponent, TextInputComponent, SliderComponent, 
    CheckBoxComponent, UIComponent, HBoxContainerComponent,
    VBoxContainerComponent, GridBoxContainerComponent,
    ImageRenderer, ProgressBarComponent, TextRenderer
)
from core.input import Input
from core.components.script import ScriptComponent
from core.logger import get_logger

_ui_logger = get_logger("ui_system")

class UISystem(System):
    required_components = (ButtonComponent, TextInputComponent, SliderComponent,
                           CheckBoxComponent, UIComponent, HBoxContainerComponent,
                           VBoxContainerComponent, GridBoxContainerComponent,
                           ImageRenderer, ProgressBarComponent, TextRenderer)

    def __init__(self):
        super().__init__()
        self.focused_entity = None
        self.dragging_entity = None
        self.last_mouse_pressed = False
        
        # Initialize font for size calculations if needed
        if not pygame.font.get_init():
            pygame.font.init()
        self.font_cache = {}

    def update(self, dt: float, entities: list[Entity]):
        # 1. Update Layouts
        self._update_layouts(entities)
        
        # 2. Handle Input
        mouse_pos = Input.get_game_mouse_position()
        mouse_pressed = Input.get_mouse_button(0) # Left click
        events = Input.get_events()
        
        # Filter UI entities
        if self.world:
            cached_ui = set(self.world.get_entities_with(UIComponent, Transform))
            ui_entities = [entity for entity in entities if entity in cached_ui]
        else:
            ui_entities = []
            for e in entities:
                if any(isinstance(c, UIComponent) for c in e.components.values()):
                    ui_entities.append(e)
        
        # Reverse for input priority (top-most first)
        # Assuming entities list order is draw order (Painter's algorithm)
        ui_entities.reverse()
        
        handled_click = False
        
        for entity in ui_entities:
            transform = entity.get_component(Transform)
            if not transform:
                continue
            
            # Button
            btn = entity.get_component(ButtonComponent)
            if btn:
                if self._handle_button(entity, btn, transform, mouse_pos, mouse_pressed, handled_click):
                    handled_click = True
            
            # CheckBox
            chk = entity.get_component(CheckBoxComponent)
            if chk:
                if self._handle_checkbox(entity, chk, transform, mouse_pos, mouse_pressed, handled_click):
                    handled_click = True
            
            # Slider
            slider = entity.get_component(SliderComponent)
            if slider:
                 if self._handle_slider(entity, slider, transform, mouse_pos, mouse_pressed, handled_click):
                     handled_click = True
            
            # TextInput
            txt_input = entity.get_component(TextInputComponent)
            if txt_input:
                if self._handle_text_input(
                    entity, txt_input, transform, mouse_pos, mouse_pressed, events, handled_click, dt
                ):
                    handled_click = True
                    
        # Handle dragging outside
        if self.dragging_entity:
            # Continue dragging logic even if mouse moved away
            slider = self.dragging_entity.get_component(SliderComponent)
            transform = self.dragging_entity.get_component(Transform)
            if slider and transform:
                if not mouse_pressed:
                    self.dragging_entity = None
                    slider.is_dragging = False
                else:
                    self._update_slider_value(slider, transform, mouse_pos)
                    
        self.last_mouse_pressed = mouse_pressed

    def _update_layouts(self, entities: list[Entity]):
        if self.world:
            cached_containers = set(self.world.get_entities_with(HBoxContainerComponent, Transform))
            cached_containers.update(self.world.get_entities_with(VBoxContainerComponent, Transform))
            cached_containers.update(self.world.get_entities_with(GridBoxContainerComponent, Transform))
            container_entities = [entity for entity in entities if entity in cached_containers]
        else:
            container_entities = entities

        for entity in container_entities:
            hbox = entity.get_component(HBoxContainerComponent)
            vbox = entity.get_component(VBoxContainerComponent)
            grid = entity.get_component(GridBoxContainerComponent)
            
            if not (hbox or vbox or grid):
                continue
                
            transform = entity.get_component(Transform)
            if not transform:
                continue
                
            children = entity.get_children()
            if not children:
                continue
                
            start_x = transform.x
            start_y = transform.y
            
            current_x = start_x
            current_y = start_y
            
            # Dimensions tracking
            max_row_h = 0
            max_row_w = 0 # For VBox/Grid
            grid_width = 0.0 # For Grid
            
            valid_children_count = 0
            
            for i, child in enumerate(children):
                child_transform = child.get_component(Transform)
                if not child_transform:
                    continue
                
                valid_children_count += 1
                
                w, h = self._get_ui_size(child)
                # Apply scale
                w *= child_transform.scale_x
                h *= child_transform.scale_y
                
                if hbox:
                    # Only update if changed to avoid jitter/float drift if possible, 
                    # but Transform setter handles propagation logic so we just set world pos.
                    child_transform.x = current_x
                    child_transform.y = start_y 
                    current_x += w + hbox.spacing
                    max_row_h = max(max_row_h, h)
                    
                elif vbox:
                    child_transform.x = start_x
                    child_transform.y = current_y
                    current_y += h + vbox.spacing
                    max_row_w = max(max_row_w, w)
                    
                elif grid:
                    col = i % grid.columns
                    row = i // grid.columns
                    
                    if col == 0 and i > 0:
                        current_x = start_x
                        current_y += max_row_h + grid.spacing_y
                        max_row_h = 0
                    
                    child_transform.x = current_x
                    child_transform.y = current_y
                    
                    current_x += w + grid.spacing_x
                    max_row_h = max(max_row_h, h)
                    grid_width = max(grid_width, current_x - start_x - grid.spacing_x)

            # Update container dimensions
            if hbox:
                hbox.width = max(0, current_x - start_x - hbox.spacing) if valid_children_count > 0 else 0.0
                hbox.height = max_row_h
            elif vbox:
                vbox.width = max_row_w
                vbox.height = max(0, current_y - start_y - vbox.spacing) if valid_children_count > 0 else 0.0
            elif grid:
                grid.width = grid_width
                grid.height = current_y + max_row_h - start_y

    def _get_ui_size(self, entity):
        width = 0
        height = 0
        
        # Button
        btn = entity.get_component(ButtonComponent)
        if btn:
            width = max(width, btn.width)
            height = max(height, btn.height)
            
        # Image
        img = entity.get_component(ImageRenderer)
        if img:
            width = max(width, img.width)
            height = max(height, img.height)
            
        # TextInput
        txt = entity.get_component(TextInputComponent)
        if txt:
            width = max(width, txt.width)
            height = max(height, txt.height)
            
        # Slider
        slider = entity.get_component(SliderComponent)
        if slider:
            width = max(width, slider.width)
            height = max(height, slider.height)
            
        # ProgressBar
        bar = entity.get_component(ProgressBarComponent)
        if bar:
            width = max(width, bar.width)
            height = max(height, bar.height)
            
        # CheckBox
        chk = entity.get_component(CheckBoxComponent)
        if chk:
            width = max(width, chk.size)
            height = max(height, chk.size)

        # TextRenderer
        text = entity.get_component(TextRenderer)
        if text:
            # Estimate text size
            font_size = text.font_size
            # Basic estimation if font not loaded: width ~ 0.6 * size * chars, height ~ size
            # Or try to use pygame font
            try:
                key = (text.font_path, text.font_size)
                if key not in self.font_cache:
                    self.font_cache[key] = pygame.font.Font(text.font_path, text.font_size)
                font = self.font_cache[key]
                size = font.size(text.text)
                width = max(width, size[0])
                height = max(height, size[1])
            except:
                # Fallback estimation
                width = max(width, len(text.text) * (font_size * 0.6))
                height = max(height, font_size)

        return width, height

    def _get_rect(self, transform, width, height):
        w = width * transform.scale_x
        h = height * transform.scale_y
        return pygame.Rect(transform.x, transform.y, w, h)

    def _handle_button(self, entity, btn, transform, mouse_pos, mouse_pressed, handled_click):
        rect = self._get_rect(transform, btn.width, btn.height)
        hovered = rect.collidepoint(mouse_pos)
        
        if handled_click:
            btn.is_hovered = False
            btn.is_pressed = False
            return False

        btn.is_hovered = hovered
        
        if hovered:
            if mouse_pressed:
                btn.is_pressed = True
                return True # Consume click
            else:
                if btn.is_pressed: # Release inside
                    # Clicked!
                    self._trigger_event(entity, "on_click")
                    btn.is_pressed = False
                return False
        else:
            btn.is_pressed = False
            return False

    def _handle_checkbox(self, entity, chk, transform, mouse_pos, mouse_pressed, handled_click):
        rect = self._get_rect(transform, chk.size, chk.size)
        hovered = rect.collidepoint(mouse_pos)
        
        if handled_click: return False
        
        if hovered and mouse_pressed and not self.last_mouse_pressed:
            chk.checked = not chk.checked
            self._trigger_event(entity, "on_toggle", chk.checked)
            return True
        return False

    def _handle_slider(self, entity, slider, transform, mouse_pos, mouse_pressed, handled_click):
        rect = self._get_rect(transform, slider.width, slider.height)
        hovered = rect.collidepoint(mouse_pos)
        
        if self.dragging_entity == entity:
            return True # Already handling
            
        if handled_click: return False
        
        if hovered and mouse_pressed and not self.last_mouse_pressed:
            self.dragging_entity = entity
            slider.is_dragging = True
            self._update_slider_value(slider, transform, mouse_pos)
            return True
        return False

    def _update_slider_value(self, slider, transform, mouse_pos):
        rect = self._get_rect(transform, slider.width, slider.height)
        rel_x = mouse_pos[0] - rect.x
        pct = max(0.0, min(1.0, rel_x / rect.width))
        val_range = slider.max_value - slider.min_value
        new_val = slider.min_value + (val_range * pct)
        if new_val != slider.value:
            slider.value = new_val
            self._trigger_event(self.dragging_entity, "on_value_changed", slider.value)

    def _handle_text_input(self, entity, txt_input, transform, mouse_pos, mouse_pressed, events, handled_click, dt: float):
        rect = self._get_rect(transform, txt_input.width, txt_input.height)
        hovered = rect.collidepoint(mouse_pos)
        
        # Focus handling
        if mouse_pressed and not self.last_mouse_pressed:
            if hovered and not handled_click:
                self.focused_entity = entity
                txt_input.is_focused = True
                return True
            else:
                if self.focused_entity == entity:
                    self.focused_entity = None
                    txt_input.is_focused = False
        
        if self.focused_entity == entity:
            # Handle text input
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_BACKSPACE:
                        txt_input.text = txt_input.text[:-1]
                        self._trigger_event(entity, "on_text_changed", txt_input.text)
                    elif event.key == pygame.K_RETURN:
                         self._trigger_event(entity, "on_submit", txt_input.text)
                         self.focused_entity = None
                         txt_input.is_focused = False
                elif event.type == pygame.TEXTINPUT:
                    txt_input.text += event.text
                    self._trigger_event(entity, "on_text_changed", txt_input.text)
            
            # Cursor blink (real frame dt so blink rate is consistent across FPS)
            txt_input.cursor_timer += max(0.0, float(dt))
            if txt_input.cursor_timer >= 0.5:
                txt_input.cursor_timer = 0
                txt_input.cursor_visible = not txt_input.cursor_visible
        else:
            txt_input.is_focused = False
            txt_input.cursor_visible = False
            
        return False

    def _trigger_event(self, entity, method_name, *args):
        # Call method on script if exists
        script = entity.get_component(ScriptComponent)
        if script and script.instance:
            if hasattr(script.instance, method_name):
                try:
                    getattr(script.instance, method_name)(*args)
                except Exception as e:
                    _ui_logger.error("Error calling UI callback", method=method_name, entity=entity.name, error=str(e))
