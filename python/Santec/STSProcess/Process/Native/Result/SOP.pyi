from __future__ import annotations

import flatbuffers
import numpy as np

import typing
from typing import cast

uoffset: typing.TypeAlias = flatbuffers.number_types.UOffsetTFlags.py_type

class SOP(object):
  None_ = cast(int, ...)
  VLP = cast(int, ...)
  HLP = cast(int, ...)
  LP45 = cast(int, ...)
  LPN45 = cast(int, ...)
  RCP = cast(int, ...)
  LCP = cast(int, ...)

