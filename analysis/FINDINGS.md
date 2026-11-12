# Session 2 Findings (2026-11-11): ACPI + Board-Init Decompilation

> **Start with [`PORTING_MAP.md`](./PORTING_MAP.md)** for the consolidated coreboot-oriented synthesis, and [`LIVE_ACPI.md`](./LIVE_ACPI.md) for the runtime-ACPI analysis. This file holds the detailed per-area notes (§4a–4l).

All artifacts are under `analysis/`. All of it comes from static analysis. Nothing was flashed.

## 1. ACPI tables (`analysis/acpi/`)
Extracted with `tools/extract_acpi.py`, which scans every `body.bin` for headers with a valid length and checksum. Disassembled with `iasl -d`.
35 static tables: 4 DSDTs + 31 SSDTs. FADT/MADT/HPET/MCFG are not stored; AMI builds them at runtime.

| DSDT file | Source FFS | Root ports | Likely CPU family |
|---|---|---|---|
| `DSDT_AMI_d65ff902` | 362 3642B53D… | GPP0–GPPF, GP17/18 | Zen/Zen+ desktop (Summit/Pinnacle Ridge) |
| `DSDT_AMI_db1572a8` | 364 8FF19984… | GPP0–GPPF, GP10–13, GP30/31 | Zen 2/3 desktop (Matisse/Vermeer) |
| `DSDT_AMI_71c66a6f` | 363 89D41B4B…9E86 | GPP0–6 + VGA/ACP/MP2C/I2S | APU (Raven/Picasso) |
| `DSDT_AMI_d6eeab4c` | 365 89D41B4B…9E11 | GPP0–9 + BROD/I2S | APU (Renoir/Cezanne) |

The family mapping is inferred from the device sets; verify it against AmdNbio module GUIDs if it matters.

Platform constants (DSDT globals, same in all four):
- MMCONFIG size `PEBL=0x08000000` (128 MiB). In PEI the code accesses it at **0xF0000000**.
- IOAPIC `0xFEC00000`, HPET `0xFED00000`, FCH ACPI MMIO `0xFED80000` (SMBus regs at `0xFED80200`)
- ACPI PM base `0x800` (len 0xA0), SMBus `0xB00`/`0xB20`, SMI command port `0xB2`
- SIO IO windows: `0xA00`/0x30, `0xA30`/0x10, `0xA40`/0x10, `0xA60`/0x10

Promontory (B450) on Matisse/Vermeer: behind `GPP2` (00:01.3). Upstream functions are `PT01`/`PT02`, downstream bridges `PT20`–`PT27` (dev 0–7), plus xHCI `PTXH`. The chipset also has its own SSDT: `SSDT_FCHPT_*`.

## 2. Ghidra decompilation (`analysis/decomp/*.c`)
PEIMs are TE images. `tools/te2pe.py` rebuilds a loadable PE32 for them (`analysis/modules/`). `tools/ExportDecomp.java` is a headless script that dumps C for every function.
Re-run with:
```
/opt/ghidra/support/analyzeHeadless <projdir> biosrea -import analysis/modules/*.efi -overwrite \
  -scriptPath tools -postScript ExportDecomp.java "$PWD/analysis/decomp"
```
Modules done: AmdCpmOemInitPeim (×2), AmdCpmGpioInitPeim, FchPromontoryGpioPei, FchPromontoryCbsPei, IT8728FPeiInit, FchPromontorySmmInit, IT8728FSmmFeaturesDxe, AmdCpmOemInitDxe.

## 3. Super I/O: TWO ITE chips (`analysis/superio_it87_tables.txt`)
The decode comes from `IT8728FPeiInit` (`tools/decode_it87_tables.py`).
- The module is generic Gigabyte code. It reads chip ID CR20/21 and handles IT8728/8620/8609/8628/**8686**/8688/8689.
- **Chip 1 @ 0x2E** (key `87 01 55 55`), expected IT8686E:
  - LDN4 EC/HWM at `0xA40` (HWM index/data `0xA45`/`0xA46`), PME at `0xA30`
  - LDN5 KBC at 0x60/0x64, IRQ1
  - LDN7 GPIO
- **Chip 2 @ 0x4E** (key `87 01 55 AA`), expected IT8792E (a fan/HWM companion):
  - LDN4 at `0xA60`
  - LDN7 at `0xA50`
  - LDN 0x10 at `0xA68`
  - LDN 0x0F enabled
