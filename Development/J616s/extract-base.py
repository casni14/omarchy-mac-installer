#!/usr/bin/env python3
"""Verify the official Omarchy base and extract it into a new image directory."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from catalog_release import identity

BASE_SHA256 = 'ad6f83c99488688dcbb7b00935a018256aeb24240d6b9a40d9efa0ffc72316ad'


def extract(build):
    source = build / 'omarchy-base.zip'
    with source.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != BASE_SHA256:
            raise ValueError('Omarchy base payload differs from its signed catalog')
    destination = build / 'image'
    destination.mkdir(exist_ok=False)
    with zipfile.ZipFile(source) as archive:
        for member in archive.infolist():
            path = Path(member.filename)
            file_type = (member.external_attr >> 16) & 0o170000
            if path.is_absolute() or '..' in path.parts or file_type == 0o120000:
                raise ValueError('unsafe base payload member')
        archive.extractall(destination)
    (build / 'base-input.json').write_text(json.dumps({'sha256': BASE_SHA256,
        'source': identity()['INSTALLER_CATALOG_BASE'] + '/releases/omarchy-mac-4.5.0-r2-2026.11.05-08c81abcef4f/'
                  'omarchy-2026.11.05-aarch64-apple-silicon-mac-stable-os-package.zip'}, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build', type=Path)
    extract(parser.parse_args().build)
