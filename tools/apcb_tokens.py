#!/usr/bin/env python3
"""Decode AMD APCB TOKEN group entries into (token_id, value).
Token entry type_id: 0=bool, 1=byte, 2=word, 4=dword. Each token record is u32 token_id + value,
padded to an 8-byte stride. Usage: apcb_tokens.py <image> <apcb_flash_offset>"""
import sys, struct
d = open(sys.argv[1], 'rb').read()
o = int(sys.argv[2], 0)
hdr = 0x20
size = struct.unpack_from('<I', d, o + 8)[0]
end = o + size
TYW = {0: (1, 'bool'), 1: (1, 'byte'), 2: (2, 'word'), 4: (4, 'dword')}
p = o + hdr
result = []
while p + 0x10 <= end:
    magic = d[p:p + 4]
    gsz = struct.unpack_from('<I', d, p + 12)[0]
    if gsz < 0x10 or p + gsz > end:
        break
    if magic == b'TOKN':
        q = p + 0x10
        while q + 0x10 <= p + gsz:
            tid = struct.unpack_from('<H', d, q + 2)[0]
            esz = struct.unpack_from('<I', d, q + 4)[0]
            if esz < 0x10 or q + esz > p + gsz:
                break
            w, label = TYW.get(tid, (4, '?'))
            r = q + 0x10
            toks = []
            while r + 8 <= q + esz:
                tkid = struct.unpack_from('<I', d, r)[0]
                if tkid == 0xffffffff:
                    break
                val = int.from_bytes(d[r + 4:r + 4 + w], 'little')
                toks.append((tkid, val))
                r += 8
            result.append((label, toks))
            q += (esz + 3) & ~3          # advance past this entry
        break
    p += (gsz + 3) & ~3
for label, toks in result:
    print(f'# TOKEN {label}: {len(toks)} tokens')
    for tk, v in toks:
        print(f'  {tk:#010x} = {v:#x}')
