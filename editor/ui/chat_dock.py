"""AI Chat dock widget for the AxisPy Engine editor."""
from __future__ import annotations

import os
import re
import threading
from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPlainTextEdit, QPushButton, QLabel,
    QScrollArea, QFrame, QApplication, QSizePolicy,
    QComboBox, QMenu, QInputDialog, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import (
    QFont, QColor, QTextCharFormat, QTextCursor,
    QPalette, QSyntaxHighlighter,
)
from PyQt6.QtWidgets import QGraphicsOpacityEffect
import qtawesome as qta
from editor.ui.engine_settings import theme_icon_color


def _markdown_to_html(text: str, is_dark: bool = True) -> str:
    """Convert basic Markdown to Qt HTML subset."""
    import html

    # Process tables first and store them
    tables = []
    
    def _extract_tables(match):
        """Extract table and replace with placeholder."""
        tables.append(match.group(0))
        return f"\n___TABLE_{len(tables)-1}___\n"
    
    # Match table blocks (lines starting and ending with |)
    def _process_tables(txt: str) -> str:
        lines = txt.split('\n')
        result_lines = []
        i = 0
        table_html_list = []
        
        while i < len(lines):
            line = lines[i]
            # Check if this is a table row
            if line.strip().startswith('|') and line.strip().endswith('|'):
                # Collect all table rows
                table_lines = []
                while i < len(lines) and lines[i].strip().startswith('|') and lines[i].strip().endswith('|'):
                    table_lines.append(lines[i])
                    i += 1
                
                if len(table_lines) >= 2:
                    # Parse table
                    header_row = table_lines[0]
                    separator_row = table_lines[1]
                    data_rows = table_lines[2:] if len(table_lines) > 2 else []
                    
                    # Check if separator row is valid
                    is_valid_separator = all(c in '|-:\t ' for c in separator_row.strip())
                    
                    if is_valid_separator:
                        # Build HTML table
                        border_color = '#555' if is_dark else '#ccc'
                        bg_color = '#2a2a3a' if is_dark else '#f5f5f5'
                        html_table = f'<table style="border-collapse:collapse;margin:8px 0;border:1px solid {border_color};">'
                        
                        # Header
                        html_table += '<thead>'
                        html_table += _parse_table_row(header_row, True, border_color, bg_color)
                        html_table += '</thead>'
                        
                        # Body
                        if data_rows:
                            html_table += '<tbody>'
                            for row in data_rows:
                                html_table += _parse_table_row(row, False, border_color, bg_color)
                            html_table += '</tbody>'
                        
                        html_table += '</table>'
                        table_html_list.append(html_table)
                        # Use HTML comment as placeholder - won't be affected by markdown
                        result_lines.append(f"<!--TABLE{len(table_html_list)-1}-->")
                        continue
                
                # Not a valid table, add lines back
                for tl in table_lines:
                    result_lines.append(tl)
                continue
            else:
                result_lines.append(line)
                i += 1
        
        return '\n'.join(result_lines), table_html_list
    
    text, table_html_list = _process_tables(text)
    
    # Escape HTML first
    text = html.escape(text)
    # Convert **bold** and __bold__
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
    # Convert *italic* and _italic_
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'_(.+?)_', r'<i>\1</i>', text)
    # Convert `code` spans
    code_color = '#e6c07b' if is_dark else '#c7254e'
    text = re.sub(r'`([^`]+)`', rf'<code style="background:rgba(255,255,255,0.1);color:{code_color};padding:1px 4px;border-radius:3px;font-family:Consolas,monospace;">\1</code>', text)
    # Convert [text](url) links
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    # Convert ### headings
    text = re.sub(r'### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'# (.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
    # Convert - and * list items
    text = re.sub(r'^\s*[-\*] (.+)$', r'• \1<br/>', text, flags=re.MULTILINE)
    # Preserve line breaks
    text = text.replace('\n', '<br/>')
    
    # Restore tables (unescaped)
    for i, table_html in enumerate(table_html_list):
        text = text.replace(f"&lt;!--TABLE{i}--&gt;", table_html)
    
    return text


def _parse_table_row(row: str, is_header: bool, border_color: str, bg_color: str) -> str:
    """Parse a markdown table row into HTML <tr>."""
    cells = row.strip('|').split('|')
    tag = 'th' if is_header else 'td'
    padding = '8px 12px'
    font_weight = 'bold' if is_header else 'normal'
    bg = bg_color if is_header else 'transparent'
    
    html_row = f'<tr style="border-bottom:1px solid {border_color};">'
    for cell in cells:
        content = cell.strip()
        # Apply inline markdown formatting to cell content
        content = _format_inline_markdown(content)
        html_row += f'<{tag} style="padding:{padding};font-weight:{font_weight};background:{bg};text-align:left;">{content}</{tag}>'
    html_row += '</tr>'
    return html_row


def _format_inline_markdown(text: str) -> str:
    """Apply inline markdown formatting (bold, italic, code, links)."""
    import html
    # Escape HTML first
    text = html.escape(text)
    # Convert **bold** and __bold__
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
    # Convert *italic* and _italic_
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'_(.+?)_', r'<i>\1</i>', text)
    # Convert `code` spans
    text = re.sub(r'`([^`]+)`', r'<code style="background:rgba(255,255,255,0.15);color:#e6c07b;padding:1px 4px;border-radius:3px;font-family:Consolas,monospace;font-size:12px;">\1</code>', text)
    # Convert [text](url) links
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color:#7ab3ef;text-decoration:underline;">\1</a>', text)
    return text


