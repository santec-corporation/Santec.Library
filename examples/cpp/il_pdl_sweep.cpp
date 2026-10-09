// =============================================================================
//  il_pdl_sweep.cpp
//  IL / PDL wavelength sweep demo
//
//  Workflow
//  --------
//  1.  User enters wavelength range (start / stop in nm).
//  2.  User enters an OPM-150 channel number, or 0 for all channels.
//  3.  Reference scan:
//        For each wavelength band in range
//          For each of the 4 SOP states (LHP, LVP, LP45, LCP)
//            Set wavelength on TSL570.
//            Set SOP on PCU110.
//            Capture OPM-150 power (selected channel / all channels).
//            Capture PCU110 power-monitor reading.
//  4.  User inserts DUT, then measurement scan (same structure).
//  5.  For every wavelength (and channel), call Calculation() for IL / PDL.
//  6.  Print results table and export to "il_pdl_sweep_results.csv".
// =============================================================================

#include "sample_helpers.hpp"
#include "sample_options.hpp"
#include <cstdio>
#include <cmath>
#include <cstring>
#include <utility>
#include <vector>
#include <string>
#include <fstream>
#include <thread>
#include <chrono>

// ---------------------------------------------------------------------------
// Wavelength table, maps centre nm to the Wavelength enum value
// ---------------------------------------------------------------------------
struct WlEntry
{
	double nm;
	NominalWavelength wl;
	const char* label;
};

static const WlEntry WL_TABLE[] =
{
	{.nm = 850.0, .wl = NominalWavelength::Wl850, .label = " 850 nm"},
	{.nm = 980.0, .wl = NominalWavelength::Wl980, .label = " 980 nm"},
	{.nm = 1300.0, .wl = NominalWavelength::Wl1300, .label = "1300 nm"},
	{.nm = 1310.0, .wl = NominalWavelength::Wl1310, .label = "1310 nm"},
	{.nm = 1490.0, .wl = NominalWavelength::Wl1490, .label = "1490 nm"},
	{.nm = 1550.0, .wl = NominalWavelength::Wl1550, .label = "1550 nm"},
	{.nm = 1625.0, .wl = NominalWavelength::Wl1625, .label = "1625 nm"},
	{.nm = 1650.0, .wl = NominalWavelength::Wl1650, .label = "1650 nm"},
};
static constexpr int WL_TABLE_SIZE = std::size(WL_TABLE);

// The four SOP states required by the Jones-matrix IL/PDL calculation.
// Order matches PowerData::Power[] indexing: [0]=LHP [1]=LVP [2]=LP45 [3]=LCP
static constexpr PolarizationState FOUR_SOPS[4] =
{
	PolarizationState::LHP,
	PolarizationState::LVP,
	PolarizationState::LP45,
	PolarizationState::RCP
};

// ---------------------------------------------------------------------------
// Per-wavelength, per-channel result
// ---------------------------------------------------------------------------
struct SweepResult
{
	double wavelengthNm;
	int channel; // 1-based; 0 = "all channels" aggregated
	double il; // dB
	double pdl; // dB
};

// ---------------------------------------------------------------------------
// Read power from one channel (or all channels).
// Returns false if the OPM returned no valid data.
//
// Called once per SOP state; the caller is responsible for setting the
// PCU SOP and (for single-channel mode) the active OPM channel beforehand.
// ---------------------------------------------------------------------------
static bool capturePowerData(const char* opmSerial,
                             const int channelRequest, // 0 = all channels
                             const int numChannels,    // total channels on device
                             std::vector<double>& outPowers)
{
	outPowers.clear();

	if (channelRequest == 0)
	{
		double* allPwr = nullptr;
		int32_t length = 0;
		ReadOPMAllChannels(opmSerial, &allPwr, &length);

		if (!allPwr || length <= 0)
		{
			std::printf("    [WARN] ReadOPMAllChannels returned no data\n");
			if (allPwr) FreeAllChannelsRead(allPwr);
			return false;
		}

		const int chCount = length < numChannels ? length : numChannels;
		outPowers.resize(static_cast<size_t>(chCount));
		for (int ch = 0; ch < chCount; ++ch)
			outPowers[static_cast<size_t>(ch)] = allPwr[ch];

		FreeAllChannelsRead(allPwr);
	}
	else
	{
		const double pwr = ReadOPMPower(opmSerial);
		outPowers.push_back(pwr);
	}

	return true;
}

