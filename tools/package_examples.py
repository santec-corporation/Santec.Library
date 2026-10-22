#!/usr/bin/env python3
"""Package each example in this repository as its own release asset.

The release workflow runs this for every version tag, so a release carries one
archive per example rather than a single bundle. Each archive holds the example
plus the SDK files it needs, laid out the way this repository lays them out, so
it can be built or run on its own:

  * the native examples get include/ and lib/win-x64/ (DLL and import library),
  * the managed examples get lib/win-x64/ (DLL),
  * each Python script gets the santec_library package, the Santec bindings and
    lib/win-x64/ (DLL).

Every archive carries the binary licence and the version manifest next to the
DLL. Build output (bin/, obj/, x64/, __pycache__) never travels.

Usage
    python tools/package_examples.py --version 1.8.0.2
    python tools/package_examples.py --version 1.8.0.2 --output dist
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = re.compile(r"^\d+(?:\.\d+){1,3}$")

#: Build residue that must never travel. examples/csharp/ has a committed obj/
#: directory, and anybody who built an example has more.
EXCLUDED_DIRS = {".git", ".vs", "bin", "obj", "x64", "__pycache__"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".pdb", ".user", ".suo", ".zip"}

#: The SDK files every archive carries, relative to the repository root.
SDK_LIBRARY = [
    "lib/win-x64/Santec.Library.dll",
    "lib/win-x64/LICENSE.txt",
    "lib/win-x64/versions.json",
]
IMPORT_LIBRARY = "lib/win-x64/Santec.Library.lib"
PYTHON_PACKAGE = ["python/santec_library", "python/Santec"]


@dataclass
class Example:
    """One archive: a slug for its name, the files it ships, and its readme."""

    slug: str
    members: list[tuple[Path, str]]
    readme: str


def version_of(root: Path) -> str:
    manifest = root / "lib" / "win-x64" / "versions.json"
    if not manifest.is_file():
        raise SystemExit(f"{manifest} not found: not a Santec.Library checkout")
    return str(json.loads(manifest.read_text(encoding="utf-8")).get("version", ""))


def travelling(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    return not (any(part in EXCLUDED_DIRS for part in relative.parts)
                or path.suffix.lower() in EXCLUDED_SUFFIXES)


def files_under(root: Path, directory: str) -> list[tuple[Path, str]]:
    """Every file under a repository directory, with its archive path."""
    base = root / directory
    if not base.is_dir():
        raise SystemExit(f"{base} is missing")
    return [(path, path.relative_to(root).as_posix())
            for path in sorted(base.rglob("*")) if path.is_file() and travelling(path, root)]


def sdk_library(root: Path, names: list[str]) -> list[tuple[Path, str]]:
    entries = []
    for name in names:
        path = root / name
        if not path.is_file():
            raise SystemExit(f"{path} is missing; the archives would not run")
        entries.append((path, name))
    return entries


def native_example(root: Path, directory: Path, version: str) -> Example:
    """A Visual Studio project: headers and both halves of the import library."""
    project = next(directory.glob("*.vcxproj"), None)
    if project is None:
        raise SystemExit(f"{directory} has no .vcxproj")
    members = files_under(root, directory.relative_to(root).as_posix())
    members += files_under(root, "include")
    members += sdk_library(root, SDK_LIBRARY + [IMPORT_LIBRARY])
    readme = f"""Santec.Library {version} - C++ example: {directory.name}

  examples/{directory.name}/   the example (open {project.name})
  include/                     SantecLibrary.h and SantecLibrary.hpp
  lib/win-x64/                 Santec.Library.dll, Santec.Library.lib, LICENSE.txt, versions.json

Build with Visual Studio 2022 or later, x64:

  msbuild examples\\{directory.name}\\{project.name} /p:Configuration=Release /p:Platform=x64

