from __future__ import annotations

from pathlib import Path

import pytest

from mech.workspace import reject_symlinks, workspace_path, workspace_root


def test_workspace_root_uses_project_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    assert workspace_root() == tmp_path.resolve()


def test_workspace_path_allows_relative_path(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    assert workspace_path("drawings/board.dxf", root) == root / "drawings" / "board.dxf"


def test_workspace_path_rejects_traversal_and_absolute_outside_path(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    with pytest.raises(ValueError, match="outside the workspace"):
        workspace_path("../outside.dxf", root)
    with pytest.raises(ValueError, match="outside the workspace"):
        workspace_path(tmp_path / "outside.dxf", root)


def test_workspace_path_rejects_symlink_component(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="contains a symlink"):
        workspace_path("link/part.dxf", root)


def test_reject_symlinks_rejects_nested_output_link(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "link").symlink_to(tmp_path / "outside")

    with pytest.raises(ValueError, match="generated output path is a symlink"):
        reject_symlinks(output)
