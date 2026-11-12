# Open-Firmware Options for the Gigabyte B450 AORUS PRO

Honest assessment of every route to run more-open firmware on **this specific board**, grounded in the
reverse-engineering (see `PORTING_MAP.md`, `FINDINGS.md`). Your standing rule — **do not flash the
physical chip** — is noted against each; most routes ultimately require a flash to *deploy*, so they are
documented as feasibility, not as something executable in this environment.

## Route A — Full coreboot port
- **Status: not feasible now.** Needs a new `src/soc/amd/am4_desktop`, a Promontory driver, two ITE
  superio drivers, and the PSP to accept an unsigned bootblock. The first three are large engineering;
  the last is a hardware eFuse wall on retail AORUS boards (`FINDINGS.md` §3).
- All the *board* data a port needs is recovered (`coreboot_reference/mainboard_draft/`). The gap is AMD
  SoC code, not board knowledge.

## Route B — LinuxBoot / UEFI payload in the stock image
Keep the signed SEC/PEI/AGESA/PSP/Promontory init (satisfies the PSP and brings up RAM + the chipset),
replace only the DXE boot path with a Linux kernel + initramfs (u-root). This is the **least-blocked**
route because it doesn't touch the signed region.
- **What you'd replace:** the DXE Boot-Device-Selection path. Relevant modules in the image:
  `BdsDxe`, `UiApp`/SetupBrowser, `Shell`, and the CSM stack (`CsmDxe`, `CsmVideo`, `CsmBlockIo`,
  `UefiPxeBcDxe`) — the board still ships a full CSM, so legacy/!UEFI boot exists.
- **Where:** the main DXE firmware volume at flash **0x94f000** (`flash_layout_full.txt`); the UEFI
  volume is BHD type 0x62 (`amdfw_psp_combo.txt`). The PSP's measured RTM volume (BHD type 0x62) is at
  **0xe42000** (the PEI region), **not** the DXE volume at 0x94f000.
- **Verified favorable point:** the image has **no separate DXE-hash / BootGuard-style verifier module**
  (grep for `FvMainHash`/`BootGuard`/`VerifyFv` finds nothing). So replacing DXE content should not trip
  an x86-side integrity check — only the PSP's PEI measurement matters, and that region is untouched.
  (Caveat still: the RTM entry's size is ~0x3c0000, larger than the 0x1c0000 PEI FV, so confirm the exact
  measured span before relying on this.)
- **Verified blocker for the normal update path:** the board ships `SecSMIFlash` + `CapsuleRuntimeDxe` +
  **`RpmcDxe`/`RpmcSmm` (Replay-Protected Monotonic Counter = anti-rollback)**. So you **cannot** deploy a
  modified image through the in-OS/BIOS updater — it verifies capsule signatures and enforces anti-rollback.
- **Tools:** UEFITool/uefireplace to swap a DXE driver for a `LinuxBootPkg` payload. **Note:
  `uefitool`/`uefiextract` are not installed here** (were available in session 1); reinstall before attempting.
- **Deploy:** requires writing the 16 MiB chip with an **external CH341A + SOIC-8 clip** and a verified
  backup (the internal/capsule path is signature-locked, per above). Under your no-flash rule this stays a
  paper procedure.

## Route C — Use a board that already has open firmware
If the goal is *running* open firmware rather than this exact board: pick hardware with upstream coreboot
or Dasharo support (some Intel desktop boards, supported ThinkPads/Chromebooks, a few AMD server boards
like the `mz33-ar1` that exists in-tree). Zero risk, fully supported.

## Route D — Virtual experimentation (safe, available now)
The coreboot QEMU sandbox is built and boots (`tools/run_coreboot_qemu.sh`, `FINDINGS.md` §5c). Use it to
learn coreboot internals, ACPI generation, and payloads with **zero hardware risk**. This is the only
route that is both open-firmware *and* executable under the no-flash rule.

- **Payload size (Session 6):** a stock distro kernel + u-root (~4–5 MiB) does not fit the 2.17 MiB
  room left after stripping Setup/network/CSM. A coreboot-style custom kernel + busybox does:
  **2.067 MiB** (`../linuxboot/tinylinux/`, verified booting + kexec in QEMU). Remaining gaps: a
  BDS-replacement DXE shim, loss of the Setup menu, and no way to test without flashing.

## Route E — LinuxBoot userspace from disk via the EFI boot stub (tested in QEMU)
Route B's payload does not fit the DXE volume (`../linuxboot/PROGRESS.md`). The same u-root + kexec
userspace can instead be a **Unified Kernel Image** on the ESP or a USB stick, launched directly by the
stock UEFI through the Linux EFI boot stub. No flash write, no size limit. Verified under OVMF:
firmware -> UKI -> u-root menu -> BootLoaderSpec entry on an NVMe disk -> kexec -> target kernel.
- **Open:** everything after the firmware hand-off. **Still closed:** the whole AMI UEFI, which runs first.
- Details, build scripts and gotchas: `../linuxboot/efistub/README.md`.

## Recommendation
- To *learn / experiment*: **Route D** now; **Route C** if you want it on real hardware.
- For *this board specifically*: **Route B** is the only one that could ever work, and only as far as a
  documented procedure — deployment needs a flash you've (correctly) ruled out without external recovery
  gear. Route A remains blocked by AMD code + PSP fuses regardless of effort.

## Cross-checks logged this session
- `Ite8790ECSmi` DXE module present → confirms the **IT8792E** (8790-class) EC, matching the live
  `it8792-isa-0a60` and the §3 decode.
- Full **CSM** present (`CsmDxe`/`CsmVideo`/…) → legacy boot is available, which simplifies a LinuxBoot
  payload that wants BIOS-style callbacks.
