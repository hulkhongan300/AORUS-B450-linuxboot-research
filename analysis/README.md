# Analysis Index — Gigabyte B450 AORUS PRO BIOS RE

Reverse-engineering of `B450AORUSPRO.F67c` (16 MiB, AGESA ComboAM4v2PI). All static analysis + two
read-only live checks on the actual board (Ryzen 7 2700X, BIOS F66i). Nothing was ever flashed.

## Read in this order
1. **`PORTING_MAP.md`** — coreboot porting map: every hardware block → recovered data → coreboot
   mechanism → status. The synthesis; start here.
2. **`LIVE_ACPI.md`** — runtime ACPI analysis (IOMMU, IO-APICs, tables AGESA generates at boot).
3. **`PROMONTORY_FW_LOADER.md`** — the B450 chipset firmware-upload + config protocol (the one block
   with no coreboot equivalent).
4. **`OPEN_FIRMWARE_OPTIONS.md`** — the achievable paths (coreboot vs LinuxBoot vs other board vs QEMU) with this board's constraints (RPMC anti-rollback, signed capsule, no DXE hash).
5. **`FINDINGS.md`** — the detailed per-area log (§4a–4n) with cross-references.
6. **`coreboot_reference/mainboard_draft/`** — draft coreboot mainboard files (not buildable; reference).

## Data files (`*.txt`) by topic
| Topic | File | Tool |
|---|---|---|
| Super I/O registers | `superio_it87_tables.txt` | `decode_it87_tables.py` |
| Fan/HWM init (IT8686E) | `fan_hwm_init.txt` | (GbtCrbPei decomp) |
| Board GPIO | `board_gpio_table.txt` | `decode_cpm_gpio.py` |
| GEVENT/SCI wake | `board_gevent_table.txt` | `decode_cpm_gevent.py` |
| PCIe/DXIO lanes | `pcie_dxio_topology.txt` | `decode_dxio.py` |
| PCI IRQ routing | `pci_irq_routing.txt` | `decode_prt.py` |
| CPM table inventory | `cpm_tables_inventory.txt`, `cpm_power_reset.txt` | `decode_cpm.py` |
| Promontory PHY/SATA defaults | `promontory_phy_defaults.txt`, `promontory_sata_defaults.txt` | `decode_pt_phy_defaults.py`, `pei_pcd.py` |
| GPE 0x0A resolution | `gpe0a_resolved.txt` | (live acpidump) |
| APCB structure + tokens | `apcb_inventory.txt`, `apcb_tokens_all.txt` | `apcb_inventory.py`, `apcb_tokens.py` |
| PSP/BIOS firmware dirs | `amdfw_psp_combo.txt`, `amdfw_directory.txt` | `amdfw_combo.py`, amdfwread |
| CPU microcode | `amdfw_microcode.txt` | `amdfw_microcode.py` |
| USB port map | `usb_port_map.txt` | `decode_usb_ports.py` |
| Firmware volumes / flash map | `firmware_volume_map.txt`, `flash_layout_full.txt` | (python one-offs) |

## Directories
- `coreboot_reference/` — `superio_devicetree.cb` + the `mainboard_draft/` file set.

**Not in this repo** (Gigabyte/AMD/AMI copyrighted material — regenerate from your own copy of the BIOS
with `../tools/`): `acpi/` (disassembled ACPI tables), `live_acpi/` (`sudo acpidump` of a running board),
`decomp/` (Ghidra decompilations), `modules/` (extracted PE/TE binaries), `promontory_fw/` (chipset
firmware blobs). The docs still name these paths so you know where each fact came from.

## Tools (`../tools/`)
Reverse-engineering helpers written for this project: TE→PE converter, Ghidra headless export, ACPI
extractor, CPM/DXIO/GPIO/GEVENT decoders, PEI PCD reader, APCB + PSP/BHD combo walkers, microcode
lister, Promontory FW carver, coreboot-in-QEMU runner. Each has a docstring; most take the image path.

## Status
Board hardware is **fully documented**. The two former open items (2nd Super I/O ID, GPE 0x0A source)
are **closed**. The coreboot blocker is missing upstream AMD AM4-desktop code + the PSP signature chain,
not board knowledge — see `PORTING_MAP.md`. `../CLAUDE.md` has the full session-by-session handoff.
