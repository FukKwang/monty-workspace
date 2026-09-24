"""Host function exceptions must be catchable by sandbox try/except on both runner paths.

Run: python tests/test_runner.py   (or pytest)
"""

from monty_workspace.sandbox.registry import HostFunctionRegistry
from monty_workspace.sandbox.runner import SandboxRunner

CODE = (
    "try:\n"
    "    boom({})\n"
    "    result = 'not caught'\n"
    "except ValueError as e:\n"
    "    result = 'caught: ' + str(e)"
)


def _runner(with_human_fn: bool) -> SandboxRunner:
    registry = HostFunctionRegistry()

    @registry.register("boom", "Always raises")
    def boom(params):
        raise ValueError("bad")

    if with_human_fn:
        # A registered human-input function switches the runner to its snapshot loop.
        registry.register("ask", "Ask a human", human_input=True)(lambda params: None)
    return SandboxRunner(registry)


def test_host_exception_is_catchable():
    for with_human_fn in (False, True):
        r = _runner(with_human_fn).run(CODE)
        assert r.success, (with_human_fn, r.error)
        assert r.value == "caught: bad", (with_human_fn, r.value)


def test_uncaught_host_exception_fails_run():
    for with_human_fn in (False, True):
        r = _runner(with_human_fn).run("result = boom({})")
        assert not r.success
        assert "ValueError" in r.error and "bad" in r.error, (with_human_fn, r.error)


if __name__ == "__main__":
    test_host_exception_is_catchable()
    test_uncaught_host_exception_fails_run()
    print("ok")