- The FCH LPC decode is programmed through PCI config of **00:14.3** (`0xF00A3044/48/64/66/74/90`): IO decode enable, the 0x2E/0x4E enables, and wide-IO ranges for `0xA00`/0x50 and `0xA50`/0x20. In coreboot this corresponds to `soc/amd/common/block/lpc` (`lpc_enable_decode`, `lpc_set_wideio_range`).
- Neither IT8686E nor IT8792E has a driver in upstream coreboot, as far as known. Verify by checking `src/superio/ite/`.

## 4. AMD CPM board tables (`analysis/cpm_tables_inventory.txt`)
`AmdCpmOemInitPeim` holds many `$Axx` CPM tables (offset/signature/size listed). The per-board GPIO init, PCIe slot reset and device power tables live here.
The signature→meaning mapping is NOT yet verified. Use the AmdCpmPkg headers (`AmdCpmDefine.h`), for example from leaked or open AGESA trees, before trusting it.

## 4b. CPM tables decoded (continued)
Formats derived from the consuming code: `AmdCpmGpioInitPeim` and the CPM core `AmdCpmInitPeim`, the latter decompiled as `analysis/decomp/AmdCpmInitPeim_1.efi.c`.
- **Common header** (16 B): `u32 sig; u16 size; u8 fmt; u8 rev; u32 platform_mask; u32 attribute`.
- **`$A10` = board GPIO init.** `{u16 pin; u16 setting}`, terminated by pin 0xFF, applied through CPM `SetGpio` (`FUN_09e17810`).
  `setting` bits:
  - `0x80` pull valid: `0x20` pull-up, `0x40` pull-down, `0x04` pull-up strength sel
  - `0x08` leave direction unchanged; otherwise `0x02` input, else `0x01` output high / output low
  - `0x800` IOMUX valid, function = `(s>>8)&7`
  - pins ≥0x100 go to the remote bank (`+0x1200`/`+0x12C0`)
  - HW targets: `ACPIMMIO+0x1500+pin*4` byte 2 (bits 19–23) and IOMUX `ACPIMMIO+0xD00+pin`
  Decoded: **`analysis/board_gpio_table.txt`** (`tools/decode_cpm_gpio.py`).
  - OEM PEIM copy 1 = Zen/Zen+ (CPUID 0x800F00). Copy 2 = **Matisse/Vermeer** (CPUID 0x870F00 / 0xA20F00).
  - The copies differ on GPIO 115 (pull strength) and on the mux-1/2 inputs (95–99 vs 135–141).
  - Caveat: the `PAD_*` column ignores IOMUX. A pin is only a GPIO if its mux function is the GPIO function for that pin. Check against the FCH pin list.
- **`$A13` power sequence / `$A15` reset sequence.** 8-byte entries `{dev, mode, type(0 set,1 wait,2 delay,3 defer), u16 pin, u8 val}`. **Both are EMPTY in this ROM** (first byte 0xFF), so the board does no GPIO slot power sequencing.
- **`$A04`** = per-device enable flags. **`$A06`** = deferred items for pins tagged `0x300`.
- **`$A26` = DXIO lane descriptors** (`tools/decode_dxio.py` → **`analysis/pcie_dxio_topology.txt`**).
  - 16 records of 0x1A4 bytes starting at +0x14: `u32 flags (0x80000000 = end); u8 engine (1 PCIe / 3 SATA / 0 unused); u8 eflags; u8 start_lane; u8 end_lane; u32 gpio_group; u32 port_data (bit0 present, bits3-7 PCI dev, bits8-10 fn)…`
  - This is the same concept as coreboot's `fsp_dxio_descriptor` in `src/vendorcode/amd/fsp/*/platform_descriptors.h`.
  - Board topology (Matisse/Vermeer copy), consistent with the DSDT:
    - x16 slot: lanes 16–31 → **00:03.1** (GPP8). The x8/x4 split records are UNUSED, so no bifurcation.
    - B450 Promontory uplink: lanes 8–11 x4 → **00:01.3** (GPP2). The Zen/Zen+ copy has lanes 7→4, i.e. reversed.
  - M.2 (M2A, lanes 0–3) is **appended at runtime** by `AmdCpmOemInitPeim`:
    - If `GPIO8 == 0 && GPIO116 == 1`: PCIe x4 → **00:01.1** (GPP0).
    - Otherwise: a SATA engine (type 3, rec `0x3020003`, lanes patched to 4–5).
    - GPIO 8 and 116 are therefore the M.2 module-type detect inputs.
- **Remaining tables decoded (Session 4):**
  - **`$A11` = GEVENT→GPE/SCI map** (`tools/decode_cpm_gevent.py` → `analysis/board_gevent_table.txt`). Entries are `{u16 event; u16 setting}`.
    - Setting bits (from `AmdCpmInitDxe` `FUN_000055e8`; register names match coreboot `soc/amd/*/smi.h`, SMI base = ACPIMMIO+0x200):

