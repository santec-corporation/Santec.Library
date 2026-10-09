#include "sample_helpers.hpp"
#include "sample_options.hpp"
#include <cstdio>

// ---------------------------------------------------------------------------
// opm_control.cpp : OPM150 single-channel reads, all-channel reads,
//                   OP-ETH session timeout, gain control, range mode,
//                   and read validation
// ---------------------------------------------------------------------------

// The serial number comes from the command line (--opm-serial) so no specific
// instrument is baked into the sample.
static const char* const& OPM_SERIAL = g_options.opmSerial;

void runOPMDemo()
{
	std::printf("\n[OPM Control]  (serial: %s)\n", OPM_SERIAL);
	printSeparator();

	// --- OP-ETH session timeout (Ethernet only; no-op over FTDI) ---
	std::printf("\n OP-ETH session timeout ...\n");
	uint16_t tcpPort = 0, udpPort = 0, timeout = 0;

	GetOPMFlashConfig(OPM_SERIAL, &tcpPort, &udpPort, &timeout);
	std::printf("  Current config: TCP=%u, UDP=%u, Timeout=%u s\n",
		tcpPort, udpPort, timeout);

	constexpr uint16_t newTimeout = 120;
	std::printf("  Setting timeout to %u s ...\n", newTimeout);
	SetOPMTimeout(OPM_SERIAL, newTimeout);

	GetOPMTempConfig(OPM_SERIAL, &tcpPort, &udpPort, &timeout);
	std::printf("  Temp config after TCP change: TCP=%u, UDP=%u, Timeout=%u s\n",
		tcpPort, udpPort, timeout);

	// --- Range mode ---
	std::printf("\n Range mode ...\n");

	std::printf("  Switching to RangeHold ...\n");
	SetOPMRangeMode(OPM_SERIAL, OPMRangeMode::RangeHold);

	// --- Gain control ---
	std::printf("\n Gain control ...\n");

	std::printf("  Setting gain to Gain0 ...\n");
	SetOPMGain(OPM_SERIAL, OPMGain::Gain0);

	SaveOPMConfig(OPM_SERIAL);
	// --- Single channel read (channel 1) ---
	constexpr uint8_t channel = 1;
	std::printf("\n Single channel read ...\n");
	std::printf("  Activating channel %u ...\n", channel);
	SetOPMChannel(OPM_SERIAL, channel);

	if (const double singlePwr = ReadOPMPower(OPM_SERIAL); std::isnan(singlePwr))
		std::printf("  Channel %u power : not connected / not available\n", channel);
	else
		std::printf("  Channel %u power : %.4f dBm\n", channel, singlePwr);

	// --- All-channels read ---
	double* allPwr = nullptr;
	int32_t numCh = 0;

	std::printf("\n  Reading all channels ...\n");
	ReadOPMAllChannels(OPM_SERIAL, &allPwr, &numCh);

	if (allPwr && numCh > 0)
	{
		for (int32_t i = 0; i < numCh; ++i)
			std::printf("    Channel %2d : %.4f dBm\n", i + 1, allPwr[i]);

		// IMPORTANT: free the library-allocated buffer
		FreeAllChannelsRead(allPwr);
	}
	else
	{
		std::printf("  All-channel read returned no data.\n");
	}

	// --- Read validation ---
	std::printf("\n Read validation ...\n");

	const int32_t initialValidation = GetOPMReadValidation(OPM_SERIAL);
	if (initialValidation == -1)
		std::printf("  Could not query read validation state.\n");
	else
		std::printf("  Read validation : %s\n", initialValidation ? "enabled" : "disabled");

	const double initialDeltaDb = GetOPMReadMaxDeltaDb(OPM_SERIAL);
	if (std::isnan(initialDeltaDb))
		std::printf("  Could not query max delta threshold.\n");
	else
		std::printf("  Max delta threshold : %.2f dB\n", initialDeltaDb);

	std::printf("  Enabling read validation ...\n");
	SetOPMReadValidation(OPM_SERIAL, true);

	constexpr double newMaxDeltaDb = 0.3;
	std::printf("  Setting max delta threshold to %.2f dB ...\n", newMaxDeltaDb);
	SetOPMReadMaxDeltaDb(OPM_SERIAL, newMaxDeltaDb);

	const int32_t updatedValidation = GetOPMReadValidation(OPM_SERIAL);
	const double updatedDeltaDb = GetOPMReadMaxDeltaDb(OPM_SERIAL);

	std::printf("  Updated read validation : %s\n",
		updatedValidation == 1 ? "enabled" : (updatedValidation == -1 ? "error" : "disabled"));
	if (!std::isnan(updatedDeltaDb))
		std::printf("  Updated max delta threshold : %.2f dB\n", updatedDeltaDb);
}
