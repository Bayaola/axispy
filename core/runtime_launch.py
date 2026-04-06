from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
import os
import subprocess
import sys
from typing import Any


@dataclass
class LaunchProfile:
    module: str = "core.player"
    scene_file_name: str = "temp_scene.scn"
    working_directory: str = ""
    report_directory: str = ""
    python_executable: str = ""
    extra_args: list[str] = field(default_factory=list)
    python_path_entries: list[str] = field(default_factory=list)
    env_overrides: dict[str, str] = field(default_factory=dict)


@dataclass
class LaunchHandle:
    process: subprocess.Popen
    command: list[str]
    scene_path: str
    report_stdout_path: str
    report_stderr_path: str
    _stdout_file: Any = field(default=None, repr=False)
    _stderr_file: Any = field(default=None, repr=False)
    use_pipe: bool = field(default=False, repr=False)

    def close_logs(self):
        """Close the log file handles. Safe to call multiple times."""
        if not self.use_pipe:
            for f in (self._stdout_file, self._stderr_file):
                if f and not f.closed:
                    try:
                        f.close()
                    except Exception:
                        pass
        self._stdout_file = None
        self._stderr_file = None


class RuntimeCommandBuilder:
    @staticmethod
    def _resolve_working_directory(profile: LaunchProfile):
        if profile.working_directory:
            return os.path.abspath(os.path.normpath(profile.working_directory))
        return os.getcwd()

    @staticmethod
    def _resolve_report_directory(profile: LaunchProfile, working_directory: str):
        if profile.report_directory:
            report_dir = profile.report_directory
        else:
            report_dir = os.path.join(working_directory, ".axispy", "reports")
        report_dir = os.path.abspath(os.path.normpath(report_dir))
        os.makedirs(report_dir, exist_ok=True)
        return report_dir

    @staticmethod
    def _timestamp():
        return datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")

    @classmethod
    def build_command(cls, profile: LaunchProfile, scene_path: str):
        python_exec = profile.python_executable or sys.executable
        current_executable = os.path.abspath(sys.executable)
        target_executable = os.path.abspath(python_exec)
        if getattr(sys, "frozen", False) and target_executable == current_executable:
            cmd = [python_exec, "--axispy-module", profile.module, scene_path]
        else:
            cmd = [python_exec, "-u", "-m", profile.module, scene_path]  # Add -u for unbuffered output
        if profile.extra_args:
            cmd.extend([str(arg) for arg in profile.extra_args])
        return cmd

    @classmethod
    def launch(cls, profile: LaunchProfile, scene_data: str, use_pipe: bool = False):
        working_directory = cls._resolve_working_directory(profile)
        os.makedirs(working_directory, exist_ok=True)
        scene_path = os.path.join(working_directory, profile.scene_file_name)
        with open(scene_path, "w", encoding="utf-8") as file:
            file.write(scene_data)

        report_dir = cls._resolve_report_directory(profile, working_directory)
        timestamp = cls._timestamp()
        stdout_path = os.path.join(report_dir, f"runtime-{timestamp}.out.log")
        stderr_path = os.path.join(report_dir, f"runtime-{timestamp}.err.log")
        env = os.environ.copy()
        python_paths = []
        existing_pythonpath = env.get("PYTHONPATH", "")
        if existing_pythonpath:
            python_paths.extend([part for part in existing_pythonpath.split(os.pathsep) if part])
        for entry in profile.python_path_entries:
            normalized_entry = os.path.abspath(os.path.normpath(str(entry)))
            if normalized_entry not in python_paths:
                python_paths.append(normalized_entry)
        if python_paths:
            env["PYTHONPATH"] = os.pathsep.join(python_paths)
        if profile.env_overrides:
            for key, value in profile.env_overrides.items():
                env[str(key)] = str(value)
        command = cls.build_command(profile, scene_path)
        
        if use_pipe:
            # Use PIPE for real-time streaming
            process = subprocess.Popen(
                command,
                cwd=working_directory,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True,
                bufsize=1  # Line buffered
            )
            stdout_handle = None
            stderr_handle = None
        else:
            # Use file handles (original behavior)
            stdout_handle = open(stdout_path, "w", encoding="utf-8")
            stderr_handle = open(stderr_path, "w", encoding="utf-8")
            process = subprocess.Popen(
                command,
                cwd=working_directory,
                env=env,
                stdout=stdout_handle,
                stderr=stderr_handle
            )
            
        return LaunchHandle(
            process=process,
            command=command,
            scene_path=scene_path,
            report_stdout_path=stdout_path,
            report_stderr_path=stderr_path,
            _stdout_file=stdout_handle,
            _stderr_file=stderr_handle,
            use_pipe=use_pipe
        )
