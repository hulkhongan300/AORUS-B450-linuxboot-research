/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * DRAFT / REFERENCE ONLY — NOT BUILDABLE.
 * PCIe/DXIO lane map reconstructed from the stock BIOS AMD-CPM $A26 table
 * (analysis/pcie_dxio_topology.txt, tools/decode_dxio.py) for the Zen/Zen+ copy
 * (this 2700X board). Field names follow coreboot's fsp_dxio_descriptor
 * (src/vendorcode/amd/fsp/*/platform_descriptors.h).
 *
 * Verified against live `lspci -t`: GPU (RX 580) on the x16 slot behind 00:03.1;
 * B450 chipset (43d5/43c8/43c6) behind 00:01.3.
 */
#include <platform_descriptors.h>

static const fsp_dxio_descriptor b450_aorus_pro_dxio[] = {
	/* PCIe x16 slot (CPU lanes 16-31) -> 00:03.1 */
	{
		.engine_type = PCIE_ENGINE,
		.port_present = true,
		.start_lane = 16,
		.end_lane = 31,
		.device_number = 3,
		.function_number = 1,
		.link_speed_capability = GEN3,
		.turn_off_unused_lanes = true,
		.link_aspm = ASPM_L1,
		.link_hotplug = HOTPLUG_DISABLED,
	},
	/* B450 (Promontory) chipset uplink, x4.
	 * NOTE: Zen/Zen+ copy numbers these lanes 7->4 (reversed); Matisse/Vermeer use 8-11.
	 * -> 00:01.3 */
	{
		.engine_type = PCIE_ENGINE,
		.port_present = true,
		.start_lane = 4,
		.end_lane = 7,
		.device_number = 1,
		.function_number = 3,
		.link_speed_capability = GEN3,
		.turn_off_unused_lanes = true,
		.link_aspm = ASPM_L1,
		.link_hotplug = HOTPLUG_DISABLED,
	},
	/*
	 * M.2 socket (CPU lanes 0-3) is appended at RUNTIME by AmdCpmOemInitPeim based on
	 * GPIO8 / GPIO116 straps (M.2 module-type detect, see FINDINGS 4b):
	 *   GPIO8==0 && GPIO116==1 -> PCIe x4 to 00:01.1 (GPP0)
	 *   otherwise              -> SATA_ENGINE on lanes 4-5
	 * A port must replicate that strap read; shown here as the NVMe (PCIe) case:
	 */
	{
		.engine_type = PCIE_ENGINE,
		.port_present = true,
		.start_lane = 0,
		.end_lane = 3,
		.device_number = 1,
		.function_number = 1,
		.link_speed_capability = GEN3,
		.turn_off_unused_lanes = true,
		.link_aspm = ASPM_L1,
		.link_hotplug = HOTPLUG_DISABLED,
	},
};

/* romstage hook (cf. soc/amd/*/romstage.c calling mainboard_get_dxio_ddi_descriptors) */
void mainboard_get_dxio_ddi_descriptors(const fsp_dxio_descriptor **dxio, size_t *dxio_num,
					const fsp_ddi_descriptor **ddi, size_t *ddi_num)
{
	*dxio = b450_aorus_pro_dxio;
	*dxio_num = ARRAY_SIZE(b450_aorus_pro_dxio);
	*ddi = NULL;		/* desktop AM4 has no display DDI (APU-only; see $A20) */
	*ddi_num = 0;
}
