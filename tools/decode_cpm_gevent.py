#!/usr/bin/env python3
"""Decode the AMD CPM $A11 GEVENT/SCI table. Semantics from AmdCpmInitDxe FUN_000055e8; register names match
coreboot soc/amd/*/include/soc/smi.h (SMI block = ACPIMMIO+0x200)."""
import sys, re, struct
d = open(sys.argv[1], 'rb').read()
for m in re.finditer(rb'\$A11', d):
    o = m.start(); sz = struct.unpack_from('<H', d, o + 4)[0]
    if 0x14 <= sz <= 0x400 and o + sz <= len(d): break
else: raise SystemExit('no $A11')
print(f'# $A11 GEVENT/SCI map @ {o:#x} size {sz:#x}  ({sys.argv[1]})')
SMIC = {0: 'off', 1: 'SMI', 2: 'NMI', 3: 'IRQ13'}
p = o + 16
while p + 4 <= o + sz:
    ev, s = struct.unpack_from('<HH', d, p); p += 4
    if ev == 0xff: break
    if ev >= 0x40:
        print(f'  pin {ev:#06x}: raw GPIO reg write {s:#06x} (ACPIMMIO+0x1500+{ev & 0xff}*4)'); continue
    gpe = (s >> 5) & 0x1f
    trig = 'auto(opposite of pin)' if s & 0x400 else ('high/rising' if s & 2 else 'low/falling')
    print(f'  GEVENT{ev:<3d} setting={s:#06x} valid={s & 1} -> GPE {gpe:2d}  trig={trig:21s} '
          f'{"level" if s & 4 else "edge "}  SCI_EN={s >> 3 & 1} bit4={s >> 4 & 1} SMI={SMIC.get(s >> 12, s >> 12)}'
          + (f' SMITRIG={s >> 11 & 1}' if ev < 0x18 else ''))
