# Promontory (B450) Firmware Upload: Protocol Notes

Source: `FchPromontoryXhciPei`, decompiled in `analysis/decomp/FchPromontoryXhciPei_1.efi.c`:
- main flow: `FUN_09ca635b`
- 400-series upload: `FUN_09ca79cf`
- unlock: `FUN_09ca5a8c`
- mailbox helpers: `FUN_09ca767c` / `FUN_09ca76f9` / `FUN_09ca7614`
- 300-series upload: `FUN_09ca7757`, not yet read

Everything here comes from static analysis of the user's own image. Nothing has been tested on hardware.
Parts marked *(unverified)* are inferences.

## Why this matters
The B450 chipset's USB/SATA/PCIe functions only work after the x86 BIOS pushes this firmware into it during PEI.
Any replacement firmware, coreboot included, has to do the same, using the AMD-signed `_PT_` blob from the stock image.
This is in addition to the PSP/AGESA blockers.

## 1. Locating the image
- Scan for the AMD **EFS** (`0x55AA55AA`) at `0xFFFA0000, 0xFFF20000, 0xFFE20000, 0xFFC20000, 0xFF820000, 0xFF020000`. On this board it's at flash `0x20000`.
- Use `EFS+0x30` if the chipset xHCI is `1022:43b9..43bc` (300-series).
- Use **`EFS+0x34` if it's `1022:43d0..43d8` (400-series; B450 = 43d5)**.
- amdfwtool calls `+0x34` `lp_promontory_fw_ptr`, but on this board it holds the 400-series image.
- Image format, verified with `tools/promontory_fw.py` (both checksums match):
  ```
  +0x00 char[4] '_PT_'
  +0x04 u32     total size incl. header (0x1C00C here)
  +0x08 u32     sum of bytes [0x0C, size)  (32-bit wrap)
  +0x0C ...     payload, 0x1C000 bytes
  +0x8C u8[6]   copied to the config struct as a version. Looks like BCD YY MM DD:
                300-series 19-10-30, 400-series 21-04-14 (unverified)
  ```
- The loader copies the image to RAM and re-verifies the checksum, up to 10 tries.
- Carved copies: `analysis/promontory_fw/promontory_fw_efs{30,34}.bin`.

## 2. Reaching the chip before PCI enumeration
1. *(Optional)* Poll SMN `0x11140294 | (n<<12)` (via D0F0 `0xB8/0xBC`) for `(val & 0xFF) == 0x10`. Up to 200 × ~2 ms. Probably the root-port link-training state = L0 *(unverified)*.
2. For each candidate root port (21-entry table: 00:01.1–7, 00:02.1–5, 00:03.1–7, 00:04.1; **B450 on Zen 2/3 = 00:01.3**):
   - Set secondary = subordinate = temporary bus.
   - Read the xHCI at `bus:00.x` (fn from `DAT_09ca912c`).
   - Also handle a PLX **PEX8714/PEX8718** switch (`10b5:8714/8718`) in front of the chipset.
3. Allocate 1 MiB of non-PCI MMIO below 4 GiB through the DF (`FabricAllocateMmio v3`). On family 15h, use the fixed window `0xF1000000` via D18F1 0x80/0x84.
4. Program:
   - xHCI BAR0 (cfg `0x10`)
   - bridge memory base/limit (cfg `0x20/0x22`) on the root port and any switch ports
   - command = 6 everywhere
5. Disable ASPM on the path: clear bits 1:0 of root-port cfg `0x68`, of the xHCI fn and fn1/fn2 cfg `0x90`, and of the switch cfg `0x78`.
6. **If xHCI cfg `0xF0` == `0x55AA55AA`, the firmware is already running. Skip the upload.**

