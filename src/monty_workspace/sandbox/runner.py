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
    tests: list[dict[str, Any]] = field(default_factory=list)
    function_logs: list[dict[str, Any]] = field(default_factory=list)


class SandboxRunner:
    def __init__(self, registry: HostFunctionRegistry, limits: dict | None = None):
        self._registry = registry
        self._limits = limits

    @staticmethod
    def _call_host(fn: Any, args: list[Any]) -> dict[str, Any]:
        """Call a host function. An exception goes back into the sandbox, where try/except can catch it,
        as feed_run(external_lookup=...) does."""
        try:
            return {"return_value": fn(*args)}
        except Exception as e:
            return {"exception": e}

    @staticmethod
    def _compile_check(code: str, label: str = "<user>") -> str | None:
        try:
            compile(code, label, "exec")
            return None
        except SyntaxError as e:
            return f"SyntaxError: {e.msg} (line {e.lineno})"

    def run(self, code: str, inputs: dict[str, Any] | None = None,
            allowlist: list[str] | None = None,
            limits: dict | None = None,
            interactive: bool = True,
            on_suspend: Any = None,
            storage: Any = None,
            file_name: str | None = None) -> RunResult:
        err = self._compile_check(code)
        if err:
            return RunResult(success=False, error=err)

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
                            snapshot = snapshot.resume(self._call_host(external_lookup[name], args))
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
                            snapshot = snapshot.resume(self._call_host(external_lookup[name], args))
                        else:
                            snapshot = snapshot.resume_not_handled()

                    result_val = session.feed_run("result")
                    return RunResult(success=True, value=result_val, suspensions=suspensions, function_logs=call_logs)
        except Exception as e:
            return RunResult(success=False, error=f"{type(e).__name__}: {e}", suspensions=suspensions, function_logs=call_logs)

    def run_tests(self, solution_code: str, test_code: str,
                  allowlist: list[str] | None = None,
                  inputs: dict[str, Any] | None = None,
                  limits: dict | None = None,
                  use_samples: bool = True) -> TestResult:
        import re as _re

        err = self._compile_check(solution_code, "<solution>")
        if err:
            return TestResult(passed=False, failures=[err], total=0)
        err = self._compile_check(test_code, "<test>")
        if err:
            return TestResult(passed=False, failures=[err], total=0)

        try:
            from pydantic_monty import Monty, ResourceLimits
        except ImportError as e:
            raise RuntimeError("pydantic-monty required: pip install pydantic-monty") from e

        test_names = _re.findall(r'def (test_\w+)\s*\(', test_code)
        if not test_names:
            return TestResult(passed=False, failures=["No test_* functions found"], total=0)

        runner_snippet = "\n__test_results__ = []\n"
        for name in test_names:
            runner_snippet += (
                f"try:\n"
                f"    {name}()\n"
                f"    __test_results__.append({{\"name\": \"{name}\", \"passed\": True, \"error\": None}})\n"
                f"except Exception as __e:\n"
                f"    __test_results__.append({{\"name\": \"{name}\", \"passed\": False, \"error\": str(__e)}})\n"
            )
        runner_snippet += "result = __test_results__\n"

        combined = f"{solution_code}\n\n{test_code}\n\n{runner_snippet}"
        call_logs: list[dict[str, Any]] = []
        external_lookup = self._registry.build_lookup(
            allowlist, call_logs=call_logs, use_samples=use_samples,
        )
        wrapped = {"inputs": inputs or {}}
        rl = ResourceLimits(**(limits or self._limits or {}))

        try:
            with Monty() as pool:
                with pool.checkout(limits=rl) as session:
                    session.feed_run(combined, inputs=wrapped, external_lookup=external_lookup)
                    tests = session.feed_run("result")
                    failures = [t["error"] for t in tests if not t["passed"]]
                    return TestResult(
                        passed=len(failures) == 0,
                        failures=failures,
                        total=len(tests),
                        tests=tests,
                        function_logs=call_logs,
                    )
        except Exception as e:
            return TestResult(
                passed=False, failures=[str(e)], total=len(test_names),
                function_logs=call_logs,
            )
