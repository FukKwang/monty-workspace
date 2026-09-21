"""Formula registry with composition, persistence, and audit logging."""

from __future__ import annotations

import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage import Storage


class FormulaRegistry:
    def __init__(self, storage: Storage):
        self._storage = storage
        self._cache: dict[str, dict[str, Any]] = {}
        self._run_id: int | None = None
        self._load_from_db()

    def _load_from_db(self):
        for f in self._storage.list_formulas():
            self._cache[f["name"]] = {"expr": f["expr"], "vars": f["vars"], "description": f["description"]}

    def set_run_id(self, run_id: int | None):
        self._run_id = run_id

    def _log(self, formula_name: str, operation: str, args: dict, result: Any = None, error: str | None = None, duration_ms: int | None = None):
        self._storage.log_formula_op(
            run_id=self._run_id, formula_name=formula_name,
            operation=operation, args=args, result=result,
            error=error, duration_ms=duration_ms,
        )

    def _sympify(self, expr_str: str):
        from sympy import sympify
        return sympify(expr_str, evaluate=False)

    def _to_str(self, expr) -> str:
        return str(expr)

    def _to_latex(self, expr) -> str:
        from sympy import latex
        return latex(expr)

    def define(self, name: str, expr: str, vars: list[str], description: str = "", persist: bool = True) -> dict[str, Any]:
        t0 = time.monotonic()
        try:
            parsed = self._sympify(expr)
            self._cache[name] = {"expr": expr, "vars": vars, "description": description}
            if persist:
                self._storage.save_formula(name, expr, vars, description)
            result = {
                "name": name, "expr": self._to_str(parsed),
                "latex": self._to_latex(parsed), "vars": vars,
            }
            self._log(name, "define", {"expr": expr, "vars": vars, "description": description, "persist": persist},
                       result=result, duration_ms=int((time.monotonic() - t0) * 1000))
            return result
        except Exception as e:
            self._log(name, "define", {"expr": expr, "vars": vars}, error=str(e),
                       duration_ms=int((time.monotonic() - t0) * 1000))
            raise

    def resolve(self, name: str, _seen: set[str] | None = None):
        if _seen is None:
            _seen = set()
        if name in _seen:
            raise ValueError(f"circular reference: {' -> '.join(_seen)} -> {name}")
        _seen.add(name)

        formula = self._cache.get(name)
        if not formula:
            raise KeyError(f"formula '{name}' not found")

        expr = self._sympify(formula["expr"])
        for sym in expr.free_symbols:
            sym_name = str(sym)
            if sym_name in self._cache:
                sub = self.resolve(sym_name, set(_seen))
                expr = expr.subs(sym, sub)
        return expr

    def evaluate(self, name: str, values: dict[str, Any]) -> dict[str, Any]:
        from sympy import Symbol
        t0 = time.monotonic()
        try:
            expr = self.resolve(name)
            result = expr.subs({Symbol(k): v for k, v in values.items()})
            try:
                numeric = float(result.evalf())
            except (TypeError, ValueError):
                numeric = None
            out = {"result": self._to_str(result), "numeric": numeric, "latex": self._to_latex(result)}
            self._log(name, "evaluate", {"values": values}, result=out,
                       duration_ms=int((time.monotonic() - t0) * 1000))
            return out
        except Exception as e:
            self._log(name, "evaluate", {"values": values}, error=str(e),
                       duration_ms=int((time.monotonic() - t0) * 1000))
            raise

    def partial(self, name: str, values: dict[str, Any]) -> dict[str, Any]:
        from sympy import Symbol
        t0 = time.monotonic()
        try:
            expr = self.resolve(name)
            result = expr.subs({Symbol(k): self._sympify(str(v)) for k, v in values.items()})
            remaining = sorted(str(s) for s in result.free_symbols)
            out = {"result": self._to_str(result), "latex": self._to_latex(result), "remaining_vars": remaining}
            self._log(name, "partial", {"values": values}, result=out,
                       duration_ms=int((time.monotonic() - t0) * 1000))
            return out
        except Exception as e:
            self._log(name, "partial", {"values": values}, error=str(e),
                       duration_ms=int((time.monotonic() - t0) * 1000))
            raise

    def differentiate(self, name: str, var: str, order: int = 1) -> dict[str, str]:
        from sympy import diff, Symbol
        t0 = time.monotonic()
        try:
            expr = self.resolve(name)
            result = diff(expr, Symbol(var), order)
            out = {"result": self._to_str(result), "latex": self._to_latex(result), "variable": var}
            self._log(name, "differentiate", {"var": var, "order": order}, result=out,
                       duration_ms=int((time.monotonic() - t0) * 1000))
            return out
        except Exception as e:
            self._log(name, "differentiate", {"var": var, "order": order}, error=str(e),
                       duration_ms=int((time.monotonic() - t0) * 1000))
            raise

    def integrate(self, name: str, var: str, lower: str | None = None, upper: str | None = None) -> dict[str, str]:
        from sympy import integrate as sym_integrate, Symbol
        t0 = time.monotonic()
        args = {"var": var, "lower": lower, "upper": upper}
        try:
            expr = self.resolve(name)
            v = Symbol(var)
            if lower is not None and upper is not None:
                result = sym_integrate(expr, (v, self._sympify(lower), self._sympify(upper)))
            else:
                result = sym_integrate(expr, v)
            out = {"result": self._to_str(result), "latex": self._to_latex(result), "variable": var}
            self._log(name, "integrate", args, result=out,
                       duration_ms=int((time.monotonic() - t0) * 1000))
            return out
        except Exception as e:
            self._log(name, "integrate", args, error=str(e),
                       duration_ms=int((time.monotonic() - t0) * 1000))
            raise

    def solve_for(self, name: str, var: str) -> dict[str, Any]:
        from sympy import solve, Symbol
        t0 = time.monotonic()
        try:
            expr = self.resolve(name)
            solutions = solve(expr, Symbol(var))
            out = {
                "variable": var,
                "solutions": [self._to_str(s) for s in solutions],
                "latex": [self._to_latex(s) for s in solutions],
            }
            self._log(name, "solve", {"var": var}, result=out,
                       duration_ms=int((time.monotonic() - t0) * 1000))
            return out
        except Exception as e:
            self._log(name, "solve", {"var": var}, error=str(e),
                       duration_ms=int((time.monotonic() - t0) * 1000))
            raise

    def series(self, name: str, var: str, point: str = "0", order: int = 6) -> dict[str, str]:
        from sympy import series as sym_series, Symbol
        t0 = time.monotonic()
        args = {"var": var, "point": point, "order": order}
        try:
            expr = self.resolve(name)
            result = sym_series(expr, Symbol(var), self._sympify(point), order)
            out = {"result": self._to_str(result), "latex": self._to_latex(result)}
            self._log(name, "series", args, result=out,
                       duration_ms=int((time.monotonic() - t0) * 1000))
            return out
        except Exception as e:
            self._log(name, "series", args, error=str(e),
                       duration_ms=int((time.monotonic() - t0) * 1000))
            raise

    def get_info(self, name: str) -> dict[str, Any]:
        formula = self._cache.get(name)
        if not formula:
            raise KeyError(f"formula '{name}' not found")
        expanded = self.resolve(name)
        return {
            "name": name,
            "expr": formula["expr"],
            "vars": formula["vars"],
            "description": formula["description"],
            "expanded": self._to_str(expanded),
            "expanded_latex": self._to_latex(expanded),
        }

    def list_all(self) -> list[dict[str, Any]]:
        result = []
        for name, f in sorted(self._cache.items()):
            try:
                expanded = self._to_str(self.resolve(name))
            except (ValueError, KeyError):
                expanded = f["expr"]
            result.append({
                "name": name, "expr": f["expr"], "vars": f["vars"],
                "description": f["description"], "expanded": expanded,
            })
        return result

    def delete(self, name: str) -> bool:
        self._cache.pop(name, None)
        deleted = self._storage.delete_formula(name)
        if deleted:
            self._log(name, "delete", {})
        return deleted

    def build_host_functions(self) -> dict[str, tuple[str, Any]]:
        """Return host function definitions for sandbox registration."""
        registry = self

        def formula_define(args_dict: dict[str, Any]) -> dict[str, Any]:
            return registry.define(
                name=args_dict["name"], expr=args_dict["expr"],
                vars=args_dict.get("vars", []),
                description=args_dict.get("description", ""),
                persist=args_dict.get("persist", True),
            )

        def formula_evaluate(args_dict: dict[str, Any]) -> dict[str, Any]:
            return registry.evaluate(args_dict["formula"], args_dict["values"])

        def formula_partial(args_dict: dict[str, Any]) -> dict[str, Any]:
            return registry.partial(args_dict["formula"], args_dict["values"])

        def formula_diff(args_dict: dict[str, Any]) -> dict[str, str]:
            return registry.differentiate(
                args_dict["formula"], args_dict["var"],
                order=args_dict.get("order", 1),
            )

        def formula_integrate(args_dict: dict[str, Any]) -> dict[str, str]:
            return registry.integrate(
                args_dict["formula"], args_dict["var"],
                lower=args_dict.get("lower"), upper=args_dict.get("upper"),
            )

        def formula_solve(args_dict: dict[str, Any]) -> dict[str, Any]:
            return registry.solve_for(args_dict["formula"], args_dict["var"])

        def formula_series(args_dict: dict[str, Any]) -> dict[str, str]:
            return registry.series(
                args_dict["formula"], args_dict["var"],
                point=args_dict.get("point", "0"),
                order=args_dict.get("order", 6),
            )

        def formula_info(args_dict: dict[str, Any]) -> dict[str, Any]:
            return registry.get_info(args_dict["formula"])

        def formula_list(_args_dict: dict[str, Any]) -> list[dict[str, Any]]:
            return registry.list_all()

        def formula_delete(args_dict: dict[str, Any]) -> dict[str, bool]:
            return {"deleted": registry.delete(args_dict["formula"])}

        return {
            "formula_define": (
                "formula_define({'name': str, 'expr': str, 'vars': list[str], 'description': str='', 'persist': bool=True}) -> dict: define/save formula",
                formula_define,
            ),
            "formula_evaluate": (
                "formula_evaluate({'formula': str, 'values': dict[str, number]}) -> dict: evaluate formula with values (auto-resolves references)",
                formula_evaluate,
            ),
            "formula_partial": (
                "formula_partial({'formula': str, 'values': dict}) -> dict: substitute some values, keep rest symbolic",
                formula_partial,
            ),
            "formula_diff": (
                "formula_diff({'formula': str, 'var': str, 'order': int=1}) -> dict: differentiate formula",
                formula_diff,
            ),
            "formula_integrate": (
                "formula_integrate({'formula': str, 'var': str, 'lower': str|None, 'upper': str|None}) -> dict: integrate formula",
                formula_integrate,
            ),
            "formula_solve": (
                "formula_solve({'formula': str, 'var': str}) -> dict: solve formula=0 for variable",
                formula_solve,
            ),
            "formula_series": (
                "formula_series({'formula': str, 'var': str, 'point': str='0', 'order': int=6}) -> dict: Taylor series",
                formula_series,
            ),
            "formula_info": (
                "formula_info({'formula': str}) -> dict: formula details with expanded form",
                formula_info,
            ),
            "formula_list": (
                "formula_list({}) -> list: all registered formulas",
                formula_list,
            ),
            "formula_delete": (
                "formula_delete({'formula': str}) -> dict: delete formula",
                formula_delete,
            ),
        }
