"""Web UI for monty-workspace. Code editor, sandbox runner, host function browser. Requires htmx 4.0."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

from ..sandbox.runner import SandboxRunner

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
  --bg:#f5f6f8;--surface:#fff;--surface2:#f0f1f4;--border:#dcdfe6;
  --text:#1a1d27;--dim:#6b7280;--accent:#4f6df5;--accent2:#0ea5a0;
  --err:#dc2626;--ok:#16a34a;--code-bg:#fafbfc;--hover:#eef0f4;
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

.toolbar{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap}
.toolbar select,.toolbar input{padding:.4rem .6rem;background:var(--surface2);border:1px solid var(--border);
border-radius:4px;color:var(--text);font-size:.85rem}
.btn{padding:.5rem 1rem;border:none;border-radius:4px;cursor:pointer;font-weight:600;font-size:.85rem;
transition:opacity .15s}
.btn:hover{opacity:.85}
.btn-primary{background:var(--accent);color:#fff}
.btn-success{background:var(--ok);color:#fff}
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
.fn-card .tag{display:inline-block;font-size:.7rem;padding:.1rem .4rem;background:#fef3c7;
border-radius:3px;color:#92400e;margin-left:.5rem}

.empty{color:var(--dim);font-style:italic;padding:2rem;text-align:center}
.grid-2{display:grid;grid-template-columns:250px 1fr;gap:1rem}
@media(max-width:768px){.grid-2{grid-template-columns:1fr}.inputs-form{grid-template-columns:1fr}}

.CodeMirror-hints{z-index:100;font-family:ui-monospace,monospace;font-size:13px;
background:var(--surface);border:1px solid var(--border);border-radius:4px;
box-shadow:0 4px 12px rgba(0,0,0,.08);max-height:220px;overflow-y:auto;padding:2px 0}
.CodeMirror-hint{padding:4px 10px;color:var(--text);cursor:pointer;white-space:nowrap}
.CodeMirror-hint-active{background:var(--accent);color:#fff;border-radius:2px}
.hint-sig{font-size:11px;color:var(--dim);margin-left:8px}
.CodeMirror-hint-active .hint-sig{color:rgba(255,255,255,.7)}

.fn-tooltip{position:absolute;z-index:200;background:var(--surface);border:1px solid var(--border);
border-radius:6px;box-shadow:0 4px 16px rgba(0,0,0,.1);padding:8px 12px;max-width:420px;
font-size:13px;line-height:1.5;pointer-events:none}
.fn-tooltip .fn-tip-name{font-weight:700;color:var(--accent);font-family:ui-monospace,monospace}
.fn-tooltip .fn-tip-desc{color:var(--dim);margin-top:2px}

.input-chip{display:inline-flex;align-items:center;gap:4px;background:var(--surface);
border:1px solid var(--border);border-radius:4px;padding:2px 4px 2px 8px;font-size:.8rem}
.input-chip .chip-key{font-family:ui-monospace,monospace;color:var(--accent);font-weight:600}
.input-chip input{width:80px;padding:2px 6px;border:1px solid var(--border);border-radius:3px;
font-size:.8rem;background:var(--code-bg);color:var(--text);font-family:ui-monospace,monospace}
.input-chip input:focus{outline:none;border-color:var(--accent)}

.run-row{padding:.5rem 1rem;border-bottom:1px solid var(--border);display:flex;align-items:center;
gap:.75rem;font-size:.82rem;cursor:pointer;transition:background .1s}
.run-row:hover{background:var(--hover)}
.run-row .status{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.run-row .status.ok{background:var(--ok)}
.run-row .status.err{background:var(--err)}
.run-row .meta{color:var(--dim);margin-left:auto;font-size:.75rem;white-space:nowrap}
.run-detail{padding:1rem}
.run-detail pre{background:var(--code-bg);border:1px solid var(--border);border-radius:4px;
padding:.75rem;font-size:.8rem;overflow-x:auto;white-space:pre-wrap;max-height:300px;overflow-y:auto}
.run-detail h4{font-size:.8rem;color:var(--dim);margin-bottom:.25rem;text-transform:uppercase}

.version-row{padding:.4rem .75rem;border-bottom:1px solid var(--border);display:flex;
align-items:center;gap:.5rem;font-size:.8rem;cursor:pointer;transition:background .1s}
.version-row:hover{background:var(--hover)}
.version-row .meta{color:var(--dim);flex:1}
.version-row .btn{opacity:0;transition:opacity .1s}
.version-row:hover .btn{opacity:1}

.modal-overlay{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.3);
z-index:300;display:flex;align-items:center;justify-content:center}
.modal{background:var(--surface);border:1px solid var(--border);border-radius:8px;
box-shadow:0 8px 32px rgba(0,0,0,.15);max-width:700px;width:90%;max-height:80vh;overflow:hidden;
display:flex;flex-direction:column}
.modal-header{padding:.75rem 1rem;border-bottom:1px solid var(--border);display:flex;
align-items:center;justify-content:space-between;background:var(--surface2)}
.modal-header h3{font-size:.9rem;font-weight:600}
.modal-body{overflow-y:auto;flex:1}

.suspend-bar{background:#fef3c7;border:1px solid #fbbf24;border-radius:var(--radius);padding:.75rem 1rem;
margin-top:.75rem;display:flex;align-items:center;gap:.75rem;flex-wrap:wrap}
.suspend-bar .suspend-label{font-weight:600;color:#92400e;font-size:.85rem}
.suspend-bar .suspend-fn{font-family:ui-monospace,monospace;color:#b45309;font-size:.85rem}
.suspend-bar input{flex:1;min-width:120px;padding:.4rem .6rem;border:1px solid #fbbf24;border-radius:4px;
background:#fff;color:var(--text);font-size:.85rem;font-family:ui-monospace,monospace}
.suspend-bar .btn{white-space:nowrap}

.cfn-card{padding:.75rem 1rem;border-bottom:1px solid var(--border)}
.cfn-card:last-child{border-bottom:none}
.cfn-sig{font-family:ui-monospace,monospace;font-size:.85rem;font-weight:600;color:var(--accent)}
.cfn-sig .cfn-ret{color:var(--accent2);font-weight:500}
.cfn-desc{color:var(--dim);font-size:.82rem;margin-top:2px}
.cfn-table{width:100%;border-collapse:collapse;margin-top:.4rem;font-size:.78rem}
.cfn-table th{text-align:left;padding:3px 8px;color:var(--dim);font-weight:600;font-size:.7rem;
text-transform:uppercase;letter-spacing:.5px;border-bottom:1px solid var(--border)}
.cfn-table td{padding:3px 8px;border-bottom:1px solid var(--surface2)}
.cfn-table td:first-child{font-family:ui-monospace,monospace;color:var(--accent);font-weight:500}
.cfn-table .cfn-type{color:var(--accent2);font-family:ui-monospace,monospace}
.cfn-table .cfn-default{color:var(--dim);font-style:italic;font-size:.75rem}
.cfn-section{font-size:.72rem;font-weight:600;color:var(--dim);text-transform:uppercase;
letter-spacing:.5px;margin-top:.5rem;margin-bottom:.15rem}
"""