## 3. Mailbox (MMIO, xHCI BAR0)
| Offset | Use |
|---|---|
| `+0x3000` | index bits 7:0 |
| `+0x3001` | index bits 15:8 |
| `+0x3004` | data byte (write) |
| `+0x3008` | data byte (read). The status read in `FUN_09ca76f9` reads `+0x3004` after selecting index `0x5040` |
| `+0x3009` | bit 7 = busy; poll until clear after every access |
| `+0x3010` | firmware download data port (dword) |

Only the low 16 bits of an index reach the hardware. AMD's code writes e.g. `0x1A520`, which becomes index `0xA520`.

## 4. Upload sequence (400-series, `FUN_09ca79cf` + `FUN_09ca5a8c`)
```
mbox[0xA520..0xA523] = 78 56 34 12        ; unlock key 0x12345678
mbox[0xC51F]         = port mask (8 bits from config +0x127..0x12E) (unverified meaning)
loop {
  BAR0 &= ~0xF; cmd = 6
  mbox[0x5040] = 2 ; mbox[0x5042] = 1
  wait while (BAR+0x20) & 2               ; xHCI USBCMD.HCRST?
  mbox[0x500E] = 1                        ; enter download mode
  cfg[0xEF] = 0x80 ; cfg16[0xE2] = 0 ; wait cfg16[0xE2] == 0
  for k = 0 .. 0x7FFE step 2:             ; phase 1 (payload offsets 0x0000..0xFFFF)
      BAR[0x3010] = pay[k] | pay[k+1]<<8 | pay[0x8000+k]<<16 | pay[0x8001+k]<<24
      wait cfg16[0xE2] != k               ; HW advances the counter
  cfg16[0xE2] = 0x8000 ; wait cfg16[0xE2] == 0x8000
  for i = 0x4000 .. 0x7FFF:               ; phase 2 (payload offsets 0x10000..0x1BFFF)
      j = 2*(i-0x4000)
      lo = pay[0x10000+j] | pay[0x10001+j]<<8
      hi = (i < 0x6000) ? pay[0x18000+j] | pay[0x18001+j]<<8 : 0
      BAR[0x3010] = lo | hi<<16 ; wait cfg16[0xE2] advances
  repeat { mbox[0x5040] = 3 } until mbox_read(0x5040) == 3     ; start firmware
  cfg[0xEF] = 0 ; mbox[0x500E] = 0
  up to 255 × ~65 ms: wait while (BAR+0x20) & 2
} while BAR0 == 0 || (BAR+0x20) & 2
```
`pay` = image + 0x0C. Both phases' byte indexing was re-derived from the decompiler's pointer arithmetic: `this+0x8001` with `[-0x8001]/[-0x8000]/[-1]/[0]` for phase 1, and `this+0x10001` / `+0x7fff` for phase 2. **Verified against the raw disassembly (Session 4, rizin `0x09ca7ad1..0x09ca7ba2`):** the phase-1 dword is built `[p]<<24|[p-1]<<16|[p-0x8000]<<8|[p-0x8001]`; phase 2 has `cmp di,0x6000; jae` (high half only while the counter is below 0x6000) and the loop runs `di = 0x4000..0x7FFF`; after each dword the code spins while cfg16[0xE2] still equals the expected count. The `this` argument = `local_bc+3` (u32*) = image + 0x0C.

## 5. Afterwards
- Restore ASPM bits, clear BAR0, bridge windows, command registers and temporary bus numbers.
- Zen: notify through the PPI `DAT_09ca8a90` (`+8` callback).
- Then `FchPromontoryCbsPei` applies setup options:
  - SATA device-ID personality: `0x43c8` AHCI / `0x43bd`
  - USB port masks: `0x4C1`, `0x0151` bit 2
  - and so on (see FINDINGS §4c)

## 4b. USB port enables before the upload (`FUN_09ca5b62`)
- Each port flag in the config struct (1 = enabled) sets a bit in a 24-bit mask.
- The mask is written to `mbox[0xB520..0xB522]` after the key `78 56 34 12` goes to `0xA520..0xA523`.
- Variants by xHCI ID:

| xHCI ID | cfg bytes | Mask layout |
|---|---|---|
| 43b9/43ba/43d0/43d1/43d2 | `+0x3A..0x47` | 14 ports |
| 43d3 | `+0x48..0x53` | 12 ports |
| **43d5 (B450)**/43d6/43d8 | `+0x54..0x5D` | USB3+companion pairs `0x0202, 0x0404, 0x0808, 0x1010`, then USB2-only bits 17..22 |
| 43bb / 43bc (300-series) | `+0x54..0x5D` / `+0x5E..0x66` | key `CD CD CD CD` → `0xC520..0xC523`; mask → `0xD520/21` or `0xD522/23` |

- The B450 mask = **4 USB 3.x + 6 USB 2.0**, which matches AMD's B450 spec (2× Gen2 + 2× Gen1 + 6× USB2). That is a sanity check on the decode.
- A second key (`78 56 34 12` → `0xA51C..0xA51F`) gates read-modify-write of `0xB51C` (setup bytes `+0x0A/0x0B/0x0C`) and `0xC51C` (depends on CPU family 17h).
- Key/data register pairs differ by 0x1000: `A5xx` holds the key, `B5xx` holds the data.

## 6. Post-load configuration (`FchPromontoryCbsPei`, orchestrator `FUN_09cac72b`)
Order:
1. Same temporary bus/MMIO bring-up as the loader.
2. `FUN_09caaffa`: common USB settings.
   - port-disable mask: `FUN_09caaf29`, reg `0x04C1` + enable bit 2 of `0x0151`
   - 8-entry per-port table: `FUN_09caad74`, offsets `0x50/52/58/5A/30/32/1030/…/1832`
   - regs `0x8514/0x8515/0x006D`
3. **400-series:**
   - `FUN_09cab9ef`: PHY tuning, see below
   - `FUN_09cabdf8`: set bit 1 of `0x0151`
   - 300-series instead: `FUN_09cab474`
4. `FUN_09cac2e8`: **SATA** (decoded Session 4; defaults in `analysis/promontory_sata_defaults.txt`). Everything goes through the PT-fn1 index/data regs.
   - 8 ports. Port n enable (400-series, `FUN_09cabeb4`):
     1. `0xEFE=n`; if `0xE88≠0`, `0xE88&=~2`
     2. unlock: `0x800|=0x80`, `0x888=(cur&F6)|6`
     3. **`0x81C|=1<<n`**
     4. lock: `0x800&=0x7F`, `0x888&=F0`
     5. `0xD06|=1<<n`
   - Disable (`FUN_09cabfe5`) clears those bits and sets `0xE88|=2`. The 300-series uses `FUN_09cac129/205` (0x810→0x81C).
   - Options:
     - `+0x0E` class: 0 = AHCI → DID `0x43c8`, 1 = RAID → DID `0x43bd`
     - `+0x0F/+0x10` → `0xD0A` bits 0/1
     - `+0x11/+0x12/+0x13` → `0xD00` bits 26/13/14
     - `+0x15/+0x16` → port 0/1 `0xF45` = `0x90/0xA0/0xC0` for options 1/2/3
     - `+0x17` → `0xDC8..0xDCF` bit 3
   - Board defaults (PCD): AHCI, all 8 ports enabled, `0xD00` bits 26/13/14 set, the rest 0.
   - **Live check:** `01:00.1` is `1022:43c8` (AHCI) with 8 ATA ports ✓
   - Device-ID personality (`FUN_09caabef`): AHCI `0x43c8` on 400-series, or `0x43bd`.
   - `FUN_09cabe56` clears bit 1 of `0x0151` when SATA reports a flag.
5. On S3 resume (PEI boot mode 0x11) after a fresh firmware load: clear bit 4 of mbox reg `0x5087` (the dword write also sets `+0x3002 = 0x01`; role unknown).

