#!/usr/bin/env python3
"""V5.1 enclosure, millimetres: X=width, Y=front, Z=up.
Seller drawings are the source. Connector/lead dimensions remain assumptions.
Run anywhere; outputs go beside this script. Screen installs BEFORE the board.
"""
from pathlib import Path
import json
import numpy as np
import trimesh

OUT = Path(__file__).resolve().parent
W, D, H = 76., 48., 74.
WALL, LEG_H = 2.4, 14.
FRONT, REAR = D / 2, -D / 2
INNER_X = W / 2 - WALL
FLOOR, CEILING = LEG_H + WALL, H - WALL
CLEARANCE = .30
# Portrait PCBA 32 x 43.72; rotate with header on right, centre active area.
SCREEN_W, SCREEN_L, PCB_T, MODULE_T = 32., 43.72, 1.2, 2.58
AA, AA_TOP, AA_SIDE, FACE_Z = 27.72, 6.45, 2.14, 48.
PCB_CX = -(SCREEN_L / 2 - AA_TOP - AA / 2)
PCB_X0, PCB_X1 = PCB_CX - SCREEN_L / 2, PCB_CX + SCREEN_L / 2
SCREEN_Z0 = FACE_Z - AA_SIDE - AA / 2
GLASS_FRONT = FRONT - WALL - .6
PCB_FRONT = GLASS_FRONT - (MODULE_T - PCB_T)
PCB_BACK = PCB_FRONT - PCB_T
WINDOW = 27.2  # Conceals glass border; masks .26 mm of active area per edge.
SCREEN_HOLES_X = (PCB_X0 + 2.5, PCB_X1 - 2.5)
SCREEN_HOLES_Z = (SCREEN_Z0 + 2.5, SCREEN_Z0 + SCREEN_W - 2.5)
PILOT_R = .85
# 53.34 = pin span; 57.15 = PCB; 2495.63 mil = antenna-inclusive envelope.
BOARD_L, BOARD_W, BOARD_PCB_L, BOARD_T = 2495.63 * .0254, 27.94, 57.15, 1.2
BOARD_X, BOARD_Y, BOARD_Z, PIN_BELOW, LEAD_ABOVE = 3.5, -5., 20., 2.6, 14.
USB_W, USB_H, USB_Z = BOARD_W + 4.4, 12., BOARD_Z + 2.2
BACK_HOLES_X, BACK_HOLES_Z = (-32.5, 32.5), (40., 67.5)
BACK_T, LIP_D, LIP_T = 2.4, 2., 1.4


def box(w, d, h, x=0, y=0, z=0):
    return trimesh.creation.box(extents=[w, d, h], transform=
        trimesh.transformations.translation_matrix([x, y, z + h / 2]))


def cylinder_y(x, y, z, r, length):
    m = trimesh.creation.cylinder(radius=r, height=length, sections=32)
    m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    m.apply_translation([x, y, z])
    return m


def union(parts):
    return trimesh.boolean.union(parts, engine='manifold')


def subtract(base, cuts):
    return trimesh.boolean.difference([base, *cuts], engine='manifold')


def rear_post_gusset(x, z):
    # With the face on the bed, height grows towards -Y. This wedge grows
    # from the sidewall at <=45 degrees and meets the rear post's first layer.
    side = 1 if x > 0 else -1
    outer_x = side * (INNER_X + .5)
    inner_x = x - side * 3.6
    run = abs(outer_x - inner_x)
    tip_y = REAR + 6 - .1
    pts = np.array([[outer_x, tip_y + run + .2, z - 3.6],
                    [outer_x, tip_y, z - 3.6],
                    [inner_x, tip_y, z - 3.6]])
    vertices = np.vstack([pts, pts + [0,0,7.2]])
    faces = [[0,1,2],[3,5,4],[0,3,4],[0,4,1],
             [1,4,5],[1,5,2],[2,5,3],[2,3,0]]
    m = trimesh.Trimesh(vertices=vertices, faces=faces)
    if m.volume < 0:
        m.invert()
    return m