# ------------------------------------------------------------------
# Minimal Python syntax highlighter for code blocks
# ------------------------------------------------------------------

class _PythonHighlighter(QSyntaxHighlighter):
    """Very small highlighter used inside code-block widgets."""

    KEYWORDS = {
        "def", "class", "return", "if", "elif", "else", "for", "while",
        "import", "from", "as", "with", "try", "except", "finally",
        "raise", "yield", "pass", "break", "continue", "and", "or",
        "not", "in", "is", "None", "True", "False", "self", "lambda",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._formats = {}
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#c678dd"))
        kw_fmt.setFontWeight(QFont.Weight.Bold)
        self._formats["keyword"] = kw_fmt

        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#98c379"))
        self._formats["string"] = str_fmt

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#5c6370"))
        self._formats["comment"] = comment_fmt

        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor("#d19a66"))
        self._formats["number"] = num_fmt

        func_fmt = QTextCharFormat()
        func_fmt.setForeground(QColor("#61afef"))
        self._formats["function"] = func_fmt

    def highlightBlock(self, text: str):
        # Comments
        idx = text.find("#")
        if idx >= 0:
            self.setFormat(idx, len(text) - idx, self._formats["comment"])

        # Keywords
        for match in re.finditer(r"\b(" + "|".join(self.KEYWORDS) + r")\b", text):
            self.setFormat(match.start(), match.end() - match.start(), self._formats["keyword"])

        # Strings (simple)
        for match in re.finditer(r'(\".*?\"|\'.*?\')', text):
            self.setFormat(match.start(), match.end() - match.start(), self._formats["string"])

        # Numbers
        for match in re.finditer(r"\b\d+\.?\d*\b", text):
            self.setFormat(match.start(), match.end() - match.start(), self._formats["number"])

        # Function definitions
        for match in re.finditer(r"\bdef\s+(\w+)", text):
            self.setFormat(match.start(1), match.end(1) - match.start(1), self._formats["function"])


# ------------------------------------------------------------------
# Diff display widget
# ------------------------------------------------------------------

