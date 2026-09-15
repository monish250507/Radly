import ast
import os
import re
from typing import Any

from .logger import paperblast_logger as logger


class PythonCodeVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, code_lines: list[str]):
        self.file_path = file_path
        self.code_lines = code_lines
        self.symbols = []
        self.current_class = None
        self.current_function = None

    def _add_symbol(self, symbol: str, sym_type: str, node: ast.AST, value: str = None):
        line = getattr(node, 'lineno', 1)
        col = getattr(node, 'col_offset', 0)
        
        # safely slice source text
        source_text = ""
        end_line = getattr(node, 'end_lineno', line)
        if 1 <= line <= len(self.code_lines):
            if line == end_line:
                source_text = self.code_lines[line - 1].strip()
            else:
                source_text = "\n".join(self.code_lines[line - 1 : min(end_line, len(self.code_lines))])

        if value is None:
            value = source_text[:100] + ('...' if len(source_text) > 100 else '')

        self.symbols.append({
            'symbol': symbol,
            'type': sym_type,
            'value': value,
            'file': self.file_path,
            'line': line,
            'col_offset': col,
            'source_text': source_text,
            'parent_context': self.current_function or self.current_class
        })

    def visit_Import(self, node):
        for alias in node.names:
            self._add_symbol(alias.name, 'Import', node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ''
        for alias in node.names:
            self._add_symbol(f"{module}.{alias.name}", 'ImportFrom', node)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        prev = self.current_class
        self.current_class = node.name
        self._add_symbol(node.name, 'Class', node, value=f"class {node.name}")
        self.generic_visit(node)
        self.current_class = prev

    def visit_FunctionDef(self, node):
        prev = self.current_function
        self.current_function = node.name
        
        args = [arg.arg for arg in node.args.args]
        val_str = f"def {node.name}({', '.join(args)})"
        
        type_str = f"Method ({self.current_class})" if self.current_class else 'Function'
        self._add_symbol(node.name, type_str, node, value=val_str)
        
        # record arguments as Variable
        for arg in args:
            if arg not in ('self', 'cls'):
                self._add_symbol(arg, 'Argument', node.args)
                
        self.generic_visit(node)
        self.current_function = prev

    def visit_Assign(self, node):
        try:
            val_str = ast.unparse(node.value) if hasattr(ast, 'unparse') else "..."
        except Exception:
            val_str = "..."

        for target in node.targets:
            if isinstance(target, ast.Name):
                self._add_symbol(target.id, 'Assignment', node, value=val_str)
            elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                self._add_symbol(f"{target.value.id}.{target.attr}", 'Assignment', node, value=val_str)
        
        self.generic_visit(node)

    def visit_Call(self, node):
        try:
            func_name = ast.unparse(node.func) if hasattr(ast, 'unparse') else "..."
        except Exception:
            func_name = "..."
        
        if func_name != "...":
            self._add_symbol(func_name, 'Call', node, value=func_name)
            
        self.generic_visit(node)


def extract_code_symbols(files: list[dict[str, str]]) -> list[dict[str, Any]]:
    """
    Extract AST symbols from all provided files. Files that fail to parse
    produce an EXTRACTION_FAILED sentinel logged as a warning. Sentinels are
    EXCLUDED from the returned symbol list — callers receive only real symbols
    from successfully parsed files.
    """
    symbols = []
    failed_files = []

    for f in files:
        if not f or not f.get('content'):
            continue

        file_path = f.get('path') or f.get('name') or ''
        ext = os.path.splitext(file_path)[1].lower()

        # Enforce size limits per file (5MB limit)
        if len(f['content']) > 5 * 1024 * 1024:
            continue

        if ext == '.py':
            py_symbols = parse_python_ast(f['content'], file_path)
            # P0 FIX: Check for EXTRACTION_FAILED sentinels — do not mix into results
            if py_symbols and is_extraction_failed(py_symbols[0]):
                failed_files.append({
                    'file': file_path,
                    'error': py_symbols[0].get('value', 'unknown'),
                    'extraction_status': 'FAILED'
                })
                logger.warn(
                    f"Skipping failed parse for {file_path} — no symbols emitted",
                    {'extraction_status': 'FAILED'}
                )
            else:
                symbols.extend(py_symbols)
        elif ext in ['.js', '.ts', '.jsx', '.tsx', '.json', '.yaml', '.yml']:
            js_symbols = parse_js_or_config(f['content'], file_path)
            symbols.extend(js_symbols)

    if failed_files:
        logger.warn(
            f"{len(failed_files)} file(s) failed AST parse and were excluded from analysis",
            {'failed_files': [f['file'] for f in failed_files]}
        )

    return symbols

def parse_python_ast(code: str, file_path: str) -> list[dict[str, Any]]:
    """
    Parse Python source via AST. On SyntaxError returns a single EXTRACTION_FAILED
    sentinel record — callers MUST check is_extraction_failed() and must NOT treat
    degraded output as a verified parse. No regex fallback is applied.
    """
    lines = code.split('\n')
    try:
        tree = ast.parse(code, filename=file_path)
        visitor = PythonCodeVisitor(file_path, lines)
        visitor.visit(tree)
        return visitor.symbols
    except SyntaxError as e:
        logger.warn(
            f"SyntaxError parsing Python file {file_path} — returning EXTRACTION_FAILED sentinel; "
            f"downstream findings from this file are BLOCKED",
            {"error": str(e)}
        )
        # P0 FIX: Do NOT fall back to regex. An invalid parse must not produce
        # plausible-looking symbols. Return an explicit failure sentinel only.
        return [{
            'symbol': '__EXTRACTION_FAILED__',
            'type': 'EXTRACTION_FAILED',
            'value': f"SyntaxError: {e}",
            'file': file_path,
            'line': getattr(e, 'lineno', 0),
            'col_offset': getattr(e, 'offset', 0),
            'source_text': '',
            'parent_context': None,
            'extraction_status': 'FAILED',
        }]
    except Exception as e:
        logger.error(f"Unexpected AST error on {file_path}", {"error": str(e)})
        return [{
            'symbol': '__EXTRACTION_FAILED__',
            'type': 'EXTRACTION_FAILED',
            'value': f"UnexpectedError: {e}",
            'file': file_path,
            'line': 0,
            'col_offset': 0,
            'source_text': '',
            'parent_context': None,
            'extraction_status': 'FAILED',
        }]


def is_extraction_failed(symbol: dict[str, Any]) -> bool:
    """Returns True if the symbol is an EXTRACTION_FAILED sentinel.
    Callers must filter these out before building evidence or findings."""
    return symbol.get('type') == 'EXTRACTION_FAILED'


def parse_js_or_config(code: str, file_path: str) -> list[dict[str, Any]]:
    symbols = []
    lines = code.split('\n')

    var_re = re.compile(r'(?:const|let|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*([^;]+)')
    kv_re = re.compile(r'^"?([a-zA-Z_][a-zA-Z0-9_-]*)"?\s*:\s*(.+)$')

    for idx, line_text in enumerate(lines):
        line_num = idx + 1
        trimmed = line_text.strip()

        if not trimmed or trimmed.startswith('//') or trimmed.startswith('#'):
            continue

        var_match = var_re.search(trimmed)
        if var_match:
            symbols.append({
                'symbol': var_match.group(1),
                'type': 'Variable',
                'value': var_match.group(2).strip(),
                'line': line_num,
                'file': file_path
            })

        kv_match = kv_re.match(trimmed)
        if kv_match:
            val = kv_match.group(2).replace(',', '').replace('"', '').strip()
            symbols.append({
                'symbol': kv_match.group(1),
                'type': 'ConfigKey',
                'value': val,
                'line': line_num,
                'file': file_path
            })

    return symbols
