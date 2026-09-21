"""Static analysis of user code: extract function signatures, docstrings, parameters, return fields."""

from __future__ import annotations

import ast
import re
from typing import Any


def inspect_functions(source: str, file_name: str = "") -> list[dict[str, Any]]:
    """Parse Python source and return structured function metadata."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            results.append(_extract_function(node))

    module_doc = _extract_module(tree, file_name)
    if module_doc:
        results.insert(0, module_doc)

    return results


def _extract_module(tree: ast.Module, file_name: str) -> dict[str, Any] | None:
    """Extract module-level docstring as file-level documentation."""
    docstring = ast.get_docstring(tree) or ""
    if not docstring:
        return None

    doc_params = _parse_docstring_params(docstring)
    doc_returns = _parse_docstring_returns(docstring)
    description = _first_line(docstring)

    if not description and not doc_params and not doc_returns:
        return None

    params: dict[str, Any] = {}
    for name, desc in doc_params.items():
        params[name] = {"description": desc}

    result: dict[str, Any] = {
        "name": file_name or "(module)",
        "description": description,
        "parameters": params,
        "returns": {},
        "lineno": 1,
        "module": True,
    }
    if doc_returns:
        result["returns"]["fields"] = doc_returns
    return result


def _extract_function(node: ast.FunctionDef) -> dict[str, Any]:
    docstring = ast.get_docstring(node) or ""
    doc_params = _parse_docstring_params(docstring)
    doc_returns = _parse_docstring_returns(docstring)
    description = _first_line(docstring)

    params = _extract_params(node, doc_params)
    return_type = _extract_return_type(node)

    result: dict[str, Any] = {
        "name": node.name,
        "description": description,
        "parameters": params,
        "returns": {"type": return_type},
        "lineno": node.lineno,
    }
    if doc_returns:
        result["returns"]["fields"] = doc_returns
    return result


def _extract_params(node: ast.FunctionDef, doc_params: dict[str, str]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    args = node.args

    num_defaults = len(args.defaults)
    num_args = len(args.args)

    for i, arg in enumerate(args.args):
        if arg.arg == "self":
            continue
        info: dict[str, Any] = {}
        if arg.annotation:
            info["type"] = _annotation_str(arg.annotation)

        default_index = i - (num_args - num_defaults)
        if default_index >= 0:
            info["required"] = False
            info["default"] = _literal_value(args.defaults[default_index])
        else:
            info["required"] = True

        if arg.arg in doc_params:
            info["description"] = doc_params[arg.arg]

        params[arg.arg] = info

    return params


def _extract_return_type(node: ast.FunctionDef) -> str:
    if node.returns:
        return _annotation_str(node.returns)
    return "Any"


def _annotation_str(node: ast.expr) -> str:
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_annotation_str(node.value)}.{node.attr}"
    if isinstance(node, ast.Subscript):
        return f"{_annotation_str(node.value)}[{_annotation_str(node.slice)}]"
    if isinstance(node, ast.Tuple):
        return ", ".join(_annotation_str(e) for e in node.elts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return f"{_annotation_str(node.left)} | {_annotation_str(node.right)}"
    return ast.dump(node)


def _literal_value(node: ast.expr) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name) and node.id == "None":
        return None
    if isinstance(node, ast.List):
        return [_literal_value(e) for e in node.elts]
    if isinstance(node, ast.Dict):
        return {_literal_value(k): _literal_value(v) for k, v in zip(node.keys, node.values) if k is not None}
    return str(ast.dump(node))


def _first_line(docstring: str) -> str:
    for line in docstring.strip().splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def _parse_docstring_params(docstring: str) -> dict[str, str]:
    """Parse Args/Parameters section from Google-style docstring."""
    params: dict[str, str] = {}
    in_args = False
    current_name = None
    current_desc_lines: list[str] = []

    for line in docstring.splitlines():
        stripped = line.strip()

        if re.match(r"^(Args|Arguments|Parameters|Params)\s*:", stripped):
            in_args = True
            continue
        if in_args and re.match(r"^(Returns|Raises|Yields|Note|Example)", stripped):
            if current_name:
                params[current_name] = " ".join(current_desc_lines).strip()
            break

        if not in_args:
            continue

        param_match = re.match(r"^(\w+)\s*(?:\(.*?\))?\s*:\s*(.*)", stripped)
        if param_match:
            if current_name:
                params[current_name] = " ".join(current_desc_lines).strip()
            current_name = param_match.group(1)
            current_desc_lines = [param_match.group(2)] if param_match.group(2) else []
        elif current_name and stripped:
            current_desc_lines.append(stripped)

    if current_name:
        params[current_name] = " ".join(current_desc_lines).strip()
    return params


def _parse_docstring_returns(docstring: str) -> dict[str, str]:
    """Parse Returns section — extract named fields."""
    fields: dict[str, str] = {}
    in_returns = False
    current_name = None
    current_desc_lines: list[str] = []

    for line in docstring.splitlines():
        stripped = line.strip()

        if re.match(r"^Returns\s*:", stripped):
            in_returns = True
            continue
        if in_returns and re.match(r"^(Args|Raises|Yields|Note|Example)", stripped):
            if current_name:
                fields[current_name] = " ".join(current_desc_lines).strip()
            break

        if not in_returns:
            continue

        field_match = re.match(r"^(\w+)\s*(?:\(.*?\))?\s*:\s*(.*)", stripped)
        if field_match:
            if current_name:
                fields[current_name] = " ".join(current_desc_lines).strip()
            current_name = field_match.group(1)
            current_desc_lines = [field_match.group(2)] if field_match.group(2) else []
        elif current_name and stripped:
            current_desc_lines.append(stripped)

    if current_name:
        fields[current_name] = " ".join(current_desc_lines).strip()
    return fields
