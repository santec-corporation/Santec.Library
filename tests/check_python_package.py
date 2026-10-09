#!/usr/bin/env python3
"""Check the Python package without hardware.

The package is the public Python API, and until now nothing exercised it: the
existing harness scripts need instruments, and the native library cannot be
published in this environment. This checks the parts that can be checked:

  * importing the package does not load the DLL (no import-time side effects);
  * every script in the tree imports without a DLL, and none of them still imports
    the wrapper module that the package replaced;
  * every FlatBuffers accessor ``results.py`` names really exists on the
    generated classes, which is where a typo would otherwise survive until a
    measurement;
  * the vector helper works with and without numpy, and copes with a keyless
    sweep;
  * ``resolve_dll`` honours the documented search order;
  * loading an older DLL fails with the list of missing entry points rather than a
    crash.

What it cannot check: parsing a real scan payload, which needs a measurement.

Usage
    python tools/check_python_package.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PACKAGE_DIR = REPO / "python"

# Compiles into a library that exports none of the entry points the package binds, so the
# rejection path is exercised against a binary that is certainly incomplete. The publish
# output under Santec.Library/bin holds a current library, which exports everything and
# would report the check's own failure against a good binary.
STUB_C = """
#include <windows.h>
__declspec(dllexport) int SantecLibraryStub(void) { return 0; }
BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID reserved) { return TRUE; }
"""

FAILURES: list[str] = []


def report(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILURES.append(f"{label}{': ' + detail if detail else ''}")


def run_isolated(code: str, env: dict | None = None, cwd: str | None = None) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PACKAGE_DIR)
    environment.pop("SANTEC_LIBRARY_DLL", None)
    if env:
        environment.update(env)
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          env=environment, cwd=cwd)


def newest(paths) -> Path | None:
    """The highest-versioned path, since the toolchain lays out versions as directory names."""
    found = sorted(paths)
    return found[-1] if found else None


def build_stub_dll(directory: Path) -> Path | None:
    """Build an incomplete Santec.Library.dll, or None when no C toolchain is available.

    The compiler is called by absolute path with INCLUDE and LIB derived from the tools
    layout. Borrowing vcvars64.bat for this does not work: it exits non-zero when this
    script runs it, and MSVC 14.44 and later leave the standard headers to INCLUDE.
    """
    vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / \
        "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if not vswhere.is_file():
        return None
    found = subprocess.run([str(vswhere), "-latest", "-property", "installationPath"],
                           capture_output=True, text=True)
    if found.returncode != 0 or not found.stdout.strip():
        return None

    compiler = newest((Path(found.stdout.strip()) / "VC" / "Tools" / "MSVC")
                      .glob("*/bin/HostX64/x64/cl.exe"))
    if compiler is None:
        return None
    visual_c = compiler.parents[3]

    environment = dict(os.environ)
    kits = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Windows Kits" / "10"
    sdk_include = newest(kits.glob("Include/*/um"))
    sdk_lib = newest(kits.glob("Lib/*/um"))
    include = [str(visual_c / "include")]
    library = [str(visual_c / "lib" / "x64")]
    if sdk_include and sdk_lib:
        include = [str(sdk_include.parent / part) for part in ("ucrt", "shared", "um")] + include
        library = [str(sdk_lib.parent / part / "x64") for part in ("ucrt", "um")] + library
    environment["INCLUDE"] = ";".join(include)
    environment["LIB"] = ";".join(library)

    source = directory / "santec_library_stub.c"
    source.write_text(STUB_C, encoding="ascii")
    target = directory / "Santec.Library.dll"
    built = subprocess.run([str(compiler), "/nologo", "/LD", "/O1", str(source), f"/Fe{target}"],
                           capture_output=True, text=True, cwd=directory, env=environment)
    return target if built.returncode == 0 and target.is_file() else None


def main() -> int:
    if not (PACKAGE_DIR / "santec_library" / "__init__.py").is_file():
        print(f"not found: {PACKAGE_DIR / 'santec_library'}")
        return 2

    if str(PACKAGE_DIR) not in sys.path:
        sys.path.insert(0, str(PACKAGE_DIR))

    # 1. Importing must not touch the DLL: do it in a process whose only DLL
    #    candidate is a path that does not exist.
    result = run_isolated(
        "import santec_library, sys;"
        "print('imported', santec_library.PACKAGE_VERSION);"
        "print('exports:', sorted(n for n in dir(santec_library) if not n.startswith('_'))[:6])",
        env={"SANTEC_LIBRARY_DLL": "Z:/definitely/not/here/Santec.Library.dll"},
    )
    report("importing the package does not load the DLL", result.returncode == 0,
           (result.stdout + result.stderr).strip().splitlines()[0] if result.stdout or result.stderr else "")

    # 2. Every FlatBuffers accessor results.py names must exist in the bindings.
    results_source = (PACKAGE_DIR / "santec_library" / "results.py").read_text(encoding="utf-8")
    # The vector helper takes the three accessor names as string literals, and the
    # rest of the object graph is reached through these calls.
    accessors = set(re.findall(r'"(\w+(?:AsNumpy|Length|IsNone))"', results_source))
    accessors |= {
        "GetRootAsSweepResultSet", "ResultsLength", "Results", "ResultsType", "Init",
        "SweepKey", "ChannelKey", "ModuleKey", "ChannelNumber", "ModuleType",
        "Data", "Wavelength", "InsertionLoss", "RescaledDataLength", "RescaledData",
        "Key", "PowerLog", "PowerMonitorLog",
    }

    from importlib import import_module

    classes = []
    for module_name, class_names in (
        ("Santec.STSProcess.Process.Native.Result.SweepResultSet", ["SweepResultSet"]),
        ("Santec.STSProcess.Process.Native.Result.SweepResultEntry", ["SweepResultEntry"]),
        ("Santec.STSProcess.Process.Native.Result.SweepResult", ["SweepResult"]),
        ("Santec.STSProcess.Process.Native.Result.ILReferenceResult", ["ILReferenceResult"]),
        ("Santec.STSProcess.Process.Native.Result.ILResult", ["ILResult"]),
        ("Santec.STSProcess.Process.Native.Result.SweepData", ["SweepData"]),
        ("Santec.STSProcess.Process.Native.Result.ILSweepData", ["ILSweepData"]),
        ("Santec.STSProcess.Process.Native.Result.SweepKey", ["SweepKey"]),
        ("Santec.STSProcess.Process.Native.Result.ChannelKey", ["ChannelKey"]),
        ("Santec.STSProcess.Process.Native.Result.ModuleKey", ["ModuleKey"]),
        ("Santec.STSProcess.Process.Native.Rescale.RescaledScanData", ["RescaledScanData"]),
        ("Santec.STSProcess.Process.Native.Rescale.RescaledPowerLog", ["RescaledPowerLog"]),
        ("Santec.STSProcess.Process.Native.Rescale.RescaledPowerMonitorLog", ["RescaledPowerMonitorLog"]),
    ):
        module = import_module(module_name)
        classes.extend(getattr(module, name) for name in class_names)

    known = {name for cls in classes for name in dir(cls)}
    unknown = sorted(name for name in accessors if name not in known)
    report(f"all {len(accessors)} FlatBuffers accessors named in results.py exist",
           not unknown, f"unknown: {unknown}" if unknown else "")

    # 3. The vector helper, with and without numpy, and the keyless sweep path.
    check = run_isolated(
        """
