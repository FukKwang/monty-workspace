"""MCP server exposing Monty sandbox as tools for any LLM."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP

if TYPE_CHECKING:
    from ..core import Monty


def create_mcp_server(monty: Monty) -> FastMCP:
    mcp = FastMCP(monty.config.mcp.name)

    @mcp.tool()
    def run_code(code: str, inputs: str = "{}") -> str:
        """Execute Python code in sandboxed Monty environment. Code must assign to `result`. Inputs available as `inputs` dict."""
        try:
            parsed_inputs = json.loads(inputs)
        except json.JSONDecodeError:
            return json.dumps({"success": False, "error": "Invalid JSON for inputs"})
        run_result = monty.run(code, parsed_inputs)
        return json.dumps({
            "success": run_result.success,
            "value": run_result.value if run_result.success else None,
            "error": run_result.error,
        }, default=str)

    @mcp.tool()
    def run_tests(solution_code: str, test_code: str, inputs: str = "{}") -> str:
        """Run test assertions against solution code in sandbox."""
        try:
            parsed_inputs = json.loads(inputs)
        except json.JSONDecodeError:
            return json.dumps({"success": False, "error": "Invalid JSON for inputs"})
        result = monty.run_tests(solution_code, test_code, inputs=parsed_inputs)
        return json.dumps({
            "passed": result.passed,
            "failures": result.failures,
            "total": result.total,
        })

    @mcp.tool()
    def list_host_functions() -> str:
        """List all registered host functions with descriptions."""
        return json.dumps(monty.registry.descriptions, indent=2)

    @mcp.tool()
    def list_files() -> str:
        """List Python files in workspace directory."""
        files = sorted(f.name for f in monty.workspace.glob("*.py"))
        return json.dumps(files)

    @mcp.tool()
    def read_file(name: str) -> str:
        """Read a Python file from workspace."""
        path = monty.workspace / name
        if not path.exists() or ".." in name or "/" in name:
            return json.dumps({"error": f"{name} not found"})
        return path.read_text()

    @mcp.tool()
    def write_file(name: str, content: str) -> str:
        """Write/update a Python file in workspace."""
        if ".." in name or "/" in name:
            return json.dumps({"error": "invalid filename"})
        path = monty.workspace / name
        path.write_text(content)
        return json.dumps({"ok": True, "name": name})

    @mcp.tool()
    def run_file(name: str, inputs: str = "{}") -> str:
        """Run a workspace file in sandbox."""
        path = monty.workspace / name
        if not path.exists() or ".." in name or "/" in name:
            return json.dumps({"success": False, "error": f"{name} not found"})
        try:
            parsed_inputs = json.loads(inputs)
        except json.JSONDecodeError:
            return json.dumps({"success": False, "error": "Invalid JSON for inputs"})
        code = path.read_text()
        run_result = monty.run(code, parsed_inputs)
        return json.dumps({
            "success": run_result.success,
            "value": run_result.value if run_result.success else None,
            "error": run_result.error,
        }, default=str)

    return mcp


def main():
    import argparse
    from ..core import Monty as MontyClass

    p = argparse.ArgumentParser(prog="monty-mcp")
    p.add_argument("--workspace", default="workspace")
    p.add_argument("--name", default="monty-workspace")
    args = p.parse_args()

    monty = MontyClass(
        mcp={"name": args.name},
        workspace_dir=args.workspace,
    )
    server = create_mcp_server(monty)
    server.run()
