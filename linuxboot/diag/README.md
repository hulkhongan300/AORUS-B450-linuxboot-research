# diag — information gathering for the tinylinux test (not part of any firmware image)

Two tools that collect and check everything needed to test `../tinylinux/out/tinylinux.efi` on the real
board **from a USB stick**. They only read; nothing here flashes, mounts, or changes boot settings.

| File | Runs on | Does |
|---|---|---|
| `collect.sh` | installed OS **and** tinylinux's USB shell | Read-only snapshot: board/BIOS, CPU, UEFI + Secure Boot, every PCI device with its driver, disks/partitions/filesystems, kernels + boot configs, keyboards, display, serial, USB, ACPI, sensors, kernel log. Plain `sh`; works with tinylinux's 20 busybox commands. Drops firewall log lines (LAN IPs/MACs) and DMI serials. |
| `check_readiness.py` | your PC (Python 3) | Turns reports into a PASS/FAIL/WARN/TODO checklist against tinylinux's **actual** kernel `.config`: maps each storage/USB controller's driver to its Kconfig symbol via the kernel Makefiles; checks `/boot` filesystem, boot entries, keyboard, framebuffer, Secure Boot, CPU, BIOS version. Converts `limine.conf` into suggested BootLoaderSpec entries (written to the report, never installed). |

## Workflow
**1. On CachyOS** (sudo adds `/boot`, kernel log, ESRT details):
```sh
sudo sh collect.sh ~/hwinfo-os
python3 check_readiness.py ~/hwinfo-os          # -> ~/hwinfo-os/READINESS.md
```
Fix any FAIL. If it wrote `suggested_bls/*.conf`, review them; copying them into `/boot/loader/entries/`
lets tinylinux's menu list CachyOS (Limine ignores that folder, so the normal boot is unaffected).

**2. Prepare a USB stick** (FAT32): copy `../tinylinux/out/tinylinux.efi` to `EFI/BOOT/BOOTX64.EFI`
and `collect.sh` to the stick's top folder.

**3. Boot it**: F12 at power-on → choose the USB stick. At the tinylinux menu press `s` (if it found no
entries it goes to the shell by itself). Find the stick (`ls /mnt` — the removable one; tinylinux mounts
every FAT partition read-only, including your ESP), then:
```sh
mount -o remount,rw /mnt/sdb1 && sh /mnt/sdb1/collect.sh      # writes /mnt/sdb1/report-tinylinux
umount /mnt/sdb1 && reboot -f
```
**4. Back in CachyOS**:
```sh
python3 check_readiness.py ~/hwinfo-os --tinylinux /run/media/$USER/<stick>/report-tinylinux
```
The `tinylinux run` section is the real proof: which of *this* board's controllers tinylinux's kernel
actually drove, whether the disks and framebuffer appeared, and any kernel errors.

## First run on a B450 AORUS PRO (Ryzen 7 2700X)
17 PASS, 0 FAIL: all boot-relevant controllers (Promontory xHCI + SATA, CPU xHCI + SATA, NVMe) are
covered by tinylinux's built-in drivers. Personal reports are not stored in this repo.

## Verified
- `collect.sh` on CachyOS as a normal user (0.9 s) and inside tinylinux under QEMU/OVMF (busybox only),
  including the default output path next to the script.
- `check_readiness.py`: live report, live + tinylinux report, different-machine detection (QEMU → per-device
  checks skipped), Limine → BLS conversion on a CachyOS-style `limine.conf`.
