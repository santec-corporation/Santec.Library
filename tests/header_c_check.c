/*
 * Proves that SantecLibrary.h is usable from a C compiler, which the C++ sample
 * cannot show: it compiles the same header as C++.
 *
 * Run it with MSVC (there is nothing to link, this only needs to compile):
 *
 *   cl /nologo /TC /W3 /Zs /I Santec.Library tools\header_c_check.c
 *
 * The release job runs exactly that, and the public repository runs it against the
 * published header as `cl ... /Zs /I include tests\header_c_check.c`, where this
 * file is mirrored.
 *
 * /TC forces C. If this stops compiling, the header has grown C++-only syntax
 * again - most likely a fixed underlying type on an enum, which is why those are
 * wrapped in #ifdef __cplusplus with an integer typedef for C.
 */

#include "SantecLibrary.h"

#include <stdio.h>

int main(void)
{
    ConnectionConfig devices[4];
    int32_t written;

    SetLogLevel(LogEventLevel_Information);

    /* The C forms of the enums: prefixed names, integer-typed constants. */
    SetWavelength(NominalWavelength_Wl1550);
    SetOPMRangeMode("SN00000", OPMRangeMode_AutoRange);
    SetOPMGain("SN00000", OPMGain_Gain2);
    SetOPMReadValidation("SN00000", 1);
    SetPCUSOP(PolarizationState_LVP);

    written = GetDevices(devices, 4);
    FreeConnectionConfigs(devices, written);

    printf("%d %.3f\n", (int)written, GetOPMReadMaxDeltaDb("SN00000"));
    return 0;
}
