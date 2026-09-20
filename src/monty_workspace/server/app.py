"""Web UI for monty-workspace. Code editor, sandbox runner, host function browser. Requires htmx 4.0."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

if TYPE_CHECKING:
    from ..core import Monty


_monty: Monty | None = None


def _e(text: str) -> str:
    return html.escape(str(text))


_CSS = """\
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0f1117;--surface:#1a1d27;--surface2:#242736;--border:#2e3348;
  --text:#e1e4ed;--dim:#8b90a5;--accent:#6c8cff;--accent2:#2ec4b6;
  --err:#ff6b6b;--ok:#51cf66;--code-bg:#141620;--hover:#2a2d3e;
  --radius:8px;
}
body{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
nav{display:flex;gap:0;border-bottom:1px solid var(--border);background:var(--surface);padding:0 1rem}
nav a{padding:.75rem 1.25rem;color:var(--dim);text-decoration:none;border-bottom:2px solid transparent;
font-weight:500;transition:all .15s;font-size:.9rem}
nav a:hover{color:var(--text)}
nav a.active{color:var(--accent);border-bottom-color:var(--accent)}
nav .logo{padding:.75rem 1.25rem .75rem 0;font-weight:700;color:var(--accent);font-size:.95rem;
border-right:1px solid var(--border);margin-right:.5rem}
#main{max-width:1200px;margin:0 auto;padding:1.5rem}

.panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
overflow:hidden;margin-bottom:1rem}
.panel-header{padding:.75rem 1rem;border-bottom:1px solid var(--border);display:flex;
align-items:center;gap:.75rem;background:var(--surface2)}
.panel-header h3{font-size:.85rem;font-weight:600;color:var(--dim);text-transform:uppercase;letter-spacing:.5px}
.panel-body{padding:1rem}

.editor-wrap{position:relative;min-height:300px}
.editor-wrap .cm-editor{height:400px;font-size:14px;background:var(--code-bg)}
.editor-wrap .cm-editor .cm-gutters{background:var(--surface);border-right:1px solid var(--border)}
.editor-wrap .cm-editor .cm-activeLineGutter,.editor-wrap .cm-editor .cm-activeLine{background:var(--surface2)}