// ---------------------------------------------------------------------------
// Perform one full scan (reference or measurement).
// Returns a 2-D array:
//      scanData[wlIdx][chIdx] = PowerData (4 SOPs)
//      monitorData[wlIdx][sopIdx] = PCU monitor reading
// ---------------------------------------------------------------------------
static void performScan(
	const char* opmSerial,
	const int channelRequest,
	const int numChannels,
	const std::vector<const WlEntry*>& wlList,
	std::vector<std::vector<PowerData>>& scanData,
	std::vector<std::vector<double>>& monitorData)
{
	const int wlCount = static_cast<int>(wlList.size());
	const int chCount = (channelRequest == 0) ? numChannels : 1;

	scanData.assign(
		static_cast<size_t>(wlCount),
		std::vector<PowerData>(static_cast<size_t>(chCount)));

	monitorData.assign(
		static_cast<size_t>(wlCount),
		std::vector<double>(4, std::numeric_limits<double>::quiet_NaN()));

	for (int wIdx = 0; wIdx < wlCount; ++wIdx)
	{
		const WlEntry* entry = wlList[static_cast<size_t>(wIdx)];

		std::printf("  \nWavelength %s\n", entry->label);

		// Set wavelength (once per wavelength)
		SetWavelength(entry->wl);

		// Laser settling delay
		std::this_thread::sleep_for(std::chrono::milliseconds(100));

		// Activate the target OPM channel once per wavelength
		// (all-channel mode reads every channel in one call, so this is a
		// no-op when channelRequest == 0).
		if (channelRequest != 0)
		{
			SetOPMChannel(opmSerial, static_cast<uint8_t>(channelRequest));
		}

		// Four SOP measurements
		for (int sopIdx = 0; sopIdx < 4; ++sopIdx)
		{
			std::printf("    SOP %-30s\n", polarizationName(FOUR_SOPS[sopIdx]));

			// Set PCU SOP
			SetPCUSOP(FOUR_SOPS[sopIdx]);

			// Capture OPM power (single read at the current SOP)
			std::vector<double> powers;
			capturePowerData(opmSerial, channelRequest, numChannels, powers);

			for (int ch = 0; ch < static_cast<int>(powers.size()); ++ch)
			{
				scanData[static_cast<size_t>(wIdx)]
					[static_cast<size_t>(ch)]
					.Power[sopIdx] = powers[static_cast<size_t>(ch)];
			}

			// Read PCU monitor
			double mon = ReadPCUPowerMonitor();
			monitorData[static_cast<size_t>(wIdx)][sopIdx] = mon;

			// Console output
			std::printf(
				"OPM ch%d = %.4f dBm  monitor = %.4f dBm\n",
				channelRequest == 0 ? 1 : channelRequest,
				std::isnan(scanData[static_cast<size_t>(wIdx)][0].Power[sopIdx])
				? 0.0
				: scanData[static_cast<size_t>(wIdx)][0].Power[sopIdx],
				std::isnan(mon) ? 0.0 : mon);
		}
	}
}

// ---------------------------------------------------------------------------
// Export results to CSV
// ---------------------------------------------------------------------------
static void exportCSV(const std::vector<SweepResult>& results,
                      const char* filename)
{
	std::ofstream ofs(filename);
	if (!ofs)
	{
		std::printf("  [ERROR] Could not open %s for writing.\n", filename);
		return;
	}

	ofs << "Wavelength_nm,Channel,IL_dB,PDL_dB\n";
	for (const auto& [wavelengthNm, channel, il, pdl] : results)
	{
		ofs << wavelengthNm << ","
			<< channel << ",";

		if (std::isnan(il)) ofs << "N/A";
		else ofs << il;
		ofs << ",";
		if (std::isnan(pdl)) ofs << "N/A";
		else ofs << pdl;
		ofs << "\n";
	}

	std::printf("  Results exported to: %s\n", filename);
}

