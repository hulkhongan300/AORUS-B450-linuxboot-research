#!/usr/bin/env python3
"""Decode the SIO register tables used by Gigabyte's IT8728FPeiInit (PE converted from TE)."""
import sys, struct
pe = open(sys.argv[1], 'rb').read()
BASE = 0x09dfca8c          # ImageBase as loaded by Ghidra
def at(va, n): o = va - BASE; return pe[o:o + n]
CHIP = {0: 'IT8728', 1: 'IT8620', 2: 'IT8609', 3: 'IT8628', 4: 'IT8686', 5: 'IT8688', 6: 'IT8689'}
print('# LPC decode requests {u16 port, u8 size, u8 ?, u32 kind}  (kind 0xff = generic/wide IO, 6=COM, 7=LPT)')
for i in range(5):
    port, sz, x, kind = struct.unpack('<HBBI', at(0x9dfd57c + 8 * i, 8))
    print(f'  port={port:#06x} size={sz:#x} kind={kind:#x}')
TABLES = [(0x9dfd60c, 0x72, 'common (all chips)'), (0x9dfd50c, 10, 'IT8620 only'),
          (0x9dfd5ec, 6, 'IT8728 only'), (0x9dfd5bc, 10, 'IT8628 only'),
          (0x9dfd3ec, 0x18, 'IT8686/88/89'), (0x9dfd3cc, 8, 'IT8688 extra'),
          (0x9dfd53c, 0x10, 'IT8689 extra'), (0x9dfd5ac, 4, 'common tail'), (0x9dfd44c, 0x30, 'common tail 2')]
for va, n, name in TABLES:
    print(f'\n# table @ {va:#x} ({n} writes) - {name}')
    reg = None
    for i in range(n):
        port, mask, val = struct.unpack('<HBB', at(va + 4 * i, 4))
        op = f'= {val:#04x}' if mask == 0 else f'= (cur & {mask:#04x}) | {val:#04x}'
        note = ''
        if port == 0x2e: reg = val; note = '  ; select reg'
        elif port == 0x2f and reg == 0x07: note = f'  ; LDN {val}'
        elif port == 0x2f: note = f'  ; CR{reg:02X}'
        print(f'  out({port:#06x}) {op}{note}')
