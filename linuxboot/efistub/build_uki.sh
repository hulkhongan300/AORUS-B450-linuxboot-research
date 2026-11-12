#!/usr/bin/env bash
# Build a Unified Kernel Image (UKI): kernel + u-root initramfs + cmdline in ONE EFI executable.
# The stock UEFI firmware can launch it directly (EFI boot stub) -- nothing is written to flash.
# Method: Arch wiki "Unified kernel image" -> manual objcopy with systemd's linuxx64.efi.stub.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
KERNEL="${1:-$here/../bzImage-lts}"
INITRD="${2:-$here/../initramfs-min.cpio.xz}"
CMDLINE="${3:-console=ttyS0,115200 console=tty0 quiet}"
OUT="${4:-$here/esp/EFI/BOOT/BOOTX64.EFI}"
STUB=/usr/lib/systemd/boot/efi/linuxx64.efi.stub

work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
printf '%s' "$CMDLINE" > "$work/cmdline"
printf 'NAME="u-root LinuxBoot-on-disk"\nID=uroot\n' > "$work/os-release"

align=$((16#$(objdump -p "$STUB" | awk '$1=="SectionAlignment"{print $2}')))
up() { echo $(( ($1 + align - 1) / align * align )); }
end=$(objdump -h "$STUB" | awk 'NF==7 {e=strtonum("0x"$3)+strtonum("0x"$4)} END{print e}')
osrel=$(up "$end")
cmdl=$(up $((osrel + $(stat -Lc%s "$work/os-release"))))
init=$(up $((cmdl + $(stat -Lc%s "$work/cmdline"))))
linux=$(up $((init + $(stat -Lc%s "$INITRD"))))

mkdir -p "$(dirname "$OUT")"
objcopy \
  --add-section .osrel="$work/os-release" --change-section-vma .osrel=$(printf 0x%x $osrel) \
  --add-section .cmdline="$work/cmdline"  --change-section-vma .cmdline=$(printf 0x%x $cmdl) \
  --add-section .initrd="$INITRD"         --change-section-vma .initrd=$(printf 0x%x $init) \
  --add-section .linux="$KERNEL"          --change-section-vma .linux=$(printf 0x%x $linux) \
  "$STUB" "$OUT"
ls -l "$OUT"
