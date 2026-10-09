#include "sample_helpers.hpp"

// ---------------------------------------------------------------------------
// pcu_control.cpp, demonstrates PCU polarization state control
// ---------------------------------------------------------------------------

void runPCUDemo()
{
	std::printf("\n[PCU Control]\n");
	printSeparator();

	// Read power monitor before changing SOP
	const double monBefore = ReadPCUPowerMonitor();
	if (std::isnan(monBefore))
		std::printf("  PCU power monitor : not connected / not available\n");
	else
		std::printf("  PCU power monitor (before) : %.4f dBm\n", monBefore);

	// Cycle through all polarization states
	constexpr PolarizationState states[] = {
		PolarizationState::LHP,
		PolarizationState::LVP,
		PolarizationState::LP45,
		PolarizationState::LN45,
		PolarizationState::RCP,
		PolarizationState::LCP
	};

	for (const auto sop : states)
	{
		std::printf("  Setting SOP -> %-30s  ", polarizationName(sop));
		SetPCUSOP(sop);
		const double pwr = ReadPCUPowerMonitor();
		if (std::isnan(pwr))
			std::printf("power = N/A\n");
		else
			std::printf("power = %.4f dBm\n", pwr);
	}
}
