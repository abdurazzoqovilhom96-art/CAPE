"""Timing protocol (spec section 20): monotonic perf_counter_ns, GC paused inside the timed
region, and work shorter than `small_task_ns` repeated inside one timed sample until the batch
lasts at least `min_batch_ns` (iterations and batch duration are recorded). Every iteration
really runs the codec: results are never cached across iterations or repeats."""

from __future__ import annotations

import gc
import math
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Timed:
    per_call_ns: int
    iterations: int
    batch_ns: int
    first_ns: int
    result: Any


def time_call(fn: Callable[[], Any], min_batch_ns: int, small_task_ns: int) -> Timed:
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        t0 = time.perf_counter_ns()
        result = fn()
        first = max(1, time.perf_counter_ns() - t0)
        if first >= small_task_ns or min_batch_ns <= 0:
            return Timed(first, 1, first, first, result)
        iters = max(2, math.ceil(min_batch_ns / first))
        t0 = time.perf_counter_ns()
        for _ in range(iters):
            result = fn()
        batch = max(1, time.perf_counter_ns() - t0)
        return Timed(max(1, batch // iters), iters, batch, first, result)
    finally:
        if was_enabled:
            gc.enable()
