#!/usr/bin/env python3
"""check_readiness.py - turn collect.sh reports into a tinylinux / LinuxBoot readiness checklist.

usage:
  check_readiness.py LIVE_REPORT [--tinylinux TINYBOOT_REPORT] [--kconfig FILE] [--ksrc DIR] [--out FILE]

LIVE_REPORT      directory written by `collect.sh` on the installed OS (ideally run with sudo)
--tinylinux DIR   directory written by `collect.sh` inside the tinylinux USB shell (optional; the
                 real proof that tinylinux's kernel drives this hardware)
--kconfig FILE   tinylinux kernel .config        (default: ../tinylinux/out/kernel-build/.config)
--ksrc DIR       kernel source used for tinylinux (default: ../toolchain/src/linux-6.18.60)
--out FILE       report path                    (default: LIVE_REPORT/READINESS.md)

Read-only analysis: it writes only the report and, if it can, suggested BootLoaderSpec entries
(LIVE_REPORT/suggested_bls/*.conf) for you to review. It installs nothing.
"""
import argparse, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANALYSED_IMAGE = "F67c"                      # BIOS file all static analysis in this project used
PROMONTORY_IDS = {"1022:43d5": "Promontory xHCI", "1022:43c8": "Promontory SATA", "1022:43c6": "Promontory bridge"}
X86_64_V3 = ["avx", "avx2", "bmi1", "bmi2", "fma", "f16c", "movbe", "abm", "xsave"]
REQUIRED_CLASSES = {"0x0106": "SATA controller", "0x0108": "NVMe controller", "0x0c03": "USB controller"}
INFO_CLASSES = {"0x02": "network (tinylinux has no networking - not needed to boot from disk)",
                "0x03": "display (tinylinux draws on the UEFI GOP framebuffer - GPU driver not needed)",
                "0x04": "audio/multimedia (not needed)", "0x06": "bridge (enumerated without a driver)",
                "0x08": "system peripheral (not needed)", "0x10": "crypto/PSP interface (not needed)",
                "0x11": "signal processing (not needed)", "0x13": "non-essential instrumentation"}
ESP_GUID = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"
TINYBOOT_FS = {"vfat"}
KNOWN_HARMLESS = [r"genetlink family for ACPI event"]   # side effects of tinylinux's trimmed config                       # filesystems tinylinux can read kernels from

checks = []          # (area, status, item, detail)
def add(area, status, item, detail=""): checks.append((area, status, item, detail))

def read(d, name):
    p = Path(d) / name
    try: return p.read_text(errors="replace")
    except OSError: return ""

def kvfile(d, name):
    out = {}
    for line in read(d, name).splitlines():
        if "=" in line:
            k, v = line.split("=", 1); out[k.strip()] = v.strip()
    return out

def tsv(d, name):
    lines = read(d, name).splitlines()
    if not lines: return []
    hdr = lines[0].split("\t")
    return [dict(zip(hdr, l.split("\t"))) for l in lines[1:] if l.strip()]

def kconfig(path):
    cfg = {}
    for line in Path(path).read_text().splitlines():
        m = re.match(r"(CONFIG_\w+)=(.*)", line)
        if m: cfg[m.group(1)] = m.group(2).strip('"')
    return cfg

def module_map(ksrc):
    """object/module name -> {CONFIG_*} from obj-$(CONFIG_X) += name.o lines in kernel Makefiles."""
    mm = {}
    for top in ("drivers", "sound", "fs"):
        for mk in Path(ksrc, top).rglob("Makefile"):
            text = mk.read_text(errors="replace").replace("\\\n", " ")
            for m in re.finditer(r"obj-\$\((CONFIG_\w+)\)\s*[+:]?=\s*([^\n]*)", text):
                for tok in m.group(2).split():
                    if tok.endswith(".o"):
                        mm.setdefault(tok[:-2].replace("-", "_"), set()).add(m.group(1))
    return mm

