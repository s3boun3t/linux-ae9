# AE-9 driver continuous integration

GitHub Actions runs the [AE-9 driver checks workflow](https://github.com/s3boun3t/linux-ae9/actions/workflows/ae9-driver.yml)
for the `ae9-driver` branch. Its definition is
[.github/workflows/ae9-driver.yml](../.github/workflows/ae9-driver.yml).

## Triggers and permissions

- Pushes to `ae9-driver` and pull requests targeting it, filtered to driver,
  build, installation and CI paths.
- Manual execution with **Run workflow**, restricted to `ae9-driver`.
- New executions cancel superseded runs for the same branch or pull request.
- One standard GitHub-hosted `ubuntu-24.04` job, limited to 20 minutes.
- `GITHUB_TOKEN` has `contents: read`; checkout credentials are not persisted.
- The job skips private repositories. Standard hosted runners are free for
  public repositories under [GitHub's billing rules](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

There is no schedule, `pull_request_target`, personal secret, artifact upload,
package publication, persistent cache, self-hosted runner or larger runner.
Build reports are printed in the job log.

The only action is `actions/checkout` **v5.0.1**, pinned to the complete SHA
`93cb6efe18208431cddfb8368fd83d5badbf9bfd`. It uses **Node.js 24**, replacing
v4.3.1 and its Node.js 20 deprecation warning.

## Checks performed

The job checks Python and JSON syntax, shell syntax for the desktop hook and
DKMS configuration, then runs the nine portable compiler-selection regressions
in `tests/test_build.py`.

It verifies and extracts the pinned kernel header packages, builds both
`snd-hda-core` and `snd-hda-codec-ca0132` with `W=1`, and checks cleanup.
`ci/build.py` works in a temporary source copy, records source/module hashes,
and never installs or loads a module. No full kernel build is performed.

The workflow depends on:

- `ci/build.py`: isolated module build, reports and cleanup checks;
- `ci/headers.py`: package verification and header extraction;
- `ci/kernels.json`: exact target release, package URLs and SHA-256 values;
- `tests/test_build.py`: compiler-selection regressions;
- the package's `build.py`, driver sources and Makefiles.

## Kernel target and dependencies

The current target is **Ubuntu `7.0.0-42-generic`, with GCC 13**. This is
independent of the kernel running on the Ubuntu runner: the exact release and
matching header directory are passed explicitly to the build helper.
The package supports the documented Linux 7.0–7.3 preview range; it does not
support Ubuntu's stock 6.x kernel merely because the runner is ubuntu-24.04.
One pinned target keeps this first CI small. XanMod/LLVM 21 is a separate
build qualification, not a second hosted job.

Both official Ubuntu header package URLs and SHA-256 values are pinned in
`ci/kernels.json`. All package hashes are checked before extraction; no kernel
package is installed and no package maintainer script runs. Missing or changed
packages fail the job instead of selecting a newer kernel.

Build tools are provisioned only on the disposable runner, using
`build-essential`, `gcc-13`, `libelf-dev` and `libssl-dev`. Ubuntu runner images
and APT security updates are rolling; this is not a bit-for-bit reproducible
toolchain image.

## Verified execution

The [Node.js 24 workflow run](https://github.com/s3boun3t/linux-ae9/actions/runs/42513709525),
for commit `275b3d2a607f3d8f709d363cf76e0f606e55957f`, completed successfully:
script syntax checks, all nine compiler tests, HTTPS retrieval and verification
of the pinned headers, module compilation and cleanup. Its job log contains
no Node.js 20 deprecation warning.

Inspect later results under **Actions -> AE-9 driver checks**. Expand the job
and its steps for diagnostics; no downloadable artifact is produced.

## Reproduce without installation

Choose a new extraction output directory; it must not already exist:

```sh
python3 -B ci/headers.py --package-dir /var/cache/apt/archives \
  --output-dir /tmp/ae9-ubuntu-headers
python3 -B ci/build.py --kernel-release 7.0.0-42-generic \
  --kdir /tmp/ae9-ubuntu-headers/usr/src/linux-headers-7.0.0-42-generic
python3 -B tests/test_build.py
```

Omit `--package-dir` to retrieve the pinned packages over HTTPS instead.

## Scope and limits

The hosted workflow does not run the full synthetic driver suite or the native
ACP/desktop installer tests. It does not qualify the DKMS lifecycle, Secure
Boot, WirePlumber variants, other distributions or other kernel configurations.
Its results do not turn the accepted version range into a compatibility
guarantee. Compilation and simulation do not prove AE-9 hardware operation.
No firmware, audio stream or hardware test is required by the workflow.
