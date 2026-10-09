from __future__ import annotations

import flatbuffers
import numpy as np

import typing
from typing import cast

uoffset: typing.TypeAlias = flatbuffers.number_types.UOffsetTFlags.py_type

class PowerMonitorLogSource(object):
  Unknown = cast(int, ...)
  TSL = cast(int, ...)
  SPU = cast(int, ...)
  MPM = cast(int, ...)

