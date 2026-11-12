# On-disk LinuxBoot via the EFI boot stub (UKI) — tested in QEMU

The in-flash LinuxBoot payload does not fit this board's DXE volume (`../PROGRESS.md`: 2.17 MiB budget vs
~4–5 MiB needed). This directory takes the same LinuxBoot userspace (u-root + kexec) and puts it **on disk**
instead: the stock UEFI firmware launches it directly through the Linux **EFI boot stub** as a single
**Unified Kernel Image** (UKI). Nothing is written to the SPI flash.

## What this is (and is not)
- **Is:** firmware → `EFI/BOOT/BOOTX64.EFI` (kernel + u-root initramfs + cmdline in one PE file) → u-root
  boot menu (parses BootLoaderSpec / GRUB / syslinux configs on all disks) → `kexec` into the real OS.
  Everything after the firmware hand-off is open source.
- **Is not:** open *firmware*. The AMI UEFI (DXE, SMM, CSM, Setup) still runs in full before the UKI.
  It replaces the bootloader layer (on this PC: Limine, which is already open source), not the BIOS.
- No size limit (the ESP holds hundreds of MB), no flash, no capsule/RPMC/PSP involvement.

## Files
| File | Purpose |
|---|---|
| `build_initramfs.sh` | u-root initramfs (init, boot, gosh, kexec, ls, cat, mount, dmesg) **+ FAT and NVMe kernel modules** |
| `build_uki.sh` | Wrap kernel + initramfs + cmdline into one EFI executable (objcopy + systemd `linuxx64.efi.stub`, Arch-wiki method) |
| `run_qemu.sh` | Boot it under OVMF with a demo OS on an emulated NVMe disk (interactive, Ctrl-A X quits) |
| `esp/EFI/BOOT/BOOTX64.EFI` | The built UKI (20 MiB) — the fallback path firmware boots from removable media |
| `initramfs-uki.cpio.xz` | The initramfs inside it (3.07 MB) |
| `qemu_kexec_boot.log` | Serial log of the verified run |

## Verified result (QEMU q35 + OVMF, TCG, 2026-11-11)
1. OVMF boot manager loaded `BOOTX64.EFI` from the ESP (EFI stub, no bootloader).
2. u-root init auto-loaded the bundled modules → `nvme0n1` appeared, FAT mountable.
3. u-root `boot` found the BLS entry `loader/entries/demo.conf` on the NVMe disk → menu entry 01.
4. Default entry kexec'd the target kernel; its `/proc/cmdline` carried the marker `demo_kexec_ok=1`.
5. The kexec'd kernel kept UEFI: `efi: EFI v2.7 by EDK II`, `efivars: Registered efivars operations`
   (runtime services survive kexec_file_load).

## Gotchas found
- **CPU level:** the CachyOS kernel is built `X86_64_VERSION=3` (AVX2). QEMU's default `qemu64` CPU makes it
  reset-loop silently right after the firmware starts it → use `-cpu max` (or KVM `-cpu host`).
  The real 2700X has AVX2, so it is fine on hardware.
- **Modules:** this kernel has `VFAT_FS=m` and `BLK_DEV_NVME=m` (ext4, btrfs, AHCI, xHCI built-in). Without
  bundling `fat/vfat/nls_iso8859-1/hkdf/nvme-keyring/nvme-auth/nvme-core/nvme`, u-root sees the disks but
  cannot read the ESP or the NVMe SSD. u-root's init loads `/lib/modules/*.ko` alphabetically in one pass,
  so the build script prefixes them `00-`..`07-` in `modules.dep` order.
- **Config formats:** u-root `boot` reads BootLoaderSpec (`loader/entries/*.conf`), GRUB, syslinux and ISOs.
  It does **not** read `limine.conf`, which is what this PC currently uses — a real OS needs a BLS entry
  (or grub.cfg) next to its kernel for u-root to list it.
- **Secure Boot:** the UKI is unsigned. This PC reports Secure Boot disabled, so it would be accepted; with
  Secure Boot on it would need signing with your own enrolled keys (e.g. `sbctl`).

## Trying it on the real PC without touching firmware
Copy `BOOTX64.EFI` to a FAT-formatted USB stick at `EFI/BOOT/BOOTX64.EFI` and pick the stick from the
one-time boot menu (F12 on Gigabyte). That is an ordinary removable-media boot: no flash write, no boot-entry
change. Expect the u-root menu; it will list an OS only if one has a BLS entry/grub.cfg (see above).
For a console on the monitor rather than serial, rebuild with `console=tty0` in the cmdline.
