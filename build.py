#!/usr/bin/env python3
"""Build the external AE-9 modules using the explicitly selected kernel."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def compiler_matches(name, family, major):
    """Probe automatic candidates; never execute command strings or wrappers."""
    if not shutil.which(name):
        return False
    def probe(*args):
        return subprocess.run([name, *args], check=True, capture_output=True,
                              text=True, timeout=2).stdout.strip()
    try:
        banner = probe('--version')
        clang = re.search(r'\bclang version (\d+)[.]', banner)
        if family == 'clang':
            return bool(clang and int(clang[1]) == major)
        if clang or not re.search(r'\b(?:gcc|GCC)\b', banner):
            return False
        version = probe('-dumpfullversion', '-dumpversion')
        return bool(re.fullmatch(r'\d+(?:[.]\d+)*', version) and
                    int(version.split('.')[0]) == major)
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return False


def compiler_environment(config, environment):
    """Resolve automatic tools while retaining explicit compiler overrides."""
    env = dict(environment)
    clang = config.get('CONFIG_CC_IS_CLANG') == 'y'
    family = 'clang' if clang else 'gcc'
    major = int(config.get('CONFIG_CLANG_VERSION' if clang else
                           'CONFIG_GCC_VERSION', '0')) // 10000
    if 'CC' in env and not env['CC'].strip():
        raise ValueError('CC must not be empty')
    if 'LLVM' in env and not env['LLVM']:
        raise ValueError('LLVM must not be empty')
    # Old DKMS forces bare clang even on distributions with only clang-N.
    fallback = (env.get('CC') == 'clang' and not shutil.which('clang') and
                clang and major > 0 and env.get('LLVM') in ('1', f'-{major}'))
    if fallback:
        name = f'clang-{major}'
        if not compiler_matches(name, 'clang', major):
            raise ValueError(f'{name} with matching family/version is required')
        env.update(CC=name, LLVM=f'-{major}')
        # Override make's inherited command-line LD as well as its environment.
        linker_choice = env.get('LD')
        if linker_choice is None and re.search(
                r'(?:^|\s)LD=ld[.]lld(?:\s|$)', env.get('MAKEFLAGS', '')):
            linker_choice = 'ld.lld'
        if linker_choice == 'ld.lld' and not shutil.which('ld.lld'):
            linker = f'ld.lld-{major}'
            if not shutil.which(linker):
                raise ValueError(f'{linker} is required')
            env['LD'] = linker
        return env
    if 'CC' in env:
        return env
    if 'LLVM' in env and env['LLVM'] != '1':
        return env
    if env.get('LLVM') == '1':
        family = 'clang'
        major = int(config.get('CONFIG_CLANG_VERSION', '0')) // 10000
        # A GCC-built kernel has no reference Clang version for this override.
        if major == 0 and shutil.which('clang'):
            return env
        candidates = ['clang', f'clang-{major}']
    else:
        candidates = []
        recorded = config.get('CONFIG_CC_VERSION_TEXT', '').strip('"').split()
        if (not clang and recorded and
                re.fullmatch(r'[\w.+-]*gcc(?:-' + str(major) + r')?', recorded[0])):
            candidates.append(recorded[0])
        candidates += [f'{family}-{major}', family]
    for name in dict.fromkeys(candidates):
        if major > 0 and compiler_matches(name, family, major):
            env['CC'] = name
            if family == 'clang':
                env['LLVM'] = '1' if name == 'clang' else f'-{major}'
            return env
    raise ValueError(f'{family}-{major} is required (matching family/version), '
                     'or explicitly set CC/LLVM')


def kernel_source(kdir, release, ksrc=None):
    """Resolve API headers without evaluating or running kernel Makefiles."""
    api = ('include/sound/hdaudio.h', 'include/sound/control.h')
    if ksrc is None and all((kdir / name).is_file() for name in api):
        return kdir
    if ksrc is not None and Path(ksrc).resolve(strict=True) == kdir and all(
            (kdir / name).is_file() for name in api):
        return kdir
    wrapper = kdir / 'Makefile'
    lines = [line.strip() for line in
             (wrapper.read_text().splitlines() if wrapper.is_file() else [])
             if line.strip() and not line.lstrip().startswith('#')]
    includes = [line for line in lines
                if re.match(r'(?:-?include|sinclude)\s+', line)]
    included = None
    # Only generated, unconditional literal wrappers have a provable source.
    simple = all(re.fullmatch(r'include [^\s$#\\]+/Makefile', line) or
                 re.fullmatch(r'KBUILD_OUTPUT\s*=\s*[^\s$#\\]+', line)
                 for line in lines)
    if includes and (not simple or len(includes) != 1):
        raise ValueError('ambiguous kernel source wrapper; check --ksrc and Makefile')
    if len(includes) == 1:
        path = Path(includes[0][len('include '):])
        if not path.is_absolute():
            path = kdir / path
        included = path.parent.resolve()
    if ksrc is None:
        if included is None or not (included / 'Makefile').is_file():
            raise ValueError('cannot resolve kernel sources; provide --ksrc')
        source = included
    else:
        source = Path(ksrc).resolve(strict=True)
        if (included is not None and (included / 'Makefile').is_file() and
                source != included):
            raise ValueError('--ksrc conflicts with the build Makefile source')
    if not all((source / name).is_file() for name in api):
        raise ValueError('kernel source API headers missing; check --ksrc')
    if source != kdir:
        expected = re.match(r'^(\d+)[.](\d+)[.](\d+)', release)
        if not expected:
            raise ValueError('invalid target kernel release')
        expected = tuple(map(int, expected.groups()))
        config = (kdir / '.config').read_text()
        signature = re.search(
            r'^CONFIG_VERSION_SIGNATURE="Ubuntu [^"\n]+ (\d+)[.](\d+)[.](\d+)"$',
            config, re.M)
        if signature:
            base = tuple(map(int, signature.groups()))
            if base[:2] != expected[:2]:
                raise ValueError('Ubuntu base version differs from target kernel')
            expected = base
        makefile = (source / 'Makefile').read_text()
        actual = []
        for key in ('VERSION', 'PATCHLEVEL', 'SUBLEVEL'):
            values = re.findall(r'^' + key + r'\s*=\s*(\d+)\s*$', makefile, re.M)
            if len(values) != 1:
                raise ValueError('kernel source version must be literal and unique')
            actual.append(int(values[0]))
        if tuple(actual) != expected:
            raise ValueError('kernel source version differs from target kernel')
    return source


def build(args):
    root = Path(__file__).resolve().parent
    kdir = args.kdir.resolve(strict=True)
    release = (kdir / 'include/config/kernel.release').read_text().strip()
    if release != args.kernel_release:
        raise ValueError(f'headers are for {release}, requested {args.kernel_release}')
    config = dict(re.findall(r'^(CONFIG_\w+)=(.*)$', (kdir / '.config').read_text(), re.M))
    command = ['make', '-C', str(kdir), f'M={root / "driver"}', 'W=1']
    # Makefile assignments can override environment CC; command-line values win.
    if 'CC' in os.environ:
        command.append(f'CC={os.environ["CC"]}')
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
    source = kernel_source(kdir, release, args.ksrc)
    hda = (source / 'include/sound/hdaudio.h').read_text()
    control = (source / 'include/sound/control.h').read_text()
    if not re.search(r'\bint\s+snd_hdac_power_down\s*\(', hda):
        raise ValueError('this stable driver requires the integer HDA power API')
    hook = re.search(r'\bint\s+snd_ctl_add_vmaster_hook\s*\((.*?)\);', control, re.S)
    if not hook or not hook[1].strip().startswith('struct snd_kcontrol *'):
        raise ValueError('this stable driver requires the three-argument vmaster API')
    selected = compiler_environment(config, os.environ)
    for variable in ('CC', 'LLVM', 'LD'):
        if variable in selected and (variable != 'LD' or
                                     selected[variable] != os.environ.get(variable)):
            command.append(f'{variable}={selected[variable]}')
    command += [f'-j{args.jobs}', 'modules']
    print('AE-9 target:', release, flush=True)
    return subprocess.run(command, check=False).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'clean'])
    parser.add_argument('--kernel-release', required=True)
    parser.add_argument('--kdir', type=Path, required=True)
    parser.add_argument('--ksrc', type=Path, help='kernel source API headers; build stays in --kdir')
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
