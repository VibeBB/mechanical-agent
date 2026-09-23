from __future__ import annotations

from scripts.check_dependency_updates import (
    project_dependencies,
    uv_version_pin,
    workflow_files,
)


def test_project_dependencies_parsed():
    deps = dict(project_dependencies())
    assert "build123d" in deps
    assert deps["build123d"] == "0.11.1"
    assert "openhands-sdk" in deps
    assert deps["openhands-sdk"] == "1.49.4"
    assert "pytest" in deps


def test_uv_pin_parsed():
    assert uv_version_pin() == "==0.12.18"


def test_workflow_files_have_expected_suffixes():
    files = workflow_files()
    assert all(f.suffix in {".yml", ".yaml"} for f in files)
