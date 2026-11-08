#!/usr/bin/env python3
"""Compile both modules in a temporary copy, without installing or loading them."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel-release', required=True)
    parser.add_argument('--kdir', required=True, type=Path)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'build-results')
    args = parser.parse_args()
    try:
        kdir = args.kdir.resolve(strict=True)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output = Path(tempfile.mkdtemp(prefix='build-', dir=args.output_dir.resolve()))
        source = ROOT / 'driver'
        before = {str(f.relative_to(source)): sha(f) for f in source.rglob('*')
                  if f.is_file() and (f.suffix in {'.c', '.h'} or f.name == 'Makefile')}
        report = {'kernel_release': args.kernel_release, 'headers': str(kdir),
                  'sources': before, 'status': 'failed', 'installed': False,
                  'config_sha256': sha(kdir / '.config'),
                  'symvers_sha256': sha(kdir / 'Module.symvers'),
                  'toolchain': {k: os.environ[k] for k in ['CC', 'LLVM'] if k in os.environ}}
        with tempfile.TemporaryDirectory(prefix='ae9-build-') as temp:
            work = Path(temp)
            for relative in before:
                target = work / 'driver' / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / relative, target)
            shutil.copy2(ROOT / 'build.py', work / 'build.py')
            command = [sys.executable, str(work / 'build.py'), 'build',
                       '--kernel-release', args.kernel_release, '--kdir', str(kdir)]
            with (output / 'build.log').open('w') as log:
                built = subprocess.run(command, cwd=work, stdout=log, stderr=subprocess.STDOUT)
            report['build_returncode'] = built.returncode
            modules = [work / 'driver/hda-core/snd-hda-core.ko',
                       work / 'driver/ca0132/snd-hda-codec-ca0132.ko']
            if built.returncode == 0 and all(p.is_file() for p in modules):
                report['modules'] = {p.name: sha(p) for p in modules}
                # Retain logs/metadata, not potentially installable module artifacts.
                clean = subprocess.run(command[:2] + ['clean'] + command[3:], cwd=work,
                                       capture_output=True, text=True)
                (output / 'clean.log').write_text(clean.stdout + clean.stderr)
                report['clean_returncode'] = clean.returncode
                if clean.returncode == 0 and all(not p.exists() for p in modules):
                    report['status'] = 'passed'
            if any(sha(source / relative) != expected for relative, expected in before.items()):
                report['status'] = 'failed'
                report['error'] = 'source changed during compilation'
        (output / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
        print('Build:', report['status'], '\nReport:', output / 'summary.json')
        return 0 if report['status'] == 'passed' else 1
    except (OSError, ValueError) as exc:
        print('AE-9 CI build:', exc, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
