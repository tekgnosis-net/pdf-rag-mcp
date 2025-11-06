#!/usr/bin/env python3
"""Synchronise project version numbers for semantic-release."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = ROOT / "pyproject.toml"
FRONTEND_PACKAGE = ROOT / "src" / "frontend" / "package.json"
FRONTEND_LOCK = ROOT / "src" / "frontend" / "package-lock.json"
RELEASE_PACKAGE = ROOT / "package.json"
RELEASE_LOCK = ROOT / "package-lock.json"


PROJECT_VERSION_PATTERN = re.compile(r'(?ms)(\[project\].*?^version\s*=\s*")([^"]+)(".*$)')


def update_pyproject(version: str) -> None:
    text = PYPROJECT_PATH.read_text(encoding="utf-8") if PYPROJECT_PATH.exists() else ""
    if "[project]" not in text:
        text = (
            "[project]\n"
            "name = \"pdf-rag-mcp\"\n"
            f"version = \"{version}\"\n\n"
        ) + text.lstrip()
    else:
        def _replace(match: re.Match[str]) -> str:
            prefix, _current, suffix = match.groups()
            return f"{prefix}{version}{suffix}"

        text, count = PROJECT_VERSION_PATTERN.subn(_replace, text, count=1)
        if count == 0:
            raise ValueError("Unable to locate [project] version field in pyproject.toml")
    PYPROJECT_PATH.write_text(text, encoding="utf-8")


def update_package_json(path: Path, version: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        raise SystemExit("Usage: update_version.py <version>")
    version = argv[1]
    update_pyproject(version)
    update_package_json(FRONTEND_PACKAGE, version)
    if FRONTEND_LOCK.exists():
        lock_data = json.loads(FRONTEND_LOCK.read_text(encoding="utf-8"))
        lock_data["version"] = version
        packages = lock_data.get("packages")
        if isinstance(packages, dict) and "" in packages:
            packages[""]["version"] = version
        FRONTEND_LOCK.write_text(json.dumps(lock_data, indent=2) + "\n", encoding="utf-8")
    update_package_json(RELEASE_PACKAGE, version)
    if RELEASE_LOCK.exists():
        data = json.loads(RELEASE_LOCK.read_text(encoding="utf-8"))
        data["version"] = version
        packages = data.get("packages")
        if isinstance(packages, dict) and "" in packages:
            packages[""]["version"] = version
        RELEASE_LOCK.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv)
