# Live ACPI Analysis (from `sudo acpidump`, 2026-11-11)

Source: the running board (B450 AORUS PRO-CF, BIOS **F66i**, Ryzen 7 2700X). Disassembled set saved in
`analysis/live_acpi/`. This captures tables the AGESA/PSP/CPM code **generates at runtime** that are
absent from the static flash image — a coreboot port must reproduce all of them (via `acpigen`/SoC code).

## 1. Table inventory — static (from flash) vs runtime-generated

| Table | OEM ID | Origin | Notes |
|---|---|---|---|
| DSDT | ALASKA / "A M I " | **static** (flash) | the AMI DSDT (matches `DSDT_AMI_*` §1) |
| SSDT CPUSSDT | ALASKA | **static** | 16 `Processor()` objects (see §3) |
| SSDT GSWApp | GBT | **static** | Gigabyte Software App (cf. flash `SSDT_GSWApp_1db7561e`; F66i live = 5509 lines vs F67c flash 5603 — small version delta) |
| SSDT AmdTable ×3 | AMD | **runtime (AGESA)** | GNB/PCIe/system resource SSDTs |
| SSDT MYRTLE ×2 | AMD | **runtime (CPM)** | GPIO/GEVENT; holds the GPE 0x0A handler (§4d) |
| SSDT FCHZP | AMD | **runtime (FCH)** | FCH (Zeppelin) devices; == `SSDT_FCHZP_*` |
| SSDT "AMD AOD" | AMD | **runtime (AGESA)** | AMD Overclocking mailbox (see §4) |
| IVRS | AMD/AmdTable | **runtime (AGESA)** | IOMMU (see §2) — **not in flash** |
| CRAT, CDIT | AMD | **runtime (AGESA)** | CCX/NUMA topology (CRAT 3920 B) — **not in flash** |
| VFCT | — | **runtime** | GPU video BIOS image (60 KB, the RX 580) — **not in flash** |
| APIC, HPET, MCFG, FACP, FACS, FIDT, FPDT, WSMT, TPM2, BGRT | — | runtime (platform) | built by PEI/DXE, see §5 |

So a port's ACPI work is substantial: AGESA/openSIL normally emits IVRS/CRAT/CDIT/AmdTable and the FCH/CPM
SSDTs; coreboot would have to generate equivalents (one more reason the missing SoC code is the real blocker).

## 2. IOMMU (IVRS) — absent from flash, must be generated
- IOMMU MMIO **base 0xFEB80000**, capability offset 0x40, PCI segment 0.
- IVHD device ranges: start 0x0008 … end 0xFFFE (all downstream), alias range from 0xFF00 (src 0x00A4),
  plus special device entries for IOAPIC/HPET (src dev 0x00A0, 0x0001).
- A coreboot port emits this via `acpi_fill_ivrs` in the SoC's northbridge code.

## 3. Processors (CPUSSDT) — the 2700X
- **16 logical processors** `C000..C00F` (8 cores × SMT2), P_BLK I/O base **0x810** (matches DSDT `PMBS=0x800`, +0x10).
- Detailed P-states/C-states/CPPC are provided dynamically (AOD + `_PSS`/`_CPC` under the processor scope),
  not as static packages — consistent with AGESA building them from fused CPU limits.

## 4. AMD Overclocking ("AMD AOD") — live memory/CPU tuning mailbox
- A runtime SSDT exposing a PSP-SMI mailbox (`PSMI`/`PMRG` operation regions) with fields for OC values:
  `BTCL`/`MTCL` (memory CAS latency), `BOCV`/`BOCF` (OC voltage/frequency), `BOCD`, `BFOC`.
- This is the ACPI side of AMD's "AMD Overclocking" / Ryzen Master interface. It talks to the PSP, so it
  only works with the signed AGESA stack — another thing a port cannot reproduce without AMD code.

## 5. Platform fixed addresses (verified on live hardware)
| Resource | Address | Cross-check |
|---|---|---|
| **MCFG / PCIe ECAM** | **0xF0000000** (bus 0–0x7F) | == the `0xF0000000` base throughout the PEI decompiles (§4c/4d) |
| Local APIC | 0xFEE00000 | standard |
| **IO-APIC #1 (FCH, id 0x11)** | 0xFEC00000 | **GSI base 0** (ISA IRQs + FCH internal, GSI 0–23) |
| **IO-APIC #2 (GNB, id 0x12)** | 0xFEC01000 | **GSI base 24** — the `_PRT` GSIs ≥24 (§4h) land here |
| IOMMU | 0xFEB80000 | §2 |
| HPET | 0xFED00000 | == DSDT `HPTB` (§1) |
| FCH ACPI MMIO | 0xFED80000 | == DSDT (§1) |

## 6. Refinement to the IRQ-routing finding (§4h)
The live APIC table shows **two** IO-APICs: FCH @0xFEC00000 **GSI base 0** (covers GSI 0–23: ISA IRQs +
FCH internal 00:14.x at 16/17/18) and GNB @0xFEC01000 **GSI base 24**. So the `_PRT` GSIs ≥24 (§4h, e.g.
GPP ports at 36–44) are inputs on the **GNB** IO-APIC, not the FCH one. A port's `mp_irq`/IO-APIC setup must
declare both controllers with these exact bases.

## 7. Both former open items — now closed
- **2nd Super I/O = IT8792E @ ISA 0xA60** (`sensors`: `it8792-isa-0a60`), matching the §3 decode.
- **GPE 0x0A = AMD CPM MYRTLE runtime SSDT** `_L0A` (GPIO/GEVENT aggregate SCI), matching static `$A11`.
