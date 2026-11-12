# tinylinux — a LinuxBoot payload small enough for the B450 AORUS PRO flash budget

**Result: 2,167,808 bytes (2.067 MiB) for kernel + boot menu + kexec, all in one EFI file — under the
2.17 MiB DXE budget measured in `../PROGRESS.md`. Boots and kexecs in QEMU/OVMF. Nothing flashed.**

## How it was shrunk (the coreboot recipe)
coreboot's LinuxBoot payload (`payloads/external/LinuxBoot/` in the coreboot tree) compiles a kernel from
kernel.org with its own small config instead of using a distro kernel. Same approach here:

| Step | Size of the one-file payload |
|---|---|
| CachyOS distro kernel + u-root UKI (`../efistub/`) | 20.0 MiB |
| `tinyconfig` + needed drivers built in, XZ, `-Os`, busybox (static) + kexec tool (static glibc) | 2.42 MiB |
| kexec tool rewritten without libc (862 KB → 9 KB) | 2.36 MiB |
| Trim what a boot menu never uses (below) | **2.067 MiB** |

Why the distro kernel is 17 MB: it carries drivers for every PC, every CPU vendor, networking, sound, GPUs,
all filesystems, debugging. A boot menu on one known board needs a tiny fraction.

### What is built in (`kernel.fragment`)
EFI stub, ACPI (PCI IRQ routing on real hw), PCI/MSI, `KEXEC_FILE` + `EFI_RUNTIME_MAP` (next kernel keeps
UEFI runtime), NVMe, SATA AHCI (Promontory), USB xHCI + mass storage + HID keyboard, PS/2 keyboard,
UEFI GOP framebuffer console, 8250 serial, VFAT (ESP). No modules, no networking, no SMP.

### What was trimmed
Initrd decompressors (the *target* kernel unpacks its own initrd), non-AMD CPU support, ACPI power drivers
(battery/fan/thermal/processor/button), EFI extras, PCI serial cards, legacy PATA, VGA text console, mouse,
extra I/O schedulers, smaller log buffer. x86 forces three options back on (microcode loader, perf events,
EFI ESRT) — `build.sh` reports this as `STILL ON`.

### Userspace (embedded initramfs)
- **busybox 1.37.0**, static, `allnoconfig` + 26 applets (shell, mount, sed, ...).
- **`kexec-boot.c`** — 50 lines, no libc, raw `kexec_file_load` + `reboot(KEXEC)` syscalls.
- **`init`** — ~50-line shell boot menu: scans every FAT partition for BootLoaderSpec entries
  (`loader/entries/*.conf`), shows a menu with a 5 s default, concatenates multiple `initrd` lines
  (amd-ucode + initramfs), kexecs. `s` = shell. Heads (coreboot+LinuxBoot) uses this busybox style;
  u-root (Go) did not fit — its runtime alone is ~2.8 MiB compressed.

## Files
| File | Purpose |
|---|---|
| `fetch.sh` | Downloads kernel.org 6.18.60 + busybox 1.37.0 into `../toolchain/src`, checks sha256 |
| `build.sh` | Builds everything from those sources |
| `kernel.fragment` | Kernel config on top of `tinyconfig` |
| `init`, `kexec-boot.c` | Boot menu + kexec tool |
| `run_qemu.sh` | OVMF + demo OS on emulated NVMe (`IMG=tinylinux.efi` for the screen build; `DEMO_KERNEL=` to kexec another kernel) |
| `out/tinylinux.efi` | **Real-board build**: menu on the monitor (`CONSOLE=screen`, default) |
| `out/tinylinux-serial.efi` | QEMU build: menu on serial (`CONSOLE=serial ./build.sh`) |
| `screen_menu.png`, `qemu_serial.log` | Evidence of the verified runs |

Build needs: gcc, make, flex, bison, bc, libelf, curl. QEMU test needs: qemu, edk2-ovmf, mtools.

## Verified (QEMU q35 + OVMF, 2026-11-11)
OVMF → `tinylinux.efi` (EFI stub) → menu after 8 s → BLS entry on NVMe → kexec → target kernel with
`efi: EFI v2.7`, `efivars` registered (UEFI runtime survived). Screen build shows the menu on the
framebuffer (`screen_menu.png`).

## Where this stands for the flash chip — honestly
- **Size: solved on paper.** 2.067 MiB fits the 2.17 MiB room, with ~105 KB spare.
- **That room only exists after removing the Setup menu, network stack, CSM and flash tools** from the
  DXE volume (tier 2a in `../PROGRESS.md`). You would lose the BIOS settings screen (XMP, fan curves,
  boot order) — settings would be stuck at whatever is saved.
- **A kernel alone can't replace the AMI boot manager.** DXE Core hands off to a driver that provides
  the BDS protocol; a plain EFI application isn't one. It needs a small BDS-replacement DXE driver
  that loads the kernel (the LinuxBoot project provides one). Not built here.
- **It cannot be tested without flashing**, which this project rules out. No modified ROM was produced.

## Safe next step on the real board (no flash, no settings changed)
Step-by-step with information gathering and an automatic checklist: `../diag/README.md`.

Copy `out/tinylinux.efi` to a FAT USB stick as `EFI/BOOT/BOOTX64.EFI`, pick it from the F12 boot menu.
This exercises the same kernel on the real NVMe/SATA/USB/ACPI hardware — the most validation possible
without touching the chip. It lists any OS that has a BLS entry; otherwise press `s` and run e.g.
`kexec-boot /mnt/nvme0n1p1/<kernel> /mnt/nvme0n1p1/<initramfs> "root=UUID=... rw"`.
