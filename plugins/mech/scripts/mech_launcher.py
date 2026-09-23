"""Resolve the mech package that matches the installed plugin, then exec.

Plugin installs update the assets under plugins/mech but do not reinstall
the `mech` Python package, so `python3 -m mech.*` may import a stale
site-packages copy that lacks the tools the assets expect. This launcher
points PYTHONPATH at a source tree consistent with the plugin before execing
the requested module.

Resolution order (first directory containing mech/__init__.py wins):
  1. $MECH_SRC
  2. newest ~/.openhands/cache/extensions/mechanical-agent-*/src
  3. /opt/mech/src (mech-server image)
  4. <repo>/src when running from a repository checkout
  5. none found -> fall back to the already-installed package
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_MODULES = {"mcp_server": "mech.mcp_server", "doctor": "mech.cli"}


def _candidates(plugin_root: Path) -> list[Path]:
    candidates: list[Path] = []
    env_src = os.environ.get("MECH_SRC")
    if env_src:
        candidates.append(Path(env_src))
    cache = Path.home() / ".openhands" / "cache" / "extensions"
    try:
        if cache.is_dir():
            candidates.extend(
                sorted(
                    cache.glob("mechanical-agent-*/src"),
                    key=lambda path: path.stat().st_mtime,
                    reverse=True,
                )
            )
    except OSError:
        pass
    candidates.append(Path("/opt/mech/src"))
    candidates.append(plugin_root.parent.parent / "src")
    return candidates


def resolve_source(plugin_root: Path) -> Path | None:
    for candidate in _candidates(plugin_root):
        try:
            if (candidate / "mech" / "__init__.py").is_file():
                return candidate.resolve()
        except OSError:
            continue
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("module", choices=sorted(_MODULES))
    parser.add_argument("args", nargs=argparse.REMAINDER)
    ns = parser.parse_args()

    plugin_root = Path(__file__).resolve().parent.parent
    source = resolve_source(plugin_root)
    if source is not None:
        python_path = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = (
            f"{source}{os.pathsep}{python_path}" if python_path else str(source)
        )

    if ns.module == "doctor":
        argv = [sys.executable, "-m", "mech.cli", "doctor", *ns.args]
    else:
        argv = [sys.executable, "-m", _MODULES[ns.module], *ns.args]
    os.execvpe(sys.executable, argv, os.environ)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