def _page_html(body: str, active: str = "editor") -> str:
    tabs = [("editor", "Editor"), ("functions", "Functions"), ("history", "History")]
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
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/codemirror@5.65.18/addon/hint/show-hint.css">
<script src="https://cdn.jsdelivr.net/npm/codemirror@5.65.18/lib/codemirror.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/codemirror@5.65.18/mode/python/python.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/codemirror@5.65.18/addon/hint/show-hint.min.js"></script>
<style>{_CSS}</style>
</head><body>
<nav id="nav">{nav}</nav>
<div id="main">{body}</div>
</body></html>"""


def _editor_html() -> str:
    assert _monty is not None
    files = _list_workspace_files()
    test_files = {f for f in files if f.startswith("test_")}
    solution_files = [f for f in files if not f.startswith("test_")]
    orphan_tests = [f for f in test_files if f"test_{f}" not in test_files and f[5:] not in solution_files]

    file_items = ""
    for f in solution_files:
        file_items += (
            f'<li onclick="fetch(\'/api/file?name={_e(f)}\').then(function(r){{return r.json()}}).then(function(d){{loadFile(d.name,d.content)}})">{_e(f)}</li>\n'
        )
        tf = f"test_{f}"
        if tf in test_files:
            file_items += (
                f'<li onclick="fetch(\'/api/file?name={_e(tf)}\').then(function(r){{return r.json()}}).then(function(d){{loadFile(d.name,d.content)}})" '
                f'style="padding-left:2rem;font-size:.78rem;color:var(--dim)">'
                f'<span style="color:var(--accent2);margin-right:4px">&#9881;</span>{_e(tf)}</li>\n'
            )
    for f in orphan_tests:
        file_items += (
            f'<li onclick="fetch(\'/api/file?name={_e(f)}\').then(function(r){{return r.json()}}).then(function(d){{loadFile(d.name,d.content)}})">{_e(f)}</li>\n'
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
  </div>
  <div>
    <div class="panel">
      <div class="panel-header">
        <h3 id="current-file-name">untitled.py</h3>
        <div class="toolbar" style="margin-left:auto">
          <button class="btn btn-primary" onclick="runCode()">&#9654; Run</button>
          <button class="btn btn-ghost btn-sm" id="btn-test" onclick="runTests()" style="display:none">&#9881; Test</button>
          <button class="btn btn-success btn-sm" onclick="saveFile()">Save</button>
          <button class="btn btn-ghost btn-sm" onclick="showVersions()">Versions</button>
        </div>
      </div>
      <div id="inputs-bar" style="display:none;padding:.5rem 1rem;border-bottom:1px solid var(--border);
        display:flex;flex-wrap:wrap;gap:.4rem;align-items:center;background:var(--surface2)">
        <span style="font-size:.75rem;color:var(--dim);font-weight:600;text-transform:uppercase;letter-spacing:.5px;margin-right:.25rem">Inputs</span>
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
    <div class="panel" id="code-functions-panel" style="display:none">
      <div class="panel-header"><h3 id="code-functions-title">Code Functions</h3></div>
      <div id="code-functions-body" style="padding:0"></div>
    </div>
  </div>
</div>
<script>
var hostFunctions = [];
var hostFnMap = {{}};
fetch('/api/completions').then(function(r){{ return r.json(); }}).then(function(d){{
  hostFunctions = d;
  d.forEach(function(f){{ hostFnMap[f.name] = f; }});
}});

var BUILTINS = [
  {{n:'abs',d:'abs(x) -> absolute value',cat:'builtin'}},
  {{n:'all',d:'all(iterable) -> True if all elements truthy',cat:'builtin'}},
  {{n:'any',d:'any(iterable) -> True if any element truthy',cat:'builtin'}},
  {{n:'bool',d:'bool(x) -> boolean value',cat:'builtin'}},
  {{n:'chr',d:'chr(i) -> character from Unicode code point',cat:'builtin'}},
  {{n:'dict',d:'dict() -> new dictionary',cat:'builtin'}},
  {{n:'dir',d:'dir(obj) -> list of names in scope',cat:'builtin'}},
  {{n:'enumerate',d:'enumerate(iterable) -> pairs (eager, not lazy)',cat:'builtin'}},
  {{n:'eval',d:'eval(source) -> evaluate expression (source text only)',cat:'builtin'}},
  {{n:'exec',d:'exec(source) -> execute statements (source text only)',cat:'builtin'}},
  {{n:'filter',d:'filter(fn, iterable) -> filtered list (eager)',cat:'builtin'}},
  {{n:'float',d:'float(x) -> floating point number',cat:'builtin'}},
  {{n:'format',d:'format(value, spec) -> formatted string',cat:'builtin'}},
  {{n:'frozenset',d:'frozenset(iterable) -> immutable set',cat:'builtin'}},
  {{n:'getattr',d:'getattr(obj, name, default)',cat:'builtin'}},
  {{n:'hasattr',d:'hasattr(obj, name) -> bool',cat:'builtin'}},
  {{n:'hash',d:'hash(obj) -> hash value',cat:'builtin'}},
  {{n:'hex',d:'hex(x) -> hex string',cat:'builtin'}},
  {{n:'id',d:'id(obj) -> identity',cat:'builtin'}},
  {{n:'input',d:'input(prompt) -> string from user',cat:'builtin'}},
  {{n:'int',d:'int(x) -> integer',cat:'builtin'}},
  {{n:'isinstance',d:'isinstance(obj, class) -> bool',cat:'builtin'}},
  {{n:'issubclass',d:'issubclass(cls, parent) -> bool',cat:'builtin'}},
  {{n:'iter',d:'iter(obj) -> iterator',cat:'builtin'}},
  {{n:'len',d:'len(obj) -> length',cat:'builtin'}},
  {{n:'list',d:'list(iterable) -> new list',cat:'builtin'}},
  {{n:'locals',d:'locals() -> dict of local variables',cat:'builtin'}},
  {{n:'map',d:'map(fn, iterable) -> mapped list (eager)',cat:'builtin'}},
  {{n:'max',d:'max(iterable) -> largest item',cat:'builtin'}},
  {{n:'min',d:'min(iterable) -> smallest item',cat:'builtin'}},
  {{n:'next',d:'next(iterator) -> next item',cat:'builtin'}},
  {{n:'oct',d:'oct(x) -> octal string',cat:'builtin'}},
  {{n:'ord',d:'ord(c) -> Unicode code point',cat:'builtin'}},
  {{n:'pow',d:'pow(base, exp) -> power',cat:'builtin'}},
  {{n:'print',d:'print(*args) -> output to stdout',cat:'builtin'}},
  {{n:'range',d:'range(stop) or range(start, stop, step)',cat:'builtin'}},
  {{n:'repr',d:'repr(obj) -> printable representation',cat:'builtin'}},
  {{n:'reversed',d:'reversed(seq) -> reversed list (eager)',cat:'builtin'}},
  {{n:'round',d:'round(number, ndigits)',cat:'builtin'}},
  {{n:'set',d:'set(iterable) -> new set',cat:'builtin'}},
  {{n:'setattr',d:'setattr(obj, name, value)',cat:'builtin'}},
  {{n:'slice',d:'slice(stop) -> slice object',cat:'builtin'}},
  {{n:'sorted',d:'sorted(iterable) -> new sorted list',cat:'builtin'}},
  {{n:'str',d:'str(obj) -> string',cat:'builtin'}},
  {{n:'sum',d:'sum(iterable) -> total',cat:'builtin'}},
  {{n:'tuple',d:'tuple(iterable) -> new tuple',cat:'builtin'}},
  {{n:'type',d:'type(obj) -> type of object',cat:'builtin'}},
  {{n:'zip',d:'zip(*iterables) -> zipped list (eager)',cat:'builtin'}},
  {{n:'ValueError',d:'Exception: inappropriate value',cat:'exception'}},
  {{n:'TypeError',d:'Exception: inappropriate type',cat:'exception'}},
  {{n:'KeyError',d:'Exception: key not found in dict',cat:'exception'}},
  {{n:'IndexError',d:'Exception: index out of range',cat:'exception'}},
  {{n:'AttributeError',d:'Exception: attribute not found',cat:'exception'}},
  {{n:'RuntimeError',d:'Exception: generic runtime error',cat:'exception'}},
  {{n:'StopIteration',d:'Exception: iterator exhausted',cat:'exception'}},
  {{n:'AssertionError',d:'Exception: assert failed (pytest-style messages)',cat:'exception'}},
  {{n:'NameError',d:'Exception: name not found',cat:'exception'}},
  {{n:'MemoryError',d:'Exception: memory limit exceeded',cat:'exception'}},
  {{n:'ZeroDivisionError',d:'Exception: division by zero',cat:'exception'}},
  {{n:'NotImplementedError',d:'Exception: not implemented',cat:'exception'}},
  {{n:'True',d:'Boolean true',cat:'const'}},
  {{n:'False',d:'Boolean false',cat:'const'}},
  {{n:'None',d:'None value',cat:'const'}},
  {{n:'inputs',d:'Dict of input values passed to sandbox',cat:'sandbox'}},
  {{n:'result',d:'Assign to this variable to return output',cat:'sandbox'}}
];

var MODULES = [
  {{n:'math',d:'Math functions: sqrt, sin, cos, log, pi, e, etc.',cat:'module'}},
  {{n:'json',d:'JSON encode/decode: dumps, loads',cat:'module'}},
  {{n:'re',d:'Regex (Rust fancy-regex backend, no bytes/VERBOSE)',cat:'module'}},
  {{n:'random',d:'Random: random, randint, choice, shuffle, seed',cat:'module'}},
  {{n:'datetime',d:'Date/time: datetime, date, time, timedelta',cat:'module'}},
  {{n:'collections',d:'OrderedDict, defaultdict, Counter, deque, namedtuple',cat:'module'}},
  {{n:'itertools',d:'All itertools functions (complete)',cat:'module'}},
  {{n:'functools',d:'Partial functools: reduce, partial, lru_cache',cat:'module'}},
  {{n:'copy',d:'copy, deepcopy',cat:'module'}},
  {{n:'time',d:'Partial time module',cat:'module'}},
  {{n:'base64',d:'Base64 encoding/decoding',cat:'module'}},
  {{n:'asyncio',d:'Only: run, gather, sleep (no event loop)',cat:'module'}},
  {{n:'dataclasses',d:'@dataclass (only eq= and frozen= options)',cat:'module'}},
  {{n:'typing',d:'Type hints (runtime generic aliases, | unions)',cat:'module'}},
  {{n:'os',d:'Partial os module (limited)',cat:'module'}},
  {{n:'pathlib',d:'Partial pathlib module (limited)',cat:'module'}},
  {{n:'sys',d:'Partial sys module (no sys.path)',cat:'module'}},
  {{n:'unicodedata',d:'Unicode character data (partial)',cat:'module'}},
  {{n:'binascii',d:'Binary/ASCII conversions (partial)',cat:'module'}}
];

var BLOCKED = [
  {{n:'compile',d:'BLOCKED: not available in sandbox',cat:'blocked'}},
  {{n:'globals',d:'BLOCKED: not available in sandbox',cat:'blocked'}},
  {{n:'__import__',d:'BLOCKED: use import statement instead',cat:'blocked'}},
  {{n:'super',d:'BLOCKED: no class inheritance in sandbox',cat:'blocked'}},
  {{n:'yield',d:'BLOCKED: no generators (gen expressions become lists)',cat:'blocked'}},
  {{n:'match',d:'BLOCKED: match statements not supported',cat:'blocked'}},
  {{n:'del',d:'BLOCKED: del statements not supported',cat:'blocked'}}
];

var allCompletions = [];
BUILTINS.forEach(function(b) {{ allCompletions.push(b); }});
MODULES.forEach(function(m) {{ allCompletions.push(m); }});
BLOCKED.forEach(function(b) {{ allCompletions.push(b); }});

var catColors = {{
  'host':'var(--accent)','builtin':'#16a34a','module':'#9333ea',
  'exception':'#dc2626','const':'#ca8a04','sandbox':'#0ea5a0','blocked':'#9ca3af'
}};
var catLabels = {{
  'host':'host','builtin':'builtin','module':'import','exception':'except',
  'const':'const','sandbox':'sandbox','blocked':'blocked'
}};

function montyHint(cm) {{
  var cur = cm.getCursor();
  var token = cm.getTokenAt(cur);
  var word = token.string;
  if (!word || word.length < 1) return;

  var line = cm.getLine(cur.line).slice(0, cur.ch);
  var isImport = /^\\s*(import|from)\\s+/.test(line);

  var results = [];

  if (isImport) {{
    MODULES.forEach(function(m) {{
      if (m.n.indexOf(word) === 0) results.push(m);
    }});
  }} else {{
    hostFunctions.forEach(function(f) {{
      if (f.name.indexOf(word) === 0) results.push({{n:f.name,d:f.description,cat:'host',paren:true}});
    }});
    allCompletions.forEach(function(c) {{
      if (c.n.indexOf(word) === 0) results.push(c);
    }});
  }}

  if (!results.length) return;

  return {{
    list: results.map(function(r) {{
      var color = catColors[r.cat] || 'var(--dim)';
      var label = catLabels[r.cat] || r.cat;
      var isBlocked = r.cat === 'blocked';
      return {{
        text: r.paren ? r.n + '(' : r.n,
        displayText: r.n,
        render: function(el, self, data) {{
          el.style.opacity = isBlocked ? '0.5' : '1';
          el.innerHTML = '<span style="color:' + color + ';font-weight:600;font-size:10px;border:1px solid ' + color + ';border-radius:3px;padding:0 3px;margin-right:6px">' + label + '</span>' +
            '<strong>' + data.displayText + '</strong>' +
            '<span class="hint-sig">' + (r.d || '') + '</span>';
        }}
      }};
    }}),
    from: CodeMirror.Pos(cur.line, token.start),
    to: CodeMirror.Pos(cur.line, token.end)
  }};
}}

window.editor = CodeMirror.fromTextArea(document.getElementById('code-editor'), {{
  mode: 'python',
  lineNumbers: true,
  indentUnit: 4,
  tabSize: 4,
  indentWithTabs: false,
  extraKeys: {{
    "Tab": function(cm) {{ cm.replaceSelection("    ", "end"); }},
    "Ctrl-Space": "autocomplete"
  }},
  hintOptions: {{ hint: montyHint, completeSingle: false }},
  viewportMargin: Infinity
}});
editor.setSize(null, 400);
editor.on('inputRead', function(cm, change) {{
  if (change.text[0] && /[a-zA-Z_]/.test(change.text[0])) {{
    cm.showHint({{ hint: montyHint, completeSingle: false }});
  }}
}});
var tooltip = document.createElement('div');
tooltip.className = 'fn-tooltip';
tooltip.style.display = 'none';
document.body.appendChild(tooltip);

var allLookup = {{}};
allCompletions.forEach(function(c) {{ allLookup[c.n] = c; }});
hostFunctions.forEach(function(f) {{ allLookup[f.name] = {{n:f.name,d:f.description,cat:'host'}}; }});
fetch('/api/completions').then(function(r){{ return r.json(); }}).then(function(d){{
  d.forEach(function(f){{ allLookup[f.name] = {{n:f.name,d:f.description,cat:'host'}}; }});
}});

editor.getWrapperElement().addEventListener('mousemove', function(e) {{
  var pos = editor.coordsChar({{left: e.clientX, top: e.clientY}});
  var token = editor.getTokenAt(pos);
  var word = token.string;
  var info = allLookup[word];
  if (info) {{
    var color = catColors[info.cat] || 'var(--dim)';
    var label = catLabels[info.cat] || info.cat;
    var badge = '<span style="color:' + color + ';font-size:10px;border:1px solid ' + color + ';border-radius:3px;padding:0 4px;margin-left:6px">' + label + '</span>';
    tooltip.innerHTML = '<div class="fn-tip-name">' + info.n + badge + '</div><div class="fn-tip-desc">' + (info.d || '') + '</div>';
    tooltip.style.display = 'block';
    tooltip.style.left = (e.pageX + 12) + 'px';
    tooltip.style.top = (e.pageY + 16) + 'px';
  }} else {{
    tooltip.style.display = 'none';
  }}
}});
editor.getWrapperElement().addEventListener('mouseleave', function() {{
  tooltip.style.display = 'none';
}});

function escHtml(s) {{
  var d = document.createElement('div');
  d.textContent = typeof s === 'string' ? s : JSON.stringify(s, null, 2);
  return d.innerHTML;
}}

window.currentFile = '';

window.loadFile = function loadFile(name, content) {{
  currentFile = name;
  editor.setValue(content);
  document.getElementById('current-file-name').textContent = name;
  document.querySelectorAll('.file-list li').forEach(function(li) {{
    li.classList.toggle('active', li.textContent.trim() === name);
  }});
}}

window.createFile = function createFile() {{
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

window.saveFile = function saveFile() {{
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

var inputValues = {{}};

function detectInputs() {{
  var code = editor.getValue();
  var re = /inputs\\[["']([^"']+)["']\\]/g;
  var keys = [];
  var m;
  while ((m = re.exec(code)) !== null) {{
    if (keys.indexOf(m[1]) === -1) keys.push(m[1]);
  }}
  var bar = document.getElementById('inputs-bar');
  var chips = bar.querySelectorAll('.input-chip');
  chips.forEach(function(c) {{ c.remove(); }});
  if (keys.length === 0) {{
    bar.style.display = 'none';
    return;
  }}
  bar.style.display = 'flex';
  keys.forEach(function(key) {{
    var chip = document.createElement('span');
    chip.className = 'input-chip';
    chip.innerHTML = '<span class="chip-key">' + key + '</span><input type="text" placeholder="value" value="' + (inputValues[key] || '').replace(/"/g, '&quot;') + '">';
    chip.querySelector('input').addEventListener('input', function(e) {{
      inputValues[key] = e.target.value;
    }});
    bar.appendChild(chip);
  }});
}}

editor.on('change', function() {{
  clearTimeout(window._detectTimer);
  window._detectTimer = setTimeout(detectInputs, 400);
}});
detectInputs();

function showRunResult(d) {{
  var out = document.getElementById('output-area');
  var oldBar = document.querySelector('.suspend-bar');
  if (oldBar) oldBar.remove();
  if (d.suspended) {{
    out.textContent = 'Paused at ' + d.function_name + '(' + (d.args || []).join(', ') + ')';
    out.className = 'output-area';
    var bar = document.createElement('div');
    bar.className = 'suspend-bar';
    bar.innerHTML = '<span class="suspend-label">Suspended</span>' +
      '<span class="suspend-fn">' + d.function_name + '(' + (d.args || []).map(function(a){{ return JSON.stringify(a); }}).join(', ') + ')</span>' +
      '<input type="text" id="resume-value" placeholder="return value (JSON or string)">' +
      '<button class="btn btn-primary btn-sm" onclick="resumeSnapshot(' + d.snapshot_id + ')">Resume</button>' +
      '<button class="btn btn-ghost btn-sm" onclick="this.parentElement.remove()">Discard</button>';
    out.parentElement.appendChild(bar);
    document.getElementById('resume-value').focus();
  }} else if (d.success) {{
    out.textContent = JSON.stringify(d.value, null, 2);
    out.className = 'output-area ok';
  }} else {{
    out.textContent = d.error || 'Unknown error';
    out.className = 'output-area err';
  }}
  var oldLogs = document.getElementById('fn-logs-panel');
  if (oldLogs) oldLogs.remove();
  if (d.function_logs && d.function_logs.length) {{
    var panel = document.createElement('div');
    panel.id = 'fn-logs-panel';
    panel.className = 'panel';
    panel.style.marginTop = '1rem';
    var rows = d.function_logs.map(function(l) {{
      var logColors = {{'debug':'#9ca3af','info':'var(--dim)','warning':'#d97706','error':'var(--err)'}};
      var extra = l.logs && l.logs.length ? '<div style="font-size:.78rem;margin-top:2px">' + l.logs.map(function(m){{
        var lvl = (m && m.level) || 'info';
        var msg = (m && m.message) || (typeof m === 'string' ? m : JSON.stringify(m));
        var color = logColors[lvl] || 'var(--dim)';
        var ts = m && m.timestamp ? '<span style="color:#9ca3af;font-size:.7rem;margin-right:4px">' + m.timestamp.slice(11,23) + '</span>' : '';
        return ts + '<span style="color:' + color + ';font-weight:600;font-size:.7rem;text-transform:uppercase;margin-right:4px">' + lvl + '</span><span style="color:' + color + '">' + escHtml(msg) + '</span>';
      }}).join('<br>') + '</div>' : '';
      return '<div style="padding:.5rem .75rem;border-bottom:1px solid var(--border);font-size:.83rem">' +
        '<span style="color:var(--accent);font-weight:600;font-family:ui-monospace,monospace">' + escHtml(l.function) + '</span>' +
        '<span style="color:var(--dim)">(' + (l.args||[]).map(function(a){{ return escHtml(JSON.stringify(a)); }}).join(', ') + ')</span>' +
        ' <span style="color:var(--ok)">&rarr; ' + escHtml(JSON.stringify(l.result)) + '</span>' +
        (l.duration_ms != null ? ' <span style="color:var(--dim);font-size:.75rem">' + l.duration_ms + 'ms</span>' : '') +
        extra + '</div>';
    }}).join('');
    panel.innerHTML = '<div class="panel-header"><h3>Function Calls (' + d.function_logs.length + ')</h3></div>' + rows;
    out.parentElement.parentElement.appendChild(panel);
  }}
}}

window.runCode = function runCode() {{
  var inputs = {{}};
  document.querySelectorAll('.input-chip').forEach(function(chip) {{
    var key = chip.querySelector('.chip-key').textContent;
    var val = chip.querySelector('input').value;
    inputs[key] = val;
  }});
  var out = document.getElementById('output-area');
  out.textContent = 'Running...';
  out.className = 'output-area';
  var oldBar = document.querySelector('.suspend-bar');
  if (oldBar) oldBar.remove();
  fetch('/api/run', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{code: editor.getValue(), inputs: inputs, file_name: currentFile || null}})
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    showRunResult(d);
  }}).catch(function(e) {{
    out.textContent = 'Request failed: ' + e;
    out.className = 'output-area err';
  }});
}}

window.resumeSnapshot = function resumeSnapshot(snapshotId) {{
  var val = document.getElementById('resume-value').value;
  var out = document.getElementById('output-area');
  out.textContent = 'Resuming...';
  out.className = 'output-area';
  fetch('/api/resume', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{snapshot_id: snapshotId, value: val}})
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    showRunResult(d);
  }}).catch(function(e) {{
    out.textContent = 'Resume failed: ' + e;
    out.className = 'output-area err';
  }});
}}

window.refreshFileList = function refreshFileList() {{
  fetch('/api/files').then(function(r) {{ return r.json(); }}).then(function(files) {{
    var ul = document.querySelector('#file-list-area ul');
    ul.innerHTML = '';
    var testSet = {{}};
    files.forEach(function(f) {{ if (f.indexOf('test_') === 0) testSet[f] = true; }});
    var solutions = files.filter(function(f) {{ return f.indexOf('test_') !== 0; }});
    var orphans = files.filter(function(f) {{ return f.indexOf('test_') === 0 && solutions.indexOf(f.slice(5)) === -1; }});

    function makeLi(f, isChild) {{
      var li = document.createElement('li');
      if (isChild) {{
        li.style.paddingLeft = '2rem';
        li.style.fontSize = '.78rem';
        li.style.color = 'var(--dim)';
        li.innerHTML = '<span style="color:var(--accent2);margin-right:4px">&#9881;</span>' + f;
      }} else {{
        li.textContent = f;
      }}
      li.onclick = function() {{
        fetch('/api/file?name=' + encodeURIComponent(f))
          .then(function(r) {{ return r.json(); }})
          .then(function(d) {{ loadFile(f, d.content); }});
      }};
      if (f === currentFile) li.classList.add('active');
      return li;
    }}

    solutions.forEach(function(f) {{
      ul.appendChild(makeLi(f, false));
      var tf = 'test_' + f;
      if (testSet[tf]) ul.appendChild(makeLi(tf, true));
    }});
    orphans.forEach(function(f) {{ ul.appendChild(makeLi(f, false)); }});
  }});
}}

var _versionCache = [];
window.showVersions = function showVersions() {{
  if (!currentFile) return;
  fetch('/api/versions?name=' + encodeURIComponent(currentFile))
    .then(function(r) {{ return r.json(); }})
    .then(function(versions) {{
      _versionCache = versions;
      var overlay = document.createElement('div');
      overlay.className = 'modal-overlay';
      overlay.onclick = function(e) {{ if (e.target === overlay) overlay.remove(); }};
      var rows = '';
      if (!versions.length) {{
        rows = '<div class="empty">No previous versions.</div>';
      }} else {{
        versions.forEach(function(v) {{
          var ts = (v.created_at || '').slice(0, 19).replace('T', ' ');
          rows += '<div class="version-row" data-id="' + v.id + '">' +
            '<span class="meta">' + ts + '</span>' +
            '<button class="btn btn-ghost btn-sm" onclick="previewVersion(' + v.id + ')">Preview</button>' +
            '<button class="btn btn-primary btn-sm" onclick="restoreVersion(' + v.id + ')">Restore</button>' +
            '</div>';
        }});
      }}
      overlay.innerHTML = '<div class="modal">' +
        '<div class="modal-header"><h3>Versions: ' + currentFile + '</h3>' +
        '<button class="btn btn-ghost btn-sm" id="modal-close-btn">Close</button></div>' +
        '<div class="modal-body" id="version-list">' + rows + '</div></div>';
      document.body.appendChild(overlay);
      document.getElementById('modal-close-btn').onclick = function() {{ overlay.remove(); }};
    }});
}}

function previewVersion(id) {{
  var v = _versionCache.find(function(ver) {{ return ver.id === id; }});
  if (!v) return;
  var pre = document.querySelector('.modal .version-preview');
  if (!pre) {{
    pre = document.createElement('div');
    pre.className = 'version-preview';
    pre.style.cssText = 'padding:.75rem;border-top:1px solid var(--border)';
    document.querySelector('.modal-body').appendChild(pre);
  }}
  var d = document.createElement('div');
  d.textContent = v.content;
  pre.innerHTML = '<pre style="background:var(--code-bg);border:1px solid var(--border);border-radius:4px;padding:.75rem;font-size:.8rem;max-height:300px;overflow:auto;white-space:pre-wrap">' + d.innerHTML + '</pre>';
}}

function restoreVersion(id) {{
  fetch('/api/versions/restore', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{id: id}})
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (d.ok) {{
      editor.setValue(d.content);
      document.querySelector('.modal-overlay').remove();
      var out = document.getElementById('output-area');
      out.textContent = 'Restored ' + d.name + ' from version';
      out.className = 'output-area ok';
    }}
  }});
}}

function checkTestFile() {{
  if (!currentFile) {{ document.getElementById('btn-test').style.display = 'none'; return; }}
  var testName = currentFile.startsWith('test_') ? currentFile : 'test_' + currentFile;
  fetch('/api/files').then(function(r) {{ return r.json(); }}).then(function(files) {{
    var hasTest = files.indexOf(testName) !== -1 || currentFile.startsWith('test_');
    document.getElementById('btn-test').style.display = hasTest ? '' : 'none';
  }});
}}

window.runTests = function runTests() {{
  if (!currentFile) return;
  var inputs = {{}};
  document.querySelectorAll('.input-chip').forEach(function(chip) {{
    var key = chip.querySelector('.chip-key').textContent;
    var val = chip.querySelector('input').value;
    inputs[key] = val;
  }});
  var out = document.getElementById('output-area');
  out.textContent = 'Running tests...';
  out.className = 'output-area';
  fetch('/api/test', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{file_name: currentFile, inputs: inputs}})
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (d.error) {{
      out.textContent = d.error;
      out.className = 'output-area err';
      return;
    }}
    showTestResult(d);
  }}).catch(function(e) {{
    out.textContent = 'Test failed: ' + e;
    out.className = 'output-area err';
  }});
}}

function showTestResult(d) {{
  var out = document.getElementById('output-area');
  var passed = d.tests ? d.tests.filter(function(t) {{ return t.passed; }}).length : 0;
  var failed = d.total - passed;
  var summary = passed + '/' + d.total + ' passed';
  if (d.duration_ms) summary += ' (' + d.duration_ms + 'ms)';
  if (d.solution_file) summary += '  [' + d.solution_file + ' + ' + d.test_file + ']';
  out.textContent = summary;
  out.className = d.passed ? 'output-area ok' : 'output-area err';

  var oldTests = document.getElementById('test-results-panel');
  if (oldTests) oldTests.remove();
  var oldLogs = document.getElementById('fn-logs-panel');
  if (oldLogs) oldLogs.remove();

  if (d.tests && d.tests.length) {{
    var panel = document.createElement('div');
    panel.id = 'test-results-panel';
    panel.className = 'panel';
    panel.style.marginTop = '1rem';
    var rows = d.tests.map(function(t) {{
      var icon = t.passed ? '<span style="color:var(--ok)">&#10003;</span>' : '<span style="color:var(--err)">&#10007;</span>';
      var errHtml = t.error ? '<div style="color:var(--err);font-size:.78rem;margin-top:2px;font-family:ui-monospace,monospace">' + escHtml(t.error) + '</div>' : '';
      return '<div style="padding:.5rem .75rem;border-bottom:1px solid var(--border);font-size:.85rem">' +
        icon + ' <span style="font-family:ui-monospace,monospace;font-weight:600">' + escHtml(t.name) + '</span>' +
        errHtml + '</div>';
    }}).join('');
    panel.innerHTML = '<div class="panel-header"><h3>Tests (' + passed + '/' + d.total + ')</h3>' +
      '<span style="margin-left:auto;font-size:.75rem;color:var(--dim)">using sample data</span></div>' + rows;
    out.parentElement.parentElement.appendChild(panel);
  }}

  if (d.function_logs && d.function_logs.length) {{
    var logPanel = document.createElement('div');
    logPanel.id = 'fn-logs-panel';
    logPanel.className = 'panel';
    logPanel.style.marginTop = '1rem';
    var logColors = {{'debug':'#9ca3af','info':'var(--dim)','warning':'#d97706','error':'var(--err)'}};
    var logRows = d.function_logs.map(function(l) {{
      var extra = l.logs && l.logs.length ? '<div style="font-size:.78rem;margin-top:2px">' + l.logs.map(function(m){{
        var lvl = (m && m.level) || 'info';
        var msg = (m && m.message) || (typeof m === 'string' ? m : JSON.stringify(m));
        var color = logColors[lvl] || 'var(--dim)';
        var ts = m && m.timestamp ? '<span style="color:#9ca3af;font-size:.7rem;margin-right:4px">' + m.timestamp.slice(11,23) + '</span>' : '';
        return ts + '<span style="color:' + color + ';font-weight:600;font-size:.7rem;text-transform:uppercase;margin-right:4px">' + lvl + '</span><span style="color:' + color + '">' + escHtml(msg) + '</span>';
      }}).join('<br>') + '</div>' : '';
      return '<div style="padding:.5rem .75rem;border-bottom:1px solid var(--border);font-size:.83rem">' +
        '<span style="color:var(--accent);font-weight:600;font-family:ui-monospace,monospace">' + escHtml(l.function) + '</span>' +
        '<span style="color:var(--dim)">(' + (l.args||[]).map(function(a){{ return escHtml(JSON.stringify(a)); }}).join(', ') + ')</span>' +
        ' <span style="color:var(--ok)">&rarr; ' + escHtml(JSON.stringify(l.result)) + '</span>' +
        (l.duration_ms != null ? ' <span style="color:var(--dim);font-size:.75rem">' + l.duration_ms + 'ms</span>' : '') +
        extra + '</div>';
    }}).join('');
    logPanel.innerHTML = '<div class="panel-header"><h3>Function Calls (' + d.function_logs.length + ')</h3></div>' + logRows;
    out.parentElement.parentElement.appendChild(logPanel);
  }}
}}

var _origLoadFile = window.loadFile;
window.loadFile = function(name, content) {{
  _origLoadFile(name, content);
  checkTestFile();
  loadCodeFunctions(name);
}};
checkTestFile();

function loadCodeFunctions(name) {{
  var panel = document.getElementById('code-functions-panel');
  var body = document.getElementById('code-functions-body');
  var title = document.getElementById('code-functions-title');
  if (!name || name.startsWith('test_')) {{
    panel.style.display = 'none';
    return;
  }}
  fetch('/api/functions?file=' + encodeURIComponent(name))
    .then(function(r) {{ return r.json(); }})
    .then(function(fns) {{
      if (!fns || !fns.length) {{
        panel.style.display = 'none';
        return;
      }}
      title.textContent = 'Code Functions (' + fns.length + ')';
      body.innerHTML = fns.map(renderCodeFunction).join('');
      panel.style.display = '';
    }})
    .catch(function() {{ panel.style.display = 'none'; }});
}}

function renderCodeFunction(fn) {{
  var params = fn.parameters || {{}};
  var paramKeys = Object.keys(params);
  var ret = fn.returns || {{}};

  var sig = '<span class="cfn-sig">' + escHtml(fn.name) + '(';
  sig += paramKeys.map(function(k) {{
    var p = params[k];
    var s = k;
    if (p.type) s += '<span class="cfn-type">: ' + escHtml(p.type) + '</span>';
    if (p.default !== undefined && p.default !== null) s += ' = ' + escHtml(String(p.default));
    return s;
  }}).join(', ');
  sig += ')';
  if (ret.type && ret.type !== 'Any') sig += ' <span class="cfn-ret">&rarr; ' + escHtml(ret.type) + '</span>';
  sig += '</span>';

  var desc = fn.description ? '<div class="cfn-desc">' + escHtml(fn.description) + '</div>' : '';

  var paramHtml = '';
  if (paramKeys.length) {{
    paramHtml = '<div class="cfn-section">Parameters</div><table class="cfn-table"><tr><th>Name</th><th>Type</th><th>Description</th></tr>';
    paramKeys.forEach(function(k) {{
      var p = params[k];
      var typeStr = p.type || '';
      if (!p.required && p.default !== undefined) typeStr += ' <span class="cfn-default">= ' + escHtml(String(p.default)) + '</span>';
      paramHtml += '<tr><td>' + escHtml(k) + (p.required ? ' <span style="color:var(--err)">*</span>' : '') + '</td>';
      paramHtml += '<td class="cfn-type">' + typeStr + '</td>';
      paramHtml += '<td>' + escHtml(p.description || '') + '</td></tr>';
    }});
    paramHtml += '</table>';
  }}

  var retHtml = '';
  if (ret.fields) {{
    var retKeys = Object.keys(ret.fields);
    if (retKeys.length) {{
      retHtml = '<div class="cfn-section">Returns</div><table class="cfn-table"><tr><th>Field</th><th colspan="2">Description</th></tr>';
      retKeys.forEach(function(k) {{
        retHtml += '<tr><td>' + escHtml(k) + '</td><td colspan="2">' + escHtml(ret.fields[k]) + '</td></tr>';
      }});
      retHtml += '</table>';
    }}
  }}

  return '<div class="cfn-card">' + sig + desc + paramHtml + retHtml + '</div>';
}}
</script>"""


