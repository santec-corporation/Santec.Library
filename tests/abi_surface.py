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

# An exported managed method: the attribute that exports it, then the method, which
# takes the entry point's name. The backreference ties the two together, so the
# scanner skips a method whose name disagrees with its attribute.
MANAGED_SIGNATURE = re.compile(
    r'\[UnmanagedCallersOnly\(EntryPoint\s*=\s*"(?P<name>[A-Za-z0-9_]+)"\)\]'
    r"\s*public\s+static\s+(?:unsafe\s+)?(?P<returns>[A-Za-z_][A-Za-z0-9_*]*)\s+(?P=name)\s*\(",
)

# A declaration in either header: the return type, then the name and its parameter
# list. One pattern reads SantecLibrary.h and SantecLibrary.hpp, which differ only in
# how they spell an empty parameter list, "()" against "(void)".
SIGNATURE = re.compile(
    r"^\s*(?P<returns>void|bool|char\s*\*|const\s+char\s*\*|double|int32_t|uint8_t|uint16_t|int64_t|uint32_t|float)"
    r"\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
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
    return set(header_signatures(header))


def parenthesised(text: str, opening: int) -> str:
    """The text between the parenthesis at ``opening`` and the one that closes it."""
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return text[opening + 1:index]
    fail("a declaration has unbalanced parentheses")


def top_level_parameters(arguments: str) -> list[str]:
    """A parameter list split at the commas that separate parameters.

    A comma inside a nested bracket, such as the one in a function pointer, does not
    separate: the scanner counts the depth. "void" and an empty list declare none.
    """
    text = arguments.strip()
    if not text or text == "void":
        return []

    parameters, depth, current = [], 0, ""
    for character in text:
        if character in "([{":
            depth += 1
        elif character in ")]}":
            depth -= 1
        if character == "," and depth == 0:
            parameters.append(current)
            current = ""
        else:
            current += character
    parameters.append(current)
    return [parameter.strip() for parameter in parameters if parameter.strip()]


def c_type(text: str) -> str:
    """A C type with its spacing normalised.

    ``const char *`` and ``const char*`` are one type, and the two headers write
    them both ways in places.
    """
    return re.sub(r"\s*\*\s*", "*", " ".join(text.split()))


def parameter_types(arguments: str) -> tuple[str, ...]:
    """The types a parameter list declares, with the parameter names dropped.

    A parameter is written "type name", so everything before the last identifier is
    the type. A parameter that is only a type keeps all of itself.
    """
    types = []
    for parameter in top_level_parameters(arguments):
        match = re.match(r"^(?P<type>.*?)\s*[A-Za-z_][A-Za-z0-9_]*$", parameter)
        stated = match.group("type") if match and match.group("type").strip() else parameter
        types.append(c_type(stated))
    return tuple(types)


def header_signatures(header: Path) -> dict[str, tuple[str, tuple[str, ...]]]:
    """The return type and parameter types of every declaration in a header.

    Two declarations of one name must state one signature: a header holding two
    cannot tell a caller which one the binary implements.
    """
    text = header.read_text(encoding="utf-8", errors="replace")
    signatures: dict[str, tuple[str, tuple[str, ...]]] = {}
    for match in SIGNATURE.finditer(text):
        name = match.group("name")
        signature = (c_type(match.group("returns")),
                     parameter_types(parenthesised(text, match.end() - 1)))
        if name in signatures and signatures[name] != signature:
            fail(f"{header.name} declares {name} with two different signatures")
        signatures[name] = signature
    return signatures


def managed_signatures(*sources: Path) -> dict[str, tuple[str, tuple[str, ...]]]:
    """The return type and parameter types of every exported managed method."""
    signatures: dict[str, tuple[str, tuple[str, ...]]] = {}
    for source in sources:
        text = source.read_text(encoding="utf-8", errors="replace")
        for match in MANAGED_SIGNATURE.finditer(text):
            signatures[match.group("name")] = (
                c_type(match.group("returns")),
                parameter_types(parenthesised(text, match.end() - 1)),
            )
    return signatures


def header_arities(header: Path) -> dict[str, int]:
    """The parameter count every declaration in a header states."""
    return {name: len(parameters) for name, (_, parameters) in header_signatures(header).items()}


def managed_arities(*sources: Path) -> dict[str, int]:
    """The parameter count every ``[UnmanagedCallersOnly]`` method declares."""
    return {name: len(parameters) for name, (_, parameters) in managed_signatures(*sources).items()}


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
