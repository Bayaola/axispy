from __future__ import annotations
import pygame
import os
import json
import hashlib
from core.logger import get_logger

class ResourceManager:
    _images = {}
    _sounds = {}
    _spritesheet_frames = {}
    _base_path = ""
    _atlas_entries = {}
    _atlas_surfaces = {}
    _atlas_enabled = False
    _atlas_manifest_mtime = 0.0
    _headless = False
    _logger = get_logger("resources")

    @classmethod
    def set_headless(cls, headless: bool = True):
        """Enable headless mode: skip all image/sound/atlas loading."""
        cls._headless = headless

    @classmethod
    def set_base_path(cls, path: str):
        cls._base_path = os.path.abspath(os.path.normpath(path))
        if not cls._headless:
            cls.prebuild_sprite_atlas()

    @classmethod
    def portable_path(cls, path: str) -> str:
        """Normalize a path to always use forward slashes for cross-platform storage."""
        if not path:
            return path
        return os.path.normpath(path).replace("\\", "/")

    @classmethod
    def to_os_path(cls, path: str) -> str:
        """Convert a stored portable path (forward slashes) to native OS separators."""
        if not path:
            return path
        return os.path.normpath(path.replace("/", os.sep).replace("\\", os.sep))

    @classmethod
    def resolve_path(cls, path: str) -> str:
        # Normalize path separators to OS-native
        path = cls.to_os_path(path)
        
        if os.path.isabs(path):
            return path
        
        # Try relative to base path
        if cls._base_path:
            full_path = os.path.normpath(os.path.join(cls._base_path, path))
            if os.path.exists(full_path):
                return full_path
                
        # Try relative to CWD (fallback)
        if os.path.exists(path):
            return path
            
        return path # Return original if not found

    @classmethod
    def _normalize_key(cls, path: str) -> str:
        return os.path.normpath(path).replace("\\", "/")

    @classmethod
    def _load_raw_image(cls, path: str):
        image = pygame.image.load(path)
        try:
            image = image.convert_alpha()
        except pygame.error:
            pass
        return image

    @classmethod
    def _atlas_paths(cls, project_path: str):
        project_path = os.path.normpath(project_path)
        atlas_dir = os.path.join(project_path, "assets", ".atlas")
        atlas_image = os.path.join(atlas_dir, "sprites_atlas.png")
        atlas_manifest = os.path.join(atlas_dir, "sprites_atlas.json")
        return atlas_dir, atlas_image, atlas_manifest

    @classmethod
    def _collect_sprite_files(cls, images_root: str, atlas_dir: str) -> list[str]:
        valid_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
        files = []
        atlas_dir_norm = os.path.normpath(atlas_dir)
        for root, _, names in os.walk(images_root):
            root_norm = os.path.normpath(root)
            if root_norm.startswith(atlas_dir_norm):
                continue
            for name in names:
                ext = os.path.splitext(name)[1].lower()
                if ext not in valid_exts:
                    continue
                files.append(os.path.join(root, name))
        files.sort()
        return files

    @classmethod
    def _compute_source_signature(cls, project_path: str, source_files: list[str]) -> dict:
        hasher = hashlib.sha1()
        normalized_project = os.path.normpath(project_path)
        for abs_path in source_files:
            normalized_abs = os.path.normpath(abs_path)
            rel_path = cls._normalize_key(os.path.relpath(normalized_abs, normalized_project))
            try:
                stat_info = os.stat(normalized_abs)
            except OSError:
                continue
            hasher.update(rel_path.encode("utf-8"))
            hasher.update(b"|")
            hasher.update(str(int(stat_info.st_size)).encode("utf-8"))
            hasher.update(b"|")
            hasher.update(str(int(stat_info.st_mtime_ns)).encode("utf-8"))
            hasher.update(b"\n")
        return {
            "count": len(source_files),
            "hash": hasher.hexdigest()
        }

    @classmethod
    def prebuild_sprite_atlas(cls, force: bool = False):
        previous_manifest_mtime = cls._atlas_manifest_mtime
        cls.build_sprite_atlas_if_needed(force=force)
        cls.load_sprite_atlas_manifest()
        if cls._atlas_manifest_mtime != previous_manifest_mtime:
            cls._images.clear()
            cls._spritesheet_frames.clear()

    @classmethod
    def build_sprite_atlas_if_needed(cls, force: bool = False, max_size: int = 2048, padding: int = 2) -> bool:
        project_path = os.path.normpath(cls._base_path) if cls._base_path else ""
        if not project_path or not os.path.isdir(project_path):
            return False

        images_root = os.path.join(project_path, "assets", "images")
        if not os.path.isdir(images_root):
            return False

        atlas_dir, atlas_image_path, atlas_manifest_path = cls._atlas_paths(project_path)
        source_files = cls._collect_sprite_files(images_root, atlas_dir)
        if not source_files:
            return False

        source_signature = cls._compute_source_signature(project_path, source_files)
        if not force and os.path.exists(atlas_image_path) and os.path.exists(atlas_manifest_path):
            try:
                with open(atlas_manifest_path, "r", encoding="utf-8") as f:
                    existing_manifest = json.load(f)
            except Exception:
                existing_manifest = {}
            if existing_manifest.get("source_signature") == source_signature:
                return True

        sprite_data = []
        for abs_path in source_files:
            try:
                surface = pygame.image.load(abs_path)
            except Exception:
                continue
            if not isinstance(surface, pygame.Surface):
                continue
            width, height = surface.get_size()
            if width <= 0 or height <= 0:
                continue
            sprite_data.append({
                "abs_path": os.path.normpath(abs_path),
                "rel_path": cls._normalize_key(os.path.relpath(abs_path, project_path)),
                "surface": surface,
                "w": int(width),
                "h": int(height),
            })

        if not sprite_data:
            return False

        sprite_data.sort(key=lambda item: max(item["w"], item["h"]), reverse=True)

        x = int(padding)
        y = int(padding)
        row_h = 0
        atlas_w = int(padding)
        atlas_h = int(padding)
        placements = []

        for item in sprite_data:
            w = item["w"]
            h = item["h"]
            if w + (padding * 2) > max_size or h + (padding * 2) > max_size:
                return False
            if x + w + padding > max_size:
                x = int(padding)
                y += row_h + int(padding)
                row_h = 0
            if y + h + padding > max_size:
                return False
            placements.append({
                "rel_path": item["rel_path"],
                "surface": item["surface"],
                "x": x,
                "y": y,
                "w": w,
                "h": h,
            })
            x += w + int(padding)
            row_h = max(row_h, h)
            atlas_w = max(atlas_w, x)
            atlas_h = max(atlas_h, y + h + int(padding))

        os.makedirs(atlas_dir, exist_ok=True)
        atlas_surface = pygame.Surface((atlas_w, atlas_h), pygame.SRCALPHA, 32)
        atlas_surface.fill((0, 0, 0, 0))

        sprites = {}
        for item in placements:
            atlas_surface.blit(item["surface"], (item["x"], item["y"]))
            sprites[item["rel_path"]] = {
                "x": item["x"],
                "y": item["y"],
                "w": item["w"],
                "h": item["h"],
            }

        pygame.image.save(atlas_surface, atlas_image_path)

        manifest_data = {
            "atlas_image": cls._normalize_key(os.path.relpath(atlas_image_path, project_path)),
            "source_signature": source_signature,
            "sprites": sprites,
        }
        with open(atlas_manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)
        return True

    @classmethod
    def load_sprite_atlas_manifest(cls) -> bool:
        project_path = os.path.normpath(cls._base_path) if cls._base_path else ""
        if not project_path or not os.path.isdir(project_path):
            cls._atlas_entries.clear()
            cls._atlas_surfaces.clear()
            cls._atlas_enabled = False
            cls._atlas_manifest_mtime = 0.0
            return False

        _, _, atlas_manifest_path = cls._atlas_paths(project_path)
        if not os.path.exists(atlas_manifest_path):
            cls._atlas_entries.clear()
            cls._atlas_surfaces.clear()
            cls._atlas_enabled = False
            cls._atlas_manifest_mtime = 0.0
            return False

        try:
            with open(atlas_manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            cls._atlas_entries.clear()
            cls._atlas_surfaces.clear()
            cls._atlas_enabled = False
            cls._atlas_manifest_mtime = 0.0
            return False

        atlas_rel = data.get("atlas_image")
        sprites = data.get("sprites", {})
        atlas_abs = os.path.normpath(os.path.join(project_path, atlas_rel)) if atlas_rel else ""
        if not atlas_abs or not os.path.exists(atlas_abs):
            cls._atlas_entries.clear()
            cls._atlas_surfaces.clear()
            cls._atlas_enabled = False
            cls._atlas_manifest_mtime = 0.0
            return False

        entries = {}
        for rel_path, rect_data in sprites.items():
            try:
                x = int(rect_data["x"])
                y = int(rect_data["y"])
                w = int(rect_data["w"])
                h = int(rect_data["h"])
            except Exception:
                continue
            if w <= 0 or h <= 0:
                continue
            key = cls._normalize_key(rel_path)
            entries[key] = {
                "atlas": atlas_abs,
                "x": x,
                "y": y,
                "w": w,
                "h": h,
            }

        cls._atlas_entries = entries
        cls._atlas_surfaces.clear()
        cls._atlas_enabled = bool(entries)
        cls._atlas_manifest_mtime = os.path.getmtime(atlas_manifest_path)
        return cls._atlas_enabled

    @classmethod
    def _atlas_lookup_keys(cls, path: str, resolved_path: str) -> list[str]:
        keys = []
        keys.append(cls._normalize_key(path))
        keys.append(cls._normalize_key(resolved_path))
        if cls._base_path:
            base = os.path.normpath(cls._base_path)
            resolved_norm = os.path.normpath(resolved_path)
            try:
                rel = os.path.relpath(resolved_norm, base)
                if not rel.startswith(".."):
                    keys.append(cls._normalize_key(rel))
            except Exception:
                pass
        unique = []
        seen = set()
        for key in keys:
            if key in seen:
                continue
            seen.add(key)
            unique.append(key)
        return unique

    @classmethod
    def _load_image_from_atlas(cls, path: str, resolved_path: str):
        if not cls._atlas_enabled:
            return None
        for key in cls._atlas_lookup_keys(path, resolved_path):
            entry = cls._atlas_entries.get(key)
            if not entry:
                continue
            atlas_path = entry["atlas"]
            if cls._normalize_key(resolved_path) == cls._normalize_key(atlas_path):
                return None
            atlas_surface = cls._atlas_surfaces.get(atlas_path)
            if atlas_surface is None:
                try:
                    atlas_surface = cls._load_raw_image(atlas_path)
                except Exception:
                    return None
                cls._atlas_surfaces[atlas_path] = atlas_surface
            rect = pygame.Rect(entry["x"], entry["y"], entry["w"], entry["h"])
            if not atlas_surface.get_rect().contains(rect):
                return None
            return atlas_surface.subsurface(rect)
        return None

    @classmethod
    def load_image(cls, path: str) -> pygame.Surface:
        if cls._headless:
            return None
        if path in cls._images:
            return cls._images[path]
        
        resolved_path = cls.resolve_path(path)
        
        try:
            atlas_image = cls._load_image_from_atlas(path, resolved_path)
            if atlas_image is not None:
                cls._images[path] = atlas_image
                return atlas_image
            if os.path.exists(resolved_path):
                image = cls._load_raw_image(resolved_path)
                    
                cls._images[path] = image
                return image
            else:
                cls._logger.warning("Image not found", requested_path=path, resolved_path=resolved_path)
                return None
        except Exception as e:
            cls._logger.error("Failed to load image", requested_path=path, resolved_path=resolved_path, error=str(e))
            return None

    @classmethod
    def load_sound(cls, path: str):
        if cls._headless:
            return None
        if path in cls._sounds:
            return cls._sounds[path]
            
        resolved_path = cls.resolve_path(path)
        
        try:
            if os.path.exists(resolved_path):
                sound = pygame.mixer.Sound(resolved_path)
                cls._sounds[path] = sound
                return sound
            else:
                cls._logger.warning("Sound not found", requested_path=path, resolved_path=resolved_path)
                return None
        except Exception as e:
            cls._logger.error("Failed to load sound", requested_path=path, resolved_path=resolved_path, error=str(e))
            return None

    @classmethod
    def slice_spritesheet(
        cls,
        path: str,
        frame_width: int,
        frame_height: int,
        frame_count: int = 0,
        margin: int = 0,
        spacing: int = 0
    ) -> list[pygame.Surface]:
        if cls._headless:
            return []
        if frame_width <= 0 or frame_height <= 0:
            return []

        cache_key = (path, int(frame_width), int(frame_height), int(frame_count), int(margin), int(spacing))
        if cache_key in cls._spritesheet_frames:
            return cls._spritesheet_frames[cache_key]

        sheet = cls.load_image(path)
        if not sheet:
            cls._spritesheet_frames[cache_key] = []
            return []

        try:
            size = sheet.get_size()
        except Exception:
            size = None
        if isinstance(size, (tuple, list)) and len(size) == 2:
            sheet_w, sheet_h = int(size[0]), int(size[1])
        else:
            sheet_w = int(sheet.get_width())
            sheet_h = int(sheet.get_height())
        frames = []
        y = int(margin)
        max_frames = int(frame_count) if frame_count and frame_count > 0 else None

        while y + frame_height <= sheet_h:
            x = int(margin)
            while x + frame_width <= sheet_w:
                rect = pygame.Rect(x, y, int(frame_width), int(frame_height))
                frame = sheet.subsurface(rect).copy()
                frames.append(frame)
                if max_frames is not None and len(frames) >= max_frames:
                    cls._spritesheet_frames[cache_key] = frames
                    return frames
                x += int(frame_width) + int(spacing)
            y += int(frame_height) + int(spacing)

        cls._spritesheet_frames[cache_key] = frames
        return frames
            
    @classmethod
    def unload_image(cls, path: str):
        """Remove a single image from the cache."""
        cls._images.pop(path, None)

    @classmethod
    def unload_sound(cls, path: str):
        """Remove a single sound from the cache."""
        cls._sounds.pop(path, None)

    @classmethod
    def unload_unused(cls, used_image_paths: set[str] = None, used_sound_paths: set[str] = None):
        """Remove cached resources not in the provided sets.
        Useful between scene changes to free memory.
        Atlas surfaces are kept since they are shared across scenes."""
        if used_image_paths is not None:
            stale_images = [k for k in cls._images if k not in used_image_paths]
            for k in stale_images:
                del cls._images[k]
        if used_sound_paths is not None:
            stale_sounds = [k for k in cls._sounds if k not in used_sound_paths]
            for k in stale_sounds:
                del cls._sounds[k]

    @classmethod
    def preload_scene_assets(cls, entities) -> dict:
        """Eagerly load all images, sounds, and fonts referenced by scene entities.
        Call this at scene load to avoid lazy-load hitches during gameplay.
        Returns a summary dict with counts of preloaded assets."""
        if cls._headless:
            return {
                "images": 0,
                "sounds": 0,
                "spritesheets": 0,
                "fonts": 0,
                "used_image_paths": None,
                "used_sound_paths": None,
            }

        from core.components.sprite_renderer import SpriteRenderer
        from core.components.sound import SoundComponent
        from core.components.ui import TextRenderer, ImageRenderer
        from core.components.animator import AnimatorComponent
        from core.components.tilemap import TilemapComponent

        image_paths = set()
        sound_paths = set()
        spritesheet_keys = set()  # (path, fw, fh, margin, spacing)
        font_keys = set()         # (font_path, font_size)

        for entity in entities:
            comps = entity.components

            # SpriteRenderer images
            for comp in comps.values():
                if isinstance(comp, SpriteRenderer) and comp.image_path:
                    image_paths.add(comp.image_path)

                elif isinstance(comp, ImageRenderer) and comp.image_path:
                    image_paths.add(comp.image_path)

                elif isinstance(comp, SoundComponent) and comp.file_path:
                    sound_paths.add(comp.file_path)

                elif isinstance(comp, TextRenderer):
                    font_keys.add((comp.font_path, max(8, int(comp.font_size))))

                elif isinstance(comp, AnimatorComponent) and comp.controller:
                    for node in comp.controller.nodes.values():
                        clip = node.clip
                        if not clip:
                            continue
                        if clip.type == "spritesheet" and clip.sheet_path:
                            spritesheet_keys.add((
                                clip.sheet_path,
                                int(clip.frame_width),
                                int(clip.frame_height),
                                int(clip.margin),
                                int(clip.spacing)
                            ))
                        elif clip.type == "images" and clip.image_paths:
                            for img_path in clip.image_paths:
                                if img_path:
                                    image_paths.add(img_path)

                elif isinstance(comp, TilemapComponent):
                    ts = comp.tileset
                    if ts and ts.image_path:
                        spritesheet_keys.add((
                            ts.image_path,
                            int(ts.tile_width),
                            int(ts.tile_height),
                            int(ts.margin),
                            int(ts.spacing)
                        ))

        # Preload images
        img_count = 0
        for path in image_paths:
            if path not in cls._images:
                result = cls.load_image(path)
                if result is not None:
                    img_count += 1

        # Preload sounds
        snd_count = 0
        for path in sound_paths:
            if path not in cls._sounds:
                result = cls.load_sound(path)
                if result is not None:
                    snd_count += 1

        # Preload spritesheets
        ss_count = 0
        for key in spritesheet_keys:
            cache_key = (key[0], key[1], key[2], 0, key[3], key[4])
            if cache_key not in cls._spritesheet_frames:
                frames = cls.slice_spritesheet(key[0], key[1], key[2], 0, key[3], key[4])
                if frames:
                    ss_count += 1

        # Preload fonts (into pygame font cache)
        font_count = 0
        for font_path, font_size in font_keys:
            try:
                pygame.font.Font(font_path, font_size)
                font_count += 1
            except Exception:
                pass

        cls._logger.info(
            "Preloaded scene assets",
            images=img_count, sounds=snd_count,
            spritesheets=ss_count, fonts=font_count
        )
        return {
            "images": img_count,
            "sounds": snd_count,
            "spritesheets": ss_count,
            "fonts": font_count,
            "used_image_paths": image_paths,
            "used_sound_paths": sound_paths,
        }

    @classmethod
    def snapshot(cls) -> dict:
        """Capture the current state of all caches for later restore().
        Useful in unit tests to isolate resource side-effects."""
        return {
            "_images": dict(cls._images),
            "_sounds": dict(cls._sounds),
            "_spritesheet_frames": dict(cls._spritesheet_frames),
            "_base_path": cls._base_path,
            "_atlas_entries": dict(cls._atlas_entries),
            "_atlas_surfaces": dict(cls._atlas_surfaces),
            "_atlas_enabled": cls._atlas_enabled,
            "_atlas_manifest_mtime": cls._atlas_manifest_mtime,
            "_headless": cls._headless,
        }

    @classmethod
    def restore(cls, snap: dict):
        """Restore a previously captured snapshot, replacing all current state."""
        cls._images = snap.get("_images", {})
        cls._sounds = snap.get("_sounds", {})
        cls._spritesheet_frames = snap.get("_spritesheet_frames", {})
        cls._base_path = snap.get("_base_path", "")
        cls._atlas_entries = snap.get("_atlas_entries", {})
        cls._atlas_surfaces = snap.get("_atlas_surfaces", {})
        cls._atlas_enabled = snap.get("_atlas_enabled", False)
        cls._atlas_manifest_mtime = snap.get("_atlas_manifest_mtime", 0.0)
        cls._headless = snap.get("_headless", False)

    @classmethod
    def clear(cls):
        cls._images.clear()
        cls._sounds.clear()
        cls._spritesheet_frames.clear()
        cls._atlas_surfaces.clear()
        cls._atlas_manifest_mtime = 0.0
