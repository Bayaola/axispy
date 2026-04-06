from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from core.ecs import Component


@dataclass
class Tileset:
    image_path: str = ""
    tile_width: int = 32
    tile_height: int = 32
    spacing: int = 0
    margin: int = 0


@dataclass
class TileLayer:
    name: str = "Layer"
    width: int = 10
    height: int = 10
    tiles: List[int] = field(default_factory=list)  # row-major, 0 = empty, otherwise 1..N
    visible: bool = True
    # For infinite expansion: track offset from origin (0,0)
    offset_x: int = 0  # Index of tile at world x=0 in the array
    offset_y: int = 0  # Index of tile at world y=0 in the array

    def ensure_size(self, width: int, height: int):
        width = max(1, int(width))
        height = max(1, int(height))
        if self.width == width and self.height == height and len(self.tiles) == width * height:
            return
        old_w = max(1, int(self.width))
        old_h = max(1, int(self.height))
        old_tiles = list(self.tiles or [])
        new_tiles = [0] * (width * height)
        for y in range(min(height, old_h)):
            for x in range(min(width, old_w)):
                old_index = y * old_w + x
                new_index = y * width + x
                if 0 <= old_index < len(old_tiles):
                    new_tiles[new_index] = int(old_tiles[old_index])
        self.width = width
        self.height = height
        self.tiles = new_tiles

    def get(self, x: int, y: int) -> int:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return 0
        idx = y * self.width + x
        if idx < 0 or idx >= len(self.tiles):
            return 0
        try:
            return int(self.tiles[idx])
        except Exception:
            return 0

    def set(self, x: int, y: int, value: int):
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return
        idx = y * self.width + x
        needed = self.width * self.height
        if len(self.tiles) != needed:
            self.ensure_size(self.width, self.height)
        self.tiles[idx] = int(value)

    def world_to_array(self, world_x: int, world_y: int) -> tuple[int, int]:
        """Convert world coordinates to array indices"""
        array_x = world_x - self.offset_x
        array_y = world_y - self.offset_y
        return array_x, array_y

    def array_to_world(self, array_x: int, array_y: int) -> tuple[int, int]:
        """Convert array indices to world coordinates"""
        world_x = array_x + self.offset_x
        world_y = array_y + self.offset_y
        return world_x, world_y

    def get_world(self, world_x: int, world_y: int) -> int:
        """Get tile value at world coordinates"""
        array_x, array_y = self.world_to_array(world_x, world_y)
        return self.get(array_x, array_y)

    def set_world(self, world_x: int, world_y: int, value: int):
        """Set tile value at world coordinates, expanding if necessary"""
        array_x, array_y = self.world_to_array(world_x, world_y)
        
        # Check if we need to expand
        if array_x < 0 or array_y < 0 or array_x >= self.width or array_y >= self.height:
            self.expand_to_include(world_x, world_y)
            # Recalculate array position after expansion
            array_x, array_y = self.world_to_array(world_x, world_y)
        
        self.set(array_x, array_y, value)

    def expand_to_include(self, world_x: int, world_y: int):
        """Expand the tilemap to include the given world coordinate"""
        array_x, array_y = self.world_to_array(world_x, world_y)
        
        # Calculate new dimensions and offset
        new_width = self.width
        new_height = self.height
        new_offset_x = self.offset_x
        new_offset_y = self.offset_y
        
        # Expand left if needed
        if array_x < 0:
            expand_left = -array_x
            new_width += expand_left
            new_offset_x -= expand_left
        
        # Expand right if needed
        if array_x >= self.width:
            expand_right = array_x - self.width + 1
            new_width += expand_right
        
        # Expand up if needed
        if array_y < 0:
            expand_up = -array_y
            new_height += expand_up
            new_offset_y -= expand_up
        
        # Expand down if needed
        if array_y >= self.height:
            expand_down = array_y - self.height + 1
            new_height += expand_down
        
        # Apply expansion if needed
        if new_width != self.width or new_height != self.height:
            self.resize_with_offset(new_width, new_height, new_offset_x, new_offset_y)

    def resize_with_offset(self, new_width: int, new_height: int, new_offset_x: int, new_offset_y: int):
        """Resize the tilemap with a new offset"""
        new_width = max(1, int(new_width))
        new_height = max(1, int(new_height))
        
        # Create new tile array
        new_tiles = [0] * (new_width * new_height)
        
        # Copy existing tiles
        for array_y in range(self.height):
            for array_x in range(self.width):
                world_x, world_y = self.array_to_world(array_x, array_y)
                new_array_x, new_array_y = world_x - new_offset_x, world_y - new_offset_y
                
                if 0 <= new_array_x < new_width and 0 <= new_array_y < new_height:
                    old_idx = array_y * self.width + array_x
                    new_idx = new_array_y * new_width + new_array_x
                    if old_idx < len(self.tiles):
                        new_tiles[new_idx] = self.tiles[old_idx]
        
        # Update properties
        self.width = new_width
        self.height = new_height
        self.offset_x = new_offset_x
        self.offset_y = new_offset_y
        self.tiles = new_tiles


class TilemapComponent(Component):
    """
    Spritesheet-based tilemap.

    Coordinates:
    - Tile coordinates are (0..width-1, 0..height-1)
    - World origin is the parent entity Transform center by convention; editor treats tilemap origin as top-left.
      Rendering uses the entity Transform as an anchor, see render system for details.
    """

    def __init__(
        self,
        map_width: int = 20,
        map_height: int = 15,
        tileset: Optional[Tileset] = None,
        cell_width: Optional[int] = None,
        cell_height: Optional[int] = None,
        layers: Optional[List[TileLayer]] = None,
    ):
        self.entity = None
        self.map_width = max(1, int(map_width))
        self.map_height = max(1, int(map_height))
        self.tileset = tileset if tileset is not None else Tileset()
        self.cell_width = int(cell_width) if cell_width is not None else int(self.tileset.tile_width)
        self.cell_height = int(cell_height) if cell_height is not None else int(self.tileset.tile_height)
        self.layers: List[TileLayer] = layers if layers is not None else [TileLayer(name="Base", width=self.map_width, height=self.map_height, tiles=[0] * (self.map_width * self.map_height))]

        self._tileset_cache_key = None
        self._tileset_frames = None

    def ensure_layer_sizes(self):
        for layer in self.layers:
            layer.ensure_size(self.map_width, self.map_height)

    def get_tileset_frames(self):
        """
        Lazy cache of sliced tile images.
        Returns a list of pygame.Surface frames, index (tile_id - 1).
        """
        from core.resources import ResourceManager

        ts = self.tileset or Tileset()
        key = (ts.image_path, int(ts.tile_width), int(ts.tile_height), int(ts.margin), int(ts.spacing))
        if self._tileset_cache_key == key and self._tileset_frames is not None:
            return self._tileset_frames
        self._tileset_cache_key = key
        if not ts.image_path:
            self._tileset_frames = []
            return self._tileset_frames
        frames = ResourceManager.slice_spritesheet(
            ts.image_path,
            frame_width=int(ts.tile_width),
            frame_height=int(ts.tile_height),
            frame_count=0,
            margin=int(ts.margin),
            spacing=int(ts.spacing),
        )
        self._tileset_frames = frames or []
        return self._tileset_frames

