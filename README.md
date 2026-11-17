# Sound Blaster AE-9 Linux driver

An experimental ALSA/HDA driver for the **Creative Sound Blaster AE-9** and
its external **Audio Control Module (ACM)**, with playback, microphone,
SBX/CrystalVoice effects and desktop volume controls.

## What works?

Status for **`0.2.0-preview45-dac-ramp1-native-hda-output-presets1-a`** on one Linux Mint / XanMod
reference system. This preview adds AE-9-specific DAC output presets and
includes the DSP startup-state checks and bounded InFX status handling from
the preceding `state1-a` candidate.

| Feature | Hardware status |
|---|---|
| Startup sound, music, desktop volume and ACM knob | Reported working on this preview |
| SBX ON/OFF during music playback | Reported working on this preview |
| Microphone and InFX in Discord | Five successful switches reported on `state1-a`; audible capture has yet to be checked on this preview |
| Direct stereo playback at 48 / 96 / 192 kHz | Experimental; headphone playback reported at 48 and 192 kHz on earlier previews; 96 kHz remains unqualified |
| Live Direct ↔ DSP switching | Earlier brief tests at 48 kHz reported a short audible gap; broader testing is pending |
| ACM display, 3.5 mm jack detection and What U Hear | Implemented and observed in earlier tests; further testing on this preview is pending |
| Front RCA speakers, surround and optical | No complete hardware validation; the new speaker preset has yet to be tested |
| ACM recovery after configuration loss, suspend/resume and prolonged duplex audio | Hardware validation pending |
| Direct at 44.1 / 88.2 / 176.4 / 384 kHz, multichannel, optical or DSD | Outside the implemented Direct mode |

The software suite passed 36 groups and the three modules built together on
the target kernel. The reference boot reached the expected DSP states
`3 → 4 → 5 → 0`. Other sound cards, including AE-5 and AE-7, remain
unqualified by this project.

## Install

### 1. Check your system

This preview targets **`7.3.3-x64v3-xanmod1`, x86_64 only**. Check with
`uname -r`. Other kernels are refused by the build configuration.

Install **Git, DKMS, Python 3, Make, the exact kernel's development headers
and LLVM/Clang 21**. On Ubuntu/Mint, the header package is
`linux-headers-7.3.3-x64v3-xanmod1`. The build helper selects a matching
compiler from the installed tools.

The package replaces **three modules together**: `snd-hda-core`,
`snd-hda-codec` and `snd-hda-codec-ca0132`. The first two are shared with
other HDA devices. Keep a working kernel or previous driver available.

### 2. Prepare the firmware

Two files are required:

- `ctefx-desktop.bin`
- `ae9-dsp-output-overlay.bin`

Follow the [firmware guide](https://github.com/s3boun3t/linux-ae9/wiki/Firmware)
to obtain them and check their full hashes. Creative's firmware and Windows
installers are **not included** in this repository. The Windows installer is
only unpacked, never run.

The preferred directory is `/lib/firmware/creative/ae9/`; existing working
files in `/lib/firmware/` remain supported. The firmware guide uses that
older location. Follow the commands below for the current driver rather
than the wiki's older driver installation instructions.

### 3. Build and install

These commands are for a first installation on the supported running kernel.
Stop if any command fails.

```sh
git clone --depth 1 --single-branch --branch ae9-driver https://github.com/s3boun3t/linux-ae9.git sb-ae9
cd sb-ae9
dkms status
```

If another AE-9 driver is installed, resolve that installation before
continuing. Do not use `--force` to overwrite another provider. For an update,
keep the previous working version until the new version has built successfully.

```sh
target_kernel="$(uname -r)"
sudo dkms add .
sudo dkms build -m sb-ae9 -v 0.2.0-preview45-dac-ramp1-native-hda-output-presets1-a -k "$target_kernel"
sudo dkms install -m sb-ae9 -v 0.2.0-preview45-dac-ramp1-native-hda-output-presets1-a -k "$target_kernel"
```

If this exact version is already registered, skip `dkms add .`.
**Automatic installation for future kernels is disabled** in this preview.

If Secure Boot is enabled, complete your distribution's DKMS signing and
key-enrollment procedure before rebooting. If your boot image contains HDA
modules, refresh it for this kernel. On Ubuntu/Mint:

```sh
sudo update-initramfs -u -k "$target_kernel"
```

**Reboot normally**, then select the AE-9 in your desktop sound settings.
Avoid unloading the shared HDA modules during use.

## Using the driver

- Use the desktop volume control or the ACM knob for volume and mute.
- In DSP mode, the ACM SBX button toggles playback effects. In Direct mode,
  it returns to DSP and enables SBX.
- For microphone recording, select the AE-9 microphone in your application.
- For playback capture, select **AE-9 What U Hear** in DSP mode. With the
  **Analog Stereo Duplex** desktop profile, the installation provides this
  input alongside the microphone on supported PipeWire/WirePlumber setups.
- Advanced controls are available in `alsamixer`: select the AE-9 with `F6`.
  **AE-9: Direct Mode Switch** is off by default.

Direct mode disables playback effects and EQ while retaining their settings.
It accepts stereo `S32_LE` at 48, 96 or 192 kHz. Close What U Hear before
enabling it. Start at low volume when comparing DSP and Direct modes.

## Known limits and troubleshooting

- Direct/SBX transitions are muted briefly; they are not gapless.
- Direct mode does not guarantee bit-perfect output: applications or
  PipeWire may resample. A negotiated rate is not a measurement of the DAC clock.
- DSP mode accepts a 192 kHz stream, but its internal route remains at 96 kHz.
- The reference boot logged an HDA timeout on command `0x11602095` and
  switched to polling. Earlier previews also logged a startup HDA timeout.

For an issue, include your kernel, driver version, affected connection and
these outputs, after checking them for personal information:

```sh
uname -r
dkms status
journalctl -k -b | grep -Ei 'ca0132|ae-9|firmware'
```

Report problems through [GitHub Issues](https://github.com/s3boun3t/linux-ae9/issues).
Do not attach firmware or Creative installers. The [wiki](https://github.com/s3boun3t/linux-ae9/wiki)
contains research and historical notes; check each page's revision before
following older installation or compatibility instructions.

To remove this version from the running kernel:

```sh
sudo dkms remove -m sb-ae9 -v 0.2.0-preview45-dac-ramp1-native-hda-output-presets1-a -k "$(uname -r)"
```

Refresh the boot image if needed, then reboot. An earlier manual installation
may also require restoring the distribution's original HDA modules.

## Credits and license

Based on Linux's CA0132/HDA drivers and
[DarkNikGr/sb-ae9](https://github.com/DarkNikGr/sb-ae9), with research from
[verzic/sb-ae9](https://github.com/verzic/sb-ae9) and
[3xHelix/SbAe9-Drv](https://github.com/3xHelix/SbAe9-Drv).
Their features and installation packages are not interchangeable with this driver.
Original notices are retained; see [COPYING](COPYING) and source headers.
