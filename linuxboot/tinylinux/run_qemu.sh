#!/usr/bin/env bash
# Boot out/tinylinux*.efi under OVMF with a demo OS on an emulated NVMe disk.
# Chain: OVMF -> tinylinux.efi (EFI stub) -> busybox /init menu -> kexec_file_load -> demo kernel.
# Demo kernel: DEMO_KERNEL (+ optional DEMO_INITRD); default = tinylinux itself, started with rdinit=/bin/sh.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; cd "$here"
IMG="${IMG:-tinylinux-serial.efi}"; DEMO_KERNEL="${DEMO_KERNEL:-out/$IMG}"; DEMO_INITRD="${DEMO_INITRD:-}"
mkdir -p esp/EFI/BOOT && cp "out/$IMG" esp/EFI/BOOT/BOOTX64.EFI
if [ ! -f osdisk.img ]; then
  truncate -s 64M osdisk.img && mformat -i osdisk.img -F -v OSDISK ::
  mmd -i osdisk.img ::/loader ::/loader/entries
  mcopy -i osdisk.img "$DEMO_KERNEL" ::/vmlinuz-demo
  entry='title   Demo OS on NVMe (kexec target)\nlinux   /vmlinuz-demo\n'
  if [ -n "$DEMO_INITRD" ]; then mcopy -i osdisk.img "$DEMO_INITRD" ::/initrd-demo; entry="${entry}initrd  /initrd-demo\\n"; fi
  printf "${entry}options console=ttyS0,115200 rdinit=/bin/sh demo_kexec_ok=1\\n" | mcopy -i osdisk.img - ::/loader/entries/demo.conf
fi
cp /usr/share/edk2/x64/OVMF_VARS.4m.fd ovmf_vars.fd
exec qemu-system-x86_64 -M q35 -cpu max -m 2048 ${QEMU_DISPLAY:--nographic} -net none \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd \
  -drive if=pflash,format=raw,file=ovmf_vars.fd -drive format=raw,file=fat:rw:esp \
  -drive if=none,id=nvm,format=raw,file=osdisk.img -device nvme,serial=demo0,drive=nvm ${QEMU_SERIAL:--serial mon:stdio} ${QEMU_EXTRA:-}
