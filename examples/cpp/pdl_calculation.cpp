#include "sample_helpers.hpp"
#include <cstdio>
#include <cmath>

// ---------------------------------------------------------------------------
// pdl_calculation.cpp, demonstrates IL/PDL calculation
// ---------------------------------------------------------------------------

void runPDLCalculationDemo()
{
	std::printf("\n[IL / PDL Calculation]\n");
	printSeparator();

	// Simulated four-SOP power data (LHP, LVP, LP45, LCP) in dBm.
	// In a real application these are collected via ReadPCUPowerMonitor()
	// or ReadOPMPower() during reference and measurement scans.
	constexpr PowerData reference = {{-3.10, -3.05, -3.08, -3.12}};
	constexpr PowerData measurement = {{-6.50, -6.30, -6.70, -6.40}};
	constexpr PowerData refMonitor = {{-0.10, -0.08, -0.09, -0.11}};
	constexpr PowerData measMonitor = {{-0.12, -0.10, -0.11, -0.13}};

	printPowerData("Reference  power data", reference);
	printPowerData("Measurement power data", measurement);
	printPowerData("Ref  power monitor data", refMonitor);
	printPowerData("Meas power monitor data", measMonitor);

	double il = std::numeric_limits<double>::quiet_NaN();
	double pdl = std::numeric_limits<double>::quiet_NaN();

	Calculation(NominalWavelength::Wl1550,
	            reference,
	            measurement,
	            refMonitor,
	            measMonitor,
	            &il,
	            &pdl);

	std::printf("\n  Results:\n");
	if (std::isnan(il))
		std::printf("    IL  : N/A  (PCU not connected?)\n");
	else
		std::printf("    IL  : %.4f dB\n", il);

	if (std::isnan(pdl))
		std::printf("    PDL : N/A  (PCU not connected?)\n");
	else
		std::printf("    PDL : %.4f dB\n", pdl);
}