def _functions_html() -> str:
    assert _monty is not None
    import json as json_mod
    descs = _monty.registry.descriptions
    human_fns = _monty.registry.human_input_functions
    samples = _monty.registry.samples
    if not descs:
        return '<div class="empty">No host functions registered.</div>'
    cards = ""
    for name, desc in sorted(descs.items()):
        tag = ' <span class="tag">human input</span>' if name in human_fns else ""
        sample_html = ""
        if name in samples:
            sample_json = _e(json_mod.dumps(samples[name], indent=2, default=str))
            sample_html = (
                f'<details style="margin-top:.5rem">'
                f'<summary style="font-size:.75rem;color:var(--accent);cursor:pointer;font-weight:600">Sample Data</summary>'
                f'<pre style="background:var(--code-bg);border:1px solid var(--border);border-radius:4px;'
                f'padding:.5rem;font-size:.78rem;margin-top:.25rem;max-height:200px;overflow:auto;'
                f'white-space:pre-wrap">{sample_json}</pre></details>'
            )
        cards += f'<div class="fn-card"><h4>{_e(name)}{tag}</h4><p>{_e(desc)}</p>{sample_html}</div>\n'
    return f"""<div class="panel">
<div class="panel-header"><h3>Host Functions ({len(descs)})</h3></div>
{cards}
</div>"""


