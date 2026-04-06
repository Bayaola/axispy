import pygame
import math
from core.components import Transform

class Gizmo:
    MODE_TRANSLATE = 0
    MODE_ROTATE = 1
    MODE_SCALE = 2
    
    AXIS_NONE = 0
    AXIS_X = 1
    AXIS_Y = 2
    AXIS_Z = 3 # For rotation (Z-axis in 2D)
    AXIS_BOTH = 4
    
    def __init__(self):
        self.mode = self.MODE_TRANSLATE
        self.active_axis = self.AXIS_NONE
        self.hover_axis = self.AXIS_NONE
        self.targets = [] # List of Transform components
        self.size = 60
        self.handle_size = 10
        self.last_mouse_pos = None
        self.start_values = None # Not used for multi-selection simply yet
        
        # Colors
        self.col_x = (200, 50, 50)
        self.col_y = (50, 200, 50)
        self.col_z = (50, 50, 200)
        self.col_hover = (255, 255, 0)
        self.col_active = (255, 255, 255)

    def set_targets(self, entities):
        self.targets = []
        if entities:
            if not isinstance(entities, list):
                entities = [entities]
            for e in entities:
                t = e.get_component(Transform)
                if t:
                    self.targets.append(t)

    def set_target(self, entity):
        # Backward compatibility
        self.set_targets([entity] if entity else [])

    def get_center(self):
        if not self.targets:
            return 0, 0
        sum_x = sum(t.x for t in self.targets)
        sum_y = sum(t.y for t in self.targets)
        return sum_x / len(self.targets), sum_y / len(self.targets)

    def set_mode(self, mode):
        self.mode = mode

    def render(self, surface, camera_x, camera_y, zoom):
        if not self.targets:
            return
            
        world_cx, world_cy = self.get_center()
            
        # Screen position
        cx = int((world_cx - camera_x) * zoom)
        cy = int((world_cy - camera_y) * zoom)
        
        # Colors
        c_x = self.col_hover if self.hover_axis == self.AXIS_X or self.active_axis == self.AXIS_X else self.col_x
        c_y = self.col_hover if self.hover_axis == self.AXIS_Y or self.active_axis == self.AXIS_Y else self.col_y
        c_z = self.col_hover if self.hover_axis == self.AXIS_Z or self.active_axis == self.AXIS_Z else self.col_z
        
        # Center color (common for Translate and Scale)
        c_center = self.col_hover if self.hover_axis == self.AXIS_BOTH or self.active_axis == self.AXIS_BOTH else (200, 200, 200)

        if self.mode == self.MODE_TRANSLATE:
            # X Axis
            pygame.draw.line(surface, c_x, (cx, cy), (cx + self.size, cy), 3)
            # Arrow head X
            pygame.draw.polygon(surface, c_x, [(cx + self.size + 10, cy), (cx + self.size, cy - 5), (cx + self.size, cy + 5)])
            
            # Y Axis
            pygame.draw.line(surface, c_y, (cx, cy), (cx, cy + self.size), 3)
            # Arrow head Y
            pygame.draw.polygon(surface, c_y, [(cx, cy + self.size + 10), (cx - 5, cy + self.size), (cx + 5, cy + self.size)])
            
            # Center square
            pygame.draw.rect(surface, c_center, (cx - 6, cy - 6, 12, 12))

        elif self.mode == self.MODE_ROTATE:
            # Circle
            pygame.draw.circle(surface, c_z, (cx, cy), self.size, 3)
            # Reference line to show rotation (using first target's rotation or 0)
            base_rot = self.targets[0].rotation if self.targets else 0
            rad = math.radians(base_rot) # Positive because +y is down in screen coords
            end_x = cx + math.cos(rad) * self.size
            end_y = cy + math.sin(rad) * self.size
            pygame.draw.line(surface, (255, 255, 255), (cx, cy), (end_x, end_y), 1)
            
        elif self.mode == self.MODE_SCALE:
             # X Axis
            pygame.draw.line(surface, c_x, (cx, cy), (cx + self.size, cy), 3)
            # Box X
            pygame.draw.rect(surface, c_x, (cx + self.size - 6, cy - 6, 12, 12))
            
            # Y Axis
            pygame.draw.line(surface, c_y, (cx, cy), (cx, cy + self.size), 3)
            # Box Y
            pygame.draw.rect(surface, c_y, (cx - 6, cy + self.size - 6, 12, 12))

            # Center square (Uniform Scale)
            pygame.draw.rect(surface, c_center, (cx - 6, cy - 6, 12, 12))

    def update_hover(self, mouse_pos, camera_x, camera_y, zoom):
        if not self.targets or self.active_axis != self.AXIS_NONE:
            return

        mx, my = mouse_pos
        world_cx, world_cy = self.get_center()
        
        cx = (world_cx - camera_x) * zoom
        cy = (world_cy - camera_y) * zoom
        
        self.hover_axis = self.AXIS_NONE
        
        # Hit detection logic based on mode
        if self.mode == self.MODE_TRANSLATE:
            # Check X axis (rect from center to tip)
            if cx <= mx <= cx + self.size + 15 and cy - 8 <= my <= cy + 8:
                self.hover_axis = self.AXIS_X
            # Check Y axis
            elif cx - 8 <= mx <= cx + 8 and cy <= my <= cy + self.size + 15:
                self.hover_axis = self.AXIS_Y
            # Center
            if abs(mx - cx) < 8 and abs(my - cy) < 8:
                self.hover_axis = self.AXIS_BOTH
                
        elif self.mode == self.MODE_ROTATE:
            dist = math.hypot(mx - cx, my - cy)
            radius = self.size
            if radius - 8 <= dist <= radius + 8:
                self.hover_axis = self.AXIS_Z
                
        elif self.mode == self.MODE_SCALE:
            # Center (Uniform Scale)
            if abs(mx - cx) < 8 and abs(my - cy) < 8:
                self.hover_axis = self.AXIS_BOTH
            # Check X axis handle
            elif cx + self.size - 8 <= mx <= cx + self.size + 8 and cy - 8 <= my <= cy + 8:
                self.hover_axis = self.AXIS_X
            # Check Y axis handle
            elif cx - 8 <= mx <= cx + 8 and cy + self.size - 8 <= my <= cy + self.size + 8:
                self.hover_axis = self.AXIS_Y

    def handle_event(self, event_type, mouse_pos, camera_x, camera_y, zoom):
        """
        Returns True if the event was consumed by the gizmo
        """
        if not self.targets:
            return False

        if event_type == "MOUSEBUTTONDOWN":
            # Ensure we have the latest hover state before processing click
            self.update_hover(mouse_pos, camera_x, camera_y, zoom)
            
            if self.hover_axis != self.AXIS_NONE:
                self.active_axis = self.hover_axis
                self.last_mouse_pos = mouse_pos
                return True
                
        elif event_type == "MOUSEBUTTONUP":
            if self.active_axis != self.AXIS_NONE:
                self.active_axis = self.AXIS_NONE
                self.last_mouse_pos = None
                return True
                
        elif event_type == "MOUSEMOTION":
            self.update_hover(mouse_pos, camera_x, camera_y, zoom)
            
            if self.active_axis != self.AXIS_NONE and self.last_mouse_pos:
                mx, my = mouse_pos
                lx, ly = self.last_mouse_pos
                
                dx = (mx - lx) / zoom
                dy = (my - ly) / zoom
                
                world_cx, world_cy = self.get_center()
                cx = (world_cx - camera_x) * zoom
                cy = (world_cy - camera_y) * zoom
                
                if self.mode == self.MODE_TRANSLATE:
                    dx_total = 0
                    dy_total = 0
                    if self.active_axis == self.AXIS_X:
                        dx_total = dx
                    elif self.active_axis == self.AXIS_Y:
                        dy_total = dy
                    elif self.active_axis == self.AXIS_BOTH:
                        dx_total = dx
                        dy_total = dy
                        
                    if dx_total != 0 or dy_total != 0:
                        for t in self.targets:
                            t.translate(dx_total, dy_total)
                        
                elif self.mode == self.MODE_ROTATE:
                    # Calculate angle difference relative to center
                    angle1 = math.atan2(ly - cy, lx - cx)
                    angle2 = math.atan2(my - cy, mx - cx)
                    diff = math.degrees(angle2 - angle1) 
                    
                    if diff != 0:
                        for t in self.targets:
                            t.rotate(diff)
                    
                elif self.mode == self.MODE_SCALE:
                    sensitivity = 0.01
                    dsx = 0
                    dsy = 0
                    if self.active_axis == self.AXIS_X:
                        dsx = dx * sensitivity
                    elif self.active_axis == self.AXIS_Y:
                        dsy = dy * sensitivity 
                    elif self.active_axis == self.AXIS_BOTH:
                         dsx = dx * sensitivity
                         dsy = dx * sensitivity

                    if dsx != 0 or dsy != 0:
                        for t in self.targets:
                            t.scale(dsx, dsy)

                self.last_mouse_pos = mouse_pos
                return True
                
        return False
