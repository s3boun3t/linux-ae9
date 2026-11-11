# Sound Blaster AE-9 — Linux DKMS driver

An ALSA driver for the **Creative Sound Blaster AE-9 PCIe sound card** and
its external **Audio Control Module (ACM)**. This DKMS preview
consolidates the AE-9 voice and stability improvements as two DKMS modules: `snd-hda-core` and
`snd-hda-codec-ca0132`.

## Features

- Audio playback, headphone/speaker output selection, volume and mute controls.
- ACM volume knob, dB display and SBX button, with ALSA control synchronization.
- SBX playback effects, microphone capture and microphone effects controls.
- ACM headphone switching and 3.5 mm microphone jack presence reporting.
- DAC digital filter selection.
- Separate What U Hear capture PCM, with automatic desktop profile integration.

Playback, ACM controls and microphone operation have been reported working on
the reference Mint/XanMod system. Microphone jack presence is polled at roughly
five-second intervals. XLR/TRS detection, surround/optical output and
suspend/resume are not fully qualified. Direct mode and automatic native
sample-rate switching are not included in this branch.

The driver keeps the microphone handling and complete
SCP-message serialization. On AE-9, SCP reads now preserve transport errors
and reject unexpected vendor status values. FX level and crossover controls
report errors, retain the previous cached value on failure, and return an ALSA
change notification after success. Their transactions share the output mutex.
The AE-9 bass-redirection crossover also uses the advertised 10–1000 Hz range
and restores its own cached frequency. Extra `vc2-trace1` logging remains in
the separate diagnostic version. Software checks alone do not establish hardware reliability.

AE-9 input routing now checks each operation that can report an error. A
failed selection remains invalid until a complete retry; capture preparation
detaches the old ADC before rebuilding an uncertain route. Init/resume keeps
the saved PCM configuration and restores a surviving ADC tag only after all
source, gain and voice operations succeed.

AE-9 microphone setup, source selection and teardown leave the internal DSP
streams 3/4 untouched, matching the isolated `voice1` correction tested on the
reference system. Brief user recordings reported clear NR, VoiceFX, Smart
Volume and Mic EQ capture, with the played reference suppressed during the
AEC comparison. This consolidated source adds shared VoiceFX identifiers;
it has not itself been installed. Prolonged voice sessions and suspend/resume
remain unqualified. Other CA0132 cards retain their stream 3/4 handling.

Output routing now has a separate applied-state flag. Errors prevent new
playback preparation and ACM output writes until a complete selection succeeds.
The periodic jack poll does not retry a failed switch on an unchanged jack.
An explicit selection or codec init can restore the route. Speaker configuration
controls also report failures and retain their previous cached values. These
changes are restricted to AE-9; successful software command sequences do not
prove physical DAC state or audio quality.

## Compatibility

This is a **DKMS preview**, version `0.2.0-preview11-voice2`, for **x86_64 Linux
7.0–7.3** with the expected stable HDA/ALSA APIs. The HDA core and CA0132
codec must be configured as modules, not built into the kernel.

