from __future__ import annotations

import ast
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "myApp"
URLS_FILE = APP_DIR / "urls.py"
OUTPUT_FILE = ROOT / "docs" / "FUNCTIONS_AND_ACE.md"


@dataclass
class PyFunction:
    file: str
    line: int
    name: str
    signature: str
    kind: str
    class_name: str | None = None


@dataclass
class JsFunction:
    file: str
    line: int
    name: str
    signature: str
    kind: str


def _iter_python_files(base: Path) -> Iterable[Path]:
    for path in sorted(base.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def _iter_template_files(base: Path) -> Iterable[Path]:
    templates_dir = base / "templates"
    if not templates_dir.exists():
        return []
    return sorted(templates_dir.rglob("*.html"))


def _fmt_args(args: ast.arguments) -> str:
    out: list[str] = []
    positional = list(args.posonlyargs) + list(args.args)
    positional_defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)

    if args.posonlyargs:
        for arg, default in zip(positional[: len(args.posonlyargs)], positional_defaults[: len(args.posonlyargs)]):
            out.append(f"{arg.arg}={_safe_unparse(default)}" if default is not None else arg.arg)
        out.append("/")

    start = len(args.posonlyargs)
    for arg, default in zip(positional[start:], positional_defaults[start:]):
        out.append(f"{arg.arg}={_safe_unparse(default)}" if default is not None else arg.arg)

    if args.vararg:
        out.append(f"*{args.vararg.arg}")
    elif args.kwonlyargs:
        out.append("*")

    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        out.append(f"{arg.arg}={_safe_unparse(default)}" if default is not None else arg.arg)

    if args.kwarg:
        out.append(f"**{args.kwarg.arg}")

    return ", ".join(out)


def _safe_unparse(node: ast.AST | None) -> str:
    if node is None:
        return "None"
    try:
        return ast.unparse(node)
    except Exception:
        return "..."