def pci_parent(syspath):
    """PCI function that owns a block device: last dddd:bb:dd.f component before the bus-specific part."""
    found = re.findall(r"/([0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f])(?=/)", syspath or "")
    return found[-1] if found else None

def transport(syspath):
    s = syspath or ""
    if "/nvme" in s: return "nvme"
    if "/usb" in s: return "usb"
    if "/ata" in s: return "sata"
    if "/virtual/" in s: return "virtual"
    return "?"

# ------------------------------------------------------------------------------------------------
def check_platform(live):
    dmi, cpu = kvfile(live, "dmi.txt"), read(live, "cpu.txt")
    board = dmi.get("board_name", "?"); bios = dmi.get("bios_version", "?")
    add("Platform", "PASS" if "B450 AORUS PRO" in board else "WARN", f"Board: {board}",
        "matches the board this project analysed" if "B450 AORUS PRO" in board else "not the analysed board")
    if bios == ANALYSED_IMAGE:
        add("Platform", "PASS", f"BIOS version {bios}", "same version as the analysed image")
    else:
        add("Platform", "WARN", f"BIOS version {bios} (analysed image: {ANALYSED_IMAGE})",
            "offsets/sizes in analysis/ are from F67c; any in-flash work must use the version actually on the board")
    vendor = re.search(r"vendor_id\s*:\s*(\S+)", cpu); model = re.search(r"model name\s*:\s*(.+)", cpu)
    flags = set((re.search(r"^flags\s*:\s*(.+)$", cpu, re.M) or [None, ""])[1].split())
    v = vendor.group(1) if vendor else "?"
    add("Platform", "PASS" if v == "AuthenticAMD" else "FAIL", f"CPU: {model.group(1).strip() if model else '?'}",
        "tinylinux is built AMD-only (CPU_SUP_INTEL off)" if v == "AuthenticAMD" else "tinylinux is AMD-only - rebuild with CPU_SUP_INTEL")
    missing = [f for f in X86_64_V3 if f not in flags]
    add("Platform", "PASS" if not missing else "WARN", "CPU supports x86-64-v3",
        "CachyOS kernels need it" if not missing else f"missing {missing}: CachyOS v3 kernels would not boot")
    mem = re.search(r"MemTotal:\s+(\d+)", read(live, "meminfo.txt"))
    if mem: add("Platform", "INFO", f"RAM {int(mem.group(1))/1048576:.1f} GiB")

def check_firmware(live):
    efi = kvfile(live, "efi.txt")
    add("Firmware", "PASS" if efi.get("efi") == "present" else "FAIL", "Booted in UEFI mode",
        "tinylinux is an EFI application" if efi.get("efi") == "present" else "machine booted legacy/CSM - tinylinux needs UEFI boot")
    if "fw_platform_size" in read(live, "efi.txt"):
        add("Firmware", "PASS" if ": 64" in read(live, "efi.txt") else "FAIL", "64-bit UEFI")
    sb = efi.get("SecureBoot")
    if sb is None:
        add("Firmware", "TODO", "Secure Boot state unknown", "run collect.sh on the installed OS (needs od + efivars)")
    else:
        add("Firmware", "PASS" if sb == "0" else "FAIL", f"Secure Boot {'off' if sb == '0' else 'ON'}",
            "unsigned tinylinux.efi will be accepted" if sb == "0" else "disable it in Setup or sign tinylinux.efi with your own enrolled key")
    if efi.get("SetupMode") == "1":
        add("Firmware", "INFO", "Secure Boot keys not enrolled (Setup Mode)")
    if "runtime_map=present" in read(live, "efi.txt"):
        add("Firmware", "PASS", "UEFI runtime map exported", "kexec can hand UEFI runtime to the next kernel")
    esrt = re.findall(r"fw_version: (\d+)", read(live, "efi.txt"))
    if esrt: add("Firmware", "INFO", f"ESRT firmware version {esrt[0]}")

