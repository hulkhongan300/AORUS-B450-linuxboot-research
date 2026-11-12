/* SPDX-License-Identifier: GPL-2.0-only */
/* DRAFT / REFERENCE ONLY — NOT BUILDABLE. */
#include <device/device.h>

void mainboard_program_gpios(void);		/* in gpio.c */

static void mainboard_init(void *chip_info)
{
	mainboard_program_gpios();
	/*
	 * TODO (grounded in the RE, no upstream code yet):
	 *  - Promontory (B450) bring-up: see ../../PROMONTORY_FW_LOADER.md
	 *    (upload the signed _PT_ blob, then CBS/SATA/USB/GPIO config).
	 *  - IT8686E + IT8792E HW-monitor/fan init: see ../../superio_it87_tables.txt
	 *    and ../../fan_hwm_init.txt (exact IT8686E register sequence per CPU family).
	 */
}

struct chip_operations mainboard_ops = {
	.init = mainboard_init,
};