def silhouette():
    parts = [box(W, D, H - LEG_H, z=LEG_H),
             box(10.2, D, 14, -42.9, z=30), box(10.2, D, 14, 42.9, z=30)]
    parts += [box(8, D, LEG_H + .2, x, z=0) for x in (-29, -16, 16, 29)]
    return union(parts)


def build_shell():
    cavity = box(2 * INNER_X, D - WALL + .2, CEILING - FLOOR,
                 y=-WALL / 2 - .1, z=FLOOR)
    shell = subtract(silhouette(), [cavity,
        box(WINDOW, WALL + 2, WINDOW, y=FRONT - WALL / 2, z=FACE_Z - WINDOW / 2),
        box(12, USB_W, USB_H, x=W / 2, y=BOARD_Y, z=USB_Z - USB_H / 2)])
    supports = [cylinder_y(x, (PCB_FRONT + FRONT) / 2, z, 2.3, FRONT - PCB_FRONT)
                for x in SCREEN_HOLES_X for z in SCREEN_HOLES_Z]
    supports += [cylinder_y(x, REAR + 3, z, 3.6, 6)
                 for x in BACK_HOLES_X for z in BACK_HOLES_Z]
    supports += [rear_post_gusset(x, z) for x in BACK_HOLES_X for z in BACK_HOLES_Z]
    supports += [box(12, 8, .8, BOARD_X + x, BOARD_Y, FLOOR) for x in (-12, 12)]
    shell = union([shell, *supports])
    pilots = [cylinder_y(x, (PCB_FRONT + 23.6) / 2, z, PILOT_R, 23.6 - PCB_FRONT + .02)
              for x in SCREEN_HOLES_X for z in SCREEN_HOLES_Z]
    pilots += [cylinder_y(x, REAR + 2.5, z, PILOT_R, 5.02)
               for x in BACK_HOLES_X for z in BACK_HOLES_Z]
    return subtract(shell, pilots)


def build_back():
    plate = box(W, BACK_T, H - LEG_H, y=REAR - BACK_T / 2, z=LEG_H)
    lw, lh = 2 * (INNER_X - CLEARANCE), CEILING - FLOOR - 2 * CLEARANCE
    lip = subtract(box(lw, LIP_D + .02, lh, y=REAR + LIP_D / 2 - .01,
                       z=FLOOR + CLEARANCE),
                   [box(lw - 2 * LIP_T, LIP_D + 2, lh - 2 * LIP_T,
                        y=REAR + 1, z=FLOOR + CLEARANCE + LIP_T)])
    lip = subtract(lip, [cylinder_y(x, REAR + 1, z, 4.0, 4)
                        for x in BACK_HOLES_X for z in BACK_HOLES_Z])
    return subtract(union([plate, lip]),
        [cylinder_y(x, REAR - .2, z, 1.15, 8)
         for x in BACK_HOLES_X for z in BACK_HOLES_Z] +
        [box(2, 10, 18, x=x, y=REAR, z=44) for x in (-12, -6, 0, 6, 12)])


def screen_parts():
    pcb = box(SCREEN_L, PCB_T, SCREEN_W, PCB_CX,
              (PCB_FRONT + PCB_BACK) / 2, SCREEN_Z0)
    pcb = subtract(pcb, [cylinder_y(x, PCB_FRONT, z, 1, 6)
                        for x in SCREEN_HOLES_X for z in SCREEN_HOLES_Z])
    gx = PCB_X1 - 5 - 33.72 / 2
    glass = box(33.72, MODULE_T - PCB_T, 31.52, gx,
                (GLASS_FRONT + PCB_FRONT) / 2, FACE_Z - 31.52 / 2)
    aa = box(AA, .04, AA, y=GLASS_FRONT + .02, z=FACE_Z - AA / 2)
    header = box(4.2, 16, 20.32, PCB_X1 - 1.5,
                 PCB_BACK - 8, SCREEN_Z0 + 5.84)
    return dict(screen_pcb=pcb, screen_glass=glass, screen_face=aa, screen_connector=header)


