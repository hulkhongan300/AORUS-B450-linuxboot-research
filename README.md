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

## Backstory

This started as an attempt to replace the board's closed BIOS with open-source firmware ([coreboot](https://github.com/coreboot/coreboot)).
Reverse engineering the stock BIOS (`F67c`, 16 MiB) showed why that can't be done on this board:

- **AMD binary blobs are mandatory.** Before the x86 CPU runs any code, AMD's security processor (PSP)
  loads and checks AMD-signed blobs: the PSP bootloader, memory training (ABL), SMU and the chipset
  firmware. They can't be replaced. One BIOS file carries these blobs for 6 Ryzen generations.
- **The B450 chipset (Promontory) needs its own firmware.** The BIOS uploads a ~112 KB blob into it over
  a custom protocol. coreboot has no driver for it ([`PROMONTORY_FW_LOADER.md`](analysis/PROMONTORY_FW_LOADER.md)).
- **There is no AM4 desktop support in upstream coreboot.** It only supports AMD laptop/embedded chips.
- **Updates are locked.** Signed capsules and an anti-rollback counter (RPMC) mean the normal updater only
  accepts official Gigabyte images.

So the project changed direction to **[LinuxBoot](https://github.com/linuxboot/linuxboot)**. It keeps the
AMD/AMI hardware init and replaces only the part after it (the UEFI boot manager) with a small Linux
kernel. The size left in the chip turned out to be too small for a normal kernel, so tinylinux was built
coreboot-style (a `tinyconfig` kernel plus busybox) until it fit.

Other things found along the way (details in [`analysis/`](analysis/README.md)):

- The board is based on AMD's **"Myrtle"** reference design (AGESA ComboAM4v2PI 1.2.0.12).
- It has **two ITE Super I/O chips**: the IT8686E (main I/O and fans) and the IT8792E (extra fan and
  sensor chip at 0xA60).
- **Flash map**: AMD blobs take about 8.4 MiB, the main UEFI part (DXE) 4.9 MiB and the early init (PEI) 1.75 MiB.
- Full decoded tables: GPIO, PCIe lane setup, IRQ routing, USB ports, Super I/O registers, and a draft
  coreboot mainboard ([`coreboot_reference/`](analysis/coreboot_reference/)).
- **No ACPI fan control**: fans run autonomously in the Super I/O, set up once at boot.
