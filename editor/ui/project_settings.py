import json
import os
import platform
from core.resources import ResourceManager
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QLineEdit, QSpinBox, QFormLayout, QMessageBox, QTabWidget, QWidget, QColorDialog, QComboBox, QCheckBox, QFileDialog, QListWidget, QInputDialog, QTableWidget, QTableWidgetItem, QGroupBox, QTextEdit, QScrollArea, QHeaderView, QAbstractItemView)
from PyQt6.QtGui import QColor, QKeySequence
from PyQt6.QtCore import Qt
import pygame

# Common pygame key names for the key picker dropdown
_PYGAME_KEY_NAMES: dict[int, str] = {}

def _build_key_names():
    """Build a mapping of pygame key code -> human-readable name."""
    global _PYGAME_KEY_NAMES
    if _PYGAME_KEY_NAMES:
        return
    for attr in dir(pygame):
        if attr.startswith("K_"):
            code = getattr(pygame, attr)
            if isinstance(code, int):
                _PYGAME_KEY_NAMES[code] = attr[2:]  # strip K_ prefix

def _key_name(code: int) -> str:
    _build_key_names()
    return _PYGAME_KEY_NAMES.get(code, str(code))

def _key_code_from_name(name: str) -> int | None:
    _build_key_names()
    for code, n in _PYGAME_KEY_NAMES.items():
        if n.lower() == name.lower():
            return code
    try:
        return int(name)
    except ValueError:
        return None

