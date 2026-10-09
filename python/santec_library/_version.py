"""The version of :mod:`santec_library`, and the only place it is declared.

``pyproject.toml`` takes its distribution version from here, ``library`` re-exports
it, and the release job writes it from the tag before building the bundle, so the
package, the metadata pip reports and ``Santec.Library.dll`` all agree.

This is the one file the release pipeline owns inside ``python/santec_library``: the
mirror writes it on every release, so edit it nowhere else.
"""

PACKAGE_VERSION = "1.8.0.1"
