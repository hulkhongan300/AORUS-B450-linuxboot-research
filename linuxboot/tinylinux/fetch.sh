#!/usr/bin/env bash
# Download the kernel.org kernel + busybox sources that build.sh uses, and check their sha256.
set -euo pipefail
src="$(cd "$(dirname "$0")" && pwd)/../toolchain/src"; mkdir -p "$src"; cd "$src"
get() { [ -f "$2" ] || curl -fL -o "$2" "$1/$2"; echo "$3  $2" | sha256sum -c -; [ -d "${2%.tar.*}" ] || tar xf "$2"; }
get https://cdn.kernel.org/pub/linux/kernel/v6.x linux-6.18.60.tar.xz \
    3c2f44ef6acc021a7ad444d9a2e6ec1ef488ff09368793d0004a6080f69d621e
get https://busybox.net/downloads busybox-1.37.0.tar.bz2 \
    3311dff32e746499f4df0d5df04d7eb396382d7e108bb9250e7b519b837043a4
