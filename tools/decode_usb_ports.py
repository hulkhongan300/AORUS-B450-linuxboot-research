#!/usr/bin/env python3
"""Decode the USB port map (_UPC connector type + _PLD panel location) from an iasl DSDT.
Anchors on each _UPC: the owning port Device is the nearest preceding `Device (X)` whose `{`
has not yet closed, and _ADR/_PLD are taken from that same block. Usage: decode_usb_ports.py <dsdt.dsl>"""
import sys, re
lines = open(sys.argv[1]).read().splitlines()
UPC = {0x00: 'Type-A (USB2)', 0x03: 'USB3 Std-A', 0x04: 'USB3 Std-B', 0x06: 'USB3 Micro-AB',
       0x08: 'Type-C USB2', 0x09: 'Type-C USB3+sw', 0x0A: 'Type-C USB3', 0xFF: 'proprietary/internal'}
def num(x):
    x = x.strip()
    return {'Zero': 0, 'One': 1, 'Two': 2}.get(x, int(x, 16) if x.lower().startswith('0x') else int(x))

# Build a device stack by brace depth so each _UPC maps to its enclosing Device.
ports, stack = [], []   # stack of [name, adr, depth]
depth = 0
cur = None
for i, ln in enumerate(lines):
    dm = re.search(r'Device \((\w+)\)', ln)
    if dm:
        cur = {'name': dm.group(1), 'depth': depth, 'adr': '?', 'upc': None,
               'panel': None, 'vis': None, 'open': False}
        stack.append(cur)
    depth += ln.count('{') - ln.count('}')
    for d in stack:
        if depth > d['depth']:
            d['open'] = True
    # pop devices whose block has opened and then closed
    while stack and stack[-1]['open'] and depth <= stack[-1]['depth']:
        d = stack.pop()
        if d['upc'] is not None:
            conn, typ = d['upc']
            loc = 'internal/header' if d['vis'] == 0 else (d['panel'] or '?')
            ports.append((d['name'], d['adr'], UPC.get(typ, hex(typ)),
                          'connectable' if conn == 0xFF else 'hardwired', loc))
    top = stack[-1] if stack else None
    if top is None:
        continue
    am = re.search(r'Name \(_ADR, (0x[0-9A-Fa-f]+|Zero|One|Two)\)', ln)
    if am and top['adr'] == '?':
        top['adr'] = am.group(1)
    if '_UPC' in ln and top['upc'] is None:
        # _UPC package spans the next few lines: grab first two scalars
        blob = ' '.join(lines[i:i+6])
        um = re.search(r'_UPC.*?\{\s*(0x[0-9A-Fa-f]+|Zero|One)\s*,\s*(0x[0-9A-Fa-f]+|Zero|One|Two)', blob)
        if um:
            top['upc'] = (num(um.group(1)), num(um.group(2)))
    if 'PLD_Panel' in ln and top['panel'] is None:
        pm = re.search(r'PLD_Panel\s*=\s*"(\w+)"', ln)
        blob = ' '.join(lines[i:i+4])
        vm = re.search(r'PLD_VerticalPosition\s*=\s*"(\w+)"', blob)
        hm = re.search(r'PLD_HorizontalPosition\s*=\s*"(\w+)"', blob)
        if pm:
            top['panel'] = f"{pm.group(1)}/{vm.group(1) if vm else '?'}/{hm.group(1) if hm else '?'}"
    if 'PLD_UserVisible' in ln and top['vis'] is None:
        vm = re.search(r'PLD_UserVisible\s*=\s*(0x[0-9A-Fa-f]+)', ln)
        if vm:
            top['vis'] = num(vm.group(1))

print(f'# USB port map from {sys.argv[1]}: {len(ports)} port objects with _UPC')
print(f'# {"dev":6} {"_ADR":12} {"connector":16} {"state":12} panel/Vpos/Hpos')
for name, adr, conn, st, loc in ports:
    print(f'  {name:6} {adr:12} {conn:16} {st:12} {loc}')
