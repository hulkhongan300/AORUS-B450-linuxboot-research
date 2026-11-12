# DRAFT coreboot mainboard scaffolding — Gigabyte B450 AORUS PRO

**Status: reference only, NOT buildable.** These files translate the reverse-engineered board data
into coreboot form so a future port has a concrete starting point. They **cannot compile today** because
coreboot has no AM4-desktop SoC (`soc/amd/am4_desktop` is a placeholder) and no IT8686E/IT8792E superio
drivers. See `../../PORTING_MAP.md` for why that gap — not board knowledge — is the blocker.

## Files and their data sources (all verified against the stock image and/or live hardware)

| File | Source | Confidence |
|---|---|---|
| `gpio.c` | `$A10` table → `board_gpio_table.txt` | high (raw values exact; PAD_NF function *names* unknown) |
| `dxio_descriptors.c` | `$A26` table → `pcie_dxio_topology.txt` | high; cross-checked vs live `lspci -t` |
| `devicetree.cb` | DSDT `_ADR` + live `lspci` + superio decode | high for topology; SoC chip name hypothetical |
| `Kconfig` / `Kconfig.name` | ROM size 16 MiB (verified), board name | high |
| `board_info.txt` | public board specs | n/a |
| `Makefile.mk` | standard coreboot layout | n/a |
| `mainboard.c`/`bootblock.c`/`romstage.c`/`dsdt.asl` | skeletons w/ TODOs citing the RE | low (structure only) |
| `board.fmd` | `../../flash_layout_full.txt` (16 MiB region map) | high for stock map; coreboot layout proposed |

(Fan/HWM init sequence for `mainboard.c`: `../../fan_hwm_init.txt`.)

## What is still missing before this could build (in dependency order)
1. **`src/soc/amd/am4_desktop`** — a new SoC dir (Summit→Vermeer): FCH + Data Fabric + DXIO/UMC glue,
   wrapping AMD's AGESA/ABL blobs (which exist in the image: `../../amdfw_psp_combo.txt`). No public code.
2. **Promontory (B450) chipset driver** — port `../../PROMONTORY_FW_LOADER.md` (firmware upload + CBS + SATA
   + GPIO). ~1500 lines of logic; the signed `_PT_` blob is reusable (`../../promontory_fw/`).
3. **`src/superio/ite/it8686e` and `it8792e`** — new drivers (it8689e is the closest template;
   register sequences are in `../../superio_it87_tables.txt`).
4. **ACPI** — `dsdt.asl` + acpigen for IVRS/CRAT/CDIT/SSDTs the stock AGESA emits at runtime
   (`../../LIVE_ACPI.md`); the 4 stock DSDTs are in `../../acpi/`.
5. **amdfwtool integration** — pack the 6-generation PSP/BHD signed blobs at their fixed offsets
   (`../../amdfw_psp_combo.txt`, `../../firmware_volume_map.txt`) + the 19 microcode patches
   (`../../amdfw_microcode.txt`).
6. **PSP unlock** — even complete, the PSP verifies the bootblock against fused keys; retail AORUS boards
   ship fused for production (`../../FINDINGS.md` §3). This is the hard external blocker.

## Honest bottom line
Steps 1–5 are "merely" a large amount of engineering grounded in the data here. Step 6 is a wall that
is not removable in software. The realistic open-firmware path for this board remains LinuxBoot/UEFI
payload (keep the signed init stack, replace only the DXE volume) — see `../../PORTING_MAP.md` §"If the goal…".
