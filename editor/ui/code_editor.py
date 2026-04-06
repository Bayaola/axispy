from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QToolBar,
    QMessageBox, QLineEdit, QPushButton, QLabel
)
from PyQt6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PyQt6.QtCore import Qt
from PyQt6.Qsci import QsciScintilla, QsciLexerPython, QsciAPIs
import os

from editor.ui.engine_settings import load_saved_theme_mode

# ---------------------------------------------------------------------------
# Theme color palettes
# ---------------------------------------------------------------------------

DARK_THEME = {
    "background":       "#1E1E1E",
    "text":             "#D4D4D4",
    "caret":            "#AEAFAD",
    "current_line":     "#2D2D30",
    "selection_bg":     "#264F78",
    "selection_fg":     "#D4D4D4",
    "margin_bg":        "#252526",
    "margin_fg":        "#858585",
    "fold_margin_bg":   "#252526",
    "fold_fg":          "#858585",
    "brace_match_bg":   "#3B514D",
    "brace_match_fg":   "#D4D4D4",
    "brace_bad_bg":     "#5C1E1E",
    "brace_bad_fg":     "#FF0000",
    "indent_guide":     "#404040",
    # Lexer styles
    "default":          "#D4D4D4",
    "comment":          "#6A9955",
    "number":           "#B5CEA8",
    "string":           "#CE9178",
    "keyword":          "#569CD6",
    "class_name":       "#4EC9B0",
    "function":         "#DCDCAA",
    "operator":         "#D4D4D4",
    "identifier":       "#9CDCFE",
    "decorator":        "#D7BA7D",
    "triple_string":    "#CE9178",
}

LIGHT_THEME = {
    "background":       "#FFFFFF",
    "text":             "#1E1E1E",
    "caret":            "#000000",
    "current_line":     "#E8E8E8",
    "selection_bg":     "#ADD6FF",
    "selection_fg":     "#1E1E1E",
    "margin_bg":        "#F0F0F0",
    "margin_fg":        "#6E6E6E",
    "fold_margin_bg":   "#F0F0F0",
    "fold_fg":          "#6E6E6E",
    "brace_match_bg":   "#C8E6C9",
    "brace_match_fg":   "#1E1E1E",
    "brace_bad_bg":     "#FFCDD2",
    "brace_bad_fg":     "#B00020",
    "indent_guide":     "#D0D0D0",
    # Lexer styles
    "default":          "#1E1E1E",
    "comment":          "#008000",
    "number":           "#098658",
    "string":           "#A31515",
    "keyword":          "#0000FF",
    "class_name":       "#267F99",
    "function":         "#795E26",
    "operator":         "#1E1E1E",
    "identifier":       "#001080",
    "decorator":        "#795E26",
    "triple_string":    "#A31515",
}


def _get_theme_colors():
    mode = load_saved_theme_mode()
    return DARK_THEME if mode == "Dark" else LIGHT_THEME


# ---------------------------------------------------------------------------
# Find / Replace bar
# ---------------------------------------------------------------------------

class FindReplaceBar(QWidget):
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self._editor = editor
        self.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        layout.addWidget(QLabel("Find:"))
        self.find_input = QLineEdit()
        self.find_input.setMaximumWidth(220)
        self.find_input.returnPressed.connect(self.find_next)
        layout.addWidget(self.find_input)

        self.btn_prev = QPushButton("<")
        self.btn_prev.setFixedWidth(28)
        self.btn_prev.clicked.connect(self.find_prev)
        layout.addWidget(self.btn_prev)

        self.btn_next = QPushButton(">")
        self.btn_next.setFixedWidth(28)
        self.btn_next.clicked.connect(self.find_next)
        layout.addWidget(self.btn_next)

        layout.addWidget(QLabel("Replace:"))
        self.replace_input = QLineEdit()
        self.replace_input.setMaximumWidth(220)
        layout.addWidget(self.replace_input)

        self.btn_replace = QPushButton("Replace")
        self.btn_replace.clicked.connect(self.replace_one)
        layout.addWidget(self.btn_replace)

        self.btn_replace_all = QPushButton("All")
        self.btn_replace_all.clicked.connect(self.replace_all)
        layout.addWidget(self.btn_replace_all)

        self.btn_close = QPushButton("X")
        self.btn_close.setFixedWidth(24)
        self.btn_close.clicked.connect(self.hide)
        layout.addWidget(self.btn_close)

        layout.addStretch()

    def show_bar(self):
        self.setVisible(True)
        self.find_input.setFocus()
        self.find_input.selectAll()

    def find_next(self):
        text = self.find_input.text()
        if not text:
            return
        self._editor.findFirst(text, False, False, False, True)

    def find_prev(self):
        text = self.find_input.text()
        if not text:
            return
        self._editor.findFirst(text, False, False, False, True, forward=False)

    def replace_one(self):
        text = self.find_input.text()
        replacement = self.replace_input.text()
        if not text:
            return
        if self._editor.hasSelectedText() and self._editor.selectedText() == text:
            self._editor.replace(replacement)
        self._editor.findFirst(text, False, False, False, True)

    def replace_all(self):
        text = self.find_input.text()
        replacement = self.replace_input.text()
        if not text:
            return
        count = 0
        self._editor.setCursorPosition(0, 0)
        while self._editor.findFirst(text, False, False, False, False):
            self._editor.replace(replacement)
            count += 1
        if count:
            self._editor.setCursorPosition(0, 0)


