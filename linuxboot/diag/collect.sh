#!/bin/sh
# collect.sh - READ-ONLY hardware/firmware information collector for the tinylinux / LinuxBoot
# readiness check. A diagnostic only: it is NOT part of any firmware image.
#
# Runs in two places (same script, it adapts to what is available):
#   1. Installed OS (CachyOS):  sh collect.sh [OUTDIR]
#                               sudo sh collect.sh [OUTDIR]     <- adds the root-only parts (/boot listing,
#                                                                 kernel log, serial UART details)
#   2. tinylinux USB shell (press 's' at the tinylinux menu; only busybox basics exist there):
#        mount -o remount,rw /mnt/sdX1 && sh /mnt/sdX1/collect.sh      (writes /mnt/sdX1/report-tinylinux)
#
# What it does: reads /proc, /sys and boot config files, runs listing tools when present
# (lspci, lsblk, findmnt, lsusb, efibootmgr, bootctl, mokutil), writes everything into OUTDIR.
# What it never does: load modules, write to /sys or EFI variables, change boot entries,
# mount/unmount anything, or touch the SPI flash. Serial numbers/UUIDs from DMI are not collected.
set -u
VERSION=1
if [ -x /bin/kexec-boot ]; then DEF=${0%/*}/report-tinylinux      # tinylinux: next to this script (USB stick)
else DEF=./hwinfo-$(cat /proc/sys/kernel/hostname 2>/dev/null || echo host); fi
OUT=${1:-$DEF}
case "$OUT" in */*) ;; *) OUT=./$OUT ;; esac
mkdir -p "$OUT" || { echo "collect.sh: cannot create $OUT" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }
# run FILE CMD... : save a command's output (stdout+stderr) and exit status
run() { f=$1; shift; { echo "\$ $*"; "$@"; echo "[exit $?]"; } > "$OUT/$f" 2>&1; }
# kv FILE... : print "path: content" for readable one-line sysfs files
kv() { for f in "$@"; do [ -r "$f" ] && printf '%s: %s\n' "$f" "$(cat "$f" 2>/dev/null)"; done; }
resolve() { (cd -P "$1" 2>/dev/null && pwd -P); }
note() { echo "$*" >> "$OUT/SUMMARY.txt"; echo "  $*"; }

UID_=$(sed -n 's/^Uid:[[:space:]]*\([0-9]*\).*/\1/p' /proc/self/status)
if [ -x /bin/kexec-boot ]; then ENV=tinylinux; else ENV=os; fi
: > "$OUT/SUMMARY.txt"
echo "collect.sh v$VERSION -> $OUT (env=$ENV uid=$UID_)"

# ---- meta -----------------------------------------------------------------------------------
{
  echo "collector_version=$VERSION"; echo "env=$ENV"; echo "uid=$UID_"
  echo "kernel_release=$(cat /proc/sys/kernel/osrelease)"
  echo "kernel_version=$(cat /proc/version)"
  echo "cmdline=$(cat /proc/cmdline)"
  have date && echo "date=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  [ -r /etc/os-release ] && sed -n 's/^PRETTY_NAME=/os=/p' /etc/os-release
} > "$OUT/meta.txt" 2>&1

# ---- board / BIOS (DMI, no serials) -----------------------------------------------------------
for k in sys_vendor product_name product_version board_vendor board_name board_version \
         bios_vendor bios_version bios_date bios_release chassis_type; do
  [ -r /sys/class/dmi/id/$k ] && echo "$k=$(cat /sys/class/dmi/id/$k 2>/dev/null)"
done > "$OUT/dmi.txt"

# ---- CPU / memory -----------------------------------------------------------------------------
{ sed '/^$/q' /proc/cpuinfo; echo "processors=$(grep -c '^processor' /proc/cpuinfo)"; } > "$OUT/cpu.txt" 2>&1
head -n 5 /proc/meminfo > "$OUT/meminfo.txt" 2>&1

