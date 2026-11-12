/* SPDX-License-Identifier: GPL-2.0-only */
/* DRAFT / REFERENCE ONLY — NOT BUILDABLE. */
#include <soc/romstage.h>

void mainboard_romstage_entry(void)
{
	/*
	 * Memory is trained by AMD's AGESA/ABL + PMU firmware using the APCB
	 * (../../apcb_inventory.txt). A port reuses those signed blobs unmodified;
	 * the DXIO lane map is provided via mainboard_get_dxio_ddi_descriptors()
	 * in dxio_descriptors.c.
	 */
}
