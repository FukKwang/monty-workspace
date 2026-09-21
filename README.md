# Monty Workspace

Sandboxed Python execution environment with host functions, web UI, and MCP server.

## Quick Start

```bash
pip install -e .
monty-web --workspace examples/lending/codes --host-module examples.lending.host_functions
```

Web UI at `http://localhost:8080`. MCP server via `monty-mcp`.

## Writing Code via API

Code files can be created and managed entirely through the REST API or MCP tools, without using the web UI. The same validation, documentation, and execution features apply.

### Workflow

1. **Save a file** — `POST /api/file`
2. **Check syntax errors** — response includes `syntax_error` field
3. **Inspect functions** — `GET /api/functions?file=<name>`
4. **Run the code** — `POST /api/run`
5. **Run tests** — `POST /api/test`

### API Endpoints

#### Files

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/files` | List all workspace files |
| GET | `/api/file?name=<name>` | Read file content |
| POST | `/api/file` | Save/update file (returns `syntax_error` if invalid) |
| GET | `/api/functions?file=<name>` | Extract function signatures and docstrings |
| GET | `/api/versions?name=<name>` | List file version history |
| POST | `/api/versions/restore` | Restore a previous version |

#### Execution

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/run` | Execute code in sandbox |
| POST | `/api/resume` | Resume a suspended execution |
| POST | `/api/test` | Run tests for a file |
| GET | `/api/runs?file=<name>&limit=50` | List execution history |
| GET | `/api/run-detail?id=<id>` | Get run details with function logs |
| GET | `/api/snapshots?status=pending` | List suspended execution snapshots |

#### Host Functions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/completions` | List host functions with descriptions and sample data |
| GET | `/api/samples` | Get sample data for host functions |

### Save a File

```bash
curl -X POST http://localhost:8080/api/file \
  -H "Content-Type: application/json" \
  -d '{"name": "my_code.py", "content": "result = {\"status\": \"ok\"}"}'
```

Response:
```json
{"ok": true, "syntax_error": null, "version": 1}
```

If the code has a syntax error:
```json
{"ok": true, "syntax_error": "SyntaxError: unexpected indent (line 3)", "version": 1}
```

The file is saved regardless of syntax errors (user may be mid-edit). Check `syntax_error` before running.

### Run a File

```bash
curl -X POST http://localhost:8080/api/run \
  -H "Content-Type: application/json" \
  -d '{"code": "result = {\"x\": 1}", "inputs": {}, "file_name": "my_code.py"}'
```

Response:
```json
{"success": true, "value": {"x": 1}, "error": null, "duration_ms": 12, "function_logs": []}
```

### Inspect Functions

```bash
curl http://localhost:8080/api/functions?file=my_code.py
```

Returns function signatures, parameters, types, defaults, and docstring documentation.

## Writing Code: Docstring Format

Use Google-style docstrings to document your code. The system parses these for the function discovery API and UI panel.

### Simple Script (no functions)

Use a module-level docstring at the top of the file:

```python
"""Look up borrower profile by name.

Args:
    borrower_name: Full name of borrower to search

Returns:
    borrower_id: Unique borrower identifier
    name: Borrower full name
    credit_score: Credit score (300-850)
"""
borrower = query_borrower({"name": inputs["borrower_name"]})
result = {
    "borrower_id": borrower.get("borrower_id"),
    "name": borrower.get("name"),
    "credit_score": borrower.get("credit_score"),
}
```

### Functions with Docstrings

```python
def get_borrower(name: str) -> dict:
    """Look up a single borrower by name.

    Args:
        name: Full name of the borrower to search

    Returns:
        borrower_id: Unique borrower identifier
        name: Borrower full name
        credit_score: Credit score (300-850)
    """
    return query_borrower({"name": name})
```

### Module + Function Docstrings Together

Both can coexist in the same file. Module docstring documents the script-level inputs/outputs, function docstrings document each function:

```python
"""Borrower search utilities.

Args:
    name: Borrower name to search (optional)
    city: City to search (optional)
"""

def get_borrower(name: str) -> dict:
    """Look up a single borrower by name.

    Args:
        name: Full name of the borrower

    Returns:
        borrower_id: Unique borrower identifier
        name: Borrower full name
    """
    return query_borrower({"name": name})

result = get_borrower(inputs.get("name", ""))
```

### Docstring Sections

| Section | Purpose |
|---------|---------|
| First line | Short description |
| `Args:` | Input parameters with descriptions |
| `Returns:` | Named return fields with descriptions |

Each field under `Args:` or `Returns:` follows `field_name: Description text` format.

### Code Conventions

- **`inputs`** — dict of runtime inputs, available as a global. Access via `inputs["key"]` or `inputs.get("key")`.
- **`result`** — assign your output to this variable. The sandbox captures it as the return value.
- **Host functions** — call registered host functions directly by name (e.g., `query_borrower({...})`). Use `GET /api/completions` to discover available functions.
- **Test files** — prefix with `test_` (e.g., `test_borrower_profile.py`). They pair with the solution file automatically.

## MCP Server

The MCP server exposes the same functionality as tools for LLM agents:

```bash
monty-mcp --workspace examples/lending/codes --name monty-workspace
```

Available tools: `run_code`, `run_file`, `run_tests`, `list_files`, `read_file`, `write_file`, `list_host_functions`, `list_snapshots`, `resume_snapshot`.

The `write_file` tool also returns `syntax_error` for Python files.
