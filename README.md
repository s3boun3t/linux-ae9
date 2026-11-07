# Sound Blaster AE-9 — Linux DKMS driver

An ALSA driver for the **Creative Sound Blaster AE-9 PCIe sound card** and
its external **Audio Control Module (ACM)**. This branch packages the stable
micjack1 driver as two DKMS modules: `snd-hda-core` and
`snd-hda-codec-ca0132`.

## Features

- Audio playback, headphone/speaker output selection, volume and mute controls.
- ACM volume knob, dB display and SBX button, with ALSA control synchronization.
- SBX playback effects, microphone capture and microphone effects controls.
- ACM headphone switching and 3.5 mm microphone jack presence reporting.
- DAC digital filter selection.

Playback, ACM controls and microphone operation have been reported working on
the reference Mint/XanMod system. Microphone jack presence is polled at roughly
five-second intervals. XLR/TRS detection, surround/optical output and
suspend/resume are not fully qualified. Direct mode and automatic native
sample-rate switching are not included in this branch.

## Compatibility

This is a **DKMS preview**, version `0.2.0-preview1`, for **x86_64 Linux
7.0–7.3** with the expected stable HDA/ALSA APIs. The HDA core and CA0132
codec must be configured as modules, not built into the kernel.

Both modules have been compiled against Ubuntu `7.0.0-42-generic` and XanMod
`7.2.14-x64v3-xanmod1`. Fedora, Arch and CachyOS kernels remain unqualified;
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
  sudo install -d /lib/firmware || exit 1
  sudo install -m 0644 ctefx-desktop.bin ae9-dsp-output-overlay.bin /lib/firmware/
)
```

The guarded block exits before installation on a mismatch. `/lib/firmware`
may resolve to `/usr/lib/firmware`. Refresh the initramfs if needed and reboot
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
sudo dkms build -m sb-ae9 -v 0.2.0-preview1 -k "$target_kernel"
sudo dkms install -m sb-ae9 -v 0.2.0-preview1 -k "$target_kernel"
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
sudo dkms remove -m sb-ae9 -v 0.2.0-preview1 -k "$target_kernel"
```

Refresh its initramfs if needed and reboot. If an earlier manual installation
replaced distribution modules, restore those from the distribution's kernel
packages as well.

## Credits

This project builds on Linux's CA0132/HDA drivers and the AE-9 community's
reverse engineering and development. Original source notices are retained.

- [DarkNikGr/sb-ae9](https://github.com/DarkNikGr/sb-ae9) — source base for this driver and subsequent AE-9 development.
- [verzic/sb-ae9](https://github.com/verzic/sb-ae9) — related AE-9 driver development and research.
- [3xHelix/SbAe9-Drv](https://github.com/3xHelix/SbAe9-Drv) — independent AE-9 driver development and research.

Crediting these projects does not mean that every feature in their current
branches is included here. See [COPYING](COPYING) and the source headers for
licensing information.
