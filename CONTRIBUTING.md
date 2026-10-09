# Contributing

Thanks for taking the time to help. This repository is the distribution side of
the SDK: it holds prebuilt binaries plus the header, examples and documentation
that go with them. Please read the first section before opening a pull request,
because part of the tree is generated and cannot be edited here.

## What is generated, and what you can change

| Path | Owner | Pull requests |
|---|---|---|
| `lib/` | release pipeline | **Not accepted.** The binaries, `versions.json` and the binary licence are written by the release job. A change here is overwritten by the next release. |
| `include/` | release pipeline | **Not accepted**, for the same reason: the header is published from the internal repository, and the reference in `docs/abi-reference.md` is generated from it. |
| `docs/abi-reference.md` | release pipeline | **Not accepted**, generated from the header. |
| `docs/`, `README.md`, `CHANGELOG.md` | maintainers + community | Welcome: corrections, clarifications, better examples. |
| `examples/`, `python/` | maintainers + community | Welcome: bug fixes and improvements. |
| `.github/` | maintainers | Ask first. |

If you need a change to the header or the binary, please open an issue instead:
those changes are made in the internal repository and arrive here with the next
release.

## Reporting a bug

Include:

1. the output of `GetLibraryVersion()`;
2. your platform (Windows version, architecture);
3. which instruments and which drivers are installed (NI-VISA, NI-DAQmx, FTDI);
4. the relevant part of `%APPDATA%\Santec\SantecLibrary\logs` (call
   `EnableDebug()` first for detail);
5. a minimal reproduction, for Python, a script; for C++, a snippet.

A report that names the library version and shows the log usually takes one
exchange to resolve. Without them it rarely does.

## Pull request expectations

- **Examples must run.** If you touch `examples/` or `python/`, say how you ran
  it. Hardware-dependent code is fine: state what you could and could not test.
- **Python:** 3.10 or later, standard library only. The scripts load the DLL with
  `ctypes` and must not require a managed runtime.
- **C++:** C++20, `x64` only. Include the header as the examples do.
- **Keep the licence boundary intact.** Do not copy code from the binary or from
  internal repositories into this one, and do not add files under a licence that
  conflicts with the Apache License 2.0 that covers this repository's content.
- One topic per pull request, in the same style as the existing code. Comments
  should explain *why*, not restate the line below.

## Contributor licence agreement

Substantial contributions may need a signed contributor agreement. If that
applies to your change, a maintainer will ask before merging. *(Placeholder: the
exact process is being confirmed with legal.)*

## Security

Do not open a public issue for a security problem, see
[SECURITY.md](SECURITY.md).
