#!/usr/bin/env python3
"""Decode AMD CPM board tables ($Axx) found in AmdCpmOemInitPeim (formats derived from AmdCpmGpioInitPeim code)."""
import sys, re, struct
d = open(sys.argv[1], 'rb').read()
def tables():
    for m in re.finditer(rb'\$A[0-9A-F]{2}', d):
        o = m.start(); sz = struct.unpack_from('<H', d, o + 4)[0]
        if 16 <= sz <= 0x4000 and o + sz <= len(d):
            yield m.group().decode(), o, sz
TYPE = {0: 'SET_GPIO', 1: 'WAIT_GPIO', 2: 'DELAY_us', 3: 'DEFERRED'}
def seq(name, o, sz, kind):
    print(f'\n## {name} @ {o:#x} size={sz:#x} platmask={struct.unpack_from("<I", d, o+8)[0]:#x}')
    p = o + 16
    while p + 8 <= o + sz:
        dev, a, b = d[p], d[p+1], d[p+2]
        if dev in (0, 0xff): break
        pin, val = struct.unpack_from('<HB', d, p + 3)
        if kind == 'power':
            t = TYPE.get(b, b)
            arg = f'{struct.unpack_from("<I", d, p+3)[0]} us' if b == 2 else f'pin={pin:#06x} val={val}'
            print(f'  dev={dev:#04x} mode={a} {t:9} {arg}')
        else:
            print(f'  dev={dev:#04x} {"deassert" if a else "assert  "} pin={pin:#06x} val={val} (b2={b})')
        p += 8
for sig, o, sz in tables():
    if sig == '$A13': seq('$A13 device POWER sequence', o, sz, 'power')
    elif sig == '$A15': seq('$A15 device RESET sequence', o, sz, 'reset')
