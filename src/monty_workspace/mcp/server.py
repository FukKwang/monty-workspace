"""MCP server exposing Monty sandbox as tools for any LLM."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

try:
    from mcp.server.fastmcp import FastMCP as MCPServer
except (ImportError, ModuleNotFoundError):
    from mcp.server.mcpserver import MCPServer

if TYPE_CHECKING:
    from ..core import Monty


def create_mcp_server(monty: Monty) -> MCPServer:
    mcp = MCPServer(monty.config.mcp.name)

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
            "function_logs": run_result.function_logs or None,
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
        """List Python files in workspace."""
        return json.dumps(monty.storage.list_files())

    @mcp.tool()
    def read_file(name: str) -> str:
        """Read a Python file from workspace."""
        f = monty.storage.get_file(name)
        if not f:
            return json.dumps({"error": f"{name} not found"})
        return f["content"]

    @mcp.tool()
    def write_file(name: str, content: str) -> str:
        """Write/update a Python file in workspace."""
        if ".." in name or "/" in name:
            return json.dumps({"error": "invalid filename"})
        result = monty.storage.save_file(name, content)
        return json.dumps({"ok": True, **result})

    @mcp.tool()
    def list_snapshots(status: str = "pending") -> str:
        """List execution snapshots (suspended runs awaiting resume). Status: pending, resumed, expired."""
        return json.dumps(monty.storage.list_snapshots(status=status or None))

    @mcp.tool()
    def resume_snapshot(snapshot_id: int, value: str = "null") -> str:
        """Resume a suspended execution snapshot with a return value. Value is JSON-parsed."""
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = value
        result = monty.resume_snapshot(snapshot_id, parsed)
        if result.suspended:
            return json.dumps({
                "suspended": True,
                "snapshot_id": result.snapshot_id,
                "function_name": result.snapshot_function,
                "args": result.snapshot_args,
            })
        return json.dumps({
            "success": result.success,
            "value": result.value if result.success else None,
            "error": result.error,
        }, default=str)

    @mcp.tool()
    def run_file(name: str, inputs: str = "{}") -> str:
        """Run a workspace file in sandbox."""
        f = monty.storage.get_file(name)
        if not f:
            return json.dumps({"success": False, "error": f"{name} not found"})
        try:
            parsed_inputs = json.loads(inputs)
        except json.JSONDecodeError:
            return json.dumps({"success": False, "error": "Invalid JSON for inputs"})
        run_result = monty.run(f["content"], parsed_inputs)
        return json.dumps({
            "success": run_result.success,
            "value": run_result.value if run_result.success else None,
            "error": run_result.error,
            "function_logs": run_result.function_logs or None,
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
