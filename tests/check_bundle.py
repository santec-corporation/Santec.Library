#!/usr/bin/env python3
"""Check a shipped bundle: the binary, the headers and the manifest agree.

The public repository has no build. Everything that proves the committed DLL
matches the committed headers has to be checked against the files themselves, so
this reads a bundle directory and compares:

  * the DLL's PE image: native x64, no CLR header, so a framework-dependent
    build cannot be mistaken for the published library;
  * the DLL's export table against the function declarations in
    ``include/SantecLibrary.h``;
  * every sha256 in ``lib/win-x64/versions.json`` against the file it names;
  * the manifest against the contract in ``docs/repository-split-plan.md`` §5.2:
    version, ABI number, platform, supported OS, build commit, Python package;
  * that the Python package in the bundle is the version the manifest announces,
    and that ``python/pyproject.toml`` declares the version the package does;
  * that the binary licence travels with the files.

Text files are hashed in their LF form, because that is how a repository stores
them: a hash that only matched on one machine's line endings would fail the first
time someone verified a release from a different checkout.

``--write-manifest`` writes the manifest the check reads, so the format and the
hashing rules live here rather than being repeated in the release pipeline.

It runs in three places: the release pipeline, against the staged bundle before it
is published; the public repository's own CI, against the committed files; and the
public mirror, which takes a subset of the same files.

Usage
    python tools/check_bundle.py --root Santec.Library-1.8.0-win-x64
    python tools/check_bundle.py --write-manifest --root <bundle> --version 1.8.0 --built-from <sha>
    python tools/check_bundle.py                       # the repository itself

Exit code 0 when the bundle is consistent, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from hashlib import sha256
from pathlib import Path

from abi_surface import RUNTIME_EXPORTS, header_entry_points, pe_exports, pe_image

VERSION = re.compile(r"^\d+(?:\.\d+){1,3}$")
PACKAGE_VERSION = re.compile(r'^PACKAGE_VERSION\s*=\s*"([^"]+)"', re.MULTILINE)
PYPROJECT_VERSION = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)

#: Hashing a text file means hashing its LF form. Git normalises line endings on
#: the way into a repository, so a CRLF byte hash would only match on a checkout
#: that happens to use CRLF. A release should not depend on the machine that
#: verifies it. Binaries are hashed byte for byte.
TEXT_SUFFIXES = {".h", ".hpp", ".py", ".pyi", ".md", ".txt", ".json", ".toml", ".yml", ".yaml"}

#: The manifest fields that are not derived from the files.
MANIFEST_CONSTANTS = {"abi": 1, "platform": "win-x64", "supportedOs": "Windows 8 or later (x64)"}

#: What a bundle must contain, relative to its root.
REQUIRED = [
    "include/SantecLibrary.h",
    "include/SantecLibrary.hpp",
    "lib/win-x64/Santec.Library.dll",
    "lib/win-x64/Santec.Library.lib",
    "lib/win-x64/versions.json",
    "lib/win-x64/LICENSE.txt",
]

#: The files the manifest hashes. The two binaries and both headers: enough to
#: prove the committed binary matches the committed headers, which is all the
#: public repository can check without building anything.
HASHED = [
    "lib/win-x64/Santec.Library.dll",
    "lib/win-x64/Santec.Library.lib",
    "include/SantecLibrary.h",
    "include/SantecLibrary.hpp",
]

FAILURES: list[str] = []


def report(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILURES.append(f"{label}{': ' + detail if detail else ''}")


def digest(path: Path) -> str:
    """The sha256 a bundle records for a file.

    Text files are hashed with their line endings normalised to LF, which is how
    they are stored in the public repository. Everything else is hashed as it is.
    """
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n")
    return sha256(data).hexdigest()


def normalised(version: str) -> tuple[int, ...]:
    """A version as comparable numbers, so 1.8.0 and 1.8.0.0 are the same release."""
    parts = [int(part) for part in version.split(".")]
    return tuple(parts + [0] * (4 - len(parts)))


def summarise(names: list[str], limit: int = 5) -> str:
    """A name list short enough for a CI log line."""
    if len(names) <= limit:
        return str(names)
    return f"{names[:limit]} and {len(names) - limit} more"


def check_layout(root: Path) -> bool:
    missing = [name for name in REQUIRED if not (root / name).is_file()]
    report("bundle layout", not missing, f"missing: {missing}" if missing else f"{len(REQUIRED)} files")
    return not missing


def check_binary(dll: Path, header: Path) -> None:
    machine, managed = pe_image(dll)
    if managed:
        report("the DLL is the native library", False, "managed assembly with a CLR header")
        return
    report("the DLL is a native x64 image", machine == "x64", machine)

    declared = header_entry_points(header)
    exported = set(pe_exports(dll))
    absent = sorted(declared - exported)
    report(f"the DLL exports the {len(declared)} entry points of {header.name}",
           not absent, f"absent: {summarise(absent)}" if absent else "")
    extra = sorted(exported - declared - RUNTIME_EXPORTS)
    report("the DLL exports nothing the header does not declare", not extra,
           f"undeclared: {summarise(extra)}" if extra else "")


def check_manifest(root: Path) -> tuple[str, str]:
    """Check the manifest's fields and hashes. Returns (version, platform)."""
    path = root / "lib" / "win-x64" / "versions.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        report("the manifest is valid JSON", False, str(error))
        return "", ""
    if not isinstance(manifest, dict):
        report("the manifest is a JSON object", False, type(manifest).__name__)
        return "", ""

    version = str(manifest.get("version", ""))
    platform = str(manifest.get("platform", ""))
    report("the manifest carries a version", bool(VERSION.match(version)), version or "absent")
    for field, kind in (("abi", int), ("platform", str), ("supportedOs", str),
                        ("builtFrom", str), ("pythonPackage", str)):
        report(f"the manifest carries {field}", isinstance(manifest.get(field), kind) and bool(manifest.get(field)),
               str(manifest.get(field, "absent")))
    report("the manifest describes the bundle's platform", platform == "win-x64", platform or "absent")

    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        report("the manifest lists the files it hashes", False, "no 'files' object")
        return version, platform

    for name, expected in sorted(files.items()):
        member = root / name
        if not member.is_file():
            report(f"{name} is in the bundle", False, "listed in the manifest but absent")
        elif not isinstance(expected, str) or digest(member) != expected.lower():
            report(f"{name} matches its sha256", False, f"manifest {expected}")
        else:
            report(f"{name} matches its sha256", True)

    for name in HASHED:
        if name not in files:
            report(f"the manifest hashes {name}", False, "not listed")

    return version, platform


