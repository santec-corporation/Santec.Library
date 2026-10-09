#include "device_discovery.hpp"
#include "sample_helpers.hpp"
#include <cstring>
#include <algorithm>

int discoverDevices(ConnectionConfig* outDevices, const int maxDevices)
{
	std::printf("\n[Device Discovery]\n");
	printSeparator();

	const int32_t count = GetDeviceNum();
	std::printf("  Devices found: %d\n", count);

	if (count <= 0)
	{
		std::printf("  No devices detected. Check cables and driver installation.\n");
		return 0;
	}

	const int32_t toRead = count < maxDevices ? count : maxDevices;
	// The library never writes more than the capacity, and it allocates the
	// strings inside each entry: release them once they have been printed.
	const int32_t written = GetDevices(outDevices, toRead);

	for (int32_t i = 0; i < written; ++i)
	{
		const auto& [Type, VendorName, ProductName, Address, ProductNumber, SerialNumber, FirmwareVersion] =
			outDevices[i];
		std::printf("\n  Device[%d]\n", i);
		std::printf("    Type            : %s\n", Type ? Type : "(null)");
		std::printf("    VendorName      : %s\n", VendorName ? VendorName : "(null)");
		std::printf("    ProductName     : %s\n", ProductName ? ProductName : "(null)");
		std::printf("    Address         : %s\n", Address ? Address : "(null)");
		std::printf("    ProductNumber   : %d\n", ProductNumber);
		std::printf("    SerialNumber    : %s\n", SerialNumber ? SerialNumber : "(null)");
		std::printf("    FirmwareVersion : %s\n", FirmwareVersion ? FirmwareVersion : "(null)");
	}

	FreeConnectionConfigs(outDevices, written);

	return written;
}
