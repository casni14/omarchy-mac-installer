# J616s developer installer

This branch builds a private candidate for the 16-inch M4 Pro, `apple,j616s`. Its catalog must be sealed into an `OmarchyDeveloperBuild`. Other Macs continue to use the upstream catalog. Physical installation of this fork remains pending.

The Linux desktop starts from Omarchy 4.5.0 r2's official signed-catalog payload. The platform transaction replaces its M1–M3 bootloader and platform packages with Aurora's immutable `testing-20261101.4` snapshot, the snapshot used with Aurora Installer Alpha 14. `packages.json` pins every package. The Aurora key is pinned by SHA-256 and each package signature is checked independently before installation.

Aurora's [J616s bring-up evidence](https://github.com/aurora-silicon/aurora-installer/commit/64a88d00873351d623cb9d2c6b050679bd735109) records raw Stage 1 enrollment from a macOS 26.6.2 stub. This candidate uses that raw contract. Stage 1 is personalized with the new ESP UUID. Stage 2 contains only the package-owned `t6040-j616s.dtb`, Aura and U-Boot. `/etc/default/update-m1n1` keeps that board selection during refresh. Recovery retains the finalized Stage 1, Stage 2 and per-device vendor firmware in its repair baseline.

The engine selects the 25G83 restore image and a 6 GB stub, validates the running macOS system's BCM4388 C2/hostomel Wi-Fi firmware before partitioning, and tolerates camera daemons moved to `usr/libexec` or omitted from Recovery. Proprietary per-device firmware is collected on the target and is absent from the distributed image.

## Image preparation

Use a dedicated build directory on a filesystem with at least 45 GB free. Download the base URL in `extract-base.py` as `omarchy-base.zip`, and download the packages named in `packages.json`, their `.sig` files and `aurora-alarm.asc` from `https://github.com/aurora-silicon/alarm-aurora/releases/download/testing-20261101.4/` into `aurora-packages/`. The source base digest was verified against Omarchy's Ed25519-signed stable catalog.

Run `extract-base.py BUILD_DIRECTORY` once to verify and extract into a new `image/` directory. Build the container from this directory's Dockerfile. Run it with the build directory mounted at `/build` and this directory read-only at `/source`, executing `bash /source/prepare-image.sh`. Its privileged filesystem operations are confined to the downloaded images. It updates the kernel, initramfs and Limine UKI, checks pacman's dependency database, and rebuilds `@factory` with the J616s platform.

Build the native Recovery template using `Recovery/build-recovery.sh`. Run `assemble-payload.py` with `--build`, `--recovery`, `--metadata` (the official base's `installer_data.json`) and a new `--output` directory. Include the locked upstream Asahi checkout's root and `src` directories in `PYTHONPATH`. The assembler validates the Recovery inventory and boot layout, excludes old boot backups and emits J616s-only metadata and provenance. Run read-only btrfs/ext4/FAT checks before packaging.

Rebuild and repin the engine using `docs/engine-versions.md`, including two identical reproductions. Compile and test the installer in debug and release. Package a developer/offline build with a locally generated Ed25519 catalog key and the rebuilt engine, metadata and payload. Keep the private key outside the repository and outputs. The sealed developer catalog enables only `apple,j616s`.

The test app uses ad-hoc signatures. Its package binds the root helper to the exact app hash and the restore decoder to its exact hash. The app also pins the helper hash. A Developer ID and notarization are separate distribution work.

## Update constraint

The candidate's pacman `IgnorePkg` keeps Aura, m1n1, the Aurora kernel and headers, U-Boot, Mesa and Vulkan at the tested snapshot. Test a coordinated platform upgrade before changing those pins. Omarchy desktop updates use the original repositories. A successful source build does not establish hardware boot, suspend, audio or peripheral qualification.