# ---- UEFI -------------------------------------------------------------------------------------
{
  if [ -d /sys/firmware/efi ]; then
    echo "efi=present"
    kv /sys/firmware/efi/fw_platform_size
    [ -d /sys/firmware/efi/runtime ] && echo "runtime_map=present"
    G=8be4df61-93ca-11d2-aa0d-00e098032b8c
    for v in SecureBoot SetupMode; do
      f=/sys/firmware/efi/efivars/$v-$G
      if [ -r "$f" ] && have od; then echo "$v=$(od -An -tu1 -j4 -N1 "$f" | tr -d ' ')"; fi
    done
    for e in /sys/firmware/efi/esrt/entries/*; do
      [ -d "$e" ] || continue
      echo "esrt ${e##*/}:"; kv "$e/fw_class" "$e/fw_type" "$e/fw_version" "$e/lowest_supported_fw_version" "$e/last_attempt_status"
    done
  else
    echo "efi=absent"
  fi
} > "$OUT/efi.txt" 2>&1
have efibootmgr && run efibootmgr.txt efibootmgr          # no arguments = list only
have bootctl    && run bootctl.txt bootctl status --no-pager
have mokutil    && run mokutil.txt mokutil --sb-state

# ---- PCI: every device with its bound driver/module -------------------------------------------
{
  printf 'slot\tvendor\tdevice\tsubvendor\tsubdevice\tclass\tdriver\tmodule\n'
  for d in /sys/bus/pci/devices/*; do
    [ -r "$d/vendor" ] || continue
    drv=-; mod=-
    if [ -e "$d/driver" ]; then
      p=$(resolve "$d/driver"); drv=${p##*/}
      [ -e "$d/driver/module" ] && { p=$(resolve "$d/driver/module"); mod=${p##*/}; }
    fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "${d##*/}" "$(cat "$d/vendor")" "$(cat "$d/device")" \
      "$(cat "$d/subsystem_vendor" 2>/dev/null)" "$(cat "$d/subsystem_device" 2>/dev/null)" \
      "$(cat "$d/class")" "$drv" "$mod"
  done
} > "$OUT/pci.tsv"
have lspci && run lspci.txt lspci -nnk

# ---- block devices + filesystems ----------------------------------------------------------------
{
  printf 'name\tsectors\tremovable\tro\tpartition\tsyspath\n'
  for b in /sys/class/block/*; do
    [ -e "$b" ] || continue
    part=no; [ -e "$b/partition" ] && part=yes
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "${b##*/}" "$(cat "$b/size" 2>/dev/null)" "$(cat "$b/removable" 2>/dev/null)" \
      "$(cat "$b/ro" 2>/dev/null)" "$part" "$(resolve "$b")"
  done
} > "$OUT/block.tsv"
cat /proc/mounts > "$OUT/mounts.txt" 2>&1
have lsblk   && lsblk -J -o NAME,KNAME,PKNAME,SIZE,TYPE,FSTYPE,PARTTYPE,PARTLABEL,LABEL,MOUNTPOINTS,TRAN,RM,MODEL > "$OUT/lsblk.json" 2>"$OUT/lsblk.err"
have findmnt && run findmnt.txt findmnt -no TARGET,SOURCE,FSTYPE,OPTIONS --real

# ---- boot files: kernels, initramfs, BootLoaderSpec / Limine / GRUB configs --------------------
{
  for root in /boot /efi /boot/efi /mnt/*; do
    [ -d "$root" ] || continue
    echo "##### ROOT $root"; ls -la "$root" 2>&1
    for sub in EFI EFI/BOOT EFI/Linux EFI/limine loader loader/entries limine boot; do
      [ -d "$root/$sub" ] && { echo "##### LIST $root/$sub"; ls -la "$root/$sub" 2>&1; }
    done
    for f in "$root"/loader/loader.conf "$root"/loader/entries/*.conf "$root"/limine.conf \
             "$root"/limine/limine.conf "$root"/EFI/limine/limine.conf "$root"/boot/limine.conf \
             "$root"/boot/limine/limine.conf "$root"/grub/grub.cfg "$root"/boot/grub/grub.cfg; do
      [ -f "$f" ] || continue
      echo "##### FILE $f"
      case "$f" in
        *grub.cfg) grep -nE '^[[:space:]]*(menuentry|linux|initrd)' "$f" 2>&1 | head -n 60 ;;
        *) cat "$f" 2>&1 ;;
      esac
    done
  done
} > "$OUT/boot_files.txt" 2>&1

# ---- console: keyboard, framebuffer, serial ----------------------------------------------------
cat /proc/bus/input/devices > "$OUT/input.txt" 2>&1
{
  echo "## /proc/fb"; cat /proc/fb 2>&1
  for g in /sys/class/graphics/fb*; do [ -e "$g" ] && kv "$g/name" "$g/virtual_size" "$g/bits_per_pixel"; done
  for c in /sys/class/drm/card*-*; do [ -r "$c/status" ] && echo "${c##*/}: $(cat "$c/status")"; done
} > "$OUT/display.txt"
{
  for t in /sys/class/tty/ttyS*; do [ -e "$t" ] && kv "$t/port" "$t/irq" "$t/type"; done
  [ -r /proc/tty/driver/serial ] && { echo "## /proc/tty/driver/serial"; cat /proc/tty/driver/serial; }
} > "$OUT/serial.txt" 2>&1

