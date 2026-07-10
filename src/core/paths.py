"""App paths — gumagana sa dev mode AT sa PyInstaller frozen exe.

Sa dev mode: project root = dalawang folder pataas mula dito.
Sa frozen exe (PyInstaller onefile): ang __file__ ay nasa temp extraction
dir (_MEIPASS) na nabubura pagsara — kaya ang data/ ay dapat nasa TABI ng
.exe mismo para hindi mawala ang database at logs.
"""
from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


DATA_DIR = app_root() / "data"
