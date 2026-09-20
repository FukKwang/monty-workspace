from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .registry import HostFunctionRegistry


@dataclass
class RunResult:
    success: bool = False
    value: Any = None
    error: str | None = None
    suspensions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class TestResult:
    passed: bool = False
    failures: list[str] = field(default_factory=list)
    total: int = 0


class SandboxRunner:
    def __init__(self, registry: HostFunctionRegistry, limits: dict | None = None):
        self._registry = registry
        self._limits = limits

    def run(self, code: str, inputs: dict[str, Any] | None = None,
            allowlist: list[str] | None = None,
            limits: dict | None = None,
            interactive: bool = True,
            on_suspend: Any = None) -> RunResult:
        try:
            from pydantic_monty import Monty, MontyComplete, ResourceLimits
        except ImportError as e:
            raise RuntimeError("pydantic-monty required: pip install pydantic-monty") from e

        external_lookup = self._registry.build_lookup(allowlist)
        wrapped = {"inputs": inputs or {}}
        rl = ResourceLimits(**(limits or self._limits or {}))

        human_fns = self._registry.human_input_functions
        has_human = any(f in (allowlist or list(external_lookup)) for f in human_fns)

        if not has_human:
            try:
                with Monty() as pool:
                    with pool.checkout(limits=rl) as session:
                        session.feed_run(code, inputs=wrapped, external_lookup=external_lookup)
                        value = session.feed_run("result")
                        return RunResult(success=True, value=value)
            except Exception as e:
                return RunResult(success=False, error=f"{type(e).__name__}: {e}")

        suspensions: list[dict[str, Any]] = []
        try:
            with Monty() as pool:
                with pool.checkout(limits=rl) as session:
                    snapshot = session.feed_start(code, inputs=wrapped)
                    while not isinstance(snapshot, MontyComplete):
                        name = snapshot.function_name
                        args = snapshot.args
                        suspensions.append({"function": name, "args": list(args)})

                        if name in human_fns and interactive and on_suspend:
                            value = on_suspend(name, args)
                            snapshot = snapshot.resume({"return_value": value})
                        elif name in external_lookup:
                            result = external_lookup[name](*args)
                            snapshot = snapshot.resume({"return_value": result})
                        else:
                            snapshot = snapshot.resume_not_handled()

                    value = session.feed_run("result")
                    return RunResult(success=True, value=value, suspensions=suspensions)
        except Exception as e:
            return RunResult(success=False, error=f"{type(e).__name__}: {e}", suspensions=suspensions)

    def run_tests(self, solution_code: str, test_code: str,
                  allowlist: list[str] | None = None,
                  inputs: dict[str, Any] | None = None,
                  limits: dict | None = None) -> TestResult:
        try:
            from pydantic_monty import Monty, ResourceLimits
        except ImportError as e:
            raise RuntimeError("pydantic-monty required: pip install pydantic-monty") from e

        external_lookup = self._registry.build_lookup(allowlist)
        wrapped = {"inputs": inputs or {}}
        combined = f"{solution_code}\n\n{test_code}"
        rl = ResourceLimits(**(limits or self._limits or {}))
        try:
            with Monty() as pool:
                with pool.checkout(limits=rl) as session:
                    session.feed_run(combined, inputs=wrapped, external_lookup=external_lookup)
                    return TestResult(passed=True, total=test_code.count("assert "))
        except Exception as e:
            return TestResult(passed=False, failures=[str(e)], total=test_code.count("assert "))
