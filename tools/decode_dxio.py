#!/usr/bin/env python3
"""Decode the AMD CPM $A26 DXIO (PCIe/SATA lane) descriptor table. Layout derived from the
OEM patch code in AmdCpmOemInitPeim (records of 0x1A4 bytes starting at +0x14)."""
import sys, re, struct
ENG = {0: 'UNUSED', 1: 'PCIE', 3: 'SATA', 0x10: 'ETHERNET'}
d = open(sys.argv[1], 'rb').read()
for m in re.finditer(rb'\$A26', d):          # skip code refs (push '$A26'); real table is large
    o = m.start(); sz = struct.unpack_from('<H', d, o + 4)[0]
    if 0x1000 <= sz <= 0x4000 and o + sz <= len(d): break
else: raise SystemExit('no $A26 table')
print(f'# $A26 DXIO descriptors @ {o:#x} from {sys.argv[1]}')
for n in range(16):
    r = o + 0x14 + n * 0x1a4
    if r + 0x30 > o + sz: break
    flags, = struct.unpack_from('<I', d, r)
    et, eflags, sl, el = d[r + 4:r + 8]
    gpio_grp, pd0, pd1, pd2 = struct.unpack_from('<IIII', d, r + 8)
    present, dev, fn = pd0 & 1, (pd0 >> 3) & 0x1f, (pd0 >> 8) & 7
    print(f'  [{n}] {ENG.get(et, hex(et)):8} lanes {sl:2}-{el:2} (x{el - sl + 1:<2}) '
          f'present={present} -> 00:{dev:02x}.{fn}  gpio_grp={gpio_grp} pd0={pd0:#x} pd2={pd2:#x} eflags={eflags:#x}'
          + ('  [END]' if flags & 0x80000000 else ''))
    if flags & 0x80000000: break
