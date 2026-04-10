from PyQt6.QtWidgets import (QDockWidget, QPlainTextEdit, QVBoxLayout, QHBoxLayout, 
                             QCheckBox, QLabel, QWidget, QFrame, QScrollArea, QApplication)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QTextCharFormat, QColor, QFont, QPalette
import sys
import subprocess
from typing import List, Dict, Optional
from core.logger import get_logger, add_sink, remove_sink


class ConsoleDock(QDockWidget):
    """Console dock with filtering capabilities for engine logs, stdout/stderr, and player process output."""
    _log_signal = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__("Console", parent)
        self.setObjectName("ConsoleDock")
        
        # Log storage with metadata
        self._log_entries: List[Dict] = []
        self._max_entries = 3000
        
        # Filter state
        self._filters = {
            'DEBUG': True,
            'INFO': True,
            'WARNING': True,
            'ERROR': True,
            'STDOUT': True,
            'STDERR': True,
            'PLAYER': True
        }
        
        # Determine if we're in light or dark mode
        self._is_dark_mode = self._is_dark_theme()
        
        # Text formatting for different log types (theme-aware)
        self._formats = {
            'DEBUG': self._create_format(QColor(128, 128, 128) if self._is_dark_mode else QColor(100, 100, 100)),
            'INFO': self._create_format(QColor(255, 255, 255) if self._is_dark_mode else QColor(0, 0, 0)),
            'WARNING': self._create_format(QColor(255, 200, 0)),
            'ERROR': self._create_format(QColor(255, 100, 100)),
            'STDOUT': self._create_format(QColor(200, 255, 200) if self._is_dark_mode else QColor(0, 128, 0)),
            'STDERR': self._create_format(QColor(255, 150, 150) if self._is_dark_mode else QColor(200, 0, 0)),
            'PLAYER': self._create_format(QColor(150, 200, 255) if self._is_dark_mode else QColor(0, 100, 200))
        }
        
        # Process monitoring
        self._player_process = None
        self._player_timer = QTimer()
        self._player_timer.timeout.connect(self._read_player_output)
        self._player_timer.setInterval(100)  # Read every 100ms
        
        self._setup_ui()
        self._log_signal.connect(self._add_log_entry)
        self._setup_streams()
        
    def _is_dark_theme(self) -> bool:
        """Check if the current theme is dark by checking the window color."""
        palette = QApplication.palette()
        window_color = palette.color(QPalette.ColorRole.Window)
        # Dark themes typically have darker window colors
        return window_color.lightness() < 128
    
    def _create_format(self, color: QColor) -> QTextCharFormat:
        """Create text format with given color."""
        format = QTextCharFormat()
        format.setForeground(color)
        return format
        
    def _setup_ui(self):
        """Setup the console UI with filter controls."""
        self.setMinimumHeight(100)
        # Main widget
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Filter toolbar
        filter_frame = QFrame()
        filter_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        filter_frame.setMaximumHeight(40)
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(5, 2, 5, 2)
        
        # Engine log level filters
        filter_layout.addWidget(QLabel("Engine:"))
        
        self.debug_cb = QCheckBox("DEBUG")
        self.debug_cb.setChecked(True)
        self.debug_cb.stateChanged.connect(lambda: self._update_filter('DEBUG'))
        filter_layout.addWidget(self.debug_cb)
        
        self.info_cb = QCheckBox("INFO")
        self.info_cb.setChecked(True)
        self.info_cb.stateChanged.connect(lambda: self._update_filter('INFO'))
        filter_layout.addWidget(self.info_cb)
        
        self.warning_cb = QCheckBox("WARNING")
        self.warning_cb.setChecked(True)
        self.warning_cb.stateChanged.connect(lambda: self._update_filter('WARNING'))
        filter_layout.addWidget(self.warning_cb)
        
        self.error_cb = QCheckBox("ERROR")
        self.error_cb.setChecked(True)
        self.error_cb.stateChanged.connect(lambda: self._update_filter('ERROR'))
        filter_layout.addWidget(self.error_cb)
        
        filter_layout.addWidget(QLabel(" | "))
        
        # Python output filters
        filter_layout.addWidget(QLabel("Python:"))
        
        self.stdout_cb = QCheckBox("STDOUT")
        self.stdout_cb.setChecked(True)
        self.stdout_cb.stateChanged.connect(lambda: self._update_filter('STDOUT'))
        filter_layout.addWidget(self.stdout_cb)
        
        self.stderr_cb = QCheckBox("STDERR")
        self.stderr_cb.setChecked(True)
        self.stderr_cb.stateChanged.connect(lambda: self._update_filter('STDERR'))
        filter_layout.addWidget(self.stderr_cb)
        
        filter_layout.addWidget(QLabel(" | "))
        
        # Player process filter
        self.player_cb = QCheckBox("PLAYER")
        self.player_cb.setChecked(True)
        self.player_cb.stateChanged.connect(lambda: self._update_filter('PLAYER'))
        filter_layout.addWidget(self.player_cb)
        
        filter_layout.addStretch()
        
        # Console output
        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setMaximumBlockCount(self._max_entries)
        
        # Set theme-aware background color
        palette = self.console_output.palette()
        if self._is_dark_mode:
            palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        else:
            palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
        self.console_output.setPalette(palette)
        
        # Set font
        font = QFont("Consolas", 9)
        if not font.exactMatch():
            font = QFont("Courier New", 9)
        self.console_output.setFont(font)
        
        # Assemble layout
        layout.addWidget(filter_frame)
        layout.addWidget(self.console_output)
        
        self.setWidget(main_widget)
        
    def _setup_streams(self):
        """Setup stdout/stderr redirection."""
        self._stdout_original = sys.stdout
        self._stderr_original = sys.stderr
        self._console_stream_out = _ConsoleStream(self, 'STDOUT', self._stdout_original)
        self._console_stream_err = _ConsoleStream(self, 'STDERR', self._stderr_original)
        sys.stdout = self._console_stream_out
        sys.stderr = self._console_stream_err
        
        # Setup engine logger sink
        self._logger_sink = self._on_engine_log
        add_sink(self._logger_sink)
        
    def cleanup(self):
        """Cleanup resources."""
        remove_sink(self._logger_sink)
        if self._stdout_original is not None:
            sys.stdout = self._stdout_original
        if self._stderr_original is not None:
            sys.stderr = self._stderr_original
        if self._player_process:
            self._player_process.terminate()
            
    def _update_filter(self, filter_type: str):
        """Update filter state and refresh display."""
        self._filters[filter_type] = not self._filters[filter_type]
        self._refresh_display()
        
    def _add_log_entry_threadsafe(self, source: str, level: str, text: str):
        """Route log entries to the main thread via signal if called from a background thread."""
        if QThread.currentThread() is not self.thread():
            self._log_signal.emit(source, level, text)
            return
        self._add_log_entry(source, level, text)

    def _add_log_entry(self, source: str, level: str, text: str):
        """Add a log entry with metadata. Must be called on the main thread."""
        entry = {
            'source': source,
            'level': level,
            'text': text
        }
        self._log_entries.append(entry)
        
        # Trim old entries
        if len(self._log_entries) > self._max_entries:
            self._log_entries = self._log_entries[-self._max_entries:]
            
        # Update display if this entry should be shown
        if self._filters.get(level, True):
            self._append_to_display(entry)
            
    def _append_to_display(self, entry: Dict):
        """Append a single entry to the display."""
        cursor = self.console_output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        
        # Apply formatting
        format = self._formats.get(entry['level'], self._formats['INFO'])
        cursor.setCharFormat(format)
        cursor.insertText(entry['text'])
        
        # Reset format
        cursor.setCharFormat(self._formats['INFO'])
        
        self.console_output.setTextCursor(cursor)
        self.console_output.ensureCursorVisible()
        
    def _refresh_display(self):
        """Refresh the entire display based on current filters."""
        self.console_output.clear()
        for entry in self._log_entries:
            if self._filters.get(entry['level'], True):
                self._append_to_display(entry)
                
    def write_stdout(self, text: str):
        """Write stdout text to console."""
        if text:
            self._add_log_entry_threadsafe('python', 'STDOUT', text)
            
    def write_stderr(self, text: str):
        """Write stderr text to console."""
        if text:
            self._add_log_entry_threadsafe('python', 'STDERR', text)
            
    def _on_engine_log(self, record):
        """Handle engine log records."""
        data_suffix = f" | {record.data}" if record.data else ""
        formatted = f"[{record.level}] [{record.subsystem}] {record.message}{data_suffix}\n"
        self._add_log_entry_threadsafe('engine', record.level, formatted)
        
        # Show error in status bar (only safe from main thread)
        if record.level_value >= 30 and QThread.currentThread() is self.thread():
            parent = self.parent()
            if parent and hasattr(parent, 'statusBar'):
                parent.statusBar().showMessage(formatted.strip(), 8000)
                
    def set_player_process(self, process: subprocess.Popen):
        """Set the player process for log monitoring."""
        # Stop monitoring previous process
        if self._player_process:
            self._player_timer.stop()
            
        self._player_process = process
        if process and process.poll() is None:  # Process is still running
            self._player_timer.start()
            
    def _read_player_output(self):
        """Read output from player process."""
        if not self._player_process:
            return
            
        # Check if process has exited
        if self._player_process.poll() is not None:
            # Process has exited, read any remaining output
            if self._player_process.stdout:
                try:
                    remaining = self._player_process.stdout.read()
                    if remaining:
                        self._add_log_entry('player', 'PLAYER', f"[PLAYER] {remaining}")
                except Exception:
                    pass
                    
            if self._player_process.stderr:
                try:
                    remaining = self._player_process.stderr.read()
                    if remaining:
                        self._add_log_entry('player', 'PLAYER', f"[PLAYER ERROR] {remaining}")
                except Exception:
                    pass
                    
            # Log the exit
            return_code = self._player_process.returncode
            if return_code == 0:
                # Only log normal exit if we've seen some output (means we were in editor mode)
                if any(entry['source'] == 'player' for entry in self._log_entries[-10:]):
                    self._add_log_entry('player', 'PLAYER', f"\n[PLAYER] Process exited normally (code {return_code})\n")
            else:
                self._add_log_entry('player', 'PLAYER', f"\n[PLAYER ERROR] Process exited with error (code {return_code})\n")
                
            self._player_process = None
            self._player_timer.stop()
            return
            
        # Read stdout - simple non-blocking approach
        if self._player_process.stdout:
            try:
                line = self._player_process.stdout.readline()
                if line:
                    self._add_log_entry('player', 'PLAYER', f"[PLAYER] {line}")
            except Exception:
                pass
                
        # Read stderr - simple non-blocking approach
        if self._player_process.stderr:
            try:
                line = self._player_process.stderr.readline()
                if line:
                    self._add_log_entry('player', 'PLAYER', f"[PLAYER ERROR] {line}")
            except Exception:
                pass


class _ConsoleStream:
    """Stream wrapper for capturing stdout/stderr."""
    
    def __init__(self, console: ConsoleDock, stream_type: str, original_stream=None):
        self.console = console
        self.stream_type = stream_type
        self.original_stream = original_stream or getattr(sys, stream_type.lower())
        
    def write(self, text):
        # Prevent recursive logging
        if hasattr(self, '_writing'):
            return
        self._writing = True
        try:
            if self.original_stream and not isinstance(self.original_stream, _ConsoleStream):
                self.original_stream.write(text)
            if self.console and text:
                if self.stream_type == 'STDOUT':
                    self.console.write_stdout(text)
                else:
                    self.console.write_stderr(text)
        finally:
            self._writing = False
                
    def flush(self):
        if self.original_stream and not isinstance(self.original_stream, _ConsoleStream):
            try:
                self.original_stream.flush()
            except (AttributeError, OSError):
                pass
