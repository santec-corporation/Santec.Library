"""Turn a scan payload into plain Python data.

``ReferenceScan`` and ``MeasurementScan`` hand back a FlatBuffers
``SweepResultSet``. This module reads it through the generated bindings in the
vendored ``Santec`` package and returns values you can print, plot or write to a
CSV without knowing anything about FlatBuffers.

    payload = lib.measurement_scan()
    for sweep in parse(payload):
        print(sweep.kind, sweep.wavelength[0], sweep.insertion_loss[0])

numpy is used when it is installed, and the loops fall back to per-element access
when it is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

try:  # numpy is optional: the generated bindings work without it
    import numpy as _numpy
except ImportError:  # pragma: no cover - depends on the environment
    _numpy = None

from Santec.STSProcess.Process.Native.Result.ILReferenceResult import ILReferenceResult
from Santec.STSProcess.Process.Native.Result.ILResult import ILResult
from Santec.STSProcess.Process.Native.Result.SweepResult import SweepResult
from Santec.STSProcess.Process.Native.Result.SweepResultSet import SweepResultSet

REFERENCE = "reference"
MEASUREMENT = "measurement"


@dataclass
class RescaledSpectrum:
    """One channel's rescaled spectrum from a measurement sweep."""

    channel: str
    power: Sequence[float] = field(default_factory=list)
    power_monitor: Sequence[float] = field(default_factory=list)


@dataclass
class Sweep:
    """One sweep inside a scan payload.

    ``kind`` says which fields are populated: a reference sweep has ``power`` and
    ``power_monitor``, a measurement sweep has ``insertion_loss`` and
    ``rescaled``.
    """

    kind: str
    wavelength: Sequence[float] = field(default_factory=list)
    power: Sequence[float] | None = None
    power_monitor: Sequence[float] | None = None
    insertion_loss: Sequence[float] | None = None
    rescaled: list[RescaledSpectrum] = field(default_factory=list)
    channel: str = ""

    def __str__(self) -> str:
        points = len(self.wavelength)
        detail = ""
        if self.insertion_loss:
            detail = f", IL {min(self.insertion_loss):.2f}..{max(self.insertion_loss):.2f} dB"
        return f"{self.kind} sweep, {points} points{detail}"


def _vector(obj, numpy_accessor: str, plain_accessor: str, length_accessor: str) -> Sequence[float]:
    """Read a FlatBuffers vector, using the numpy helper when numpy is present."""
    if _numpy is not None:
        values = getattr(obj, numpy_accessor)()
        if values is not None:
            return list(values)
    length = getattr(obj, length_accessor)()
    getter = getattr(obj, plain_accessor)
    return [getter(index) for index in range(length)]


def _channel_name(sweep_key) -> str:
    """A readable channel identifier, or an empty string when there is none."""
    if sweep_key is None:
        return ""
    channel = sweep_key.ChannelKey()
    if channel is None:
        return ""
    module = channel.ModuleKey()
    module_name = module.ModuleType().decode("utf-8", "replace") if module is not None else "?"
    return f"{module_name}:{channel.ChannelNumber()}"


def parse(payload: bytes) -> list[Sweep]:
    """Parse a ``ReferenceScan`` or ``MeasurementScan`` payload.

    Returns one :class:`Sweep` per result in the payload. Unknown result types are
    skipped rather than raising, so a newer library that adds one does not break
    older code.
    """
    result_set = SweepResultSet.GetRootAsSweepResultSet(payload, 0)
    sweeps: list[Sweep] = []
    tags = SweepResult()

    for index in range(result_set.ResultsLength()):
        entry = result_set.Results(index)
        if entry is None:
            continue
        result_type = entry.ResultsType()
        body = entry.Results()
        if body is None:
            continue

        if result_type == tags.ILReferenceResult:
            reference = ILReferenceResult()
            reference.Init(body.Bytes, body.Pos)

            data = reference.Data()
            sweeps.append(
                Sweep(
                    kind=REFERENCE,
                    wavelength=_vector(reference, "WavelengthAsNumpy", "Wavelength", "WavelengthLength"),
                    power=_vector(data, "PowerAsNumpy", "Power", "PowerLength") if data else None,
                    power_monitor=(
                        _vector(data, "PowerMonitorAsNumpy", "PowerMonitor", "PowerMonitorLength")
                        if data
                        else None
                    ),
                    channel=_channel_name(reference.SweepKey()),
                )
            )

        elif result_type == tags.ILResult:
            measurement = ILResult()
            measurement.Init(body.Bytes, body.Pos)

            insertion_loss = measurement.InsertionLoss()
            rescaled = []
            for position in range(measurement.RescaledDataLength()):
                entry_data = measurement.RescaledData(position)
                if entry_data is None:
                    continue
                power_log = entry_data.PowerLog()
                monitor_log = entry_data.PowerMonitorLog()
                rescaled.append(
                    RescaledSpectrum(
                        channel=str(entry_data.Key()) if entry_data.Key() is not None else "",
                        power=_vector(power_log, "DataAsNumpy", "Data", "DataLength") if power_log else [],
                        power_monitor=(
                            _vector(monitor_log, "DataAsNumpy", "Data", "DataLength") if monitor_log else []
                        ),
                    )
                )

            sweeps.append(
                Sweep(
                    kind=MEASUREMENT,
                    wavelength=_vector(measurement, "WavelengthAsNumpy", "Wavelength", "WavelengthLength"),
                    insertion_loss=(
                        _vector(insertion_loss, "InsertionLossAsNumpy", "InsertionLoss", "InsertionLossLength")
                        if insertion_loss
                        else None
                    ),
                    rescaled=rescaled,
                    channel=_channel_name(measurement.SweepKey()),
                )
            )

    return sweeps
