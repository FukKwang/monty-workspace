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
    suspended: bool = False
    snapshot_id: int | None = None
    snapshot_function: str | None = None
    snapshot_args: list[Any] | None = None
    function_logs: list[dict[str, Any]] = field(default_factory=list)


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
            on_suspend: Any = None,
            storage: Any = None,
            file_name: str | None = None) -> RunResult:
        try:
            from pydantic_monty import Monty, MontyComplete, FunctionSnapshot, ResourceLimits
        except ImportError as e:
            raise RuntimeError("pydantic-monty required: pip install pydantic-monty") from e

        call_logs: list[dict[str, Any]] = []
        external_lookup = self._registry.build_lookup(allowlist, call_logs=call_logs)
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
                        return RunResult(success=True, value=value, function_logs=call_logs)
            except Exception as e:
                return RunResult(success=False, error=f"{type(e).__name__}: {e}", function_logs=call_logs)

        suspensions: list[dict[str, Any]] = []
        try:
            with Monty() as pool:
                with pool.checkout(limits=rl) as session:
                    snapshot = session.feed_start(code, inputs=wrapped)
                    while not isinstance(snapshot, MontyComplete):
                        if not isinstance(snapshot, FunctionSnapshot):
                            snapshot = snapshot.resume_not_handled()
                            continue

                        name = snapshot.function_name
                        args = list(snapshot.args)
                        suspensions.append({"function": name, "args": args})

                        if name in human_fns and not interactive and storage:
                            blob = snapshot.dump()
                            snap_id = storage.save_snapshot(
                                function_name=name, args=args, blob=blob,
                                file_name=file_name,
                            )
                            return RunResult(
                                suspended=True, snapshot_id=snap_id,
                                snapshot_function=name, snapshot_args=args,
                                suspensions=suspensions, function_logs=call_logs,
                            )

                        if name in human_fns and interactive and on_suspend:
                            value = on_suspend(name, args)
                            snapshot = snapshot.resume({"return_value": value})
                        elif name in external_lookup:
                            result = external_lookup[name](*args)
                            snapshot = snapshot.resume({"return_value": result})
                        else:
                            snapshot = snapshot.resume_not_handled()

                    value = session.feed_run("result")
                    return RunResult(success=True, value=value, suspensions=suspensions, function_logs=call_logs)
        except Exception as e:
            return RunResult(success=False, error=f"{type(e).__name__}: {e}", suspensions=suspensions, function_logs=call_logs)

    def resume_snapshot(self, blob: bytes, value: Any,
                        allowlist: list[str] | None = None,
                        limits: dict | None = None,
                        storage: Any = None,
                        file_name: str | None = None) -> RunResult:
        try:
            from pydantic_monty import Monty, MontyComplete, FunctionSnapshot, ResourceLimits
        except ImportError as e:
            raise RuntimeError("pydantic-monty required: pip install pydantic-monty") from e

        call_logs: list[dict[str, Any]] = []
        external_lookup = self._registry.build_lookup(allowlist, call_logs=call_logs)
        rl = ResourceLimits(**(limits or self._limits or {}))
        human_fns = self._registry.human_input_functions
        suspensions: list[dict[str, Any]] = []

        try:
            with Monty() as pool:
                with pool.checkout(limits=rl) as session:
                    snapshot = session.load_snapshot(blob)
                    snapshot = snapshot.resume({"return_value": value})

                    while not isinstance(snapshot, MontyComplete):
                        if not isinstance(snapshot, FunctionSnapshot):
                            snapshot = snapshot.resume_not_handled()
                            continue

                        name = snapshot.function_name
                        args = list(snapshot.args)
                        suspensions.append({"function": name, "args": args})

                        if name in human_fns and storage:
                            new_blob = snapshot.dump()
                            snap_id = storage.save_snapshot(
                                function_name=name, args=args, blob=new_blob,
                                file_name=file_name,
                            )
                            return RunResult(
                                suspended=True, snapshot_id=snap_id,
                                snapshot_function=name, snapshot_args=args,
                                suspensions=suspensions, function_logs=call_logs,
                            )

                        if name in external_lookup:
                            result = external_lookup[name](*args)
                            snapshot = snapshot.resume({"return_value": result})
                        else:
                            snapshot = snapshot.resume_not_handled()

                    result_val = session.feed_run("result")
                    return RunResult(success=True, value=result_val, suspensions=suspensions, function_logs=call_logs)
        except Exception as e:
            return RunResult(success=False, error=f"{type(e).__name__}: {e}", suspensions=suspensions, function_logs=call_logs)

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