def same_machine(live, tb):
    """tinylinux has no DMI support, so compare the sets of PCI vendor:device IDs (Jaccard >= 0.8)."""
    ids = lambda d: {(r["vendor"], r["device"]) for r in tsv(d, "pci.tsv")}
    a, b = ids(live), ids(tb)
    j = len(a & b) / len(a | b) if a | b else 0
    return j >= 0.8, j

def check_pci(live, tb, cfg, mm):
    rows = tsv(live, "pci.tsv")
    if not rows:
        add("Drivers", "FAIL", "pci.tsv missing"); return {}
    tb_rows = {r["slot"]: r for r in tsv(tb, "pci.tsv")} if tb and same_machine(live, tb)[0] else {}
    ids = {f'{r["vendor"][2:]}:{r["device"][2:]}' for r in rows}
    for pid, name in PROMONTORY_IDS.items():
        add("Drivers", "PASS" if pid in ids else "WARN", f"{name} {pid} present", "matches analysis/" if pid in ids else "expected on this board")
    by_slot = {}
    for r in rows:
        by_slot[r["slot"]] = r
        cls = r["class"][:6]; pid = f'{r["vendor"][2:]}:{r["device"][2:]}'
        label = REQUIRED_CLASSES.get(cls)
        if not label:
            info = INFO_CLASSES.get(r["class"][:4])
            if info and r["driver"] != "-" and r["class"][:4] in ("0x02", "0x03"):
                add("Drivers", "INFO", f'{r["slot"]} {pid} {r["driver"]}', info)
            continue
        names = [n.replace("-", "_") for n in (r["module"], r["driver"]) if n and n != "-"]
        if not names:
            add("Drivers", "WARN", f'{r["slot"]} {pid} {label}', "no driver bound on the installed OS either"); continue
        syms = set().union(*[mm.get(n, set()) for n in names])
        on = sorted(s for s in syms if cfg.get(s) == "y")
        if on:
            add("Drivers", "PASS", f'{r["slot"]} {pid} {label} ({names[0]})', "built into tinylinux: " + ", ".join(on))
        elif syms:
            add("Drivers", "FAIL", f'{r["slot"]} {pid} {label} ({names[0]})', "NOT in tinylinux: enable " + ", ".join(sorted(syms)))
        else:
            add("Drivers", "WARN", f'{r["slot"]} {pid} {label} ({names[0]})', "driver not found in kernel Makefiles - check manually")
        if tb_rows:
            t = tb_rows.get(r["slot"])
            if t is None: add("tinylinux run", "FAIL", f'{r["slot"]} {label} not visible under tinylinux')
            elif t["driver"] == "-": add("tinylinux run", "FAIL", f'{r["slot"]} {label}: no driver bound under tinylinux')
            else: add("tinylinux run", "PASS", f'{r["slot"]} {label}: driven by {t["driver"]} under tinylinux')
    return by_slot

