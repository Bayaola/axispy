import os
import sys
import subprocess
import webbrowser
import platform
import threading
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout
)
from PyQt6.QtCore import QTimer
from core.logger import get_logger
from export.builder import WebExporter, DesktopExporter, MobileExporter, ServerExporter, ExportCancelled


class ExportDialog(QDialog):
    def __init__(self, project_path: str, parent=None):
        super().__init__(parent)
        self.project_path = project_path
        self._logger = get_logger("editor.export")
        self.setWindowTitle("Export Project")
        self.setMinimumWidth(520)
        self._exporter_by_name = {
            "Web": WebExporter,
            "Desktop": DesktopExporter,
            "Mobile": MobileExporter,
            "Server": ServerExporter
        }
        self._server_process = None
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        form = QFormLayout()

        self.target_combo = QComboBox()
        self.target_combo.addItems(list(self._exporter_by_name.keys()))
        self.target_combo.currentTextChanged.connect(self._on_target_changed)
        form.addRow("Target:", self.target_combo)

        self.build_mode_combo = QComboBox()
        self.build_mode_combo.addItems(["release", "debug"])
        form.addRow("Build Mode:", self.build_mode_combo)

        output_row = QHBoxLayout()
        default_output = os.path.join(self.project_path, "build")
        self.output_edit = QLineEdit(default_output)
        self.output_browse = QPushButton("Browse...")
        self.output_browse.clicked.connect(self._choose_output_folder)
        output_row.addWidget(self.output_edit)
        output_row.addWidget(self.output_browse)
        form.addRow("Output Folder:", output_row)

        # Mobile-specific options
        self.mobile_format_row = (QLabel("Android Format:"), QComboBox())
        self.mobile_format_combo = self.mobile_format_row[1]
        self.mobile_format_combo.addItems(["APK", "AAB"])
        form.addRow(*self.mobile_format_row)

        self.mobile_buildozer_row = (QLabel(""), QCheckBox("Run Buildozer build after export"))
        self.mobile_buildozer_check = self.mobile_buildozer_row[1]
        self.mobile_buildozer_check.setChecked(False)
        form.addRow(*self.mobile_buildozer_row)

        # Desktop-specific options
        self.desktop_target_os_row = (QLabel("Desktop Target OS:"), QComboBox())
        self.desktop_target_os_combo = self.desktop_target_os_row[1]
        self.desktop_target_os_combo.addItems(["Windows", "Linux", "macOS"])
        current_os = platform.system().lower()
        if current_os == "darwin":
            self.desktop_target_os_combo.setCurrentText("macOS")
        elif current_os != "windows":
            self.desktop_target_os_combo.setCurrentText("Linux")
        self.desktop_target_os_combo.currentTextChanged.connect(self._on_desktop_os_changed)
        form.addRow(*self.desktop_target_os_row)

        self.desktop_pyinstaller_row = (QLabel(""), QCheckBox("Build executable with PyInstaller"))
        self.desktop_pyinstaller_check = self.desktop_pyinstaller_row[1]
        self.desktop_pyinstaller_check.setChecked(True)
        self.desktop_pyinstaller_check.toggled.connect(lambda _: self._sync_target_os_controls())
        form.addRow(*self.desktop_pyinstaller_row)

        # Server-specific options
        self.server_target_os_row = (QLabel("Server Target OS:"), QComboBox())
        self.server_target_os_combo = self.server_target_os_row[1]
        self.server_target_os_combo.addItems(["Windows", "Linux"])
        if current_os != "windows":
            self.server_target_os_combo.setCurrentText("Linux")
        self.server_target_os_combo.currentTextChanged.connect(lambda _: self._on_target_changed(self.target_combo.currentText()))
        form.addRow(*self.server_target_os_row)

        self.server_pyinstaller_row = (QLabel(""), QCheckBox("Build standalone server executable with PyInstaller"))
        self.server_pyinstaller_check = self.server_pyinstaller_row[1]
        self.server_pyinstaller_check.setChecked(False)
        self.server_pyinstaller_check.toggled.connect(lambda _: self._sync_target_os_controls())
        form.addRow(*self.server_pyinstaller_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        form.addRow("Status:", self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Exporting...")
        self.progress_bar.setVisible(False)
        form.addRow("", self.progress_bar)

        main_layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self._run_export)
        self.open_folder_button = QPushButton("Open Build Folder")
        self.open_folder_button.clicked.connect(self._open_build_folder)
        self.open_folder_button.setVisible(False)
        self.stop_server_button = QPushButton("Stop Server")
        self.stop_server_button.clicked.connect(self._stop_server)
        self.stop_server_button.setVisible(False)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self._on_close)
        self.stop_export_button = QPushButton("Stop Export")
        self.stop_export_button.clicked.connect(self._stop_export)
        self.stop_export_button.setVisible(False)
        buttons.addWidget(self.export_button)
        buttons.addWidget(self.stop_export_button)
        buttons.addWidget(self.open_folder_button)
        buttons.addWidget(self.stop_server_button)
        buttons.addWidget(self.close_button)
        main_layout.addLayout(buttons)

        self._export_thread = None
        self._export_result = None
        self._export_error = None
        self._export_done = False
        self._export_cancelled = False
        self._last_output_path = None
        self._export_target_name = ""
        self._export_build_mode = ""
        self._export_output_path = ""
        self._current_exporter = None

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._check_export_done)

        self._sync_target_os_controls()
        self._on_target_changed(self.target_combo.currentText())

    def _host_desktop_os_label(self):
        current_os = platform.system().lower()
        if current_os == "darwin":
            return "macOS"
        if current_os == "windows":
            return "Windows"
        return "Linux"

    def _sync_target_os_controls(self):
        host_label = self._host_desktop_os_label()
        if self.desktop_pyinstaller_check.isChecked():
            self.desktop_target_os_combo.setCurrentText(host_label)
            self.desktop_target_os_combo.setEnabled(False)
        else:
            self.desktop_target_os_combo.setEnabled(True)

        if self.server_pyinstaller_check.isChecked():
            host_server = "Windows" if host_label == "Windows" else "Linux"
            self.server_target_os_combo.setCurrentText(host_server)
            self.server_target_os_combo.setEnabled(False)
        else:
            self.server_target_os_combo.setEnabled(True)

    def _on_target_changed(self, target_name: str):
        # Show/hide Mobile options
        self.mobile_format_row[0].setVisible(target_name == "Mobile")
        self.mobile_format_combo.setVisible(target_name == "Mobile")
        self.mobile_buildozer_row[0].setVisible(target_name == "Mobile")
        self.mobile_buildozer_check.setVisible(target_name == "Mobile")
        
        # Show/hide Desktop options
        self.desktop_target_os_row[0].setVisible(target_name == "Desktop")
        self.desktop_target_os_combo.setVisible(target_name == "Desktop")
        self.desktop_pyinstaller_row[0].setVisible(target_name == "Desktop")
        self.desktop_pyinstaller_check.setVisible(target_name == "Desktop")
        
        # Show/hide Server options
        self.server_target_os_row[0].setVisible(target_name == "Server")
        self.server_target_os_combo.setVisible(target_name == "Server")
        self.server_pyinstaller_row[0].setVisible(target_name == "Server")
        self.server_pyinstaller_check.setVisible(target_name == "Server")
        
        platform_name = target_name.lower()
        output_root = os.path.normpath(self.output_edit.text().strip() or os.path.join(self.project_path, "build"))
        if target_name == "Mobile":
            self.status_label.setText(f"Output path will be: {os.path.join(output_root, platform_name, 'android')}")
        elif target_name == "Desktop":
            os_name = self.desktop_target_os_combo.currentText().lower()
            msg = f"Output path will be: {os.path.join(output_root, platform_name, os_name)}"
            if self.desktop_pyinstaller_check.isChecked():
                msg += " | PyInstaller executable target is host OS only"
            self.status_label.setText(msg)
        elif target_name == "Server":
            os_name = self.server_target_os_combo.currentText().lower()
            msg = f"Output path will be: {os.path.join(output_root, platform_name, os_name)}"
            if self.server_pyinstaller_check.isChecked():
                msg += " | PyInstaller executable target is host OS only"
            self.status_label.setText(msg)
        else:
            self.status_label.setText(f"Output path will be: {os.path.join(output_root, platform_name)}")

    def _on_desktop_os_changed(self, os_name: str):
        labels = {"Windows": "Build .exe with PyInstaller", "Linux": "Build Linux binary with PyInstaller", "macOS": "Build .app bundle with PyInstaller"}
        self.desktop_pyinstaller_check.setText(labels.get(os_name, "Build executable with PyInstaller"))
        self._on_target_changed(self.target_combo.currentText())

    def _choose_output_folder(self):
        start_dir = self.output_edit.text().strip() or self.project_path
        chosen = QFileDialog.getExistingDirectory(self, "Choose Export Output Folder", start_dir)
        if chosen:
            self.output_edit.setText(os.path.normpath(chosen))
            self._on_target_changed(self.target_combo.currentText())

    def _run_export(self):
        target_name = self.target_combo.currentText()
        self._sync_target_os_controls()
        output_path = os.path.normpath(self.output_edit.text().strip())
        if not output_path:
            QMessageBox.warning(self, "Missing Output Folder", "Please choose an output folder.")
            return
        os.makedirs(output_path, exist_ok=True)
        build_mode = self.build_mode_combo.currentText()
        exporter_type = self._exporter_by_name[target_name]
        if target_name == "Mobile":
            output_format = self.mobile_format_combo.currentText().lower()
            exporter = exporter_type(build_mode=build_mode, output_format=output_format)
        elif target_name == "Desktop":
            desktop_target_os = self.desktop_target_os_combo.currentText().lower()
            exporter = exporter_type(build_mode=build_mode, target_os=desktop_target_os)
        elif target_name == "Server":
            server_target_os = self.server_target_os_combo.currentText().lower()
            exporter = exporter_type(build_mode=build_mode, target_os=server_target_os)
        else:
            exporter = exporter_type(build_mode=build_mode)

        self.export_button.setEnabled(False)
        self.stop_export_button.setVisible(True)
        self.open_folder_button.setVisible(False)
        self.status_label.setText("Exporting...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat("Exporting...")

        self._export_result = None
        self._export_error = None
        self._export_done = False
        self._export_cancelled = False
        self._current_exporter = exporter
        self._export_target_name = target_name
        self._export_build_mode = build_mode
        self._export_output_path = output_path

        def do_export():
            try:
                if target_name == "Mobile" and self.mobile_buildozer_check.isChecked() and hasattr(exporter, "export_with_buildozer"):
                    context = exporter.export_with_buildozer(self.project_path, output_path)
                elif target_name == "Web" and hasattr(exporter, "export_with_pygbag"):
                    context = exporter.export_with_pygbag(self.project_path, output_path)
                elif target_name == "Desktop" and self.desktop_pyinstaller_check.isChecked() and hasattr(exporter, "export_with_pyinstaller"):
                    context = exporter.export_with_pyinstaller(self.project_path, output_path)
                elif target_name == "Server" and self.server_pyinstaller_check.isChecked() and hasattr(exporter, "export_with_pyinstaller"):
                    context = exporter.export_with_pyinstaller(self.project_path, output_path)
                else:
                    context = exporter.export(self.project_path, output_path)
                self._export_result = context
            except ExportCancelled:
                self._export_cancelled = True
            except Exception as error:
                self._export_error = error
            finally:
                self._export_done = True

        self._export_thread = threading.Thread(target=do_export, daemon=True)
        self._export_thread.start()

        self._poll_timer.start(250)

    def _stop_export(self):
        if self._current_exporter is not None:
            self._current_exporter.cancelled.set()
        self.stop_export_button.setEnabled(False)
        self.status_label.setText("Cancelling...")

    def _check_export_done(self):
        if not self._export_done:
            return
        self._poll_timer.stop()
        self.progress_bar.setRange(0, 100)
        self.export_button.setEnabled(True)
        self.stop_export_button.setVisible(False)
        self.stop_export_button.setEnabled(True)
        self._current_exporter = None

        if self._export_cancelled:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Export cancelled")
            self.status_label.setText("Export cancelled by user.")
            self._logger.info("Export cancelled by user", target=self._export_target_name)
            return

        if self._export_error:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Export failed")
            self.status_label.setText(f"Failed: {self._export_error}")
            self._logger.error("Project export failed", target=self._export_target_name, output_path=self._export_output_path, error=str(self._export_error))
            QMessageBox.critical(self, "Export Failed", str(self._export_error))
            return

        context = self._export_result
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Export complete!")
        self._last_output_path = context.output_path
        self.status_label.setText(f"Done. Output: {context.output_path}")
        self.open_folder_button.setVisible(True)
        self._logger.info(
            "Project export completed",
            target=self._export_target_name,
            build_mode=self._export_build_mode,
            output_path=context.output_path
        )
        if self._export_target_name == "Web":
            self._start_web_preview(context)

    def _open_build_folder(self):
        folder = self._last_output_path or self.output_edit.text().strip()
        if not folder or not os.path.isdir(folder):
            folder = self.output_edit.text().strip()
        if folder and os.path.isdir(folder):
            system = platform.system()
            if system == "Windows":
                os.startfile(folder)
            elif system == "Darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])

    def _start_web_preview(self, context):
        web_dist = context.metadata.get("web_dist_path", context.output_path)
        if not os.path.isdir(web_dist):
            web_dist = context.output_path
        self._stop_server()
        port = 8000
        self._server_process = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port)],
            cwd=web_dist,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        url = f"http://127.0.0.1:{port}"
        self.status_label.setText(f"Server running at {url}  (PID {self._server_process.pid})")
        self.stop_server_button.setVisible(True)
        self._logger.info("Web preview server started", url=url, pid=self._server_process.pid, cwd=web_dist)
        self._open_browser_incognito(url)

    @staticmethod
    def _open_browser_incognito(url: str):
        system = platform.system()
        try:
            if system == "Windows":
                # Try Chrome first, then Edge, then fallback
                for browser_path, flag in [
                    (r"C:\Program Files\Google\Chrome\Application\chrome.exe", "--incognito"),
                    (r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe", "--incognito"),
                    (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "--inprivate"),
                    (r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", "--inprivate"),
                ]:
                    if os.path.exists(browser_path):
                        subprocess.Popen([browser_path, flag, url])
                        return
                webbrowser.open(url)
            elif system == "Darwin":
                subprocess.Popen(["open", "-na", "Google Chrome", "--args", "--incognito", url])
            else:
                subprocess.Popen(["google-chrome", "--incognito", url])
        except Exception:
            webbrowser.open(url)

    def _stop_server(self):
        if self._server_process and self._server_process.poll() is None:
            self._server_process.terminate()
            try:
                self._server_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._server_process.kill()
            self._logger.info("Web preview server stopped", pid=self._server_process.pid)
        self._server_process = None
        self.stop_server_button.setVisible(False)
        self.status_label.setText("Server stopped.")

    def _on_close(self):
        self._stop_server()
        self.reject()

    def closeEvent(self, event):
        self._stop_server()
        super().closeEvent(event)
