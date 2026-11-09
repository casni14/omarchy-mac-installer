#!/usr/bin/env python3
"""Package the converted image and rebuilt Recovery template for J616s only."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Engine/overlay/src'))
import omarchy_asahi  # Requires the locked engine modules on PYTHONPATH.
import omarchy_recovery


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def assemble(build, recovery, metadata, output):
    output.mkdir(parents=True, exist_ok=True)
    esp = build / 'esp-complete'
    template = esp / 'aurora/recovery'
    if template.exists():
        shutil.rmtree(template)
    shutil.copytree(recovery, template, ignore=shutil.ignore_patterns('checks', 'bundle-lookup-check'))
    omarchy_recovery.validate_source(template / omarchy_recovery.APP_NAME,
                                    template / omarchy_recovery.MANIFEST_NAME)
    # Refuse malformed Stage 1 and a layout that would select the generic Stage 2.
    stage1 = (esp / 'aurora/stage1.bin').read_bytes()
    omarchy_asahi.fill_aurora_stage1(stage1, omarchy_asahi.PLACEHOLDER_UUID, 'm1n1/boot.bin', 0)
    members = ['esp/' + p.relative_to(esp).as_posix() for p in esp.rglob('*') if p.is_file()]
    layout = omarchy_asahi.esp_board_layout('j616sap', members, common_allowed=True)
    assert layout['esp/m1n1/boot-j616s.bin'] == 'm1n1/boot.bin'
    assert 'esp/m1n1/boot.bin' not in layout
    package = output / 'omarchy-j616s-developer-os-package.zip'
    if package.exists():
        raise ValueError('refusing to overwrite an existing payload')
    provenance = {
        'board': 'apple,j616s', 'physical_installation': 'pending',
        'base_payload_sha256': 'ad6f83c99488688dcbb7b00935a018256aeb24240d6b9a40d9efa0ffc72316ad',
        'aurora_release': 'testing-20261101.4',
        'aurora_packages': json.loads((ROOT / 'Development/J616s/packages.json').read_text()),
        'stage1_sha256': hashlib.sha256(stage1).hexdigest(),
        'stage2_sha256': digest(esp / 'm1n1/boot-j616s.bin'),
        'images': {name: digest(build / 'image' / name) for name in ('boot.img', 'root.img')},
    }
    (output / 'j616s-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    with zipfile.ZipFile(package, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        archive.write(esp, 'esp/')
        archive.write(build / 'image/omarchy-volume.icns', 'omarchy-volume.icns')
        # Include directory entries, including the empty first-boot contract directories.
        for path in sorted(esp.rglob('*')):
            if path.name.endswith('.old'):
                continue
            archive.write(path, 'esp/' + path.relative_to(esp).as_posix())
        for name in ('boot.img', 'root.img'):
            archive.write(build / 'image' / name, name)
        archive.writestr('j616s-provenance.json', json.dumps(provenance, indent=2))
    document = json.loads(metadata.read_text())
    target = document['os_list'][0]
    target.update(package=package.name, name='Omarchy for J616s (developer test)',
                  supported_fw=['26.6.2'], allowed_device_classes=['j616sap'],
                  aurora_stage1={'kind': 'common-raw-v1', 'qualified_machines': {'j616sap': ['26.6.2']}})
    # The native Recovery template is staged by the rebuilt app's helper.
    # Keep the payload copy identical for the existing native Recovery contract.
    (output / 'installer_data.json').write_text(json.dumps(document, indent=2) + '\n')
    print(json.dumps({'payload': package.name, 'size': package.stat().st_size,
                      'sha256': digest(package)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'recovery', 'metadata', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    assemble(args.build, args.recovery, args.metadata, args.output)
