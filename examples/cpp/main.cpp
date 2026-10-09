// =============================================================================
//  SantecLibrary C++ Sample Program
//  Demonstrates device discovery, connection management, TSL / PCU / OPM
//  control, and IL/PDL calculation via SantecLibrary.hpp.
// =============================================================================

#include "SantecLibrary.hpp"
#include "sample_helpers.hpp"
#include "sample_options.hpp"
#include "device_discovery.hpp"

#include <cstdio>
#include <cstring>
#include <array>
#include <Windows.h>

// Forward declarations (defined in their own translation units)
void runTSLDemo();
void runPCUDemo();
void runOPMDemo();
void runPDLCalculationDemo();
void runILPDLSweepDemo();
void runOPMNetworkDemo(bool applyIP);

// ---------------------------------------------------------------------------
// Helper: find the first device whose ProductName contains a substring
// ---------------------------------------------------------------------------
static const ConnectionConfig* findDevice(const ConnectionConfig* devices,
                                          const int count,
                                          const char* productSubstring)
{
	for (int i = 0; i < count; ++i)
	{
		if (devices[i].ProductName &&
			std::strstr(devices[i].ProductName, productSubstring))
		{
			return &devices[i];
		}
	}
	return nullptr;
}

// ---------------------------------------------------------------------------
int main(int argc, char** argv)
{
	SetConsoleOutputCP(CP_UTF8);

	if (!parseSampleOptions(argc, argv))
	{
		printSampleUsage(argv[0]);
		return 2;
	}
	if (g_options.showHelp)
	{
		printSampleUsage(argv[0]);
		return 0;
	}

	// -----------------------------------------------------------------------
	// 1. Configure logging
	// -----------------------------------------------------------------------
	std::printf("=== SantecLibrary C++ Sample ===\n");
	printSeparator();
	std::printf("Enabling Information-level logging ...\n");
	SetLogLevel(LogEventLevel::Information);

	// -----------------------------------------------------------------------
	// 2. Device discovery
	// -----------------------------------------------------------------------
	constexpr int MAX_DEVICES = 32;
	std::array<ConnectionConfig, MAX_DEVICES> devices{};

	if (const int count = discoverDevices(devices.data(), MAX_DEVICES); count == 0)
	{
		std::printf("\nNo devices found, running demos in offline/simulation mode.\n");
		std::printf("Demos will show N/A for live readings.\n");

		// We still exercise the calculation API which does not need hardware.
		runPDLCalculationDemo();

		std::printf("\nSample finished.\n");
		return 0;
	}

	// -----------------------------------------------------------------------
	// 2. OPM-150 Network configuration demo (UDP broadcast)
	//    Opt-in: it changes a device's IP configuration when it runs.
	// -----------------------------------------------------------------------
	if (g_options.opmNetworkDemo)
		runOPMNetworkDemo(true);

	// -----------------------------------------------------------------------
	// 3. Connection
	//    Strategy A, connect a single device (use SetConnection).
	//    Strategy B, connect TSL + power-meter (+ optional SPU) in one call.
	// -----------------------------------------------------------------------
	std::printf("\n[Connection]\n");
	printSeparator();

	// Addresses come from the command line, so nothing lab-specific is baked in.
	// For GPIB / USB devices, discover them and use the returned configuration
	// instead: findDevice(devices.data(), count, "TSL").
	const ConnectionConfig tslConfig{ "LAN", "", "TSL-570", g_options.tslAddress };
	const ConnectionConfig opmConfig{ "LAN", "", "OPM-150", g_options.opmAddress };
	// UDP protocol: { "LAN - UDP", "", "OPM-150", g_options.opmAddress }
	const ConnectionConfig pcuConfig{ "LAN", "", "PCU-110", g_options.pcuAddress };

	const ConnectionConfig* tslDev = &tslConfig;
	const ConnectionConfig* opmDev = &opmConfig;
	const ConnectionConfig* pcuDev = &pcuConfig;

	bool connected = false;

	if (tslDev)
	{
		std::printf("  Connecting TSL device: %s\n", tslDev->ProductName);
		connected = SetConnection(tslDev);
		std::printf("  SetConnection -> %s\n", connected ? "OK" : "FAILED");
	}
	if (opmDev)
	{
		std::printf("  Connecting OPM (%s) ...\n", opmDev->ProductName);
		connected = SetConnection(opmDev);
		std::printf("  SetConnection -> %s\n", connected ? "OK" : "FAILED");
	}
	if (pcuDev)
	{
		std::printf("  Connecting PCU (%s) ...\n", pcuDev->ProductName);
		connected = SetConnection(pcuDev);
		std::printf("  SetConnection -> %s\n", connected ? "OK" : "FAILED");
	}

	if (!connected)
	{
		std::printf("\nConnection failed. Exiting.\n");
		return 1;
	}

	// -----------------------------------------------------------------------
	// 4. TSL control demo
	// -----------------------------------------------------------------------
	runTSLDemo();

	// -----------------------------------------------------------------------
	// 5. PCU control demo
	// -----------------------------------------------------------------------
	runPCUDemo();

	// -----------------------------------------------------------------------
	// 6. OPM control demo
	// -----------------------------------------------------------------------
	runOPMDemo();

	// -----------------------------------------------------------------------
	// 8. IL / PDL calculation demo (static simulated data)
	// -----------------------------------------------------------------------
	runPDLCalculationDemo();

	// -----------------------------------------------------------------------
	// 9. IL / PDL wavelength sweep (user-driven, live hardware)
	// -----------------------------------------------------------------------
	runILPDLSweepDemo();

	// -----------------------------------------------------------------------
	// 10. Disconnect
	// -----------------------------------------------------------------------
	std::printf("\n[Disconnect]\n");
	printSeparator();
	Disconnect();
	std::printf("  All devices disconnected.\n");

	std::printf("\nSample finished successfully.\n");
	return 0;
}