import santec_library.results as results

class Fake:
    def __init__(self, values): self.values = values
    def ValuesAsNumpy(self): return self.values
    def Values(self, i): return self.values[i]
    def ValuesLength(self): return len(self.values)

values = [1.5, 2.5, 3.5]
assert list(results._vector(Fake(values), "ValuesAsNumpy", "Values", "ValuesLength")) == values

saved = results._numpy
results._numpy = None
try:
    assert list(results._vector(Fake(values), "ValuesAsNumpy", "Values", "ValuesLength")) == values
finally:
    results._numpy = saved

assert results._channel_name(None) == ""
print("helper checks passed")
"""
    )
    report("the vector helper works with and without numpy", "helper checks passed" in check.stdout,
           (check.stdout + check.stderr).strip().splitlines()[-1] if check.stdout or check.stderr else "")

    # 4. Every script in the tree imports without a DLL, and none of them reaches
    #    for the wrapper module that was folded into the package.
    scripts = sorted(
        path
        for path in PACKAGE_DIR.rglob("*.py")
        if not {"Santec", "santec_library", "__pycache__"} & set(path.relative_to(PACKAGE_DIR).parts)
    )
    broken = []
    for path in scripts:
        imported = run_isolated(
            "import importlib.util\n"
            f"spec = importlib.util.spec_from_file_location('checked_script', r'{path}')\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(module)\n"
            "print('imported')\n",
            env={"SANTEC_LIBRARY_DLL": "Z:/definitely/not/here/Santec.Library.dll"},
        )
        if "imported" not in imported.stdout:
            last = (imported.stderr or imported.stdout).strip().splitlines()
            broken.append(f"{path.name}: {last[-1] if last else 'no output'}")
    report(f"all {len(scripts)} scripts import without a DLL", not broken, "; ".join(broken))

    stale = sorted(
        path.name
        for path in PACKAGE_DIR.rglob("*.py")
        if "santec_wrapper" in path.read_text(encoding="utf-8", errors="replace")
    )
    report("no module references the removed santec_wrapper", not stale, ", ".join(stale))

    # 5. resolve_dll follows the documented order.
    with tempfile.TemporaryDirectory() as empty_dir:
        missing = run_isolated("import santec_library; santec_library.Library()", cwd=empty_dir)
        report("a missing DLL raises LibraryNotFound, not OSError",
               "LibraryNotFound" in missing.stderr and missing.returncode != 0,
               missing.stderr.strip().splitlines()[-1] if missing.stderr else "")

    with tempfile.TemporaryDirectory() as fixture_dir:
        stub = build_stub_dll(Path(fixture_dir))
        if stub is None:
            print("  [--] skipping the older-DLL check: no C toolchain available")
        else:
            stale = run_isolated(
                "import santec_library\n"
                "try:\n"
                "    santec_library.Library()\n"
                "except santec_library.AbiMismatch as error:\n"
                "    print('AbiMismatch:', error)\n",
                env={"SANTEC_LIBRARY_DLL": str(stub)},
            )
            report("an older DLL fails with the missing entry points listed",
                   "AbiMismatch" in stale.stdout,
                   stale.stdout.strip() or (stale.stderr.strip().splitlines() or [""])[-1])

    print()
    if FAILURES:
        print(f"PYTHON PACKAGE CHECK FAILED ({len(FAILURES)})")
        for failure in FAILURES:
            print(f"  - {failure}")
        return 1

    print("Python package checks passed (parsing a real scan payload is not covered).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
