---
name: monty-formula
description: Define, compose, evaluate, and analyze SymPy formulas in the monty-workspace formula registry. Use when creating financial or math formulas (PMT, DTI, interest, fees), calling formula_* host functions from sandbox code, or using /api/formula* endpoints.
---

# Monty formula registry

Code: `src/monty_workspace/sandbox/formulas.py` (`FormulaRegistry`). Formulas are SymPy expression strings. They are stored in the workspace SQLite DB (`formulas` table). Every operation is written to `formula_logs`.

## Expression syntax (SymPy, not Python)

- Power is `**`. The parser also converts `^` to `**`, but write `**` so the expression is also valid Python.
- Functions: `log`, `exp`, `sqrt`, `Abs`, `Min`, `Max`, `floor`, `ceiling`, `pi`, `E`.
- Conditionals: `Piecewise((expr1, cond1), (expr2, True))`. Do not use Python `a if b else c`.
- Comparisons in conditions: `A < 1000`, `And(a > 0, b > 0)`.
- Variable names: plain identifiers (`P`, `rate`, `monthly_income`). Avoid SymPy names (`E`, `I`, `S`, `N`, `O`, `Q`, `beta`, `gamma`, `lambda`).

Examples:
```
PMT         P*r/(1 - (1 + r)**(-n))
dti         Min(monthly_debt/monthly_income, 1)
admin_fee   Piecewise((0.02*A, A < 10000000), (0.01*A, True))
```

## Composition

A free symbol whose name equals a registered formula name is replaced by that formula, recursively. Circular references raise `ValueError`.

```
PMT            P*r/(1-(1+r)**(-n))
total_cost     PMT*n                 # PMT expands
interest_paid  total_cost - P        # total_cost -> PMT expands
```

Consequences:
- Never name an input variable the same as a formula, because it is silently replaced.
- To evaluate a composed formula, pass only the base variables (`P`, `r`, `n`).
- `vars` is metadata for the UI. It is not enforced. List the direct symbols, including referenced formula names.

## Gotchas (verified)

- A missing value does NOT raise an error. `evaluate` returns `numeric: None` and a symbolic `result`. Always check `numeric is not None`.
- `result` is a string. Use `numeric` (float) for math in sandbox code.
- Rates are fractions per period. Use `0.01` for 1 %/month, not `1` or `12`.
- A string value such as `"1/100"` gives an exact rational result. Floats give float results.
- `formula_define` in sandbox code persists by default (`persist: True`). For scratch formulas, pass `"persist": False`. Scratch formulas stay in memory until the process restarts.
- `define` overwrites a formula with the same name. Before you define a formula, check `formula_list` / `GET /api/formulas`. Do not overwrite a shared formula by accident.
- A parse error raises `SympifyError`. Through REST, the response is HTTP 400 `{"error": ...}`.

## Sandbox host functions

Each function takes one dict argument.

| Function | Args | Returns |
|---|---|---|
| `formula_define` | `{name, expr, vars, description?, persist?=True}` | `{name, expr, latex, vars}` |
| `formula_evaluate` | `{formula, values}` | `{result, numeric, latex}` |
| `formula_partial` | `{formula, values}` | `{result, latex, remaining_vars}` |
| `formula_diff` | `{formula, var, order?=1}` | `{result, latex, variable}` |
| `formula_integrate` | `{formula, var, lower?, upper?}` | `{result, latex, variable}` |
| `formula_solve` | `{formula, var}` (solves formula = 0) | `{variable, solutions, latex}` |
| `formula_series` | `{formula, var, point?="0", order?=6}` | `{result, latex}` |
| `formula_info` | `{formula}` | `{name, expr, vars, description, expanded, expanded_latex}` |
| `formula_list` | `{}` | list of formulas |
| `formula_delete` | `{formula}` | `{deleted}` |

An unknown formula raises `KeyError("formula 'x' not found")`. Sandbox code can catch it.

Sandbox pattern:

```python
"""Monthly installment for a loan.

Args:
    loan_id: Loan identifier

Returns:
    installment: Monthly payment in IDR
"""
loan = query_loan_details({"loan_id": inputs["loan_id"]})["loan"]
pmt = formula_evaluate({
    "formula": "PMT",
    "values": {"P": loan["amount"], "r": loan["interest_rate"] / 100 / 12, "n": loan["tenor_months"]},
})
if pmt["numeric"] is None:
    raise ValueError("PMT unresolved: " + pmt["result"])
result = {"installment": round(pmt["numeric"], 2)}
```

To solve for a target (for example, the rate that gives a payment `X`), define a scratch formula `PMT - X`, then call `formula_solve`. `solve` can return an empty list or give up on transcendental equations. For those, use a bisection loop over `formula_evaluate` in sandbox code.

## REST API

| Method | Path | Body / query |
|---|---|---|
| GET | `/api/formulas` | none |
| GET | `/api/formula?name=` | none (404 if missing) |
| POST | `/api/formula` | `{name, expr, vars, description}` (always persists) |
| DELETE | `/api/formula` | `{name}` |
| POST | `/api/formula/evaluate` | `{formula, values}` |
| GET | `/api/formula/logs?name=&run_id=` | audit log |

The MCP server has no dedicated formula tools. Use `run_code` with the `formula_*` host functions.

Python: `monty.formulas.define(name, expr, vars, description, persist=True)`, `.evaluate(name, values)`, and the other methods in the table above.

## Workflow

1. `formula_list` / `GET /api/formulas`. Reuse an existing formula when one fits.
2. Define base formulas first, then composed formulas.
3. Check each formula with known values. Compare it to a hand-calculated or reference number (PMT(1000, 0.01, 12) = 88.8488).
4. Check `formula_info(...)["expanded"]` for composed formulas.
5. Use the formula from sandbox code (`monty-sandbox` skill). Write a `test_` file that asserts `numeric` values with a tolerance, for example `abs(x - 88.8488) < 1e-3`.
