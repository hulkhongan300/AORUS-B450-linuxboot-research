/* kexec-boot: load KERNEL [+ INITRD] with kexec_file_load(2) and jump to it.
 * Freestanding x86_64: no libc, raw syscalls -> a few KB instead of ~860 KB static glibc.
 * usage: kexec-boot KERNEL INITRD|- [CMDLINE] */
#define SYS_write 1
#define SYS_open 2
#define SYS_exit 60
#define SYS_sync 162
#define SYS_reboot 169
#define SYS_kexec_file_load 320
#define KEXEC_FILE_NO_INITRAMFS 0x4
#define REBOOT_MAGIC1 0xfee1deadL
#define REBOOT_MAGIC2 672274793L
#define REBOOT_CMD_KEXEC 0x45584543L

static long sc(long n, long a, long b, long c, long d, long e) {
    long r;
    register long r10 __asm__("r10") = d;
    register long r8 __asm__("r8") = e;
    __asm__ volatile("syscall" : "=a"(r) : "a"(n), "D"(a), "S"(b), "d"(c), "r"(r10), "r"(r8)
                     : "rcx", "r11", "memory");
    return r;
}
static unsigned long slen(const char *s) { unsigned long n = 0; while (s[n]) n++; return n; }
static void say(const char *s) { sc(SYS_write, 2, (long)s, slen(s), 0, 0); }
static long fail(const char *what, long err) {      /* err is -errno */
    char num[24]; int i = 23; unsigned long v = (unsigned long)-err; num[i] = 0;
    do { num[--i] = '0' + v % 10; v /= 10; } while (v);
    say("kexec-boot: "); say(what); say(" failed, errno "); say(num + i); say("\n");
    return 1;
}
long cmain(long argc, char **argv) {
    if (argc < 3) { say("usage: kexec-boot KERNEL INITRD|- [CMDLINE]\n"); return 2; }
    const char *cmdline = argc > 3 ? argv[3] : "";
    long flags = 0, ifd = -1, kfd = sc(SYS_open, (long)argv[1], 0, 0, 0, 0);
    if (kfd < 0) return fail(argv[1], kfd);
    if (argv[2][0] == '-' && argv[2][1] == 0) flags |= KEXEC_FILE_NO_INITRAMFS;
    else if ((ifd = sc(SYS_open, (long)argv[2], 0, 0, 0, 0)) < 0) return fail(argv[2], ifd);
    long r = sc(SYS_kexec_file_load, kfd, ifd, slen(cmdline) + 1, (long)cmdline, flags);
    if (r < 0) return fail("kexec_file_load", r);
    sc(SYS_sync, 0, 0, 0, 0, 0);
    r = sc(SYS_reboot, REBOOT_MAGIC1, REBOOT_MAGIC2, REBOOT_CMD_KEXEC, 0, 0);
    return fail("reboot(KEXEC)", r);
}
__asm__(".globl _start\n_start:\n"
        "  xor %rbp, %rbp\n  mov (%rsp), %rdi\n  lea 8(%rsp), %rsi\n  and $-16, %rsp\n"
        "  call cmain\n  mov %rax, %rdi\n  mov $60, %rax\n  syscall\n");
