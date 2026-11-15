# Sound Blaster AE-9 — Linux DKMS driver

An ALSA driver for the **Creative Sound Blaster AE-9 PCIe sound card** and
its external **Audio Control Module (ACM)**. This DKMS preview
consolidates the AE-9 voice and stability improvements as three DKMS modules: `snd-hda-core`, `snd-hda-codec` and
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
suspend/resume are not fully qualified. Experimental Direct stereo playback
was reported working at 48/192 kHz on the reference machine. This candidate
adds live Direct/DSP switching. Preview35 is installed on the reference
machine; two 48 kHz transitions were observed without a PCM restart, with
a brief audible interruption. Prolonged, duplex, 96/192 kHz live switching
and suspend/resume qualification remain incomplete.

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
AEC comparison. This consolidated source includes shared VoiceFX identifiers. Prolonged
voice sessions and suspend/resume remain unqualified. Other CA0132 cards retain their stream 3/4 handling.

Output routing now has a separate applied-state flag. Errors prevent new
playback preparation and ACM output writes until a complete selection succeeds.
The periodic jack poll does not retry a failed switch on an unchanged jack.
An explicit selection or codec init can restore the route. Speaker configuration
controls also report failures and retain their previous cached values. These
changes are restricted to AE-9; successful software command sequences do not
prove physical DAC state or audio quality.

## Common DAC playback volume

Master volume and mute use the ES9038 stereo DAC for SBX, DSP playback
without effects, and Direct playback. The ACM knob and desktop retain the
same ALSA controls and dB scale. The HDA output amplifier is set to 0 dB
and unmuted; DSP playback gain stays at unity. This avoids applying both
HDA and DAC attenuation to the same signal.

The virtual Master supplies the effective left/right follower levels.
The driver converts their advertised HDA scale to the DAC's 0.5 dB steps,
rounding toward more attenuation when necessary. The OLED displays the
louder channel's commanded DAC level, or MUTE. That command cache is not
hardware readback or an audio measurement.

User mute is distinct from the temporary mute used during transitions and
failures. Saved levels are reapplied before startup unmute. Capture gains,
DAC master trim, volume ramp settings and the other DAC are unchanged.
No fixed DSP/Direct gain compensation is introduced.

Live volume changes use a 4–4.5 ms settle per DAC level command, following
3xHelix revision 9a661afe. The two commands therefore request 8–9 ms of
settling instead of 40 ms; scheduler and I/O time come in addition. Mute,
startup and restoration retain their existing 20 ms waits. Writes remain
synchronous so the desktop receives completion after the DAC commands.
This reduces control latency; removal of audible interruptions during rapid
volume changes still requires a hardware trial.

The preceding Direct candidate played audio while Master changed only the
bypassed HDA amplifier, leaving its audible level unchanged. This candidate
corrects that command path. Volume, mute, both channels and mode/output
transitions still need low-level hardware qualification after installation.
The failure-stage logs for the earlier Direct preparation error are retained;
that separate error has not been explained by a reproduced failure.

## Experimental Direct playback

`AE-9: Direct Mode Switch` selects stereo playback without the playback DSP
processing path. It is off by default and is available in alsamixer or
amixer. For prepared stereo playback at 48, 96 or 192 kHz, mode changes
run asynchronously so ALSA control reads can continue feeding the PCM.
The codec route changes under mute without explicitly restarting the
controller DMA or changing the negotiated PCM format. This does not yet
establish uninterrupted hardware playback. A prepared stream
must use a stereo 24-bit or 32-bit HDA transport at one of these rates;
other active formats are refused with `-EINVAL` before programming.
An open What U Hear stream blocks entry to Direct with `-EBUSY`.

Direct playback accepts two channels in `S32_LE` at 48, 96 or 192 kHz.
Other rates, including 44.1 and 384 kHz, are rejected. The first version
covers ACM headphones and front RCA. Multichannel, optical and DSD Direct
playback are outside its scope. The firmware remains loaded for control and
capture. The negotiated PCM rate and transport format do not demonstrate
the physical DAC clock or 32-bit analog precision.

