from __future__ import annotations

import flatbuffers
import numpy as np

import typing
from typing import cast

uoffset: typing.TypeAlias = flatbuffers.number_types.UOffsetTFlags.py_type

class PowerMeterParameters(object):
  NONE = cast(int, ...)
  MPM = cast(int, ...)
  OPM = cast(int, ...)

