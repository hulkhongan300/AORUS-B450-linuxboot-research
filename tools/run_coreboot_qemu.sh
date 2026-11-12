#!/usr/bin/env bash
# Boot the sandbox coreboot (qemu-q35 + SeaBIOS) build in QEMU. Virtual only - touches no hardware.
#   tools/run_coreboot_qemu.sh            -> interactive, serial console on this terminal (Ctrl-A X to quit)
#   tools/run_coreboot_qemu.sh log 15     -> headless for 15 s, console saved to analysis/coreboot_qemu_serial.log
set -euo pipefail
cd "$(dirname "$0")/.."
ROM=coreboot/build/coreboot.rom
[ -f "$ROM" ] || { echo "build first: cd coreboot && make -j\$(nproc)"; exit 1; }
if [ "${1:-}" = log ]; then
  timeout "${2:-15}" qemu-system-x86_64 -M q35 -m 1G -bios "$ROM" -display none \
    -serial file:analysis/coreboot_qemu_serial.log -no-reboot || true
  sed 's/\x1b\[[0-9;]*m//g' analysis/coreboot_qemu_serial.log | grep -E 'starting|Jumping|SeaBIOS|Press ESC' | head
else
  exec qemu-system-x86_64 -M q35 -m 1G -bios "$ROM" -nographic -serial mon:stdio
fi
