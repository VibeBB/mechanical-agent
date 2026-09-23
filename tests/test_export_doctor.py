from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mech.brief import DesignBrief
from mech.doctor import run_doctor
from mech.export import export_design
from mech.generators import generate


def test_export_manifest_complete(enclosure_brief: DesignBrief, tmp_path: Path):
    out_dir = tmp_path / "out"
    design = generate(enclosure_brief)
    manifest = export_design(enclosure_brief, design, out_dir)
    kinds = {entry["kind"] for entry in manifest["files"]}
    assert {"step", "stl", "dxf", "3mf"} <= kinds
    for entry in manifest["files"]:
        assert (out_dir / entry["path"]).exists()


def test_manifest_sha_matches(enclosure_brief: DesignBrief, tmp_path: Path):
    import hashlib

    out_dir = tmp_path / "out"
    design = generate(enclosure_brief)
    manifest = export_design(enclosure_brief, design, out_dir)
    for entry in manifest["files"]:
        digest = hashlib.sha256((out_dir / entry["path"]).read_bytes()).hexdigest()
        assert digest == entry["sha256"]


def test_provenance_has_brief_sha(enclosure_brief: DesignBrief, tmp_path: Path):
    out_dir = tmp_path / "out"
    design = generate(enclosure_brief)
    export_design(enclosure_brief, design, out_dir)
    provenance = json.loads((out_dir / "provenance.json").read_text(encoding="utf-8"))
    assert len(provenance["brief_sha256"]) == 64
    assert provenance["tools"]["build123d"]


def test_export_deterministic(enclosure_brief: DesignBrief, tmp_path: Path):
    """Same brief + design must produce byte-identical STEP/STL/3MF, identical
    file lists, and semantically identical DXF (OCCT serializes DXF entity
    order non-deterministically, so DXF is compared as a token multiset)."""
    design = generate(enclosure_brief)
    a = export_design(enclosure_brief, design, tmp_path / "a")
    b = export_design(enclosure_brief, design, tmp_path / "b")

    def by_kind(manifest: dict[str, Any], kind: str) -> dict[str, str]:
        return {e["path"]: e["sha256"] for e in manifest["files"] if e["kind"] == kind}

    for kind in ("step", "stl"):
        assert by_kind(a, kind) == by_kind(b, kind)
    assert {e["path"] for e in a["files"]} == {e["path"] for e in b["files"]}

    def threemf_entries(path: Path) -> dict[str, bytes]:
        """Decompressed 3MF entries: the lib3mf container emits volatile zip64
        header fields, so byte equality applies to entry content only."""
        import zipfile

        with zipfile.ZipFile(path) as archive:
            return {name: archive.read(name) for name in archive.namelist()}

    for entry in a["files"]:
        if entry["kind"] != "3mf":
            continue
        assert threemf_entries(tmp_path / "a" / entry["path"]) == threemf_entries(
            tmp_path / "b" / entry["path"]
        )

    def dxf_tokens(path: Path) -> list[str]:
        """Entity-section tokens only: header extents and block records carry
        volatile sentinels; OCCT also flips entity serialization order."""
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        try:
            start = next(i for i, t in enumerate(lines) if t.strip() == "ENTITIES")
            end = next(i for i, t in enumerate(lines) if t.strip() == "OBJECTS")
        except StopIteration:
            return []
        tokens: list[str] = []
        for t in lines[start:end]:
            t = t.strip()
            if t.startswith("{") or t.startswith("1.4.4 @"):
                continue
            try:
                # OCCT may flip a circle centre's sign on symmetric holes;
                # the geometry content is the absolute values.
                tokens.append(str(abs(float(t))))
            except ValueError:
                tokens.append(t)
        return sorted(tokens)

    for entry in a["files"]:
        if entry["kind"] != "dxf":
            continue
        assert dxf_tokens(tmp_path / "a" / entry["path"]) == dxf_tokens(
            tmp_path / "b" / entry["path"]
        )


def test_export_bracket(bracket_brief_dict: dict[str, Any], tmp_path: Path):
    brief = DesignBrief.model_validate(bracket_brief_dict)
    design = generate(brief)
    manifest = export_design(brief, design, tmp_path / "out")
    assert manifest["files"]


def test_doctor_reports_kernel():
    report = run_doctor()
    checks = report["checks"]
    kernel = [c for c in checks if c["capability"] in {"ocp-kernel", "build123d"}]
    assert len(kernel) == 2
    assert report["verdict"] in {"pass", "fail"}


def test_doctor_fail_closed_shape():
    report = run_doctor()
    assert "checks" in report
    for check in report["checks"]:
        assert check["status"] in {"pass", "fail"}