// =============================================================================
//  OPM-150 Network Configuration Demo
//  Demonstrates GIPA discovery, SIPA temp config, TIPA query, and UIPC commit.
// 
//  All commands use UDP broadcast on port 61022 (OP-ETH module default).
//  The module also listens on a backup UDP port 61023 that cannot be changed.
//  Default TCP port for Telnet is 23.
//
//  DHCP: pass "0.0.0.0" as the IP to SIPA to enable DHCP on the module.
//  If no DHCP server responds the module falls back to AutoIP
//  (a 169.254.x.x address with mask 255.255.0.0).
// 
// @param applyIP Boolean to apply a new IP address to the OPM.
// 
// =============================================================================
void runOPMNetworkDemo(bool applyIP = false)
{
	std::printf("\n[OPM-150 Network Configuration Demo]\n");
	printSeparator();

	// -------------------------------------------------------------------
	// Step 1, Discover all OPM-150 devices on the network (GIPA)
	// -------------------------------------------------------------------
	std::printf("  Step 1: Broadcasting GIPA discovery ...\n");

	if (const char* discovered = DiscoverOPMDevices(); discovered && std::strlen(discovered) > 0)
	{
		std::printf("  Discovered devices:\n%s\n", discovered);
		FreeString(const_cast<char*>(discovered));
	}
	else
	{
		std::printf("  No OPM-150 devices found on the network.\n");
		if (discovered) FreeString(const_cast<char*>(discovered));

		std::printf("  Skipping remaining network demo steps.\n");
		printSeparator();
		return;
	}

	if (!applyIP)
		return;

	// -------------------------------------------------------------------
	// Step 2, Set a temporary IP configuration (SIPA)
	//    The MAC must match a device discovered above; values come from the
	//    command line (--mac / --ip / --mask).
	// -------------------------------------------------------------------
	const char* targetMac = g_options.mac;
	const char* newIp = g_options.newIp;
	const char* newMask = g_options.newMask;

	std::printf("\n  Step 2: Setting temporary IP config via SIPA ...\n");
	std::printf("    MAC  : %s\n", targetMac);
	std::printf("    IP   : %s\n", newIp);
	std::printf("    Mask : %s\n", newMask);

	if (const char* sipaResponse = SetOPMNetworkConfig(targetMac, newIp, newMask))
	{
		std::printf("  SIPA response: %s\n", sipaResponse);
		FreeString(const_cast<char*>(sipaResponse));
	}
	else
	{
		std::printf("  SIPA command failed (timeout or error).\n");
	}

	// -------------------------------------------------------------------
	// Step 3, Query the temporary configuration (TIPA)
	//    This retrieves the in-memory config that has NOT yet been saved
	//    to flash.
	// -------------------------------------------------------------------
	std::printf("\n  Step 3: Querying temporary config via TIPA ...\n");
	if (const char* tipaResponse = QueryOPMTempConfig(); tipaResponse && std::strlen(tipaResponse) > 0)
	{
		std::printf("  TIPA response:\n%s\n", tipaResponse);
		FreeString(const_cast<char*>(tipaResponse));
	}
	else
	{
		std::printf("  No TIPA response.\n");
		if (tipaResponse) FreeString(const_cast<char*>(tipaResponse));
	}

	// -------------------------------------------------------------------
	// Step 4, Apply and save the configuration to flash (UIPC)
	//    This commits the temporary SIPA changes permanently.
	// -------------------------------------------------------------------
	std::printf("\n  Step 4: Applying config to flash via UIPC ...\n");
	std::printf("    Target MAC: %s\n", targetMac);

	if (const char* uipcResponse = ApplyOPMNetworkConfig(targetMac))
	{
		std::printf("  UIPC response: %s\n", uipcResponse);

		// Check if the MAC was found
		if (std::strstr(uipcResponse, "not found"))
			std::printf("  -> WARNING: MAC address was not found on the network.\n");
		else
			std::printf("  -> IP configuration successfully saved to flash.\n");

		FreeString(const_cast<char*>(uipcResponse));
	}
	else
	{
		std::printf("  UIPC command failed (timeout or error).\n");
	}

	printSeparator();
	std::printf("  Network demo complete.\n");
}
