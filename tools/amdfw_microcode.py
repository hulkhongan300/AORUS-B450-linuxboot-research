#!/usr/bin/env python3
"""List the CPU microcode patches in an AMD BIOS image, identified by patch_id (authoritative).
Walks the BIOS directories (BHD2 combo + per-generation $BHD/$BL2) and reads each type-0x66 entry's
AMD microcode header (date u32, patch_id u32). Usage: amdfw_microcode.py <image>"""
import sys, struct
d = open(sys.argv[1], 'rb').read()
ROM = 0x100000000 - len(d)
def fo(a):
    if a in (0, 0xffffffff): return None
    return a - ROM if a >= ROM else (a & 0xffffff if a > len(d) else a)
# patch_id bits [16:31] == CPUID family/model group
FAM = {0x0800: 'Summit/Pinnacle Ridge (Zen/Zen+, fam17h 00-0Fh)',
       0x0810: 'Raven/Picasso (Zen APU, fam17h 10-1Fh)',
       0x0820: 'Raven2/Dali (fam17h 20-2Fh)',
       0x0870: 'Matisse (Zen2, fam17h 70-7Fh)',
       0x0860: 'Renoir/Lucienne (Zen2 APU, fam17h 60-6Fh)',
       0x0a20: 'Vermeer (Zen3, fam19h 20-2Fh)',
       0x0a50: 'Cezanne (Zen3 APU, fam19h 50-5Fh)'}
def bcd_date(x):          # AMD ucode date is packed BCD MMDDYYYY
    return f'{x >> 24 & 0xff:02x}/{x >> 16 & 0xff:02x}/{x & 0xffff:04x}'
found = {}
def walk_bhd(off):
    if d[off:off+4] not in (b'$BHD', b'$BL2'): return
    cnt = struct.unpack_from('<I', d, off+8)[0]
    for i in range(cnt):
        t, ri, fl, sz, addr, dest = struct.unpack_from('<BBHIQQ', d, off+0x10+i*24)
        f = fo(addr & 0xffffffff)
        if t == 0x70 and f: walk_bhd(f)
        elif t == 0x66 and f and f+8 <= len(d):
            date, patch = struct.unpack_from('<II', d, f)
            found[patch] = (f, date)
# BHD2 combo
coff = 0xe7800
if d[coff:coff+4] == b'2BHD':
    cnt = struct.unpack_from('<I', d, coff+8)[0]
    for i in range(cnt):
        idsel, idv, addr = struct.unpack_from('<IIQ', d, coff+0x20+i*16)
        f = fo(addr)
        if f: walk_bhd(f)
# per-generation BIOS dirs referenced by the EFS
for a in (0xff240000, 0xff3af000, 0x005df000):
    f = fo(a)
    if f: walk_bhd(f)
print(f'# {len(found)} CPU microcode patches in {sys.argv[1]} (by patch_id):')
for patch in sorted(found):
    f, date = found[patch]
    fam = FAM.get((patch >> 16) & 0xffff, f'unknown ({patch >> 16 & 0xffff:#06x})')
    print(f'  @ {f:#09x}  patch_id={patch:#010x}  date={bcd_date(date)}  {fam}')
fams = sorted({(p >> 16) & 0xffff for p in found})
print(f'# {len(fams)} CPU families covered: {[hex(x) for x in fams]}')
print('# (Summit+Pinnacle share patch group 0x0800 and one PSP dir, so the PSP2 combo lists 6 dirs for these 7 families.)')
