#!/usr/bin/env python3
"""Walk the AMD PSP2 *combo* firmware directory and list each SoC generation's $PSP entries.
amdfwread chokes on the PSP2/BHD2 combo cookie; this handles it. Reference inventory of the
signed blobs an AM4 coreboot port would have to reuse. Usage: amdfw_combo.py <image> [psp_dir_off]"""
import sys, struct
d = open(sys.argv[1], 'rb').read()
ROM = 0x100000000 - len(d)
def f(addr):                 # map an EFS/flash address to a file offset
    if addr in (0, 0xffffffff): return None
    return (addr - ROM) if addr >= ROM else (addr & 0xffffff if addr > len(d) else addr)
def fletcher32(off, nbytes):     # AMD dir checksum: Fletcher-32 over count..end (from off+8)
    s1 = s2 = 0
    for i in range(nbytes // 2):
        w = struct.unpack_from('<H', d, off + 8 + i*2)[0]
        s1 = (s1 + w) % 0xffff; s2 = (s2 + s1) % 0xffff
    return (s2 << 16) | s1
def cksum_ok(off, hdr, stride):
    cnt = struct.unpack_from('<I', d, off + 8)[0]
    return struct.unpack_from('<I', d, off + 4)[0] == fletcher32(off, hdr - 8 + cnt*stride)
# SOC-id -> name is APPROXIMATE (ids are AMD-internal). Authoritative family ID is the microcode
# patch_id (see tools/amdfw_microcode.py); a BIOS dir may carry microcode for more than one family.
SOC = {0xbc0a0000: 'SummitRidge?', 0xbc0a0100: 'PinnacleRidge?', 0xbc090000: 'Raven/Picasso?',
       0xbc0b0500: 'Renoir/Cezanne?', 0xbc0c0000: 'Matisse?', 0xbc0c0140: 'Vermeer/Cezanne?'}
# A few common PSP entry type names (public, from coreboot psp_verstage / amdfwtool).
PT = {0x00: 'AMD_PUBLIC_KEY', 0x01: 'PSP_FW_BOOT_LOADER', 0x02: 'PSP_FW_TRUSTED_OS',
      0x03: 'PSP_FW_RECOVERY_BOOT_LOADER', 0x08: 'SMU_OFFCHIP_FW', 0x09: 'AMD_SEC_DBG_PUBLIC_KEY',
      0x0a: 'OEM_PSP_FW_PUBLIC_KEY', 0x0c: 'PSP_FW_SOFT_FUSE_CHAIN_01', 0x12: 'SMU_OFF_CHIP_FW_2',
      0x1a: 'PSP_DEBUG_UNLOCK', 0x21: 'WRAPPED_IKEK', 0x24: 'SEC_GASKET', 0x28: 'DRIVER_ENTRIES',
      0x2a: 'MP2_FW', 0x30: 'AGESA_BOOTLOADER_0', 0x40: 'PSP_DIR_LVL2', 0x5f: 'FW_PSP_SMUSCS',
      0x60: 'FW_IMC', 0x61: 'FW_GEC', 0x62: 'FW_XHCI', 0x63: 'FW_INVALID', 0x6b: 'ABL0'}
BT = {0x60: 'APCB', 0x61: 'APOB_NV', 0x62: 'BIOS_RTM_VOLUME(UEFI)', 0x63: 'APOB', 0x64: 'PMU_INSTRUCTION',
      0x65: 'PMU_DATA', 0x66: 'MICROCODE', 0x67: 'CORE_MCEDATA', 0x68: 'APCB_BACKUP', 0x70: 'BIOS_DIR_LVL2',
      0x6a: 'DYNAMIC_SPDS', 0x5a: 'PSP_MCLF', 0x1a: 'DRIVER', 0x30: 'AGESA'}
def walk_bhd(off, tag):
    cookie = d[off:off+4]
    if cookie not in (b'$BHD', b'$BL2'): return
    cnt = struct.unpack_from('<I', d, off+8)[0]
    print(f'\n## {tag}  {cookie.decode()} bios-dir @ {off:#x}  ({cnt} entries) cksum={"OK" if cksum_ok(off,0x10,24) else "BAD"}')
    for i in range(cnt):
        e = off + 0x10 + i*24
        t, rinst, flags, size, addr, dest = struct.unpack_from('<BBHIQQ', d, e)
        is_value = size == 0xffffffff or (addr >> 32 and (addr & 0xffff000000000000))
        fo = f(addr & 0xffffffff) if not is_value else None
        name = BT.get(t, '')
        inst = (rinst >> 4) & 0xf
        print(f'  type {t:#04x} {name:22} inst={inst} size={size:#010x} addr={addr & 0xffffffff:#x}'
              + (f' (flash {fo:#x})' if fo is not None else ''))
        if t == 0x70 and fo is not None: walk_bhd(fo, tag + ' L2')

def walk_psp(off, tag):
    cookie = d[off:off+4]
    if cookie not in (b'$PSP', b'$PL2'): return
    cnt = struct.unpack_from('<I', d, off+8)[0]
    print(f'\n## {tag}  {cookie.decode()} dir @ {off:#x}  ({cnt} entries) cksum={"OK" if cksum_ok(off,0x10,16) else "BAD"}')
    for i in range(cnt):
        e = off + 0x10 + i*16
        t, sub, flags, size, addr = struct.unpack_from('<BBHIQ', d, e)
        is_value = size == 0xffffffff or (addr >> 32) or (addr & 0xe0000000) == 0x20000000
        fo = None if is_value else f(addr)
        name = PT.get(t, '')
        loc = f' value={addr:#x}' if is_value else (f' addr={addr:#x}' + (f' (flash {fo:#x})' if fo is not None else ''))
        print(f'  type {t:#04x} {name:28} sub={sub} size={size:#010x}{loc}')
        if t == 0x40 and fo is not None:        # level-2 PSP dir
            walk_psp(fo, tag + ' L2')
def combo(off):
    cookie, cksum, cnt, lookup = struct.unpack_from('<4sIII', d, off)
    if cookie != b'2PSP':
        return walk_psp(off, 'PSP')
    print(f'PSP2 combo @ {off:#x}: {cnt} SoC generations cksum={"OK" if cksum_ok(off,0x20,16) else "BAD"}')
    for i in range(cnt):
        idsel, idv, addr = struct.unpack_from('<IIQ', d, off + 0x20 + i*16)
        fo = f(addr)
        tag = f'{SOC.get(idv, "?"):14} (id {idv:#010x})'
        if fo is not None: walk_psp(fo, tag)
combo(int(sys.argv[2], 0) if len(sys.argv) > 2 else 0xe7000)

# BIOS combo directory (2BHD) — per-generation $BHD holding APCB/PMU/UEFI-volume pointers
def combo_bhd(off):
    cookie, cksum, cnt, lookup = struct.unpack_from('<4sIII', d, off)
    if cookie != b'2BHD':
        return walk_bhd(off, 'BIOS')
    print(f'\n==== BHD2 combo @ {off:#x}: {cnt} generations cksum={"OK" if cksum_ok(off,0x20,16) else "BAD"} ====')
    for i in range(cnt):
        idsel, idv, addr = struct.unpack_from('<IIQ', d, off + 0x20 + i*16)
        fo = f(addr)
        if fo is not None: walk_bhd(fo, f'{SOC.get(idv,"?"):14} (id {idv:#010x})')
if len(sys.argv) <= 2:
    combo_bhd(0xe7800)
