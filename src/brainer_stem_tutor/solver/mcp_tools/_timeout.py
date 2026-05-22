"""Cross-platform soft timeout for sympy calls.

POSIX gets a SIGALRM-based timeout; everywhere else (and in nested calls
where SIGALRM is unavailable) falls back to a thread-based runner. Either
way the public surface is `run_with_timeout(fn, args, kwargs, seconds)`
which returns the result or raises `TimeoutError`.
"""
from __future__ import annotations

import signal
import threading
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

_HAS_SIGALRM = hasattr(signal, "SIGALRM")


class _Sentinel:
    pass


_TIMEOUT_SENTINEL = _Sentinel()


@contextmanager
def _alarm(seconds: float):
    def _handler(signum, frame):
        raise TimeoutError(f"timed out after {seconds}s")

    prev = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, prev)


def _run_threaded(fn: Callable[..., Any], args, kwargs, seconds: float) -> Any:
    """Run `fn` in a daemon thread, raise TimeoutError if it overruns.

    Note: the thread cannot be safely killed in Python; an over-long sympy
    call will keep consuming CPU until it finishes. The caller observes
    TimeoutError and moves on. In production we'd run sympy out of process.
    """
    result: list[Any] = [_TIMEOUT_SENTINEL]
    error: list[BaseException | None] = [None]

    def target():
        try:
            result[0] = fn(*args, **kwargs)
        except BaseException as exc:  # pragma: no cover - propagation only
            error[0] = exc

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        raise TimeoutError(f"timed out after {seconds}s")
    if error[0]:
        raise error[0]
    return result[0]


def run_with_timeout(
    fn: Callable[..., Any],
    args: tuple = (),
    kwargs: dict | None = None,
    seconds: float = 2.0,
    use_signal: bool | None = None,
) -> Any:
    """Run `fn(*args, **kwargs)` with a wall-clock timeout.

    Use SIGALRM on POSIX main threads (fastest, lowest overhead). Fall back
    to a thread if SIGALRM is unavailable or we're called from a non-main
    thread (SIGALRM only works in the main thread).
    """
    kwargs = kwargs or {}
    if use_signal is None:
        use_signal = _HAS_SIGALRM and threading.current_thread() is threading.main_thread()
    if use_signal:
        with _alarm(seconds):
            return fn(*args, **kwargs)
    return _run_threaded(fn, args, kwargs, seconds)