Run it with --help for the connection options. The project's relative paths are
the ones in this archive, so it builds without the repository.
"""
    return Example(slug=f"{directory.name}-sample", members=members, readme=readme)


def managed_example(root: Path, directory: Path, version: str) -> Example:
    """A .NET project: the native DLL is copied next to the executable."""
    project = next(directory.glob("*.csproj"), None)
    if project is None:
        raise SystemExit(f"{directory} has no .csproj")
    members = files_under(root, directory.relative_to(root).as_posix())
    members += sdk_library(root, SDK_LIBRARY)
    readme = f"""Santec.Library {version} - .NET example: {directory.name}

  examples/{directory.name}/   the example (open {project.name})
  lib/win-x64/                 Santec.Library.dll, LICENSE.txt, versions.json

Run it from this folder:

  dotnet run --project examples\\{directory.name}\\{project.name} -- --help

The project copies ..\\..\\lib\\win-x64\\Santec.Library.dll next to the executable,
which is the path it has inside this archive.
"""
    return Example(slug=f"{directory.name}-sample", members=members, readme=readme)


def python_example(root: Path, script: Path, version: str) -> Example:
    """One script plus the package and bindings it imports."""
    relative = script.relative_to(root)
    members = [(script, relative.as_posix())]
    for directory in PYTHON_PACKAGE:
        members += files_under(root, directory)
    members += sdk_library(root, SDK_LIBRARY)
    command = f"python {relative.as_posix().replace('/', chr(92))} --help"
    readme = f"""Santec.Library {version} - Python example: {relative.name}

  {relative.as_posix()}   the example
  python/santec_library/    the package the example imports
  python/Santec/            the FlatBuffers result bindings
  lib/win-x64/              Santec.Library.dll, LICENSE.txt, versions.json

Install the dependency once:

  pip install flatbuffers

Run it from this folder:

  {command}

A script that loads the DLL itself, such as agilent_integration.py, also takes
--dll lib\\win-x64\\Santec.Library.dll; the others find it in lib/win-x64 from
this folder.
"""
    return Example(slug="python-" + script.stem.replace("_", "-"), members=members, readme=readme)


def collect(root: Path, version: str) -> list[Example]:
    examples: list[Example] = []

    for directory in sorted((root / "examples").iterdir()):
        if not directory.is_dir() or not travelling(directory, root):
            continue
        if next(directory.glob("*.vcxproj"), None):
            examples.append(native_example(root, directory, version))
        elif next(directory.glob("*.csproj"), None):
            examples.append(managed_example(root, directory, version))

    for pattern in ("python/*.py", "python/examples/*.py"):
        for script in sorted(root.glob(pattern)):
            if script.is_file() and travelling(script, root):
                examples.append(python_example(root, script, version))

    if not examples:
        raise SystemExit("no examples found; nothing would be released")
    return examples


def write(example: Example, version: str, output: Path) -> Path:
    base = f"Santec.Library-{version}-{example.slug}"
    archive = output / f"{base}.zip"

    # A file reached twice by two rules is written once.
    members = {name: source for source, name in example.members}
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        bundle.writestr(f"{base}/README.txt", example.readme.replace("\r\n", "\n"))
        for name, source in sorted(members.items()):
            bundle.write(source, f"{base}/{name}")
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", help="the version to name the archives with; defaults to versions.json")
    parser.add_argument("--output", type=Path, default=ROOT / "dist", help="directory to write the archives into")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository to package; for a test run")
    args = parser.parse_args()

    root = args.root.resolve()
    version = args.version or version_of(root)
    if not VERSION.match(version):
        raise SystemExit(f"{version} is not a release version: expected two to four dot-separated numbers")

    examples = collect(root, version)
    args.output.mkdir(parents=True, exist_ok=True)
    for example in examples:
        archive = write(example, version, args.output)
        print(f"{archive.name}  {archive.stat().st_size:,} bytes")

    print(f"\n{len(examples)} example(s) packaged from {root} into {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
