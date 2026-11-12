#!/usr/bin/env python3
"""Convert a UEFI TE (Terse Executable) image back into a loadable PE32/PE32+ file."""
import sys, struct
src, dst = sys.argv[1], sys.argv[2]
te = open(src, 'rb').read()
assert te[:2] == b'VZ', 'not a TE image'
mach, nsec, subsys, stripped, entry, boc, base = struct.unpack_from('<HBBHIIQ', te, 2)
reloc_rva, reloc_sz, dbg_rva, dbg_sz = struct.unpack_from('<IIII', te, 24)
secs = te[40:40 + 40 * nsec]
body = te[40:]                       # section headers + data; lands at file offset `stripped`
is64 = mach in (0x8664, 0xAA64)
ndirs = 16
opt_sz = (112 if is64 else 96) + 8 * ndirs
hdr_needed = 0x40 + 4 + 20 + opt_sz  # minimum: DOS hdr + PE sig + COFF + opt
if hdr_needed > stripped:
    raise SystemExit(f'stripped size {stripped:#x} too small for header {hdr_needed:#x}')
# image size / alignment from sections
end = 0; vas = []
fixed = bytearray(secs)
for i in range(nsec):
    o = i * 40
    vs, va, rs, rp = struct.unpack_from('<IIII', secs, o + 8)
    end = max(end, va + max(vs, rs)); vas.append(va)
align = 0x20
for a in (0x1000, 0x200, 0x80, 0x40, 0x20):
    if all(v % a == 0 for v in vas) and stripped % min(a, 0x200) == 0:
        align = a; break
size_img = (end + align - 1) // align * align
dirs = [(0, 0)] * ndirs
dirs[5] = (reloc_rva, reloc_sz); dirs[6] = (dbg_rva, dbg_sz)
lfanew = stripped - 24 - opt_sz          # section table must directly follow optional header
dos = bytearray(lfanew); dos[0:2] = b'MZ'; struct.pack_into('<I', dos, 0x3c, lfanew)
chars = 0x0002 | (0x0020 if is64 else 0x0100) | (0 if reloc_sz else 0x0001)
coff = struct.pack('<HHIIIHH', mach, nsec, 0, 0, 0, opt_sz, chars)
if is64:
    opt = struct.pack('<HBBIIIIIQIIHHHHHHIIIIHHQQQQII', 0x20b, 0, 0, 0, 0, 0, entry, boc, base,
                      align, align, 0, 0, 0, 0, 0, 0, 0, size_img, stripped, 0, subsys, 0,
                      0, 0, 0, 0, 0, ndirs)
else:
    opt = struct.pack('<HBBIIIIIIIIIHHHHHHIIIIHHIIIIII', 0x10b, 0, 0, 0, 0, 0, entry, boc, 0,
                      base & 0xffffffff, align, align, 0, 0, 0, 0, 0, 0, 0, size_img, stripped,
                      0, subsys, 0, 0, 0, 0, 0, 0, ndirs)
opt += b''.join(struct.pack('<II', *d) for d in dirs)
hdr = bytes(dos) + b'PE\0\0' + coff + opt
assert len(hdr) == stripped
open(dst, 'wb').write(hdr + body)
print(f'{dst}: mach={mach:#x} base={base:#x} entry={entry:#x} stripped={stripped:#x} align={align:#x}')
