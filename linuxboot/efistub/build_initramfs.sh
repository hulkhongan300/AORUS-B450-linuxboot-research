#!/usr/bin/env bash
# Build the u-root initramfs for the on-disk LinuxBoot UKI, bundling the kernel modules that the
# CachyOS-LTS kernel builds as modules but the boot path needs (FAT for the ESP, NVMe for the SSD).
# u-root init auto-loads /lib/modules/*.ko in ALPHABETICAL order, single pass -> numeric prefixes
# encode the dependency order from modules.dep.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; lb="$here/.."
KVER="${KVER:-6.18.60-2-cachyos-lts}"; M="/usr/lib/modules/$KVER/kernel"
OUT="${1:-$here/initramfs-uki.cpio}"
stage="$here/modstage"; rm -rf "$stage"; mkdir -p "$stage"
i=0
for m in fs/fat/fat fs/fat/vfat fs/nls/nls_iso8859-1 \
         crypto/hkdf drivers/nvme/common/nvme-keyring drivers/nvme/common/nvme-auth \
         drivers/nvme/host/nvme-core drivers/nvme/host/nvme; do
  name=$(printf '%02d-%s.ko' $i "$(basename $m)"); i=$((i+1))
  zstd -q -d -f "$M/$m.ko.zst" -o "$stage/$name"
done
files=(); for f in "$stage"/*.ko; do files+=(-files "$f:lib/modules/$(basename "$f")"); done
export PATH="$lb/toolchain/go/bin:$PATH" GOPATH="$lb/toolchain/gopath" GOTOOLCHAIN=local
cd "$lb/toolchain/u-root"
go run . -o "$OUT" -uinitcmd=boot "${files[@]}" \
  ./cmds/core/init ./cmds/core/gosh ./cmds/core/ls ./cmds/core/cat ./cmds/core/mount \
  ./cmds/core/dmesg ./cmds/boot/boot ./cmds/core/kexec
xz -9e --check=crc32 -T0 -k -f "$OUT"
ls -l "$OUT" "$OUT.xz"; ls "$stage"