def check_storage(live, pci_by_slot):
    blocks = {b["name"]: b for b in tsv(live, "block.tsv")}
    lsblk = read(live, "lsblk.json")
    parts = []
    if lsblk:
        def walk(n, disk=None):
            disk = disk or (n["name"] if n.get("type") == "disk" else None)
            parts.append((n, disk))
            for c in n.get("children") or []: walk(c, disk)
        for n in json.loads(lsblk)["blockdevices"]: walk(n)
    esp = [(n, d) for n, d in parts if (n.get("parttype") or "").lower() == ESP_GUID]
    for n, d in esp:
        tr = transport(blocks.get(d, {}).get("syspath", ""))
        ctrl = pci_parent(blocks.get(d, {}).get("syspath", ""))
        drv = pci_by_slot.get(ctrl, {}).get("driver", "?") if ctrl else "?"
        add("Boot path", "INFO", f'EFI system partition {n["name"]} ({n.get("fstype")}, {n.get("size")}) on {d} [{tr}]',
            f"controller {ctrl} driver {drv}; mounted at {', '.join(m for m in n.get('mountpoints') or [] if m) or '-'}")
    boot = [(n, d) for n, d in parts if "/boot" in (n.get("mountpoints") or [])]
    if boot:
        n, d = boot[0]
        fs = n.get("fstype")
        add("Boot path", "PASS" if fs in TINYBOOT_FS else "FAIL", f"/boot is {n['name']} ({fs}) on {d}",
            "tinylinux can read the kernels there" if fs in TINYBOOT_FS else f"tinylinux reads only {TINYBOOT_FS}: add that filesystem to kernel.fragment or move kernels to the ESP")
    elif parts:
        root = [(n, d) for n, d in parts if "/" in (n.get("mountpoints") or [])]
        fs = root[0][0].get("fstype") if root else "?"
        add("Boot path", "FAIL" if fs not in TINYBOOT_FS else "PASS", f"/boot is on the root filesystem ({fs})",
            "tinylinux cannot read it - kernels must be on a FAT partition (or add the fs to tinylinux)")
    else:
        add("Boot path", "TODO", "storage layout unknown (no lsblk output)")

def parse_files(text):
    files, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"##### (ROOT|LIST|FILE) (.+)", line)
        if m:
            cur = m.group(2) if m.group(1) == "FILE" else None
            if cur: files[cur] = []
            continue
        if cur: files[cur].append(line)
    return {k: "\n".join(v) for k, v in files.items()}

def limine_entries(text):
    """Parse Limine (v8+ and older) config into [{title, kernel, initrds, cmdline}]."""
    out, cur = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"): continue
        m = re.match(r"^/+\+?(.*)$", line)
        if m:
            cur = {"title": m.group(1).strip(), "kernel": None, "initrds": [], "cmdline": "", "protocol": ""}
            out.append(cur); continue
        if cur is None or ":" not in line: continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "protocol": cur["protocol"] = v.lower()
        elif k in ("path", "kernel_path"): cur["kernel"] = v
        elif k in ("module_path",): cur["initrds"].append(v)
        elif k in ("cmdline", "kernel_cmdline"): cur["cmdline"] = v
    return [e for e in out if e["kernel"] and e["protocol"] in ("linux", "")]

def limine_path(p):
    m = re.match(r"^(boot|uuid|guid|fslabel)\(([^)]*)\):(.*)$", p)
    if not m: return p, None
    return m.group(3), (None if m.group(1) == "boot" else f"{m.group(1)}({m.group(2)})")

def check_boot_entries(live, outdir):
    text = read(live, "boot_files.txt")
    if "/boot': Permission denied" in text or "cannot open directory '/boot'" in text:
        add("Boot entries", "TODO", "/boot not readable", "rerun with sudo to list kernels and read limine.conf")
        return
    files = parse_files(text)
    bls = {k: v for k, v in files.items() if "/loader/entries/" in k}
    kernels = sorted(set(re.findall(r"\s((?:vmlinuz|bzImage)[^\s/]*)$", text, re.M)))
    if kernels: add("Boot entries", "INFO", "kernels found: " + ", ".join(kernels))
    if bls:
        for k in bls: add("Boot entries", "PASS", f"BootLoaderSpec entry {k}", "tinylinux will list it")
        return
    lim = {k: v for k, v in files.items() if k.endswith("limine.conf")}
    if not lim:
        add("Boot entries", "FAIL", "no BootLoaderSpec entries and no limine.conf found",
            "tinylinux's menu will be empty; boot by hand from its shell with kexec-boot")
        return
    sugg = Path(outdir) / "suggested_bls"; sugg.mkdir(exist_ok=True)
    n = 0
    for path, conf in lim.items():
        root = path.rsplit("/limine", 1)[0].rsplit("/EFI", 1)[0].rsplit("/boot", 1)[0] or "/boot"
        for e in limine_entries(conf):
            kpath, other = limine_path(e["kernel"])
            ipaths = [limine_path(i)[0] for i in e["initrds"]]
            if other:
                add("Boot entries", "WARN", f'Limine entry "{e["title"]}" uses {other}', "kernel on another partition - check by hand"); continue
            n += 1
            name = re.sub(r"[^A-Za-z0-9._-]+", "-", e["title"]).strip("-").lower() or f"entry{n}"
            body = [f"title   {e['title']}", f"linux   {kpath}"] + [f"initrd  {i}" for i in ipaths] + [f"options {e['cmdline']}"]
            (sugg / f"{n:02d}-{name}.conf").write_text("\n".join(body) + "\n")
    if n:
        add("Boot entries", "WARN", f"no BootLoaderSpec entries; {n} converted from {', '.join(lim)}",
            f"review {sugg}/ - copying them to <ESP>/loader/entries/ would let tinylinux list them (Limine ignores that folder)")
    else:
        add("Boot entries", "FAIL", "limine.conf has no linux entries tinylinux can use")

