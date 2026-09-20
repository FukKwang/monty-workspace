from __future__ import annotations

from typing import Callable


class HostFunctionRegistry:
    def __init__(self):
        self._functions: dict[str, Callable] = {}
        self._descriptions: dict[str, str] = {}
        self._human_input: set[str] = set()

    def register(self, name: str, description: str, *, human_input: bool = False) -> Callable:
        def decorator(fn: Callable) -> Callable:
            self._functions[name] = fn
            self._descriptions[name] = description
            if human_input:
                self._human_input.add(name)
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

    def build_lookup(self, allowlist: list[str] | None = None) -> dict[str, Callable]:
        if allowlist is None:
            return dict(self._functions)
        return {k: v for k, v in self._functions.items() if k in allowlist}

    def clear(self) -> None:
        self._functions.clear()
        self._descriptions.clear()
        self._human_input.clear()