def board_parts():
    x0 = -BOARD_L / 2 + BOARD_L - BOARD_PCB_L
    pcb = box(BOARD_PCB_L, BOARD_W, BOARD_T, (x0 + BOARD_L / 2) / 2, BOARD_Y, BOARD_Z)
    antenna = box(BOARD_L - BOARD_PCB_L, 18, 3,
                  -BOARD_L / 2 + (BOARD_L - BOARD_PCB_L) / 2, BOARD_Y, BOARD_Z)
    leads = [box(53.34, 2.54, LEAD_ABOVE + BOARD_T + PIN_BELOW,
                 y=BOARD_Y + s * 12.7, z=BOARD_Z - PIN_BELOW) for s in (-1, 1)]
    radio = box(21, 17, 3, x=-12, y=BOARD_Y, z=BOARD_Z + BOARD_T)
    usbs = [box(7, 9, 3.2, x=BOARD_L / 2 - 3.5,
                y=BOARD_Y + s * 6, z=BOARD_Z + BOARD_T) for s in (-1, 1)]
    parts = dict(board_pcb=pcb, board_antenna=antenna, board_leads=union(leads),
                 board_radio=radio, board_usb=union(usbs))
    for m in parts.values():
        m.apply_translation([BOARD_X,0,0])
    return parts


def screws():
    parts = {}
    for i, (x, z) in enumerate((x, z) for x in SCREEN_HOLES_X for z in SCREEN_HOLES_Z):
        parts[f'screen_screw_{i}'] = union([cylinder_y(x, PCB_BACK - .7, z, 1.8, 1.4),
                                          cylinder_y(x, PCB_BACK + 2.5, z, .9, 5)])
    for i, (x, z) in enumerate((x, z) for x in BACK_HOLES_X for z in BACK_HOLES_Z):
        parts[f'back_screw_{i}'] = union([cylinder_y(x, REAR - BACK_T - .7, z, 1.8, 1.4),
                                        cylinder_y(x, REAR - BACK_T + 3, z, .9, 6)])
    return parts


COLORS = dict(front='#f18329', back='#eab16e', screen_pcb='#24629b',
              screen_glass='#161c23', screen_face='#101820', screen_connector='#766496',
              board_pcb='#299666', board_antenna='#183a2c', board_leads='#4a515f',
              board_radio='#b3bcc8', board_usb='#c5ced8')


def assembly_parts():
    parts = dict(front=build_shell(), back=build_back(), **screen_parts(), **board_parts(), **screws())
    for x in (-6.5, 6.5):
        parts[f'eye_{x}'] = box(2.4, .08, 8, x, GLASS_FRONT + .085, FACE_Z - 4)
    return parts


def overlap(a, b):
    if np.any(a.bounds[1] <= b.bounds[0]) or np.any(b.bounds[1] <= a.bounds[0]):
        return 0.
    m = trimesh.boolean.intersection([a, b], engine='manifold')
    if m is None or len(m.faces) == 0:
        return 0.
    # Touching solids can return degenerate faces with no enclosed volume.
    # Integrate volume alone, avoiding a centre-of-mass division by zero.
    t = m.triangles
    cross_x = t[:,1,1]*t[:,2,2]-t[:,1,2]*t[:,2,1]
    cross_y = t[:,1,2]*t[:,2,0]-t[:,1,0]*t[:,2,2]
    cross_z = t[:,1,0]*t[:,2,1]-t[:,1,1]*t[:,2,0]
    return abs(float(np.sum(t[:,0,0]*cross_x+t[:,0,1]*cross_y+t[:,0,2]*cross_z)/6))


