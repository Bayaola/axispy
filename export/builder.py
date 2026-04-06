from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import platform
import subprocess
import sys
from core.logger import get_logger


@dataclass
class BuildContext:
    project_path: str
    output_path: str
    platform: str
    build_mode: str = "release"
    logger: any = None
    metadata: dict = field(default_factory=dict)


class WebTemplatePart:
    """A named contribution to the pygbag HTML template from a plugin."""
    __slots__ = ("plugin_name", "section", "content", "priority")

    def __init__(self, plugin_name: str, section: str, content: str, priority: int = 100):
        self.plugin_name = plugin_name
        self.section = section      # e.g. "head_styles", "head_scripts", "body_top", "body_bottom", "config_overrides"
        self.content = content
        self.priority = priority    # lower = earlier in output


class WebTemplateRegistry:
    """
    Central registry that plugins use to contribute template customizations.
    Multiple plugins can each add parts to named sections; the final template
    is assembled by merging all contributions sorted by priority.

    Supported sections:
        head_styles      – CSS injected inside <style> in <head>
        head_scripts     – <script> blocks injected in <head>
        body_top         – HTML inserted at the top of <body>
        body_bottom      – HTML / <script> inserted at the bottom of <body>
        config_overrides – JavaScript object literals merged into the config block
        meta_tags        – extra <meta> tags in <head>
    """
    _instance: "WebTemplateRegistry | None" = None
    VALID_SECTIONS = {"head_styles", "head_scripts", "body_top", "body_bottom",
                      "config_overrides", "meta_tags"}

    def __init__(self):
        self._parts: list[WebTemplatePart] = []

    @classmethod
    def instance(cls) -> "WebTemplateRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        cls._instance = None

    # ── Plugin API ───────────────────────────────────────────────────

    def register(self, plugin_name: str, section: str, content: str, priority: int = 100):
        if section not in self.VALID_SECTIONS:
            raise ValueError(f"Unknown template section '{section}'. Valid: {sorted(self.VALID_SECTIONS)}")
        self._parts.append(WebTemplatePart(plugin_name, section, content, priority))

    def unregister(self, plugin_name: str):
        self._parts = [p for p in self._parts if p.plugin_name != plugin_name]

    def clear(self):
        self._parts.clear()

    # ── Assembly ─────────────────────────────────────────────────────

    def get_section(self, section: str) -> str:
        parts = sorted(
            [p for p in self._parts if p.section == section],
            key=lambda p: p.priority
        )
        return "\n".join(p.content for p in parts if p.content.strip())

    def has_contributions(self) -> bool:
        return len(self._parts) > 0

    def build_template(self, project_config: dict, logo_url: str = None, bg_image_url: str = None) -> str:
        """
        Assemble the full pygbag custom.tmpl HTML from a base skeleton
        plus all registered plugin contributions.
        Returns the complete HTML string.
        """
        designer = project_config.get("pygbag_designer", {})
        bg_color = designer.get("background_color", "#222222")
        text_color = designer.get("text_color", "#cccccc")
        accent_color = designer.get("accent_color", "#4fc3f7")
        loading_text = designer.get("loading_text", "Loading, please wait ...")
        show_progress = designer.get("show_progress_bar", True)
        # Use provided URLs or fall back to config values
        logo_url = logo_url if logo_url is not None else designer.get("logo_url", "")
        bg_image_url = bg_image_url if bg_image_url is not None else designer.get("background_image_url", "")
        font_family = designer.get("font_family", "Arial, Helvetica, sans-serif")
        layout = designer.get("layout", "centered")

        res_cfg = project_config.get("resolution", {})
        disp_cfg = project_config.get("display", {})
        win_cfg = disp_cfg.get("window", {})
        fb_w = int(win_cfg.get("width", res_cfg.get("width", 1280)))
        fb_h = int(win_cfg.get("height", res_cfg.get("height", 720)))
        fb_ar = round(fb_w / fb_h, 3) if fb_h > 0 else 1.77

        # Layout-dependent overlay alignment
        if layout == "top-left":
            overlay_align = "align-items: flex-start; justify-content: flex-start; padding: 40px;"
        elif layout == "bottom-center":
            overlay_align = "align-items: center; justify-content: flex-end; padding-bottom: 60px;"
        else:
            overlay_align = "align-items: center; justify-content: center;"

        bg_image_css = ""
        if bg_image_url:
            bg_image_css = f"background-image: url('{bg_image_url}'); background-size: cover; background-position: center;"

        # ── Base styles ──────────────────────────────────────────────
        base_styles = f"""
        body {{ font-family: {font_family}; margin: 0; padding: 0; background-color: {bg_color}; overflow: hidden; }}
        #status {{ display: inline-block; vertical-align: top; margin-top: 20px; margin-left: 30px; font-weight: bold; color: {text_color}; }}
        #progress {{ height: 20px; width: 300px; accent-color: {accent_color}; }}
        #infobox {{ position: fixed; background: {accent_color}; color: #fff; font-weight: bold; padding: 12px 24px; border-radius: 6px; z-index: 999999; }}
        div.emscripten {{ text-align: center; }}
        canvas.emscripten {{ border: 0px none; background-color: transparent; width: 100%; height: 100%; z-index: 5; padding: 0; margin: 0 auto; position: absolute; top: 0; bottom: 0; left: 0; right: 0; image-rendering: pixelated; image-rendering: crisp-edges; will-change: contents; }}
        #loading-overlay {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; display: flex; flex-direction: column; {overlay_align} z-index: 10; background: {bg_color}; {bg_image_css} }}
        #loading-overlay .logo {{ max-width: 200px; max-height: 200px; margin-bottom: 20px; }}
        #loading-overlay .loading-text {{ color: {text_color}; font-size: 18px; margin-bottom: 12px; }}
        #loading-overlay .progress-bar-container {{ width: 320px; height: 22px; background: rgba(255,255,255,0.1); border-radius: 11px; overflow: hidden; }}
        #loading-overlay .progress-bar-fill {{ height: 100%; width: 0%; background: {accent_color}; border-radius: 11px; transition: width 0.3s; }}
        """

        plugin_styles = self.get_section("head_styles")
        plugin_meta = self.get_section("meta_tags")
        plugin_head_scripts = self.get_section("head_scripts")
        plugin_body_top = self.get_section("body_top")
        plugin_body_bottom = self.get_section("body_bottom")
        plugin_config_overrides = self.get_section("config_overrides")

        # Build logo HTML
        logo_html = ""
        if logo_url:
            logo_html = f'<img class="logo" src="{logo_url}" alt="logo">'

        progress_html = ""
        if show_progress:
            progress_html = '<div class="progress-bar-container"><div class="progress-bar-fill" id="loading-bar"></div></div>'

        # ── Assemble template ────────────────────────────────────────
        template = (
            '<html lang="en-us">'
            '<script src="{{cookiecutter.cdn}}pythons.js" type=module id="site" '
            'data-python="python{{cookiecutter.PYBUILD}}" data-LINES=42 data-COLUMNS=132 '
            'data-os="vtx,snd,gui" async defer>#<!--\n'
            '\n'
            'print("""\n'
            'Loading {{cookiecutter.title}} from {{cookiecutter.archive}}.apk\n'
            '    Pygbag Version : {{cookiecutter.version}}\n'
            '    Template Version : 0.9.3\n'
            '    Python  : {{cookiecutter.PYBUILD}}\n'
            '    CDN URL : {{cookiecutter.cdn}}\n'
            '    Screen  : {{cookiecutter.width}}x{{cookiecutter.height}}\n'
            '    Title   : {{cookiecutter.title}}\n'
            '    Folder  : {{cookiecutter.directory}}\n'
            '    Authors : {{cookiecutter.authors}}\n'
            '    SPDX-License-Identifier: {{cookiecutter.spdx}}\n'
            '""")\n'
            '\n'
            'import sys\n'
            'import asyncio\n'
            'import platform\n'
            'import json\n'
            'from pathlib import Path\n'
            '\n'
            'async def custom_site():\n'
            '    import embed\n'
            f'    platform.document.body.style.background = "{bg_color}"\n'
            '    platform.window.transfer.hidden = True\n'
            '    platform.window.canvas.style.visibility = "visible"\n'
            '\n'
            '    bundle = "{{cookiecutter.archive}}"\n'
            '    appdir = Path(f"/data/data/{bundle}")\n'  # noqa — raw brace intentional
            '    appdir.mkdir()\n'
            '\n'
            "    if platform.window.location.host.find('.itch.zone')>0:\n"
            '        import zipfile\n'
            '        async with platform.fopen("{{cookiecutter.archive}}.apk", "rb") as archive:\n'
            '            with zipfile.ZipFile(archive) as zip_ref:\n'
            '                zip_ref.extractall(appdir.as_posix())\n'
            '    else:\n'
            '        import tarfile\n'
            '        async with platform.fopen("{{cookiecutter.archive}}.tar.gz", "rb") as archive:\n'
            '            tar = tarfile.open(fileobj=archive, mode="r:gz")\n'
            "            tar.extractall(path=appdir.as_posix(), filter='tar')\n"
            '            tar.close()\n'
            '\n'
            '    platform.run_main(PyConfig, loaderhome= appdir / "assets", loadermain=None)\n'
            '\n'
            '    while embed.counter()<0:\n'
            '        await asyncio.sleep(.1)\n'
            '\n'
            '    main = appdir / "assets" / "main.py"\n'
            '\n'
            '    if not platform.window.MM.UME:\n'
            '        __import__(__name__).__file__ = main\n'
            '        msg  = "Ready to start ! Please click/touch page"\n'
            '        platform.window.infobox.innerText = msg\n'
            '        platform.window.show_infobox()\n'
            '        while not platform.window.MM.UME:\n'
            '            await asyncio.sleep(.1)\n'
            '\n'
            '    await TopLevel_async_handler.start_toplevel(platform.shell, console=window.python.config.debug)\n'
            '\n'
            '    __import__(__name__).__file__ = main\n'
            '\n'
            '    def ui_callback(pkg):\n'
            '        platform.window.infobox.innerText = f"installing {pkg}"\n'
            '        platform.window.show_infobox()\n'
            '\n'
            '    await shell.source(main, callback=ui_callback)\n'
            '\n'
            '    # Hide loading overlay once game starts\n'
            '    try:\n'
            '        overlay = platform.document.getElementById("loading-overlay")\n'
            '        if overlay:\n'
            '            overlay.style.display = "none"\n'
            '    except Exception:\n'
            '        pass\n'
            '\n'
            '    platform.window.infobox.style.display = "none"\n'
            '    platform.window.config.gui_divider = 1\n'
            '    platform.window.window_resize()\n'
            '\n'
            '    shell.interactive()\n'
            '\n'
            'asyncio.run( custom_site() )\n'
            '\n'
            '# --></script><head><!--\n'
            '//=============================================================================\n'
            '\n'
            '--><script type="application/javascript">\n'
            '// END BLOCK\n'
            '\n'
            'config = {\n'
            '    xtermjs : "{{cookiecutter.xtermjs}}" ,\n'
            '    _sdl2 : "canvas",\n'
            '    user_canvas : 0,\n'
            '    user_canvas_managed : 0,\n'
            '    gui_divider : 2,\n'
            '    ume_block : {{cookiecutter.ume_block}},\n'
            '    can_close : {{cookiecutter.can_close}},\n'
            '    archive : "{{cookiecutter.archive}}",\n'
            '    gui_debug : 2,\n'
            '    cdn : "{{cookiecutter.cdn}}",\n'
            '    autorun : {{cookiecutter.autorun}},\n'
            '    PYBUILD : "{{cookiecutter.PYBUILD}}",\n'
            f'    fb_ar   : {fb_ar},\n'
            f'    fb_width : "{fb_w}",\n'
            f'    fb_height : "{fb_h}"\n'
        )

        if plugin_config_overrides:
            template += '    ,' + plugin_config_overrides + '\n'

        template += (
            '}\n'
            '\n'
            'function show_infobox() {\n'
            '    infobox.style.display = "block";\n'
            '    const w = infobox.offsetWidth;\n'
            '    const h = infobox.offsetHeight;\n'
            '    const left = (window.innerWidth - w) / 2;\n'
            '    const top = (window.innerHeight - h) / 2;\n'
            '    infobox.style.left = left + "px";\n'
            '    infobox.style.top = top + "px";\n'
            '}\n'
            '</script>\n'
            '\n'
            '    <title>{{cookiecutter.title}}</title>\n'
            '    <meta charset="UTF-8">\n'
            '    <meta http-equiv="X-UA-Compatible" content="IE=edge">\n'
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">\n'
            '    <meta name="mobile-web-app-capable" content="yes">\n'
            '    <meta name="apple-mobile-web-app-capable" content="yes"/>\n'
            '    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"/>\n'
        )

        if plugin_meta:
            template += plugin_meta + '\n'

        if plugin_head_scripts:
            template += plugin_head_scripts + '\n'

        template += (
            '    <link rel="icon" type="image/png" href="favicon.png" sizes="16x16">\n'
            '    <style>\n'
            + base_styles + '\n'
        )
        if plugin_styles:
            template += plugin_styles + '\n'

        template += (
            '    </style>\n'
            '    <script src="{{cookiecutter.cdn}}/browserfs.min.js"></script>\n'
            '</head>\n'
            '\n'
            '<body>\n'
        )

        # Loading overlay
        template += (
            '    <div id="loading-overlay">\n'
        )
        if logo_html:
            template += f'        {logo_html}\n'
        template += (
            f'        <div class="loading-text">{loading_text}</div>\n'
        )
        if progress_html:
            template += f'        {progress_html}\n'
        template += '    </div>\n\n'

        if plugin_body_top:
            template += plugin_body_top + '\n'

        template += (
            '    <div id="transfer" align=center>\n'
            '        <div class="emscripten" id="status">Downloading...</div>\n'
            '        <div class="emscripten"><progress value="0" max="100" id="progress"></progress></div>\n'
            '    </div>\n'
            '\n'
            f'    <canvas class="emscripten" id="canvas" width="{fb_w}px" height="{fb_h}px" oncontextmenu="event.preventDefault()" tabindex=1></canvas>\n'
            f'    <canvas class="emscripten" id="canvas3d" width="{fb_w}px" height="{fb_h}px" oncontextmenu="event.preventDefault()" tabindex=1 hidden></canvas>\n'
            '\n'
            '    <div id="infobox" style="display: none;"></div>\n'
            '\n'
            '    <div id="pyconsole">\n'
            '        <div id="terminal" tabIndex=1 align="left"></div>\n'
            '    </div>\n'
            '\n'
            '    <script type="application/javascript">\n'
            '    const ogProg = document.getElementById("progress");\n'
            '    const custBar = document.getElementById("loading-bar");\n'
            '    if (ogProg && custBar) {\n'
            '        new MutationObserver(() => {\n'
            '            let val = ogProg.value || 0;\n'
            '            let max = ogProg.max || 100;\n'
            '            custBar.style.width = ((val / max) * 100) + "%";\n'
            '        }).observe(ogProg, { attributes: true, attributeFilter: ["value", "max"] });\n'
            '    }\n'
            '\n'
            '    async function custom_onload(debug_hidden) {\n'
            '        pyconsole.hidden = debug_hidden;\n'
            '        transfer.hidden = debug_hidden;\n'
            '        // infobox will be shown when needed during loading\n'
            '    }\n'
            '    function custom_prerun(){}\n'
            '    function custom_postrun(){}\n'
            '    </script>\n'
        )

        if plugin_body_bottom:
            template += plugin_body_bottom + '\n'

        template += (
            '</body>\n'
            '</html>\n'
        )

        return template


