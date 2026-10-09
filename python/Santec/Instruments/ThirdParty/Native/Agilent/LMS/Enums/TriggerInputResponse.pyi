from __future__ import annotations

import flatbuffers
import numpy as np

import typing
from typing import cast

uoffset: typing.TypeAlias = flatbuffers.number_types.UOffsetTFlags.py_type

class TriggerInputResponse(object):
  Ignore = cast(int, ...)
  SMEasure = cast(int, ...)
  CMEasure = cast(int, ...)
  NextStep = cast(int, ...)
  SWStart = cast(int, ...)

