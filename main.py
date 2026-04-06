import sys
import os
import importlib
import runpy
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from editor.ui.main_window import MainWindow
from editor.ui.project_hub import ProjectHub
from editor.ui.engine_settings import apply_theme_mode, load_saved_theme_mode
from core.resources import ResourceManager

def _resolve_engine_icon_path():
    root = os.path.dirname(os.path.abspath(__file__))
    assets = os.path.join(root, "editor", "ui", "assets", "images")
    candidates = [
        "icon_256.ico",
        "icon_128.ico",
        "icon_64.ico",
        "icon_48.ico",
        "icon_32.ico",
        "icon_16.ico",
        "icon.ico",
        "icon.png",
    ]
    for name in candidates:
        path = os.path.join(assets, name)
        if os.path.exists(path):
            return path
    return ""


def _dispatch_runtime_module():
    if len(sys.argv) < 3:
        return False
    if sys.argv[1] != "--axispy-module":
        return False
    module_name = str(sys.argv[2]).strip()
    scene_path = sys.argv[3] if len(sys.argv) > 3 else None
    module = importlib.import_module(module_name)
    run_callable = getattr(module, "run", None)
    if callable(run_callable):
        run_callable(scene_path)
        return True
    return False


def _dispatch_dash_m_module():
    if len(sys.argv) < 3:
        return False
    if sys.argv[1] != "-m":
        return False
    module_name = str(sys.argv[2]).strip()
    module_args = sys.argv[3:]
    sys.argv = [module_name, *module_args]
    runpy.run_module(module_name, run_name="__main__", alter_sys=True)
    return True

def main():
    if _dispatch_runtime_module() or _dispatch_dash_m_module():
        return
    app = QApplication(sys.argv)
    engine_icon_path = _resolve_engine_icon_path()
    if engine_icon_path:
        app.setWindowIcon(QIcon(engine_icon_path))
    apply_theme_mode(app, load_saved_theme_mode())

    # Keep reference to windows
    windows = []

    def launch_editor(project_path):
        # Normalize path
        project_path = os.path.normpath(project_path)
        
        # Set environment variable
        os.environ["AXISPY_PROJECT_PATH"] = project_path
        
        # Set resource base path
        ResourceManager.set_base_path(project_path)
        
        main_window = MainWindow()
        if engine_icon_path:
            main_window.setWindowIcon(QIcon(engine_icon_path))
        main_window.project_path = project_path
        main_window.asset_manager_dock.set_project_path(project_path)
        main_window.setWindowTitle(f"AxisPy Engine - {project_path}")
        main_window.load_project_settings()
        main_window.load_last_opened_scene()
        main_window.show()
        windows.append(main_window)
    
    hub = ProjectHub()
    if engine_icon_path:
        hub.setWindowIcon(QIcon(engine_icon_path))
    hub.project_selected.connect(launch_editor)
    hub.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
