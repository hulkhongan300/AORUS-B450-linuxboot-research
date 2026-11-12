#!/usr/bin/env python3
"""Minimal EDK2 PEI PCD database (BuildVersion 7) reader: resolve local token numbers to default values.
CLI:     pei_pcd.py <PcdPeim raw section> <token> [token ...]   (tokens hex or dec)
Library: PcdDb(path).value(tok) -> int | None ; .describe(tok) -> str"""
import sys, struct

TYPES = {0: 'DATA', 1: 'STRING', 4: 'VPD', 8: 'HII'}
DATUM = {0: ('PTR', 0), 1: ('U8', 1), 2: ('U16', 2), 4: ('U32', 4), 8: ('U64', 8)}

class PcdDb:
    def __init__(self, path):
        self.db = db = open(path, 'rb').read()
        (self.lfa, self.uninit, self.ltt, self.exm, self.gt, self.st, self.szt, self.sku, self.pnt) = \
            struct.unpack_from('<9I', db, 0x20)
        self.ltc, self.etc, self.gtc = struct.unpack_from('<HHH', db, 0x44)

    def _entry(self, tok):
        if not 1 <= tok <= self.ltc: raise ValueError(f'token {tok:#x} out of range 1..{self.ltc}')
        e = struct.unpack_from('<I', self.db, self.ltt + 4 * (tok - 1))[0]
        return e & 0x00FFFFFF, (e >> 24) & 0xF, e >> 28

    def value(self, tok):
        """Default value for DATA/HII tokens; 0 for uninitialised DATA; None for VPD/STRING/other."""
        off, dt, ty = self._entry(tok); n = max(DATUM.get(dt, ('?', 1))[1], 1); db = self.db
        if ty == 0: return int.from_bytes(db[off:off + n], 'little') if off < len(db) else 0
        if ty == 8:
            dvo = struct.unpack_from('<6H', db, off)[2]
            return int.from_bytes(db[dvo:dvo + n], 'little') if dvo < len(db) else 0
        return None

    def describe(self, tok):
        off, dt, ty = self._entry(tok); name = DATUM.get(dt, (hex(dt), 1))[0]; v = self.value(tok)
        if ty == 0:
            src = 'uninitialised' if off >= len(self.db) else f'off={off:#06x}'
            return f'DATA {name:3} {src} -> {v:#x}'
        if ty == 8:
            gi, si, dvo, voff, attr, prop = struct.unpack_from('<6H', self.db, off)
            var = self.db[self.st + si:self.st + si + 64].decode('utf-16le', 'ignore').split('\0')[0]
            return f'HII  {name:3} var="{var}" varoff={voff:#x} -> default {v:#x}'
        return f'{TYPES.get(ty, hex(ty))} {name} off={off:#x}'

if __name__ == '__main__':
    p = PcdDb(sys.argv[1])
    print(f'# LocalTokenCount={p.ltc} ExTokenCount={p.etc} GuidTableCount={p.gtc}')
    for t in sys.argv[2:]:
        tok = int(t, 0); print(f'token {tok:#05x}: {p.describe(tok)}')