def check_console(live, tb, cfg):
    blocks = read(live, "input.txt").split("\n\n")
    kbds = []
    for b in blocks:
        name = re.search(r'N: Name="([^"]*)"', b); phys = re.search(r"P: Phys=(\S*)", b)
        hand = re.search(r"H: Handlers=(.*)", b)
        if not (name and hand and "kbd" in hand.group(1).split()): continue
        p = phys.group(1) if phys else ""
        if p.startswith("usb-") and "leds" in hand.group(1): kbds.append((name.group(1), "usb"))
        elif p.startswith("isa0060"): kbds.append((name.group(1), "ps2"))
    if not kbds:
        add("Console", "WARN", "no keyboard detected", "tinylinux's 5 s default still boots entry 1")
    for nm, kind in kbds:
        need = ["CONFIG_USB_HID", "CONFIG_HID_GENERIC"] if kind == "usb" else ["CONFIG_KEYBOARD_ATKBD", "CONFIG_SERIO_I8042"]
        ok = all(cfg.get(s) == "y" for s in need)
        add("Console", "PASS" if ok else "FAIL", f"keyboard: {nm} ({kind})", ("supported: " if ok else "missing: ") + ", ".join(need))
    disp = read(live, "display.txt")
    conn = re.findall(r"(card\d+-\S+): connected", disp)
    add("Console", "INFO", "monitor on " + (", ".join(conn) if conn else "?"),
        "tinylinux uses the UEFI GOP framebuffer the GPU's firmware sets up (CONFIG_FB_EFI)")
    ser = re.findall(r"ttyS(\d+)/port: (0x[0-9A-Fa-f]+)", read(live, "serial.txt"))
    if ser: add("Console", "INFO", "serial ports: " + ", ".join(f"ttyS{n}@{p}" for n, p in ser), "optional debug console (board COM header)")
    if tb:   # tinylinux has no /proc/fb (FB_DEVICE trimmed): the kernel log is the evidence
        klog = read(tb, "kernel_log.txt")
        mode = re.search(r"efifb: mode is (\S+)", klog)
        ok = "frame buffer device" in klog or re.search(r"^\d+ \S", read(tb, "display.txt"), re.M)
        add("tinylinux run", "PASS" if ok else "FAIL", "framebuffer console under tinylinux",
            f"efifb {mode.group(1)}" if mode else ("present" if ok else "no framebuffer: menu only on serial"))