def _history_html() -> str:
    assert _monty is not None
    runs = _monty.storage.list_runs(limit=50)
    if not runs:
        return '<div class="empty">No runs yet. Execute some code first.</div>'
    rows = ""
    for r in runs:
        status = "ok" if r["success"] else "err"
        fname = _e(r["file_name"] or "untitled")
        ts = r["created_at"][:19].replace("T", " ")
        dur = f'{r["duration_ms"]}ms' if r["duration_ms"] else ""
        err_preview = ""
        if r["error"]:
            err_preview = f' <span style="color:var(--err)">{_e(r["error"][:60])}</span>'
        rows += (
            f'<div class="run-row" onclick="showRun({r["id"]})">'
            f'<span class="status {status}"></span>'
            f'<span style="font-family:ui-monospace,monospace">{fname}</span>'
            f'{err_preview}'
            f'<span class="meta">{dur} &middot; {ts}</span>'
            f'</div>\n'
        )
    return f"""<div class="panel">
<div class="panel-header"><h3>Run History</h3></div>
{rows}
</div>
<div id="run-detail-area"></div>
<script>
function showRun(id) {{
  fetch('/api/run-detail?id=' + id)
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{
      var area = document.getElementById('run-detail-area');
      var status = d.success ? 'ok' : 'err';
      var inputs = d.inputs || '{{}}';
      var output = d.success ? (d.output || 'null') : (d.error || 'Unknown error');
      var fnLogsHtml = '';
      if (d.function_logs && d.function_logs.length) {{
        fnLogsHtml = '<h4 style="margin-top:.75rem">Function Calls (' + d.function_logs.length + ')</h4>';
        d.function_logs.forEach(function(l) {{
          var extra = l.logs ? JSON.parse(l.logs) : [];
          var args = l.args ? JSON.parse(l.args) : [];
          var logColors = {{'debug':'#9ca3af','info':'var(--dim)','warning':'#d97706','error':'var(--err)'}};
          var extraHtml = extra.length ? '<div style="font-size:.78rem;margin-top:2px">' + extra.map(function(m){{
            var lvl = (m && m.level) || 'info';
            var msg = (m && m.message) || (typeof m === 'string' ? m : JSON.stringify(m));
            var color = logColors[lvl] || 'var(--dim)';
            var ts = m && m.timestamp ? '<span style="color:#9ca3af;font-size:.7rem;margin-right:4px">' + m.timestamp.slice(11,23) + '</span>' : '';
            return ts + '<span style="color:' + color + ';font-weight:600;font-size:.7rem;text-transform:uppercase;margin-right:4px">' + lvl + '</span><span style="color:' + color + '">' + escHtml(msg) + '</span>';
          }}).join('<br>') + '</div>' : '';
          fnLogsHtml += '<div style="padding:.4rem 0;font-size:.83rem">' +
            '<span style="color:var(--accent);font-weight:600;font-family:ui-monospace,monospace">' + escHtml(l.function_name) + '</span>' +
            '<span style="color:var(--dim)">(' + args.map(function(a){{ return escHtml(JSON.stringify(a)); }}).join(', ') + ')</span>' +
            ' <span style="color:var(--ok)">&rarr; ' + escHtml(l.result) + '</span>' +
            (l.duration_ms != null ? ' <span style="color:var(--dim);font-size:.75rem">' + l.duration_ms + 'ms</span>' : '') +
            extraHtml + '</div>';
        }});
      }}
      area.innerHTML = '<div class="panel" style="margin-top:1rem">' +
        '<div class="panel-header"><h3>Run #' + d.id + '</h3>' +
        '<span class="meta">' + (d.duration_ms || '') + 'ms &middot; ' + (d.created_at || '').slice(0,19).replace('T',' ') + '</span></div>' +
        '<div class="run-detail">' +
        '<h4>Code</h4><pre>' + escHtml(d.code) + '</pre>' +
        '<h4 style="margin-top:.75rem">Inputs</h4><pre>' + escHtml(inputs) + '</pre>' +
        '<h4 style="margin-top:.75rem">Output <span class="status ' + status + '" style="display:inline-block"></span></h4>' +
        '<pre class="' + status + '">' + escHtml(output) + '</pre>' +
        fnLogsHtml +
        '</div></div>';
    }});
}}
function escHtml(s) {{
  var d = document.createElement('div');
  d.textContent = typeof s === 'string' ? s : JSON.stringify(s, null, 2);
  return d.innerHTML;
}}
</script>"""


