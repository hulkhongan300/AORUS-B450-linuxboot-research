# Coreboot Porting Map — Gigabyte B450 AORUS PRO

Synthesis of all reverse-engineering done in sessions 1–5. Maps each hardware block to the data we
extracted and the coreboot mechanism that would consume it. **This is a feasibility/reference map, not
a claim that a port is practical** — the blockers in `FINDINGS.md §3/§5` stand. Everything here is from
static analysis of `B450AORUSPRO.F67c`; nothing was flashed.

> Draft coreboot mainboard scaffolding translated from this data lives in [`coreboot_reference/mainboard_draft/`](./coreboot_reference/mainboard_draft/) (reference only, not buildable).

## The one-line verdict
A coreboot port is **blocked by missing AMD code**, not by missing board knowledge. The board-specific
data (below) is now fully recovered. What is absent is upstream AM4-desktop SoC support + public AGESA/
openSIL for Zen–Zen3 desktop, plus the PSP signature chain. The board data would only become useful
*if* AMD desktop AM4 silicon support existed in coreboot.

## Hardware block → data → coreboot mechanism

| Block | Recovered data | coreboot mechanism | Status |
|---|---|---|---|
| **Super I/O** (IT8686E @2E, **IT8792E @0xA60 confirmed live**) | `superio_it87_tables.txt`, `coreboot_reference/superio_devicetree.cb` | `src/superio/ite/*` + devicetree | driver absent (it8689e closest); data complete |
| **LPC decodes** | FINDINGS §4d (FCH 00:14.3 cfg 0x44/48/64/66/74/90) | `soc/amd/common/block/lpc` | data complete |
| **GPIO** (board init) | `board_gpio_table.txt` (`$A10`) | `soc/amd/*/gpio.c` `PAD_*` macros | data complete, pin-mux caveat |
| **GPE/SCI wake** | `board_gevent_table.txt` (`$A11`): GEVENT8/10/13; GPE0A = CPM MYRTLE SSDT | `soc/amd/*/smi.h` SCI map | data complete |
| **PCIe lane map (DXIO)** | `pcie_dxio_topology.txt` (`$A26`) | `fsp_dxio_descriptor` / platform_descriptors.h | data complete |
| **PCI IRQ routing** | `pci_irq_routing.txt` (`_PRT`) | `mp_irq`/`intr_data` + FCH IO-APIC | data complete |
| **B450 chipset init** | `PROMONTORY_FW_LOADER.md` (full upload + CBS + SATA + GPIO) | **no coreboot equivalent exists** | would need a new driver |
| **Chipset firmware blob** | carved + checksum-verified `promontory_fw/` | cbfs raw blob | reusable as-is |
| **DRAM config** | APCB inventory + tokens (`apcb_*.txt`) | AMD APCB (opaque) | reuse AMD blob only |
| **PSP/ABL/SMU/PMU** | `amdfw_psp_combo.txt` (6 gens, cksum OK) | amdfwtool packs signed blobs | reuse unmodified |
| **CPU microcode** | `amdfw_microcode.txt` (7 families) | cbfs `cpu_microcode_blob` | reuse unmodified |
| **ACPI (DSDT/SSDT)** | `acpi/*.dsl` (4 DSDTs) + live `LIVE_ACPI.md` | `acpigen` / static ASL | data complete |
| **ACPI runtime tables** (IVRS/CRAT/CDIT/AmdTable/FCH/CPM/AOD) | `LIVE_ACPI.md` (not in flash) | AGESA/openSIL emits them; port must regenerate | **no AM4 code** |
| **Board hw-mon/fan** | FINDINGS §4f (`GbtCrbPei`) | board `mainboard.c` | data complete |

## What is reusable vs. must-be-written

**Reusable unmodified from the stock image** (PSP-signed; a port cannot re-author them):
- All 6 PSP generations' bootloader/trusted-OS/SMU/ABL/SEC-gasket (`amdfw_psp_combo.txt`)
- PMU (DRAM PHY) firmware, APCB, APOB (BHD2)
- 19 microcode patches (`amdfw_microcode.txt`)
- Promontory `_PT_` firmware (`promontory_fw/`, checksum-verified)
- → these go into the amdfwtool-built AMDFW region at the fixed EFS/BHD offsets.

**Replaceable** (the only x86 code a port controls) — the EFI firmware volumes (all GUID `78e58c8c…`, verified `_FVH`):
- Main DXE FV @ `0x94f000`, len `0x4f0000` (~5 MB) — the bulk of the UEFI BIOS (309 DXE drivers).
- PEI/bootblock FV @ `0xe40000`, len `0x1c0000` (~1.75 MB). The **BHD type-0x62 "BIOS_RTM_VOLUME"** entry points at `0xe42000` (just past this FV's header) with the *decompressed* size (~3.9 MB) — i.e. it is the measured PEI volume, the root-of-trust region the PSP checks.
- NVRAM FV @ `0x37000` (128 KiB, UEFI variables).
- coreboot would occupy these FV regions; the surrounding AMDFW (PSP/BHD signed blobs) stays fixed.

**Would have to be written from scratch** (no upstream code):
1. AM4-desktop SoC dir under `src/soc/amd/` (Summit→Vermeer FCH + DF + DXIO glue)
2. Promontory chipset driver (the `PROMONTORY_FW_LOADER.md` sequence, ~1500 lines of logic)
3. IT8686E + IT8792E superio drivers
4. The Gigabyte B450 AORUS PRO mainboard dir (devicetree from the tables above)

## Honest blocker summary (unchanged from §3)
- No public AGESA/openSIL for Zen–Zen3 **desktop** (openSIL is Zen4+ only — verified in tree `bd5c2139`).
- PSP verifies the bootblock/ABL against fused keys; retail AORUS boards ship fused for production.
- The stock image is a 6-generation combo; a port targets one generation.

## If the goal is "open firmware on this board" (not coreboot specifically)
See **`OPEN_FIRMWARE_OPTIONS.md`** for the full route comparison. The lower-risk path remains LinuxBoot/UEFI-payload: keep the signed SEC/PEI/AGESA/PSP stack and the
Promontory init intact, replace only the DXE payload in the BIOS_RTM_VOLUME. All the DXE module analysis
from sessions 1–2 supports that path, and it sidesteps every blocker above.
