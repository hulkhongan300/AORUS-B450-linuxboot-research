# AORUS-B450-linuxboot-research

A tiny open-source Linux boot menu (LinuxBoot-style) for the **Gigabyte B450 AORUS PRO**, plus the
reverse-engineering notes behind it.

- **tinylinux**: one 2.07 MiB EFI file (Linux kernel, busybox menu and kexec). It finds your OS and boots it.
- Tested in **QEMU only**. Nothing here has been written to a BIOS chip.

## Quick start

```sh
cd linuxboot/tinylinux
./fetch.sh                   # download kernel + busybox (sha256 checked)
CONSOLE=serial ./build.sh    # -> out/tinylinux-serial.efi
./run_qemu.sh                # boot it in QEMU (Ctrl-A X to quit)
```

## Try it on the real board (USB stick, no flashing)

1. `./build.sh`, which builds `out/tinylinux.efi` with the menu on the monitor.
2. Copy it to a FAT32 USB stick as `EFI/BOOT/BOOTX64.EFI`.
3. Press F12 at power-on and pick the stick.

It lists every OS that has a BootLoaderSpec entry (`loader/entries/*.conf`). Press `s` for a root shell.
To check your PC first, see [`linuxboot/diag/`](linuxboot/diag/README.md).

## What's here

| Folder | What |
|---|---|
| `linuxboot/tinylinux/` | The boot menu: kernel config, `init` script, kexec tool, build + QEMU scripts |
| `linuxboot/diag/` | Read-only hardware info collector + readiness checklist |
| `linuxboot/efistub/` | Earlier, bigger try (distro kernel + u-root, 20 MiB) |
| `analysis/` | Board RE notes: flash map, GPIO, PCIe, Super I/O, Promontory, ACPI, coreboot draft |
| `tools/` | Python decoders used for the analysis |

## Status

| | |
|---|---|
| Boots and kexecs in QEMU/OVMF | ✅ |
| Fits the size left in the BIOS chip (2.07 of 2.17 MiB) | ✅ on paper |
| Runs from the BIOS chip | ❌ needs a BDS shim, costs the Setup menu, and can't be tested without flashing |
| coreboot port | ❌ no AM4/Promontory support upstream ([why](analysis/OPEN_FIRMWARE_OPTIONS.md)) |

Details: [`linuxboot/PROGRESS.md`](linuxboot/PROGRESS.md), [`analysis/README.md`](analysis/README.md).

## Not included

No BIOS image, no extracted vendor modules, ACPI tables, decompiled code or AMD blobs, and no built binaries.
Those are copyrighted by Gigabyte, AMD and AMI, or are build output. Bring your own BIOS file
(`B450AORUSPRO.F67c`, from Gigabyte's site) to re-run the analysis tools.

## Warning

Do not flash anything from this project to your board. A bad BIOS chip write can leave the board
unable to start.

## License

GPL-2.0 (see `LICENSE`), the same as the Linux kernel and busybox it builds.

Not affiliated with Gigabyte, AMD or AMI. Names are used only to identify the hardware.