class ProjectSettingsDialog(QDialog):
    def __init__(self, project_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Project Settings")
        self.setMinimumWidth(400)
        self.project_path = project_path
        self.config_path = os.path.join(self.project_path, "project.config") if self.project_path else None
        
        self.config_data = self.load_config()
        
        self.setup_ui()
        
    def load_config(self):
        default_config = {
            "game_name": "New Game",
            "game_icon": "",
            "entry_scene": "",
            "resolution": {
                "width": 800,
                "height": 600
            },
            "display": {
                "window": {
                    "width": 800,
                    "height": 600,
                    "resizable": True,
                    "fullscreen": False
                },
                "virtual_resolution": {
                    "width": 800,
                    "height": 600
                },
                "stretch": {
                    "mode": "fit",
                    "aspect": "keep",
                    "scale": "fractional"
                }
            },
            "background_color": [0, 0, 0],
            "layers": ["Default"],
            "groups": [],
            "physics_collision_matrix": {},
            "version": "1.0.0",
            "input_actions": {},
            "lighting": {
                "shadow_extend": 2000
            },
            "ai": {
                "provider": "openai",
                "api_key": "",
                "model": "gpt-4o-mini",
                "base_url": "https://api.openai.com/v1",
                "local_model": "llama3",
                "local_url": "http://localhost:11434/v1",
                "openrouter_api_key": "",
                "openrouter_model": "deepseek/deepseek-chat:free",
                "openrouter_url": "https://openrouter.ai/api/v1",
                "google_api_key": "",
                "google_model": "gemini-2.5-flash",
                "anthropic_api_key": "",
                "anthropic_model": "claude-3-5-sonnet-latest",
                "temperature": 0.7,
                "max_tokens": 4096
            },
            "android": {
                "sdk_path": "",
                "ndk_path": "",
                "package_name": "com.axispy.mygame",
                "version_code": 1,
                "min_sdk": 21,
                "target_sdk": 33,
                "ndk_api": 21,
                "orientation": "landscape",
                "fullscreen": True,
                "permissions": ["INTERNET"],
                "python_dependencies": "",
                "keystore_path": "",
                "keystore_alias": "",
                "keystore_password": ""
            }
        }
        
        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    loaded_config = json.load(f)
                    self.merge_dicts(default_config, loaded_config)
                    loaded_display = loaded_config.get("display", {})
                    loaded_virtual = loaded_display.get("virtual_resolution", {})
                    loaded_window = loaded_display.get("window", {})
                    legacy_res = loaded_config.get("resolution", {})
                    if "width" in legacy_res and "width" not in loaded_virtual:
                        default_config["display"]["virtual_resolution"]["width"] = int(legacy_res.get("width", 800))
                    if "height" in legacy_res and "height" not in loaded_virtual:
                        default_config["display"]["virtual_resolution"]["height"] = int(legacy_res.get("height", 600))
                    if "width" in legacy_res and "width" not in loaded_window:
                        default_config["display"]["window"]["width"] = int(legacy_res.get("width", 800))
                    if "height" in legacy_res and "height" not in loaded_window:
                        default_config["display"]["window"]["height"] = int(legacy_res.get("height", 600))
            except Exception as e:
                print(f"Failed to load project config: {e}")
                
        return default_config
        
    def merge_dicts(self, default, override):
        for k, v in override.items():
            if k in default and isinstance(default[k], dict) and isinstance(v, dict):
                self.merge_dicts(default[k], v)
            else:
                default[k] = v

    def _make_scrollable(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        return scroll

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        self.setMaximumHeight(700)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # General Tab
        general_tab = QWidget()
        general_layout = QFormLayout(general_tab)
        
        self.game_name_edit = QLineEdit(self.config_data.get("game_name", ""))
        general_layout.addRow("Game Name:", self.game_name_edit)

        icon_layout = QHBoxLayout()
        self.game_icon_edit = QLineEdit(str(self.config_data.get("game_icon", "")))
        self.game_icon_browse_btn = QPushButton("Browse...")
        self.game_icon_browse_btn.clicked.connect(self.choose_game_icon)
        icon_layout.addWidget(self.game_icon_edit)
        icon_layout.addWidget(self.game_icon_browse_btn)
        general_layout.addRow("Game Icon:", icon_layout)
        
        self.version_edit = QLineEdit(self.config_data.get("version", "1.0.0"))
        general_layout.addRow("Version:", self.version_edit)

        entry_scene_layout = QHBoxLayout()
        self.entry_scene_edit = QLineEdit(str(self.config_data.get("entry_scene", "")))
        self.entry_scene_browse_btn = QPushButton("Browse...")
        self.entry_scene_browse_btn.clicked.connect(self.choose_entry_scene)
        entry_scene_layout.addWidget(self.entry_scene_edit)
        entry_scene_layout.addWidget(self.entry_scene_browse_btn)
        general_layout.addRow("Entry Scene:", entry_scene_layout)
        
        self.tabs.addTab(self._make_scrollable(general_tab), "General")
        
        # Display Tab
        display_tab = QWidget()
        display_layout = QFormLayout(display_tab)
        
        display_data = self.config_data.get("display", {})
        window_data = display_data.get("window", {})
        virtual_data = display_data.get("virtual_resolution", self.config_data.get("resolution", {"width": 800, "height": 600}))
        stretch_data = display_data.get("stretch", {})

        self.virtual_width_spin = QSpinBox()
        self.virtual_width_spin.setRange(100, 7680)
        self.virtual_width_spin.setValue(int(virtual_data.get("width", 800)))
        display_layout.addRow("Game Width:", self.virtual_width_spin)

        self.virtual_height_spin = QSpinBox()
        self.virtual_height_spin.setRange(100, 4320)
        self.virtual_height_spin.setValue(int(virtual_data.get("height", 600)))
        display_layout.addRow("Game Height:", self.virtual_height_spin)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(100, 7680)
        self.width_spin.setValue(int(window_data.get("width", self.config_data.get("resolution", {}).get("width", 800))))
        display_layout.addRow("Window Width:", self.width_spin)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(100, 4320)
        self.height_spin.setValue(int(window_data.get("height", self.config_data.get("resolution", {}).get("height", 600))))
        display_layout.addRow("Window Height:", self.height_spin)

        self.resizable_chk = QCheckBox()
        self.resizable_chk.setChecked(bool(window_data.get("resizable", True)))
        display_layout.addRow("Resizable Window:", self.resizable_chk)

        self.fullscreen_chk = QCheckBox()
        self.fullscreen_chk.setChecked(bool(window_data.get("fullscreen", False)))
        display_layout.addRow("Fullscreen:", self.fullscreen_chk)

        self.stretch_mode_combo = QComboBox()
        self.stretch_mode_combo.addItems(["disabled", "stretch", "fit", "crop"])
        self.stretch_mode_combo.setCurrentText(str(stretch_data.get("mode", "fit")))
        display_layout.addRow("Stretch Mode:", self.stretch_mode_combo)

        self.stretch_aspect_combo = QComboBox()
        self.stretch_aspect_combo.addItems(["keep", "ignore"])
        self.stretch_aspect_combo.setCurrentText(str(stretch_data.get("aspect", "keep")))
        display_layout.addRow("Stretch Aspect:", self.stretch_aspect_combo)

        self.stretch_scale_combo = QComboBox()
        self.stretch_scale_combo.addItems(["fractional", "integer"])
        self.stretch_scale_combo.setCurrentText(str(stretch_data.get("scale", "fractional")))
        display_layout.addRow("Stretch Scale:", self.stretch_scale_combo)
        
        # Background Color
        bg_color = self.config_data.get("background_color", [0, 0, 0])
        self.bg_color_btn = QPushButton()
        self.set_color_btn_style(bg_color)
        self.bg_color_btn.clicked.connect(self.choose_bg_color)
        display_layout.addRow("Background Color:", self.bg_color_btn)
        
        self.tabs.addTab(self._make_scrollable(display_tab), "Display")

        # Layers & Groups Tab
        layers_tab = QWidget()
        layers_layout = QVBoxLayout(layers_tab)

        layers_layout.addWidget(QLabel("Layers"))
        self.layers_list = QListWidget()
        self.layers_list.addItems(self._sanitize_layers(self.config_data.get("layers", ["Default"])))
        layers_layout.addWidget(self.layers_list)

        layer_buttons = QHBoxLayout()
        self.layer_add_btn = QPushButton("Add")
        self.layer_remove_btn = QPushButton("Remove")
        self.layer_up_btn = QPushButton("Up")
        self.layer_down_btn = QPushButton("Down")
        layer_buttons.addWidget(self.layer_add_btn)
        layer_buttons.addWidget(self.layer_remove_btn)
        layer_buttons.addWidget(self.layer_up_btn)
        layer_buttons.addWidget(self.layer_down_btn)
        layers_layout.addLayout(layer_buttons)

        self.layer_add_btn.clicked.connect(self.add_layer)
        self.layer_remove_btn.clicked.connect(self.remove_layer)
        self.layer_up_btn.clicked.connect(self.move_layer_up)
        self.layer_down_btn.clicked.connect(self.move_layer_down)

        layers_layout.addWidget(QLabel("Groups"))
        self.groups_list = QListWidget()
        self.groups_list.addItems(self._sanitize_groups(self.config_data.get("groups", [])))
        layers_layout.addWidget(self.groups_list)

        group_buttons = QHBoxLayout()
        self.group_add_btn = QPushButton("Add")
        self.group_remove_btn = QPushButton("Remove")
        self.group_up_btn = QPushButton("Up")
        self.group_down_btn = QPushButton("Down")
        group_buttons.addWidget(self.group_add_btn)
        group_buttons.addWidget(self.group_remove_btn)
        group_buttons.addWidget(self.group_up_btn)
        group_buttons.addWidget(self.group_down_btn)
        layers_layout.addLayout(group_buttons)

        self.group_add_btn.clicked.connect(self.add_group)
        self.group_remove_btn.clicked.connect(self.remove_group)
        self.group_up_btn.clicked.connect(self.move_group_up)
        self.group_down_btn.clicked.connect(self.move_group_down)

        layers_layout.addWidget(QLabel("Physics Collision Matrix"))
        self.collision_matrix_table = QTableWidget()
        self._syncing_matrix_table = False
        self.collision_matrix_table.itemChanged.connect(self.on_collision_matrix_item_changed)
        layers_layout.addWidget(self.collision_matrix_table)
        self._rebuild_collision_matrix_table()

        self.tabs.addTab(self._make_scrollable(layers_tab), "Layers/Groups")

        # Input Actions Tab
        input_tab = QWidget()
        input_layout = QVBoxLayout(input_tab)

        input_layout.addWidget(QLabel("Define named input actions and their key bindings."))

        self.input_actions_table = QTableWidget()
        self.input_actions_table.setColumnCount(2)
        self.input_actions_table.setHorizontalHeaderLabels(["Action Name", "Keys"])
        self.input_actions_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.input_actions_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.input_actions_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.input_actions_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        input_layout.addWidget(self.input_actions_table)

        input_btn_layout = QHBoxLayout()
        self.input_action_add_btn = QPushButton("Add Action")
        self.input_action_add_btn.clicked.connect(self._add_input_action)
        self.input_action_remove_btn = QPushButton("Remove Action")
        self.input_action_remove_btn.clicked.connect(self._remove_input_action)
        self.input_action_add_key_btn = QPushButton("Add Key")
        self.input_action_add_key_btn.clicked.connect(self._add_key_to_action)
        self.input_action_remove_key_btn = QPushButton("Remove Key")
        self.input_action_remove_key_btn.clicked.connect(self._remove_key_from_action)
        input_btn_layout.addWidget(self.input_action_add_btn)
        input_btn_layout.addWidget(self.input_action_remove_btn)
        input_btn_layout.addWidget(self.input_action_add_key_btn)
        input_btn_layout.addWidget(self.input_action_remove_key_btn)
        input_layout.addLayout(input_btn_layout)

        self._populate_input_actions_table()

        self.tabs.addTab(self._make_scrollable(input_tab), "Input Actions")

        # Lighting Tab
        lighting_tab = QWidget()
        lighting_layout = QFormLayout(lighting_tab)

        lighting_data = self.config_data.get("lighting", {})
        self.shadow_extend_spin = QSpinBox()
        self.shadow_extend_spin.setRange(100, 10000)
        self.shadow_extend_spin.setValue(int(lighting_data.get("shadow_extend", 2000)))
        self.shadow_extend_spin.setSingleStep(100)
        lighting_layout.addRow("Shadow Extend:", self.shadow_extend_spin)

        self.tabs.addTab(self._make_scrollable(lighting_tab), "Lighting")

        # AI Tab
        ai_tab = QWidget()
        ai_layout = QVBoxLayout(ai_tab)

        ai_data = self.config_data.get("ai", {})

        provider_group = QGroupBox("AI Provider")
        provider_form = QFormLayout(provider_group)

        self.ai_provider_combo = QComboBox()
        self.ai_provider_combo.addItems(["openai", "openrouter", "local", "gemini", "anthropic", "nvidia"])
        self.ai_provider_combo.setCurrentText(ai_data.get("provider", "openai"))
        self.ai_provider_combo.currentTextChanged.connect(self._on_ai_provider_changed)
        provider_form.addRow("Provider:", self.ai_provider_combo)

        ai_layout.addWidget(provider_group)

        # OpenAI settings group
        self.ai_openai_group = QGroupBox("OpenAI Settings")
        openai_form = QFormLayout(self.ai_openai_group)

        self.ai_api_key_edit = QLineEdit(ai_data.get("api_key", ""))
        self.ai_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.ai_api_key_edit.setPlaceholderText("sk-...")
        openai_form.addRow("API Key:", self.ai_api_key_edit)

        self.ai_model_edit = QLineEdit(ai_data.get("model", "gpt-4o-mini"))
        self.ai_model_edit.setPlaceholderText("gpt-4o-mini, gpt-4o, gpt-4-turbo, etc.")
        openai_form.addRow("Model:", self.ai_model_edit)

        self.ai_base_url_edit = QLineEdit(ai_data.get("base_url", "https://api.openai.com/v1"))
        self.ai_base_url_edit.setPlaceholderText("https://api.openai.com/v1")
        openai_form.addRow("Base URL:", self.ai_base_url_edit)

        self._fetch_openai_btn = QPushButton("Browse Models...")
        self._fetch_openai_btn.setToolTip("Fetch available models from OpenAI API")
        self._fetch_openai_btn.clicked.connect(self._on_fetch_openai_models)
        openai_form.addRow("", self._fetch_openai_btn)

        ai_layout.addWidget(self.ai_openai_group)

        # Local LLM settings group
        self.ai_local_group = QGroupBox("Local LLM Settings")
        local_form = QFormLayout(self.ai_local_group)

        self.ai_local_model_edit = QLineEdit(ai_data.get("local_model", "llama3"))
        self.ai_local_model_edit.setPlaceholderText("llama3, mistral, codellama, etc.")
        local_form.addRow("Model:", self.ai_local_model_edit)

        self.ai_local_url_edit = QLineEdit(ai_data.get("local_url", "http://localhost:11434/v1"))
        self.ai_local_url_edit.setPlaceholderText("http://localhost:11434/v1")
        local_form.addRow("Server URL:", self.ai_local_url_edit)

        ai_layout.addWidget(self.ai_local_group)

        # OpenRouter settings group (300+ models including DeepSeek, Claude, GPT, etc.)
        self.ai_openrouter_group = QGroupBox("OpenRouter Settings (300+ models, free tier)")
        openrouter_form = QFormLayout(self.ai_openrouter_group)

        self.ai_openrouter_key_edit = QLineEdit(ai_data.get("openrouter_api_key", ""))
        self.ai_openrouter_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.ai_openrouter_key_edit.setPlaceholderText("sk-or-...")
        openrouter_form.addRow("API Key:", self.ai_openrouter_key_edit)

        self.ai_openrouter_model_edit = QLineEdit(ai_data.get("openrouter_model", "deepseek/deepseek-chat:free"))
        self.ai_openrouter_model_edit.setPlaceholderText("deepseek/deepseek-chat:free, openrouter/auto, anthropic/claude-3.5-sonnet, etc.")
        openrouter_form.addRow("Model:", self.ai_openrouter_model_edit)

        self.ai_openrouter_url_edit = QLineEdit(ai_data.get("openrouter_url", "https://openrouter.ai/api/v1"))
        self.ai_openrouter_url_edit.setPlaceholderText("https://openrouter.ai/api/v1")
        openrouter_form.addRow("Base URL:", self.ai_openrouter_url_edit)

        # Fetch models button
        self._fetch_models_btn = QPushButton("Browse Free Models...")
        self._fetch_models_btn.setToolTip("Fetch available free models from OpenRouter")
        self._fetch_models_btn.clicked.connect(self._on_fetch_openrouter_models)
        openrouter_form.addRow("", self._fetch_models_btn)

        ai_layout.addWidget(self.ai_openrouter_group)

        # Google settings group
        self.ai_google_group = QGroupBox("Google Settings")
        google_form = QFormLayout(self.ai_google_group)

        self.ai_google_key_edit = QLineEdit(ai_data.get("google_api_key", ""))
        self.ai_google_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.ai_google_key_edit.setPlaceholderText("AIza...")
        google_form.addRow("API Key:", self.ai_google_key_edit)

        self.ai_google_model_edit = QLineEdit(ai_data.get("google_model", "gemini-2.5-flash"))
        self.ai_google_model_edit.setPlaceholderText("gemini-2.5-flash, gemini-2.0-flash, etc.")
        google_form.addRow("Model:", self.ai_google_model_edit)

        # Fetch models button
        self._fetch_google_btn = QPushButton("Browse Models...")
        self._fetch_google_btn.setToolTip("Fetch available models from Google API")
        self._fetch_google_btn.clicked.connect(self._on_fetch_google_models)
        google_form.addRow("", self._fetch_google_btn)

        ai_layout.addWidget(self.ai_google_group)

        # Anthropic settings group
        self.ai_anthropic_group = QGroupBox("Anthropic Settings")
        anthropic_form = QFormLayout(self.ai_anthropic_group)

        self.ai_anthropic_key_edit = QLineEdit(ai_data.get("anthropic_api_key", ""))
        self.ai_anthropic_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.ai_anthropic_key_edit.setPlaceholderText("sk-ant-...")
        anthropic_form.addRow("API Key:", self.ai_anthropic_key_edit)

        self.ai_anthropic_model_edit = QLineEdit(ai_data.get("anthropic_model", "claude-3-5-sonnet-latest"))
        self.ai_anthropic_model_edit.setPlaceholderText("claude-3-5-sonnet-latest, claude-3-opus-latest, etc.")
        anthropic_form.addRow("Model:", self.ai_anthropic_model_edit)

        self._fetch_anthropic_btn = QPushButton("Browse Models...")
        self._fetch_anthropic_btn.setToolTip("Fetch available models from Anthropic API")
        self._fetch_anthropic_btn.clicked.connect(self._on_fetch_anthropic_models)
        anthropic_form.addRow("", self._fetch_anthropic_btn)

        ai_layout.addWidget(self.ai_anthropic_group)

        # NVIDIA settings group
        self.ai_nvidia_group = QGroupBox("NVIDIA Settings (Free tier via build.nvidia.com)")
        nvidia_form = QFormLayout(self.ai_nvidia_group)

        self.ai_nvidia_key_edit = QLineEdit(ai_data.get("nvidia_api_key", ""))
        self.ai_nvidia_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.ai_nvidia_key_edit.setPlaceholderText("nvapi-...")
        nvidia_form.addRow("API Key:", self.ai_nvidia_key_edit)

        self.ai_nvidia_model_edit = QLineEdit(ai_data.get("nvidia_model", "google/gemma-4-31b-it"))
        self.ai_nvidia_model_edit.setPlaceholderText("google/gemma-4-31b-it, meta/llama-3.3-70b-instruct, etc.")
        nvidia_form.addRow("Model:", self.ai_nvidia_model_edit)

        self.ai_nvidia_url_edit = QLineEdit(ai_data.get("nvidia_url", "https://integrate.api.nvidia.com/v1"))
        self.ai_nvidia_url_edit.setPlaceholderText("https://integrate.api.nvidia.com/v1")
        nvidia_form.addRow("Base URL:", self.ai_nvidia_url_edit)

        ai_layout.addWidget(self.ai_nvidia_group)

        # Common AI settings
        common_group = QGroupBox("Generation Settings")
        common_form = QFormLayout(common_group)

        self.ai_temperature_spin = QSpinBox()
        self.ai_temperature_spin.setRange(0, 20)
        self.ai_temperature_spin.setValue(int(ai_data.get("temperature", 0.7) * 10))
        self.ai_temperature_spin.setSuffix(" (x0.1)")
        common_form.addRow("Temperature:", self.ai_temperature_spin)

        self.ai_max_tokens_spin = QSpinBox()
        self.ai_max_tokens_spin.setRange(256, 32768)
        self.ai_max_tokens_spin.setValue(int(ai_data.get("max_tokens", 4096)))
        self.ai_max_tokens_spin.setSingleStep(256)
        common_form.addRow("Max Tokens:", self.ai_max_tokens_spin)

        ai_layout.addWidget(common_group)
        ai_layout.addStretch()

        self.tabs.addTab(self._make_scrollable(ai_tab), "AI")
        self._on_ai_provider_changed(self.ai_provider_combo.currentText())

        # Android Tab
        android_tab = QWidget()
        android_layout = QVBoxLayout(android_tab)

        android_data = self.config_data.get("android", {})

        # SDK / NDK paths group
        sdk_group = QGroupBox("Android SDK && NDK")
        sdk_form = QFormLayout(sdk_group)

        sdk_row = QHBoxLayout()
        self.android_sdk_edit = QLineEdit(android_data.get("sdk_path", ""))
        self.android_sdk_edit.setPlaceholderText("Auto-detected or browse...")
        self.android_sdk_browse_btn = QPushButton("Browse...")
        self.android_sdk_browse_btn.clicked.connect(self._browse_android_sdk)
        self.android_sdk_detect_btn = QPushButton("Auto-Detect")
        self.android_sdk_detect_btn.clicked.connect(self._auto_detect_sdk)
        sdk_row.addWidget(self.android_sdk_edit, 1)
        sdk_row.addWidget(self.android_sdk_browse_btn)
        sdk_row.addWidget(self.android_sdk_detect_btn)
        sdk_form.addRow("SDK Path:", sdk_row)

        ndk_row = QHBoxLayout()
        self.android_ndk_edit = QLineEdit(android_data.get("ndk_path", ""))
        self.android_ndk_edit.setPlaceholderText("Auto-detected or browse...")
        self.android_ndk_browse_btn = QPushButton("Browse...")
        self.android_ndk_browse_btn.clicked.connect(self._browse_android_ndk)
        ndk_row.addWidget(self.android_ndk_edit, 1)
        ndk_row.addWidget(self.android_ndk_browse_btn)
        sdk_form.addRow("NDK Path:", ndk_row)

        self.android_sdk_status = QLabel("")
        self.android_sdk_status.setWordWrap(True)
        sdk_form.addRow("Status:", self.android_sdk_status)

        # On Windows, lock SDK/NDK fields — buildozer handles them in WSL
        if platform.system() == "Windows":
            self.android_sdk_edit.clear()
            self.android_sdk_edit.setPlaceholderText("Not needed on Windows (Buildozer downloads SDK in WSL)")
            self.android_sdk_edit.setEnabled(False)
            self.android_sdk_browse_btn.setEnabled(False)
            self.android_sdk_detect_btn.setEnabled(False)
            self.android_ndk_edit.clear()
            self.android_ndk_edit.setPlaceholderText("Not needed on Windows (Buildozer downloads NDK in WSL)")
            self.android_ndk_edit.setEnabled(False)
            self.android_ndk_browse_btn.setEnabled(False)
            self.android_sdk_status.setText("Buildozer will automatically download SDK/NDK when you build inside WSL or Linux.")
            self.android_sdk_status.setStyleSheet("color: #888;")

        android_layout.addWidget(sdk_group)

        # App identity group
        identity_group = QGroupBox("App Identity")
        identity_form = QFormLayout(identity_group)

        self.android_package_edit = QLineEdit(android_data.get("package_name", "com.axispy.mygame"))
        self.android_package_edit.setPlaceholderText("com.company.gamename")
        identity_form.addRow("Package Name:", self.android_package_edit)

        self.android_version_code_spin = QSpinBox()
        self.android_version_code_spin.setRange(1, 2147483647)
        self.android_version_code_spin.setValue(int(android_data.get("version_code", 1)))
        identity_form.addRow("Version Code:", self.android_version_code_spin)

        self.android_orientation_combo = QComboBox()
        self.android_orientation_combo.addItems(["landscape", "portrait", "sensor", "user"])
        self.android_orientation_combo.setCurrentText(android_data.get("orientation", "landscape"))
        identity_form.addRow("Orientation:", self.android_orientation_combo)

        self.android_fullscreen_chk = QCheckBox()
        self.android_fullscreen_chk.setChecked(bool(android_data.get("fullscreen", True)))
        identity_form.addRow("Fullscreen:", self.android_fullscreen_chk)

        android_layout.addWidget(identity_group)

        # SDK versions group
        versions_group = QGroupBox("SDK Versions")
        versions_form = QFormLayout(versions_group)

        self.android_min_sdk_spin = QSpinBox()
        self.android_min_sdk_spin.setRange(16, 35)
        self.android_min_sdk_spin.setValue(int(android_data.get("min_sdk", 21)))
        versions_form.addRow("Min SDK (API Level):", self.android_min_sdk_spin)

        self.android_target_sdk_spin = QSpinBox()
        self.android_target_sdk_spin.setRange(21, 35)
        self.android_target_sdk_spin.setValue(int(android_data.get("target_sdk", 33)))
        versions_form.addRow("Target SDK (API Level):", self.android_target_sdk_spin)

        self.android_ndk_api_spin = QSpinBox()
        self.android_ndk_api_spin.setRange(16, 35)
        self.android_ndk_api_spin.setValue(int(android_data.get("ndk_api", 21)))
        versions_form.addRow("NDK API Level:", self.android_ndk_api_spin)

        android_layout.addWidget(versions_group)

        # Permissions group
        permissions_group = QGroupBox("Permissions")
        permissions_layout = QVBoxLayout(permissions_group)

        self.android_permissions_list = QListWidget()
        permissions = android_data.get("permissions", ["INTERNET"])
        if isinstance(permissions, list):
            self.android_permissions_list.addItems(permissions)
        permissions_layout.addWidget(self.android_permissions_list)

        perm_buttons = QHBoxLayout()
        self.android_perm_add_btn = QPushButton("Add")
        self.android_perm_add_btn.clicked.connect(self._add_android_permission)
        self.android_perm_remove_btn = QPushButton("Remove")
        self.android_perm_remove_btn.clicked.connect(self._remove_android_permission)
        perm_buttons.addWidget(self.android_perm_add_btn)
        perm_buttons.addWidget(self.android_perm_remove_btn)
        permissions_layout.addLayout(perm_buttons)

        android_layout.addWidget(permissions_group)

        # Signing group
        signing_group = QGroupBox("Signing (Release)")
        signing_form = QFormLayout(signing_group)

        ks_row = QHBoxLayout()
        self.android_keystore_edit = QLineEdit(android_data.get("keystore_path", ""))
        self.android_keystore_edit.setPlaceholderText("Path to .keystore or .jks file")
        self.android_keystore_browse_btn = QPushButton("Browse...")
        self.android_keystore_browse_btn.clicked.connect(self._browse_keystore)
        ks_row.addWidget(self.android_keystore_edit, 1)
        ks_row.addWidget(self.android_keystore_browse_btn)
        signing_form.addRow("Keystore Path:", ks_row)

        self.android_keystore_alias_edit = QLineEdit(android_data.get("keystore_alias", ""))
        self.android_keystore_alias_edit.setPlaceholderText("Key alias")
        signing_form.addRow("Key Alias:", self.android_keystore_alias_edit)

        self.android_keystore_password_edit = QLineEdit(android_data.get("keystore_password", ""))
        self.android_keystore_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.android_keystore_password_edit.setPlaceholderText("Keystore password")
        signing_form.addRow("Password:", self.android_keystore_password_edit)

        android_layout.addWidget(signing_group)

        # Python dependencies group
        deps_group = QGroupBox("Python Dependencies")
        deps_layout = QVBoxLayout(deps_group)

        deps_label = QLabel("Additional pip packages (comma-separated). The following are already included by default: pygame, websockets, pywebview, aiortc")
        deps_label.setWordWrap(True)
        deps_layout.addWidget(deps_label)

        self.android_python_deps_edit = QTextEdit()
        self.android_python_deps_edit.setMaximumHeight(60)
        self.android_python_deps_edit.setPlainText(android_data.get("python_dependencies", ""))
        deps_layout.addWidget(self.android_python_deps_edit)

        android_layout.addWidget(deps_group)
        android_layout.addStretch()

        self.tabs.addTab(self._make_scrollable(android_tab), "Android")

        # Auto-detect SDK on first load if not set (skip on Windows — buildozer handles it)
        if platform.system() != "Windows":
            if not self.android_sdk_edit.text().strip():
                self._auto_detect_sdk(silent=True)
            else:
                self._validate_sdk_path(self.android_sdk_edit.text().strip())

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_config)
        btn_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        main_layout.addLayout(btn_layout)

    def _sanitize_layers(self, layers):
        sanitized = []
        seen = set()
        if isinstance(layers, list):
            for layer in layers:
                name = str(layer).strip()
                if not name:
                    continue
                lowered = name.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                sanitized.append(name)
        if "default" in seen:
            sanitized = [layer for layer in sanitized if layer.lower() != "default"]
        sanitized.insert(0, "Default")
        return sanitized

    def _collect_layers_from_ui(self):
        layers = [self.layers_list.item(i).text() for i in range(self.layers_list.count())]
        return self._sanitize_layers(layers)

    def _sanitize_groups(self, groups):
        sanitized = []
        seen = set()
        if isinstance(groups, list):
            for group in groups:
                name = str(group).strip()
                if not name:
                    continue
                lowered = name.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                sanitized.append(name)
        return sanitized

    def _collect_groups_from_ui(self):
        groups = [self.groups_list.item(i).text() for i in range(self.groups_list.count())]
        return self._sanitize_groups(groups)

    def _sanitize_collision_matrix(self, groups, matrix_data):
        group_list = self._sanitize_groups(groups)
        normalized = {}
        source = matrix_data if isinstance(matrix_data, dict) else {}
        for row_group in group_list:
            raw_targets = source.get(row_group, group_list)
            if not isinstance(raw_targets, list):
                raw_targets = group_list
            allowed = []
            allowed_seen = set()
            for target in raw_targets:
                target_name = str(target).strip()
                if target_name not in group_list:
                    continue
                lowered = target_name.lower()
                if lowered in allowed_seen:
                    continue
                allowed_seen.add(lowered)
                allowed.append(target_name)
            normalized[row_group] = allowed
        for row_group in group_list:
            for target in list(normalized.get(row_group, [])):
                peer = normalized.setdefault(target, [])
                if row_group not in peer:
                    peer.append(row_group)
        return normalized

    def _collect_collision_matrix_from_ui(self):
        groups = self._collect_groups_from_ui()
        table = self.collision_matrix_table
        matrix = {group: [] for group in groups}
        if table.rowCount() != len(groups) or table.columnCount() != len(groups):
            return self._sanitize_collision_matrix(groups, matrix)
        for row_index, row_group in enumerate(groups):
            for col_index, col_group in enumerate(groups):
                item = table.item(row_index, col_index)
                if item and item.checkState() == Qt.CheckState.Checked:
                    matrix[row_group].append(col_group)
        return self._sanitize_collision_matrix(groups, matrix)

    def _rebuild_collision_matrix_table(self):
        groups = self._collect_groups_from_ui()
        current_matrix = self.config_data.get("physics_collision_matrix", {})
        if hasattr(self, "collision_matrix_table") and self.collision_matrix_table.rowCount() > 0:
            current_matrix = self._collect_collision_matrix_from_ui()
        sanitized = self._sanitize_collision_matrix(groups, current_matrix)
        self.config_data["physics_collision_matrix"] = sanitized
        table = self.collision_matrix_table
        self._syncing_matrix_table = True
        table.blockSignals(True)
        table.clear()
        table.setRowCount(len(groups))
        table.setColumnCount(len(groups))
        table.setHorizontalHeaderLabels(groups)
        table.setVerticalHeaderLabels(groups)
        for row_index, row_group in enumerate(groups):
            allowed = set(sanitized.get(row_group, []))
            for col_index, col_group in enumerate(groups):
                item = QTableWidgetItem("")
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled |
                    Qt.ItemFlag.ItemIsSelectable |
                    Qt.ItemFlag.ItemIsUserCheckable
                )
                item.setCheckState(Qt.CheckState.Checked if col_group in allowed else Qt.CheckState.Unchecked)
                table.setItem(row_index, col_index, item)
        table.blockSignals(False)
        self._syncing_matrix_table = False

    def on_collision_matrix_item_changed(self, item):
        if self._syncing_matrix_table:
            return
        row = item.row()
        col = item.column()
        mirror = self.collision_matrix_table.item(col, row)
        if mirror is None:
            return
        self._syncing_matrix_table = True
        mirror.setCheckState(item.checkState())
        self._syncing_matrix_table = False

    def _sync_layers_ui(self):
        current = self.layers_list.currentItem().text() if self.layers_list.currentItem() else ""
        layers = self._collect_layers_from_ui()
        self.layers_list.clear()
        self.layers_list.addItems(layers)
        if current:
            matching = self.layers_list.findItems(current, Qt.MatchFlag.MatchExactly)
            if matching:
                self.layers_list.setCurrentItem(matching[0])

    def add_layer(self):
        name, ok = QInputDialog.getText(self, "Add Layer", "Layer Name:")
        if not ok:
            return
        name = str(name).strip()
        if not name:
            return
        existing = {self.layers_list.item(i).text().lower() for i in range(self.layers_list.count())}
        if name.lower() in existing:
            QMessageBox.warning(self, "Error", "Layer already exists")
            return
        self.layers_list.addItem(name)

    def remove_layer(self):
        item = self.layers_list.currentItem()
        if not item:
            return
        if item.text() == "Default":
            QMessageBox.warning(self, "Error", "Default layer cannot be removed")
            return
        self.layers_list.takeItem(self.layers_list.row(item))

    def move_layer_up(self):
        row = self.layers_list.currentRow()
        if row <= 0:
            return
        item = self.layers_list.item(row)
        if item.text() == "Default":
            QMessageBox.warning(self, "Error", "Default layer cannot be reordered")
            return
        prev_item = self.layers_list.item(row - 1)
        if prev_item and prev_item.text() == "Default":
            QMessageBox.warning(self, "Error", "Default layer cannot be reordered")
            return
        moving = self.layers_list.takeItem(row)
        self.layers_list.insertItem(row - 1, moving)
        self.layers_list.setCurrentRow(row - 1)

    def move_layer_down(self):
        row = self.layers_list.currentRow()
        if row < 0 or row >= self.layers_list.count() - 1:
            return
        item = self.layers_list.item(row)
        if item.text() == "Default":
            QMessageBox.warning(self, "Error", "Default layer cannot be reordered")
            return
        next_item = self.layers_list.item(row + 1)
        if next_item and next_item.text() == "Default":
            QMessageBox.warning(self, "Error", "Default layer cannot be reordered")
            return
        moving = self.layers_list.takeItem(row)
        self.layers_list.insertItem(row + 1, moving)
        self.layers_list.setCurrentRow(row + 1)

    def add_group(self):
        name, ok = QInputDialog.getText(self, "Add Group", "Group Name:")
        if not ok:
            return
        name = str(name).strip()
        if not name:
            return
        existing = {self.groups_list.item(i).text().lower() for i in range(self.groups_list.count())}
        if name.lower() in existing:
            QMessageBox.warning(self, "Error", "Group already exists")
            return
        self.groups_list.addItem(name)
        self._rebuild_collision_matrix_table()

    def remove_group(self):
        item = self.groups_list.currentItem()
        if not item:
            return
        self.groups_list.takeItem(self.groups_list.row(item))
        self._rebuild_collision_matrix_table()

    def move_group_up(self):
        row = self.groups_list.currentRow()
        if row <= 0:
            return
        moving = self.groups_list.takeItem(row)
        self.groups_list.insertItem(row - 1, moving)
        self.groups_list.setCurrentRow(row - 1)
        self._rebuild_collision_matrix_table()

    def move_group_down(self):
        row = self.groups_list.currentRow()
        if row < 0 or row >= self.groups_list.count() - 1:
            return
        moving = self.groups_list.takeItem(row)
        self.groups_list.insertItem(row + 1, moving)
        self.groups_list.setCurrentRow(row + 1)
        self._rebuild_collision_matrix_table()

    def set_color_btn_style(self, color_list):
        r, g, b = color_list
        self.bg_color_btn.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); border: 1px solid #555;")
        self.bg_color_btn.setText(f"RGB({r}, {g}, {b})")
        # Store current color in property for easy access
        self.bg_color_btn.setProperty("current_color", color_list)

    def choose_bg_color(self):
        current = self.bg_color_btn.property("current_color")
        color = QColorDialog.getColor(QColor(*current), self, "Select Background Color")
        if color.isValid():
            new_color = [color.red(), color.green(), color.blue()]
            self.set_color_btn_style(new_color)

    def choose_game_icon(self):
        start_dir = self.project_path if self.project_path else os.getcwd()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Game Icon",
            start_dir,
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.ico)"
        )
        if not file_path:
            return
        normalized = os.path.normpath(file_path)
        if self.project_path:
            abs_project = os.path.abspath(self.project_path)
            abs_file = os.path.abspath(normalized)
            try:
                rel = os.path.relpath(abs_file, abs_project)
                if not rel.startswith(".."):
                    normalized = rel
            except ValueError:
                pass
        self.game_icon_edit.setText(ResourceManager.portable_path(normalized))

    def choose_entry_scene(self):
        start_dir = self.project_path if self.project_path else os.getcwd()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Entry Scene",
            start_dir,
            "Scene Files (*.scn)"
        )
        if not file_path:
            return
        normalized = os.path.normpath(file_path)
        if self.project_path:
            abs_project = os.path.abspath(self.project_path)
            abs_file = os.path.abspath(normalized)
            try:
                rel = os.path.relpath(abs_file, abs_project)
                if not rel.startswith(".."):
                    normalized = rel
            except ValueError:
                pass
        self.entry_scene_edit.setText(ResourceManager.portable_path(normalized))
        
    def save_config(self):
        if not self.config_path:
            QMessageBox.warning(self, "Warning", "No project path available to save settings.")
            return
            
        # Update config data from UI
        self.config_data["game_name"] = self.game_name_edit.text()
        self.config_data["game_icon"] = self.game_icon_edit.text().strip()
        self.config_data["version"] = self.version_edit.text()
        self.config_data["entry_scene"] = self.entry_scene_edit.text().strip()
        self.config_data["resolution"]["width"] = self.virtual_width_spin.value()
        self.config_data["resolution"]["height"] = self.virtual_height_spin.value()
        if "display" not in self.config_data:
            self.config_data["display"] = {}
        self.config_data["display"]["window"] = {
            "width": self.width_spin.value(),
            "height": self.height_spin.value(),
            "resizable": self.resizable_chk.isChecked(),
            "fullscreen": self.fullscreen_chk.isChecked()
        }
        self.config_data["display"]["virtual_resolution"] = {
            "width": self.virtual_width_spin.value(),
            "height": self.virtual_height_spin.value()
        }
        self.config_data["display"]["stretch"] = {
            "mode": self.stretch_mode_combo.currentText(),
            "aspect": self.stretch_aspect_combo.currentText(),
            "scale": self.stretch_scale_combo.currentText()
        }
        
        # Save background color
        if hasattr(self, 'bg_color_btn'):
            self.config_data["background_color"] = self.bg_color_btn.property("current_color")
        self.config_data["layers"] = self._collect_layers_from_ui()
        self.config_data["groups"] = self._collect_groups_from_ui()
        self.config_data["physics_collision_matrix"] = self._collect_collision_matrix_from_ui()

        # Save Input Actions
        self.config_data["input_actions"] = self._collect_input_actions_from_ui()

        # Save Lighting settings
        if "lighting" not in self.config_data:
            self.config_data["lighting"] = {}
        self.config_data["lighting"]["shadow_extend"] = self.shadow_extend_spin.value()

        # Save AI settings
        if "ai" not in self.config_data:
            self.config_data["ai"] = {}
        self.config_data["ai"]["provider"] = self.ai_provider_combo.currentText()
        self.config_data["ai"]["api_key"] = self.ai_api_key_edit.text().strip()
        self.config_data["ai"]["model"] = self.ai_model_edit.text().strip() or "gpt-4o-mini"
        self.config_data["ai"]["base_url"] = self.ai_base_url_edit.text().strip() or "https://api.openai.com/v1"
        self.config_data["ai"]["local_model"] = self.ai_local_model_edit.text().strip() or "llama3"
        self.config_data["ai"]["local_url"] = self.ai_local_url_edit.text().strip() or "http://localhost:11434/v1"
        self.config_data["ai"]["openrouter_api_key"] = self.ai_openrouter_key_edit.text().strip()
        self.config_data["ai"]["openrouter_model"] = self.ai_openrouter_model_edit.text().strip() or "deepseek/deepseek-chat:free"
        self.config_data["ai"]["openrouter_url"] = self.ai_openrouter_url_edit.text().strip() or "https://openrouter.ai/api/v1"
        self.config_data["ai"]["google_api_key"] = self.ai_google_key_edit.text().strip()
        self.config_data["ai"]["google_model"] = self.ai_google_model_edit.text().strip() or "gemini-2.5-flash"
        self.config_data["ai"]["anthropic_api_key"] = self.ai_anthropic_key_edit.text().strip()
        self.config_data["ai"]["anthropic_model"] = self.ai_anthropic_model_edit.text().strip() or "claude-3-5-sonnet-latest"
        self.config_data["ai"]["nvidia_api_key"] = self.ai_nvidia_key_edit.text().strip()
        self.config_data["ai"]["nvidia_model"] = self.ai_nvidia_model_edit.text().strip() or "google/gemma-4-31b-it"
        self.config_data["ai"]["nvidia_url"] = self.ai_nvidia_url_edit.text().strip() or "https://integrate.api.nvidia.com/v1"
        self.config_data["ai"]["temperature"] = self.ai_temperature_spin.value() / 10.0
        self.config_data["ai"]["max_tokens"] = self.ai_max_tokens_spin.value()

        # Save Android settings
        self.config_data["android"] = {
            "sdk_path": self.android_sdk_edit.text().strip(),
            "ndk_path": self.android_ndk_edit.text().strip(),
            "package_name": self.android_package_edit.text().strip() or "com.axispy.mygame",
            "version_code": self.android_version_code_spin.value(),
            "min_sdk": self.android_min_sdk_spin.value(),
            "target_sdk": self.android_target_sdk_spin.value(),
            "ndk_api": self.android_ndk_api_spin.value(),
            "orientation": self.android_orientation_combo.currentText(),
            "fullscreen": self.android_fullscreen_chk.isChecked(),
            "permissions": [self.android_permissions_list.item(i).text() for i in range(self.android_permissions_list.count())],
            "python_dependencies": self.android_python_deps_edit.toPlainText().strip(),
            "keystore_path": self.android_keystore_edit.text().strip(),
            "keystore_alias": self.android_keystore_alias_edit.text().strip(),
            "keystore_password": self.android_keystore_password_edit.text().strip()
        }

        try:
            with open(self.config_path, "w") as f:
                json.dump(self.config_data, f, indent=4)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project settings: {e}")

    # ── AI helpers ────────────────────────────────────────────────────

    def _on_ai_provider_changed(self, provider: str):
        """Show/hide provider-specific settings groups."""
        self.ai_openai_group.setVisible(provider == "openai")
        self.ai_local_group.setVisible(provider == "local")
        self.ai_openrouter_group.setVisible(provider == "openrouter")
        self.ai_google_group.setVisible(provider == "google")
        self.ai_anthropic_group.setVisible(provider == "anthropic")
        self.ai_nvidia_group.setVisible(provider == "nvidia")

    def _on_fetch_openrouter_models(self):
        """Fetch free models from OpenRouter and show a selection dialog."""
        import threading

        self._fetch_models_btn.setEnabled(False)
        self._fetch_models_btn.setText("Fetching...")

        def _fetch():
            try:
                import urllib.request
                url = "https://openrouter.ai/api/v1/models"
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                models = data.get("data", [])
                # Filter free models
                free = []
                for m in models:
                    pricing = m.get("pricing", {})
                    pp = float(pricing.get("prompt", "1"))
                    cp = float(pricing.get("completion", "1"))
                    if pp == 0 and cp == 0:
                        free.append(m)
                # Sort by name
                free.sort(key=lambda m: m.get("name", m["id"]))
                self._fetched_models = free
            except Exception as e:
                self._fetched_models = None
                self._fetch_error = str(e)

        def _on_done():
            self._fetch_models_btn.setEnabled(True)
            self._fetch_models_btn.setText("Browse Free Models...")
            if hasattr(self, '_fetch_error') and self._fetched_models is None:
                QMessageBox.warning(self, "Error", f"Failed to fetch models:\n{self._fetch_error}")
                return
            if not self._fetched_models:
                QMessageBox.information(self, "Models", "No free models found.")
                return
            # Show selection dialog
            from PyQt6.QtWidgets import QInputDialog
            items = []
            for m in self._fetched_models:
                ctx = m.get("context_length", 0)
                name = m.get("name", m["id"])
                items.append(f"{m['id']}  —  {name}  (ctx: {ctx:,})")
            selected, ok = QInputDialog.getItem(
                self, "Select Model", "Free OpenRouter Models:", items, 0, False)
            if ok and selected:
                model_id = selected.split("  —  ")[0].strip()
                self.ai_openrouter_model_edit.setText(model_id)

        t = threading.Thread(target=_fetch, daemon=True)
        t.start()

        # Poll for completion
        from PyQt6.QtCore import QTimer
        timer = QTimer(self)

        def _check():
            if not t.is_alive():
                timer.stop()
                _on_done()

        timer.timeout.connect(_check)
        timer.start(100)

    def _on_fetch_google_models(self):
        """Fetch available models from Google API and show a selection dialog."""
        import threading

        api_key = self.ai_google_key_edit.text().strip()
        if not api_key:
            QMessageBox.warning(self, "API Key Required", "Please enter a Google API Key first to fetch models.")
            return

        self._fetch_google_btn.setEnabled(False)
        self._fetch_google_btn.setText("Fetching...")

        def _fetch():
            try:
                import urllib.request
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                models = data.get("models", [])
                
                # Filter models that support generateContent
                available = []
                for m in models:
                    if "generateContent" in m.get("supportedGenerationMethods", []):
                        available.append(m)
                
                self._fetched_google_models = available
            except Exception as e:
                self._fetched_google_models = None
                self._fetch_google_error = str(e)

        def _on_done():
            self._fetch_google_btn.setEnabled(True)
            self._fetch_google_btn.setText("Browse Models...")
            if hasattr(self, '_fetch_google_error') and self._fetched_google_models is None:
                QMessageBox.warning(self, "Error", f"Failed to fetch models:\n{self._fetch_google_error}")
                return
            if not self._fetched_google_models:
                QMessageBox.information(self, "Models", "No models found supporting generateContent.")
                return
            # Show selection dialog
            from PyQt6.QtWidgets import QInputDialog
            items = []
            for m in self._fetched_google_models:
                name = m.get("name", "")
                display = m.get("displayName", name)
                if name.startswith("models/"):
                    name = name[7:]
                items.append(f"{name}  —  {display}")
            selected, ok = QInputDialog.getItem(
                self, "Select Model", "Available Google Models:", items, 0, False)
            if ok and selected:
                model_id = selected.split("  —  ")[0].strip()
                self.ai_google_model_edit.setText(model_id)

        t = threading.Thread(target=_fetch, daemon=True)
        t.start()

        # Poll for completion
        from PyQt6.QtCore import QTimer
        timer = QTimer(self)

        def _check():
            if not t.is_alive():
                timer.stop()
                _on_done()

        timer.timeout.connect(_check)
        timer.start(100)

    def _on_fetch_openai_models(self):
        """Fetch available models from OpenAI API and show a selection dialog."""
        import threading

        api_key = self.ai_api_key_edit.text().strip()
        base_url = self.ai_base_url_edit.text().strip() or "https://api.openai.com/v1"
        url = f"{base_url.rstrip('/')}/models"

        if not api_key:
            QMessageBox.warning(self, "API Key Required", "Please enter an OpenAI API Key first to fetch models.")
            return

        self._fetch_openai_btn.setEnabled(False)
        self._fetch_openai_btn.setText("Fetching...")

        def _fetch():
            try:
                import urllib.request
                req = urllib.request.Request(url, method="GET")
                req.add_header("Authorization", f"Bearer {api_key}")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                
                models = data.get("data", [])
                
                # Sort by id
                models.sort(key=lambda m: m.get("id", ""))
                
                self._fetched_openai_models = models
            except Exception as e:
                self._fetched_openai_models = None
                self._fetch_openai_error = str(e)

        def _on_done():
            self._fetch_openai_btn.setEnabled(True)
            self._fetch_openai_btn.setText("Browse Models...")
            if hasattr(self, '_fetch_openai_error') and self._fetched_openai_models is None:
                QMessageBox.warning(self, "Error", f"Failed to fetch models:\n{self._fetch_openai_error}")
                return
            if not self._fetched_openai_models:
                QMessageBox.information(self, "Models", "No models found.")
                return
            # Show selection dialog
            from PyQt6.QtWidgets import QInputDialog
            items = []
            for m in self._fetched_openai_models:
                name = m.get("id", "")
                items.append(name)
            selected, ok = QInputDialog.getItem(
                self, "Select Model", "Available OpenAI Models:", items, 0, False)
            if ok and selected:
                self.ai_model_edit.setText(selected.strip())

        t = threading.Thread(target=_fetch, daemon=True)
        t.start()

        from PyQt6.QtCore import QTimer
        timer = QTimer(self)

        def _check():
            if not t.is_alive():
                timer.stop()
                _on_done()

        timer.timeout.connect(_check)
        timer.start(100)

    def _on_fetch_anthropic_models(self):
        """Fetch available models from Anthropic API and show a selection dialog."""
        import threading

        api_key = self.ai_anthropic_key_edit.text().strip()
        url = "https://api.anthropic.com/v1/models"

        if not api_key:
            QMessageBox.warning(self, "API Key Required", "Please enter an Anthropic API Key first to fetch models.")
            return

        self._fetch_anthropic_btn.setEnabled(False)
        self._fetch_anthropic_btn.setText("Fetching...")

        def _fetch():
            try:
                import urllib.request
                req = urllib.request.Request(url, method="GET")
                req.add_header("x-api-key", api_key)
                req.add_header("anthropic-version", "2023-06-01")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                
                models = data.get("data", [])
                
                # Sort by id/name
                models.sort(key=lambda m: m.get("display_name", m.get("id", "")))
                
                self._fetched_anthropic_models = models
            except Exception as e:
                self._fetched_anthropic_models = None
                self._fetch_anthropic_error = str(e)

        def _on_done():
            self._fetch_anthropic_btn.setEnabled(True)
            self._fetch_anthropic_btn.setText("Browse Models...")
            if hasattr(self, '_fetch_anthropic_error') and self._fetched_anthropic_models is None:
                QMessageBox.warning(self, "Error", f"Failed to fetch models:\n{self._fetch_anthropic_error}")
                return
            if not self._fetched_anthropic_models:
                QMessageBox.information(self, "Models", "No models found.")
                return
            # Show selection dialog
            from PyQt6.QtWidgets import QInputDialog
            items = []
            for m in self._fetched_anthropic_models:
                id_ = m.get("id", "")
                name = m.get("display_name", id_)
                items.append(f"{id_}  —  {name}")
            selected, ok = QInputDialog.getItem(
                self, "Select Model", "Available Anthropic Models:", items, 0, False)
            if ok and selected:
                model_id = selected.split("  —  ")[0].strip()
                self.ai_anthropic_model_edit.setText(model_id)

        t = threading.Thread(target=_fetch, daemon=True)
        t.start()

        from PyQt6.QtCore import QTimer
        timer = QTimer(self)

        def _check():
            if not t.is_alive():
                timer.stop()
                _on_done()

        timer.timeout.connect(_check)
        timer.start(100)

    # ── Input Actions helpers ─────────────────────────────────────────

    def _populate_input_actions_table(self):
        """Fill the input actions table from config_data."""
        actions = self.config_data.get("input_actions", {})
        table = self.input_actions_table
        table.setRowCount(0)
        for action_name, key_codes in actions.items():
            if not isinstance(key_codes, list):
                continue
            row = table.rowCount()
            table.insertRow(row)
            name_item = QTableWidgetItem(str(action_name))
            table.setItem(row, 0, name_item)
            keys_str = ", ".join(_key_name(int(k)) for k in key_codes)
            keys_item = QTableWidgetItem(keys_str)
            keys_item.setFlags(keys_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            keys_item.setData(Qt.ItemDataRole.UserRole, list(key_codes))
            table.setItem(row, 1, keys_item)

    def _collect_input_actions_from_ui(self) -> dict:
        """Read the input actions table back into a dict for saving."""
        table = self.input_actions_table
        actions = {}
        for row in range(table.rowCount()):
            name_item = table.item(row, 0)
            keys_item = table.item(row, 1)
            if not name_item:
                continue
            action_name = name_item.text().strip()
            if not action_name:
                continue
            key_codes = []
            if keys_item:
                stored = keys_item.data(Qt.ItemDataRole.UserRole)
                if isinstance(stored, list):
                    key_codes = [int(k) for k in stored]
            actions[action_name] = key_codes
        return actions

    def _add_input_action(self):
        name, ok = QInputDialog.getText(self, "Add Action", "Action name (e.g. jump, fire, move_left):")
        if not ok or not name.strip():
            return
        name = name.strip()
        # Check for duplicate
        for row in range(self.input_actions_table.rowCount()):
            item = self.input_actions_table.item(row, 0)
            if item and item.text().strip().lower() == name.lower():
                QMessageBox.warning(self, "Duplicate", f"Action '{name}' already exists.")
                return
        row = self.input_actions_table.rowCount()
        self.input_actions_table.insertRow(row)
        self.input_actions_table.setItem(row, 0, QTableWidgetItem(name))
        keys_item = QTableWidgetItem("")
        keys_item.setFlags(keys_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        keys_item.setData(Qt.ItemDataRole.UserRole, [])
        self.input_actions_table.setItem(row, 1, keys_item)
        self.input_actions_table.selectRow(row)

    def _remove_input_action(self):
        row = self.input_actions_table.currentRow()
        if row < 0:
            return
        name = ""
        item = self.input_actions_table.item(row, 0)
        if item:
            name = item.text()
        reply = QMessageBox.question(
            self, "Remove Action",
            f"Remove action '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.input_actions_table.removeRow(row)

    def _add_key_to_action(self):
        row = self.input_actions_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Action Selected", "Select an action row first.")
            return
        _build_key_names()
        sorted_names = sorted(_PYGAME_KEY_NAMES.values(), key=str.lower)
        chosen, ok = QInputDialog.getItem(
            self, "Add Key",
            "Select a key to bind:",
            sorted_names, 0, True
        )
        if not ok or not chosen.strip():
            return
        code = _key_code_from_name(chosen.strip())
        if code is None:
            QMessageBox.warning(self, "Invalid Key", f"Unknown key: {chosen}")
            return
        keys_item = self.input_actions_table.item(row, 1)
        if not keys_item:
            return
        current_codes = keys_item.data(Qt.ItemDataRole.UserRole) or []
        if code in current_codes:
            QMessageBox.information(self, "Already Bound", f"Key '{_key_name(code)}' is already bound to this action.")
            return
        current_codes.append(code)
        keys_item.setData(Qt.ItemDataRole.UserRole, current_codes)
        keys_item.setText(", ".join(_key_name(k) for k in current_codes))

    def _remove_key_from_action(self):
        row = self.input_actions_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Action Selected", "Select an action row first.")
            return
        keys_item = self.input_actions_table.item(row, 1)
        if not keys_item:
            return
        current_codes = keys_item.data(Qt.ItemDataRole.UserRole) or []
        if not current_codes:
            return
        key_names = [_key_name(k) for k in current_codes]
        chosen, ok = QInputDialog.getItem(
            self, "Remove Key",
            "Select a key to remove:",
            key_names, 0, False
        )
        if not ok:
            return
        idx = key_names.index(chosen) if chosen in key_names else -1
        if idx >= 0:
            current_codes.pop(idx)
            keys_item.setData(Qt.ItemDataRole.UserRole, current_codes)
            keys_item.setText(", ".join(_key_name(k) for k in current_codes))

    # ── Android helpers ──────────────────────────────────────────────

    def _scan_sdk_candidates(self) -> list[str]:
        """Return a list of candidate Android SDK directories to probe."""
        candidates = []
        # Environment variables
        for env_var in ("ANDROID_HOME", "ANDROID_SDK_ROOT", "ANDROID_SDK"):
            val = os.environ.get(env_var, "").strip()
            if val:
                candidates.append(val)
        system = platform.system()
        home = os.path.expanduser("~")
        if system == "Windows":
            local_app = os.environ.get("LOCALAPPDATA", "")
            if local_app:
                candidates.append(os.path.join(local_app, "Android", "Sdk"))
            candidates.append(os.path.join(home, "AppData", "Local", "Android", "Sdk"))
            candidates.append(os.path.join(home, "Android", "Sdk"))
            prog = os.environ.get("ProgramFiles", r"C:\Program Files")
            candidates.append(os.path.join(prog, "Android", "android-sdk"))
            prog86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
            candidates.append(os.path.join(prog86, "Android", "android-sdk"))
        elif system == "Darwin":
            candidates.append(os.path.join(home, "Library", "Android", "sdk"))
            candidates.append("/usr/local/share/android-sdk")
        else:
            candidates.append(os.path.join(home, "Android", "Sdk"))
            candidates.append(os.path.join(home, "android-sdk"))
            candidates.append("/opt/android-sdk")
            candidates.append("/usr/local/android-sdk")
        return candidates

    def _is_valid_sdk(self, path: str) -> bool:
        """Check if path looks like a valid Android SDK root."""
        if not path or not os.path.isdir(path):
            return False
        # A valid SDK has platforms/ and/or build-tools/ subdirectories
        return (os.path.isdir(os.path.join(path, "platforms")) or
                os.path.isdir(os.path.join(path, "build-tools")))

    def _find_ndk_in_sdk(self, sdk_path: str) -> str:
        """Try to locate an NDK inside the SDK's ndk/ or ndk-bundle/ folder."""
        if not sdk_path:
            return ""
        ndk_dir = os.path.join(sdk_path, "ndk")
        if os.path.isdir(ndk_dir):
            # Pick the latest version subfolder
            versions = sorted(
                [d for d in os.listdir(ndk_dir) if os.path.isdir(os.path.join(ndk_dir, d))],
                reverse=True
            )
            if versions:
                return os.path.join(ndk_dir, versions[0])
        ndk_bundle = os.path.join(sdk_path, "ndk-bundle")
        if os.path.isdir(ndk_bundle):
            return ndk_bundle
        return ""

    def _sdk_status_text(self, sdk_path: str) -> str:
        """Return a summary of what's installed in the SDK."""
        parts = []
        platforms_dir = os.path.join(sdk_path, "platforms")
        if os.path.isdir(platforms_dir):
            apis = sorted([d for d in os.listdir(platforms_dir) if os.path.isdir(os.path.join(platforms_dir, d))])
            if apis:
                parts.append(f"Platforms: {', '.join(apis[-5:])}")
        bt_dir = os.path.join(sdk_path, "build-tools")
        if os.path.isdir(bt_dir):
            versions = sorted([d for d in os.listdir(bt_dir) if os.path.isdir(os.path.join(bt_dir, d))])
            if versions:
                parts.append(f"Build Tools: {versions[-1]}")
        return " | ".join(parts) if parts else "SDK found (contents unknown)"

    def _validate_sdk_path(self, sdk_path: str):
        if self._is_valid_sdk(sdk_path):
            self.android_sdk_status.setText(self._sdk_status_text(sdk_path))
            self.android_sdk_status.setStyleSheet("color: green;")
        elif sdk_path:
            self.android_sdk_status.setText("Invalid SDK path — platforms/ or build-tools/ not found")
            self.android_sdk_status.setStyleSheet("color: red;")
        else:
            self.android_sdk_status.setText("No SDK configured")
            self.android_sdk_status.setStyleSheet("color: orange;")

    def _auto_detect_sdk(self, silent: bool = False):
        for candidate in self._scan_sdk_candidates():
            normalized = os.path.normpath(candidate)
            if self._is_valid_sdk(normalized):
                self.android_sdk_edit.setText(normalized)
                self._validate_sdk_path(normalized)
                # Also try to find NDK
                if not self.android_ndk_edit.text().strip():
                    ndk = self._find_ndk_in_sdk(normalized)
                    if ndk:
                        self.android_ndk_edit.setText(ndk)
                if not silent:
                    QMessageBox.information(self, "SDK Found", f"Android SDK detected at:\n{normalized}")
                return
        if not silent:
            QMessageBox.warning(
                self, "SDK Not Found",
                "Could not auto-detect the Android SDK.\n\n"
                "Please install Android Studio or the command-line SDK tools,\n"
                "or set ANDROID_HOME / ANDROID_SDK_ROOT environment variable,\n"
                "then click Auto-Detect again or browse manually."
            )
        self._validate_sdk_path("")

    def _browse_android_sdk(self):
        start_dir = self.android_sdk_edit.text().strip() or os.path.expanduser("~")
        chosen = QFileDialog.getExistingDirectory(self, "Select Android SDK Root", start_dir)
        if chosen:
            normalized = os.path.normpath(chosen)
            self.android_sdk_edit.setText(normalized)
            self._validate_sdk_path(normalized)
            if not self.android_ndk_edit.text().strip():
                ndk = self._find_ndk_in_sdk(normalized)
                if ndk:
                    self.android_ndk_edit.setText(ndk)

    def _browse_android_ndk(self):
        start_dir = self.android_ndk_edit.text().strip() or self.android_sdk_edit.text().strip() or os.path.expanduser("~")
        chosen = QFileDialog.getExistingDirectory(self, "Select Android NDK Root", start_dir)
        if chosen:
            self.android_ndk_edit.setText(os.path.normpath(chosen))

    def _browse_keystore(self):
        start_dir = os.path.dirname(self.android_keystore_edit.text().strip()) or self.project_path or os.path.expanduser("~")
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Keystore", start_dir,
            "Keystore Files (*.keystore *.jks);;All Files (*)"
        )
        if file_path:
            self.android_keystore_edit.setText(os.path.normpath(file_path))

    def _add_android_permission(self):
        common_permissions = [
            "INTERNET", "ACCESS_NETWORK_STATE", "ACCESS_WIFI_STATE",
            "WRITE_EXTERNAL_STORAGE", "READ_EXTERNAL_STORAGE",
            "CAMERA", "RECORD_AUDIO", "ACCESS_FINE_LOCATION",
            "ACCESS_COARSE_LOCATION", "VIBRATE", "WAKE_LOCK",
            "BLUETOOTH", "BLUETOOTH_ADMIN", "NFC",
            "READ_CONTACTS", "WRITE_CONTACTS"
        ]
        existing = {self.android_permissions_list.item(i).text() for i in range(self.android_permissions_list.count())}
        available = [p for p in common_permissions if p not in existing]
        if available:
            perm, ok = QInputDialog.getItem(
                self, "Add Permission",
                "Select a permission (or type a custom one):",
                available, 0, True
            )
        else:
            perm, ok = QInputDialog.getText(
                self, "Add Permission",
                "Permission name (e.g. ACCESS_FINE_LOCATION):"
            )
        if ok and perm:
            perm = perm.strip().upper()
            if perm and perm not in existing:
                self.android_permissions_list.addItem(perm)

    def _remove_android_permission(self):
        item = self.android_permissions_list.currentItem()
        if item:
            self.android_permissions_list.takeItem(self.android_permissions_list.row(item))