def collect_python_functions(base: Path) -> list[PyFunction]:
    collected: list[PyFunction] = []
    for py_file in _iter_python_files(base):
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        rel = py_file.relative_to(ROOT).as_posix()

        class StackVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.class_stack: list[str] = []

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                self.class_stack.append(node.name)
                self.generic_visit(node)
                self.class_stack.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                sig = _fmt_args(node.args)
                class_name = self.class_stack[-1] if self.class_stack else None
                kind = "method" if class_name else "function"
                collected.append(
                    PyFunction(
                        file=rel,
                        line=node.lineno,
                        name=node.name,
                        signature=f"{node.name}({sig})",
                        kind=kind,
                        class_name=class_name,
                    )
                )
                self.generic_visit(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                sig = _fmt_args(node.args)
                class_name = self.class_stack[-1] if self.class_stack else None
                kind = "method" if class_name else "function"
                collected.append(
                    PyFunction(
                        file=rel,
                        line=node.lineno,
                        name=node.name,
                        signature=f"async {node.name}({sig})",
                        kind=kind,
                        class_name=class_name,
                    )
                )
                self.generic_visit(node)

        StackVisitor().visit(tree)
    return sorted(collected, key=lambda x: (x.file, x.line, x.name))


RE_JS_DECL = re.compile(
    r"^\s*(async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)",
    re.MULTILINE,
)
RE_JS_ARROW = re.compile(
    r"^\s*(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>",
    re.MULTILINE,
)


def collect_js_functions(base: Path) -> list[JsFunction]:
    collected: list[JsFunction] = []
    for html_file in _iter_template_files(base):
        text = html_file.read_text(encoding="utf-8")
        rel = html_file.relative_to(ROOT).as_posix()

        for match in RE_JS_DECL.finditer(text):
            async_kw, name, args = match.groups()
            line = text.count("\n", 0, match.start()) + 1
            prefix = "async " if async_kw else ""
            collected.append(
                JsFunction(
                    file=rel,
                    line=line,
                    name=name,
                    signature=f"{prefix}{name}({args.strip()})",
                    kind="function",
                )
            )

        for match in RE_JS_ARROW.finditer(text):
            name, args = match.groups()
            line = text.count("\n", 0, match.start()) + 1
            collected.append(
                JsFunction(
                    file=rel,
                    line=line,
                    name=name,
                    signature=f"{name}({args.strip()})",
                    kind="arrow-function",
                )
            )

    return sorted(collected, key=lambda x: (x.file, x.line, x.name))


def collect_url_endpoints(urls_file: Path) -> list[tuple[str, str]]:
    if not urls_file.exists():
        return []
    text = urls_file.read_text(encoding="utf-8")
    rx = re.compile(r'path\("([^"]+)",\s*views\.([A-Za-z_][A-Za-z0-9_]*)')
    return sorted(rx.findall(text))


def _ace_summary(endpoints: list[tuple[str, str]]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for route, view in endpoints:
        if route.startswith("api/auth/"):
            groups["Authentication"].append(route)
        elif route.startswith("api/admin/"):
            groups["Admin APIs"].append(route)
        elif route.startswith("api/chat/"):
            groups["Chat APIs"].append(route)
        elif route.startswith("api/"):
            groups["Core APIs"].append(route)
        elif route.startswith("admin-dashboard"):
            groups["Admin UI Routes"].append(route)
        else:
            groups["Web UI Routes"].append(route)

    for key in list(groups.keys()):
        groups[key] = sorted(groups[key])
    return dict(sorted(groups.items(), key=lambda x: x[0]))


def build_markdown(py_items: list[PyFunction], js_items: list[JsFunction], endpoints: list[tuple[str, str]]) -> str:
    lines: list[str] = []
    lines.append("# Functions & ACE Documentation")
    lines.append("")
    lines.append("Auto-generated inventory of current backend and frontend functions.")
    lines.append("")
    lines.append("## Snapshot")
    lines.append("")
    lines.append(f"- Python functions/methods: **{len(py_items)}**")
    lines.append(f"- Template JavaScript functions: **{len(js_items)}**")
    lines.append(f"- URL endpoints mapped in `myApp/urls.py`: **{len(endpoints)}**")
    lines.append("")
    lines.append("## ACE (Architecture, Capabilities, Entry Points)")
    lines.append("")
    lines.append("- **Architecture:** Django monolith (`myProject`) with server-rendered templates and JSON API endpoints in `myApp/views.py`.")
    lines.append("- **Capabilities:** auth, onboarding, profile management, agent management, prompts, chat sessions/messages, events, industries, tools, banners, admin ops analytics, impersonation.")
    lines.append("- **Entry points:** UI routes and API routes declared in `myApp/urls.py`; frontend behavior implemented in template JavaScript.")
    lines.append("")

    lines.append("### Endpoint Groups")
    lines.append("")
    grouped = _ace_summary(endpoints)
    for section, routes in grouped.items():
        lines.append(f"#### {section} ({len(routes)})")
        for route in routes:
            lines.append(f"- `{route}`")
        lines.append("")

    lines.append("## Python Function Inventory")
    lines.append("")
    by_file: dict[str, list[PyFunction]] = defaultdict(list)
    for item in py_items:
        by_file[item.file].append(item)
    for file_path in sorted(by_file):
        items = by_file[file_path]
        lines.append(f"### `{file_path}` ({len(items)})")
        for fn in items:
            if fn.class_name:
                lines.append(f"- `{fn.signature}` - {fn.kind} on `{fn.class_name}`")
            else:
                lines.append(f"- `{fn.signature}` - {fn.kind}")
        lines.append("")

    lines.append("## Frontend Template JS Function Inventory")
    lines.append("")
    js_by_file: dict[str, list[JsFunction]] = defaultdict(list)
    for item in js_items:
        js_by_file[item.file].append(item)
    for file_path in sorted(js_by_file):
        items = js_by_file[file_path]
        lines.append(f"### `{file_path}` ({len(items)})")
        for fn in items:
            lines.append(f"- `{fn.signature}` - {fn.kind}")
        lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append("- This file is generated; re-run `python scripts/generate_function_docs.py` after function changes.")
    lines.append("- Inventory includes top-level and nested Python functions, class methods, and template JS declarations.")
    return "\n".join(lines) + "\n"


def main() -> None:
    py_items = collect_python_functions(APP_DIR)
    js_items = collect_js_functions(APP_DIR)
    endpoints = collect_url_endpoints(URLS_FILE)
    markdown = build_markdown(py_items, js_items, endpoints)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(markdown, encoding="utf-8")
    print(f"Wrote: {OUTPUT_FILE}")
    print(f"Python entries: {len(py_items)}")
    print(f"JS entries: {len(js_items)}")
    print(f"Endpoints: {len(endpoints)}")


if __name__ == "__main__":
    main()
