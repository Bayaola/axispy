from __future__ import annotations

import argparse
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path


def _run(command: list[str], cwd: Path):
    print(" ".join(command))
    completed = subprocess.run(command, cwd=str(cwd), check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def _platform_tag() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin":
        system = "macos"
    elif system == "windows":
        system = "windows"
    elif system == "linux":
        system = "linux"
    return f"{system}-{machine}"


def _resolve_build_output(dist_dir: Path, app_name: str) -> Path:
    system = platform.system().lower()
    candidates: list[Path] = []
    if system == "darwin":
        candidates.append(dist_dir / f"{app_name}.app")
    elif system == "windows":
        candidates.append(dist_dir / f"{app_name}.exe")
        candidates.append(dist_dir / app_name / f"{app_name}.exe")
        candidates.append(dist_dir / app_name)
    else:
        candidates.append(dist_dir / app_name)
        candidates.append(dist_dir / app_name / app_name)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise RuntimeError(
        "Expected build output not found. Checked: "
        + ", ".join(str(path) for path in candidates)
    )


def _archive_folder(source: Path, output_file: Path):
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if output_file.suffix == ".zip":
        with zipfile.ZipFile(output_file, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            if source.is_file():
                zipf.write(source, source.name)
            else:
                for path in source.rglob("*"):
                    zipf.write(path, path.relative_to(source.parent))
        return
    with tarfile.open(output_file, "w:gz") as tarf:
        tarf.add(source, arcname=source.name)


def _resolve_archive_source(build_output: Path) -> Path:
    if build_output.is_dir():
        return build_output
    if build_output.is_file():
        parent = build_output.parent
        if (parent / "_internal").exists():
            return parent
    return build_output


def _resolve_default_icon(project_root: Path) -> Path | None:
    assets = project_root / "editor" / "ui" / "assets" / "images"
    system = platform.system().lower()
    if system == "darwin":
        icns = assets / "icon.icns"
        return icns if icns.exists() else None
    preferred = [
        assets / "icon_256.ico",
        assets / "icon_128.ico",
        assets / "icon_64.ico",
        assets / "icon_48.ico",
        assets / "icon_32.ico",
        assets / "icon_16.ico",
        assets / "icon.ico",
        assets / "icon.png",
    ]
    for candidate in preferred:
        if candidate.exists():
            return candidate
    return None


def _collectable_packages() -> list[str]:
    candidates = [
        "pygame",
        "PyQt6",
        "PIL",
        "pygbag",
        "PyInstaller",
        "websockets",
        "webview",
        "aiortc",
        "buildozer",
        "qtawesome",
    ]
    available: list[str] = []
    for name in candidates:
        if importlib.util.find_spec(name) is not None:
            available.append(name)
    return available


def build(app_name: str, entrypoint: str, project_root: Path, icon: str | None = None, version: str | None = None):
    build_root = project_root / "build" / "pyinstaller"
    dist_dir = build_root / "dist"
    work_dir = build_root / "work"
    spec_dir = build_root / "spec"
    release_dir = project_root / "build" / "release"

    if build_root.exists():
        shutil.rmtree(build_root)
    build_root.mkdir(parents=True, exist_ok=True)

    path_sep = os.pathsep
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        app_name,
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        "--specpath",
        str(spec_dir),
        "--paths",
        str(project_root),
        "--add-data",
        f"{project_root / 'core'}{path_sep}core",
        "--add-data",
        f"{project_root / 'editor'}{path_sep}editor",
        "--add-data",
        f"{project_root / 'export'}{path_sep}export",
        "--add-data",
        f"{project_root / 'plugins'}{path_sep}plugins",
        "--hidden-import",
        "PyQt6.Qsci",
        "--exclude-module",
        "PyQt5",
        "--exclude-module",
        "PySide2",
        "--exclude-module",
        "PySide6",
    ]
    for package_name in _collectable_packages():
        command.extend(["--collect-all", package_name])
    icon_path = Path(icon) if icon else _resolve_default_icon(project_root)
    if icon_path is not None and icon_path.exists():
        command.extend(["--icon", str(icon_path)])
    command.append(str(project_root / entrypoint))

    _run(command, project_root)

    built = _resolve_build_output(dist_dir, app_name)

    platform_tag = _platform_tag()
    version_suffix = f"-{version}" if version else ""
    if platform.system().lower() == "windows":
        archive = release_dir / f"{app_name}{version_suffix}-{platform_tag}.zip"
    else:
        archive = release_dir / f"{app_name}{version_suffix}-{platform_tag}.tar.gz"

    archive_source = _resolve_archive_source(built)
    print("packaging release archive in progress...")
    _archive_folder(archive_source, archive)
    print(f"packaging is complete! The result is available in {archive}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="AxisPyEngine")
    parser.add_argument("--entrypoint", default="main.py")
    parser.add_argument("--icon", default=None)
    parser.add_argument("--version", default=None)
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    build(args.name, args.entrypoint, project_root, icon=args.icon, version=args.version)


if __name__ == "__main__":
    main()
