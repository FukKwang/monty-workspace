from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .config import MontyConfig, SandboxConfig, ServerConfig, McpConfig
from .sandbox.registry import HostFunctionRegistry
from .sandbox.runner import SandboxRunner, RunResult, TestResult
from .storage import Storage


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

    @property
    def runner(self) -> SandboxRunner:
        if self._runner is None:
            self._runner = SandboxRunner(self.registry, self.config.sandbox.clamp())
        return self._runner

    def host_function(self, name: str, description: str, *, human_input: bool = False) -> Callable:
        return self.registry.register(name, description, human_input=human_input)

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
