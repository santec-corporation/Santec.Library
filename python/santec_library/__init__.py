"""Python bindings for ``Santec.Library.dll``.

    from santec_library import Library

    with Library() as lib:
        for device in lib.list_devices():
            print(device)

Importing this package does nothing: no DLL is loaded until you create a
:class:`Library`. Reading scan results needs the FlatBuffers bindings, so import
:mod:`santec_library.results` when you want them::

    from santec_library.results import parse

    sweeps = parse(payload)
"""

from .library import (
    PACKAGE_VERSION,
    AbiMismatch,
    ConnectionConfig,
    Device,
    Library,
    LibraryNotFound,
    resolve_dll,
)

__version__ = PACKAGE_VERSION

__all__ = [
    "AbiMismatch",
    "ConnectionConfig",
    "Device",
    "Library",
    "LibraryNotFound",
    "PACKAGE_VERSION",
    "resolve_dll",
    "__version__",
]
