#!/usr/bin/env python3
"""Scan extracted UEFI bodies for ACPI tables (valid length + checksum) and dump them."""
import sys, os, struct, hashlib
root, out = sys.argv[1], sys.argv[2]
SIGS = {b'DSDT', b'SSDT', b'FACP', b'APIC', b'HPET', b'MCFG', b'FACS', b'IVRS', b'BGRT',
        b'FPDT', b'WSMT', b'TPM2', b'CRAT', b'CDIT', b'SRAT', b'SLIC', b'MSDM', b'WDRT', b'UEFI'}
os.makedirs(out, exist_ok=True)
seen = {}
for dp, _, fs in os.walk(root):
    for f in fs:
        if f not in ('body.bin',): continue
        p = os.path.join(dp, f); data = open(p, 'rb').read()
        for sig in SIGS:
            i = data.find(sig)
            while i != -1:
                if i + 36 <= len(data):
                    ln = struct.unpack_from('<I', data, i + 4)[0]
                    if sig == b'FACS':
                        ok = 64 <= ln <= 4096 and i + ln <= len(data)
                    else:
                        ok = 36 <= ln <= 0x100000 and i + ln <= len(data) and sum(data[i:i+ln]) & 0xff == 0
                    if ok:
                        t = data[i:i+ln]; h = hashlib.sha1(t).hexdigest()[:8]
                        if h not in seen:
                            oem = t[16:24].decode('latin1').strip('\0 ') if sig != b'FACS' else ''
                            name = f"{sig.decode()}_{oem or 'x'}_{h}.aml".replace('/', '_')
                            open(os.path.join(out, name), 'wb').write(t)
                            mod = [c for c in p.split('/') if not c[0].isdigit() or ' ' in c]
                            seen[h] = (name, ln, p.split('/')[-3])
                i = data.find(sig, i + 1)
for h, (n, ln, mod) in sorted(seen.items(), key=lambda x: x[1][0]):
    print(f"{n:45s} {ln:7d}  from {mod}")