Both modules have been compiled against Ubuntu `7.0.0-42-generic` and XanMod
`7.3.3-x64v3-xanmod1`. Fedora, Arch and CachyOS kernels remain unqualified;
the allowed version range is not a guarantee for every distribution kernel.
Linux 6.x and the development-kernel adaptations are outside this package.
The latter are maintained separately on
[`ae9-mainline`](https://github.com/s3boun3t/linux-ae9/tree/ae9-mainline).

## Installation

### 1. Install prerequisites

Install Git, DKMS, Python 3, Make, the compiler matching your kernel, and its
matching development headers. Check your target with `uname -r`.

| Distribution | Kernel development package |
|---|---|
| Ubuntu / Linux Mint | `linux-headers-<kernel-release>` |
| Fedora | `kernel-devel-<kernel-release>` |
| Arch Linux | The header package for your kernel, such as `linux-headers` or `linux-lts-headers` |
| CachyOS | The matching CachyOS header package, such as `linux-cachyos-headers` |

A Clang-built kernel requires the corresponding LLVM toolchain. The build
helper reads the target kernel configuration and respects explicit `CC` or
`LLVM` settings.

Automatic selection checks the compiler family and major version against the
target configuration, trying the recorded GCC name, a versioned executable,
then `gcc` or `clang`. Explicit compiler paths and wrappers are preserved
without probing. For old DKMS forcing an unavailable bare `clang`, the helper
can use matching `clang-N` and, when needed, `ld.lld-N` with compatible LLVM
settings. This does not install tools or qualify another distribution kernel.

The build directory (`--kdir`) supplies the target configuration, release and
symbols. API headers may live in a separate source directory, as on Debian:
the helper recognizes a simple generated Makefile wrapper or accepts an
explicit `--ksrc` path. It checks the source base version, including Ubuntu's
version signature when present. Ambiguous wrappers are refused. `--ksrc`
only selects API headers; it does not relocate extracted kernel Makefiles.
Compilation and cleanup still run against `--kdir`.

### 2. Obtain and install the firmware

Install `curl`, `tar` and `innoextract` using your package manager.
Two files are required: the main image `ctefx-desktop.bin` and the AE-9 overlay
`ae9-dsp-output-overlay.bin`. **Creative firmware, Windows installers and
extracted binaries are not redistributed by this project.** Obtain them from
their original publisher and keep them outside the Git checkout.

**Main image.** Use your distribution's official firmware package if it supplies
`ctefx-desktop.bin` (for example, `alsa-firmware` on Fedora/Arch). Do not assume
that `linux-firmware` supplies it on every distribution. Alternatively, obtain
it from the [official ALSA firmware archive](https://www.alsa-project.org/files/pub/firmware/):

```sh
fw_work="$HOME/.cache/ae9-firmware"
mkdir -p "$fw_work"
curl --fail --location \
  https://www.alsa-project.org/files/pub/firmware/alsa-firmware-1.2.4.tar.bz2 \
  --output "$fw_work/alsa-firmware-1.2.4.tar.bz2"
tar -xOf "$fw_work/alsa-firmware-1.2.4.tar.bz2" \
  alsa-firmware-1.2.4/ca0132/ctefx-desktop.bin \
  > "$fw_work/ctefx-desktop.bin"
```

**Overlay.** Download `AECMDMasterInstaller_3.4.92.00.exe` yourself from
[Creative's official AE-9 support page](https://support.creative.com/Products/ProductDetails.aspx?prodID=23304&prodName=Sound+Blaster+AE-9%2F1000).
Install `innoextract` with your package manager first. The following uses a
fixed, reviewed revision of DarkNikGr's extractor, unpacks the Windows
installer without executing it, and writes the overlay locally without root.
Replace the `installer` path with the file you downloaded.

```sh
fw_work="$HOME/.cache/ae9-firmware"
installer="/path/to/AECMDMasterInstaller_3.4.92.00.exe"
(
  command -v innoextract >/dev/null || exit 1
  test -f "$installer" || exit 1
  mkdir -p "$fw_work" || exit 1
  cd "$fw_work" || exit 1
  curl --fail --location \
    https://raw.githubusercontent.com/DarkNikGr/sb-ae9/be71d1733bc12e1c2145d32a52c687055f7905ba/tools/ae9-firmware-extract.sh \
    --output ae9-firmware-extract.sh || exit 1
  printf '%s\n' \
    '1718ee23b1b00ee8a01099ff3e214132d248cb9c567664454c58e2f2d1bee3d0  ae9-firmware-extract.sh' \
    | sha256sum -c - || exit 1
  bash ./ae9-firmware-extract.sh --exe "$installer" \
    --out "$fw_work/ae9-dsp-output-overlay.bin"
)
```

**Verify and install.** These full SHA-256 values and sizes identify the files
used by the micjack1 reference. If either differs, stop and report its source
and version; do not force it or rename another project's overlay. The driver's
`ctefx.bin` fallback is not proof of equivalent AE-9 behavior. Keep a copy of
any existing working firmware before replacing it.

```sh
fw_work="$HOME/.cache/ae9-firmware"
(
  cd "$fw_work" || exit 1
  printf '%s\n' \
    'c9ab092e5717080bcd90971d44aa7d8d30778058ea691dda76320cd315dcc18e  ctefx-desktop.bin' \
    'ecc0740bde7ead2be16526edb9d6089ca6413c672679ceeb33b0f13b712dfe1c  ae9-dsp-output-overlay.bin' \
    | sha256sum -c - || exit 1
  test "$(stat -c %s ctefx-desktop.bin)" = 655856 || exit 1
  test "$(stat -c %s ae9-dsp-output-overlay.bin)" = 432 || exit 1
  sudo install -d /lib/firmware/creative/ae9 || exit 1
  sudo install -m 0644 ctefx-desktop.bin ae9-dsp-output-overlay.bin \
    /lib/firmware/creative/ae9/
)
```

The guarded block exits before installation on a mismatch. The two image
hashes above are unchanged; only their preferred installation directory changes.
The driver first searches `creative/ae9/` under the standard firmware directories.
If a preferred file is absent, it tries the old root-level name. Existing
installations can therefore keep both files in `/lib/firmware/`; do not move or
remove those files if another CA0132 driver uses them. A read error or an
unexpected image size is reported as a failure, without trying another image.
The kernel checks sizes (and the overlay layout), not cryptographic identity;
the SHA-256 checks above remain required before installation. The historical
`ctefx.bin` fallback remains when neither main-image location exists, but it
is not the qualified AE-9 image.

`/lib/firmware` may resolve to `/usr/lib/firmware`. The driver creates no folders
and copies no files. Refresh the initramfs if needed and reboot
after installing the modules below; do not hot-reload HDA to test firmware.

This package replaces the shared HDA core as well as the codec. Keep a working
kernel available. If Secure Boot is enabled, follow your distribution's DKMS
module-signing and key-enrollment procedure before rebooting.

### 3. Get the driver

```sh
git clone --depth 1 --single-branch --branch ae9-driver https://github.com/s3boun3t/linux-ae9.git sb-ae9
cd sb-ae9
```

Check existing installations:

```sh
dkms status
```

If another AE-9 package provides either module, resolve that installation for
the target kernel first. Do not install overlapping providers or overwrite an
existing package with `--force`.

### 4. Build and install with DKMS

From the repository root, for the currently running, supported kernel:

```sh
target_kernel="$(uname -r)"
sudo dkms add .
sudo dkms build -m sb-ae9 -v 0.2.0-preview11-voice2 -k "$target_kernel"
sudo dkms install -m sb-ae9 -v 0.2.0-preview11-voice2 -k "$target_kernel"
```

If this exact package version is already registered, skip `dkms add .`.
To target another installed kernel, set `target_kernel` to its full release
and install its matching headers.

If HDA modules are included in your initramfs, rebuild it for that kernel
using your distribution's configured tool before rebooting. On Ubuntu/Mint,
use `sudo update-initramfs -u -k "$target_kernel"`; on Fedora, use
`sudo dracut --force --kver "$target_kernel"`. On Arch/CachyOS, use the
configured mkinitcpio or dracut procedure. Keep both HDA modules consistent.

Reboot, then check:

```sh
dkms status
modinfo -n snd-hda-core
modinfo -n snd-hda-codec-ca0132
journalctl -k -b | grep -Ei 'ca0132|ae-9|firmware'
```

Module paths show the files selected on disk; they do not by themselves prove
successful codec initialization. Check the kernel log and select the AE-9 in
your desktop audio settings. DKMS is configured to rebuild automatically for
eligible kernel updates.

To remove this version from the target kernel:

```sh
target_kernel="$(uname -r)"
sudo dkms remove -m sb-ae9 -v 0.2.0-preview11-voice2 -k "$target_kernel"
```

Refresh its initramfs if needed and reboot. If an earlier manual installation
replaced distribution modules, restore those from the distribution's kernel
packages as well.

## What U Hear in desktop applications

DKMS installation also installs standard desktop profile data for the AE-9.
With the normal **Analog Stereo Duplex** profile, the microphone and
**AE-9 What U Hear** are exposed together after reboot, without a separate
activation command. What U Hear records the card's playback mix; select it
explicitly in the application that should capture that audio. Its lower
selection priority keeps the microphone preferred. No additional resident
program is installed.

The integration is selected only for the AE-9 PCI subsystem. It extends the
installed ACP default profiles, retains their playback mappings (including
surround and optical), and does not edit the distribution's stock files or
per-user settings. Microphone duplex profiles gain the separate ALSA PCM 2
input. A lower-priority microphone-only profile remains available if What U
Hear cannot be opened. Profiles containing only What U Hear use ACP fallback
selection; the combined profile has the normal native stereo priority.
Output-only, Off, Pro Audio and explicit custom profiles retain their normal
behavior; they do not automatically gain this input.

PipeWire with its ALSA card profiles and WirePlumber 0.4 or 0.5 is the target
desktop setup. On the reference Mint system with PipeWire 1.0.5 and
WirePlumber 0.4.17, a user trial confirmed automatic visibility, recording of
playback through What U Hear, and continued microphone operation with the
microphone retained as the default input. These observations cover the
desktop profile data; the complete DKMS hook lifecycle has only been tested
offline. WirePlumber 0.5 configuration has also only been checked offline.
Systems without installed ACP profile data keep a kernel-only installation.
Other session managers and distribution variants remain unqualified.

The source is configured for stereo, 48 kHz, `S32_LE` with WirePlumber. This
container format does not establish 32-bit signal precision. No sample-rate
policy, playback effect, default-source setting or kernel route is changed.
The installer does not restart services, trigger devices or start recording;
use the normal reboot after installing the driver.

DKMS removes its unchanged desktop data when the last kernel/package target
using it is removed. Files edited by an administrator are preserved and
reported for manual review. The ownership record is
`/var/lib/sb-ae9/desktop-files.json`. Check the desktop hook messages during
installation; a DKMS module installation alone does not prove that a desktop
source was successfully created.

## Credits

This project builds on Linux's CA0132/HDA drivers and the AE-9 community's
reverse engineering and development. Original source notices are retained.

- [DarkNikGr/sb-ae9](https://github.com/DarkNikGr/sb-ae9) — source base for this driver and subsequent AE-9 development.
- [verzic/sb-ae9](https://github.com/verzic/sb-ae9) — related AE-9 driver development and research.
- [3xHelix/SbAe9-Drv](https://github.com/3xHelix/SbAe9-Drv) — independent AE-9 driver development and research.

Crediting these projects does not mean that every feature in their current
branches is included here. See [COPYING](COPYING) and the source headers for
licensing information.
