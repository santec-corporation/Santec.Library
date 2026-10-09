#include "sample_helpers.hpp"

// ---------------------------------------------------------------------------
// tsl_control.cpp, demonstrates TSL power and wavelength control
// ---------------------------------------------------------------------------

void runTSLDemo()
{
	std::printf("\n[TSL Control]\n");
	printSeparator();

	// --- Read current wavelength ---
	if (const double currentWl = GetTSLWavelength(); std::isnan(currentWl))
		std::printf("  TSL wavelength : not connected / not available\n");
	else
		std::printf("  TSL wavelength : %.4f nm\n", currentWl);

	// --- Read current power ---
	if (const double currentPwr = GetTSLPower(); std::isnan(currentPwr))
		std::printf("  TSL power      : not connected / not available\n");
	else
		std::printf("  TSL power      : %.4f dBm\n", currentPwr);

	// --- Set wavelength band ---
	constexpr auto targetBand = NominalWavelength::Wl1550;
	std::printf("  Setting wavelength band -> %s\n", wavelengthName(targetBand));
	SetWavelength(targetBand);

	// --- Set power ---
	constexpr double targetPower = 5.0; // dBm
	std::printf("  Setting TSL power -> %.1f dBm\n", targetPower);
	SetTSLPower(targetPower);

	// --- Verify ---
	if (const double newPwr = GetTSLPower(); !std::isnan(newPwr))
		std::printf("  TSL power after set : %.4f dBm\n", newPwr);
}
