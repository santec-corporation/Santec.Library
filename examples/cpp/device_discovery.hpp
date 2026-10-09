#pragma once

#include "SantecLibrary.hpp"
#include <cstdio>

// ---------------------------------------------------------------------------
// device_discovery.hpp
// Discovers devices and fills the provided vectors.
// ---------------------------------------------------------------------------

/**
 * Prints all discovered devices and returns them in @p outDevices.
 * Returns the number of devices found.
 */
int discoverDevices(ConnectionConfig* outDevices, int maxDevices);
