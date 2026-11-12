/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * DRAFT / REFERENCE ONLY — NOT BUILDABLE.
 * Translated from the stock BIOS AMD-CPM $A10 GPIO table
 * (analysis/board_gpio_table.txt, decoded by tools/decode_cpm_gpio.py).
 *
 * Targets a hypothetical src/soc/amd/<am4-desktop> that does NOT exist upstream.
 * Caveats:
 *  - PAD_NF() function names are unknown here: the $A10 table only carries the IOMUX
 *    *index* (0/1/2), not the named function. The real name comes from the SoC pin table
 *    (cf. src/soc/amd/picasso/include/soc/gpio.h). Indices are kept in comments.
 *  - Two $A10 copies exist: copy 1 = Summit/Pinnacle (Zen/Zen+, this 2700X board),
 *    copy 2 = Matisse/Vermeer. Differences noted inline.
 *  - SCI/wake pins come from the separate $A11 GEVENT map (GEVENT8/10/13); see gevent note below.
 */
#include <gpio.h>
#include "gpio.h"

/* Board GPIO configuration, Zen/Zen+ ($A10 copy 1). */
static const struct soc_amd_gpio board_gpio[] = {
	/* pin  raw       meaning (from $A10) */
	PAD_GPI(GPIO_2,   PULL_NONE),            /* 0x882  input  */
	PAD_GPO(GPIO_5,   LOW),                  /* 0x880  output low */
	PAD_GPI(GPIO_8,   PULL_NONE),            /* 0x882  input  — M.2 module-type detect (see $A26) */
	PAD_NF(GPIO_17,   IOMUX_F0, PULL_NONE),  /* 0x888  native func idx 0 */
	PAD_GPO(GPIO_85,  HIGH),                 /* 0x981  output high */
	PAD_NF(GPIO_91,   IOMUX_F0, PULL_NONE),  /* 0x888  native func idx 0 */
	PAD_GPI(GPIO_95,  PULL_NONE),            /* 0x982  input (idx1)  [copy2: GPIO_136] */
	PAD_GPI(GPIO_96,  PULL_NONE),            /* 0x982  input */
	PAD_GPI(GPIO_97,  PULL_NONE),            /* 0x982  input */
	PAD_GPI(GPIO_98,  PULL_NONE),            /* 0x982  input */
	PAD_GPI(GPIO_99,  PULL_NONE),            /* 0x982  input */
	PAD_NF(GPIO_115,  IOMUX_F0, PULL_UP),    /* 0x8a8  native func idx 0, pull-up [copy2: PUsel set] */
	PAD_GPI(GPIO_116, PULL_NONE),            /* 0x982  input (idx1) — M.2 module-type detect */
	PAD_NF(GPIO_129,  IOMUX_F0, PULL_UP),    /* 0x8a8  native func idx 0, pull-up */
};

/*
 * $A11 GEVENT -> GPE/SCI map (analysis/board_gevent_table.txt):
 *   GEVENT8  -> GPE 8  (edge, low)   : PCIe WAKE# aggregate (_L08 notifies all GPP ports)
 *   GEVENT10 -> GPE 10 (edge, low)   : SCI enabled — AMD CPM aggregate GPIO SCI (live _L0A, MYRTLE SSDT)
 *   GEVENT13 -> GPE 13 (edge, low)
 * In coreboot these are set via the SoC GEVENT/SCI tables (configure_scimap / sci_source),
 * not plain PAD_SCI, because they are FCH GEVENT inputs rather than directly-muxed GPIOs.
 */

void mainboard_program_gpios(void)
{
	gpio_configure_pads(board_gpio, ARRAY_SIZE(board_gpio));
}
