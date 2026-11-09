#!/usr/bin/env python3
"""Exercise build.py compiler selection through real GNU make, without a kernel."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / 'build.py'


class CompilerSelection(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ae9-build-compiler-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / 'project'
        self.project.mkdir()
        (self.project / 'driver').mkdir()
        shutil.copy2(HELPER, self.project / 'build.py')
        self.headers = self.root / 'headers'
        (self.headers / 'include/config').mkdir(parents=True)
        (self.headers / 'include/sound').mkdir()
        (self.headers / 'include/config/kernel.release').write_text('7.0.0-test\n')
        (self.headers / 'Module.symvers').write_text('')
        (self.headers / 'include/sound/hdaudio.h').write_text('int snd_hdac_power_down(void);\n')
        (self.headers / 'include/sound/control.h').write_text(
            'int snd_ctl_add_vmaster_hook(struct snd_kcontrol *k, void *hook, void *data);\n')
        # Like Kbuild, this assignment overrides environment CC but not a make argument.
        (self.headers / 'Makefile').write_text('''CC = header-default-cc
ifeq ($(LLVM),-21)
CC = clang-21
endif
.PHONY: modules clean
modules clean:
\t@printf '%s\\n' '$(CC)' > '$(M)/cc-$@'
\t@printf '%s\\n' '$(LLVM)' > '$(M)/llvm-$@'
\t@printf '%s\\n' '$(W)' > '$(M)/warnings-$@'
''')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        (self.bin / 'make').symlink_to(shutil.which('make'))
        self.config()

    def config(self, recorded='x86_64-linux-gnu-gcc-13 (Ubuntu) 13.3.0', clang=False):
        (self.headers / '.config').write_text(
            f'CONFIG_CC_VERSION_TEXT="{recorded}"\n'
            'CONFIG_GCC_VERSION=130300\nCONFIG_CLANG_VERSION=210108\n'
            f'CONFIG_CC_IS_CLANG={"y" if clang else "n"}\n'
            'CONFIG_SND_HDA_CORE=m\nCONFIG_SND_HDA_CODEC_CA0132=m\n')

    def available(self, *names):
        for name in names:
            tool = self.bin / name
            family = 'clang' if name.startswith('clang') else 'gcc'
            major = name.rsplit('-', 1)[1]
            banner = (f'clang version {major}.0.0' if family == 'clang'
                      else f'gcc (GCC) {major}.0.0')
            tool.write_text('#!/bin/sh\ncase "$1" in\n'
                            f'--version) echo "{banner}" ;;\n'
                            f'-dumpfullversion) echo "{major}.0.0" ;;\n'
                            'esac\n')
            tool.chmod(0o755)

    def run_helper(self, action='build', **variables):
        env = {k: v for k, v in os.environ.items()
               if k not in {'CC', 'LLVM', 'MAKEFLAGS', 'MFLAGS', 'MAKEOVERRIDES'}}
        env.update(PATH=str(self.bin), **variables)
        result = subprocess.run(
            [sys.executable, '-B', str(self.project / 'build.py'), action,
             '--kernel-release', '7.0.0-test', '--kdir', str(self.headers)],
            env=env, capture_output=True, text=True)
        return result

    def selected(self, result, target='modules'):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.project / f'driver/warnings-{target}').read_text().strip(), '1')
        return (self.project / f'driver/cc-{target}').read_text().strip()

    def test_explicit_cc_reaches_make_even_with_llvm(self):
        self.assertEqual(self.selected(self.run_helper(CC='/custom/toolchain/gcc', LLVM='-21')),
                         '/custom/toolchain/gcc')

    def test_explicit_cc_wrapper_is_preserved(self):
        self.assertEqual(self.selected(self.run_helper(CC='ccache clang-21')),
                         'ccache clang-21')

    def test_clean_respects_explicit_cc(self):
        self.assertEqual(self.selected(self.run_helper('clean', CC='/custom/gcc'), 'clean'),
                         '/custom/gcc')

    def test_ubuntu_prefers_recorded_compiler_name(self):
        self.available('gcc-13', 'x86_64-linux-gnu-gcc-13')
        self.assertEqual(self.selected(self.run_helper()), 'x86_64-linux-gnu-gcc-13')

    def test_missing_recorded_name_falls_back_to_versioned_gcc(self):
        self.available('gcc-13')
        self.assertEqual(self.selected(self.run_helper()), 'gcc-13')

    def test_wrong_major_in_recorded_name_is_not_selected(self):
        self.config('x86_64-linux-gnu-gcc-12 (Ubuntu) 12.0')
        self.available('gcc-13', 'x86_64-linux-gnu-gcc-12')
        self.assertEqual(self.selected(self.run_helper()), 'gcc-13')

    def test_missing_compiler_remains_an_error(self):
        result = self.run_helper()
        self.assertEqual(result.returncode, 2)
        self.assertIn('gcc-13 is required', result.stderr)
        self.assertFalse((self.project / 'driver/cc-modules').exists())

    def test_clang_autoselection_is_unchanged(self):
        self.config('Debian clang version 21.1.8', clang=True)
        self.available('clang-21')
        self.assertEqual(self.selected(self.run_helper()), 'clang-21')
        self.assertEqual((self.project / 'driver/llvm-modules').read_text().strip(), '-21')

    def test_explicit_llvm_is_unchanged(self):
        self.assertEqual(self.selected(self.run_helper(LLVM='-21')), 'clang-21')


if __name__ == '__main__':
    unittest.main(verbosity=2)