def verify(parts):
    checks = []
    def check(name, passed, evidence):
        checks.append(dict(check=name, passed=bool(passed), evidence=evidence))
    for k in ('front', 'back'):
        m = parts[k]
        check(f'{k}: closed connected solid', m.is_volume and len(m.split()) == 1,
              dict(watertight=bool(m.is_watertight), components=len(m.split()),
                   bounds_mm=m.bounds.round(3).tolist(), volume_mm3=round(m.volume, 3)))
    pitch = [SCREEN_HOLES_X[1] - SCREEN_HOLES_X[0], SCREEN_HOLES_Z[1] - SCREEN_HOLES_Z[0]]
    check('screen hole pitch matches drawing', np.allclose(pitch, [38.72, 27]), pitch)
    check('window stays inside active area', 0 < WINDOW < AA,
          dict(AA_mm=AA, window_mm=WINDOW, mask_per_edge_mm=(AA - WINDOW) / 2))
    board_side_gaps = [INNER_X + BOARD_X - BOARD_L / 2,
                       INNER_X - BOARD_X - BOARD_L / 2]
    check('board includes antenna and fits', min(board_side_gaps) > .3,
          dict(board_mm=[BOARD_L, BOARD_W], cavity_width_mm=2 * INNER_X,
               side_clearances_mm=board_side_gaps))
    usb_recess = W / 2 - (BOARD_X + BOARD_L / 2)
    check('USB socket recess is reduced', 0 < usb_recess < 3,
          dict(recess_mm=round(usb_recess, 3), opening_mm=[USB_W, USB_H]))
    coupon = build_coupon()
    check('screen coupon: closed connected solid', coupon.is_volume and len(coupon.split()) == 1,
          dict(watertight=bool(coupon.is_watertight), components=len(coupon.split())))
    insertion_gap = SCREEN_Z0 + 5.84 - (BOARD_Z + BOARD_T + LEAD_ABOVE)
    check('screen plugs clear board plug envelope', insertion_gap > 2,
          dict(vertical_clearance_mm=round(insertion_gap, 3),
               board_plug_height_above_pcb_mm=LEAD_ABOVE, screen_plug_depth_mm=16))
    hw = [k for k in parts if (k.startswith('board_') or k.startswith('screen_')) and 'screw' not in k]
    for shell in ('front', 'back'):
        for k in hw + (['back'] if shell == 'front' else []):
            v = overlap(parts[shell], parts[k])
            check(f'{shell} / {k}: no collision', v < 1e-3, dict(intersection_mm3=round(v, 6)))
    for b in (k for k in hw if k.startswith('board_')):
        for s in (k for k in hw if k.startswith('screen_')):
            v = overlap(parts[b], parts[s])
            check(f'{b} / {s}: separate hardware', v < 1e-3, dict(intersection_mm3=round(v, 6)))
    ss = union([parts[k] for k in hw if k.startswith('screen_')])
    bs = union([parts[k] for k in hw if k.startswith('board_')])
    for label, moving, obstacles in [('screen first', ss, [parts['front']]),
            ('board second', bs, [parts['front'], ss]),
            ('cover last', parts['back'], [parts['front'], ss, bs])]:
        worst = 0.
        for dy in np.linspace(-80, 0, 81):
            moved = moving.copy()
            moved.apply_translation([0, dy, 0])
            worst = max(worst, *(overlap(moved, o) for o in obstacles))
        check(f'assembly sweep: {label}', worst < 1e-3,
              dict(sample_step_mm=1, max_intersection_mm3=round(worst, 6)))
    plug = box(18, USB_W - .4, 8, x=W / 2 + 1, y=BOARD_Y, z=USB_Z - 4)
    v = overlap(parts['front'], plug)
    check('USB plug corridor is open', v < 1e-3, dict(intersection_mm3=round(v, 6)))
    # Screw tips are checked separately from pilots: self-tapping threads
    # deliberately intersect the pilot bore but must not exit the front face.
    screen_tip = PCB_BACK + 5
    check('screen 5 mm screws stay inside front wall', screen_tip < FRONT - .4,
          dict(tip_y_mm=round(screen_tip,3), remaining_skin_mm=round(FRONT-screen_tip,3)))
    back_tip = REAR - BACK_T + 6
    check('back 6 mm screws stop inside rear posts', back_tip < REAR + 5,
          dict(tip_y_mm=round(back_tip,3), pilot_end_y_mm=REAR+5))
    gusset_run = (INNER_X+.5)-(abs(BACK_HOLES_X[0])-3.6)
    check('rear post print ramp is at most 45 degrees', gusset_run/(gusset_run+.2) <= 1,
          dict(lateral_extension_mm=round(gusset_run,3), print_height_mm=round(gusset_run+.2,3)))
    report = dict(version='V5.1', units='mm', all_geometry_checks_pass=all(c['passed'] for c in checks),
        checks=checks, not_verified=[
        'Seller drawings vs actual hardware dimensions; measure before final print.',
        'Actual connector heights, wire bends, adhesive and USB cable plug sizes.',
        'Printer tolerance and screw fit; print the small screen coupon first.',
        'Physical strength, heat and stability under cable pull.'])
    (OUT / 'fit_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    for c in checks:
        print(f"{'PASS' if c['passed'] else 'FAIL'} {c['check']}: {c['evidence']}")
    if not report['all_geometry_checks_pass']:
        raise RuntimeError('Geometry checks failed; do not release meshes.')
    return report


def build_coupon():
    slab = box(50, WALL, 37, PCB_CX, FRONT - WALL / 2, SCREEN_Z0 - 2.5)
    posts = [cylinder_y(x, (PCB_FRONT + FRONT) / 2, z, 2.3, FRONT - PCB_FRONT)
             for x in SCREEN_HOLES_X for z in SCREEN_HOLES_Z]
    return subtract(union([slab, *posts]), [
        box(WINDOW, 10, WINDOW, y=FRONT, z=FACE_Z - WINDOW / 2),
        *[cylinder_y(x, (PCB_FRONT + 23.6) / 2, z, PILOT_R, 23.6 - PCB_FRONT + .02)
          for x in SCREEN_HOLES_X for z in SCREEN_HOLES_Z]])


def build_usb_coupon():
    # Standalone aperture gauge, already lying flat on the print bed.
    # Verifies plastic plug-head clearance, not actual socket insertion depth.
    return subtract(box(USB_W + 8, USB_H + 8, WALL),
                    [box(USB_W, USB_H, WALL + 2, z=-1)])


def print_orientation(mesh, is_front):
    m = mesh.copy()
    m.apply_transform(trimesh.transformations.rotation_matrix(
        -np.pi / 2 if is_front else np.pi / 2, [1, 0, 0]))
    m.apply_translation(-m.bounds[0])
    return m


def main():
    parts = assembly_parts()
    verify(parts)
    parts['front'].export(OUT / 'agentpet_case_front.stl')
    parts['back'].export(OUT / 'agentpet_case_back.stl')
    fp = print_orientation(parts['front'], True)
    bp = print_orientation(parts['back'], False)
    fp.export(OUT / 'agentpet_case_front_print.stl')
    bp.export(OUT / 'agentpet_case_back_print.stl')
    bp.apply_translation([fp.bounds[1, 0] + 12, 0, 0])
    trimesh.util.concatenate([fp, bp]).export(OUT / 'agentpet_case_both.stl')
    print_orientation(build_coupon(), True).export(OUT / 'screen_fit_coupon.stl')
    usb_coupon = build_usb_coupon()
    usb_coupon.apply_translation(-usb_coupon.bounds[0])
    usb_coupon.export(OUT / 'usb_fit_coupon.stl')
    scene = trimesh.Scene()
    for k, m in parts.items():
        m = m.copy()
        m.visual.vertex_colors = trimesh.visual.color.hex_to_rgba(
            COLORS.get(k, '#66e0d0' if k.startswith('eye') else '#a6b0bd'))
        scene.add_geometry(m, node_name=k, geom_name=k)
    # glTF uses Y-up; preserve upright appearance in standard GLB viewers.
    scene.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
    scene.export(OUT / 'agentpet_assembly.glb')
    print('Saved validated V5.1 STL, print layouts, coupon and assembled GLB.')


if __name__ == '__main__':
    main()
