"""Environment helpers: locate the repo root and keep requirements.txt growing
as libraries are used, so the environment is reproducible from the repository."""
from __future__ import annotations

import importlib.metadata as md
import re
import sys
from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from `start` (default: cwd) until config.py is found, and put that
    directory on sys.path so `import config` and `from src import ...` work from
    notebooks/ locally or in Colab."""
    here = (start or Path.cwd()).resolve()
    for d in [here, *here.parents]:
        if (d / "config.py").exists():
            if str(d) not in sys.path:
                sys.path.insert(0, str(d))
            return d
    raise FileNotFoundError("config.py not found in any parent directory")


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def log_requirements(packages: list[str], req_file: Path, update: bool = False) -> list[str]:
    """Append `package==installed_version` to requirements.txt for every package
    not yet listed. Existing lines are left untouched unless update=True, in which
    case a listed package is re-pinned to the version installed now.

    `packages` are *distribution* names as used by pip (e.g. 'earthengine-api',
    'pillow'), not import names. Returns the lines that were added or changed."""
    req_file = Path(req_file)
    lines = req_file.read_text().splitlines() if req_file.exists() else []
    listed = {}
    for i, line in enumerate(lines):
        s = line.strip()
        if s and not s.startswith("#"):
            listed[_norm(re.split(r"[=<>!~\[ ;]", s, 1)[0])] = i

    changed = []
    for pkg in packages:
        try:
            pin = f"{pkg}=={md.version(pkg)}"
        except md.PackageNotFoundError:
            print(f"[requirements] {pkg} is not installed; skipped")
            continue
        key = _norm(pkg)
        if key not in listed:
            lines.append(pin)
            listed[key] = len(lines) - 1
            changed.append(pin)
        elif update and lines[listed[key]].strip() != pin:
            lines[listed[key]] = pin
            changed.append(pin)

    if changed:
        req_file.write_text("\n".join(lines) + "\n")
    print(f"[requirements] {len(changed)} line(s) written: {changed}" if changed
          else "[requirements] up to date")
    return changed