def check_tinylinux_run(live, tb):
    meta = kvfile(tb, "meta.txt")
    add("tinylinux run", "PASS" if meta.get("env") == "tinylinux" else "WARN", f'collected in env={meta.get("env")}',
        f'kernel {meta.get("kernel_release")}')
    same, j = same_machine(live, tb)
    add("tinylinux run", "PASS" if same else "WARN", f"same machine as the live report? {j:.0%} of PCI IDs match",
        "per-device driver checks above use it" if same else "different machine (e.g. QEMU) - per-device checks skipped")
    add("tinylinux run", "PASS" if kvfile(tb, "efi.txt").get("efi") == "present" else "FAIL", "UEFI visible under tinylinux")
    blk = [b["name"] for b in tsv(tb, "block.tsv") if b.get("partition") == "no" and not b["name"].startswith(("loop", "ram", "zram"))]
    add("tinylinux run", "PASS" if blk else "FAIL", "disks visible under tinylinux: " + (", ".join(blk) or "none"))
    errs = [l for l in read(tb, "kernel_log.txt").splitlines() if re.search(r"error|fail|timeout|firmware bug", l, re.I)]
    harmless = [l for l in errs if any(re.search(p, l) for p in KNOWN_HARMLESS)]
    errs = [l for l in errs if l not in harmless]
    if harmless: add("tinylinux run", "INFO", f"{len(harmless)} known-harmless kernel messages", "e.g. ACPI genetlink: tinylinux has no networking")
    add("tinylinux run", "INFO" if not errs else "WARN", f"{len(errs)} error-like kernel log lines", "; ".join(e[-90:] for e in errs[:4]))

# ------------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("live"); ap.add_argument("--tinylinux")
    ap.add_argument("--kconfig", default=str(HERE.parent / "tinylinux/out/kernel-build/.config"))
    ap.add_argument("--ksrc", default=str(HERE.parent / "toolchain/src/linux-6.18.60"))
    ap.add_argument("--out")
    a = ap.parse_args()
    if not Path(a.live, "pci.tsv").exists(): sys.exit(f"{a.live}: not a collect.sh report")
    cfg, mm = kconfig(a.kconfig), module_map(a.ksrc)
    check_platform(a.live); check_firmware(a.live)
    by_slot = check_pci(a.live, a.tinylinux, cfg, mm)
    check_storage(a.live, by_slot); check_boot_entries(a.live, a.live); check_console(a.live, a.tinylinux, cfg)
    if a.tinylinux: check_tinylinux_run(a.live, a.tinylinux)
    else: add("tinylinux run", "TODO", "no tinylinux report yet", "boot tinylinux.efi from USB, press s, run collect.sh (see README)")

    counts = {s: sum(1 for c in checks if c[1] == s) for s in ("PASS", "FAIL", "WARN", "TODO", "INFO")}
    icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "TODO": "⏳", "INFO": "ℹ️"}
    meta = kvfile(a.live, "meta.txt")
    lines = ["# tinylinux readiness report", "",
             f"Live report: `{a.live}` (uid {meta.get('uid')}, kernel {meta.get('kernel_release')})  ",
             f"tinylinux report: `{a.tinylinux or '-'}`  ", f"tinylinux kernel config: `{a.kconfig}`", "",
             " · ".join(f"{icon[s]} {s} {n}" for s, n in counts.items()), ""]
    area = None
    for ar, st, item, det in checks:
        if ar != area:
            lines += ["", f"## {ar}", "", "| | Check | Detail |", "|---|---|---|"]; area = ar
        lines.append(f"| {icon[st]} {st} | {item} | {det} |")
    lines += ["", "_Scope: readiness of the **USB-stick test** of tinylinux (no flash). It does not make an image flashable._", ""]
    out = Path(a.out or Path(a.live) / "READINESS.md"); out.write_text("\n".join(lines))
    for ar, st, item, det in checks:
        if st != "INFO": print(f"{st:5} {ar:13} {item}" + (f"  -- {det}" if det and st in ('FAIL', 'WARN', 'TODO') else ""))
    print(f"\n{counts}\nreport: {out}")
    return 1 if counts["FAIL"] else 0

if __name__ == "__main__":
    sys.exit(main())
