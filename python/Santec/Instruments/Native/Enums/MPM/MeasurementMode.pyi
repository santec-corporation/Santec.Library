from __future__ import annotations

import flatbuffers
import numpy as np

import typing
from typing import cast

uoffset: typing.TypeAlias = flatbuffers.number_types.UOffsetTFlags.py_type

class MeasurementMode(object):
  ManualRangeConstant = cast(int, ...)
  ManualRangeSweep = cast(int, ...)
  AutoRangeConstant = cast(int, ...)
  AutoRangeSweep = cast(int, ...)
  FreeRun = cast(int, ...)

