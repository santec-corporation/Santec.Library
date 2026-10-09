#!/usr/bin/env python3
"""Load a published Santec.Library.dll the way a customer would, with no hardware.

This is the check that runs in CI on every release. It catches the failures a
build-only pipeline cannot see:

  * a DLL that only initialises when the process working directory happens to
    contain it (an earlier build killed the host process in that case), so the
    script deliberately runs from a temporary directory;
  * a SIMULATION build, because ``--expect-devices`` defaults to zero and a
    simulation build reports three mock instruments;
  * entry points that throw instead of returning their documented sentinel when
    nothing is connected;
  * a stale binary that predates entry points the header promises;
  * a binary whose version does not match the release it is being shipped as,
    which is what ``--expect-version <tag>`` checks.

Usage
    python tools/smoke_test.py --dll aot/Santec.Library.dll
    python tools/smoke_test.py --dll aot/Santec.Library.dll --expect-version v1.8.0
"""

from __future__ import annotations

import argparse
import ctypes
import os
import sys
import tempfile
from ctypes import CDLL, POINTER, c_bool, c_char_p, c_int, c_ubyte, c_void_p, byref

# Entry points a release must export, with their ctypes signatures. Keeping the
# list here means a binary built from older sources is reported as such instead
# of failing with a bare AttributeError.
SIGNATURES = {
    "GetDeviceNum": ([], c_int),
    "GetLibraryVersion": ([], c_void_p),
    "GetDevices": ([c_void_p, c_int], c_int),
    "ValidateParameters": ([], c_void_p),
    "ReferenceScan": ([POINTER(POINTER(c_ubyte)), POINTER(c_int)], c_bool),
    "EnableDebug": ([], None),
    "SetLogLevel": ([c_int], None),
    "Disconnect": ([], None),
    "FreeString": ([c_void_p], None),
    "FreeArrayData": ([c_void_p], None),
    "FreeConnectionConfigs": ([c_void_p, c_int], None),
}

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: object = "") -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail != "" else ""))
    if not ok:
        FAILURES.append(label)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dll", required=True, help="path to the published Santec.Library.dll")
    parser.add_argument("--expect-devices", type=int, default=0,
                        help="device count expected with no instruments attached (default 0)")
    parser.add_argument("--expect-version", help="version the DLL must report, e.g. the release tag")
    args = parser.parse_args()

    dll_path = os.path.abspath(args.dll)
    if not os.path.isfile(dll_path):
        print(f"not found: {dll_path}")
        return 2

    # Deliberately move away from the DLL's directory before loading it: a
    # customer's process will not be running there either.
    os.chdir(tempfile.mkdtemp(prefix="santec-smoke-"))
    print(f"loading {dll_path}\nfrom   {os.getcwd()}\n")

    lib = CDLL(dll_path)

    missing = []
    for name, (argtypes, restype) in SIGNATURES.items():
        try:
            function = getattr(lib, name)
        except AttributeError:
            missing.append(name)
            continue
        function.argtypes = argtypes
        function.restype = restype
    if missing:
        print(f"FAIL: {os.path.basename(dll_path)} does not export: {', '.join(missing)}")
        print("      The binary is older than the header it ships with.")
        return 1

    # 1. The version query answers, and the string frees cleanly.
    ptr = lib.GetLibraryVersion()
    version = ctypes.cast(ptr, c_char_p).value.decode("utf-8", "replace") if ptr else ""
    check("GetLibraryVersion returns a non-empty version", bool(version), version)
    if ptr:
        lib.FreeString(ptr)

    if args.expect_version:
        expected = args.expect_version.lstrip("vV")
        check(f"the binary reports the released version {expected}", version == expected, version)

    # 2. Device enumeration works without any instrument attached.
    count = lib.GetDeviceNum()
    check(f"GetDeviceNum == {args.expect_devices}", count == args.expect_devices, f"got {count}")

    # 3. Validation reports "nothing to validate" rather than failing.
    check("ValidateParameters returns NULL with no device connected", not lib.ValidateParameters())

    # 4. Scanning with no instrument returns false instead of throwing.
    data = POINTER(c_ubyte)()
    length = c_int(0)
    check("ReferenceScan returns false with no instrument connected",
          not lib.ReferenceScan(byref(data), byref(length)))

    # 5. The free functions tolerate NULL, so callers can call them unconditionally.
    lib.FreeString(None)
    lib.FreeArrayData(None)
    lib.FreeConnectionConfigs(None, 0)
    check("free functions accept NULL", True)

    # 6. Logging setup and teardown do not crash.
    lib.EnableDebug()
    lib.SetLogLevel(4)  # Serilog Error
    lib.Disconnect()
    check("EnableDebug / SetLogLevel / Disconnect complete", True)

    print()
    if FAILURES:
        print(f"SMOKE TEST FAILED ({len(FAILURES)} check(s))")
        for failure in FAILURES:
            print(f"  - {failure}")
        return 1

    print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
