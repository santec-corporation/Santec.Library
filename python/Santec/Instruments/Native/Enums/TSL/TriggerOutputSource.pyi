from __future__ import annotations

import flatbuffers
import numpy as np

import typing
from typing import cast

uoffset: typing.TypeAlias = flatbuffers.number_types.UOffsetTFlags.py_type

class TriggerOutputSource(object):
  Wavelength = cast(int, ...)
  Time = cast(int, ...)

