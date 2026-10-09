#!/usr/bin/env python3
"""Inspect the saved STL/GLB files independently of the build-time checks."""
import json
from pathlib import Path
import numpy as np
import trimesh
import build_case as B

OUT = Path(__file__).resolve().parent
checks=[]
def check(name, passed, evidence):
    checks.append(dict(check=name, passed=bool(passed), evidence=evidence))

names=['agentpet_case_front.stl','agentpet_case_back.stl',
       'agentpet_case_front_print.stl','agentpet_case_back_print.stl',
       'agentpet_case_both.stl','screen_fit_coupon.stl','usb_fit_coupon.stl']
meshes={name:trimesh.load_mesh(OUT/name) for name in names}
for name,m in meshes.items():
    count=len(m.split())
    check(name+': valid saved mesh', m.is_volume and count==(2 if 'both' in name else 1)
          and np.isfinite(m.vertices).all(),
          dict(watertight=bool(m.is_watertight), components=count,
               size_mm=m.extents.round(3).tolist()))
    if '_print' in name or 'coupon' in name or 'both' in name:
        check(name+': on bed', abs(m.bounds[0,2])<1e-5,
              dict(min_z_mm=float(m.bounds[0,2])))
front=meshes['agentpet_case_front.stl']; back=meshes['agentpet_case_back.stl']
check('saved enclosure pair has no overlap',B.overlap(front,back)<1e-4,{})
for axis in (0,2):
    for delta in (-.28,.28):
        m=back.copy();shift=np.zeros(3);shift[axis]=delta;m.apply_translation(shift)
        v=B.overlap(front,m)
        check(f'cover tolerance axis {axis}, shift {delta} mm',v<1e-4,
              dict(intersection_mm3=round(v,6)))
usb_probe=B.box(4,B.USB_W-.2,B.USB_H-.2,x=B.W/2-B.WALL/2,
                y=B.BOARD_Y,z=B.USB_Z-(B.USB_H-.2)/2)
check('saved USB aperture is clear',B.overlap(front,usb_probe)<1e-4,
      dict(opening_mm=[B.USB_W,B.USB_H]))
window_probe=B.box(B.WINDOW-.2,8,B.WINDOW-.2,y=B.FRONT-1,
                   z=B.FACE_Z-(B.WINDOW-.2)/2)
check('saved face aperture is clear',B.overlap(front,window_probe)<1e-4,
      dict(window_mm=B.WINDOW))
for x in B.SCREEN_HOLES_X:
    for z in B.SCREEN_HOLES_Z:
        pilot=B.cylinder_y(x,(B.PCB_FRONT+23.5)/2,z,.75,23.5-B.PCB_FRONT)
        skin=B.cylinder_y(x,23.85,z,.7,.2)
        check(f'screen pilot ({x:.2f}, {z:.2f}): clear and blind',
              B.overlap(front,pilot)<1e-4 and B.overlap(front,skin)>.999*skin.volume,
              dict(remaining_front_skin_mm=.39))
scene=trimesh.load(OUT/'agentpet_assembly.glb')
check('GLB contains all 21 components',len(scene.geometry)==21,
      dict(geometry_count=len(scene.geometry),size_mm=scene.extents.round(3).tolist()))
for name,m in scene.geometry.items():
    if name.startswith('screen_screw'):
        check(name+': tip contained',m.bounds[1,1]<B.FRONT-.4,
              dict(tip_y_mm=round(float(m.bounds[1,1]),3)))
geometry_report=json.loads((OUT/'fit_report.json').read_text())
check('build-time geometry audit passes',geometry_report['all_geometry_checks_pass'],
      dict(check_count=len(geometry_report['checks'])))
# Overhang evidence for the shop. These are indicators, not sliced toolpaths.
m=meshes['agentpet_case_front_print.stl']
mask=(m.face_normals[:,2]<-np.sqrt(.5)-1e-6)&(m.triangles_center[:,2]>.3)
overhang_area=float(m.area_faces[mask].sum())
report=dict(version='V5.1',all_saved_file_checks_pass=all(c['passed'] for c in checks),
            checks=checks,print_review=dict(
            front_downward_overhang_area_mm2=round(overhang_area,3),
            actual_slicer_run=False,
            instruction='Shop must inspect sliced layers and add local supports as needed; do not limit support to build plate only.'),
            release='Ready for first FDM/PLA test print; physical fit not yet validated.')
(OUT/'final_print_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
for c in checks:
    print(('PASS ' if c['passed'] else 'FAIL ')+c['check'])
print('Overhang area needing slicer review:',round(overhang_area,3),'mm^2')
if not report['all_saved_file_checks_pass']: raise SystemExit(1)
