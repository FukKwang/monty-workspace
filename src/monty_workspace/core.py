from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .config import MontyConfig, SandboxConfig, ServerConfig, McpConfig
from .sandbox.registry import HostFunctionRegistry
from .sandbox.runner import SandboxRunner, RunResult, TestResult
from .storage import Storage

from .sandbox.formulas import FormulaRegistry


class Monty:
    def __init__(
        self,
        *,
        sandbox: dict | SandboxConfig | None = None,
        server: dict | ServerConfig | None = None,
        mcp: dict | McpConfig | None = None,
        workspace_dir: str | Path | None = None,
    ):
        overrides: dict[str, Any] = {}
        if sandbox is not None:
            overrides["sandbox"] = sandbox if isinstance(sandbox, SandboxConfig) else SandboxConfig(**sandbox)
        if server is not None:
            overrides["server"] = server if isinstance(server, ServerConfig) else ServerConfig(**server)
        if mcp is not None:
            overrides["mcp"] = mcp if isinstance(mcp, McpConfig) else McpConfig(**mcp)
        if workspace_dir is not None:
            overrides["workspace_dir"] = Path(workspace_dir)

        self.config = MontyConfig(**overrides)
        self.registry = HostFunctionRegistry()
        self.storage = Storage(self.config.workspace_dir)
        self._runner: SandboxRunner | None = None
        self.formulas = FormulaRegistry(self.storage)
        self._register_formula_functions()

    @property
    def runner(self) -> SandboxRunner:
        if self._runner is None:
            self._runner = SandboxRunner(self.registry, self.config.sandbox.clamp())
        return self._runner

    def _register_formula_functions(self):
        for name, (desc, fn) in self.formulas.build_host_functions().items():
            self.registry.register(name, desc)(fn)

    def host_function(self, name: str, description: str, *,
                      human_input: bool = False, sample: Any = None) -> Callable:
        return self.registry.register(name, description, human_input=human_input, sample=sample)

    def load_host_module(self, module: str) -> None:
        """Import `module` (dotted path, resolved from cwd too) and call its `register_all(monty)`."""
        import importlib
        import os
        import sys
        if os.getcwd() not in sys.path:
            sys.path.insert(0, os.getcwd())
        mod = importlib.import_module(module)
        if not hasattr(mod, "register_all"):
            raise AttributeError(f"host module {module!r} has no register_all(monty) function")
        mod.register_all(self)

    def run(self, code: str, inputs: dict[str, Any] | None = None, **kwargs) -> RunResult:
        return self.runner.run(code, inputs, storage=self.storage, **kwargs)

    def resume_snapshot(self, snapshot_id: int, value: Any) -> RunResult:
        snap = self.storage.get_snapshot(snapshot_id)
        if not snap:
            return RunResult(success=False, error=f"Snapshot {snapshot_id} not found")
        if snap["status"] != "pending":
            return RunResult(success=False, error=f"Snapshot {snapshot_id} already {snap['status']}")
        result = self.runner.resume_snapshot(
            snap["blob"], value, storage=self.storage, file_name=snap["file_name"],
        )
        self.storage.resolve_snapshot(snapshot_id, "resumed" if not result.suspended else "chained")
        return result

    def run_tests(self, solution_code: str, test_code: str, **kwargs) -> TestResult:
        return self.runner.run_tests(solution_code, test_code, **kwargs)

    def get_test_file(self, file_name: str) -> str | None:
        if file_name.startswith("test_"):
            return file_name
        test_name = f"test_{file_name}"
        f = self.storage.get_file(test_name)
        return test_name if f else None

    def get_solution_file(self, test_name: str) -> str | None:
        if not test_name.startswith("test_"):
            return test_name
        sol_name = test_name[5:]
        f = self.storage.get_file(sol_name)
        return sol_name if f else None

    @property
    def workspace(self) -> Path:
        self.config.workspace_dir.mkdir(parents=True, exist_ok=True)
        return self.config.workspace_dir

    def serve(self, **kwargs):
        from .server import create_app
        import uvicorn
        app = create_app(self)
        host = kwargs.get("host", self.config.server.host)
        port = kwargs.get("port", self.config.server.port)
        print(f"monty-workspace: http://{host}:{port}")
        uvicorn.run(app, host=host, port=port, log_level="info")

    def serve_mcp(self):
        from .mcp import create_mcp_server
        server = create_mcp_server(self)
        server.run()