def _list_workspace_files() -> list[str]:
    assert _monty is not None
    return _monty.storage.list_files()


async def index(request: Request):
    return HTMLResponse(_page_html(_editor_html()))


async def editor_partial(request: Request):
    return HTMLResponse(_editor_html())


async def functions_partial(request: Request):
    return HTMLResponse(_functions_html())


async def history_partial(request: Request):
    return HTMLResponse(_history_html())


async def api_files(request: Request):
    return JSONResponse(_list_workspace_files())


async def api_file_get(request: Request):
    assert _monty is not None
    name = request.query_params.get("name", "")
    f = _monty.storage.get_file(name)
    if not f:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse({"name": f["name"], "content": f["content"]})


async def api_file_save(request: Request):
    assert _monty is not None
    body = await request.json()
    name = body.get("name", "").strip()
    content = body.get("content", "")
    if not name or ".." in name or "/" in name:
        return JSONResponse({"error": "invalid filename"}, status_code=400)
    syntax_error = SandboxRunner._compile_check(content, name) if name.endswith(".py") else None
    result = _monty.storage.save_file(name, content)
    return JSONResponse({"ok": True, "syntax_error": syntax_error, **result})


async def api_run(request: Request):
    assert _monty is not None
    import time
    body = await request.json()
    code = body.get("code", "")
    inputs = body.get("inputs", {})
    file_name = body.get("file_name")
    t0 = time.monotonic()
    result = _monty.run(code, inputs, file_name=file_name, interactive=False)
    duration_ms = int((time.monotonic() - t0) * 1000)
    if result.suspended:
        return JSONResponse({
            "suspended": True,
            "snapshot_id": result.snapshot_id,
            "function_name": result.snapshot_function,
            "args": result.snapshot_args,
            "function_logs": result.function_logs,
        })
    run_id = _monty.storage.log_run(
        file_name=file_name, code=code, inputs=inputs,
        output=result.value if result.success else None,
        success=result.success, error=result.error, duration_ms=duration_ms,
    )
    if result.function_logs:
        _monty.storage.save_function_logs(run_id, result.function_logs)
    return JSONResponse({
        "success": result.success,
        "value": result.value if result.success else None,
        "error": result.error,
        "duration_ms": duration_ms,
        "function_logs": result.function_logs,
    })


