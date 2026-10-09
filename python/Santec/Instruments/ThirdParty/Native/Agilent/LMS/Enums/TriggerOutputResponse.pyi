from __future__ import annotations

import flatbuffers
import numpy as np

import typing
from typing import cast

uoffset: typing.TypeAlias = flatbuffers.number_types.UOffsetTFlags.py_type

class TriggerOutputResponse(object):
  Disable = cast(int, ...)
  AVGover = cast(int, ...)
  Measure = cast(int, ...)
  Modulation = cast(int, ...)
  STFinished = cast(int, ...)
  SWFinished = cast(int, ...)
  SWStarted = cast(int, ...)

