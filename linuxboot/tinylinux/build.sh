#!/usr/bin/env bash
# Build "tinylinux": one EFI-bootable bzImage = size-optimized Linux + embedded busybox initramfs + kexec-boot.
# Output: out/tinylinux.efi. Run ./fetch.sh first (kernel.org 6.18.60 + busybox 1.37.0 into ../toolchain/src).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; src="$here/../toolchain/src"; out="$here/out"
KSRC="$src/linux-6.18.60"; BB="$src/busybox-1.37.0"
export PATH="$here/../toolchain/bin:$PATH"   # busybox 'bc' (host lacks bc; kernel build needs it)
mkdir -p "$out"
# CONSOLE=screen (default, real board: menu on the monitor) | serial (QEMU -nographic tests)
CONSOLE="${CONSOLE:-screen}"
case "$CONSOLE" in
  screen) CMDLINE="console=ttyS0,115200 console=tty0 loglevel=4"; name=tinylinux.efi ;;
  serial) CMDLINE="console=tty0 console=ttyS0,115200 loglevel=4"; name=tinylinux-serial.efi ;;
  *) echo "CONSOLE must be screen|serial"; exit 2 ;;
esac

# 1. busybox: allnoconfig + only the applets /init uses, static
bbo="$out/busybox-build"; mkdir -p "$bbo"
make -s -C "$BB" O="$bbo" allnoconfig >/dev/null
for o in STATIC ASH SH_IS_ASH ASH_ECHO ASH_PRINTF ASH_TEST ASH_OPTIMIZE_FOR_SIZE FEATURE_EDITING CTTYHACK \
         SETSID FEATURE_SH_MATH MOUNT UMOUNT MKDIR RMDIR CAT LS SLEEP SED GREP HEAD CUT TR DMESG HALT POWEROFF REBOOT; do
  sed -i "s/^# CONFIG_$o is not set/CONFIG_$o=y/" "$bbo/.config"; done
yes "" | make -s -C "$BB" O="$bbo" oldconfig >/dev/null 2>&1 || true
make -s -C "$BB" O="$bbo" -j"$(nproc)" >/dev/null 2>&1
# 2. kexec-boot (static)
gcc -Os -static -nostdlib -ffreestanding -fno-builtin -fno-stack-protector -fcf-protection=none -s -Wl,--build-id=none -o "$out/kexec-boot" "$here/kexec-boot.c"
# 3. initramfs list (gen_init_cpio format), embedded uncompressed so the kernel's XZ covers both
cat > "$out/initramfs.list" <<L
dir /dev 0755 0 0
nod /dev/console 0600 0 0 c 5 1
dir /proc 0755 0 0
dir /sys 0755 0 0
dir /mnt 0755 0 0
dir /bin 0755 0 0
file /init $here/init 0755 0 0
file /bin/busybox $bbo/busybox 0755 0 0
file /bin/kexec-boot $out/kexec-boot 0755 0 0
L
for a in sh mount umount mkdir rmdir cat ls sleep sed grep head cut tr dmesg halt poweroff reboot setsid cttyhack; do
  echo "slink /bin/$a busybox 0777 0 0" >> "$out/initramfs.list"; done
# 4. kernel: tinyconfig + fragment (coreboot-LinuxBoot style), size-first
ko="$out/kernel-build"; mkdir -p "$ko"
make -s -C "$KSRC" O="$ko" ARCH=x86_64 tinyconfig >/dev/null
sed -e "s|^CONFIG_INITRAMFS_SOURCE=.*|CONFIG_INITRAMFS_SOURCE=\"$out/initramfs.list\"|" \
    -e "s|^CONFIG_CMDLINE=.*|CONFIG_CMDLINE=\"$CMDLINE\"|" "$here/kernel.fragment" > "$out/fragment.cfg"
(cd "$ko" && "$KSRC/scripts/kconfig/merge_config.sh" -m -O "$ko" "$ko/.config" "$out/fragment.cfg" >/dev/null)
make -s -C "$KSRC" O="$ko" ARCH=x86_64 olddefconfig >/dev/null
# report fragment options that did not survive dependency resolution
while IFS= read -r l; do case "$l" in CONFIG_*=*) grep -qxF "$l" "$ko/.config" || echo "NOT APPLIED: $l";; "# CONFIG_"*" is not set") s=${l#"# "}; s=${s%% *}; grep -q "^$s=" "$ko/.config" && echo "STILL ON: $s";; esac; done < "$out/fragment.cfg"
make -C "$KSRC" O="$ko" ARCH=x86_64 -j"$(nproc)" bzImage > "$out/kernel-build.log" 2>&1 || { tail -30 "$out/kernel-build.log"; exit 1; }
cp "$ko/arch/x86/boot/bzImage" "$out/$name"
ls -l "$bbo/busybox" "$out/kexec-boot" "$out/$name"