async def api_resume(request: Request):
    assert _monty is not None
    import json as json_mod
    import time
    body = await request.json()
    snapshot_id = body.get("snapshot_id")
    value_raw = body.get("value", "")
    if not snapshot_id:
        return JSONResponse({"error": "snapshot_id required"}, status_code=400)
    try:
        value = json_mod.loads(value_raw)
    except (json_mod.JSONDecodeError, TypeError):
        value = value_raw
    t0 = time.monotonic()
    result = _monty.resume_snapshot(int(snapshot_id), value)
    duration_ms = int((time.monotonic() - t0) * 1000)
    if result.suspended:
        return JSONResponse({
            "suspended": True,
            "snapshot_id": result.snapshot_id,
            "function_name": result.snapshot_function,
            "args": result.snapshot_args,
            "function_logs": result.function_logs,
        })
    snap = _monty.storage.get_snapshot(int(snapshot_id))
    run_id = _monty.storage.log_run(
        file_name=snap["file_name"] if snap else None,
        code=f"[resumed snapshot #{snapshot_id}]",
        inputs={"resume_value": value_raw},
        output=result.value if result.success else None,
        success=result.success, error=result.error, duration_ms=duration_ms,
    )
    if result.function_logs:
        _monty.storage.save_function_logs(run_id, result.function_logs)
    return JSONResponse({
        "success": result.success,
        "value": result.value if result.success else None,
        "error": result.error,
        "duration_ms": duration_ms,
        "function_logs": result.function_logs,
    })