// ---------------------------------------------------------------------------
// runILPDLSweepDemo, entry point called from main()
// ---------------------------------------------------------------------------
void runILPDLSweepDemo()
{
	std::printf("\n[IL/PDL Wavelength Sweep]\n");
	printSeparator();

	// -----------------------------------------------------------------------
	// 1. User inputs: wavelength range
	// -----------------------------------------------------------------------
	double startNm = 1480, stopNm = 1640;

	if (startNm > stopNm)
	{
		std::swap(startNm, stopNm);
	}

	// Build filtered wavelength list
	std::vector<const WlEntry*> wlList;
	for (const auto& i : WL_TABLE)
	{
		if (i.nm >= startNm && i.nm <= stopNm)
			wlList.push_back(&i);
	}

	if (wlList.empty())
	{
		std::printf("  No supported wavelength bands found in [%.0f, %.0f] nm.\n"
		            "  Supported bands: 850, 980, 1300, 1310, 1490, 1550, 1625, 1650 nm.\n",
		            startNm, stopNm);
		return;
	}

	std::printf("  Wavelength bands selected:\n");
	for (auto* e : wlList)
		std::printf("    %s\n", e->label);

	// -----------------------------------------------------------------------
	// 2. OPM-150 serial number and channel selection.
	//    The serial comes from the command line (--opm-serial).
	// -----------------------------------------------------------------------
	const char* opmSerial = g_options.opmSerial;

	// 0 for all channels
	constexpr int channelRequest = 1;

	// Determine number of channels available (used only when reading all channels)
	int numChannels = 1;
	if constexpr (channelRequest == 0)
	{
		double* probe = nullptr;
		int32_t probeN = 0;

		// Prime with 1550 nm band to get channel count
		SetWavelength(NominalWavelength::Wl1550);

		std::this_thread::sleep_for(std::chrono::milliseconds(100));

		ReadOPMAllChannels(opmSerial, &probe, &probeN);
		if (probe && probeN > 0)
		{
			numChannels = probeN;
			FreeAllChannelsRead(probe);
		}
		std::printf("  OPM-150 reports %d channel(s).\n", numChannels);
	}

	constexpr int chCount = channelRequest == 0 ? numChannels : 1;

	// -----------------------------------------------------------------------
	// 3. Reference scan
	// -----------------------------------------------------------------------
	std::printf("\n--- REFERENCE SCAN ---\n");
	std::printf("  Remove DUT. Connect reference path. Press ENTER when ready ...");
	std::getchar();

	std::vector<std::vector<PowerData>> refData, measData;
	std::vector<std::vector<double>> refMon, measMon;

	performScan(opmSerial, channelRequest, numChannels,
		wlList, refData, refMon);

	// -----------------------------------------------------------------------
	// 4. Measurement scan
	// -----------------------------------------------------------------------
	std::printf("\n--- MEASUREMENT SCAN ---\n");
	std::printf("  Insert DUT. Press ENTER when ready ...");
	std::getchar();

	performScan(opmSerial, channelRequest, numChannels,
		wlList, measData, measMon);

	// -----------------------------------------------------------------------
	// 5. Calculate IL and PDL per wavelength per channel
	// -----------------------------------------------------------------------
	std::printf("\n--- RESULTS ---\n");
	std::printf("  %-10s  %-8s  %-12s  %-12s\n",
	            "Wavelength", "Channel", "IL (dB)", "PDL (dB)");
	printSeparator();

	std::vector<SweepResult> results;

	for (int wIdx = 0; std::cmp_less(wIdx, wlList.size()); ++wIdx)
	{
		const WlEntry* entry = wlList[static_cast<size_t>(wIdx)];

		// Build PowerData for monitors (same monitor reading shared across channels)
		PowerData refMonPD = {};
		PowerData measMonPD = {};

		for (int s = 0; s < 4; ++s)
		{
			refMonPD.Power[s] = refMon[static_cast<size_t>(wIdx)][static_cast<size_t>(s)];
			measMonPD.Power[s] = measMon[static_cast<size_t>(wIdx)][static_cast<size_t>(s)];
		}

		for (int ch = 0; ch < chCount; ++ch)
		{
			double il = std::numeric_limits<double>::quiet_NaN();
			double pdl = std::numeric_limits<double>::quiet_NaN();

			Calculation(entry->wl,
				refData[static_cast<size_t>(wIdx)][static_cast<size_t>(ch)],
				measData[static_cast<size_t>(wIdx)][static_cast<size_t>(ch)],
				refMonPD,
				measMonPD,
				&il,
				&pdl);

			constexpr int displayCh = channelRequest == 0 ? ch + 1 : channelRequest;

			if (std::isnan(il) || std::isnan(pdl))
				std::printf("  %-10s  ch %-5d  IL = N/A         PDL = N/A\n",
					entry->label, displayCh);
			else
				std::printf("  %-10s  ch %-5d  IL = %+8.4f dB  PDL = %7.4f dB\n",
					entry->label, displayCh, il, pdl);

			results.push_back({ .wavelengthNm = entry->nm, .channel = displayCh, .il = il, .pdl = pdl });
		}
	}

	// -----------------------------------------------------------------------
	// 6. Export results to CSV
	// -----------------------------------------------------------------------
	std::printf("\n");
	exportCSV(results, "il_pdl_sweep_results.csv");
}
