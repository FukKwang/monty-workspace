from __future__ import annotations

import contextvars
import time
from datetime import datetime, timezone
from typing import Any, Callable

_current_logs: contextvars.ContextVar[list[dict[str, str]] | None] = contextvars.ContextVar(
    "current_logs", default=None,
)

_LEVELS = ("debug", "info", "warning", "error")


def log(message: str, level: str = "info") -> None:
    """Log a message from inside a host function. Import: `from monty_workspace import log`"""
    logs = _current_logs.get()
    if logs is not None:
        logs.append({
            "level": level if level in _LEVELS else "info",
            "message": str(message),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


def log_debug(message: str) -> None:
    log(message, "debug")


def log_warning(message: str) -> None:
    log(message, "warning")


def log_error(message: str) -> None:
    log(message, "error")


class HostFunctionRegistry:
    def __init__(self):
        self._functions: dict[str, Callable] = {}
        self._descriptions: dict[str, str] = {}
        self._human_input: set[str] = set()
        self._samples: dict[str, Any] = {}

    def register(self, name: str, description: str, *,
                 human_input: bool = False, sample: Any = None) -> Callable:
        def decorator(fn: Callable) -> Callable:
            self._functions[name] = fn
            self._descriptions[name] = description
            if human_input:
                self._human_input.add(name)
            if sample is not None:
                self._samples[name] = sample
            return fn
        return decorator

    @property
    def functions(self) -> dict[str, Callable]:
        return dict(self._functions)

    @property
    def descriptions(self) -> dict[str, str]:
        return dict(self._descriptions)

    @property
    def human_input_functions(self) -> set[str]:
        return set(self._human_input)

    @property
    def samples(self) -> dict[str, Any]:
        return dict(self._samples)

    def build_lookup(
        self,
        allowlist: list[str] | None = None,
        call_logs: list[dict[str, Any]] | None = None,
        use_samples: bool = False,
    ) -> dict[str, Callable]:
        raw = self._functions if allowlist is None else {
            k: v for k, v in self._functions.items() if k in allowlist
        }
        if use_samples:
            stubbed: dict[str, Callable] = {}
            for name, fn in raw.items():
                if name in self._samples:
                    s = self._samples[name]
                    stubbed[name] = lambda *args, _s=s: _s
                else:
                    stubbed[name] = fn
            raw = stubbed
        if call_logs is None:
            return dict(raw)
        return {name: self._wrap(name, fn, call_logs) for name, fn in raw.items()}

    @staticmethod
    def _wrap(name: str, fn: Callable, call_logs: list[dict[str, Any]]) -> Callable:
        def wrapper(*args: Any) -> Any:
            extra: list[dict[str, str]] = []
            token = _current_logs.set(extra)
            t0 = time.monotonic()
            try:
                result = fn(*args)
            finally:
                duration_ms = int((time.monotonic() - t0) * 1000)
                _current_logs.reset(token)
            call_logs.append({
                "function": name,
                "args": list(args),
                "result": result,
                "logs": extra,
                "duration_ms": duration_ms,
            })
            return result
        return wrapper

    def clear(self) -> None:
        self._functions.clear()
        self._descriptions.clear()
        self._human_input.clear()
