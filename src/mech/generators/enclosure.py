"""Two-piece clamshell enclosure generator.

Layout: the shell is an open-top box centred on XY with its floor at Z=0.
The lid closes the top. Screw lids are flat caps with corner clearance holes
over in-cavity bosses; snap lids carry a skirt ring that engages a groove in
the shell wall. All dimensions are millimetres.
"""

from __future__ import annotations

from typing import Any

from ..brief import DesignBrief, EnclosureSpec, Opening
from ..standards import thread
from .common import GeneratedDesign, GeneratedPart, ReferenceSolid, build123d

CUT_OVER_MM = 2.0  # extra prism depth beyond each wall face
SNAP_FIT_GAP_MM = 0.2  # radial gap between lid skirt and shell cavity
WELD_MM = 0.1  # overlap depth to keep unions off coincident faces


def standoff_geometry(hole_diameter_mm: float) -> tuple[float, float]:
    """(outer_diameter, pilot_diameter) for a board standoff.

    The pilot is the self-tapping/tap drill for the board screw: the board
    clearance hole minus 0.7 mm (e.g. a 3.2 mm M3 hole yields a 2.5 mm M3
    tap drill), never smaller than 1.0 mm.
    """
    pilot = max(1.0, hole_diameter_mm - 0.7)
    return hole_diameter_mm + 3.0, pilot


def _outer_solid(spec: EnclosureSpec, height_mm: float) -> Any:
    b = build123d()
    outer = b.Pos(0, 0, 0) * b.Box(
        spec.width_mm,
        spec.depth_mm,
        height_mm,
        align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN),
    )
    if spec.corner_radius_mm > 0:
        outer = b.fillet(outer.edges().filter_by(b.Axis.Z), spec.corner_radius_mm)
    return outer


def opening_prism(spec: EnclosureSpec, opening: Opening, shell_height: float) -> Any:
    b = build123d()
    depth = spec.wall_mm + CUT_OVER_MM
    if opening.face in ("top", "bottom"):
        z_center = spec.height_mm - spec.wall_mm / 2 if opening.face == "top" else spec.floor_mm / 2
        depth_z = (
            spec.wall_mm + CUT_OVER_MM if opening.face == "top" else spec.floor_mm + CUT_OVER_MM
        )
        if opening.kind == "rect":
            return b.Pos(opening.center_x_mm, opening.center_y_mm, z_center) * b.Box(
                opening.width_mm, opening.height_mm, depth_z
            )
        return b.Pos(opening.center_x_mm, opening.center_y_mm, z_center) * b.Cylinder(
            radius=opening.width_mm / 2, height=depth_z
        )
    z_world = spec.height_mm / 2 + opening.center_y_mm
    if opening.face in ("front", "back"):
        y_face = (
            -spec.depth_mm / 2 + spec.wall_mm / 2
            if opening.face == "front"
            else spec.depth_mm / 2 - spec.wall_mm / 2
        )
        if opening.kind == "rect":
            return b.Pos(opening.center_x_mm, y_face, z_world) * b.Box(
                opening.width_mm, depth, opening.height_mm
            )
        return b.Pos(opening.center_x_mm, y_face, z_world) * b.Cylinder(
            radius=opening.width_mm / 2,
            height=depth,
            rotation=(90, 0, 0),
        )
    x_face = (
        -spec.width_mm / 2 + spec.wall_mm / 2
        if opening.face == "left"
        else spec.width_mm / 2 - spec.wall_mm / 2
    )
    if opening.kind == "rect":
        return b.Pos(x_face, opening.center_x_mm, z_world) * b.Box(
            depth, opening.width_mm, opening.height_mm
        )
    return b.Pos(x_face, opening.center_x_mm, z_world) * b.Cylinder(
        radius=opening.width_mm / 2,
        height=depth,
        rotation=(0, 90, 0),
    )


