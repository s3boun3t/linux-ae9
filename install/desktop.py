#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Install standard AE-9 desktop data from DKMS hooks; never touch live audio."""
import argparse
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

DATA = Path(__file__).resolve().parent / 'data'
STATE = Path('var/lib/sb-ae9/desktop-files.json')
PROFILE_DIRS = [Path('usr/share/alsa-card-profile/mixer/profile-sets'),
                Path('usr/share/pulseaudio/alsa-mixer/profile-sets')]
STATIC = {
    'usr/lib/udev/rules.d/90-sb-ae9-desktop.rules': '90-sb-ae9-desktop.rules',
    'usr/share/wireplumber/main.lua.d/99-sb-ae9-desktop.lua': '99-sb-ae9-desktop.lua',
    'usr/share/wireplumber/wireplumber.conf.d/99-sb-ae9-desktop.conf': '99-sb-ae9-desktop.conf',
}
ALLOWED = set(STATIC)
for directory in PROFILE_DIRS:
    ALLOWED.update([str(directory / 'sb-ae9.conf'),
                    str(directory.parent / 'paths/sb-ae9-what-u-hear.conf')])


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_profile(path, root):
    """Expand ACP includes in order, restoring the parent section afterwards."""
    root = root.resolve()

    def expand(file, stack):
        file = file.resolve()
        if not file.is_relative_to(root) or file in stack:
            raise RuntimeError('Unsafe or cyclic ACP profile include')
        output = []
        section = None
        for line in file.read_text().splitlines(True):
            stripped = line.strip()
            if stripped.startswith('.include '):
                name = Path(stripped[9:].strip())
                include = root / str(name).lstrip('/') if name.is_absolute() else file.parent / name
                output.extend(expand(include, stack + [file]))
                if section:
                    output.append(f'[{section}]\n')
            else:
                if stripped.startswith('[') and stripped.endswith(']'):
                    section = stripped[1:-1]
                output.append(line if line.endswith('\n') else line + '\n')
        return output

    conf = configparser.ConfigParser(interpolation=None, strict=False)
    conf.read_string(''.join(expand(path, [])))
    return conf


def mapping_priority(mapping):
    """Match ACP's stereo probe bonus before computing auto-profile priorities.

    PipeWire 1.0.5 initializes a stereo bonus map, then mapping_verify() adds
    50 for the same map or 30 for another two-channel map. Explicit profiles
    do not receive this bonus automatically (alsa-mixer.c / acp.c).
    """
    priority = int(mapping.get('priority', '0'))
    positions = [p.strip() for p in mapping['channel-map'].split(',')]
    if positions == ['stereo'] or (len(positions) == 2 and
            positions[0] in ['left', 'front-left'] and
            positions[1] in ['right', 'front-right']):
        return priority + 50
    return priority + (30 if len(positions) == 2 else 0)


def render_profile(default, root):
    conf = read_profile(default, root)
    micro = conf['Mapping analog-stereo']
    if (not conf.getboolean('General', 'auto-profiles') or
            micro.get('direction', 'any') == 'output' or int(micro['priority']) <= 1):
        raise RuntimeError('Unsupported stock ACP profile; preserving existing configuration')
    if 'Mapping sb-ae9-what-u-hear' in conf:
        raise RuntimeError('Stock profile already defines the reserved AE-9 mapping')
    lines = ['# Managed by sb-ae9 desktop integration; stock data stays authoritative.\n',
             '.include default.conf\n\n', '[Mapping sb-ae9-what-u-hear]\n',
             'description = What U Hear\ndevice-strings = hw:%f,2\n',
             'channel-map = left,right\ndirection = input\n',
             'paths-input = sb-ae9-what-u-hear\npriority = 1\nfallback = yes\n\n']
    profiles = [('input:analog-stereo', None, mapping_priority(micro))]
    for section in conf.sections():
        if not section.startswith('Mapping '):
            continue
        mapping = conf[section]
        if mapping.get('direction', 'any') == 'input' or mapping.getboolean('fallback', fallback=False):
            continue
        name = section[8:]
        profiles.append((f'output:{name}+input:analog-stereo', name,
                         mapping_priority(mapping) * 100 + mapping_priority(micro)))
    for name, output, priority in profiles:
        if 'Profile ' + name in conf:
            continue  # Explicit administrator/vendor profiles are never replaced.
        lines.append(f'[Profile {name}]\n')
        if output:
            lines.append(f'output-mappings = {output}\n')
        lines.append('input-mappings = analog-stereo sb-ae9-what-u-hear\n')
        lines.append(f'priority = {priority}\n\n')
        # A failed/busy What U Hear PCM must not remove microphone duplex.
        backup = 'Profile sb-ae9-microphone-only:' + name
        if backup in conf:
            raise RuntimeError('Stock profile already defines the reserved AE-9 backup')
        lines.append(f'[{backup}]\n')
        if output:
            lines.append(f'output-mappings = {output}\n')
        lines.append(f'input-mappings = analog-stereo\npriority = {priority - 1}\n\n')
    return ''.join(lines).encode()