Playback effects and EQ become inactive while their saved settings are
retained. The SBX LED stays off in Direct. Pressing the ACM SBX button
returns to DSP and enables SBX, including during playback. In DSP mode
the button retains its normal SBX on/off behavior. Outside a pending mode
transition, output selection, Master volume, mute, the ACM knob and DAC
filter remain available. Saved effects
return in DSP mode; DSP playback now also admits 192 kHz. The DSP route
and DAC clock configuration remain at 96 kHz; a 192 kHz ALSA stream is not
a claim of native 192 kHz DSP processing.
Transitions are muted; failed programming detaches playback and reports an
error rather than silently using the DSP path.

During prepared playback, Direct and `Enable OutFX Playback Switch` writes
accept a request; they do not report completion of the hardware operation.
The mode and OutFX getters show the accepted request while it is pending.
Other control reads use snapshots, and concurrent writes return `-EBUSY`
before entering the virtual Master callbacks. Completion updates the values
and effect availability and sends ALSA notifications. `AE-9: Last Mode Error`
reports zero after success or a negative errno after failure; the requested
mode returns to the retained applied state on failure, without claiming that
a partially changed hardware route was restored. When no AE-9 PCM stream
is open or prepared, ALSA mode writes apply immediately to preserve sequential
`alsactl` restoration. The physical SBX button uses the asynchronous path.
The transition still mutes the DAC; seamless audible switching is unverified.

Microphone capture and Voice Clarity remain independent. The existing
`Enable InFX Capture Switch` can disable voice effects, but it is not a
complete hardware DSP bypass. What U Hear returns `-EOPNOTSUPP` in Direct.
PipeWire or applications may still mix or resample before the card; this
switch alone does not guarantee bit-perfect playback.

This is a software-checked candidate. Before normal listening, separately
validate volume and mute at low level, both channels, all three rates,
return to DSP, microphone duplex, suspend/resume and ACM recovery. No fixed
gain offset is applied between DSP and Direct.

## Additional codec changes in this preview

The optional clock snapshot collector and `ae9_clock_diag` parameter are
removed. Remove obsolete `ae9_clock_diag=...` options from custom module
configuration before installing this version. PLL/I2S setup is retained.

AE-9 microphone boost writes both amp channels and forces a retry after a
failed write. Levels remain 0/+10/+20/+30 dB, with 0 dB as the default.
Firmware FLS segment bounds and the terminator are checked before transfer;
these structural checks do not establish cryptographic identity.

The primary AE-9 digital PCM is hidden while the secondary optical PCM is
retained. Saved ALSA PCM/control indices may change. The previous primary
widget initialization is retained, and the ACM headphone route uses physical
pin 0x10. RCA and optical operation remain unqualified.

AE-9 parameter exchanges retain transport errors. DSP LOW/HIGH writes stop
on HDA errors without replaying an ambiguously accepted half-word. SBX on an
already configured headphone route avoids a full output reroute. Failed SBX
transactions do not publish their desired cache/LED state, and an interrupted
SCP message blocks further writes until a confirmed DSP reset.

`ae9_dac_diag` is an optional read-only module parameter, disabled by default.
It repeats selected configuration-register reads and reports disagreement;
matching values do not prove freshness or physical DAC state. It is separate
from the removed clock collector and is not an audio-quality test.

The timeout at boot is not declared resolved. Favorable user reports concern
specific isolated candidates, including the three-module rirbread1 package.
The requested codec-only series was validated separately with two modules.
This combined experimental HDA package has not been qualified on hardware.

## Experimental HDA stage

This stage is rirbread1. It retains the exact PCI scope for AE-9 special
handling. ICW recovery and bounded RIRB rereads are not evidence that the
initial timeout is fixed. No earlyquirk1 refactor is included.

## ACM recovery and display

The ACM marker read is validated before its value is used. A reported loss
of setup invalidates jack observations and suppresses their use until setup
frames have been sent and the expected marker is observed again. Unknown or
malformed marker replies do not authorize recovery. Replay is limited to
three attempts per detected loss; existing transmit fault latches stay set.