def _vent_prisms(spec: EnclosureSpec) -> list[Any]:
    if spec.vent is None:
        return []
    b = build123d()
    vent = spec.vent
    face_w, _face_h = _vent_face_span(spec, vent.face)
    usable = face_w - 2 * vent.margin_mm
    count = max(1, int((usable - vent.slot_width_mm) // vent.slot_pitch_mm) + 1)
    start = -(count - 1) * vent.slot_pitch_mm / 2
    depth = spec.wall_mm + CUT_OVER_MM
    prisms: list[Any] = []
    for index in range(count):
        x = start + index * vent.slot_pitch_mm
        if vent.face == "top":
            prisms.append(
                b.Pos(x, 0, spec.height_mm - spec.wall_mm / 2)
                * b.Box(vent.slot_width_mm, vent.slot_length_mm, depth)
            )
        elif vent.face in ("front", "back"):
            y_face = (
                -spec.depth_mm / 2 + spec.wall_mm / 2
                if vent.face == "front"
                else spec.depth_mm / 2 - spec.wall_mm / 2
            )
            z_mid = spec.floor_mm + (spec.height_mm - spec.floor_mm) / 2
            prisms.append(
                b.Pos(x, y_face, z_mid) * b.Box(vent.slot_width_mm, depth, vent.slot_length_mm)
            )
        else:
            x_face = (
                -spec.width_mm / 2 + spec.wall_mm / 2
                if vent.face == "left"
                else spec.width_mm / 2 - spec.wall_mm / 2
            )
            z_mid = spec.floor_mm + (spec.height_mm - spec.floor_mm) / 2
            prisms.append(
                b.Pos(x_face, x, z_mid) * b.Box(depth, vent.slot_width_mm, vent.slot_length_mm)
            )
    return prisms


def _vent_face_span(spec: EnclosureSpec, face: str) -> tuple[float, float]:
    if face in ("front", "back"):
        return spec.width_mm, spec.height_mm - spec.floor_mm
    if face in ("left", "right"):
        return spec.depth_mm, spec.height_mm - spec.floor_mm
    return spec.width_mm, spec.depth_mm


def _build_shell(spec: EnclosureSpec, shell_height: float) -> Any:
    b = build123d()
    outer = _outer_solid(spec, shell_height)
    cavity = b.Pos(0, 0, spec.floor_mm) * b.Box(
        spec.width_mm - 2 * spec.wall_mm,
        spec.depth_mm - 2 * spec.wall_mm,
        shell_height - spec.floor_mm + 1.0,
        align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN),
    )
    shell = outer - cavity

    # Board standoffs and their blind pilot holes.
    if spec.board is not None:
        for hole in spec.board.mount_holes:
            od, pilot = standoff_geometry(hole.diameter_mm)
            standoff = b.Pos(hole.x_mm, hole.y_mm, spec.floor_mm - WELD_MM) * b.Cylinder(
                radius=od / 2,
                height=spec.standoff_height_mm + WELD_MM,
                align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN),
            )
            shell += standoff
            shell -= b.Pos(
                hole.x_mm,
                hole.y_mm,
                spec.floor_mm / 2,
            ) * b.Cylinder(
                radius=pilot / 2,
                height=spec.standoff_height_mm + spec.floor_mm / 2 + 0.1,
                align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN),
            )

    # Corner bosses for a screw lid.
    boss_positions = _boss_positions(spec)
    if spec.lid == "screw" and spec.screw is not None:
        tap = thread(spec.screw.size).minor_diameter_mm
        for x, y in boss_positions:
            boss_h = shell_height - spec.floor_mm
            shell += b.Pos(x, y, spec.floor_mm) * b.Cylinder(
                radius=spec.screw.boss_diameter_mm / 2,
                height=boss_h,
                align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN),
            )
            tap_depth = min(boss_h - 1.0, max(6.0, 2.5 * _nominal_thread_diameter(spec.screw.size)))
            shell -= b.Pos(x, y, shell_height - tap_depth) * b.Cylinder(
                radius=tap / 2,
                height=tap_depth + 0.1,
                align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN),
            )

    # Groove for a snap lid.
    if spec.lid == "snap":
        engage = _snap_engage_mm(spec)
        ridge_h = _snap_ridge_mm(spec)
        ridge_z = spec.height_mm - spec.wall_mm - engage / 2
        groove_d = _snap_ridge_mm(spec) + 0.1
        groove_h = ridge_h + 0.2
        w_in = spec.width_mm - 2 * spec.wall_mm
        d_in = spec.depth_mm - 2 * spec.wall_mm
        ring = b.Pos(0, 0, ridge_z) * (
            b.Box(w_in + 2 * groove_d, d_in + 2 * groove_d, groove_h)
            - b.Box(w_in, d_in, groove_h + 0.5)
        )
        shell -= ring

    # Openings through walls and the floor. Top-face openings belong to the
    # lid and are cut there.
    for opening in spec.openings:
        if opening.face in ("top",):
            continue
        shell -= opening_prism(spec, opening, shell_height)
    for prism in _vent_prisms(spec):
        if spec.vent is not None and spec.vent.face != "top":
            shell -= prism

    return shell


def _nominal_thread_diameter(designation: str) -> float:
    return float(designation.upper().lstrip("M"))


