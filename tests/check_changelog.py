#!/usr/bin/env python3
"""Check that every released version has a changelog section.

``lib/<platform>/versions.json`` names the release a bundle carries, and
``CHANGELOG.md`` is the record a reader consults for it. Nothing in the release job
edits the changelog, so a tag can ship while its section still says Unreleased; that
happened to 1.8.0.7 and to 1.8.0.10. This check closes that gap:

  * every version a bundle names has a ``## [<version>] - <date>`` section;
  * each release heading carries an ISO date and appears once;
  * release headings run newest first, with Unreleased above them;
  * no section is empty.

Usage
    python tests/check_changelog.py
    python tests/check_changelog.py --root <checkout>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from common import FAILURES, base_version, report, version_tuple

REPO = Path(__file__).resolve().parent.parent

#: A level-two heading, optionally carrying the date a release was cut.
HEADING = re.compile(r"^##[ \t]+\[([^\]]+)\](?:[ \t]+-[ \t]+(\d{4}-\d{2}-\d{2}))?[ \t]*$",
                     re.MULTILINE)

#: The heading Keep a Changelog reserves for work that has no release yet.
UNRELEASED = "Unreleased"


class Entry:
    """One level-two section of the changelog."""

    def __init__(self, name: str, date: str | None, body: str) -> None:
        self.name = name
        self.date = date
        self.body = body

    @property
    def released(self) -> bool:
        return self.name != UNRELEASED


def sections(text: str) -> list[Entry]:
    """The changelog's level-two sections, in file order."""
    matches = list(HEADING.finditer(text))
    entries = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        entries.append(Entry(match.group(1), match.group(2), text[match.end():end]))
    return entries


def bundle_versions(root: Path) -> list[tuple[str, str]]:
    """The (platform, version) pairs the committed manifests name."""
    found = []
    for manifest in sorted((root / "lib").glob("*/versions.json")):
        try:
            version = str(json.loads(manifest.read_text(encoding="utf-8")).get("version", ""))
        except json.JSONDecodeError:
            version = ""
        found.append((manifest.parent.name, version))
    return found


def check_versions(entries: list[Entry], versions: list[tuple[str, str]]) -> None:
    """Every version a bundle names has a section."""
    if not versions:
        report("a bundle manifest exists", False, "no lib/<platform>/versions.json")
        return

    unnamed = [platform for platform, version in versions if not version]
    report("every manifest names a version", not unnamed,
           "no version in " + ", ".join(unnamed) if unnamed else "")

    names = {entry.name for entry in entries}
    missing = [f"{base_version(version)} ({platform})" for platform, version in versions
               if version and base_version(version) not in names]
    named = ", ".join(base_version(version) for _, version in versions if version)
    report(f"every bundle version has a section ({named})", not missing,
           "no section for " + ", ".join(missing) if missing else "")


def check_headings(entries: list[Entry]) -> None:
    """The headings are well formed, unique, and ordered."""
    unreleased = [entry for entry in entries if not entry.released]
    released = [entry for entry in entries if entry.released]

    report("the file has an Unreleased section", len(unreleased) == 1,
           "found none" if not unreleased else f"found {len(unreleased)}")
    report("Unreleased sits above the releases",
           bool(unreleased) and entries[0] is unreleased[0],
           f"first heading is [{entries[0].name}]" if entries else "no headings")

    undated = [entry.name for entry in released if not entry.date]
    report("every release heading carries a date", not undated,
           "no date on " + ", ".join(f"[{name}]" for name in undated) if undated else "")

    seen: set[str] = set()
    duplicates: set[str] = set()
    for entry in released:
        if entry.name in seen:
            duplicates.add(entry.name)
        seen.add(entry.name)
    report("no release heading appears twice", not duplicates,
           "repeated " + ", ".join(f"[{name}]" for name in sorted(duplicates))
           if duplicates else "")

    out_of_order = [f"[{earlier.name}] before [{later.name}]"
                    for earlier, later in zip(released, released[1:])
                    if earlier.name != later.name
                    and version_tuple(earlier.name) <= version_tuple(later.name)]
    report("release headings run newest first", not out_of_order,
           "; ".join(out_of_order[:3]) if out_of_order else "")


def check_bodies(entries: list[Entry]) -> None:
    """No section is an empty stub."""
    empty = [entry.name for entry in entries if not entry.body.strip()]
    report("every section carries text", not empty,
           "empty " + ", ".join(f"[{name}]" for name in empty) if empty else "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=REPO,
                        help="the checkout to check (default: this repository)")
    args = parser.parse_args()

    root = args.root.resolve()
    changelog = root / "CHANGELOG.md"
    if not changelog.is_file():
        print(f"no CHANGELOG.md in {root}")
        report("CHANGELOG.md exists", False, str(changelog))
        return 1

    print(f"checking {root}\n")
    entries = sections(changelog.read_text(encoding="utf-8"))
    report("the changelog has level-two sections", bool(entries),
           "no '## [...]' heading" if not entries else f"{len(entries)} sections")

    check_versions(entries, bundle_versions(root))
    check_headings(entries)
    check_bodies(entries)

    print()
    if FAILURES:
        print(f"CHANGELOG CHECK FAILED ({len(FAILURES)})")
        for failure in FAILURES:
            print(f"  - {failure}")
        return 1

    released = [entry.name for entry in entries if entry.released]
    print("Changelog check passed: the newest released section is "
          f"{max(released, key=version_tuple)}." if released
          else "Changelog check passed: no release sections yet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