# ---------------------------------------------------------------------------
# QScintilla-based Code Editor
# ---------------------------------------------------------------------------

class CodeEditor(QsciScintilla):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._theme_colors = _get_theme_colors()

        # Font
        self._font = QFont("Consolas", 10)
        self._font.setFixedPitch(True)
        self.setFont(self._font)

        # --- Lexer (Python syntax highlighting) ---
        self._lexer = QsciLexerPython(self)
        self._lexer.setFont(self._font)
        self.setLexer(self._lexer)

        # --- Autocompletion ---
        self._apis = QsciAPIs(self._lexer)
        self._build_api_entries()
        self._apis.prepare()
        self.setAutoCompletionSource(QsciScintilla.AutoCompletionSource.AcsAll)
        self.setAutoCompletionThreshold(1)
        self.setAutoCompletionCaseSensitivity(False)
        self.setAutoCompletionReplaceWord(True)

        # --- Line numbers ---
        self.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
        self.setMarginWidth(0, "00000")
        self.setMarginLineNumbers(0, True)

        # --- Code folding ---
        self.setFolding(QsciScintilla.FoldStyle.BoxedTreeFoldStyle, 2)

        # --- Current line highlighting ---
        self.setCaretLineVisible(True)

        # --- Bracket matching ---
        self.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)

        # --- Indentation ---
        self.setIndentationsUseTabs(False)
        self.setTabWidth(4)
        self.setAutoIndent(True)
        self.setTabIndents(True)
        self.setBackspaceUnindents(True)

        # --- Indentation guides ---
        self.setIndentationGuides(True)

        # --- Edge column (ruler at 80 chars) ---
        self.setEdgeMode(QsciScintilla.EdgeMode.EdgeLine)
        self.setEdgeColumn(100)

        # --- Wrap ---
        self.setWrapMode(QsciScintilla.WrapMode.WrapNone)

        # --- End-of-line ---
        self.setEolMode(QsciScintilla.EolMode.EolUnix)
        self.setEolVisibility(False)

        # Apply theme
        self._apply_theme_colors()

    # -----------------------------------------------------------------------
    # Theme
    # -----------------------------------------------------------------------
    def _apply_theme_colors(self):
        c = self._theme_colors

        # Editor colors
        self.setColor(QColor(c["text"]))
        self.setPaper(QColor(c["background"]))
        self.setCaretForegroundColor(QColor(c["caret"]))
        self.setCaretLineBackgroundColor(QColor(c["current_line"]))
        self.setSelectionBackgroundColor(QColor(c["selection_bg"]))
        self.setSelectionForegroundColor(QColor(c["selection_fg"]))

        # Line number margin
        self.setMarginsBackgroundColor(QColor(c["margin_bg"]))
        self.setMarginsForegroundColor(QColor(c["margin_fg"]))

        # Fold margin
        self.setFoldMarginColors(QColor(c["fold_margin_bg"]), QColor(c["fold_margin_bg"]))

        # Brace matching
        self.setMatchedBraceBackgroundColor(QColor(c["brace_match_bg"]))
        self.setMatchedBraceForegroundColor(QColor(c["brace_match_fg"]))
        self.setUnmatchedBraceBackgroundColor(QColor(c["brace_bad_bg"]))
        self.setUnmatchedBraceForegroundColor(QColor(c["brace_bad_fg"]))

        # Indent guides
        self.setIndentationGuidesBackgroundColor(QColor(c["indent_guide"]))
        self.setIndentationGuidesForegroundColor(QColor(c["indent_guide"]))

        # Edge line
        self.setEdgeColor(QColor(c["indent_guide"]))

        # --- Lexer styles ---
        lexer = self._lexer
        font = self._font

        # Default
        lexer.setColor(QColor(c["default"]), QsciLexerPython.Default)
        lexer.setPaper(QColor(c["background"]), QsciLexerPython.Default)
        lexer.setFont(font, QsciLexerPython.Default)

        # Comments
        for style in (QsciLexerPython.Comment, QsciLexerPython.CommentBlock):
            lexer.setColor(QColor(c["comment"]), style)
            lexer.setPaper(QColor(c["background"]), style)
            lexer.setFont(font, style)

        # Numbers
        lexer.setColor(QColor(c["number"]), QsciLexerPython.Number)
        lexer.setPaper(QColor(c["background"]), QsciLexerPython.Number)
        lexer.setFont(font, QsciLexerPython.Number)

        # Strings (single and double quoted)
        for style in (QsciLexerPython.SingleQuotedString,
                      QsciLexerPython.DoubleQuotedString,
                      QsciLexerPython.SingleQuotedFString,
                      QsciLexerPython.DoubleQuotedFString):
            lexer.setColor(QColor(c["string"]), style)
            lexer.setPaper(QColor(c["background"]), style)
            lexer.setFont(font, style)

        # Triple-quoted strings
        for style in (QsciLexerPython.TripleSingleQuotedString,
                      QsciLexerPython.TripleDoubleQuotedString,
                      QsciLexerPython.TripleSingleQuotedFString,
                      QsciLexerPython.TripleDoubleQuotedFString):
            lexer.setColor(QColor(c["triple_string"]), style)
            lexer.setPaper(QColor(c["background"]), style)
            lexer.setFont(font, style)

        # Keywords
        lexer.setColor(QColor(c["keyword"]), QsciLexerPython.Keyword)
        lexer.setPaper(QColor(c["background"]), QsciLexerPython.Keyword)
        bold_font = QFont(font)
        bold_font.setBold(True)
        lexer.setFont(bold_font, QsciLexerPython.Keyword)

        # Class names
        lexer.setColor(QColor(c["class_name"]), QsciLexerPython.ClassName)
        lexer.setPaper(QColor(c["background"]), QsciLexerPython.ClassName)
        lexer.setFont(bold_font, QsciLexerPython.ClassName)

        # Function / method names
        lexer.setColor(QColor(c["function"]), QsciLexerPython.FunctionMethodName)
        lexer.setPaper(QColor(c["background"]), QsciLexerPython.FunctionMethodName)
        lexer.setFont(font, QsciLexerPython.FunctionMethodName)

        # Operators
        lexer.setColor(QColor(c["operator"]), QsciLexerPython.Operator)
        lexer.setPaper(QColor(c["background"]), QsciLexerPython.Operator)
        lexer.setFont(font, QsciLexerPython.Operator)

        # Identifiers
        lexer.setColor(QColor(c["identifier"]), QsciLexerPython.Identifier)
        lexer.setPaper(QColor(c["background"]), QsciLexerPython.Identifier)
        lexer.setFont(font, QsciLexerPython.Identifier)

        # Decorators
        lexer.setColor(QColor(c["decorator"]), QsciLexerPython.Decorator)
        lexer.setPaper(QColor(c["background"]), QsciLexerPython.Decorator)
        lexer.setFont(font, QsciLexerPython.Decorator)

    def apply_theme(self):
        self._theme_colors = _get_theme_colors()
        self._apply_theme_colors()

    # -----------------------------------------------------------------------
    # Autocompletion API builder
    # -----------------------------------------------------------------------
    def _build_api_entries(self):
        apis = self._apis

        # Python keywords
        keywords = [
            "and", "as", "assert", "break", "class", "continue", "def",
            "del", "elif", "else", "except", "False", "finally", "for",
            "from", "global", "if", "import", "in", "is", "lambda", "None",
            "nonlocal", "not", "or", "pass", "raise", "return", "True",
            "try", "while", "with", "yield", "self",
        ]
        for w in keywords:
            apis.add(w)

        # Python builtins
        builtins_list = dir(__builtins__) if isinstance(__builtins__, dict) else dir(__builtins__)
        for w in builtins_list:
            if not w.startswith("_"):
                apis.add(w)

        # -- ScriptComponent methods (available via self.*) --
        script_methods = [
            "self.on_start()",
            "self.on_update(dt)",
            "self.on_collision_enter(other)",
            "self.find(name)",
            "self.get_children(name)",
            "self.destroy()",
            "self.hide()",
            "self.show()",
            "self.process_physics(enabled)",
            "self.change_scene(scene_name)",
            "self.call_group(group_name, method_name)",
            "self.subscribe_to_event(event_name, callback)",
            "self.unsubscribe_from_event(event_name, callback)",
            "self.emit_global_event(event_name)",
            "self.emit_local_event(event_name)",
            "self.instantiate_prefab(prefab_path)",
            "self.spawn_prefab(prefab_path)",
            "self.entity",
        ]
        for entry in script_methods:
            apis.add(entry)

        # -- Entity properties/methods (available via self.entity.*) --
        entity_members = [
            "self.entity.name",
            "self.entity.id",
            "self.entity.parent",
            "self.entity.children",
            "self.entity.world",
            "self.entity.layer",
            "self.entity.groups",
            "self.entity.add_component(component)",
            "self.entity.get_component(component_type)",
            "self.entity.remove_component(component_type)",
            "self.entity.add_child(child)",
            "self.entity.remove_child(child)",
            "self.entity.get_child(name)",
            "self.entity.get_children()",
            "self.entity.get_children_copy()",
            "self.entity.add_group(group)",
            "self.entity.remove_group(group)",
            "self.entity.has_group(group)",
            "self.entity.set_layer(layer)",
            "self.entity.hide()",
            "self.entity.show()",
            "self.entity.is_visible()",
            "self.entity.destroy()",
            "self.entity.process_physics(enabled)",
            "self.entity.is_physics_processing()",
            "self.entity.events",
        ]
        for entry in entity_members:
            apis.add(entry)

        # -- Input class (static methods) --
        input_methods = [
            "Input.get_key(key_code)",
            "Input.get_mouse_button(button_index)",
            "Input.get_mouse_position()",
            "Input.get_game_mouse_position()",
            "Input.get_axis(axis_name)",
            "Input.get_events()",
            "Input.get_joy_button(button)",
            "Input.get_joy_button_down(button)",
            "Input.get_joy_button_up(button)",
            "Input.get_joy_axis(axis)",
            "Input.get_joy_hat(hat)",
            "Input.get_joystick_count()",
            "Input.get_joystick_ids()",
            "Input.get_joystick_name()",
            "Input.set_joystick_deadzone(deadzone)",
            "Input.get_touches()",
            "Input.get_touch_count()",
            "Input.get_touches_started()",
            "Input.get_touches_moved()",
            "Input.get_touches_ended()",
            "Input.is_touching()",
            "Input.get_gesture()",
            "Input.JOY_A", "Input.JOY_B", "Input.JOY_X", "Input.JOY_Y",
            "Input.JOY_LB", "Input.JOY_RB", "Input.JOY_BACK", "Input.JOY_START",
            "Input.JOY_L3", "Input.JOY_R3",
            "Input.JOY_LEFT_X", "Input.JOY_LEFT_Y",
            "Input.JOY_RIGHT_X", "Input.JOY_RIGHT_Y",
            "Input.JOY_LT", "Input.JOY_RT",
        ]
        for entry in input_methods:
            apis.add(entry)

        # -- Vector2 --
        vector2_members = [
            "Vector2(x, y)",
            "Vector2.x", "Vector2.y",
            "Vector2.magnitude()",
            "Vector2.normalize()",
            "Vector2.dot(other)",
            "Vector2.copy()",
        ]
        for entry in vector2_members:
            apis.add(entry)

        # -- Common components --
        components = [
            "Transform", "SpriteRenderer", "CameraComponent",
            "Rigidbody2D", "BoxCollider2D", "CircleCollider2D", "PolygonCollider2D",
            "AnimatorComponent", "ParticleEmitterComponent",
            "ScriptComponent", "SoundComponent", "WebSocketComponent",
            "HTTPClientComponent", "HTTPRequestComponent", "WebviewComponent",
            "WebRTCComponent", "MultiplayerComponent", "NetworkIdentityComponent",
            "TilemapComponent",
            "TextRenderer", "ButtonComponent", "TextInputComponent",
            "SliderComponent", "ProgressBarComponent", "CheckBoxComponent",
            "ImageRenderer",
            "HBoxContainerComponent", "VBoxContainerComponent", "GridBoxContainerComponent",
        ]
        for c in components:
            apis.add(c)

        # -- Common imports --
        common_imports = [
            "from core.components.script import ScriptComponent",
            "from core.input import Input",
            "from core.components import Transform",
            "from core.components import SpriteRenderer",
            "from core.components import Rigidbody2D",
            "from core.components import BoxCollider2D",
            "from core.components import CircleCollider2D",
            "from core.components import SoundComponent",
            "from core.components.websocket import WebSocketComponent",
            "from core.components.http_client import HTTPClientComponent",
            "from core.components.http_request import HTTPRequestComponent",
            "from core.components.webview import WebviewComponent",
            "from core.components.webrtc import WebRTCComponent",
            "from core.components.multiplayer import MultiplayerComponent",
            "from core.components.network_identity import NetworkIdentityComponent",
            "from core.multiplayer.room import Player",
            "from core.components import AnimatorComponent",
            "from core.components import CameraComponent",
            "from core.components import ParticleEmitterComponent",
            "from core.vector import Vector2",
        ]
        for entry in common_imports:
            apis.add(entry)

        # -- pygame constants commonly used --
        pygame_keys = [
            "pygame.K_UP", "pygame.K_DOWN", "pygame.K_LEFT", "pygame.K_RIGHT",
            "pygame.K_SPACE", "pygame.K_RETURN", "pygame.K_ESCAPE",
            "pygame.K_a", "pygame.K_b", "pygame.K_c", "pygame.K_d",
            "pygame.K_e", "pygame.K_f", "pygame.K_g", "pygame.K_h",
            "pygame.K_i", "pygame.K_j", "pygame.K_k", "pygame.K_l",
            "pygame.K_m", "pygame.K_n", "pygame.K_o", "pygame.K_p",
            "pygame.K_q", "pygame.K_r", "pygame.K_s", "pygame.K_t",
            "pygame.K_u", "pygame.K_v", "pygame.K_w", "pygame.K_x",
            "pygame.K_y", "pygame.K_z",
            "pygame.K_0", "pygame.K_1", "pygame.K_2", "pygame.K_3",
            "pygame.K_4", "pygame.K_5", "pygame.K_6", "pygame.K_7",
            "pygame.K_8", "pygame.K_9",
            "pygame.K_LSHIFT", "pygame.K_RSHIFT", "pygame.K_LCTRL", "pygame.K_RCTRL",
        ]
        for entry in pygame_keys:
            apis.add(entry)

    def refresh_apis_from_document(self):
        """Scan the current document text and add identifiers to the API set."""
        import re
        text = self.text()
        # Extract def/class names and variable assignments
        identifiers = set()
        for m in re.finditer(r'\bdef\s+(\w+)', text):
            name = m.group(1)
            identifiers.add(f"self.{name}")
            identifiers.add(name)
        for m in re.finditer(r'\bclass\s+(\w+)', text):
            identifiers.add(m.group(1))
        for m in re.finditer(r'\bself\.(\w+)\s*=', text):
            identifiers.add(f"self.{m.group(1)}")
        if identifiers:
            for word in identifiers:
                self._apis.add(word)
            self._apis.prepare()

    # -----------------------------------------------------------------------
    # Compatibility helpers (used by ScriptEditorWidget)
    # -----------------------------------------------------------------------
    def setPlainText(self, text):
        self.setText(text)
        self.refresh_apis_from_document()

    def toPlainText(self):
        return self.text()