The replay uses the current headphone/speaker and SBX state. It sends ACM
frames only, without a DAC reset, GPIO power cycle, HDA volume/mute update,
or microphone gain/phantom command. The first fresh headphone sample after
recovery establishes a new baseline and preserves the selected output.
Existing recovery after six missing keepalives also invalidates jack reports.
A cleared microphone jack report means presence is no longer trusted; it
changes neither the selected input nor its gain.

With polling enabled, the OLED holds AE-9 for at least five seconds, then
the current HP/SP label for at least five seconds, then displays the current
volume. The existing worker advances deadlines without sleeping for these
holds; knob turbo does not shorten them. UART exchanges retain their existing
wait limits. With polling disabled, initialization still shows volume and
parks the worker. Long SBX presses remain ignored.

Reopening playback or switching DSP/Direct with the same selected output
keeps the volume display. HP/SP is announced when the output changes,
at startup and after ACM recovery.

The preceding ACM recovery build was installed on the reference system.
Automatic reattachment after a configuration loss has not been exercised on
hardware. The preceding revision corrected and shortened source comments.
Direct mode keeps the ACM recovery path and supports the SBX shortcut.
These software guards do not prove that the physical ACM retained all
settings. The shared HDA sources are unchanged from the preceding
rirbread1 package.

## Compatibility

This experimental HDA package targets **7.3.3-x64v3-xanmod1 on x86_64 only**.
It builds the core, common codec/controller and CA0132 modules together.
Use matching target headers and LLVM 21. Module imports are checked, but
CONFIG_MODVERSIONS is disabled on this target, so no real CRC validation
is claimed. Other kernels and other HDA cards remain unqualified.

No GitHub Actions workflow is enabled in this branch. Local build and
regression reports are development evidence and are not part of the driver
package. The three modules must be built for the exact supported kernel.

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
sudo dkms build -m sb-ae9 -v 0.2.0-preview34-dspref-hold1 -k "$target_kernel"
sudo dkms install -m sb-ae9 -v 0.2.0-preview34-dspref-hold1 -k "$target_kernel"
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
sudo dkms remove -m sb-ae9 -v 0.2.0-preview34-dspref-hold1 -k "$target_kernel"
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

## Live switching candidate

The temporary `ae9_dsp192_probe` parameter is removed. DSP playback now
admits 192 kHz without an opt-in. Preview31's second manual probe completed
in about four seconds at the expected PCM progression rate, and the user
heard both channels. Its earlier one-sided timeout remains unexplained.
These observations do not qualify live switching in this new candidate.

A stream opened without prepared hardware defers routing until prepare.
Switching does not renegotiate an already open PCM: unsupported formats
must be closed and reopened. Microphone controls remain independent, but
concurrent capture and clock transitions still require hardware validation.

## DSP reference lifetime correction candidate

The preview33 hardware trace at 48 kHz showed stream 0x0c dropping from
one reference to zero immediately after unbinding the HDA input. The slot
sweep and subsequent DSP restoration then failed because they required
that allocation to survive. Earlier synthetic models kept it alive.

This candidate takes one verified extra reference before mute or detach.
It retains that reference across Direct/DSP transitions and PCM cleanup,
without taking another one on every cycle. Shutdown releases it explicitly;
full initialization verifies cleanup before resetting the DMA setup. An
ambiguous reference command blocks further route preparation until verified
full initialization, rather than retrying increments or guessing ownership.

No fixed DSP ports, controller DMA changes or microphone stream changes are
introduced. The existing allocation must be present when entering Direct:
a zero count is refused before destructive work; no reconstruction from
stale DSP ports is attempted. The inherited counter bound of eight remains
a conservative guard, not a demonstrated hardware limit.

This is a software-verified candidate only once its local verification
report passes. Live 48/96/192 kHz, both channels, microphone duplex,
suspend/resume and removal still need separate hardware qualification.