class BuildNode:
    def __init__(self, name: str, action):
        self.name = name
        self.action = action
        self.dependencies: list[str] = []

    def depends_on(self, *node_names: str):
        for node_name in node_names:
            if node_name not in self.dependencies:
                self.dependencies.append(node_name)
        return self


class BuildGraph:
    def __init__(self):
        self.nodes: dict[str, BuildNode] = {}

    def add(self, node: BuildNode):
        self.nodes[node.name] = node
        return node

    def run(self, context: BuildContext):
        executed = set()
        for name in list(self.nodes.keys()):
            self._run_node(name, context, executed)

    def _run_node(self, node_name: str, context: BuildContext, executed: set[str]):
        if node_name in executed:
            return
        node = self.nodes[node_name]
        for dependency in node.dependencies:
            self._run_node(dependency, context, executed)
        context.logger.info("Build step start", platform=context.platform, step=node.name)
        node.action(context)
        context.logger.info("Build step done", platform=context.platform, step=node.name)
        executed.add(node_name)


class Exporter:
    platform = "generic"

    def __init__(self, build_mode: str = "release"):
        self.build_mode = build_mode
        self.logger = get_logger(f"export.{self.platform}")
        self.graph = self._build_graph()

    def _build_context(self, project_path: str, output_path: str):
        normalized_output = os.path.abspath(os.path.normpath(output_path))
        platform_output = normalized_output
        if os.path.basename(normalized_output).lower() != self.platform.lower():
            platform_output = os.path.join(normalized_output, self.platform)
        return BuildContext(
            project_path=os.path.abspath(os.path.normpath(project_path)),
            output_path=os.path.abspath(os.path.normpath(platform_output)),
            platform=self.platform,
            build_mode=self.build_mode,
            logger=self.logger
        )

    def _build_graph(self):
        graph = BuildGraph()
        graph.add(BuildNode("prepare_output", self._prepare_output))
        graph.add(BuildNode("capture_manifest", self._capture_manifest)).depends_on("prepare_output")
        graph.add(BuildNode("cook_assets", self._cook_assets)).depends_on("capture_manifest")
        graph.add(BuildNode("copy_runtime", self._copy_runtime)).depends_on("cook_assets")
        graph.add(BuildNode("write_template", self._write_platform_template)).depends_on("copy_runtime")
        graph.add(BuildNode("finalize", self._finalize)).depends_on("write_template")
        return graph

    def export(self, project_path: str, output_path: str):
        context = self._build_context(project_path, output_path)
        self.graph.run(context)
        return context

    def _prepare_output(self, context: BuildContext):
        os.makedirs(context.output_path, exist_ok=True)

    def _capture_manifest(self, context: BuildContext):
        manifest = self._collect_file_manifest(context.project_path)
        manifest_path = os.path.join(context.output_path, "build_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as file:
            json.dump(manifest, file, indent=2)
        context.metadata["manifest"] = manifest
        context.metadata["manifest_path"] = manifest_path

    def _cook_assets(self, context: BuildContext):
        source_assets = os.path.join(context.project_path, "assets")
        cooked_assets = os.path.join(context.output_path, "assets")
        if os.path.exists(cooked_assets):
            shutil.rmtree(cooked_assets)
        if os.path.exists(source_assets):
            shutil.copytree(source_assets, cooked_assets)
        context.metadata["cooked_assets"] = cooked_assets

    def _copy_runtime(self, context: BuildContext):
        runtime_dirs = ["core", "plugins"]
        engine_root = self._engine_root()
        for runtime_dir in runtime_dirs:
            source = os.path.join(context.project_path, runtime_dir)
            if not os.path.exists(source):
                source = os.path.join(engine_root, runtime_dir)
            if not os.path.exists(source):
                continue
            destination = os.path.join(context.output_path, runtime_dir)
            if os.path.exists(destination):
                shutil.rmtree(destination)
            shutil.copytree(source, destination)

    def _read_game_icon_path(self, project_path: str):
        config_path = os.path.join(project_path, "project.config")
        if not os.path.exists(config_path):
            return ""
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            icon_value = str(data.get("game_icon", "")).strip()
            if not icon_value:
                return ""
            if os.path.isabs(icon_value):
                icon_path = os.path.normpath(icon_value)
            else:
                icon_path = os.path.normpath(os.path.join(project_path, icon_value))
            if not os.path.exists(icon_path):
                return ""
            return icon_path
        except Exception:
            return ""

    def _prepare_web_icon(self, icon_path: str, output_path: str):
        if not icon_path:
            return ""
        if importlib.util.find_spec("PIL") is None:
            self.logger.warning(
                "Game icon skipped for web because Pillow is not installed",
                icon_path=icon_path
            )
            return ""
        try:
            from PIL import Image
            converted_icon = os.path.join(output_path, "favicon.png")
            with Image.open(icon_path) as image:
                resized_image = image.resize((32, 32), Image.Resampling.LANCZOS)
                resized_image.save(converted_icon, format="PNG")
            if os.path.exists(converted_icon):
                return converted_icon
        except Exception as error:
            self.logger.warning(
                "Failed to convert game icon for web, using default icon",
                icon_path=icon_path,
                error=str(error)
            )
        return ""

    def _write_platform_template(self, context: BuildContext):
        template = {
            "platform": context.platform,
            "mode": context.build_mode,
            "entrypoint": "core.player"
        }
        template_path = os.path.join(context.output_path, f"{context.platform}_template.json")
        with open(template_path, "w", encoding="utf-8") as file:
            json.dump(template, file, indent=2)
        context.metadata["template_path"] = template_path

    def _finalize(self, context: BuildContext):
        stamp_path = os.path.join(context.output_path, ".build_complete")
        with open(stamp_path, "w", encoding="utf-8") as file:
            file.write("ok")
        context.metadata["build_stamp"] = stamp_path

    def _collect_file_manifest(self, root_path: str):
        manifest = {"project_root": root_path, "files": []}
        for current_root, _, files in os.walk(root_path):
            for filename in sorted(files):
                full_path = os.path.join(current_root, filename)
                rel_path = os.path.relpath(full_path, root_path)
                if rel_path.startswith(".git"):
                    continue
                stat = os.stat(full_path)
                manifest["files"].append(
                    {
                        "path": rel_path.replace("\\", "/"),
                        "size": stat.st_size,
                        "sha256": self._hash_file(full_path)
                    }
                )
        manifest["files"].sort(key=lambda item: item["path"])
        return manifest

    def _hash_file(self, file_path: str):
        digest = hashlib.sha256()
        with open(file_path, "rb") as file:
            while True:
                chunk = file.read(65536)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def _engine_root(self):
        return os.path.abspath(os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))

    def _resolve_module_command(self, module_name: str):
        if not getattr(sys, "frozen", False):
            if importlib.util.find_spec(module_name) is None:
                return None
            return [sys.executable, "-m", module_name]

        candidate_prefixes = self._candidate_python_prefixes()
        probe_env = self._tool_env()
        seen = set()
        for prefix in candidate_prefixes:
            key = tuple(prefix)
            if key in seen:
                continue
            seen.add(key)
            if self._probe_module_on_prefix(prefix, module_name, probe_env):
                return [*prefix, "-m", module_name]
            packages = self._required_packages_for_module(module_name)
            if packages and self._install_host_packages(prefix, packages):
                if self._probe_module_on_prefix(prefix, module_name, probe_env):
                    return [*prefix, "-m", module_name]
        return None

    def _tool_env(self):
        env = os.environ.copy()
        if getattr(sys, "frozen", False):
            env.pop("PYTHONHOME", None)
            env.pop("PYTHONPATH", None)
            env.pop("PYTHONEXECUTABLE", None)
            env.pop("PYTHONNOUSERSITE", None)
            env.pop("PYTHONUSERBASE", None)
        return env

    def _candidate_python_prefixes(self):
        candidate_prefixes: list[list[str]] = []
        host_python = os.environ.get("AXISPY_HOST_PYTHON", "").strip()
        if host_python:
            candidate_prefixes.append([host_python])
        if platform.system() == "Windows":
            candidate_prefixes.append(["py", "-3"])
        python_bin = shutil.which("python")
        if python_bin:
            candidate_prefixes.append([python_bin])
        python3_bin = shutil.which("python3")
        if python3_bin:
            candidate_prefixes.append([python3_bin])
        return candidate_prefixes

    def _probe_module_on_prefix(self, prefix: list[str], module_name: str, env: dict):
        try:
            probe = subprocess.run(
                [*prefix, "-c", f"import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('{module_name}') else 1)"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
                env=env
            )
            return probe.returncode == 0
        except Exception:
            return False

    def _required_packages_for_module(self, module_name: str):
        mapping = {
            "PyInstaller": ["pyinstaller", "pyinstaller-hooks-contrib", "cryptography"],
            "pygbag": ["pygbag"],
            "buildozer": ["buildozer", "cython"],
        }
        return mapping.get(module_name, [])

    def _install_host_packages(self, prefix: list[str], packages: list[str]):
        env = self._tool_env()
        base = [*prefix, "-m", "pip", "install", "--upgrade"]
        user_install = subprocess.run([*base, "--user", *packages], check=False, capture_output=True, text=True, env=env)
        if user_install.returncode == 0:
            return True
        fallback_install = subprocess.run([*base, *packages], check=False, capture_output=True, text=True, env=env)
        return fallback_install.returncode == 0

    def _python_prefix_from_module_command(self, module_cmd: list[str]):
        if "-m" in module_cmd:
            return module_cmd[:module_cmd.index("-m")]
        return module_cmd[:1]

    def _has_cryptography_hook_failure(self, output: str):
        text = str(output or "")
        return "hook-cryptography.py" in text and "NoneType" in text

    def _repair_pyinstaller_cryptography_host(self, pyinstaller_cmd: list[str]):
        prefix = self._python_prefix_from_module_command(pyinstaller_cmd)
        if not prefix:
            return False
        repair_cmd = [
            *prefix,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--force-reinstall",
            "cryptography",
            "pyinstaller-hooks-contrib",
        ]
        repair = subprocess.run(
            repair_cmd,
            check=False,
            capture_output=True,
            text=True,
            env=self._tool_env()
        )
        return repair.returncode == 0


class WebExporter(Exporter):
    platform = "web"

    def _copy_runtime(self, context: BuildContext):
        super()._copy_runtime(context)
        self._copy_project_payload(context)

    def _write_platform_template(self, context: BuildContext):
        super()._write_platform_template(context)
        entry_scene = self._resolve_entry_scene(context)
        launcher_path = os.path.join(context.output_path, "main.py")
        with open(launcher_path, "w", encoding="utf-8") as file:
            file.write("import asyncio\n")
            file.write("import importlib\n")
            file.write("import os\n")
            file.write("import pygame\n")
            file.write("import sys\n")
            file.write("base_dir = os.path.dirname(os.path.abspath(__file__))\n")
            file.write("if base_dir not in sys.path:\n")
            file.write("    sys.path.insert(0, base_dir)\n")
            file.write("if not hasattr(pygame, 'init'):\n")
            file.write("    try:\n")
            file.write("        pygame_alt = importlib.import_module('pygame_ce')\n")
            file.write("        sys.modules['pygame'] = pygame_alt\n")
            file.write("        pygame = pygame_alt\n")
            file.write("    except Exception:\n")
            file.write("        pass\n")
            file.write("project_root = os.path.join(base_dir, 'project')\n")
            file.write("os.environ['AXISPY_PROJECT_PATH'] = project_root\n")
            file.write("from core.player import run\n")
            if entry_scene:
                file.write(f"scene_path = os.path.join(project_root, {repr(entry_scene)})\n")
            else:
                file.write("scene_path = None\n")
            file.write("async def main():\n")
            file.write("    try:\n")
            file.write("        run_result = run(scene_path)\n")
            file.write("        if hasattr(run_result, '__await__'):\n")
            file.write("            await run_result\n")
            file.write("    except SystemExit:\n")
            file.write("        pass\n")
            file.write("    await asyncio.sleep(0)\n")
            file.write("asyncio.run(main())\n")
        context.metadata["web_launcher_path"] = launcher_path
        context.metadata["web_entry_scene"] = entry_scene
        
        # Prepare web favicon
        game_icon = self._read_game_icon_path(context.project_path)
        web_icon = self._prepare_web_icon(game_icon, context.output_path)
        if web_icon:
            context.metadata["web_icon_path"] = web_icon

    def export_with_pygbag(self, project_path: str, output_path: str):
        context = self.export(project_path, output_path)
        pygbag_cmd = self._resolve_module_command("pygbag")
        if pygbag_cmd is None:
            if getattr(sys, "frozen", False):
                raise RuntimeError(
                    "pygbag export from the packaged editor requires an external Python with pygbag.\n"
                    "Install Python + pygbag and ensure 'python -m pygbag --help' works,\n"
                    "or set AXISPY_HOST_PYTHON to that interpreter path."
                )
            raise RuntimeError(
                f"pygbag is not installed for interpreter '{sys.executable}'. "
                "Install it with: pip install pygbag --user --upgrade"
            )

        # Read project config for template generation
        project_config = {}
        config_path = os.path.join(context.project_path, "project.config")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    project_config = json.load(f)
            except Exception:
                pass

        # Copy designer assets (logo, bg image) into export dir if they are local files
        designer = project_config.get("pygbag_designer", {})
        for key in ("logo_url", "background_image_url"):
            asset_path = designer.get(key, "").strip()
            if asset_path and not asset_path.startswith(("http://", "https://", "//")):
                # Resolve relative to project
                if not os.path.isabs(asset_path):
                    asset_path = os.path.join(context.project_path, asset_path)
                if os.path.isfile(asset_path):
                    dest_name = os.path.basename(asset_path)
                    try:
                        shutil.copy2(asset_path, os.path.join(context.output_path, dest_name))
                        designer[key] = dest_name
                        if self.logger:
                            self.logger.info(f"Copied designer asset: {key} -> {dest_name}", src=asset_path, dest=dest_name)
                    except Exception as e:
                        if self.logger:
                            self.logger.error(f"Failed to copy designer asset: {key}", error=str(e), path=asset_path)
                else:
                    if self.logger:
                        self.logger.warning(f"Designer asset file not found: {key}", path=asset_path)
            else:
                if asset_path and self.logger:
                    self.logger.info(f"Using remote URL for {key}: {asset_path}")
            project_config["pygbag_designer"] = designer

        # Build custom template via the registry pipeline
        registry = WebTemplateRegistry.instance()
        # Pass the possibly updated URLs to build_template
        template_html = registry.build_template(project_config, 
                                               logo_url=designer.get("logo_url", ""),
                                               bg_image_url=designer.get("background_image_url", ""))
        tmpl_path = os.path.join(context.output_path, "custom.tmpl")
        with open(tmpl_path, "w", encoding="utf-8") as f:
            f.write(template_html)
        context.metadata["web_template_path"] = tmpl_path

        build_stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        parent_dir = os.path.dirname(context.output_path)
        folder_name = os.path.basename(context.output_path)
        pygbag_args = [*pygbag_cmd, "--build", "--template", tmpl_path, folder_name]
        result = subprocess.run(
            pygbag_args,
            cwd=parent_dir,
            check=False,
            capture_output=True,
            text=True,
            env=self._tool_env()
        )
        combined_output = ""
        if result.stdout:
            combined_output += result.stdout
        if result.stderr:
            if combined_output:
                combined_output += "\n"
            combined_output += result.stderr
        log_path = os.path.join(context.output_path, f"pygbag_build_{build_stamp}.log")
        with open(log_path, "w", encoding="utf-8") as log_file:
            log_file.write(combined_output)
        if result.returncode != 0:
            tail_lines = [line for line in combined_output.splitlines() if line.strip()][-20:]
            tail_text = "\n".join(tail_lines)
            raise RuntimeError(
                "pygbag build failed.\n"
                f"Interpreter: {sys.executable}\n"
                f"Log: {log_path}\n"
                f"Last output lines:\n{tail_text}"
            )
        web_build_path = os.path.join(context.output_path, "build", "web")
        if not os.path.exists(web_build_path):
            web_build_path = os.path.join(context.output_path, "build")
            
        web_icon_path = context.metadata.get("web_icon_path")
        if web_icon_path and os.path.exists(web_icon_path):
            try:
                shutil.copy2(web_icon_path, os.path.join(web_build_path, "favicon.png"))
            except Exception as e:
                self.logger.warning("Failed to copy web favicon", error=str(e))
        
        # Copy designer assets to the final web directory after pygbag build
        for key in ("logo_url", "background_image_url"):
            filename = designer.get(key, "").strip()
            if filename and not filename.startswith(("http://", "https://", "//")):
                src_path = os.path.join(context.output_path, filename)
                if os.path.isfile(src_path):
                    dst_path = os.path.join(web_build_path, filename)
                    try:
                        shutil.copy2(src_path, dst_path)
                        if self.logger:
                            self.logger.info(f"Copied designer asset to final web dir: {key}", dst=dst_path)
                    except Exception as e:
                        if self.logger:
                            self.logger.warning(f"Failed to copy designer asset to final web dir: {key}", error=str(e))
                
        context.metadata["web_dist_path"] = web_build_path
        context.metadata["pygbag_log_path"] = log_path
        return context

    def _copy_project_payload(self, context: BuildContext):
        project_payload = os.path.join(context.output_path, "project")
        if os.path.exists(project_payload):
            shutil.rmtree(project_payload)
        project_root = os.path.abspath(context.project_path)
        output_root = os.path.abspath(context.output_path)

        _WEB_IGNORE_DIRS = {"__pycache__", ".axispy", ".git", ".github"}
        _WEB_IGNORE_NAMES = {"temp_scene", "temp_scene.scn", "temp_scene_runcheck", "temp_scene_runcheck.scn", "build"}
        _WEB_IGNORE_EXTS = {".psd", ".xcf", ".blend", ".blend1", ".aseprite", ".ase"}

        def ignore_names(current_dir: str, names: list[str]):
            ignored = []
            for name in names:
                child_path = os.path.abspath(os.path.join(current_dir, name))
                try:
                    if os.path.commonpath([output_root, child_path]) == child_path:
                        ignored.append(name)
                        continue
                except ValueError:
                    pass
                if name in _WEB_IGNORE_DIRS:
                    ignored.append(name)
                    continue
                if name in _WEB_IGNORE_NAMES:
                    ignored.append(name)
                    continue
                _ext = os.path.splitext(name)[1].lower()
                if _ext in _WEB_IGNORE_EXTS:
                    ignored.append(name)
            return ignored

        shutil.copytree(project_root, project_payload, ignore=ignore_names)

    def _resolve_entry_scene(self, context: BuildContext):
        configured = self._read_entry_scene(context.project_path)
        if configured:
            configured_path = os.path.join(context.project_path, configured)
            if os.path.exists(configured_path):
                return configured.replace("\\", "/")
        for root, _, files in os.walk(context.project_path):
            for filename in sorted(files):
                if filename.lower().endswith(".scn"):
                    scene_full = os.path.join(root, filename)
                    return os.path.relpath(scene_full, context.project_path).replace("\\", "/")
        return ""

    def _read_entry_scene(self, project_path: str):
        config_path = os.path.join(project_path, "project.config")
        if not os.path.exists(config_path):
            return ""
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            entry_scene = str(data.get("entry_scene", "")).strip()
            if not entry_scene:
                return ""
            return os.path.normpath(entry_scene).replace("\\", "/")
        except Exception:
            return ""


HTML5Exporter = WebExporter


class DesktopExporter(Exporter):
    platform = "desktop"

    def __init__(self, build_mode: str = "release", target_os: str = ""):
        self.target_os = target_os.lower() if target_os else platform.system().lower()
        # Normalize common names
        if self.target_os in ("macos", "darwin", "osx", "mac"):
            self.target_os = "macos"
        elif self.target_os in ("win", "windows", "win32"):
            self.target_os = "windows"
        elif self.target_os in ("linux", "linux2"):
            self.target_os = "linux"
        super().__init__(build_mode=build_mode)

    def _build_context(self, project_path: str, output_path: str):
        context = super()._build_context(project_path, output_path)
        # Append target OS subfolder: build/desktop/windows, build/desktop/linux, build/desktop/macos
        context.output_path = os.path.join(context.output_path, self.target_os)
        return context

    def _copy_runtime(self, context: BuildContext):
        super()._copy_runtime(context)
        self._copy_project_payload(context)

    def _write_platform_template(self, context: BuildContext):
        super()._write_platform_template(context)
        entry_scene = self._resolve_entry_scene(context)
        launcher_path = os.path.join(context.output_path, "desktop_launcher.py")
        with open(launcher_path, "w", encoding="utf-8") as file:
            file.write("import os\n")
            file.write("import sys\n")
            file.write("base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))\n")
            file.write("search_paths = [base_dir, os.path.join(base_dir, '_internal')]\n")
            file.write("meipass = getattr(sys, '_MEIPASS', '')\n")
            file.write("if meipass:\n")
            file.write("    search_paths.append(meipass)\n")
            file.write("for candidate in search_paths:\n")
            file.write("    if candidate and os.path.exists(candidate) and candidate not in sys.path:\n")
            file.write("        sys.path.insert(0, candidate)\n")
            file.write("project_root = os.path.join(base_dir, 'project')\n")
            file.write("if not os.path.exists(project_root) and meipass:\n")
            file.write("    project_root = os.path.join(meipass, 'project')\n")
            file.write("os.environ['AXISPY_PROJECT_PATH'] = project_root\n")
            file.write("from core.player import run\n")
            if entry_scene:
                file.write(f"scene_path = os.path.join(project_root, {repr(entry_scene)})\n")
                file.write("run(scene_path)\n")
            else:
                file.write("run(None)\n")
        context.metadata["desktop_launcher_path"] = launcher_path
        context.metadata["desktop_entry_scene"] = entry_scene
        context.metadata["desktop_target_os"] = self.target_os

        # Write convenience run scripts for non-PyInstaller usage
        self._write_run_scripts(context, entry_scene)

    def _write_run_scripts(self, context: BuildContext, entry_scene: str):
        """Generate platform-specific run scripts."""
        # Bash script (Linux/macOS)
        bash_path = os.path.join(context.output_path, "run_game.sh")
        with open(bash_path, "w", encoding="utf-8", newline="\n") as file:
            file.write("#!/bin/bash\n")
            file.write("SCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\n")
            file.write("cd \"$SCRIPT_DIR\"\n")
            file.write("python3 desktop_launcher.py \"$@\"\n")
        context.metadata["desktop_bash_script"] = bash_path

        # Batch script (Windows)
        bat_path = os.path.join(context.output_path, "run_game.bat")
        with open(bat_path, "w", encoding="utf-8") as file:
            file.write("@echo off\n")
            file.write("cd /d \"%~dp0\"\n")
            file.write("python desktop_launcher.py %*\n")
        context.metadata["desktop_bat_script"] = bat_path

    def export_with_pyinstaller(self, project_path: str, output_path: str):
        context = self.export(project_path, output_path)
        pyinstaller_cmd = self._resolve_module_command("PyInstaller")
        if pyinstaller_cmd is None:
            if getattr(sys, "frozen", False):
                raise RuntimeError(
                    "PyInstaller export from the packaged editor requires an external Python with PyInstaller.\n"
                    "Install Python + PyInstaller and ensure 'python -m PyInstaller --version' works,\n"
                    "or set AXISPY_HOST_PYTHON to that interpreter path."
                )
            raise RuntimeError(
                f"PyInstaller is not installed for interpreter '{sys.executable}'. "
                "Install it with: pip install pyinstaller"
            )
        launcher_path = context.metadata.get("desktop_launcher_path")
        if not launcher_path or not os.path.exists(launcher_path):
            raise RuntimeError("Desktop launcher was not generated.")
        build_stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        dist_path = os.path.join(context.output_path, "dist", build_stamp)
        work_path = os.path.join(context.output_path, "build_pyinstaller", build_stamp)
        spec_path = os.path.join(context.output_path, "spec", build_stamp)
        os.makedirs(dist_path, exist_ok=True)
        os.makedirs(work_path, exist_ok=True)
        os.makedirs(spec_path, exist_ok=True)
        game_name = self._read_game_name(context.project_path) or "AxisPyGame"
        game_icon = self._read_game_icon_path(context.project_path)
        pyinstaller_icon = self._prepare_platform_icon(game_icon, context.output_path, build_stamp)
        pyinstaller_args = [
            *pyinstaller_cmd,
            "--noconfirm",
            "--clean",
            "--name",
            game_name,
            "--distpath",
            dist_path,
            "--workpath",
            work_path,
            "--specpath",
            spec_path,
            "--windowed",
            "--paths",
            context.output_path,
            "--paths",
            self._engine_root(),
            "--hidden-import",
            "pygame",
            "--collect-all",
            "pygame"
        ]
        # Platform-specific PyInstaller args
        if self.target_os == "macos":
            bundle_id = f"com.axispy.{game_name.lower()}"
            pyinstaller_args.extend(["--osx-bundle-identifier", bundle_id])
        if pyinstaller_icon:
            pyinstaller_args.extend(["--icon", pyinstaller_icon])
        for data_path in ("project", "core", "plugins"):
            absolute_data_path = os.path.join(context.output_path, data_path)
            if os.path.exists(absolute_data_path):
                pyinstaller_args.extend(["--add-data", f"{absolute_data_path}{os.pathsep}{data_path}"])
        pyinstaller_args.append(launcher_path)
        log_path = os.path.join(context.output_path, f"pyinstaller_build_{build_stamp}.log")
        result = subprocess.run(
            pyinstaller_args,
            cwd=context.output_path,
            check=False,
            capture_output=True,
            text=True,
            env=self._tool_env()
        )
        retried_after_repair = False
        if result.returncode != 0:
            combined_probe = (result.stdout or "") + "\n" + (result.stderr or "")
            if self._has_cryptography_hook_failure(combined_probe):
                if self._repair_pyinstaller_cryptography_host(pyinstaller_cmd):
                    retried_after_repair = True
                    result = subprocess.run(
                        pyinstaller_args,
                        cwd=context.output_path,
                        check=False,
                        capture_output=True,
                        text=True,
                        env=self._tool_env()
                    )
        combined_output = ""
        if result.stdout:
            combined_output += result.stdout
        if result.stderr:
            if combined_output:
                combined_output += "\n"
            combined_output += result.stderr
        with open(log_path, "w", encoding="utf-8") as log_file:
            log_file.write(combined_output)
        if result.returncode != 0:
            tail_lines = [line for line in combined_output.splitlines() if line.strip()][-20:]
            tail_text = "\n".join(tail_lines)
            hint = ""
            if self._has_cryptography_hook_failure(combined_output):
                hint = (
                    "\n\nDetected cryptography hook failure in the external Python environment.\n"
                    "Run on the host Python:\n"
                    "  python -m pip install --upgrade --force-reinstall cryptography pyinstaller-hooks-contrib"
                )
                if retried_after_repair:
                    hint += "\nAutomatic repair was attempted once but the host environment is still failing."
            raise RuntimeError(
                "PyInstaller build failed.\n"
                f"Target OS: {self.target_os}\n"
                f"Interpreter: {sys.executable}\n"
                f"Log: {log_path}\n"
                f"Last output lines:\n{tail_text}{hint}"
            )
        context.metadata["desktop_dist_path"] = dist_path
        context.metadata["desktop_executable_name"] = game_name
        context.metadata["desktop_icon_path"] = game_icon
        context.metadata["desktop_pyinstaller_icon_path"] = pyinstaller_icon
        context.metadata["desktop_target_os"] = self.target_os
        context.metadata["pyinstaller_log_path"] = log_path
        return context

    def _copy_project_payload(self, context: BuildContext):
        project_payload = os.path.join(context.output_path, "project")
        if os.path.exists(project_payload):
            shutil.rmtree(project_payload)
        project_root = os.path.abspath(context.project_path)
        output_root = os.path.abspath(context.output_path)

        def ignore_names(current_dir: str, names: list[str]):
            ignored = []
            for name in names:
                child_path = os.path.abspath(os.path.join(current_dir, name))
                try:
                    if os.path.commonpath([output_root, child_path]) == child_path:
                        ignored.append(name)
                        continue
                except ValueError:
                    pass
                if name == "__pycache__":
                    ignored.append(name)
                if name in {"temp_scene", "temp_scene.scn", "temp_scene_runcheck", "temp_scene_runcheck.scn", "build"}:
                    ignored.append(name)
            return ignored

        shutil.copytree(project_root, project_payload, ignore=ignore_names)
        pruned_count = self._prune_images_if_atlas_ready(project_payload)
        context.metadata["pruned_source_images_count"] = pruned_count

    def _prune_images_if_atlas_ready(self, project_payload: str):
        atlas_manifest = os.path.join(project_payload, "assets", ".atlas", "sprites_atlas.json")
        atlas_image = os.path.join(project_payload, "assets", ".atlas", "sprites_atlas.png")
        images_root = os.path.join(project_payload, "assets", "images")
        if not os.path.exists(atlas_manifest) or not os.path.exists(atlas_image) or not os.path.isdir(images_root):
            return 0
        try:
            with open(atlas_manifest, "r", encoding="utf-8") as file:
                manifest_data = json.load(file)
        except Exception:
            return 0
        source_signature = manifest_data.get("source_signature", {})
        if not isinstance(source_signature, dict):
            return 0
        source_files = self._collect_image_source_files(images_root)
        actual_signature = self._compute_image_signature(project_payload, source_files)
        if source_signature.get("count") != actual_signature.get("count"):
            return 0
        if source_signature.get("hash") != actual_signature.get("hash"):
            return 0
        pruned = 0
        for abs_path in source_files:
            try:
                os.remove(abs_path)
                pruned += 1
            except Exception:
                continue
        return pruned

    def _collect_image_source_files(self, images_root: str):
        valid_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
        files = []
        for root, _, names in os.walk(images_root):
            for name in names:
                if os.path.splitext(name)[1].lower() in valid_exts:
                    files.append(os.path.join(root, name))
        files.sort()
        return files

    def _compute_image_signature(self, project_payload: str, source_files: list[str]):
        hasher = hashlib.sha1()
        normalized_project = os.path.normpath(project_payload)
        for abs_path in source_files:
            normalized_abs = os.path.normpath(abs_path)
            rel_path = os.path.relpath(normalized_abs, normalized_project).replace("\\", "/")
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

    def _resolve_entry_scene(self, context: BuildContext):
        configured = self._read_entry_scene(context.project_path)
        if configured:
            configured_path = os.path.join(context.project_path, configured)
            if os.path.exists(configured_path):
                return configured
        for root, _, files in os.walk(context.project_path):
            for filename in sorted(files):
                if filename.lower().endswith(".scn"):
                    scene_full = os.path.join(root, filename)
                    return os.path.relpath(scene_full, context.project_path)
        return ""

    def _read_entry_scene(self, project_path: str):
        config_path = os.path.join(project_path, "project.config")
        if not os.path.exists(config_path):
            return ""
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            entry_scene = str(data.get("entry_scene", "")).strip()
            if not entry_scene:
                return ""
            return os.path.normpath(entry_scene)
        except Exception:
            return ""

    def _read_game_name(self, project_path: str):
        config_path = os.path.join(project_path, "project.config")
        if not os.path.exists(config_path):
            return ""
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            name = str(data.get("game_name", "")).strip()
            if not name:
                return ""
            sanitized = "".join(ch for ch in name if ch.isalnum() or ch in ("_", "-"))
            return sanitized or ""
        except Exception:
            return ""

    def _prepare_platform_icon(self, icon_path: str, output_path: str, build_stamp: str):
        """Convert game icon to the correct format for the target OS.
        Windows: .ico, macOS: .icns, Linux: .png (PyInstaller accepts .png).
        """
        if not icon_path:
            return ""
        extension = os.path.splitext(icon_path)[1].lower()

        # Windows — needs .ico
        if self.target_os == "windows":
            if extension == ".ico":
                return icon_path
            if importlib.util.find_spec("PIL") is None:
                self.logger.warning("Game icon skipped (Pillow not installed)", icon_path=icon_path)
                return ""
            try:
                from PIL import Image
                converted = os.path.join(output_path, f"icon_{build_stamp}.ico")
                with Image.open(icon_path) as img:
                    img.save(
                        converted,
                        format="ICO",
                        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
                    )
                if os.path.exists(converted):
                    return converted
            except Exception as error:
                self.logger.warning("Failed to convert icon to .ico", icon_path=icon_path, error=str(error))
            return ""

        # macOS — needs .icns
        if self.target_os == "macos":
            if extension == ".icns":
                return icon_path
            if importlib.util.find_spec("PIL") is None:
                self.logger.warning("Game icon skipped (Pillow not installed)", icon_path=icon_path)
                return ""
            try:
                from PIL import Image
                converted = os.path.join(output_path, f"icon_{build_stamp}.icns")
                with Image.open(icon_path) as img:
                    # macOS .icns needs specific sizes; Pillow saves the largest
                    resized = img.resize((1024, 1024), Image.Resampling.LANCZOS)
                    resized.save(converted, format="ICNS")
                if os.path.exists(converted):
                    return converted
            except Exception as error:
                self.logger.warning("Failed to convert icon to .icns", icon_path=icon_path, error=str(error))
            return ""

        # Linux — .png works directly with PyInstaller
        if self.target_os == "linux":
            if extension == ".png":
                return icon_path
            if importlib.util.find_spec("PIL") is None:
                self.logger.warning("Game icon skipped (Pillow not installed)", icon_path=icon_path)
                return ""
            try:
                from PIL import Image
                converted = os.path.join(output_path, f"icon_{build_stamp}.png")
                with Image.open(icon_path) as img:
                    resized = img.resize((256, 256), Image.Resampling.LANCZOS)
                    resized.save(converted, format="PNG")
                if os.path.exists(converted):
                    return converted
            except Exception as error:
                self.logger.warning("Failed to convert icon to .png", icon_path=icon_path, error=str(error))
            return ""

        return ""


class MobileExporter(Exporter):
    platform = "mobile"

    def __init__(self, build_mode: str = "release", output_format: str = "apk"):
        self.output_format = output_format.lower()  # "apk" or "aab"
        super().__init__(build_mode=build_mode)

    def _build_context(self, project_path: str, output_path: str):
        context = super()._build_context(project_path, output_path)
        context.output_path = os.path.join(context.output_path, "android")
        return context

    def _copy_runtime(self, context: BuildContext):
        super()._copy_runtime(context)
        self._copy_project_payload(context)

    def _copy_project_payload(self, context: BuildContext):
        project_payload = os.path.join(context.output_path, "project")
        if os.path.exists(project_payload):
            shutil.rmtree(project_payload)
        project_root = os.path.abspath(context.project_path)
        output_root = os.path.abspath(context.output_path)

        def ignore_names(current_dir: str, names: list[str]):
            ignored = []
            for name in names:
                child_path = os.path.abspath(os.path.join(current_dir, name))
                try:
                    if os.path.commonpath([output_root, child_path]) == child_path:
                        ignored.append(name)
                        continue
                except ValueError:
                    pass
                if name == "__pycache__":
                    ignored.append(name)
                if name in {"build", "temp_scene", "temp_scene.scn", "temp_scene_runcheck", "temp_scene_runcheck.scn"}:
                    ignored.append(name)
            return ignored

        shutil.copytree(project_root, project_payload, ignore=ignore_names)

    def _read_android_config(self, project_path: str) -> dict:
        config_path = os.path.join(project_path, "project.config")
        if not os.path.exists(config_path):
            return {}
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("android", {})
        except Exception:
            return {}

    def _write_platform_template(self, context: BuildContext):
        super()._write_platform_template(context)
        android_cfg = self._read_android_config(context.project_path)
        game_name = self._read_game_name(context.project_path) or "AxisPyGame"
        game_version = self._read_game_version(context.project_path) or "1.0.0"
        entry_scene = self._resolve_entry_scene(context)
        game_icon = self._read_game_icon_path(context.project_path)

        package_name = android_cfg.get("package_name", "com.axispy.mygame")
        version_code = int(android_cfg.get("version_code", 1))
        min_sdk = int(android_cfg.get("min_sdk", 21))
        target_sdk = int(android_cfg.get("target_sdk", 33))
        ndk_api = int(android_cfg.get("ndk_api", 21))
        orientation = android_cfg.get("orientation", "landscape")
        fullscreen = bool(android_cfg.get("fullscreen", True))
        permissions_list = android_cfg.get("permissions", ["INTERNET"])
        if isinstance(permissions_list, list):
            permissions_str = ",".join(permissions_list)
        else:
            permissions_str = "INTERNET"
        python_deps = android_cfg.get("python_dependencies", "").strip()
        sdk_path = android_cfg.get("sdk_path", "")
        ndk_path = android_cfg.get("ndk_path", "")

        # Build requirements (default engine dependencies always included)
        requirements = "python3,kivy,pygame,websockets,pywebview,aiortc"
        if python_deps:
            requirements += "," + python_deps

        # Write mobile launcher (main.py for Buildozer)
        launcher_path = os.path.join(context.output_path, "main.py")
        with open(launcher_path, "w", encoding="utf-8") as f:
            f.write("import os\n")
            f.write("import sys\n")
            f.write("base_dir = os.path.dirname(os.path.abspath(__file__))\n")
            f.write("sys.path.insert(0, base_dir)\n")
            f.write("project_root = os.path.join(base_dir, 'project')\n")
            f.write("os.environ['AXISPY_PROJECT_PATH'] = project_root\n")
            f.write("from core.player import run\n")
            if entry_scene:
                f.write(f"scene_path = os.path.join(project_root, {repr(entry_scene)})\n")
                f.write("run(scene_path)\n")
            else:
                f.write("run(None)\n")
        context.metadata["mobile_launcher_path"] = launcher_path

        # Write buildozer.spec
        spec_path = os.path.join(context.output_path, "buildozer.spec")
        spec_lines = [
            "[app]",
            f"title = {game_name}",
            f"package.name = {package_name.rsplit('.', 1)[-1]}",
            f"package.domain = {'.'.join(package_name.rsplit('.', 1)[:-1]) or 'com.axispy'}",
            "source.dir = .",
            "source.include_exts = py,png,jpg,jpeg,bmp,gif,webp,wav,ogg,mp3,json,scn,cfg,config,txt,ttf,otf,fnt",
            "source.exclude_dirs = build,dist,.buildozer,__pycache__,.git",
            f"version = {game_version}",
            f"requirements = {requirements}",
            f"android.minapi = {min_sdk}",
            f"android.api = {target_sdk}",
            f"android.ndk_api = {ndk_api}",
            f"orientation = {orientation}",
            f"fullscreen = {'1' if fullscreen else '0'}",
            f"android.permissions = {permissions_str}",
            f"android.archs = arm64-v8a,armeabi-v7a",
            f"android.numeric_version = {version_code}",
        ]

        if game_icon:
            # Copy icon into export dir
            icon_dest = os.path.join(context.output_path, "icon.png")
            try:
                if os.path.exists(game_icon):
                    shutil.copy2(game_icon, icon_dest)
                    spec_lines.append(f"icon.filename = icon.png")
            except Exception:
                pass

        if sdk_path:
            spec_lines.append(f"android.sdk_path = {sdk_path}")
        if ndk_path:
            spec_lines.append(f"android.ndk_path = {ndk_path}")

        # Signing configuration
        keystore_path = android_cfg.get("keystore_path", "")
        keystore_alias = android_cfg.get("keystore_alias", "")
        keystore_password = android_cfg.get("keystore_password", "")

        if keystore_path and keystore_alias:
            spec_lines.append(f"android.keystore = {keystore_path}")
            spec_lines.append(f"android.keyalias = {keystore_alias}")
            if keystore_password:
                spec_lines.append(f"android.keystore_password = {keystore_password}")
                spec_lines.append(f"android.keyalias_password = {keystore_password}")

        # AAB support
        if self.output_format == "aab":
            spec_lines.append("android.aab = True")

        spec_lines.append("")  # trailing newline
        spec_lines.append("[buildozer]")
        spec_lines.append("log_level = 2")
        spec_lines.append("warn_on_root = 1")
        spec_lines.append("")

        with open(spec_path, "w", encoding="utf-8") as f:
            f.write("\n".join(spec_lines))

        context.metadata["buildozer_spec"] = spec_path
        context.metadata["mobile_output_format"] = self.output_format
        context.metadata["mobile_package_name"] = package_name
        context.metadata["mobile_entry_scene"] = entry_scene

        # Write build manifest
        manifest = {
            "game_name": game_name,
            "package_name": package_name,
            "version": game_version,
            "version_code": version_code,
            "output_format": self.output_format,
            "min_sdk": min_sdk,
            "target_sdk": target_sdk,
            "orientation": orientation,
            "build_mode": context.build_mode,
            "permissions": permissions_list,
            "has_keystore": bool(keystore_path and keystore_alias)
        }
        manifest_path = os.path.join(context.output_path, "build_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        context.metadata["mobile_manifest_path"] = manifest_path

    def _resolve_entry_scene(self, context: BuildContext):
        configured = self._read_entry_scene(context.project_path)
        if configured:
            configured_path = os.path.join(context.project_path, configured)
            if os.path.exists(configured_path):
                return configured
        for root, _, files in os.walk(context.project_path):
            for filename in sorted(files):
                if filename.lower().endswith(".scn"):
                    scene_full = os.path.join(root, filename)
                    return os.path.relpath(scene_full, context.project_path)
        return ""

    def _read_entry_scene(self, project_path: str):
        config_path = os.path.join(project_path, "project.config")
        if not os.path.exists(config_path):
            return ""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return os.path.normpath(str(data.get("entry_scene", "")).strip()) if data.get("entry_scene") else ""
        except Exception:
            return ""

    def _read_game_name(self, project_path: str):
        config_path = os.path.join(project_path, "project.config")
        if not os.path.exists(config_path):
            return ""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = str(data.get("game_name", "")).strip()
            return name or ""
        except Exception:
            return ""

    def _read_game_version(self, project_path: str):
        config_path = os.path.join(project_path, "project.config")
        if not os.path.exists(config_path):
            return ""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return str(data.get("version", "1.0.0")).strip()
        except Exception:
            return "1.0.0"

    def _read_game_icon_path(self, project_path: str):
        config_path = os.path.join(project_path, "project.config")
        if not os.path.exists(config_path):
            return ""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            icon = str(data.get("game_icon", "")).strip()
            if not icon:
                return ""
            if os.path.isabs(icon):
                return icon
            return os.path.join(project_path, icon)
        except Exception:
            return ""

    def export_with_buildozer(self, project_path: str, output_path: str):
        context = self.export(project_path, output_path)

        build_action = "release" if self.build_mode == "release" else "debug"

        # ── Windows: buildozer cannot run natively, generate WSL script ──
        if platform.system() == "Windows":
            wsl_script_path = os.path.join(context.output_path, "build_with_wsl.sh")
            with open(wsl_script_path, "w", encoding="utf-8", newline="\n") as f:
                f.write("#!/bin/bash\n")
                f.write("# Run this script inside WSL or a Linux machine.\n")
                f.write("# Buildozer does NOT run natively on Windows.\n")
                f.write("#\n")
                f.write("# Prerequisites (run once):\n")
                f.write("#   sudo apt update && sudo apt install -y \\\n")
                f.write("#     build-essential git zip unzip openjdk-17-jdk \\\n")
                f.write("#     autoconf libtool pkg-config zlib1g-dev \\\n")
                f.write("#     libncurses5-dev libncursesw5-dev cmake \\\n")
                f.write("#     libffi-dev libssl-dev python3-pip\n")
                f.write("#   pip3 install --user buildozer cython\n")
                f.write("#\n")
                f.write("set -e\n")
                f.write('SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n')
                f.write('cd "$SCRIPT_DIR"\n')
                f.write(f"buildozer android {build_action}\n")

            context.metadata["mobile_wsl_script"] = wsl_script_path
            context.metadata["mobile_build_action"] = build_action
            context.metadata["mobile_windows_only"] = True

            # Convert Windows path to WSL-style for instructions
            win_path = os.path.abspath(context.output_path)
            # e.g. D:\foo\bar -> /mnt/d/foo/bar
            drive = win_path[0].lower()
            wsl_path = f"/mnt/{drive}/{win_path[3:].replace(os.sep, '/')}"

            raise RuntimeError(
                "Buildozer cannot run on Windows natively.\n\n"
                "The buildozer.spec and project files have been exported successfully.\n"
                "To build the APK/AAB, open WSL (or a Linux machine) and run:\n\n"
                f"  cd \"{wsl_path}\"\n"
                f"  bash build_with_wsl.sh\n\n"
                "Buildozer will automatically download the Android SDK and NDK for you.\n\n"
                "Prerequisites (run once in WSL):\n"
                "  sudo apt update && sudo apt install -y build-essential git zip unzip \\\n"
                "    openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev \\\n"
                "    libncurses5-dev libncursesw5-dev cmake libffi-dev libssl-dev \\\n"
                "    python3-pip\n"
                "  pip3 install --user buildozer cython"
            )

        # ── Linux / macOS: run buildozer directly ──
        buildozer_cmd = self._resolve_module_command("buildozer")
        if buildozer_cmd is None:
            if getattr(sys, "frozen", False):
                raise RuntimeError(
                    "Buildozer export from the packaged editor requires an external Python with buildozer.\n"
                    "Install Python + buildozer and ensure 'python -m buildozer --version' works,\n"
                    "or set AXISPY_HOST_PYTHON to that interpreter path."
                )
            raise RuntimeError(
                "Buildozer is not installed or not found.\n"
                "Install it with: pip install buildozer cython\n"
                "You also need: sudo apt install build-essential git zip unzip "
                "openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev libncurses5-dev "
                "libncursesw5-dev cmake libffi-dev libssl-dev"
            )

        log_path = os.path.join(context.output_path, f"buildozer_{build_action}.log")
        self.logger.info(
            "Starting Buildozer",
            action=build_action,
            format=self.output_format,
            cwd=context.output_path
        )

        result = subprocess.run(
            [*buildozer_cmd, "android", build_action],
            cwd=context.output_path,
            check=False,
            capture_output=True,
            text=True,
            env=self._tool_env()
        )

        combined = ""
        if result.stdout:
            combined += result.stdout
        if result.stderr:
            if combined:
                combined += "\n"
            combined += result.stderr
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(combined)

        if result.returncode != 0:
            tail_lines = [l for l in combined.splitlines() if l.strip()][-20:]
            tail_text = "\n".join(tail_lines)
            raise RuntimeError(
                f"Buildozer {build_action} build failed.\n"
                f"Log: {log_path}\n"
                f"Last output:\n{tail_text}"
            )

        # Locate output artifact
        bin_dir = os.path.join(context.output_path, "bin")
        artifact_path = ""
        if os.path.isdir(bin_dir):
            ext = ".aab" if self.output_format == "aab" else ".apk"
            for fname in sorted(os.listdir(bin_dir), reverse=True):
                if fname.endswith(ext):
                    artifact_path = os.path.join(bin_dir, fname)
                    break
            if not artifact_path:
                for fname in sorted(os.listdir(bin_dir), reverse=True):
                    if fname.endswith(".apk") or fname.endswith(".aab"):
                        artifact_path = os.path.join(bin_dir, fname)
                        break

        context.metadata["buildozer_log_path"] = log_path
        context.metadata["mobile_artifact_path"] = artifact_path
        context.metadata["mobile_build_action"] = build_action
        self.logger.info(
            "Buildozer build complete",
            artifact=artifact_path,
            log=log_path
        )
        return context


class ServerExporter(Exporter):
    platform = "server"

    def __init__(self, build_mode: str = "release", target_os: str = ""):
        self.target_os = target_os.lower() if target_os else platform.system().lower()
        super().__init__(build_mode=build_mode)

    def _build_context(self, project_path: str, output_path: str):
        context = super()._build_context(project_path, output_path)
        # Append target OS subfolder: build/server/windows, build/server/linux
        context.output_path = os.path.join(context.output_path, self.target_os)
        return context

    def _copy_runtime(self, context: BuildContext):
        super()._copy_runtime(context)
        self._copy_project_payload(context)

    def _write_platform_template(self, context: BuildContext):
        super()._write_platform_template(context)
        entry_scene = self._resolve_entry_scene(context)
        tick_rate = self._read_server_tick_rate(context.project_path)

        # Write headless launcher
        launcher_path = os.path.join(context.output_path, "server_launcher.py")
        with open(launcher_path, "w", encoding="utf-8") as file:
            file.write("#!/usr/bin/env python3\n")
            file.write("import os\n")
            file.write("import sys\n")
            file.write("base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))\n")
            file.write("search_paths = [base_dir, os.path.join(base_dir, '_internal')]\n")
            file.write("meipass = getattr(sys, '_MEIPASS', '')\n")
            file.write("if meipass:\n")
            file.write("    search_paths.append(meipass)\n")
            file.write("for candidate in search_paths:\n")
            file.write("    if candidate and os.path.exists(candidate) and candidate not in sys.path:\n")
            file.write("        sys.path.insert(0, candidate)\n")
            file.write("project_root = os.path.join(base_dir, 'project')\n")
            file.write("if not os.path.exists(project_root) and meipass:\n")
            file.write("    project_root = os.path.join(meipass, 'project')\n")
            file.write("os.environ['AXISPY_PROJECT_PATH'] = project_root\n")
            file.write("from core.headless_server import run_headless\n")
            if entry_scene:
                file.write(f"scene_path = os.path.join(project_root, {repr(entry_scene)})\n")
            else:
                file.write("scene_path = None\n")
            file.write(f"tick_rate = {tick_rate}\n")
            file.write("run_headless(scene_path, tick_rate=tick_rate, verbose=True)\n")

        context.metadata["server_launcher_path"] = launcher_path
        context.metadata["server_entry_scene"] = entry_scene
        context.metadata["server_tick_rate"] = tick_rate

        # Write server manifest
        server_manifest_path = os.path.join(context.output_path, "server_manifest.json")
        server_manifest = {
            "platform": context.platform,
            "target_os": self.target_os,
            "mode": context.build_mode,
            "entrypoint": "core.headless_server",
            "launcher": "server_launcher.py",
            "tick_rate": tick_rate,
            "entry_scene": entry_scene,
            "network_profile": "headless"
        }
        with open(server_manifest_path, "w", encoding="utf-8") as file:
            json.dump(server_manifest, file, indent=2)
        context.metadata["server_manifest_path"] = server_manifest_path

        # Write convenience run scripts
        self._write_run_scripts(context)

    def _write_run_scripts(self, context: BuildContext):
        """Generate platform-specific run scripts."""
        # Bash script (Linux/macOS)
        bash_path = os.path.join(context.output_path, "start_server.sh")
        with open(bash_path, "w", encoding="utf-8", newline="\n") as file:
            file.write("#!/bin/bash\n")
            file.write("SCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\n")
            file.write("cd \"$SCRIPT_DIR\"\n")
            file.write("echo \"Starting AxisPy Headless Server...\"\n")
            file.write("python3 server_launcher.py \"$@\"\n")
        context.metadata["server_bash_script"] = bash_path

        # Batch script (Windows)
        bat_path = os.path.join(context.output_path, "start_server.bat")
        with open(bat_path, "w", encoding="utf-8") as file:
            file.write("@echo off\n")
            file.write("cd /d \"%~dp0\"\n")
            file.write("echo Starting AxisPy Headless Server...\n")
            file.write("python server_launcher.py %*\n")
            file.write("pause\n")
        context.metadata["server_bat_script"] = bat_path

    def export_with_pyinstaller(self, project_path: str, output_path: str):
        """Build a standalone headless server executable using PyInstaller."""
        context = self.export(project_path, output_path)
        pyinstaller_cmd = self._resolve_module_command("PyInstaller")
        if pyinstaller_cmd is None:
            if getattr(sys, "frozen", False):
                raise RuntimeError(
                    "PyInstaller export from the packaged editor requires an external Python with PyInstaller.\n"
                    "Install Python + PyInstaller and ensure 'python -m PyInstaller --version' works,\n"
                    "or set AXISPY_HOST_PYTHON to that interpreter path."
                )
            raise RuntimeError(
                f"PyInstaller is not installed for interpreter '{sys.executable}'. "
                "Install it with: pip install pyinstaller"
            )
        launcher_path = context.metadata.get("server_launcher_path")
        if not launcher_path or not os.path.exists(launcher_path):
            raise RuntimeError("Server launcher was not generated.")

        build_stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        dist_path = os.path.join(context.output_path, "dist", build_stamp)
        work_path = os.path.join(context.output_path, "build_pyinstaller", build_stamp)
        spec_path = os.path.join(context.output_path, "spec", build_stamp)
        os.makedirs(dist_path, exist_ok=True)
        os.makedirs(work_path, exist_ok=True)
        os.makedirs(spec_path, exist_ok=True)

        game_name = self._read_game_name(context.project_path) or "AxisPyServer"
        server_name = game_name + "Server"

        pyinstaller_args = [
            *pyinstaller_cmd,
            "--noconfirm",
            "--clean",
            "--name",
            server_name,
            "--distpath",
            dist_path,
            "--workpath",
            work_path,
            "--specpath",
            spec_path,
            "--console",
            "--paths",
            context.output_path,
            "--paths",
            self._engine_root(),
            "--hidden-import",
            "pygame",
            "--collect-all",
            "pygame",
            "--hidden-import",
            "websockets",
        ]
        # Add data paths
        for data_dir in ("project", "core", "plugins"):
            abs_data = os.path.join(context.output_path, data_dir)
            if os.path.exists(abs_data):
                pyinstaller_args.extend(["--add-data", f"{abs_data}{os.pathsep}{data_dir}"])
        pyinstaller_args.append(launcher_path)

        log_path = os.path.join(context.output_path, f"pyinstaller_server_{build_stamp}.log")
        result = subprocess.run(
            pyinstaller_args,
            cwd=context.output_path,
            check=False,
            capture_output=True,
            text=True,
            env=self._tool_env()
        )
        if result.returncode != 0:
            combined_probe = (result.stdout or "") + "\n" + (result.stderr or "")
            if self._has_cryptography_hook_failure(combined_probe):
                if self._repair_pyinstaller_cryptography_host(pyinstaller_cmd):
                    result = subprocess.run(
                        pyinstaller_args,
                        cwd=context.output_path,
                        check=False,
                        capture_output=True,
                        text=True,
                        env=self._tool_env()
                    )
        combined_output = ""
        if result.stdout:
            combined_output += result.stdout
        if result.stderr:
            if combined_output:
                combined_output += "\n"
            combined_output += result.stderr

        if self.logger:
            self.logger.info("PyInstaller build completed", 
                           returncode=result.returncode,
                           output_lines=len(combined_output.splitlines()) if combined_output else 0)

        # Write pygbag output to a log file for debugging
        if combined_output:
            log_name = f"pygbag_build_{build_stamp}.log"
            log_path = os.path.join(context.output_path, log_name)
            with open(log_path, "w", encoding="utf-8") as log_f:
                log_f.write(combined_output)
            context.metadata["pygbag_log_path"] = log_path

        # After pygbag completes, copy assets to the final web directory
        # Pygbag creates a nested structure: build/web/build/web/
        final_web_dir = os.path.join(context.output_path, "build", "web")
        if os.path.exists(final_web_dir):
            for key in ("logo_url", "background_image_url"):
                filename = designer.get(key, "").strip()
                if filename and not filename.startswith(("http://", "https://", "//")):
                    src_path = os.path.join(context.output_path, filename)
                    if os.path.isfile(src_path):
                        dst_path = os.path.join(final_web_dir, filename)
                        try:
                            shutil.copy2(src_path, dst_path)
                            if self.logger:
                                self.logger.info(f"Copied asset to final web dir: {filename}", dst=dst_path)
                        except Exception as e:
                            if self.logger:
                                self.logger.error(f"Failed to copy asset to final web dir: {filename}", error=str(e))
        context.metadata["server_executable_name"] = server_name
        context.metadata["server_pyinstaller_log"] = log_path
        context.metadata["server_target_os"] = self.target_os
        return context

    def _copy_project_payload(self, context: BuildContext):
        project_payload = os.path.join(context.output_path, "project")
        if os.path.exists(project_payload):
            shutil.rmtree(project_payload)
        project_root = os.path.abspath(context.project_path)
        output_root = os.path.abspath(context.output_path)

        def ignore_names(current_dir: str, names: list[str]):
            ignored = []
            for name in names:
                child_path = os.path.abspath(os.path.join(current_dir, name))
                try:
                    if os.path.commonpath([output_root, child_path]) == child_path:
                        ignored.append(name)
                        continue
                except ValueError:
                    pass
                if name == "__pycache__":
                    ignored.append(name)
                if name in {"temp_scene", "temp_scene.scn", "temp_scene_runcheck", "temp_scene_runcheck.scn", "build"}:
                    ignored.append(name)
                # Strip assets not needed on server (images, sounds)
                lower = name.lower()
                if lower.endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp",
                                   ".wav", ".mp3", ".ogg", ".flac")):
                    ignored.append(name)
            return ignored

        shutil.copytree(project_root, project_payload, ignore=ignore_names)
        context.metadata["server_project_payload"] = project_payload

    def _resolve_entry_scene(self, context: BuildContext):
        configured = self._read_entry_scene(context.project_path)
        if configured:
            configured_path = os.path.join(context.project_path, configured)
            if os.path.exists(configured_path):
                return configured
        for root, _, files in os.walk(context.project_path):
            for filename in sorted(files):
                if filename.lower().endswith(".scn"):
                    scene_full = os.path.join(root, filename)
                    return os.path.relpath(scene_full, context.project_path)
        return ""

    def _read_entry_scene(self, project_path: str):
        config_path = os.path.join(project_path, "project.config")
        if not os.path.exists(config_path):
            return ""
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            entry_scene = str(data.get("entry_scene", "")).strip()
            if not entry_scene:
                return ""
            return os.path.normpath(entry_scene)
        except Exception:
            return ""

    def _read_game_name(self, project_path: str):
        config_path = os.path.join(project_path, "project.config")
        if not os.path.exists(config_path):
            return ""
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            name = str(data.get("game_name", "")).strip()
            if not name:
                return ""
            sanitized = "".join(ch for ch in name if ch.isalnum() or ch in ("_", "-"))
            return sanitized or ""
        except Exception:
            return ""

    def _read_server_tick_rate(self, project_path: str):
        config_path = os.path.join(project_path, "project.config")
        if not os.path.exists(config_path):
            return 60.0
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            server_cfg = data.get("server", {})
            if isinstance(server_cfg, dict):
                return max(1.0, float(server_cfg.get("tick_rate", 60.0)))
            return 60.0
        except Exception:
            return 60.0
