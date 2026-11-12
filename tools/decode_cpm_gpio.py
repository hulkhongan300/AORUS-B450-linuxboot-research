#!/usr/bin/env python3
"""Decode the AMD CPM $A10 GPIO-init table into FCH GPIO semantics.
Bit meanings derived from the CPM SetGpio routine (AmdCpmInitPeim FUN_09e17810)."""
import sys, re, struct
d = open(sys.argv[1], 'rb').read()
for m in re.finditer(rb'\$A10', d):          # skip code refs; table has a sane size
    o = m.start(); sz = struct.unpack_from('<H', d, o + 4)[0]
    if 0x20 <= sz <= 0x2000 and o + sz <= len(d): break
print(f'# $A10 GPIO init table @ {o:#x} (size {sz:#x}) from {sys.argv[1]}')
print('# pin    setting  iomux  direction       pull         coreboot-style')
p = o + 16
while p + 4 <= o + sz:
    pin, s = struct.unpack_from('<HH', d, p); p += 4
    if pin == 0xff: break
    mux = (s >> 8) & 7 if s & 0x800 else None
    if s & 0x08: dirn = 'unchanged'
    elif s & 0x02: dirn = 'input'
    elif s & 0x01: dirn = 'output HIGH'
    else: dirn = 'output LOW'
    if s & 0x80:
        pull = 'pull-up' if s & 0x20 else 'pull-down' if s & 0x40 else 'none'
        if s & 0x04: pull += '(PUsel)'
    else: pull = 'unchanged'
    bank = 'remote ' if pin >= 0x100 else ''
    pn = pin & 0xff
    if dirn == 'input': cb = f'PAD_GPI(GPIO_{pn}, {"PULL_UP" if "up" in pull else "PULL_DOWN" if "down" in pull else "PULL_NONE"})'
    elif dirn.startswith('output'): cb = f'PAD_GPO(GPIO_{pn}, {"HIGH" if "HIGH" in dirn else "LOW"})'
    else: cb = f'PAD_NF(GPIO_{pn}, <func {mux}>, {"PULL_NONE" if pull=="none" else pull.upper()})'
    print(f'{bank}{pn:5d}  {s:#08x}  {str(mux):5}  {dirn:14}  {pull:12} {cb}')
