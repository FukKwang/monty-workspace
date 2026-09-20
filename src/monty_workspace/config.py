from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class SandboxConfig(BaseModel):
    max_duration_secs: float = 10.0
    max_memory: int = 64_000_000
    max_recursion_depth: int = 500

    min_duration_secs: float = 1.0
    cap_duration_secs: float = 60.0
    min_memory: int = 16_000_000
    cap_memory: int = 256_000_000

    def clamp(self, requested: dict | None = None) -> dict:
        r = requested or {}
        dur = r.get("max_duration_secs") or self.max_duration_secs
        mem = r.get("max_memory") or self.max_memory
        return {
            "max_duration_secs": max(self.min_duration_secs, min(dur, self.cap_duration_secs)),
            "max_memory": max(self.min_memory, min(int(mem), self.cap_memory)),
            "max_recursion_depth": min(
                int(r.get("max_recursion_depth") or self.max_recursion_depth),
                self.max_recursion_depth,
            ),
        }


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080


class McpConfig(BaseModel):
    name: str = "monty-workspace"


class MontyConfig(BaseSettings):
    sandbox: SandboxConfig = SandboxConfig()
    server: ServerConfig = ServerConfig()
    mcp: McpConfig = McpConfig()
    workspace_dir: Path = Path("workspace")

    model_config = SettingsConfigDict(env_prefix="MONTY_", env_nested_delimiter="__")