# ---------------------------------------------------------------------------
# Script Editor Widget (tab container with toolbar)
# ---------------------------------------------------------------------------

class ScriptEditorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        # Toolbar
        self.toolbar = QToolBar()
        self.save_action = self.toolbar.addAction("Save")
        self.save_action.triggered.connect(self.save_file)
        self.find_action = self.toolbar.addAction("Find")
        self.find_action.triggered.connect(self._toggle_find_bar)
        self._layout.addWidget(self.toolbar)

        # Find / Replace bar (hidden by default)
        self._find_bar_placeholder = QWidget()
        self._find_bar_placeholder.setVisible(False)
        self._layout.addWidget(self._find_bar_placeholder)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._layout.addWidget(self.tabs)

        self.current_file_path = None
        self._find_bars: dict[int, FindReplaceBar] = {}

        # Global shortcuts
        QShortcut(QKeySequence("Ctrl+F"), self, self._toggle_find_bar)
        QShortcut(QKeySequence("Ctrl+H"), self, self._toggle_find_bar)
        QShortcut(QKeySequence("Ctrl+G"), self, self._goto_line)
        QShortcut(QKeySequence("Ctrl+/"), self, self._toggle_comment)
        QShortcut(QKeySequence("Ctrl+D"), self, self._duplicate_line)

    # -----------------------------------------------------------------------
    # Theme
    # -----------------------------------------------------------------------
    def apply_theme(self):
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if isinstance(editor, CodeEditor):
                editor.apply_theme()

    # -----------------------------------------------------------------------
    # File operations
    # -----------------------------------------------------------------------
    def open_file(self, path):
        try:
            with open(path, "r") as f:
                content = f.read()
            existing_index = self.find_tab_by_path(path)
            if existing_index != -1:
                editor = self.tabs.widget(existing_index)
                editor.setPlainText(content)
                self.tabs.setCurrentIndex(existing_index)
            else:
                editor = CodeEditor()
                editor.setPlainText(content)
                editor.setProperty("file_path", path)
                title = os.path.basename(path)
                index = self.tabs.addTab(editor, title)
                self.tabs.setCurrentIndex(index)
            self.save_action.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error opening file {path}: {e}")

    def save_file(self):
        editor = self.tabs.currentWidget()
        if editor:
            file_path = editor.property("file_path")
            if file_path:
                try:
                    with open(file_path, "w") as f:
                        f.write(editor.toPlainText())
                    print(f"Saved file {file_path}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Error saving file {file_path}: {e}")

    def close_tab(self, index):
        widget = self.tabs.widget(index)
        if widget:
            self._find_bars.pop(id(widget), None)
            widget.setParent(None)

    def find_tab_by_path(self, path):
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if widget and widget.property("file_path") == path:
                return i
        return -1

    # -----------------------------------------------------------------------
    # Find / Replace
    # -----------------------------------------------------------------------
    def _current_editor(self):
        w = self.tabs.currentWidget()
        return w if isinstance(w, CodeEditor) else None

    def _get_find_bar(self, editor):
        key = id(editor)
        if key not in self._find_bars:
            bar = FindReplaceBar(editor, self)
            self._find_bars[key] = bar
            idx = self._layout.indexOf(self.tabs)
            self._layout.insertWidget(idx, bar)
        return self._find_bars[key]

    def _toggle_find_bar(self):
        editor = self._current_editor()
        if not editor:
            return
        bar = self._get_find_bar(editor)
        if bar.isVisible():
            bar.hide()
        else:
            # Hide all other bars
            for b in self._find_bars.values():
                b.hide()
            bar.show_bar()

    def _on_tab_changed(self, index):
        # Hide all find bars when switching tabs
        for bar in self._find_bars.values():
            bar.hide()

    # -----------------------------------------------------------------------
    # Extra shortcuts
    # -----------------------------------------------------------------------
    def _goto_line(self):
        editor = self._current_editor()
        if not editor:
            return
        from PyQt6.QtWidgets import QInputDialog
        line, ok = QInputDialog.getInt(self, "Go to Line", "Line number:", 1, 1, editor.lines())
        if ok:
            editor.setCursorPosition(line - 1, 0)
            editor.setFocus()

    def _toggle_comment(self):
        editor = self._current_editor()
        if not editor:
            return
        line_from, idx_from, line_to, idx_to = editor.getSelection()
        if line_from == -1:
            line_from = line_to = editor.getCursorPosition()[0]
        editor.beginUndoAction()
        for line in range(line_from, line_to + 1):
            text = editor.text(line)
            stripped = text.lstrip()
            if stripped.startswith("# "):
                indent = len(text) - len(stripped)
                editor.setSelection(line, indent, line, indent + 2)
                editor.replaceSelectedText("")
            elif stripped.startswith("#"):
                indent = len(text) - len(stripped)
                editor.setSelection(line, indent, line, indent + 1)
                editor.replaceSelectedText("")
            else:
                indent = len(text) - len(stripped)
                editor.insertAt("# ", line, indent)
        editor.endUndoAction()

    def _duplicate_line(self):
        editor = self._current_editor()
        if not editor:
            return
        line, col = editor.getCursorPosition()
        text = editor.text(line)
        eol = "\n" if not text.endswith("\n") else ""
        editor.beginUndoAction()
        editor.setCursorPosition(line, len(editor.text(line).rstrip("\n")))
        editor.insert("\n" + text.rstrip("\n"))
        editor.endUndoAction()
        editor.setCursorPosition(line + 1, col)

