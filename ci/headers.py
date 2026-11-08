#!/usr/bin/env python3
"""Verify and extract pinned header packages; never install a kernel package."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent


def main():
    profiles = json.loads((ROOT / 'kernels.json').read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=profiles, default='ubuntu-7.0')
    parser.add_argument('--package-dir', type=Path,
                        help='use local .deb files instead of downloading')
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    try:
        profile = profiles[args.profile]
        output = args.output_dir.resolve()
        output.mkdir(parents=True, exist_ok=False)
        packages = output / 'packages'
        packages.mkdir()
        for package in profile['packages']:
            path = packages / package['name']
            if args.package_dir:
                shutil.copyfile(args.package_dir / package['name'], path)
            else:
                with urllib.request.urlopen(package['url'], timeout=60) as response:
                    with path.open('wb') as destination:
                        shutil.copyfileobj(response, destination)
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != package['sha256']:
                raise ValueError('header package hash mismatch: ' + package['name'])
        # Verify every package before invoking the extractor. No maintainer scripts run.
        for package in profile['packages']:
            subprocess.run(['dpkg-deb', '--extract', str(packages / package['name']),
                            str(output)], check=True)
        headers = output / profile['headers']
        release = (headers / 'include/config/kernel.release').read_text().strip()
        if release != profile['release']:
            raise ValueError('extracted kernel release differs from profile')
        print(headers)
        return 0
    except (OSError, ValueError, urllib.error.URLError, subprocess.CalledProcessError) as exc:
        print('AE-9 headers:', exc, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
