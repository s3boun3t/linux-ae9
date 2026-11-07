#!/usr/bin/env python3
"""Build the external AE-9 modules using the explicitly selected kernel."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def build(args):
    root = Path(__file__).resolve().parent
    kdir = args.kdir.resolve(strict=True)
    release = (kdir / 'include/config/kernel.release').read_text().strip()
    if release != args.kernel_release:
        raise ValueError(f'headers are for {release}, requested {args.kernel_release}')
    config = dict(re.findall(r'^(CONFIG_\w+)=(.*)$', (kdir / '.config').read_text(), re.M))
    command = ['make', '-C', str(kdir), f'M={root / "driver"}', 'W=1']
    # Cleanup must also target the requested kernel, independently of uname.
    if args.action == 'clean':
        return subprocess.run(command + ['clean'], check=False).returncode
    version = re.match(r'^(\d+)\.(\d+)\.', release)
    if not version or not ((7, 0) <= tuple(map(int, version.groups())) <= (7, 3)):
        raise ValueError('this preview covers Linux 7.0 through 7.3 only')
    for option in ['CONFIG_SND_HDA_CORE', 'CONFIG_SND_HDA_CODEC_CA0132']:
        if config.get(option) != 'm':
            raise ValueError(f'{option}=m required; cannot replace a built-in driver')
    if not (kdir / 'Module.symvers').is_file():
        raise ValueError('the target Module.symvers is required')
    hda = (kdir / 'include/sound/hdaudio.h').read_text()
    control = (kdir / 'include/sound/control.h').read_text()
    if not re.search(r'\bint\s+snd_hdac_power_down\s*\(', hda):
        raise ValueError('this stable driver requires the integer HDA power API')
    hook = re.search(r'\bint\s+snd_ctl_add_vmaster_hook\s*\((.*?)\);', control, re.S)
    if not hook or not hook[1].strip().startswith('struct snd_kcontrol *'):
        raise ValueError('this stable driver requires the three-argument vmaster API')
    if os.environ.get('LLVM') == '1' and not shutil.which('clang'):
        major = int(config.get('CONFIG_CLANG_VERSION', '0')) // 10000
        if not shutil.which(f'clang-{major}'):
            raise ValueError(f'clang-{major} or clang is required')
        command.append(f'LLVM=-{major}')
    if 'LLVM' not in os.environ and 'CC' not in os.environ:
        clang = config.get('CONFIG_CC_IS_CLANG') == 'y'
        compiler = 'clang' if clang else 'gcc'
        number = config.get('CONFIG_CLANG_VERSION' if clang else 'CONFIG_GCC_VERSION', '0')
        major = int(number) // 10000
        name = f'{compiler}-{major}'
        if not shutil.which(name):
            raise ValueError(f'{name} is required, or explicitly set CC/LLVM')
        command.append(f'LLVM=-{major}' if clang else f'CC={name}')
    command += [f'-j{args.jobs}', 'modules']
    print('AE-9 target:', release, flush=True)
    return subprocess.run(command, check=False).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'clean'])
    parser.add_argument('--kernel-release', required=True)
    parser.add_argument('--kdir', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=min(os.cpu_count() or 1, 8))
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    try:
        return build(args)
    except (OSError, ValueError) as exc:
        print(f'AE-9: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
