# Security policy

## Reporting a vulnerability

Please report privately, either through GitHub's [Security Advisories][advisory]
tab on this repository or by email to the address below. Do not open a public
issue.

**Contact:** *(placeholder, the security contact address must be filled in before
this repository is published)*

Include the library version (`GetLibraryVersion()`), what you observed, and how to
reproduce it. If the report involves an instrument, say which model and how it was
connected.

[advisory]: https://github.com/santec-corporation/Santec.Library/security/advisories/new

## Scope

In scope:

- `lib/win-x64/Santec.Library.dll` and `Santec.Library.lib`;
- the declarations in `include/`;
- the examples in `examples/` and `python/`.

Out of scope: vulnerabilities in the instrument drivers (NI-VISA, NI-DAQmx, IVI,
Keysight VISA, FTDI D2XX), report those to their vendors. We will help you work
out which component is at fault.

## What to expect

This SDK is provided without a support commitment (Article 19 of the binary
licence), and security reports are handled on a best-effort basis. We will
acknowledge a report, tell you whether we can reproduce it, and keep you informed
until it is resolved. We do not offer a response-time guarantee, and we will not
run a paid bounty programme.

## A published binary cannot be withdrawn

This matters for how a fix reaches you. Once a release is published, its files
stay available in tags, clones and forks, deleting them is not possible. So when
a release has a security defect we:

1. publish a fixed version and say so in `CHANGELOG.md`;
2. publish a GitHub Security Advisory naming the affected versions;
3. mark the affected version deprecated in the release notes.

Anyone who has already copied the binary has to update to the fixed version. If
your product embeds the library, treat a security release as you would any other
dependency update, and verify the file hash against `lib/win-x64/versions.json`
after updating.

## Laser safety

The library drives lasers. A defect that could cause unintended emission, defeat
an interlock, or leave the source on after a failure is a security report, and
should be sent privately like any other.
