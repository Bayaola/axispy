#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python scripts/build_pyinstaller.py --name AxisPyEngine --entrypoint main.py