async def api_snapshots(request: Request):
    assert _monty is not None
    status = request.query_params.get("status", "pending")
    return JSONResponse(_monty.storage.list_snapshots(status=status or None))


async def api_test(request: Request):
    assert _monty is not None
    import re as _re
    import time
    body = await request.json()
    file_name = body.get("file_name", "")
    inputs = body.get("inputs", {})

    if file_name.startswith("test_"):
        test_name = file_name
        sol_name = _monty.get_solution_file(test_name)
    else:
        sol_name = file_name
        test_name = _monty.get_test_file(file_name)

    if not test_name:
        return JSONResponse({"error": f"No test file found for {file_name}"}, status_code=404)

    test_file = _monty.storage.get_file(test_name)
    if not test_file:
        return JSONResponse({"error": f"Test file {test_name} not found"}, status_code=404)

    sol_code = ""
    if sol_name:
        sol_file = _monty.storage.get_file(sol_name)
        if sol_file:
            sol_code = sol_file["content"]

    for key in _re.findall(r'inputs\[["\']([^"\']+)["\']\]', sol_code):
        if key not in inputs:
            inputs[key] = "test"

    t0 = time.monotonic()
    result = _monty.run_tests(sol_code, test_file["content"], inputs=inputs, use_samples=True)
    duration_ms = int((time.monotonic() - t0) * 1000)

    return JSONResponse({
        "passed": result.passed,
        "total": result.total,
        "failures": result.failures,
        "tests": result.tests,
        "duration_ms": duration_ms,
        "function_logs": result.function_logs,
        "solution_file": sol_name,
        "test_file": test_name,
    })


