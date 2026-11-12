#!/usr/bin/env bash
# Boot the on-disk LinuxBoot UKI under OVMF (UEFI firmware stand-in) with a demo "OS" on an NVMe disk.
# Chain: OVMF -> esp/EFI/BOOT/BOOTX64.EFI (UKI: kernel + u-root) -> u-root menu -> kexec -> demo kernel.
# Interactive: serial console on stdio (Ctrl-A X quits). No KVM needed (-cpu max: kernel is x86-64-v3).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; cd "$here"
[ -f esp/EFI/BOOT/BOOTX64.EFI ] || { ./build_initramfs.sh >/dev/null && ./build_uki.sh ../bzImage-lts ./initramfs-uki.cpio.xz "console=ttyS0,115200"; }
if [ ! -f osdisk.img ]; then   # FAT disk with a BootLoaderSpec entry u-root's `boot` can parse
  truncate -s 64M osdisk.img && mformat -i osdisk.img -F -v OSDISK ::
  mmd -i osdisk.img ::/loader ::/loader/entries
  mcopy -i osdisk.img ../bzImage-lts ::/vmlinuz-demo
  mcopy -i osdisk.img ../initramfs-min.cpio.xz ::/initrd-demo.xz
  printf 'title   Demo OS on NVMe (kexec target)\nlinux   /vmlinuz-demo\ninitrd  /initrd-demo.xz\noptions console=ttyS0,115200 rdinit=/bbin/gosh demo_kexec_ok=1\n' \
    | mcopy -i osdisk.img - ::/loader/entries/demo.conf
fi
cp /usr/share/edk2/x64/OVMF_VARS.4m.fd ovmf_vars.fd
exec qemu-system-x86_64 -M q35 -cpu max -m 2048 -nographic -net none \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd \
  -drive if=pflash,format=raw,file=ovmf_vars.fd \
  -drive format=raw,file=fat:rw:esp \
  -drive if=none,id=nvm,format=raw,file=osdisk.img -device nvme,serial=demo0,drive=nvm \
  -serial mon:stdio