| Bits | Meaning | Register |
|---|---|---|
| 0 | valid | |
| 1 | trigger polarity; `0x400` = opposite of current pin level | `SCI_TRIG` 0x208 |
| 2 | level/edge | `SCI_LEVEL` 0x20C |
| 3 | SCI enable | `SCI_EN` 0x214 |
| 4 | ? | 0x220 |
| 9:5 | GPE number | `SCI_MAP0` 0x240+event |
| 11 | SMI trigger | `SMITRIG0` 0x298 |
| 15:12 | SMI control | `CONTROL0` 0x2A0 |

    - Board (both copies): **GEVENT8→GPE8, GEVENT10→GPE10 (SCI on), GEVENT13→GPE13**. All edge, low/falling.
    - DSDT check: `_L08` notifies every GPP root port (**PCIe WAKE#**). `_L19` = CPU xHCI + chipset xHCI `PTXH` + power button. `_PRW`: GPP*→0x08, xHCI→0x19, PS2K/PS2M→0x1D.
    - Live check (`/sys/firmware/acpi/interrupts`): gpe08 and gpe0A enabled, gpe0D pending with no handler, gpe19 disabled (2 events).
    - **RESOLVED (live acpidump):** GPE 0x0A is handled by a **runtime-generated AMD CPM SSDT** (OEM id `MYRTLE` — the CPM board name from `AmdCpmOemInitPeim`), absent from the static flash image because the CPM/AGESA DXE drivers emit it at boot. Its `_L0A` is an aggregate GPIO/GEVENT SCI dispatcher (calls `_GPE.SP00/SP01/…` hooks via a CPM NVS region at 0xBCE69018). This matches the static `$A11` GEVENT10→GPE10 SCI_EN=1 mapping. Other live-only AMD SSDTs: `AmdTable`, `FCHZP`, `AMD AOD` (overclocking). Saved: `analysis/gpe0a_resolved.txt`, `analysis/live_acpi/`.
  - **`$A20` = legacy (Family 15h / Bristol Ridge APU) PCIe+DDI descriptors.** 0x28-byte ports, 0x14-byte DDIs at +0x154.
    - Ports: x8 lanes 8–15 → 00:03.1, x4 lanes 0–3 → 00:02.4.
    - DDIs: lanes 16–19 **HDMI** (aux/hpd 0), lanes 20–23 **single-link DVI** (aux/hpd 1). This matches the board's HDMI + DVI-D rear outputs.
    - Patched by `$A21` (7-byte overrides).
    - `$A22`/`$A25` (PCIe hotplug / card-detect via GPIO) are **absent**, so the board has no PCIe hotplug.
  - **`$A01` = board-ID → platform-ID map** (CPM `GetPlatformId`, `AmdCpmInitPeim` `FUN_09e140f1`).
    - Entries are 7 bytes: `{u8 cpu_class; u16 mask; u16 value; u16 platform_id}`.
    - Raw-ID sources: PCD 700 (default **0xFFFF** = none), then `$A00` (GPIO straps), `$A05` (I²C bits), `$A08` (EC cmd 0x80).
    - On this board `$A00`/`$A08` are absent and `$A05` is empty, so **there is a single board variant**. The map is an identity map of a 3-bit ID per CPU class (9 → 0–7, 10 → 8–15).
    - The result goes to CPM `+0x31` and PCD 0x111.
  - `$A80`–`$A83` (consumers: `AmdCpmDisplayFeature*`, `GnbDxe`) = APU display/switchable-graphics data. Irrelevant for the 2700X (no iGPU); not decoded.
- **PEI PCD database reader:** `tools/pei_pcd.py` (EDK2 v7; 860 tokens; `analysis/modules/PeiPcdDb.bin`). Two independent checks:
  - the USB-port-enable defaults are all 1
  - token 700's U16 type matches the `Get16` accessor the code uses

## 4c. Promontory (B450) register access, from `FchPromontoryCbsPei`
- Chipset generation is detected from the xHCI ID at PT-bus:00.0:
  - `1022:43b9..43bc` = 300-series
  - `1022:43d0..43d8` = 400-series (**B450 xHCI = 43d5**)
- Access paths:
  1. **PT bus 00.1 config index/data** at `0xE0`/`0xE4`. Registers seen:
     - `0x800`: control/unlock (bit 7)
     - `0x804`/`0x806`: device-ID override
     - `0x815`: function select
     - `0xD00`: 32-bit register
  2. 300-series only: xHCI config `0xE8` (u16 index) / `0xEA` (u8 data).
  3. 400-series: an **MMIO mailbox at xHCI BAR+0x3000**:
     - index low/high byte at +0x3000/+0x3001
     - write data at +0x3004, read data at +0x3008
     - busy flag = bit 7 of +0x3009
- **SATA mode is set by rewriting the SATA device ID** (`FUN_09caabef` / `FUN_09caad06`): AHCI writes `0x43c8` on the 400-series (`0x43b5..b8` on the 300-series), RAID-like mode writes `0x43bd`.
- **USB port disable mask**: 8 bits from setup options go to chipset reg `0x4C0` (300-series) or `0x4C1` (400-series), with an enable bit 2 in reg `0x10151`.
- Before PCI enumeration, MMIO for the chipset comes from the Data Fabric (`FabricAllocateMmio v3`).
- The OEM board config is derived from AMD's **"Myrtle"** reference board (string in AmdCpmOemInitPeim).

## 4d. Promontory GPIO (`FchPromontoryGpioPei`), in progress when paused
- Installs a PPI with signature `'PT'` (0x5450) and 3 callbacks: init `FUN_09ca9efa`, set `FUN_09ca956b`, get `FUN_09ca9993`.
- Chipset GPIO regs sit behind a temporary MMIO window at **0xFEC30000**: `+0` enable mask, `+4`, `+8` output value. The pin→bit map is at `DAT_09caa6fc`.
- To reach them, the set/get callbacks temporarily program the bus numbers (cfg 0x18/0x19/0x1A) and command register (0x04 = 6/7) of the Promontory bridges. That only works when the upstream ID is `1022:43b0/43b1/43b2/43b3/43c6` (43c6 = 400-series bridge). Afterwards they restore everything.
- `FUN_09ca93e5`/`FUN_09ca94db` map root port dev/fn → SMN `0x13E3_1004+0x400n` (Matisse) / `0x13B3_1004+…` (Zen/Zen+). These are probably the IOHC bridge control registers. Unverified.
- `tools/ExportDecomp.java` now also turns pointer-only code addresses (PPI/protocol callbacks) into functions. All modules were re-exported with it.
- **Decoded (Session 3):** 8 GPIOs. `FEC30000+0` = output enable, `+4` = input level, `+8` = output value.
  - The BAR lives in the Promontory **fn2** (bridge, 1022:43c6) at cfg `0x40/0x44`, enable bit0 at `0x48`.
  - Root-port table: index 7 = 00:01.3.
- **CPM pin encoding** (`AmdCpmInitPeim` `FUN_09e17ead`): `(pin>>8)&7` selects the controller:
  - 0/1: FCH ACPI-MMIO GPIO. Bits 11–15 ≠ 0 mean a remote socket/die.
  - 2: EC GPIO via ports 0x62/0x66 (cmd 0x80/0x81).
  - **3: Promontory GPIO.** The CPM core re-implements it using temp bus 0x1F + fn2 BAR.
  - 4/5: FCH GPIO via SMN `0x02D02500`.
  - 6: PCA953x-style I²C expander at 0x20+((pin>>4)&7).

## 4o. Secure-update / integrity posture (Session 5)
- **No separate DXE-hash/BootGuard verifier** module in the image → the DXE firmware volume is not
  independently x86-hash-checked; only the PSP's PEI RTM measurement (BHD type 0x62 @0xe42000) gates boot.
  Favorable for a LinuxBoot DXE-payload swap (the DXE FV @0x94f000 is outside the measured region).
- **Signed capsule update + RPMC anti-rollback** present: `SecSMIFlash`, `CapsuleRuntimeDxe/Pei/Smi/X64`,
  `RpmcDxe`, `RpmcSmm`. So a modified image can NOT be deployed via the normal updater — an external SPI
  programmer is required. See `OPEN_FIRMWARE_OPTIONS.md`.
- `Ite8790ECSmi` DXE module → another confirmation of the IT8792E EC; full CSM stack present (legacy boot).

## 4n. USB ports & thermal (Session 5)
- **USB port map** (`tools/decode_usb_ports.py` → `analysis/usb_port_map.txt`): 30 `_UPC`/`_PLD` port objects in the DSDT. Connector types are reliable (Type-C USB3 + USB3 Std-A reported); AMI `_PLD` panel positions are templated boilerplate and should not be trusted for physical layout. Objects count USB2+USB3 halves separately, so physical-connector count is lower. Promontory USB enable masks (4×USB3 + 6×USB2, §4e) remain the authoritative port count.
- **No ACPI thermal zones:** no `ThermalZone`/`_TZ`/`PNP0C0B` fan device in any DSDT (only an incidental ref in the Gigabyte `GSWApp` SSDT). Cooling is **autonomous in the Super I/O hardware** (IT8686E/IT8792E SmartGuardian, see `fan_hwm_init.txt`) + BIOS Setup, not OS-visible ACPI. A port replicates the SIO fan setup, not ACPI `_TZ`.

## 4m. Complete 16 MiB flash map (Session 5): `analysis/flash_layout_full.txt`
Every region located and sized: EFS@0x20000, NVRAM@0x37000, PSP2/BHD2 combos@0xe7000/0xe7800, APCBs (Zen/Zen+ @0x241000/0x3b0000, Matisse/Vermeer primary+backup), Promontory FW@0x90f000/0x92f000, DXE FV@0x94f000, PEI FV@0xe40000. A draft coreboot `board.fmd` is in `coreboot_reference/mainboard_draft/`.

## 4l. Firmware-volume map / RTM resolution (Session 5): `analysis/firmware_volume_map.txt`
- Scanned all `_FVH` EFI firmware volumes (all GUID `78e58c8c…`). Confirms session-2's map: DXE FV @ 0x94f000 (0x4f0000), PEI FV @ 0xe40000 (0x1c0000), NVRAM @ 0x37000.
- **Resolved apparent discrepancy:** the BHD type-0x62 "BIOS_RTM_VOLUME" pointer (0xe42000, size ~0x3c0000) is **not** a separate FV — it points just past the PEI FV header at the measured (decompressed) RTM body. No conflict with the FV map.

## 4k. CPU microcode inventory (Session 5): `analysis/amdfw_microcode.txt`
- `tools/amdfw_microcode.py` walks the BIOS dirs and reads each type-0x66 microcode patch header (date + patch_id). patch_id is the authoritative CPU family ID.
- **19 patches across 7 CPU families**: Summit/Pinnacle (0x0800, ×5), Raven/Picasso (0x0810, ×4), Raven2/Dali (0x0820, ×1), Renoir (0x0860, ×2), Matisse (0x0870, ×2), Vermeer (0x0a20, ×3), Cezanne (0x0a50, ×1).
- Newest patch date 12/05/2024 → confirms F67c is a late-2024/2025 BIOS. This PC's **2700X uses the 0x0800 group** (patch 0x08001139, 08/22/2024 — the post-Inception/Zenbleed-era revision).
- The 7 microcode families vs 6 PSP combo dirs: Summit + Pinnacle share patch group 0x0800 and one PSP directory.
- **Caveat:** this also corrected the SOC-id→name guesses in `amdfw_combo.py` (ids 0xbc0c* carry both Matisse/Vermeer and Cezanne microcode); those labels are now marked approximate, with patch_id as ground truth.

## 4j. Full PSP/BIOS firmware-directory inventory (Session 5): `analysis/amdfw_psp_combo.txt`
- Built coreboot's `amdfwtool`/`amdfwread` from the clone (`coreboot/util/amdfwtool/`). `amdfwread -d` confirms the EFS fields I decoded by hand (PSP dir 0xe7000, BIOS dirs, Promontory FW ptrs), but it **cannot** walk the combo cookies (`PSP2`/`BHD2` vs the `PSP$`/`BHD$` it expects).
- Wrote `tools/amdfw_combo.py` to walk the combo dirs. Results:
  - **PSP2 combo @ 0xe7000: 6 SoC generations** — Summit Ridge, Pinnacle Ridge, Raven/Picasso, Renoir/Cezanne, Matisse, Vermeer. Each has a `$PSP` dir (+ `$PL2` level-2) with the signed blobs: AMD public key, PSP bootloader, trusted OS, SMU FW, ABL/AGESA bootloader, SEC gasket, soft-fuse chain, etc.
  - **BHD2 combo @ 0xe7800: 2 generations** (Matisse, Vermeer) with `$BHD`→`$BL2` holding: APCB (0x60) + APCB_BACKUP (0x68), APOB, **BIOS_RTM_VOLUME (the UEFI volume, type 0x62) @ 0xe42000 size ~0x3c0000**, PMU instruction/data (DRAM PHY firmware), microcode.
- **Correction to §4i:** the APCB regions I inventoried at 0x771000 / 0x8f1000 are the **APCB_BACKUP** copies (type 0x68). The *primary* APCBs are at 0x775000 (Matisse) / 0x8f5000 (Vermeer). The Zen/Zen+ APCBs (0x241000, 0x3b0000) are reached via the per-gen BIOS dirs, not the BHD2 combo (which only lists Matisse/Vermeer).
- **Port takeaway:** this one image carries 6 complete signed firmware stacks.
- **Integrity check:** `tools/amdfw_combo.py` now verifies each directory's Fletcher-32 checksum (field at +4 over count..end). All 14 directories (PSP2/BHD2 combos + every per-generation `$PSP`/`$PL2`/`$BHD`/`$BL2`) report **cksum=OK**, confirming the parse reads intact structures.
- **Soft-fuse (type 0x0c):** present per generation, but in this image it is a signed blob (`$PS1` cookie), not a simple 64-bit mask, so the "allow unsigned / debug" bit is not directly readable here. The *actual* enforced state lives in on-die eFuses, which are **not in the flash image at all** — consistent with §3's PSP-signature blocker (the image cannot tell us the board is unlocked, and retail AORUS boards ship fused for production keys). A coreboot AM4 port must reuse the matching generation's PSP bootloader + ABL + SMU + PMU + APCB **unmodified** (PSP verifies them); only the x86 BIOS volume (type 0x62) is replaceable. This is the concrete blob list behind the "PSP-validated boot" blocker.

## 4i. APCB (AGESA memory/board config) inventory (Session 5)
Tools: `tools/apcb_inventory.py` (group/entry structure), `tools/apcb_tokens.py` (token decode). Output: `analysis/apcb_inventory.txt`, `analysis/apcb_tokens_all.txt`.
- APCB v3 layout confirmed: `'APCB'` header (0x20B) → GROUP headers (`'xxxG'` magic + u16 id + u32 size) → ENTRY headers (u16 gid, u16 tid, u32 size).
- Regions and versions:

| Flash | ver | Groups | For |
|---|---|---|---|
| 0x241000 | 0x20 | CCX,DF,MEM,FCH,CBS | Summit/Pinnacle (Zen/Zen+) |
| 0x3b0000 | 0x20 | DF,MEM,GNB,FCH,CBS | Zen/Zen+ (2nd) |
| 0x5e0000 | 0x30 | MEM,TOKEN | Matisse/Vermeer base |
| 0x771000 | 0x30 | MEM,GNB,TOKEN | Matisse |
| 0x8f1000 | 0x30 | MEM,GNB,TOKEN | Vermeer |
- Group magics: `CCXG DFG MEMG GNBG FCHG CBSG TOKN`. MEM dominates (SPD/DRAM training; largest MEM entry ~0x884, plus a 0x10080 blob in the v0x20 copy = PMU training data).
- **TOKEN group** (what coreboot's apcb tooling edits): 4 entry types — bool/byte/word/dword. ~53/80/19/16 tokens each.
  - Token IDs are **AMD-internal UIDs with no public name map** (coreboot ships APCB as opaque blobs and only injects SPD). Values recorded raw in `apcb_tokens_all.txt`.
  - Notable dwords (0x5e0000, meaning unconfirmed): `0x34970a3c=0xBB8(3000)`, `0xcc83f65f=0x640`, `0x3d9b7d7b=0x08000000`, `0xd403ea0e=0x10000000`.
  - The Matisse (0x771000) and Vermeer (0x8f1000) token sets **differ** (17 token lines) — consistent with `SbSocMatissePei` handling both families with per-family config.
- **For a port:** these blobs are consumed by AMD's closed PSP/ABL/AGESA, which a coreboot AM4 port would have to reuse wholesale; the APCB is editable only via AMD's token mechanism, not re-authorable. Reference only.

## 4h. PCI interrupt routing / IO-APIC (Session 5): `analysis/pci_irq_routing.txt`
- Decoder: `tools/decode_prt.py` (parses `_PRT` packages from an iasl `.dsl`).
- Root bus `_SB.PCI0._PRT`: `If (PICM) Return(AR00) else Return(PD00)`. AR* = APIC packages, PD*/PR* = 8259-PIC packages.
- Root-bus APIC routing (`AR00`), GSIs on the FCH IO-APIC:
  - GPP root ports at 00:01.x → GSI 40–43, 00:03.x → 36–39, 00:07/08 → 44/32.
  - FCH internal 00:14.x (SMBus/LPC/…) → GSI 16/17/18.
- Each GPP bridge has its own downstream package (AR01→GPP0 … AR12→GP18), mapping the slot's INTA/B/C to GSIs 24–55.
- **Caveat:** this is the legacy INTx fallback. Live devices use MSI/MSI-X, so the `/sys/.../irq` values (26,27,…) are allocated vectors, not these GSIs — no direct live match expected.
- For a coreboot port this is the data behind `mp_irq`/`intr_data` tables and the FCH IO-APIC init (GSI base 0x18 for the 8 "PCI IRQ" lines, matching FINDINGS §4d GEVENT block).
- **Live refinement (§LIVE_ACPI):** there are **two** IO-APICs — FCH @0xFEC00000 (GSI base 0) and GNB @0xFEC01000 (GSI base 24). The GSIs ≥24 in `AR00`/`AR0x` are inputs on the **GNB** IO-APIC. See `analysis/LIVE_ACPI.md`.

## 4d2. Promontory PHY tuning defaults (Session 4): see `analysis/promontory_phy_defaults.txt`
- Source chain:
  1. `FchTaishanPei` builds the FCH data HOB from a static table (0x296 B) plus ~166 PCD overrides.
  2. It publishes it as the `'$FCH'` PPI.
  3. Promontory cfg = table + 0x7B.
- Full write-up in `PROMONTORY_FW_LOADER.md` §6 (`tools/decode_pt_phy_defaults.py`).

## 4e. Promontory firmware loader: see **`analysis/PROMONTORY_FW_LOADER.md`**
- `FchPromontoryXhciPei` uploads a 0x1C000-byte firmware into the chipset during PEI, via the xHCI MMIO mailbox. The full protocol is in that file.
- **B450 uses `EFS+0x34` → flash `0x92F000`.** Header is `'_PT_', size 0x1C00C, byte-sum`. Both images' checksums verified (`tools/promontory_fw.py`). Carved to `analysis/promontory_fw/`.
- Before the upload, USB ports are enabled/disabled through key-protected mailbox regs (key `0x12345678`). B450 = 4× USB3 + 6× USB2, which matches AMD's spec.
- **Consequence for coreboot:** a port must replicate this loader, using the AMD-signed `_PT_` blob from the stock image. Otherwise the chipset's USB/SATA/PCIe stay dead.

## 4f. Gigabyte OEM layer
- Per-CPU modules: `GbtCrb{Pei,Dxe,Smm,Cbs,Aod}{ZP,RV,SSP,VM,RN,CZN}`.
- `SbSoc*` mapping **confirmed** via CPUID constants in the PEIMs:
  - `SbSocSummitPei` = 0x800F00 (Zen/Zen+, this PC's 2700X)
  - `SbSocRavenPei` = RV/RV2/Picasso
  - `SbSocMatissePei` = Matisse **and** Vermeer
  - `SbSocRenoirPei` = Renoir + Cezanne
- FCH codenames:
  - Taishan/Sandstone have no CPUID literals.
  - **Both** `FchHuashanSmmInit` and `FchShastaSmmInit` reference Matisse/Vermeer/Starship IDs, so Huashan vs. Shasta is still unresolved.
- `GbtCrbPei`:
  - CPU-family-specific IT8686 HWM setup (regs 0x67/0xB2/0xB3)
  - per-slot PCIe **link speed** (`$A26` record byte +0x0D bits 3–5) and **ASPM** (byte +0x0E bits 4–5) from Setup
  - OC-fail recovery: CMOS 0x94/0x95, reset via `CF9=0x0E`
  - first-boot flag: CMOS 0x96=0xAA
- `PTUpdatePCD`: copies the Setup and `XhciDID` variables into Promontory PCDs (value 2 = Auto/skip).
- **IT8686E fan/HWM init decoded (Session 5):** `GbtCrbPei FUN_09dedbe9` → `analysis/fan_hwm_init.txt`. HWM index/data at 0xA45/0xA46. Per CPU family (0x15 Zen/Zen+, 0x17 Raven, 0x19 Matisse/Vermeer): reg 0x67 bit7, and for Zen/Zen+ reg 0xB2=0x92 / 0xB3=0x8F (SmartGuardian fan control) + a CR2C bit3 pin-mux tweak. 2nd SIO (IT8792E) fans are separate.
- **SMBIOS/DMI strings are runtime-generated**, not hardcoded in `GbtCrbSmbios` (its module has no model strings) — consistent with the single-variant `$A01` board-ID finding. Live DMI is authoritative: `product_name = "B450 AORUS PRO"`, `board_name = "B450 AORUS PRO-CF"`, vendor Gigabyte.

## 4g. Live-system cross-check (2026-11-11, read-only: `/sys`, `lspci`)
- This PC **is** the target board: `B450 AORUS PRO-CF`, running BIOS **F66i** (the analysed file is F67c). CPU **Ryzen 7 2700X** (Pinnacle Ridge, fam 17h model 8). So the **Zen/Zen+ code paths** are active: OEM-PEIM copy 1, `GbtCrb*ZP`, Taishan FCH.
- Matches with the RE results:

| Live | ID | RE prediction |
|---|---|---|
| 00:01.3 → bus 01 | GPP root port | chipset uplink (DXIO rec 2, lanes 7→4 on Zen+) ✓ |
| 01:00.0 | 1022:**43d5** | 400-series xHCI → firmware from EFS+0x34 ✓ |
| 01:00.1 | 1022:**43c8** | AHCI device ID written by `FUN_09caabef` ✓ |
| 01:00.2 | 1022:**43c6** | fn2 bridge holding the GPIO BAR ✓ |
| 02:00.0 → 03:00.0 | 8086:1539 I211 | `IntelI211UndiBin` ✓ |
| 02:08.0 → 06:00.0 | NVMe (SN5100) | chipset-attached M.2 (M2B) |
| 00:03.1 → 07:00.0 | RX 580 | x16 slot, DXIO rec 0 ✓ |
| 00:14.3 | 1022:790e LPC | SIO decode regs `0xF00A3044..` ✓ |
| (no 00:01.1) | — | CPU M.2 empty → runtime M.2 record not added |

- **CONFIRMED (live `sensors`, 2026-11-11):** the 2nd Super I/O is an **IT8792E at ISA base 0x0A60** (`it8792-isa-0a60`: 3 fans, 3 temps, 3 PWM, Vbat/3VSB) — exactly the chip-2 @ 0x4E → LDN4 HWM @ 0xA60 decode from §3. The primary IT8686E's HWM (0xA40) stays owned by the firmware SMM, so only the IT8792E binds to the Linux driver.

## 5. What this means for a coreboot port
Knowledge now in hand: the SIO configuration, LPC decodes, IO map and PCIe/Promontory topology.
The hard blockers from session 1 are unchanged:
- Promontory init
- PSP-validated boot
- No desktop AM4 SoC code in coreboot (AGESA/FSP for Zen desktop is not public)

## 5b. Upstream coreboot status (checked in tree `bd5c2139`, 2026-11-10)
- `src/soc/amd`: cezanne, common, genoa_poc, glinda, mendocino, phoenix, picasso, stoneyridge, strix_halo, turin_poc.
  - **No AM4 desktop SoC** (Summit/Pinnacle/Matisse/Vermeer), and no Promontory support (grep for promontory/43d5/B450 finds nothing in `src`).
  - AMD **openSIL** POCs exist only for genoa/phoenix/turin, i.e. Zen 4+.
- `src/superio/ite`: it8528e … it8689e, it8728f, it8772f, it8783ef, it8784e, it8786e. **No it8686e and no it8792e.** it8689e is the closest relative (also handled by Gigabyte's init module).
- `src/mainboard/gigabyte`: only Intel boards plus `mz33-ar1` (an AMD server board). No AM4 boards.

- **`analysis/coreboot_reference/superio_devicetree.cb`**: the decoded SIO programming as a coreboot devicetree. It uses `superio/ite/it8689e` as a stand-in, since it has the same LDN layout as the IT8686 path in Gigabyte's code. Chip-2, HWM and LPC-decode sequences are in the comments. Reference only; there is no AM4 mainboard to build it in.

## 5c. QEMU sandbox (working)
- `coreboot/` = shallow clone. `.config`: `EMULATION_QEMU_X86_Q35 + ANY_TOOLCHAIN + PAYLOAD_SEABIOS`. **It builds with the system GCC 16; no crossgcc needed.**
- `tools/run_coreboot_qemu.sh` (interactive) or `tools/run_coreboot_qemu.sh log 15` (headless).
- Verified boot: bootblock → romstage → postcar → ramstage → SeaBIOS 1.17.0 → "Press ESC for boot menu". Log in `analysis/coreboot_qemu_serial.log`.

## Next steps (updated end of Session 4)
Done: CPM tables (all but APU display), Promontory loader / CBS / GPIO / PHY defaults, coreboot QEMU sandbox.

Remaining, roughly by value:
1. ~~Needs the user (sudo)~~ — **DONE 2026-11-11**: 2nd SIO confirmed **IT8792E @ 0xA60**; GPE 0x0A confirmed = AMD CPM `MYRTLE` runtime SSDT. (`analysis/gpe0a_resolved.txt`, `analysis/live_acpi/`.)
2. ~~Raw-disassembly check of the upload interleave~~: **done in Session 4**, it matches the spec.
3. 300-series upload path `FUN_09ca7757`, for completeness. (SATA `FUN_09cac2e8`: **done in Session 4**, see `PROMONTORY_FW_LOADER.md` §6.)
4. Zen+ memory/APCB side: the PSP/APCB blobs hold DRAM config. Any coreboot port would need AMD's closed PSP/ABL blobs anyway, so this is reference only.
5. `$A80`–`$A83` APU display tables, only if an APU is used in this board.