# ---- USB, ACPI, sensors, IOMMU ---------------------------------------------------------------
{
  for u in /sys/bus/usb/devices/*; do
    [ -r "$u/idVendor" ] || continue
    printf '%s\t%s:%s\t%s\t%s\n' "${u##*/}" "$(cat "$u/idVendor")" "$(cat "$u/idProduct")" \
      "$(cat "$u/speed" 2>/dev/null)" "$(cat "$u/product" 2>/dev/null)"
  done
} > "$OUT/usb.tsv"
have lsusb && run lsusb.txt lsusb -t
ls -l /sys/firmware/acpi/tables /sys/firmware/acpi/tables/dynamic > "$OUT/acpi_tables.txt" 2>&1
for h in /sys/class/hwmon/hwmon*; do [ -r "$h/name" ] && echo "${h##*/}: $(cat "$h/name")"; done > "$OUT/hwmon.txt"
ls -l /sys/class/iommu > "$OUT/iommu.txt" 2>&1

# ---- kernel side: log, modules, kexec state -----------------------------------------------------
# firewall/netfilter lines (" MAC=", LAN IPs) are dropped: not needed, and private
if dmesg >/dev/null 2>&1; then
  dmesg 2>&1 | grep -v ' MAC=' > "$OUT/kernel_log.txt"
elif have journalctl && journalctl -k -b -n 1 --no-pager >/dev/null 2>&1; then
  journalctl -k -b --no-pager 2>&1 | grep -v ' MAC=' > "$OUT/kernel_log.txt"
else note "kernel log unreadable (run with sudo)"; fi
cut -d' ' -f1 /proc/modules > "$OUT/modules.txt" 2>/dev/null
kv /sys/kernel/kexec_loaded /sys/kernel/kexec_crash_loaded > "$OUT/kexec.txt"
[ "$ENV" = tinylinux ] && ls -l /bin > "$OUT/tinylinux_bin.txt" 2>&1

# ---- root-only extras ---------------------------------------------------------------------------
if [ "$UID_" = 0 ]; then
  if have dmidecode; then
    for s in bios-vendor bios-version bios-release-date baseboard-manufacturer baseboard-product-name baseboard-version; do
      echo "$s=$(dmidecode -s $s 2>&1)"
    done > "$OUT/dmidecode.txt"
  fi
  have blkid && run blkid.txt blkid
else
  note "not root: /boot contents, kernel log and some details may be missing (rerun: sudo sh collect.sh $OUT)"
fi

# ---- finish -------------------------------------------------------------------------------------
if [ -n "${SUDO_UID:-}" ] && have chown; then chown -R "$SUDO_UID:${SUDO_GID:-$SUDO_UID}" "$OUT"; fi
echo "files: $(ls "$OUT" | tr '\n' ' ')" >> "$OUT/SUMMARY.txt"
if have tar; then
  tar -czf "$OUT.tar.gz" -C "${OUT%/*}" "${OUT##*/}" 2>/dev/null && echo "archive: $OUT.tar.gz"
  [ -n "${SUDO_UID:-}" ] && have chown && chown "$SUDO_UID:${SUDO_GID:-$SUDO_UID}" "$OUT.tar.gz"
fi
echo "done: $OUT"
