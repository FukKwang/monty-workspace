---
name: monty-sandbox
description: Write, run, and test sandbox code for monty-workspace (pydantic-monty). Use when writing workspace .py files, test_ files, code that calls host functions (query_*, ask_*, tabulate_data, formula_*), or when driving the REST API (/api/file, /api/run, /api/test) or MCP tools (run_code, write_file, run_file).
---

# Monty sandbox code

Sandbox code runs inside pydantic-monty, a Rust Python interpreter. It is NOT CPython. It has a small stdlib and no filesystem, env, or network access. The only way to reach outside data is a host function.

## Contract

- `inputs`: global dict of runtime inputs. Use `inputs.get("key")` for optional keys and `inputs["key"]` for required keys.
- `result`: the code MUST assign this global. The runner reads `result` after the script ends. If it is missing, the run fails with `NameError: name 'result' is not defined`.
- `result` must be JSON-friendly: dict, list, str, int, float, bool, or None.
- Host functions are globals. Call them by name with ONE positional dict: `query_borrower({"name": "Alice"})`. Keyword arguments fail with `TypeError`.
- A host function exception goes into the sandbox as a normal exception. Catch it with `try/except` (see `tests/test_runner.py`).

## Language subset (verified)

Works: functions, classes, `@dataclass`, lambdas, comprehensions, f-strings with format specs, `try/except/raise`, star-unpacking, `isinstance`, `sorted`/`sum`/`min`/`max`/`round`/`zip`/`enumerate`, `print`.

Importable: `math`, `json`, `re`, `datetime`, `dataclasses`, `typing`, `collections`, `itertools`, `functools`, `base64`.

Not available:
- `yield` / generators: `NotImplementedError`.
- `statistics`, `decimal`, `random`, `time`, `copy`, `enum`, `operator`, `uuid`, `hashlib`, `string`: `ModuleNotFoundError`.
- Third-party packages (`pandas`, `numpy`, ...): not importable. Call a host function instead (`compute_statistics`, `tabulate_data`, `aggregate_data`, `pivot_data`).
- `open()`, `os.getenv()`, and other I/O: `PermissionError` or `RuntimeError`.

Default limits: 10 s, 64 MB, recursion depth 500 (`SandboxConfig` in `src/monty_workspace/config.py`).

## Discover host functions first

Never guess a host function name or its argument shape. Get the list:

- REST: `GET /api/completions` returns `[{name, description, sample}]`. The description holds the signature, for example `query_loans({'borrower_id': str}) -> list`.
- MCP: `list_host_functions`.
- Python: `monty.registry.descriptions` and `monty.registry.samples`.

The lending example registers its functions in `examples/lending/host_functions.py` (`register_all`). `human_input=True` functions (`ask_user`, `ask_number`, `ask_confirm`, `ask_choice`) suspend the run. Through `/api/run`, the response is `{"suspended": true, "snapshot_id": ...}`. Continue it with `POST /api/resume {"snapshot_id": N, "value": "<json>"}` or the MCP tool `resume_snapshot`.

## File template

Use Google-style docstrings. `GET /api/functions?file=` and the UI parse the `Args:` and `Returns:` sections.

```python
"""Short description of the script.

Args:
    loan_id: Loan identifier

Returns:
    loan_id: Echo of input
    paid_total: Sum of completed payments in IDR
"""
loan = query_loan_details({"loan_id": inputs["loan_id"]})
payments = loan.get("payments") or []

result = {
    "loan_id": inputs["loan_id"],
    "paid_total": sum(p["amount"] for p in payments if p["status"] == "completed"),
}
```

Rules:
- Guard against a `None` or empty host result (`x.get(...) if x else None`). Do not index blindly.
- Keep a file self-contained. There are no imports between workspace files.
- Name files `snake_case.py`. The name must not contain `/` or `..`.

## Tests

Name the test file `test_<solution>.py`. The runner concatenates solution + test, then calls every `def test_*()`. The tests see the solution globals, including `result`.

```python
def test_paid_total_non_negative():
    assert result["paid_total"] >= 0, result
```

Important:
- `/api/test` and `run_tests` use `use_samples=True`. Host functions that have a registered `sample` return that sample and ignore the arguments. Write assertions that are true for the sample data.
- `/api/test` fills each `inputs["key"]` that the solution uses with the string `"test"`, unless the request gives the key.
- `yield`-based fixtures, pytest features, and parametrize are not available. Use plain `assert`.

## Workflow

Do all steps. Do not stop after the file is written.

1. Discover host functions (above).
2. Write the file: `POST /api/file {"name", "content"}` or MCP `write_file`. Read `syntax_error` in the response. The file is saved even when the syntax is invalid.
3. Run it: `POST /api/run {"code", "inputs", "file_name"}` or MCP `run_file(name, inputs_json)`. Check `success`, `error`, and `function_logs` (each host call with its args, result, and duration).
4. Write `test_<name>.py`, then run `POST /api/test {"file_name": "<name>.py"}` or MCP `run_tests`.
5. Fix and repeat until the run succeeds and the tests pass.

### Without a running server

Run the example domain in-process with the project venv:

```bash
.venv/bin/python - <<'EOF'
import tempfile
from monty_workspace import Monty
from examples.lending.host_functions import register_all
m = Monty(workspace_dir=tempfile.mkdtemp())
register_all(m)
code = open("examples/lending/codes/loan_details.py").read()
r = m.run(code, {"loan_id": "L-001"}, interactive=False)
print(r.success, r.error, r.value)
EOF
```

`m.run_tests(solution_code, test_code, use_samples=True)` returns `TestResult(passed, failures, total, tests)`.

To serve domain host functions, pass `--host-module <dotted.module>` (repeatable) to `monty-web` or `monty-mcp`. The module must define `register_all(monty)`. Example: `monty-web --workspace examples/lending/codes --host-module examples.lending.host_functions`. Without it, only `formula_*` functions exist.

## API reference

| Action | REST | MCP tool |
|---|---|---|
| List files | `GET /api/files` | `list_files` |
| Read file | `GET /api/file?name=` | `read_file` |
| Save file | `POST /api/file` `{name, content}` | `write_file` |
| Inspect docstrings | `GET /api/functions?file=` | none |
| Run code | `POST /api/run` `{code, inputs, file_name}` | `run_code(code, inputs_json)` / `run_file(name, inputs_json)` |
| Run tests | `POST /api/test` `{file_name, inputs}` | `run_tests(solution_code, test_code, inputs_json)` |
| Host functions | `GET /api/completions`, `GET /api/samples` | `list_host_functions` |
| Suspended runs | `GET /api/snapshots`, `POST /api/resume` | `list_snapshots`, `resume_snapshot` |
| History | `GET /api/runs?file=`, `GET /api/run-detail?id=` | none |
| Versions | `GET /api/versions?name=`, `POST /api/versions/restore {id}` | none |

For MCP tools, `inputs` is a JSON **string**, for example `'{"loan_id": "L-001"}'`.

For formulas, see the `monty-formula` skill.