.toolbar{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap}
.toolbar select,.toolbar input{padding:.4rem .6rem;background:var(--surface2);border:1px solid var(--border);
border-radius:4px;color:var(--text);font-size:.85rem}
.btn{padding:.5rem 1rem;border:none;border-radius:4px;cursor:pointer;font-weight:600;font-size:.85rem;
transition:opacity .15s}
.btn:hover{opacity:.85}
.btn-primary{background:var(--accent);color:#fff}
.btn-success{background:var(--ok);color:#111}
.btn-danger{background:var(--err);color:#fff}
.btn-ghost{background:transparent;border:1px solid var(--border);color:var(--dim)}
.btn-ghost:hover{border-color:var(--accent);color:var(--accent)}
.btn-sm{padding:.3rem .6rem;font-size:.8rem}

.output-area{background:var(--code-bg);border:1px solid var(--border);border-radius:var(--radius);
padding:1rem;font-family:'Fira Code',ui-monospace,monospace;font-size:.85rem;line-height:1.6;
white-space:pre-wrap;word-break:break-word;max-height:400px;overflow-y:auto;color:var(--dim)}
.output-area.ok{border-color:var(--ok);color:var(--ok)}
.output-area.err{border-color:var(--err);color:var(--err)}

.inputs-form{display:grid;grid-template-columns:auto 1fr;gap:.5rem .75rem;align-items:center;margin-bottom:.75rem}
.inputs-form label{font-size:.85rem;color:var(--dim);font-weight:500}
.inputs-form input{padding:.4rem .6rem;background:var(--code-bg);border:1px solid var(--border);
border-radius:4px;color:var(--text);font-size:.85rem}

.file-list{list-style:none}
.file-list li{padding:.5rem .75rem;border-bottom:1px solid var(--border);cursor:pointer;
font-size:.85rem;font-family:ui-monospace,monospace;transition:background .1s;display:flex;
justify-content:space-between;align-items:center}
.file-list li:hover{background:var(--hover)}
.file-list li:last-child{border-bottom:none}
.file-list .active{background:var(--surface2);color:var(--accent)}

.fn-card{padding:.75rem 1rem;border-bottom:1px solid var(--border)}
.fn-card:last-child{border-bottom:none}
.fn-card h4{font-size:.85rem;font-family:ui-monospace,monospace;color:var(--accent);margin-bottom:.25rem}
.fn-card p{font-size:.8rem;color:var(--dim);line-height:1.4}
.fn-card .tag{display:inline-block;font-size:.7rem;padding:.1rem .4rem;background:#3d2e1a;
border-radius:3px;color:#ffb347;margin-left:.5rem}

.empty{color:var(--dim);font-style:italic;padding:2rem;text-align:center}
.grid-2{display:grid;grid-template-columns:250px 1fr;gap:1rem}
@media(max-width:768px){.grid-2{grid-template-columns:1fr}.inputs-form{grid-template-columns:1fr}}
"""


def _page_html(body: str, active: str = "editor") -> str:
    tabs = [("editor", "Editor"), ("functions", "Functions")]
    nav = '<span class="logo">Monty</span>\n'
    for key, label in tabs:
        cls = "active" if active == key else ""
        nav += (
            f'<a href="#" hx-get="/{key}" hx-target="#main" hx-push-url="false" class="{cls}" '
            f'onclick="document.querySelectorAll(\'#nav a\').forEach(a=>a.classList.remove(\'active\'));'
            f'this.classList.add(\'active\')">{label}</a>\n'
        )
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monty Workspace</title>
<script src="https://cdn.jsdelivr.net/npm/htmx.org@4.0.0"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/codemirror@5.65.18/lib/codemirror.min.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/codemirror@5.65.18/theme/dracula.css">
<script src="https://cdn.jsdelivr.net/npm/codemirror@5.65.18/lib/codemirror.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/codemirror@5.65.18/mode/python/python.min.js"></script>
<style>{_CSS}</style>
</head><body>
<nav id="nav">{nav}</nav>
<div id="main">{body}</div>
</body></html>"""


def _editor_html() -> str:
    assert _monty is not None
    files = _list_workspace_files()
    file_items = ""
    for f in files:
        file_items += (
            f'<li hx-get="/api/file?name={_e(f)}" hx-target="#editor-area" '
            f'hx-swap="innerHTML">{_e(f)}</li>\n'
        )
    if not file_items:
        file_items = '<li class="empty">No files yet</li>'

    return f"""
<div class="grid-2">
  <div>
    <div class="panel">
      <div class="panel-header">
        <h3>Files</h3>
        <button class="btn btn-ghost btn-sm" style="margin-left:auto"
          onclick="document.getElementById('new-file-form').style.display='flex'">+ New</button>
      </div>
      <div id="file-list-area">
        <ul class="file-list">{file_items}</ul>
      </div>
      <div id="new-file-form" style="display:none;padding:.5rem;gap:.5rem;align-items:center">
        <input type="text" id="new-file-name" placeholder="filename.py"
          style="flex:1;padding:.4rem;background:var(--code-bg);border:1px solid var(--border);
          border-radius:4px;color:var(--text);font-size:.85rem">
        <button class="btn btn-primary btn-sm" onclick="createFile()">Create</button>
      </div>
    </div>
    <div class="panel">
      <div class="panel-header"><h3>Inputs</h3></div>
      <div class="panel-body" id="inputs-area">
        <div class="inputs-form" id="inputs-form"></div>
        <button class="btn btn-ghost btn-sm" onclick="addInput()">+ Add input</button>
      </div>
    </div>
  </div>
  <div>
    <div class="panel">
      <div class="panel-header">
        <h3 id="current-file-name">untitled.py</h3>
        <div class="toolbar" style="margin-left:auto">
          <button class="btn btn-primary" onclick="runCode()">&#9654; Run</button>
          <button class="btn btn-success btn-sm" onclick="saveFile()">Save</button>
        </div>
      </div>
      <div id="editor-area">
        <div class="editor-wrap">
          <textarea id="code-editor">result = "Hello from Monty!"</textarea>
        </div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-header"><h3>Output</h3></div>
      <div class="panel-body">
        <div class="output-area" id="output-area">Run code to see output...</div>
      </div>
    </div>
  </div>
</div>
<script>
var editor = CodeMirror.fromTextArea(document.getElementById('code-editor'), {{
  mode: 'python',
  theme: 'dracula',
  lineNumbers: true,
  indentUnit: 4,
  tabSize: 4,
  indentWithTabs: false,
  extraKeys: {{"Tab": function(cm) {{ cm.replaceSelection("    ", "end"); }}}},
  viewportMargin: Infinity
}});
editor.setSize(null, 400);
var currentFile = '';

function loadFile(name, content) {{
  currentFile = name;
  editor.setValue(content);
  document.getElementById('current-file-name').textContent = name;
  document.querySelectorAll('.file-list li').forEach(function(li) {{
    li.classList.toggle('active', li.textContent.trim() === name);
  }});
}}

function createFile() {{
  var name = document.getElementById('new-file-name').value.trim();
  if (!name) return;
  if (!name.endsWith('.py')) name += '.py';
  fetch('/api/file', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{name: name, content: '# ' + name + '\\nresult = None\\n'}})
  }}).then(function() {{
    document.getElementById('new-file-name').value = '';
    document.getElementById('new-file-form').style.display = 'none';
    refreshFileList();
    loadFile(name, '# ' + name + '\\nresult = None\\n');
  }});
}}

function saveFile() {{
  if (!currentFile) return;
  fetch('/api/file', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{name: currentFile, content: editor.getValue()}})
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    var out = document.getElementById('output-area');
    out.textContent = 'Saved ' + currentFile;
    out.className = 'output-area ok';
  }});
}}

function runCode() {{
  var inputs = {{}};
  document.querySelectorAll('#inputs-form .input-row').forEach(function(row) {{
    var key = row.querySelector('.input-key').value.trim();
    var val = row.querySelector('.input-val').value;
    if (key) inputs[key] = val;
  }});
  var out = document.getElementById('output-area');
  out.textContent = 'Running...';
  out.className = 'output-area';
  fetch('/api/run', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{code: editor.getValue(), inputs: inputs}})
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (d.success) {{
      out.textContent = JSON.stringify(d.value, null, 2);
      out.className = 'output-area ok';
    }} else {{
      out.textContent = d.error || 'Unknown error';
      out.className = 'output-area err';
    }}
  }}).catch(function(e) {{
    out.textContent = 'Request failed: ' + e;
    out.className = 'output-area err';
  }});
}}

function addInput() {{
  var form = document.getElementById('inputs-form');
  var row = document.createElement('div');
  row.className = 'input-row';
  row.style.display = 'contents';
  row.innerHTML = '<input class="input-key" type="text" placeholder="key" style="padding:.4rem;background:var(--code-bg);border:1px solid var(--border);border-radius:4px;color:var(--text);font-size:.85rem">'
    + '<div style="display:flex;gap:.25rem"><input class="input-val" type="text" placeholder="value" style="flex:1;padding:.4rem;background:var(--code-bg);border:1px solid var(--border);border-radius:4px;color:var(--text);font-size:.85rem">'
    + '<button class="btn btn-danger btn-sm" onclick="this.closest(\'.input-row\').remove()">x</button></div>';
  form.appendChild(row);
}}

function refreshFileList() {{
  fetch('/api/files').then(function(r) {{ return r.json(); }}).then(function(files) {{
    var ul = document.querySelector('#file-list-area ul');
    ul.innerHTML = '';
    files.forEach(function(f) {{
      var li = document.createElement('li');
      li.textContent = f;
      li.setAttribute('hx-get', '/api/file?name=' + encodeURIComponent(f));
      li.setAttribute('hx-target', '#editor-area');
      li.setAttribute('hx-swap', 'innerHTML');
      li.onclick = function() {{
        fetch('/api/file?name=' + encodeURIComponent(f))
          .then(function(r) {{ return r.json(); }})
          .then(function(d) {{ loadFile(f, d.content); }});
      }};
      if (f === currentFile) li.classList.add('active');
      ul.appendChild(li);
    }});
    htmx.process(ul);
  }});
}}
</script>"""


def _functions_html() -> str:
    assert _monty is not None
    descs = _monty.registry.descriptions
    human_fns = _monty.registry.human_input_functions
    if not descs:
        return '<div class="empty">No host functions registered.</div>'
    cards = ""
    for name, desc in sorted(descs.items()):
        tag = ' <span class="tag">human input</span>' if name in human_fns else ""
        cards += f'<div class="fn-card"><h4>{_e(name)}{tag}</h4><p>{_e(desc)}</p></div>\n'
    return f"""<div class="panel">
<div class="panel-header"><h3>Host Functions ({len(descs)})</h3></div>
{cards}
</div>"""


def _list_workspace_files() -> list[str]:
    assert _monty is not None
    ws = _monty.workspace
    return sorted(f.name for f in ws.glob("*.py"))


async def index(request: Request):
    return HTMLResponse(_page_html(_editor_html()))


async def editor_partial(request: Request):
    return HTMLResponse(_editor_html())


async def functions_partial(request: Request):
    return HTMLResponse(_functions_html())


async def api_files(request: Request):
    return JSONResponse(_list_workspace_files())


async def api_file_get(request: Request):
    assert _monty is not None
    name = request.query_params.get("name", "")
    path = _monty.workspace / name
    if not path.exists() or not path.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    content = path.read_text()
    return JSONResponse({"name": name, "content": content})


async def api_file_save(request: Request):
    assert _monty is not None
    body = await request.json()
    name = body.get("name", "").strip()
    content = body.get("content", "")
    if not name or ".." in name or "/" in name:
        return JSONResponse({"error": "invalid filename"}, status_code=400)
    path = _monty.workspace / name
    path.write_text(content)
    return JSONResponse({"ok": True, "name": name})


async def api_run(request: Request):
    assert _monty is not None
    body = await request.json()
    code = body.get("code", "")
    inputs = body.get("inputs", {})
    result = _monty.run(code, inputs)
    return JSONResponse({
        "success": result.success,
        "value": result.value if result.success else None,
        "error": result.error,
    })


def create_app(monty: Monty) -> Starlette:
    global _monty
    _monty = monty
    return Starlette(routes=[
        Route("/", index),
        Route("/editor", editor_partial),
        Route("/functions", functions_partial),
        Route("/api/files", api_files),
        Route("/api/file", api_file_get),
        Route("/api/file", api_file_save, methods=["POST"]),
        Route("/api/run", api_run, methods=["POST"]),
    ])


def main():
    import argparse
    from ..core import Monty as MontyClass
    import uvicorn

    p = argparse.ArgumentParser(prog="monty-web")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--workspace", default="workspace")
    args = p.parse_args()

    monty = MontyClass(
        server={"host": args.host, "port": args.port},
        workspace_dir=args.workspace,
    )
    app = create_app(monty)
    print(f"monty-workspace: http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
