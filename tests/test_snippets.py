"""Snippets are preloaded into every sandbox run path without suspensions.

Run: python tests/test_snippets.py   (or pytest)
"""

import tempfile

from monty_workspace import Monty


def _monty(with_human_fn: bool = False) -> Monty:
    m = Monty(workspace_dir=tempfile.mkdtemp())

    @m.snippet("Double a value")
    def double(x):
        return x * 2

    @m.snippet("Value holder")
    class Box:
        def __init__(self, v):
            self.v = double(v)  # snippets can call other snippets

    @m.host_function("ask", "Ask a human", human_input=with_human_fn)
    def ask(q):
        return 5

    return m


def test_registered_source_drops_decorator():
    src = _monty().registry.snippets["double"]["source"]
    assert src.startswith("def double(x):"), src


def test_run_without_suspensions():
    # 2000 calls would exceed max_suspensions=1000 if snippets were host functions
    r = _monty().run("result = sum(double(i) for i in range(2000))")
    assert r.success, r.error
    assert r.value == 2 * sum(range(2000))
    assert r.suspensions == []


def test_snapshot_path_and_resume():
    m = _monty(with_human_fn=True)
    r = m.run("result = Box(ask('n')).v", interactive=False)
    assert r.suspended, r.error
    r2 = m.resume_snapshot(r.snapshot_id, 7)
    assert r2.success, r2.error
    assert r2.value == 14


def test_run_tests():
    t = _monty().run_tests("def f(x):\n    return double(x)\n", "def test_f():\n    assert f(3) == 6\n")
    assert t.passed, t.failures


def test_user_definition_overrides_snippet():
    r = _monty().run("def double(x):\n    return x\nresult = double(4)")
    assert r.success and r.value == 4, (r.error, r.value)


if __name__ == "__main__":
    test_registered_source_drops_decorator()
    test_run_without_suspensions()
    test_snapshot_path_and_resume()
    test_run_tests()
    test_user_definition_overrides_snippet()
    print("ok")
