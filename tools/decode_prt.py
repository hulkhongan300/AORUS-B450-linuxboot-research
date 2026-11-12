#!/usr/bin/env python3
"""Decode ACPI _PRT routing packages from an iasl-disassembled DSDT.
Shows the APIC-mode GSI each PCI device/INTx maps to. For AMD FCH, GSIs >= 0x18 (24) are the
8 PCI IRQ lines routed through the FCH IO-APIC; the low nibble is the FCH 'PCI IRQ' index."""
import sys, re
txt = open(sys.argv[1]).read()
# Collect every "Name (XXnn, Package ...) { ... }" block that holds 4-element routing packages.
pkgs = {}
for m in re.finditer(r'Name \((\w{4}), Package \(0x[0-9A-Fa-f]+\)\s*\n\s*\{(.*?)\n\s*\}\n', txt, re.S):
    name, body = m.group(1), m.group(2)
    rows = re.findall(r'Package \(0x04\)\s*\{\s*([0-9A-Fx]+),\s*(\w+),\s*(\w+),\s*([0-9A-Fx]+)\s*\}', body, re.S)
    if rows:
        pkgs[name] = rows
def val(x):
    if x in ('Zero','One','Two'): return {'Zero':0,'One':1,'Two':2}[x]
    return int(x,16) if x.lower().startswith('0x') else int(x)
# Which packages are APIC-mode: those returned under If(PICM)/If(APIC). Heuristic: 'AR'/'AP' prefix.
apic = {k:v for k,v in pkgs.items() if re.match(r'A[RP]', k)}
print(f"# {sys.argv[1]}: {len(apic)} APIC-mode _PRT packages")
INTX='ABCD'
for name in sorted(apic):
    rows = apic[name]
    out=[]
    for adr,pin,src,gsi in rows:
        dev=(val(adr)>>16)&0xffff
        g=val(gsi)
        out.append(f"{dev:02X}.{INTX[val(pin)&3]}->{g}")
    # compress
    print(f"{name}: " + "  ".join(out))
