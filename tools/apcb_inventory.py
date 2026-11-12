#!/usr/bin/env python3
"""Structural inventory of AMD APCB v3 blocks (reference only).
APCB header 0x20B: 'APCB' u16 hdr, u16 ver, u32 size.
Then GROUP headers: u32 magic('xxxG'), u16 group_id, u16 hdr_size(0x10), u32 version, u32 group_size.
Inside a group, ENTRY headers: u16 group_id, u16 type_id, u32 entry_size, u32 flags, then data."""
import sys, struct, re
d=open(sys.argv[1],'rb').read()
GROUPS={0x1701:'PSP',0x1702:'CCX',0x1703:'DF',0x1704:'MEM',0x1705:'GNB',0x1706:'FCH',0x1707:'CBS',0x3000:'TOKEN'}
def inv(o):
    if d[o:o+4]!=b'APCB': return None
    hdr,ver=struct.unpack_from('<HH',d,o+4); size=struct.unpack_from('<I',d,o+8)[0]
    out=[f'APCB @ {o:#x} ver={ver:#x} size={size:#x}']
    p=o+hdr; end=o+size
    while p+0x10<=end:
        magic=d[p:p+4]; gid=struct.unpack_from('<H',d,p+4)[0]; gsz=struct.unpack_from('<I',d,p+12)[0]
        if gid not in GROUPS or gsz<0x10 or p+gsz>end: break
        # walk entries
        q=p+0x10; ents=[]
        while q+0x10<=p+gsz:
            egid,tid=struct.unpack_from('<HH',d,q); esz=struct.unpack_from('<I',d,q+4)[0]
            if egid!=gid or esz<0x10 or q+esz>p+gsz: break
            ents.append((tid,esz)); q+=((esz+3)&~3)
        big=max((e[1] for e in ents),default=0)
        out.append(f'  {magic.decode("latin1")} {GROUPS[gid]:5} (gid {gid:#06x}): {len(ents)} entries, '
                   f'types={sorted(set(hex(t) for t,_ in ents))}, max_entry={big:#x}')
        p+=((gsz+3)&~3)
    return '\n'.join(out)
seen=set()
for m in re.finditer(b'APCB', d):
    o=m.start(); region=o&~0xfffff
    if region in seen: continue
    r=inv(o)
    if r and 'entries' in r: seen.add(region); print(r); print()
