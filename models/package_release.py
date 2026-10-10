#!/usr/bin/env python3
"""Package the checked V5.3 models; keep older archives untouched."""
from pathlib import Path
import hashlib
import json
from zipfile import ZIP_DEFLATED, ZipFile

OUT = Path(__file__).resolve().parent
VERSION, TAG = 'V5.3', 'v5_3'
FILES = [
    'README.md', 'print_shop_instructions.txt', 'build_case.py',
    'render_assembly.py', 'final_print_audit.py', 'package_release.py',
    'requirements.txt', 'agentpet_case.scad', 'agentpet_case_front.stl',
    'agentpet_case_back.stl', 'agentpet_case_front_print.stl',
    'agentpet_case_back_print.stl', 'agentpet_case_back_v5_3_print.stl', 'agentpet_case_both.stl',
    'screen_fit_coupon.stl', 'usb_fit_coupon.stl', 'agentpet_assembly.glb',
    'assembly_preview.html', 'assembly_viewer.template.html',
    'assembly_steps.png', 'case_preview.png', 'case_preview4.png',
    'screen_pin_clearance.png', 'rear_lip_revision.png', 'fit_report.json', 'final_print_audit.json',
    'build_hardware_fit.py', 'screen_hardware.glb', 'esp32_s3_hardware.glb',
    'hardware_fit_assembly.glb', 'hardware_fit_preview.html',
    'hardware_fit_overview.png', 'hardware_fit_report.json', 'hardware_fit_browser.jpg',
    'rear_lip_browser.jpg']
SHOP = {
    '01_screen_fit_coupon.stl': 'screen_fit_coupon.stl',
    '02_usb_fit_coupon.stl': 'usb_fit_coupon.stl',
    '03_front.stl': 'agentpet_case_front_print.stl',
    '04_back.stl': 'agentpet_case_back_v5_3_print.stl',
    '打印说明.txt': 'print_shop_instructions.txt',
    '装配预览.png': 'assembly_steps.png',
    '针脚间隙说明.png': 'screen_pin_clearance.png',
    '后盖定位边修正.png': 'rear_lip_revision.png'}


def main():
    geometry = json.loads((OUT/'fit_report.json').read_text())
    saved = json.loads((OUT/'final_print_audit.json').read_text())
    assert geometry['version'] == saved['version'] == VERSION
    assert geometry['all_geometry_checks_pass'] and saved['all_saved_file_checks_pass']
    assert all(c['passed'] for c in geometry['checks'] + saved['checks'])
    hardware=json.loads((OUT/'hardware_fit_report.json').read_text())
    assert hardware['all_checks_pass'] and all(c['passed'] for c in hardware['checks'])
    manifest = dict(version=VERSION, date='2026-10-10',
                    geometry_checks_passed=len(geometry['checks']),
                    saved_file_checks_passed=len(saved['checks']),
                    hardware_fit_checks_passed=len(hardware['checks']),
                    actual_slicer_run=False, physical_fit_verified=False,
                    front_pin_height_upper_bound_mm=2.0, user_confirmed_pins_below_glass=True, front_pin_height_measured=False,
                    files={})
    for name in FILES:
        data = (OUT/name).read_bytes()
        manifest['files'][name] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    (OUT/'artifact_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    with ZipFile(OUT/f'agentpet_case_{TAG}.zip','w',ZIP_DEFLATED) as z:
        for name in [*FILES,'artifact_manifest.json']:
            z.write(OUT/name, f'agentpet_case_{TAG}/{name}')
    with ZipFile(OUT/f'agentpet_print_shop_{TAG}.zip','w',ZIP_DEFLATED) as z:
        for name,source in SHOP.items():
            z.write(OUT/source, f'agentpet_print_shop_{TAG}/{name}')
    # Verify archived bytes, including the four printable meshes, after writing.
    for kind,items in [('case',{name:name for name in [*FILES,'artifact_manifest.json']}),
                       ('print_shop',SHOP)]:
        prefix=f'agentpet_{kind}_{TAG}'
        with ZipFile(OUT/f'{prefix}.zip') as z:
            assert z.testzip() is None
            assert len(z.namelist()) == len(items)
            for name,source in items.items():
                assert z.read(f'{prefix}/{name}') == (OUT/source).read_bytes()
    print(f'{VERSION}: both archives verified; {len(geometry["checks"])} geometry and '
          f'{len(saved["checks"])} saved-file checks passed.')


if __name__ == '__main__':
    main()
