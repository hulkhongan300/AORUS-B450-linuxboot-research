/* SPDX-License-Identifier: GPL-2.0-only */
/* DRAFT / REFERENCE ONLY — NOT BUILDABLE. */
#include <acpi/acpi.h>
DefinitionBlock (
	"dsdt.aml",
	"DSDT",
	ACPI_DSDT_REV_2,
	OEM_ID,
	ACPI_TABLE_CREATOR,
	0x00010001
	)
{
	#include <acpi/dsdt_top.asl>
	#include <soc.asl>		/* hypothetical am4_desktop SoC ASL */

	/*
	 * Board-specific ACPI would go here. The stock DSDTs (4 of them, one per CPU
	 * family) are in ../../acpi/ for reference; the runtime AGESA/CPM SSDTs
	 * (IVRS/CRAT/MYRTLE/AOD) are catalogued in ../../LIVE_ACPI.md and would be
	 * emitted by the SoC code via acpigen, not hand-written here.
	 */
}
