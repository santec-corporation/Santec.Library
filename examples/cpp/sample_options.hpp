// =============================================================================
//  sample_options.hpp
//  Command-line options shared by the sample's translation units.
//
//  This sample ships publicly, so no lab address, serial number or MAC is baked
//  into the source: every connection detail has a placeholder default and can be
//  overridden on the command line.
// =============================================================================
#pragma once

#include <cstdio>
#include <cstring>

struct SampleOptions
{
	// Documentation addresses (RFC 5737: 192.0.2.0/24, 198.51.100.0/24 and
	// 203.0.113.0/24 are reserved for examples). Nothing here is a lab address.
	const char* tslAddress = "192.0.2.10:5000"; // Santec TSL-570 over LAN
	const char* opmAddress = "192.0.2.11:23";   // OPM-150 over LAN (Telnet)
	const char* pcuAddress = "192.0.2.12:5000"; // PCU-110 over LAN
	const char* opmSerial = "SN00000";          // OPM-150 serial number
	const char* mac = "00-00-00-00-00-00";      // target for the network demo
	const char* newIp = "0.0.0.0";              // "0.0.0.0" selects DHCP
	const char* newMask = "255.255.255.0";
	bool opmNetworkDemo = false;
	bool showHelp = false;
};

inline SampleOptions g_options;

inline void printSampleUsage(const char* exe)
{
	std::printf(
		"Usage: %s [options]\n"
		"  --tsl <address>      TSL LAN address        (default %s)\n"
		"  --opm <address>      OPM-150 LAN address    (default %s)\n"
		"  --pcu <address>      PCU-110 LAN address    (default %s)\n"
		"  --opm-serial <sn>    OPM-150 serial number  (default %s)\n"
		"  --opm-network-demo   run the GIPA/SIPA/TIPA/UIPC network demo\n"
		"  --mac <mac>          target MAC for the network demo (default %s)\n"
		"  --ip <address>       IP to stage in the network demo (0.0.0.0 = DHCP)\n"
		"  --mask <mask>        netmask to stage in the network demo\n"
		"  --help               show this text\n",
		exe, g_options.tslAddress, g_options.opmAddress, g_options.pcuAddress,
		g_options.opmSerial, g_options.mac);
}

// Returns false when an option is unknown or is missing its value.
inline bool parseSampleOptions(int argc, char** argv)
{
	for (int i = 1; i < argc; ++i)
	{
		const char* arg = argv[i];
		const auto takeValue = [&](const char*& target)
		{
			if (i + 1 >= argc) return false;
			target = argv[++i];
			return true;
		};

		if (std::strcmp(arg, "--help") == 0 || std::strcmp(arg, "-h") == 0)
			g_options.showHelp = true;
		else if (std::strcmp(arg, "--opm-network-demo") == 0)
			g_options.opmNetworkDemo = true;
		else if (std::strcmp(arg, "--tsl") == 0)
		{
			if (!takeValue(g_options.tslAddress)) return false;
		}
		else if (std::strcmp(arg, "--opm") == 0)
		{
			if (!takeValue(g_options.opmAddress)) return false;
		}
		else if (std::strcmp(arg, "--pcu") == 0)
		{
			if (!takeValue(g_options.pcuAddress)) return false;
		}
		else if (std::strcmp(arg, "--opm-serial") == 0)
		{
			if (!takeValue(g_options.opmSerial)) return false;
		}
		else if (std::strcmp(arg, "--mac") == 0)
		{
			if (!takeValue(g_options.mac)) return false;
		}
		else if (std::strcmp(arg, "--ip") == 0)
		{
			if (!takeValue(g_options.newIp)) return false;
		}
		else if (std::strcmp(arg, "--mask") == 0)
		{
			if (!takeValue(g_options.newMask)) return false;
		}
		else
		{
			std::printf("Unknown option: %s\n", arg);
			return false;
		}
	}

	return true;
}
