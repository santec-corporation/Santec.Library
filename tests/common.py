#!/usr/bin/env python3
"""What the tools share: the repository path, versions, text files, and the check report.

Each tool under ``tools/`` is a script that ends in ``main()``, and several of them
need the same small rules: where the repository is, how a version compares, which
files count as text, and how a check reports itself. This module holds those rules
once. It imports nothing else from ``tools/``, so a check tool and a release tool
both depend on it without depending on each other.

Usage
    from common import REPO, public_root, report, version_tuple
"""

from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: The sibling names a public checkout can carry, in the order the tools try them.
SIBLING_NAMES = ("Santec.Library.Public", "Santec.Library", "public")

#: How a release version is spelled: two to four dot-separated numbers.
VERSION_PATTERN = re.compile(r"^\d+(?:\.\d+){1,3}$")

#: A tag carries a leading v or V that the version inside it does not.
TAG_PREFIX = re.compile(r"^[vV]")

#: Hashing or writing a text file means using its LF form. Git normalises line
#: endings on the way into a repository, so a CRLF byte hash only matches a checkout
#: that happens to use CRLF, and a release should not depend on that.
TEXT_SUFFIXES = {".c", ".h", ".hpp", ".py", ".pyi", ".md", ".txt", ".json", ".toml", ".yml", ".yaml"}

FAILURES: list[str] = []


def public_root(sentinel: str) -> Path:
    """The public checkout: the sibling that holds ``sentinel``, or the fallback path.

    This repository carries one of the candidate names as well, because the internal
    clone is often called Santec.Library too, so the search drops it: a check that
    compared the tree with itself would pass every file.
    """
    candidates = [REPO.parent / name for name in SIBLING_NAMES]
    candidates = [candidate for candidate in candidates if candidate.resolve() != REPO]
    for candidate in candidates:
        if (candidate / sentinel).is_dir():
            return candidate
    return candidates[0] if candidates else REPO.parent / "public"


def version_tuple(version: str) -> tuple[int, ...]:
    """A version as comparable numbers, so 1.8 and 1.8.0.0 name one release."""
    parts = [int(part) for part in version.split(".")]
    return tuple(parts + [0] * (4 - len(parts)))


def is_text(path: Path) -> bool:
    """Whether a file holds text, so its hash and its written form use LF.

    ``TEXT_SUFFIXES`` names the formats a bundle carries. A dot file such as
    ``python/.gitignore`` carries no suffix at all and holds text all the same:
    both repositories store it with LF, and a byte hash of a Windows checkout
    would never match the blob.
    """
    return path.suffix.lower() in TEXT_SUFFIXES or (not path.suffix and path.name.startswith("."))


def as_lf(content: bytes) -> bytes:
    """The bytes as git stores text, so a CRLF checkout compares equal."""
    return content.replace(b"\r\n", b"\n")


def digest(path: Path) -> str:
    """The sha256 the manifest and the sync record keep for a file."""
    data = path.read_bytes()
    return sha256(as_lf(data) if is_text(path) else data).hexdigest()


def report(label: str, ok: bool, detail: str = "") -> None:
    """Print one check line and remember a failure for the exit code."""
    print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILURES.append(f"{label}{': ' + detail if detail else ''}")