async def api_samples(request: Request):
    assert _monty is not None
    samples = _monty.registry.samples
    return JSONResponse({
        name: sample for name, sample in sorted(samples.items())
    })


async def api_completions(request: Request):
    assert _monty is not None
    descs = _monty.registry.descriptions
    samples = _monty.registry.samples
    return JSONResponse([
        {"name": name, "description": desc, "sample": samples.get(name)}
        for name, desc in sorted(descs.items())
    ])


async def api_runs(request: Request):
    assert _monty is not None
    file_name = request.query_params.get("file")
    limit = int(request.query_params.get("limit", "50"))
    return JSONResponse(_monty.storage.list_runs(limit=limit, file_name=file_name or None))


async def api_run_detail(request: Request):
    assert _monty is not None
    run_id = int(request.query_params.get("id", "0"))
    run = _monty.storage.get_run(run_id)
    if not run:
        return JSONResponse({"error": "not found"}, status_code=404)
    run["function_logs"] = _monty.storage.list_function_logs(run_id)
    return JSONResponse(run)


async def api_functions(request: Request):
    assert _monty is not None
    from ..sandbox.inspector import inspect_functions
    name = request.query_params.get("file", "")
    if not name:
        return JSONResponse({"error": "file parameter required"}, status_code=400)
    f = _monty.storage.get_file(name)
    if not f:
        return JSONResponse({"error": "not found"}, status_code=404)
    functions = inspect_functions(f["content"], file_name=name)
    return JSONResponse(functions)


async def api_versions(request: Request):
    assert _monty is not None
    name = request.query_params.get("name", "")
    if not name:
        return JSONResponse({"error": "name required"}, status_code=400)
    return JSONResponse(_monty.storage.file_versions(name))


async def api_version_restore(request: Request):
    assert _monty is not None
    body = await request.json()
    version_id = body.get("id")
    if not version_id:
        return JSONResponse({"error": "version id required"}, status_code=400)
    version = _monty.storage.get_version(int(version_id))
    if not version:
        return JSONResponse({"error": "version not found"}, status_code=404)
    _monty.storage.save_file(version["file_name"], version["content"])
    return JSONResponse({"ok": True, "name": version["file_name"], "content": version["content"]})


def create_app(monty: Monty) -> Starlette:
    global _monty
    _monty = monty
    return Starlette(routes=[
        Route("/", index),
        Route("/editor", editor_partial),
        Route("/functions", functions_partial),
        Route("/history", history_partial),
        Route("/api/files", api_files),
        Route("/api/file", api_file_get),
        Route("/api/file", api_file_save, methods=["POST"]),
        Route("/api/run", api_run, methods=["POST"]),
        Route("/api/resume", api_resume, methods=["POST"]),
        Route("/api/test", api_test, methods=["POST"]),
        Route("/api/snapshots", api_snapshots),
        Route("/api/samples", api_samples),
        Route("/api/completions", api_completions),
        Route("/api/runs", api_runs),
        Route("/api/run-detail", api_run_detail),
        Route("/api/functions", api_functions),
        Route("/api/versions", api_versions),
        Route("/api/versions/restore", api_version_restore, methods=["POST"]),
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