class DiffWidget(QFrame):
    """A collapsible unified diff widget for showing script edits."""

    def __init__(self, path: str, old_text: str, new_text: str, parent=None):
        super().__init__(parent)
        self._path = path
        self._old_text = old_text
        self._new_text = new_text
        self._collapsed = False

        is_dark = QApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128

        border = "#444" if is_dark else "#ccc"
        self.setStyleSheet(f"""
            DiffWidget {{
                background: {'#1e1e2e' if is_dark else '#fafafa'};
                border: 1px solid {border};
                border-radius: 6px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- Header bar ----
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background: {'#2a2a3a' if is_dark else '#e8e8f0'};
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border-bottom: 1px solid {border};
            }}
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 6, 10, 6)
        h_layout.setSpacing(6)

        edit_icon = QLabel()
        edit_icon.setPixmap(qta.icon("fa5s.file-code", color="#7ab3ef").pixmap(14, 14))
        h_layout.addWidget(edit_icon)

        path_label = QLabel(f"<b style='color:#7ab3ef;'>{path}</b>")
        path_label.setTextFormat(Qt.TextFormat.RichText)
        path_label.setStyleSheet(f"color: {'#aaa' if is_dark else '#555'}; font-size: 12px;")
        h_layout.addWidget(path_label)

        h_layout.addStretch()

        # Stats label (added/removed counts)
        old_lines = old_text.splitlines() if old_text.strip() else []
        new_lines = new_text.splitlines() if new_text.strip() else []
        stats_text = f"<span style='color:#ff6b6b;'>−{len(old_lines)}</span>&nbsp;&nbsp;<span style='color:#6bff6b;'>+{len(new_lines)}</span>"
        stats_label = QLabel(stats_text)
        stats_label.setTextFormat(Qt.TextFormat.RichText)
        stats_label.setStyleSheet("font-size: 11px; font-family: Consolas;")
        h_layout.addWidget(stats_label)

        # Copy diff button
        copy_btn = QPushButton()
        copy_btn.setIcon(qta.icon("fa5s.copy", color="#888"))
        copy_btn.setToolTip("Copy diff")
        copy_btn.setFixedSize(22, 22)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; border-radius: 3px; }
            QPushButton:hover { background: rgba(255,255,255,30); }
        """)
        copy_btn.clicked.connect(self._copy_diff)
        h_layout.addWidget(copy_btn)

        # Collapse/expand button
        self._toggle_btn = QPushButton()
        self._toggle_btn.setIcon(qta.icon("fa5s.chevron-up", color="#888"))
        self._toggle_btn.setToolTip("Collapse")
        self._toggle_btn.setFixedSize(22, 22)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; border-radius: 3px; }
            QPushButton:hover { background: rgba(255,255,255,30); }
        """)
        self._toggle_btn.clicked.connect(self._toggle_collapse)
        h_layout.addWidget(self._toggle_btn)

        layout.addWidget(header)

        # ---- Diff body ----
        self._body = QFrame()
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        diff_lines = self._build_unified_diff(old_text, new_text, is_dark)

        for line_widget in diff_lines:
            body_layout.addWidget(line_widget)

        layout.addWidget(self._body)

    def _build_unified_diff(self, old_text: str, new_text: str, is_dark: bool) -> list:
        """Build unified diff line widgets."""
        import difflib

        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)

        diff = list(difflib.unified_diff(old_lines, new_lines, n=3))

        widgets = []

        if not diff:
            lbl = QLabel("  No differences detected")
            lbl.setStyleSheet(f"color: {'#888' if is_dark else '#666'}; padding: 8px; font-size: 12px; font-family: Consolas;")
            widgets.append(lbl)
            return widgets

        line_num = 0
        for raw_line in diff:
            line = raw_line.rstrip('\n').rstrip('\r')

            # Skip diff headers (---, +++, @@)
            if line.startswith('---') or line.startswith('+++'):
                continue

            if line.startswith('@@'):
                # Hunk header
                w = self._make_line_widget(line, 'hunk', is_dark)
                widgets.append(w)
                continue

            line_num += 1
            if line.startswith('-'):
                w = self._make_line_widget(line, 'removed', is_dark)
            elif line.startswith('+'):
                w = self._make_line_widget(line, 'added', is_dark)
            else:
                w = self._make_line_widget(line, 'context', is_dark)
            widgets.append(w)

        # Limit displayed lines and add a "show more" indicator if needed
        max_lines = 40
        if len(widgets) > max_lines:
            truncated = widgets[:max_lines]
            more_lbl = QLabel(f"  ... and {len(widgets) - max_lines} more lines")
            more_lbl.setStyleSheet(f"color: {'#888' if is_dark else '#666'}; padding: 4px 8px; font-size: 11px; font-style: italic; font-family: Consolas;")
            truncated.append(more_lbl)
            return truncated

        return widgets

    @staticmethod
    def _make_line_widget(text: str, kind: str, is_dark: bool) -> QLabel:
        """Create a styled QLabel for a single diff line."""
        import html as html_mod
        escaped = html_mod.escape(text)

        if kind == 'removed':
            bg = '#3a1f1f' if is_dark else '#ffeef0'
            fg = '#ff9999' if is_dark else '#b31d28'
            prefix_color = '#ff6b6b' if is_dark else '#cb2431'
        elif kind == 'added':
            bg = '#1f3a1f' if is_dark else '#e6ffec'
            fg = '#99ff99' if is_dark else '#22863a'
            prefix_color = '#6bff6b' if is_dark else '#28a745'
        elif kind == 'hunk':
            bg = '#252540' if is_dark else '#f1f1ff'
            fg = '#8888cc' if is_dark else '#6f42c1'
            prefix_color = fg
        else:
            bg = 'transparent'
            fg = '#aaa' if is_dark else '#444'
            prefix_color = fg

        # Color the prefix character differently
        if kind in ('removed', 'added') and len(escaped) > 0:
            display = f"<span style='color:{prefix_color};font-weight:bold;'>{escaped[0]}</span>{escaped[1:]}"
        elif kind == 'hunk':
            display = f"<span style='color:{prefix_color};'>{escaped}</span>"
        else:
            display = f" {escaped}"

        lbl = QLabel(f"<pre style='margin:0;padding:0;font-family:Consolas,monospace;font-size:12px;white-space:pre;'>{display}</pre>")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl.setStyleSheet(f"""
            QLabel {{
                background: {bg};
                color: {fg};
                padding: 1px 8px;
                border: none;
                min-height: 18px;
            }}
        """)
        return lbl

    def _copy_diff(self):
        """Copy the full diff text to clipboard."""
        import difflib
        old_lines = self._old_text.splitlines(keepends=True)
        new_lines = self._new_text.splitlines(keepends=True)
        diff = difflib.unified_diff(old_lines, new_lines, fromfile=self._path, tofile=self._path)
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(''.join(diff))

        # Show toast on parent ChatMessageWidget
        parent = self.parent()
        if hasattr(parent, '_show_copy_toast'):
            parent._show_copy_toast()

    def _toggle_collapse(self):
        """Toggle the diff body visibility."""
        self._collapsed = not self._collapsed
        self._body.setVisible(not self._collapsed)
        if self._collapsed:
            self._toggle_btn.setIcon(qta.icon("fa5s.chevron-down", color="#888"))
            self._toggle_btn.setToolTip("Expand")
        else:
            self._toggle_btn.setIcon(qta.icon("fa5s.chevron-up", color="#888"))
            self._toggle_btn.setToolTip("Collapse")


# ------------------------------------------------------------------
# Chat message widget
# ------------------------------------------------------------------

class ChatMessageWidget(QFrame):
    """A single chat message bubble."""

    copy_code_requested = pyqtSignal(str)
    revert_requested = pyqtSignal(int)  # prompt_index

    def __init__(self, role: str, content: str, prompt_index: int = -1, parent=None):
        super().__init__(parent)
        self.role = role
        self.content = content
        self.prompt_index = prompt_index
        self._revert_btn = None

        is_dark = QApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128

        if role == "user":
            bg = "#2b3d4f" if is_dark else "#dce8f5"
            fg = "#e0e0e0" if is_dark else "#1a1a1a"
        else:
            bg = "#1e2a1e" if is_dark else "#e8f5e8"
            fg = "#e0e0e0" if is_dark else "#1a1a1a"

        self.setStyleSheet(f"""
            ChatMessageWidget {{
                background-color: {bg};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)

        # Profile Header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        icon_label = QLabel()
        c = "#7ab3ef" if role != "user" else "#a0c0e0"
        icon_name = "fa5s.robot" if role != "user" else "fa5s.user"
        icon_label.setPixmap(qta.icon(icon_name, color=c).pixmap(16, 16))
        
        role_name_label = QLabel("You" if role == "user" else "Axis AI Assistant")
        role_name_label.setStyleSheet(f"color: {c}; font-weight: bold; font-size: 13px;")
        
        import datetime
        time_label = QLabel(datetime.datetime.now().strftime("%H:%M"))
        time_label.setStyleSheet(f"color: {'#888' if is_dark else '#666'}; font-size: 10px;")
        
        copy_msg_btn = QPushButton()
        copy_msg_btn.setIcon(qta.icon("fa5s.copy", color="#666"))
        copy_msg_btn.setToolTip("Copy message")
        copy_msg_btn.setFixedSize(20, 20)
        copy_msg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_msg_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; border-radius: 3px; }
            QPushButton:hover { background: rgba(255,255,255,30); }
        """)
        copy_msg_btn.clicked.connect(self._copy_message)
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(role_name_label)
        header_layout.addStretch()
        header_layout.addWidget(time_label)
        header_layout.addWidget(copy_msg_btn)

        # Revert button (hidden by default, shown when prompt had file actions)
        if role != "user":
            self._revert_btn = QPushButton()
            self._revert_btn.setIcon(qta.icon("fa5s.undo-alt", color="#e0a050"))
            self._revert_btn.setToolTip("Revert changes from this response")
            self._revert_btn.setFixedSize(20, 20)
            self._revert_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._revert_btn.setStyleSheet("""
                QPushButton { background: transparent; border: none; border-radius: 3px; }
                QPushButton:hover { background: rgba(255,200,100,40); }
            """)
            self._revert_btn.clicked.connect(self._on_revert_clicked)
            self._revert_btn.hide()
            header_layout.addWidget(self._revert_btn)

        layout.addLayout(header_layout)

        # Parse content for code blocks
        self._add_content(layout, content, fg, is_dark)

    def _add_content(self, layout: QVBoxLayout, content: str, fg: str, is_dark: bool):
        """Parse markdown-like content and add text/code widgets."""
        parts = re.split(r"(```[\s\S]*?```)", content)
        for part in parts:
            if part.startswith("```") and part.endswith("```"):
                # Code block
                code = part[3:]
                lang = ""
                if "\n" in code:
                    first_line, rest = code.split("\n", 1)
                    lang = first_line.strip()
                    code = rest
                elif "\r\n" in code:
                    first_line, rest = code.split("\r\n", 1)
                    lang = first_line.strip()
                    code = rest

                code = code.rstrip("`").rstrip()

                code_frame = QFrame()
                code_frame.setStyleSheet(f"""
                    QFrame {{
                        background-color: {'#1a1a2e' if is_dark else '#f0f0f0'};
                        border: 1px solid {'#333' if is_dark else '#ccc'};
                        border-radius: 4px;
                    }}
                """)
                code_layout = QVBoxLayout(code_frame)
                code_layout.setContentsMargins(8, 4, 8, 4)
                code_layout.setSpacing(2)

                # Copy button + Language Label
                btn_row = QHBoxLayout()
                if lang:
                    lang_label = QLabel(lang)
                    lang_label.setStyleSheet(f"color: {'#7ab3ef' if is_dark else '#2a4a6b'}; font-size: 10px; font-weight: bold; font-family: Consolas;")
                    btn_row.addWidget(lang_label)
                btn_row.addStretch()
                copy_btn = QPushButton("Copy")
                copy_btn.setFixedHeight(20)
                copy_btn.setStyleSheet("""
                    QPushButton {
                        background: transparent; border: 1px solid #555;
                        border-radius: 3px; padding: 1px 8px; font-size: 10px;
                        color: #aaa;
                    }
                    QPushButton:hover { background: #333; color: #fff; }
                """)
                captured_code = code
                copy_btn.clicked.connect(lambda checked, c=captured_code: self._copy_code(c))
                btn_row.addWidget(copy_btn)
                code_layout.addLayout(btn_row)

                code_edit = QPlainTextEdit()
                code_edit.setPlainText(code)
                code_edit.setReadOnly(True)
                code_edit.setFont(QFont("Consolas", 10))
                code_edit.setStyleSheet(f"""
                    QPlainTextEdit {{
                        background: transparent;
                        color: {'#abb2bf' if is_dark else '#333'};
                        border: none;
                    }}
                """)
                # Auto-size height
                doc = code_edit.document()
                doc.setDefaultFont(code_edit.font())
                height = int(doc.size().height()) + 10
                code_edit.setFixedHeight(min(height, 400))
                _PythonHighlighter(code_edit.document())

                code_layout.addWidget(code_edit)
                layout.addWidget(code_frame)
            else:
                # Markdown text
                text = part.strip()
                if text:
                    html = _markdown_to_html(text, is_dark)
                    label = QLabel(html)
                    label.setWordWrap(True)
                    label.setTextFormat(Qt.TextFormat.RichText)
                    label.setTextInteractionFlags(
                        Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse
                    )
                    label.setOpenExternalLinks(True)
                    label.setStyleSheet(f"""
                        QLabel {{
                            color: {fg};
                            font-size: 13px;
                            line-height: 1.4;
                        }}
                        QLabel a {{
                            color: #7ab3ef;
                            text-decoration: underline;
                        }}
                        QLabel code {{
                            font-family: Consolas, monospace;
                        }}
                    """)
                    layout.addWidget(label)

    def show_revert_button(self):
        """Make the revert button visible (called when prompt had file actions)."""
        if self._revert_btn:
            self._revert_btn.show()

    def mark_reverted(self):
        """Visually mark this message as reverted."""
        if self._revert_btn:
            self._revert_btn.setIcon(qta.icon("fa5s.check", color="#888"))
            self._revert_btn.setToolTip("Changes reverted")
            self._revert_btn.setEnabled(False)
            self._revert_btn.setStyleSheet("""
                QPushButton { background: transparent; border: none; border-radius: 3px; }
            """)

    def _on_revert_clicked(self):
        """Emit revert signal with this message's prompt index."""
        if self.prompt_index >= 0:
            self.revert_requested.emit(self.prompt_index)

    def _copy_message(self):
        """Copy the entire message content to clipboard."""
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.content)
            self._show_copy_toast()

    def _copy_code(self, code: str):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(code)
            self._show_copy_toast()
        self.copy_code_requested.emit(code)

    def _show_copy_toast(self):
        """Show a small animated 'Copied!' toast over this message."""
        self._show_copy_toast_text("✓ Copied!")

    def _show_copy_toast_text(self, text: str):
        """Show a small animated toast with custom text over this message."""
        toast = QLabel(text, self)
        toast.setStyleSheet("""
            QLabel {
                background: #2a2a3a;
                color: #7ab3ef;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        toast.adjustSize()
        toast.move(self.width() - toast.width() - 10, 4)
        toast.show()

        effect = QGraphicsOpacityEffect(toast)
        toast.setGraphicsEffect(effect)
        effect.setOpacity(1.0)

        anim = QPropertyAnimation(effect, b"opacity", toast)
        anim.setDuration(1200)
        anim.setStartValue(1.0)
        anim.setKeyValueAt(0.6, 1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InQuad)
        anim.finished.connect(toast.deleteLater)
        anim.start()

    def update_content(self, content: str):
        """Replace content (used during streaming)."""
        self.content = content
        layout = self.layout()

        # Preserve DiffWidgets before clearing
        diff_widgets = []
        i = 1
        while i < layout.count():
            item = layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, DiffWidget):
                layout.takeAt(i)
                diff_widgets.append(widget)
            else:
                i += 1

        # Clear existing widgets except role label (index 0)
        while layout.count() > 1:
            item = layout.takeAt(1)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        is_dark = QApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128
        fg = "#e0e0e0" if is_dark else "#1a1a1a"
        self._add_content(layout, content, fg, is_dark)

        # Re-add DiffWidgets at the bottom
        for diff_w in diff_widgets:
            layout.addWidget(diff_w)

    def inject_diff_widget(self, path: str, old_text: str, new_text: str):
        """Inject a DiffWidget into the message."""
        diff_w = DiffWidget(path, old_text, new_text, parent=self)
        self.layout().addWidget(diff_w)


# ------------------------------------------------------------------
# Main chat dock
# ------------------------------------------------------------------

class ChatDock(QDockWidget):
    """Dockable AI chat panel for the editor."""

    message_received = pyqtSignal(str)

    def __init__(self, chat_manager, parent=None):
        super().__init__("AI Assistant", parent)
        self.setObjectName("ChatDock")
        self.chat_manager = chat_manager
        self._streaming = False
        self._stream_widget: ChatMessageWidget | None = None
        self._stream_text = ""
        self._pending_chunks: list[str] = []
        self._chunk_timer = QTimer(self)
        self._chunk_timer.setInterval(50)
        self._chunk_timer.timeout.connect(self._flush_chunks)
        self._current_prompt_index = -1
        self._stream_had_actions = False

        self._setup_ui()

    def _setup_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # Header with session selector, model info, and clear button
        header = QHBoxLayout()
        c = theme_icon_color()

        # Session selector
        self._session_combo = QComboBox()
        self._session_combo.setFixedWidth(140)
        self._session_combo.setToolTip("Select conversation session")
        self._session_combo.currentIndexChanged.connect(self._on_session_changed)
        header.addWidget(self._session_combo)

        # New session button
        new_btn = QPushButton()
        new_btn.setIcon(qta.icon("fa5s.plus", color=c))
        new_btn.setToolTip("New session")
        new_btn.setFixedSize(24, 24)
        new_btn.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 4px; } QPushButton:hover { background: rgba(255,255,255,30); }")
        new_btn.clicked.connect(self._on_new_session)
        header.addWidget(new_btn)

        # Delete session button
        del_btn = QPushButton()
        del_btn.setIcon(qta.icon("fa5s.trash", color=c))
        del_btn.setToolTip("Delete session")
        del_btn.setFixedSize(24, 24)
        del_btn.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 4px; } QPushButton:hover { background: rgba(255,255,255,30); }")
        del_btn.clicked.connect(self._on_delete_session)
        header.addWidget(del_btn)

        header.addSpacing(10)

        self._model_label = QLabel("No provider")
        self._model_label.setStyleSheet("color: #888; font-size: 11px;")
        header.addWidget(self._model_label)
        header.addStretch()

        clear_btn = QPushButton()
        clear_btn.setIcon(qta.icon("fa5s.trash-alt", color=c))
        clear_btn.setToolTip("Clear conversation")
        clear_btn.setFixedSize(28, 28)
        clear_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; border-radius: 4px; }
            QPushButton:hover { background: rgba(255,255,255,30); }
        """)
        clear_btn.clicked.connect(self._clear_chat)
        header.addWidget(clear_btn)
        main_layout.addLayout(header)

        # Scroll area for messages
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet("QScrollArea { border: none; }")

        self._messages_widget = QWidget()
        self._messages_layout = QVBoxLayout(self._messages_widget)
        self._messages_layout.setContentsMargins(2, 2, 2, 2)
        self._messages_layout.setSpacing(8)
        
        # Empty state
        self._empty_state_frame = QFrame()
        empty_layout = QVBoxLayout(self._empty_state_frame)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        empty_icon = QLabel()
        empty_icon.setPixmap(qta.icon("fa5s.robot", color="#666").pixmap(48, 48))
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_title = QLabel("Axis AI Assistant")
        empty_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #7ab3ef; margin-top: 10px;")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_desc = QLabel("I can help you build your game, write scripts,\nand navigate the AxisPy Engine.")
        empty_desc.setStyleSheet("color: #888; font-size: 12px; margin-top: 5px;")
        empty_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        empty_layout.addWidget(empty_icon)
        empty_layout.addWidget(empty_title)
        empty_layout.addWidget(empty_desc)
        
        self._messages_layout.addWidget(self._empty_state_frame)
        self._messages_layout.addStretch()
        self._scroll_area.setWidget(self._messages_widget)
        main_layout.addWidget(self._scroll_area, 1)

        # Input area
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #444;
                border-radius: 6px;
                background: palette(base);
            }
        """)
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(6, 6, 6, 6)
        input_layout.setSpacing(4)

        self._input_edit = QPlainTextEdit()
        self._input_edit.setPlaceholderText("Ask anything about your game project...")
        self._input_edit.setFont(QFont("Segoe UI", 11))
        self._input_edit.setMaximumHeight(100)
        self._input_edit.setStyleSheet("""
            QPlainTextEdit {
                border: none;
                background: transparent;
            }
        """)
        input_layout.addWidget(self._input_edit)

        # Bottom row: context toggle + send
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(6)

        self._context_check = QPushButton("Context: On")
        self._context_check.setCheckable(True)
        self._context_check.setChecked(True)
        self._context_check.setFixedHeight(28)
        self._context_check.setStyleSheet("""
            QPushButton {
                background: transparent; border: 1px solid #555;
                border-radius: 4px; padding: 2px 10px; font-size: 11px;
                color: #aaa;
            }
            QPushButton:checked { color: #7ab3ef; border-color: #7ab3ef; }
            QPushButton:hover { background: rgba(255,255,255,20); }
        """)
        self._context_check.toggled.connect(
            lambda on: self._context_check.setText("Context: On" if on else "Context: Off")
        )
        bottom_row.addWidget(self._context_check)
        bottom_row.addStretch()

        self._send_btn = QPushButton("Send")
        self._send_btn.setIcon(qta.icon("fa5s.paper-plane", color="#7ab3ef"))
        self._send_btn.setFixedHeight(30)
        self._send_btn.setStyleSheet("""
            QPushButton {
                background: #2a4a6b; color: white;
                border: none; border-radius: 4px; padding: 4px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #3a5a7b; }
            QPushButton:disabled { background: #333; color: #666; }
        """)
        self._send_btn.clicked.connect(self._on_send)
        bottom_row.addWidget(self._send_btn)

        input_layout.addLayout(bottom_row)
        main_layout.addWidget(input_frame)

        self.setWidget(main_widget)

        # Install Ctrl+Enter shortcut on input
        self._input_edit.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self._input_edit and event.type() == event.Type.KeyPress:
            key = event.key()
            mods = event.modifiers()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if mods & Qt.KeyboardModifier.ControlModifier:
                    self._on_send()
                    return True
                elif not (mods & Qt.KeyboardModifier.ShiftModifier):
                    self._on_send()
                    return True
        return super().eventFilter(obj, event)

    def update_model_label(self):
        if self.chat_manager.provider and self.chat_manager.provider.is_available():
            self._model_label.setText(f"Model: {self.chat_manager.provider.model_name()}")
            self._model_label.setStyleSheet("color: #7ab3ef; font-size: 11px;")
        else:
            self._model_label.setText("No AI provider configured")
            self._model_label.setStyleSheet("color: #888; font-size: 11px;")

    # ------------------------------------------------------------------
    # Send / receive
    # ------------------------------------------------------------------

    def _on_send(self):
        if self._streaming:
            return

        text = self._input_edit.toPlainText().strip()
        if not text:
            return

        self._input_edit.clear()
        self._add_message("user", text)

        # Disable context if toggled off
        original_context = self.chat_manager.context_builder
        if not self._context_check.isChecked():
            self.chat_manager.context_builder = type(original_context)()

        # Start streaming in a background thread
        self._streaming = True
        self._send_btn.setEnabled(False)
        self._send_btn.setText("● Thinking...")
        self._stream_text = ""
        self._pending_chunks = []
        self._stream_had_actions = False

        # Create placeholder assistant message with prompt index
        self._current_prompt_index = self.chat_manager.current_prompt_index + 1
        self._stream_widget = self._add_message("assistant", "...", prompt_index=self._current_prompt_index)

        self.chat_manager.set_callbacks(
            on_chunk=self._on_stream_chunk,
            on_complete=self._on_stream_complete,
            on_error=self._on_stream_error,
            on_session_changed=self.refresh_sessions,
            on_tool_result=self._on_tool_result,
        )

        def _run():
            try:
                self.chat_manager.send_message_stream(text)
            except Exception as e:
                self._pending_chunks.append(f"\n[Error] {e}")

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        self._chunk_timer.start()

        # Restore context builder
        if not self._context_check.isChecked():
            self.chat_manager.context_builder = original_context

    def _on_stream_chunk(self, chunk: str):
        """Called from background thread — append to pending list."""
        self._pending_chunks.append(chunk)

    def _on_stream_complete(self, full_text: str):
        """Called from background thread when streaming is done."""
        self._pending_chunks.append(None)  # Sentinel

    def _on_stream_error(self, error: str):
        self._pending_chunks.append(error)
        self._pending_chunks.append(None)

    def _on_tool_result(self, tool_name: str, result: str):
        """Called when a tool execution completes — show diff for script edits."""
        try:
            import json
            data = json.loads(result)
        except Exception:
            return

        # Track that this prompt had file-modifying actions
        modifying_tools = {"edit_script", "write_script", "create_entity",
                           "add_component_to_entity", "modify_component"}
        if tool_name in modifying_tools and data.get("success"):
            self._stream_had_actions = True

        # Only show diff for edit_script with successful result
        if tool_name == "edit_script" and data.get("success") and data.get("diff"):
            diff = data["diff"]
            old_text = diff.get("old_text", "")
            new_text = diff.get("new_text", "")
            path = data.get("path", "")

            # Store diff data and schedule widget creation on main thread
            self._pending_diff = (path, old_text, new_text)
            QTimer.singleShot(0, self._inject_diff_widget)

    def _inject_diff_widget(self):
        """Create and inject a DiffWidget into the current stream widget (main thread)."""
        diff_data = getattr(self, '_pending_diff', None)
        if diff_data and self._stream_widget:
            path, old_text, new_text = diff_data
            self._stream_widget.inject_diff_widget(path, old_text, new_text)
            self._scroll_to_bottom()
        self._pending_diff = None

    def _flush_chunks(self):
        """Called by QTimer on the main thread — apply pending chunks to UI."""
        if not self._pending_chunks:
            return

        chunks = list(self._pending_chunks)
        self._pending_chunks.clear()
        done = False

        for chunk in chunks:
            if chunk is None:
                done = True
                break
            self._stream_text += chunk

        if self._stream_widget:
            self._stream_widget.update_content(self._stream_text)

        self._scroll_to_bottom()

        if done:
            self._chunk_timer.stop()
            self._streaming = False
            self._send_btn.setEnabled(True)
            self._send_btn.setText("Send")
            # Show revert button if this prompt had file-modifying actions
            if self._stream_had_actions and self._stream_widget:
                self._stream_widget.show_revert_button()
            self._stream_widget = None

    # ------------------------------------------------------------------
    # Message display
    # ------------------------------------------------------------------

    def _add_message(self, role: str, content: str, prompt_index: int = -1) -> ChatMessageWidget:
        self._empty_state_frame.hide()
        msg_widget = ChatMessageWidget(role, content, prompt_index=prompt_index)
        msg_widget.revert_requested.connect(self._on_revert_prompt)
        # Insert before the stretch
        count = self._messages_layout.count()
        self._messages_layout.insertWidget(count - 1, msg_widget)
        QTimer.singleShot(10, self._scroll_to_bottom)
        return msg_widget

    def _scroll_to_bottom(self):
        vbar = self._scroll_area.verticalScrollBar()
        vbar.setValue(vbar.maximum())

    def _on_revert_prompt(self, prompt_index: int):
        """Handle revert request from a message widget."""
        tracker = self.chat_manager.action_tracker

        if tracker.is_reverted(prompt_index):
            return

        files = tracker.get_modified_files(prompt_index)
        if not files:
            return

        # Build a short file list for the confirmation dialog
        file_names = [os.path.basename(f) for f in files]
        file_list = "\n".join(f"  • {n}" for n in file_names)
        reply = QMessageBox.question(
            self, "Revert AI Changes",
            f"Revert changes to {len(files)} file(s)?\n\n{file_list}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        results = self.chat_manager.revert_prompt(prompt_index)

        # Mark the widget as reverted
        sender = self.sender()
        if isinstance(sender, ChatMessageWidget):
            sender.mark_reverted()
        else:
            # Find the widget by prompt_index
            for i in range(self._messages_layout.count()):
                item = self._messages_layout.itemAt(i)
                w = item.widget() if item else None
                if isinstance(w, ChatMessageWidget) and w.prompt_index == prompt_index:
                    w.mark_reverted()
                    break

        # Reload scene if any scene files were reverted
        scene_reload_cb = self.chat_manager.tool_executor._scene_reload_callback
        if scene_reload_cb:
            for path, status in results.items():
                if status == "restored" and path.endswith(".scene"):
                    try:
                        scene_reload_cb(path)
                    except Exception:
                        pass

        # Show confirmation toast on the reverted message widget
        for i in range(self._messages_layout.count()):
            item = self._messages_layout.itemAt(i)
            w = item.widget() if item else None
            if isinstance(w, ChatMessageWidget) and w.prompt_index == prompt_index:
                w._show_copy_toast_text("✓ Reverted!")
                break

    def _clear_chat(self):
        self.chat_manager.clear_history()
        self.chat_manager.action_tracker.clear()
        self._clear_message_widgets()
        self._empty_state_frame.show()

    def _clear_message_widgets(self):
        for i in reversed(range(self._messages_layout.count())):
            item = self._messages_layout.itemAt(i)
            if item.widget() and isinstance(item.widget(), ChatMessageWidget):
                widget = item.widget()
                self._messages_layout.removeItem(item)
                widget.deleteLater()

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def refresh_sessions(self):
        """Refresh the session dropdown from session_manager."""
        self._session_combo.blockSignals(True)
        self._session_combo.clear()

        sessions = self.chat_manager.session_manager.get_session_list()
        active_id = self.chat_manager.session_manager.active_session_id

        for sess in sessions:
            self._session_combo.addItem(sess.name, sess.id)

        # Select active session
        for i in range(self._session_combo.count()):
            if self._session_combo.itemData(i) == active_id:
                self._session_combo.setCurrentIndex(i)
                break

        self._session_combo.blockSignals(False)

    def _on_session_changed(self, index: int):
        """Handle session dropdown change."""
        if index < 0:
            return
        session_id = self._session_combo.itemData(index)
        if session_id and session_id != self.chat_manager.session_manager.active_session_id:
            self.chat_manager.switch_session(session_id)
            self._reload_messages()

    def _on_new_session(self):
        """Create a new session."""
        name, ok = QInputDialog.getText(self, "New Session", "Session name:", text="New Session")
        if ok:
            self.chat_manager.create_new_session(name)
            self.refresh_sessions()
            self._reload_messages()

    def _on_delete_session(self):
        """Delete the current session."""
        current_id = self.chat_manager.session_manager.active_session_id
        if not current_id:
            return

        session = self.chat_manager.session_manager.sessions.get(current_id)
        if not session:
            return

        reply = QMessageBox.question(
            self, "Delete Session",
            f"Delete session \"{session.name}\"?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.chat_manager.delete_session(current_id)
            self.refresh_sessions()
            self._reload_messages()

    def _reload_messages(self):
        """Reload all messages from the active session."""
        self._clear_message_widgets()
        
        has_messages = False
        # Load from history
        for msg in self.chat_manager.history:
            if msg.role in ("user", "assistant"):
                self._add_message(msg.role, msg.content)
                has_messages = True

        if has_messages:
            self._empty_state_frame.hide()
        else:
            self._empty_state_frame.show()

        self._scroll_to_bottom()