def plan(root):
    files = {}
    for directory in PROFILE_DIRS:
        default = root / directory / 'default.conf'
        if default.is_file():
            files[str(directory / 'sb-ae9.conf')] = render_profile(default, root)
            files[str(directory.parent / 'paths/sb-ae9-what-u-hear.conf')] = (
                DATA / 'sb-ae9-what-u-hear.conf').read_bytes()
    if files:
        files.update({path: (DATA / name).read_bytes() for path, name in STATIC.items()})
    return files


def load_state(root):
    path = root / STATE
    if path.is_symlink():
        raise RuntimeError('Refusing a desktop manifest symlink')
    if not path.exists():
        return {'schema': 1, 'files': {}, 'targets': []}
    state = json.loads(path.read_text())
    if (not isinstance(state, dict) or state.get('schema') != 1 or
            not isinstance(state.get('files'), dict) or
            not isinstance(state.get('targets'), list) or
            not set(state['files']).issubset(ALLOWED) or
            any(not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value)
                for value in state['files'].values())):
        raise RuntimeError('Unknown desktop manifest; no data removed')
    for target in state.get('targets', []):
        if not isinstance(target, list) or len(target) != 2:
            raise RuntimeError('Invalid installed desktop target')
        validate_target(*target)
    for name, expected in state['files'].items():
        path = root / name
        if path.is_symlink() or (path.exists() and digest(path.read_bytes()) != expected):
            raise RuntimeError(f'Installed desktop data changed: {name}; preserving it')
    return state


def validate_target(kernel, version):
    if any(not isinstance(value, str) or
           not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]{0,127}', value)
           for value in [kernel, version]):
        raise RuntimeError('Invalid kernel or package version')


def check(root):
    files = plan(root)
    state = load_state(root)
    for name in files:
        path = root / name
        if path.is_symlink() or (path.exists() and name not in state['files']):
            raise RuntimeError(f'Desktop file has another owner: {name}')
    return files, state


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as out:
            temporary = Path(out.name)
            out.write(data)
        temporary.chmod(0o600 if path.name == STATE.name else 0o644)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def transaction(root, files, state):
    payloads = dict(files)
    payloads[str(STATE)] = json.dumps(state, sort_keys=True, indent=2).encode() + b'\n' if state['targets'] else None
    previous = {name: (root / name).read_bytes() if (root / name).exists() else None
                for name in payloads}
    changed = []
    try:
        for name, data in payloads.items():
            changed.append(name)
            path = root / name
            if data is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, data)
    except Exception:
        for name in reversed(changed):
            path = root / name
            if previous[name] is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, previous[name])
        raise


def install(root, kernel, version):
    validate_target(kernel, version)
    files, _ = check(root)
    if not files:
        print('AE-9: no ACP desktop profile data installed; kernel-only installation.')
        return False
    (root / STATE.parent).mkdir(parents=True, exist_ok=True)
    with (root / STATE.parent / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        files, state = check(root)
        targets = sorted({tuple(t) for t in state['targets']} | {(kernel, version)})
        new_state = {'schema': 1, 'targets': [list(t) for t in targets],
                     'files': {name: digest(data) for name, data in files.items()}}
        stale = {name: None for name in state['files'] if name not in files}
        transaction(root, {**stale, **files}, new_state)
    return True


def remove(root, kernel, version):
    validate_target(kernel, version)
    if not (root / STATE).exists():
        return
    with (root / STATE.parent / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load_state(root)
        state['targets'] = [t for t in state['targets'] if t != [kernel, version]]
        files = {} if state['targets'] else {name: None for name in state['files']}
        if not state['targets']:
            state['files'] = {}
        transaction(root, files, state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'install', 'remove'])
    parser.add_argument('kernel', nargs='?')
    parser.add_argument('version', nargs='?')
    parser.add_argument('--root', type=Path, default=Path('/'), help='package staging root')
    args = parser.parse_args()
    root = args.root.resolve()
    if args.action != 'check' and root == Path('/') and os.geteuid() != 0:
        parser.error('Installing desktop data requires root')
    if args.action != 'check' and (not args.kernel or not args.version):
        parser.error('install/remove require the target kernel and package version')
    try:
        if args.action == 'check':
            files, _ = check(root)
            print(f'AE-9 desktop preflight: {len(files)} data files; no change applied.')
        elif args.action == 'install':
            if install(root, args.kernel, args.version):
                print('AE-9 desktop data prepared for the next normal driver reboot/login.')
        else:
            remove(root, args.kernel, args.version)
            print('AE-9 desktop target removed; data retained if another target needs it.')
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, configparser.Error) as error:
        print('AE-9 desktop integration:', error, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
