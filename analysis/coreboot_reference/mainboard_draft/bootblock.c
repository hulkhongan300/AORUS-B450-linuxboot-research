/* SPDX-License-Identifier: GPL-2.0-only */
/* DRAFT / REFERENCE ONLY — NOT BUILDABLE. */
#include <bootblock_common.h>

void bootblock_mainboard_early_init(void)
{
	/*
	 * Early Super I/O enable so serial/console and the HW monitors are reachable.
	 * FCH LPC decode for 0x2E/0x4E and the 0xA00/0xA50 wide-IO windows must be
	 * programmed here (decoded in FINDINGS 4d; FCH 00:14.3 cfg 0x44/48/64/66/74/90).
	 */
}
