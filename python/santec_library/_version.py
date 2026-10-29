"""The version of :mod:`santec_library`, and the only place it is declared.

``pyproject.toml`` takes its distribution version from here, ``library`` re-exports
it, and the release job writes it from the tag before building the bundle, so the
package, the metadata pip reports and ``Santec.Library.dll`` all agree.

The value committed in the repository is the last released version. It matters only
to a local ``pip install ./python``, because a release overwrites it on the way past.
"""

PACKAGE_VERSION = "1.8.0.4"
