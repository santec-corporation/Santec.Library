#!/usr/bin/env python3
"""How the ABI surface is read: from the C header and from the binary.

Both readers are shared because the same questions are asked in two places:

  * ``tools/check_abi.py`` (internal) compares the header, the managed sources
    and a freshly published DLL: three sources, one of which only exists in a
    repository that can build.
  * ``tools/check_bundle.py`` compares the header and the DLL of a shipped
    bundle, with no sources and no compiler involved. That is all the public
    repository has.

Two parsers for one contract would drift, so the header scanner and the PE
readers live here.

Usage
    from abi_surface import header_entry_points, pe_exports, pe_image
"""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

# Declaration lines in the C header: a known return type, a name, then "(".
HEADER_DECL = re.compile(
    r"^\s*(?:void|bool|char\s*\*|const\s+char\s*\*|double|int32_t|uint8_t|uint16_t|int64_t|uint32_t|float)"
    r"\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.MULTILINE,
)

# Symbols the NativeAOT toolchain adds to every native library. They are not part
# of our contract, so an "extra export" report has to ignore them.
RUNTIME_EXPORTS = {"DotNetRuntimeDebugHeader"}

MACHINES = {0x8664: "x64", 0x014C: "x86", 0xAA64: "arm64"}


def fail(message: str) -> None:
    """Report a malformed input the way the callers do: a message, then exit 1."""
    print(message, file=sys.stderr)
    raise SystemExit(1)


def header_entry_points(header: Path) -> set[str]:
    """The function names a C header declares.

    Members inside an enum or a macro are not declarations and are not matched,
    because the pattern requires a return type at the start of the line.
    """
    return set(HEADER_DECL.findall(header.read_text(encoding="utf-8", errors="replace")))


def pe_layout(data: bytes, path: Path) -> tuple[int, int, int, int]:
    """Offsets shared by the readers below: (COFF, optional header, directories, sections)."""
    if len(data) < 0x40:
        fail(f"{path} is too short to be a PE file")
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        fail(f"{path} is not a PE file")

    coff = e_lfanew + 4
    optional_size, = struct.unpack_from("<H", data, coff + 16)
    optional = coff + 20
    magic, = struct.unpack_from("<H", data, optional)
    directories = optional + (96 if magic == 0x10B else 112)
    return coff, optional, directories, optional + optional_size


def pe_image(path: Path) -> tuple[str, bool]:
    """The machine type of a PE file, and whether it carries a CLR header.

    A published library must be a native x64 image: a framework-dependent publish
    produces a managed assembly with the same name, which loads under .NET but
    exports nothing to a C caller.
    """
    data = path.read_bytes()
    coff, _, directories, _ = pe_layout(data, path)
    machine, = struct.unpack_from("<H", data, coff)
    # Data directory 14 is the COM descriptor, which only a managed image has.
    com_rva, com_size = struct.unpack_from("<II", data, directories + 14 * 8)
    return MACHINES.get(machine, f"0x{machine:04x}"), bool(com_rva and com_size)


def pe_exports(path: Path) -> list[str]:
    """Names in the PE export table. Handles PE32 and PE32+."""
    data = path.read_bytes()
    coff, _, directories, sections_base = pe_layout(data, path)

    section_count, = struct.unpack_from("<H", data, coff + 2)
    export_rva, export_size = struct.unpack_from("<II", data, directories)
    if export_rva == 0 or export_size == 0:
        return []  # no export table (a managed assembly, for instance)

    sections = []
    for index in range(section_count):
        base = sections_base + index * 40
        virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from("<IIII", data, base + 8)
        sections.append((virtual_address, virtual_size, raw_pointer))

    def to_offset(rva: int) -> int:
        for virtual_address, virtual_size, raw_pointer in sections:
            if virtual_address <= rva < virtual_address + max(virtual_size, 1):
                return raw_pointer + (rva - virtual_address)
        fail(f"RVA 0x{rva:x} is not inside any section of {path}")

    export = to_offset(export_rva)
    number_of_names, = struct.unpack_from("<I", data, export + 24)
    names_rva, = struct.unpack_from("<I", data, export + 32)
    names = to_offset(names_rva)

    exported = []
    for index in range(number_of_names):
        name_rva, = struct.unpack_from("<I", data, names + index * 4)
        start = to_offset(name_rva)
        end = data.index(b"\0", start)
        exported.append(data[start:end].decode("ascii", errors="replace"))
    return exported
