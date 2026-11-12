# LinuxBoot Progress — B450 AORUS PRO

## Session 5 (2026-11-11): tooling validated, approach confirmed safe

### DONE
1. **Go 1.27.4** installed locally (`toolchain/go`, no sudo) — on the /home volume.
2. **fiano/utk v1.2.0** built (`toolchain/bin/utk`) — parses the stock image cleanly.
   - Structure: 9 FVs, 503 files, **309 DXE drivers**, 1 DXE core, 112 MM (SMM) modules, 1791 sections.
3. **CRITICAL VALIDATION — utk round-trip preserves the signed/measured regions byte-for-byte:**
   | Region | Result |
   |---|---|
   | EFS + PSP/BHD + APCB (0x20000–0x94f000) | **IDENTICAL** |
   | Promontory FW (0x90f000–0x94f000) | **IDENTICAL** |
   | PEI/RTM FV, PSP-measured (0xe40000–0x1000000) | **IDENTICAL** |
   | DXE FV (0x94f000–0xe3f000) | re-serialized (expected; same 503 logical files) |
   → A LinuxBoot DXE modification will **not** disturb the PSP signature chain or the AMD blobs. This was
     the key unknown; it is now answered. (Verified with a python byte-range diff.)
4. **Replacement target identified:** the AMI **`Bds`** driver
   `GUID 8F4B8F82-9B91-4028-86E6-F4DB7D4C1DFF` — the standard LinuxBoot insertion point (swap the UEFI
   boot manager for a payload that boots Linux).

### Space budget (measured, Session 5)
- DXE volume is 5,177,344 bytes and nearly full; stock headroom ~650 KB.
- Tier 1 strip (35 drivers: Setup UI, network stack, PXE/HTTP boot, I211 UNDI, UEFI RAID, CSM) -> budget 1.54 MiB.
- Tier 2a (+ TlsDxe, CoolGUIDxe, QFlashHandler, ReFlash) -> **budget 2.17 MiB**, all CPUs still supported.
- Tier 2b (+60 other-CPU-family drivers) -> 2.31 MiB only; not worth locking to Zen/Zen+.
- utk v1.2.0 `remove` crashes when one pattern matches several files; workaround = remove by exact GUID.
- Signed/measured regions stayed byte-identical and all 14 directory checksums OK after every strip.

### Payload size (measured)
- Minimal u-root initramfs (init, boot, gosh, kexec, ls, cat, mount, dmesg): 9.0 MiB raw, **2.79 MiB xz**.
- Full u-root core: 4.31 MiB xz. Stock distro kernel: 17 MiB.
- **Result: does not fit.** The minimal initramfs alone exceeds the 2.17 MiB budget, before adding a kernel
  (~1.5–2 MiB even when heavily trimmed). Needed total ~4–5 MiB vs 2.17 MiB available.

### Status after the size result (Session 6)
- **In-flash route: parked.** The payload does not fit the stock DXE volume, and making room would mean
  removing core firmware components that cannot be validated without flashing (ruled out). No modified
  ROM is being produced.
- **On-disk route: working in QEMU.** Same u-root/kexec userspace, launched by the stock UEFI through the
  Linux EFI boot stub as one UKI file -> `efistub/README.md`. Verified chain: OVMF -> UKI -> u-root menu ->
  BLS entry on NVMe -> kexec -> target kernel (EFI runtime preserved). Not open firmware (AMI UEFI still
  runs); it opens everything after the firmware hand-off.

### Size problem solved on paper (Session 6, `tinylinux/`)
- Coreboot-style custom kernel (kernel.org 6.18.60, `tinyconfig` + board drivers, XZ, -Os) + static busybox
  + libc-free kexec tool, all in one EFI bzImage: **2,167,808 B = 2.067 MiB < 2.17 MiB budget**.
- Verified in QEMU/OVMF: firmware -> tinylinux.efi -> menu (8 s) -> BLS entry on NVMe -> kexec, UEFI
  runtime kept. Screen build shows the menu on the GOP framebuffer.
- Still not a chip image: needs a BDS-replacement DXE shim, costs the Setup menu (tier 2a strip), and
  cannot be tested without flashing. No modified ROM produced. Safe real-hw test = USB stick + F12.

### Diagnostics (Session 6, `diag/`)
- `collect.sh` (read-only, runs on CachyOS and inside tinylinux's busybox) + `check_readiness.py`
  (checklist vs tinylinux's real .config). First run on this PC: 17 PASS / 0 FAIL / 1 WARN (BIOS F66i vs
  analysed F67c) / 2 TODO (sudo for /boot, the USB tinylinux run).

### NEXT (optional)
- Kernel trimmed for this board (built-in nvme/vfat/igb/amdgpu, no modules) to shrink the UKI.
- A BLS entry for the installed CachyOS kernel so u-root can list it (it does not parse limine.conf).
