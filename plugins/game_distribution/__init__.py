import json
import os
import sys
from PyQt6.QtWidgets import QWidget, QFormLayout, QLineEdit, QCheckBox, QVBoxLayout, QGroupBox, QLabel, QScrollArea
from PyQt6.QtCore import Qt

_manager = None
_ui_hooked = False
_builder_hooked = False

def register_plugin(manager):
    global _manager
    _manager = manager

def on_load(context):
    _inject_project_settings()
    _inject_export_builder()

def on_unload():
    try:
        from export.builder import WebTemplateRegistry
        WebTemplateRegistry.instance().unregister("game_distribution")
    except Exception:
        pass

def on_project_open(project_path: str):
    _refresh_gd_contributions(project_path)

def _inject_project_settings():
    try:
        from editor.ui.project_settings import ProjectSettingsDialog
        
        # Keep original methods
        original_setup_ui = ProjectSettingsDialog.setup_ui
        original_save_config = ProjectSettingsDialog.save_config
        
        def new_setup_ui(self):
            original_setup_ui(self)
            
            # Find or create "Plugins" tab
            plugins_tab_index = -1
            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) == "Plugins":
                    plugins_tab_index = i
                    break
                    
            if plugins_tab_index == -1:
                self.plugins_tab = QWidget()
                self.plugins_layout = QVBoxLayout(self.plugins_tab)
                self.plugins_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setWidget(self.plugins_tab)
                self.tabs.addTab(scroll, "Plugins")
            else:
                scroll_widget = self.tabs.widget(plugins_tab_index)
                if isinstance(scroll_widget, QScrollArea):
                    self.plugins_tab = scroll_widget.widget()
                else:
                    self.plugins_tab = scroll_widget
                self.plugins_layout = self.plugins_tab.layout()
            
            # Collapsible Group for Game Distribution
            group_box = QGroupBox("Game Distribution SDK Settings")
            form = QFormLayout(group_box)
            
            gd_config = self.config_data.get("game_distribution", {})
            
            self.gd_enabled_chk = QCheckBox("Enable Game Distribution SDK")
            self.gd_enabled_chk.setChecked(bool(gd_config.get("enabled", False)))
            form.addRow(self.gd_enabled_chk)
            
            self.gd_game_id_edit = QLineEdit(str(gd_config.get("game_id", "")))
            form.addRow("Game ID:", self.gd_game_id_edit)
            
            self.gd_prefix_edit = QLineEdit(str(gd_config.get("prefix", "")))
            form.addRow("Prefix (optional):", self.gd_prefix_edit)
            
            self.plugins_layout.addWidget(group_box)

            
        def new_save_config(self):
            if hasattr(self, 'gd_enabled_chk'):
                if "game_distribution" not in self.config_data:
                    self.config_data["game_distribution"] = {}
                self.config_data["game_distribution"]["enabled"] = self.gd_enabled_chk.isChecked()
                self.config_data["game_distribution"]["game_id"] = self.gd_game_id_edit.text().strip()
                self.config_data["game_distribution"]["prefix"] = self.gd_prefix_edit.text().strip()
            original_save_config(self)
            
        ProjectSettingsDialog.setup_ui = new_setup_ui
        ProjectSettingsDialog.save_config = new_save_config
        
        global _ui_hooked
        _ui_hooked = True
    except Exception as e:
        if _manager:
            _manager._logger.error("Failed to inject UI", error=str(e))

def _inject_export_builder():
    try:
        from export.builder import WebTemplateRegistry
        
        original_build_template = WebTemplateRegistry.build_template
        
        def new_build_template(self, project_config: dict, logo_url: str = None, bg_image_url: str = None) -> str:
            _refresh_gd_contributions_from_config(project_config)
            return original_build_template(self, project_config, logo_url, bg_image_url)
            
        WebTemplateRegistry.build_template = new_build_template
        
        global _builder_hooked
        _builder_hooked = True
    except Exception as e:
        if _manager:
            _manager._logger.error("Failed to inject Export Builder", error=str(e))

def _refresh_gd_contributions_from_config(data: dict):
    from export.builder import WebTemplateRegistry
    registry = WebTemplateRegistry.instance()
    
    # Remove any previous contributions from this plugin
    registry.unregister("game_distribution")

    gd_config = data.get("game_distribution", {})
    if not gd_config.get("enabled", False):
        return
    game_id = str(gd_config.get("game_id", "")).strip()
    if not game_id:
        return
    prefix = str(gd_config.get("prefix", "")).strip()

    # GD SDK script (injected in <head>)
    gd_head_script = f"""    <script>
        window["GD_OPTIONS"] = {{
            "gameId": "{game_id}",
            "prefix": "{prefix}",
            "onEvent": function(event) {{
                switch (event.name) {{
                    case "SDK_GAME_START":
                        window.gdGamePaused = false;
                        if (typeof window.gdResumeAudio === 'function') window.gdResumeAudio();
                        break;
                    case "SDK_GAME_PAUSE":
                        window.gdGamePaused = true;
                        if (typeof window.gdPauseAudio === 'function') window.gdPauseAudio();
                        break;
                    case "SDK_GDPR_TRACKING":
                        break;
                    case "SDK_GDPR_TARGETING":
                        break;
                    case "SDK_REWARDED_WATCH_COMPLETE":
                        window.gdRewardGranted = true;
                        break;
                }}
            }}
        }};
        (function(d, s, id) {{
            var js, fjs = d.getElementsByTagName(s)[0];
            if (d.getElementById(id)) return;
            js = d.createElement(s);
            js.id = id;
            js.src = 'https://html5.api.gamedistribution.com/main.min.js';
            fjs.parentNode.insertBefore(js, fjs);
        }}(document, 'script', 'gamedistribution-jssdk'));

        window.requestGameAd = function(adType) {{
            if (typeof gdsdk !== 'undefined' && typeof gdsdk.showAd !== 'undefined') {{
                gdsdk.showAd(adType).then(function() {{
                    window.gdGamePaused = false;
                    if (typeof window.gdResumeAudio === 'function') window.gdResumeAudio();
                }}).catch(function() {{
                    window.gdGamePaused = false;
                    if (typeof window.gdResumeAudio === 'function') window.gdResumeAudio();
                }});
                return true;
            }}
            return false;
        }};
    </script>"""

    registry.register("game_distribution", "head_scripts", gd_head_script, priority=200)

def _refresh_gd_contributions(project_path: str = ""):
    if not project_path:
        return
    config_path = os.path.join(project_path, "project.config")
    if not os.path.exists(config_path):
        return
    try:
        import json
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            _refresh_gd_contributions_from_config(data)
    except Exception:
        pass

class GameDistributionAPI:
    @staticmethod
    def show_ad(ad_type="interstitial"):
        import sys
        if sys.platform == "emscripten":
            import platform
            platform.window.requestGameAd(ad_type)
            return True
        return False
        
    @staticmethod
    def is_paused():
        import sys
        if sys.platform == "emscripten":
            import platform
            return bool(getattr(platform.window, "gdGamePaused", False))
        return False

    @staticmethod
    def is_reward_granted():
        import sys
        if sys.platform == "emscripten":
            import platform
            granted = bool(getattr(platform.window, "gdRewardGranted", False))
            if granted:
                platform.window.gdRewardGranted = False
            return granted
        return False
