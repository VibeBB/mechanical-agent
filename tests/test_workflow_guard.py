"""Structural guards for the CI invariants the 2026-10 workflow audit found.

The defects it caught — a CIS aggregator that silently read the wrong JSON
level, a recurring workflow missing from the main-failure watchlist, and a
coverage-flag drift between ci.yml and verify_all — are all mechanically
checkable, so they get a regression test here instead of another audit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
WATCHER = "main-ci-failure-issue.yml"


def _load(name: str) -> dict[Any, Any]:
    # YAML keys are not necessarily strings: PyYAML parses the bare `on:`
    # key as boolean True (YAML 1.1).
    data: dict[Any, Any] = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    return data


def _on(data: dict[Any, Any]) -> dict[Any, Any]:
    on: dict[Any, Any] = data.get("on") or data.get(True) or {}
    return on


def _workflow_files() -> list[Path]:
    return sorted(WORKFLOWS.glob("*.yml"))


def test_every_workflow_declares_permissions_concurrency_and_timeouts() -> None:
    for path in _workflow_files():
        data = _load(path.name)
        assert "permissions" in data, f"{path.name}: missing top-level permissions"
        assert "concurrency" in data, f"{path.name}: missing concurrency block"
        jobs: dict[Any, Any] = data.get("jobs") or {}
        for job_name, job in jobs.items():
            if "uses" in job:  # reusable-workflow call, no runner of its own
                continue
            assert "timeout-minutes" in job, f"{path.name}:{job_name} missing timeout-minutes"


def _runs_on_main(on: dict[Any, Any]) -> bool:
    if "schedule" in on or "workflow_dispatch" in on:
        return True
    push: dict[Any, Any] = on.get("push") or {}
    return "main" in (push.get("branches") or [])


def test_failure_watchlist_covers_every_main_workflow() -> None:
    watcher = _load(WATCHER)
    watched: set[str] = set(_on(watcher)["workflow_run"]["workflows"])
    expected: set[str] = set()
    for path in _workflow_files():
        if path.name == WATCHER:
            continue
        data = _load(path.name)
        if _runs_on_main(_on(data)):
            expected.add(data["name"])
    assert watched == expected, (
        f"{WATCHER} watchlist drift: missing {sorted(expected - watched)}, "
        f"extra {sorted(watched - expected)}"
    )


def test_container_audit_cis_aggregation_walks_nested_results_and_fails_loud() -> None:
    text = (WORKFLOWS / "container-audit.yml").read_text(encoding="utf-8")
    script = (ROOT / "scripts/container_hardening_report.py").read_text(encoding="utf-8")
    # The CIS scan exits 0 even on an empty payload, so the workflow must
    # gate the report on a non-empty payload check, with one retry.
    assert "--check-cis trivy-cis.json" in text
    assert "empty payload; retrying once" in text
    assert "python3 scripts/container_hardening_report.py" in text
    # trivy --compliance nests MisconfSummary under Results[].Results[]; a
    # flat read silently reports 0/0, so the aggregator must recurse and
    # must fail when the scan produced nothing.
    assert "def _summaries(node" in script
    assert "yield from _summaries(child)" in script
    assert 'sys.exit("Docker CIS scan produced no results")' in script


def test_publish_never_pushes_latest_before_the_trivy_gate() -> None:
    data = _load("publish-mech-images.yml")
    steps: list[dict[Any, Any]] = data["jobs"]["publish"]["steps"]
    for step in steps:
        if "docker/build-push-action" in (step.get("uses") or ""):
            with_block: dict[Any, Any] = step.get("with") or {}
            tags: str = with_block.get("tags") or ""
            assert ":latest" not in tags, "build-push must push immutable tags only"
    promote = [s for s in steps if s.get("name") == "Promote :latest"]
    assert promote, "publish must promote :latest explicitly after the gates"
    assert "imagetools create" in promote[0]["run"]
    gate = next(
        i for i, s in enumerate(steps) if s.get("name") == "Scan server image (Trivy SARIF)"
    )
    after = next(i for i, s in enumerate(steps) if s.get("name") == "Promote :latest")
    assert gate < after, ":latest must be promoted only after the Trivy gate"


def test_ci_pytest_enforces_the_coverage_floor() -> None:
    data = _load("ci.yml")
    steps: list[dict[Any, Any]] = data["jobs"]["verify"]["steps"]
    pytest_step = next(s for s in steps if (s.get("run") or "").startswith("uv run pytest"))
    run: str = pytest_step.get("run") or ""
    assert "--cov" in run, (
        "ci.yml must run pytest with the same --cov flags as verify_all "
        "so the [tool.coverage.report] fail_under floor gates CI"
    )


def test_publish_dispatch_is_limited_to_main() -> None:
    data = _load("publish-mech-images.yml")
    job: dict[Any, Any] = data["jobs"]["publish"]
    assert job.get("if") == "github.ref == 'refs/heads/main'"
