#!/usr/bin/env python3
"""Usage: decode_pt_phy_defaults.py FchTaishanPei_1.efi [PeiPcdDb.bin]
Dump the Promontory PHY-tuning defaults from FchTaishanPei's static FCH reset-data table.
Promontory config offset X == table offset 0x7B + X (FchTaishanPei publishes table+0x7B as PPI field +8).
Register mapping follows FchPromontoryCbsPei FUN_09cab9ef (400-series path)."""
import sys
pe = open(sys.argv[1], 'rb').read()
BASE, TABLE, SIZE = 0x09cbba80, 0x09cbf790, 0x296
t = pe[TABLE - BASE:TABLE - BASE + SIZE]
c = lambda x: t[0x7b + x]
PCD_TOK = [0x233,0x182,0x184,0x1f4,0xa0,0x128,0xaa,0x1a4,0xb5,0x2d2,0x8a,0x1f8,     # cfg +0xBB..+0xC6
           0x331,0x143,0x2a5,0x227,0x2da,0x322,0x1c7,0x193,0x3d,0x2de,0x175,0x243]   # cfg +0xC7..+0xD2
pcd = {}
if len(sys.argv) > 2:
    import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from pei_pcd import PcdDb
    db = PcdDb(sys.argv[2])
    pcd = {0xbb + i: db.value(tok) or 0 for i, tok in enumerate(PCD_TOK)}
print('# Promontory PHY defaults (static FCH table' + (' + PEI PCD DB' if pcd else '; PCD fields +0xBB..+0xD2 not shown') + ')')
for b, blk in enumerate(('0x9', '0xA')):
    o = 0x95 + 10 * b
    f = [c(o + i) for i in range(10)]
    print(f'USB3 block {blk}xxx  raw +{o:#x}: {" ".join(f"{v:02x}" for v in f)}')
    print(f'   {blk}450[7:4]={f[0]:#x}  {blk}460[7:4]={f[1]:#x}  '
          f'{blk}459=({f[2]:#x}<<4)|{f[4] & 0xf:#x}  {blk}469=({f[3]:#x}<<4)|{f[5] & 0xf:#x}  '
          f'{blk}450[6:3|2:0]=({f[6]:#x}<<3)|{f[8] & 7:#x}  {blk}460=({f[7]:#x}<<3)|{f[9] & 7:#x}')
USB2 = ['0xB450', '0xB490', '0xC450', '0xC490', '0xD450', '0xD490']
for p in range(6):
    o = 0xa9 + 3 * p; a, bb, cc = c(o), c(o + 1), c(o + 2)
    r2 = USB2[p][:-1] + '9'
    print(f'USB2 port {p}  raw +{o:#x}: {a:02x} {bb:02x} {cc:02x}   {USB2[p]}[7:4]={a:#x}  {r2}=({bb:#x}<<4)|{cc & 0xf:#x}')
if pcd:
    g = lambda x: pcd[x]
    for i, blk in enumerate(('0xA', '0xB', '0xC', '0xD')):
        p0, p1, p2 = g(0xbb + 3 * i), g(0xbc + 3 * i), g(0xbd + 3 * i); pc, pd, pe_ = g(0xc7 + 3 * i), g(0xc8 + 3 * i), g(0xc9 + 3 * i)
        r0 = ((p1 & 7) << 2 | p0 & 3) & 0xff; r1 = ((((pc & 3) | pd << 2) << 2 | p2 & 3) << 2) & 0xff; r2 = (pe_ << 6 | (pd >> 2) & 1) & 0xff
        print(f'common {blk}598: fields {p0},{p1},{p2},{pc},{pd},{pe_} -> {blk}598=(cur&E0)|{r0:#04x} {blk}599=(cur&03)|{r1:#04x} {blk}59A=(cur&3E)|{r2:#04x}')
print('PCIe/SATA lanes (mbox 0x2EFE=lane, then 0x2F22..0x2F25)')
for n in range(8):
    o = 0xd3 + 9 * n; p = [c(o + i) for i in range(9)]
    r22 = (p[6] << 4 | p[0] & 0xf) & 0xff; r23 = (p[1] & 0xf | p[7] << 4) & 0xff; r24 = (p[2] & 0xf | p[8] << 4) & 0xff
    r25 = ((p[5] * 2 | p[4]) * 2 | p[3]) & 0xff
    print(f'  lane {n}: raw {" ".join(f"{v:02x}" for v in p)}  -> 2F22={r22:#04x} 2F23={r23:#04x} 2F24={r24:#04x} 2F25|={r25:#04x} (low 3 bits)')
print('Other Promontory fields of interest:')
for name, off in (('root-port index (+0x22)', 0x22), ('switch present (+0x23)', 0x23), ('xHCI DID (+0x26, u32)', 0x26)):
    v = int.from_bytes(t[0x7b + off:0x7b + off + (4 if 'u32' in name else 1)], 'little'); print(f'  {name}: {v:#x}')
