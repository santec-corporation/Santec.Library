#pragma once

#include "SantecLibrary.hpp"
#include <cstdio>
#include <cmath>
#include <string>

// ---------------------------------------------------------------------------
// Pretty-print helpers
// ---------------------------------------------------------------------------

inline const char* wavelengthName(const NominalWavelength wl)
{
	switch (wl)
	{
	case NominalWavelength::Wl850: return "850 nm";
	case NominalWavelength::Wl980: return "980 nm";
	case NominalWavelength::Wl1300: return "1300 nm";
	case NominalWavelength::Wl1310: return "1310 nm";
	case NominalWavelength::Wl1490: return "1490 nm";
	case NominalWavelength::Wl1550: return "1550 nm";
	case NominalWavelength::Wl1625: return "1625 nm";
	case NominalWavelength::Wl1650: return "1650 nm";
	case NominalWavelength::Unknown: return "Unknown";
	default: return "Unknown";
	}
}

inline const char* polarizationName(const PolarizationState sop)
{
	switch (sop)
	{
	case PolarizationState::LVP: return "LVP  (Linear Vertical)";
	case PolarizationState::LHP: return "LHP  (Linear Horizontal)";
	case PolarizationState::LP45: return "LP45 (Linear +45°)";
	case PolarizationState::LN45: return "LN45 (Linear -45°)";
	case PolarizationState::RCP: return "RCP  (Right Circular)";
	case PolarizationState::LCP: return "LCP  (Left Circular)";
	default: return "Unknown";
	}
}

inline void printPowerData(const char* label, const PowerData& pd)
{
	std::printf("  %-40s  LHP=%.4f  LVP=%.4f  LP45=%.4f  LCP=%.4f  (dBm)\n",
	            label, pd.Power[0], pd.Power[1], pd.Power[2], pd.Power[3]);
}

inline void printSeparator()
{
	std::printf("%.60s\n", "------------------------------------------------------------");
}