def check_python_package(root: Path, manifest_version: str) -> None:
    package = package_version(root)
    if not package:
        report("the bundle carries the Python package", False, f"not found: {root / 'python' / 'santec_library' / 'library.py'}")
        return

    report("the Python package is the announced version",
           normalised(package) == normalised(manifest_version) if VERSION.match(manifest_version) else False,
           f"package {package}, manifest {manifest_version}")

    # The version is declared twice: the distribution metadata pip reports, and the
    # string the package calls itself. A release that bumps one and not the other
    # passes every other check, so the two are compared here.
    declared = pyproject_version(root)
    report("pyproject.toml declares the version the package does",
           bool(declared) and normalised(declared) == normalised(package),
           f"pyproject {declared or 'absent'}, package {package}")


def package_version(root: Path) -> str:
    """The version the bundle's own Python package declares."""
    source = root / "python" / "santec_library" / "library.py"
    if not source.is_file():
        return ""
    match = PACKAGE_VERSION.search(source.read_text(encoding="utf-8", errors="replace"))
    return match.group(1) if match else ""


def pyproject_version(root: Path) -> str:
    """The version the distribution metadata declares, which pip reports."""
    source = root / "python" / "pyproject.toml"
    if not source.is_file():
        return ""
    match = PYPROJECT_VERSION.search(source.read_text(encoding="utf-8", errors="replace"))
    return match.group(1) if match else ""


def write_manifest(root: Path, version: str, built_from: str) -> int:
    """Write lib/win-x64/versions.json, the compatibility matrix the bundle ships."""
    if not VERSION.match(version):
        print(f"{version} is not a release version: expected two to four dot-separated numbers")
        return 1

    missing = [name for name in HASHED if not (root / name).is_file()]
    if missing:
        print(f"cannot describe the bundle: {root} is missing {missing}")
        return 1

    package = package_version(root)
    if not package:
        print(f"cannot describe the bundle: {root / 'python' / 'santec_library' / 'library.py'} "
              "is missing, so the Python package version is unknown")
        return 1

    manifest = {
        "version": version,
        **MANIFEST_CONSTANTS,
        "builtFrom": built_from,
        "pythonPackage": package,
        "files": {name: digest(root / name) for name in HASHED},
    }
    target = root / "lib" / "win-x64" / "versions.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {target}: {version}, {len(HASHED)} hashed files, python package {package}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="bundle directory to check (default: this repository)")
    parser.add_argument("--write-manifest", action="store_true",
                        help="write lib/win-x64/versions.json for the bundle in --root")
    parser.add_argument("--version", help="the version to record when writing the manifest")
    parser.add_argument("--built-from", default="", help="the commit the bundle was built from")
    args = parser.parse_args()

    root = args.root.resolve()

    if args.write_manifest:
        if not args.version:
            print("--write-manifest needs --version")
            return 1
        return write_manifest(root, args.version, args.built_from)

    print(f"checking {root}\n")

    if not check_layout(root):
        print("\nBUNDLE CHECK FAILED")
        for failure in FAILURES:
            print(f"  - {failure}")
        return 1

    check_binary(root / "lib" / "win-x64" / "Santec.Library.dll", root / "include" / "SantecLibrary.h")

    version, platform = check_manifest(root)
    check_python_package(root, version)

    print()
    if FAILURES:
        print(f"BUNDLE CHECK FAILED ({len(FAILURES)})")
        for failure in FAILURES:
            print(f"  - {failure}")
        return 1

    print(f"Bundle check passed: {version} ({platform}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