PHY tuning register map (16-bit mailbox index; the high nibble selects the PHY block). The grouping is inferred from loop counts vs. the B450 port count:

| Regs | Count | Likely meaning |
|---|---|---|
| `0x9450,0xA450` / `0x9460,0xA460` (+`…59`/`…69`) | 2 blocks × 2 ports | 4× USB3 PHY: nibble fields (swing / de-emphasis?) |
| `0xB450,0xB490,0xC450,0xC490,0xD450,0xD490` (+`…59`/`…99`) | 6 | 6× USB2 PHY |
| `0xA598,0xB598,0xC598,0xD598` (+1, +2) | 4 | per-block common |
| `0x2EFE` = lane select n, then `0x2F22..0x2F25` | 8 lanes | PCIe/SATA GPP lane PHY (8 lanes = PT20..PT27) |

**Where the defaults come from (Session 4):**
- The config struct is created by **`FchTaishanPei`** (the Zen+ FCH; other families have their own `Fch*Pei`):
  1. It creates a 0x2AE-byte GUID HOB.
  2. It copies a **static default table** (`DAT_09cbf790`, 0x296 B) into it.
  3. It overrides ~166 fields from **PEI PCDs** (`FUN_09cbc03e`).
  4. It publishes PPI `3fb7a27a…` (`'$FCH'`). Field `+8` of that PPI = table + **0x7B**, so Promontory cfg offset X = FCH table offset 0x7B+X.
  - Check: the runtime-only fields hold sentinels at exactly those offsets (root-port idx `0xFF`, xHCI DID `0xFFFFFFFF`).
- Data flow: **Setup → `PTUpdatePCD` (PcdSet) → `FchTaishanPei` (PcdGet) → struct → `PTInterfacePei` (Setup overrides, 2 = Auto) → `FchPromontoryCbsPei`**. The PCD token numbers match on both sides.
- Sources by field range:

| Cfg range | Source |
|---|---|
| `+0x95…0xBA` (USB3/USB2 PHY) | static table |
| `+0xD3…0x11A` (8 lanes) | static table |
| `+0xBB…0xD2` (per-block `0x?598`) | PCD tokens `0x233,0x182,…,0x243` |

- Read with **`tools/pei_pcd.py`**, an EDK2 PEI PCD DB v7 reader: 860 local tokens. The `PcdPeim` raw section is saved as `analysis/modules/PeiPcdDb.bin`.
- Parser check: all 10 B450 USB-port-enable PCDs default to 1.
- **Decoded register values: `analysis/promontory_phy_defaults.txt`** (`tools/decode_pt_phy_defaults.py`). AMD reference defaults are uniform:
  - USB3 blocks `0x9/0xA`: `x450[7:4]=F, x460[7:4]=F, x459=0x14, x469=0x13`, then `x450=(cur&F0)|0x04`, `x460=(cur&F0)|0x09`
  - USB2 ports: `x450/x490[7:4]=F`, `x459=0x14` (even ports) / `0x1C` (odd ports)
  - common `0xA598..0xD598`: `=(cur&E0)|0x1D`, `+1 = (cur&03)|0xD4`, `+2 = (cur&3E)|0x41`
  - all 8 lanes: `2F22=0x00, 2F23=0x24, 2F24=0x38, 2F25=(cur&F8)|0x06`
- Caveat: the same register (e.g. `0x9450`) is written twice, first the high nibble, then `(cur&F0)|…`. The decode keeps that order. Meanings (swing, de-emphasis, …) are unknown.
- Correction: cfg `+0x11F…0x126` are per-port **enable** flags (PCD default 1). The 400-series code writes `~mask` to reg `0x04C1`, a *disable* register, so the default is 0.

## Open items
- `FUN_09ca7757` (the 300-series path) is not yet read.
- Meaning of mailbox regs `0x5040/0x5042/0x500E/0xC51F` and of cfg `0xE2/0xEF/0xF0` beyond what the code shows.
