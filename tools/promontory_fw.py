#!/usr/bin/env python3
"""Locate (via AMD EFS), verify and carve the Promontory chipset firmware from a full SPI image.
Format confirmed against FchPromontoryXhciPei: '_PT_' | u32 total_size | u32 sum(bytes[12:size]) | payload."""
import sys, struct, os
img = open(sys.argv[1], 'rb').read(); out = sys.argv[2] if len(sys.argv) > 2 else None
base = 0x100000000 - len(img)               # flash is mapped just below 4 GiB
efs = None
for cand in (0xFFFA0000, 0xFFF20000, 0xFFE20000, 0xFFC20000, 0xFF820000, 0xFF020000):
    o = cand - base
    if 0 <= o < len(img) and struct.unpack_from('<I', img, o)[0] == 0x55AA55AA: efs = o; break
if efs is None: raise SystemExit('EFS not found')
print(f'EFS @ flash {efs:#x}')
for field, label in ((0x30, '300-series (xHCI 1022:43b9..43bc)'), (0x34, '400-series (xHCI 1022:43d0..43d8, B450/X470)')):
    ptr = struct.unpack_from('<I', img, efs + field)[0]; o = ptr - base if ptr >= base else ptr
    sig, size, ck = struct.unpack_from('<4sII', img, o)
    calc = sum(img[o + 12:o + size]) & 0xffffffff
    v = img[o + 0x8c:o + 0x92]
    print(f'EFS+{field:#x} -> {ptr:#010x} (flash {o:#x}) {label}\n   sig={sig} size={size:#x} checksum={ck:#x} '
          f'{"OK" if calc == ck else "BAD (calc %#x)" % calc}  version-ish bytes={v.hex(" ")}')
    if out:
        os.makedirs(out, exist_ok=True)
        fn = os.path.join(out, f'promontory_fw_efs{field:02x}.bin'); open(fn, 'wb').write(img[o:o + size]); print('   ->', fn)