def _boss_positions(spec: EnclosureSpec) -> list[tuple[float, float]]:
    if spec.screw is None:
        return []
    radius = spec.screw.boss_diameter_mm / 2
    # Bosses are webbed to the walls: their OD must overlap the inner wall
    # face, because an exactly tangent union produces a non-manifold mesh.
    embed = min(0.4, radius / 4)
    x = spec.width_mm / 2 - spec.wall_mm - radius + embed
    y = spec.depth_mm / 2 - spec.wall_mm - radius + embed
    return [(x, y), (-x, y), (x, -y), (-x, -y)]


def _snap_engage_mm(spec: EnclosureSpec) -> float:
    return min(3.0, 1.5 * spec.wall_mm)


def _snap_ridge_mm(spec: EnclosureSpec) -> float:
    return min(0.6, 0.3 * spec.wall_mm)


def _build_lid(spec: EnclosureSpec) -> Any:
    b = build123d()
    plate = _outer_solid(spec, spec.wall_mm).located(b.Pos(0, 0, spec.height_mm - spec.wall_mm))
    lid = plate
    if spec.lid == "screw" and spec.screw is not None:
        clearance = thread(spec.screw.size).clearance_medium_mm
        for x, y in _boss_positions(spec):
            lid -= b.Pos(x, y, spec.height_mm - spec.wall_mm / 2) * b.Cylinder(
                radius=clearance / 2,
                height=spec.wall_mm + CUT_OVER_MM,
            )
    if spec.lid == "snap":
        engage = _snap_engage_mm(spec)
        ridge_h = _snap_ridge_mm(spec)
        fit = SNAP_FIT_GAP_MM
        skirt_t = max(0.8, 0.5 * spec.wall_mm)
        w_out = spec.width_mm - 2 * spec.wall_mm - 2 * fit
        d_out = spec.depth_mm - 2 * spec.wall_mm - 2 * fit
        skirt_bottom = spec.height_mm - spec.wall_mm - engage
        # Skirt welds WELD_MM into the lid plate so the union is not
        # coplanar (a tangent contact produces a non-manifold mesh).
        skirt = b.Pos(0, 0, skirt_bottom) * (
            b.Box(
                w_out,
                d_out,
                engage + WELD_MM,
                align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN),
            )
            - b.Pos(0, 0, -0.1)
            * b.Box(
                w_out - 2 * skirt_t,
                d_out - 2 * skirt_t,
                engage + WELD_MM + 0.2,
                align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN),
            )
        )
        lid += skirt
        ridge_z = spec.height_mm - spec.wall_mm - engage / 2
        ridge = b.Pos(0, 0, ridge_z) * (
            b.Box(w_out + 2 * ridge_h, d_out + 2 * ridge_h, ridge_h)
            - b.Box(w_out - 2 * WELD_MM, d_out - 2 * WELD_MM, ridge_h + 0.5)
        )
        lid += ridge
    for opening in spec.openings:
        if opening.face != "top":
            continue
        lid -= opening_prism(spec, opening, spec.height_mm)
    for prism in _vent_prisms(spec):
        if spec.vent is not None and spec.vent.face == "top":
            lid -= prism
    return lid


def _board_keepout(spec: EnclosureSpec) -> Any | None:
    if spec.board is None:
        return None
    b = build123d()
    board = spec.board
    z0 = spec.floor_mm + spec.standoff_height_mm
    return b.Pos(0, 0, z0) * b.Box(
        board.width_mm,
        board.depth_mm,
        board.thickness_mm + board.keepout_height_mm,
        align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN),
    )


def generate_enclosure(brief: DesignBrief) -> GeneratedDesign:
    spec = brief.enclosure
    if spec is None:
        raise ValueError("enclosure spec is missing")
    shell_height = spec.height_mm - spec.wall_mm
    shell = _build_shell(spec, shell_height)
    shell = _attach_features(brief, shell)
    lid = _build_lid(spec)
    parts = [
        GeneratedPart("shell", shell),
        GeneratedPart("lid", lid),
    ]
    references: list[ReferenceSolid] = []
    keepout = _board_keepout(spec)
    if keepout is not None:
        references.append(ReferenceSolid("board_keepout", keepout))
    return GeneratedDesign(
        parts=parts,
        references=references,
        provenance={
            "generator": "enclosure",
            "shell_height_mm": shell_height,
            "lid_fastening": spec.lid,
        },
    )


def _attach_features(brief: DesignBrief, shell: Any) -> Any:
    """Attach modeled mechanism features to the shell solid."""
    from .features import attach_boss, attach_rib, attach_snap_fit

    spec = brief.enclosure
    if spec is None:
        return shell
    for feature in brief.mechanism_features:
        if feature.mount != "shell":
            continue
        if feature.type == "snap_fit":
            shell += attach_snap_fit(feature, spec)
        elif feature.type == "rib":
            shell += attach_rib(feature, spec)
        elif feature.type == "boss":
            shell += attach_boss(feature, spec)
    return shell
