#!/usr/bin/env python3
"""
Django Project Deep Analyzer
=============================
Varredura REAL e completa do projeto Django — views, models, urls, templates,
forms, admin, signals, middleware, settings, estáticos, testes, segurança,
eficiência, complexidade, dependências e muito mais.

Uso:
    python analyze_django_project.py /caminho/do/projeto
    python analyze_django_project.py /caminho/do/projeto -o relatorio.md
    python analyze_django_project.py /caminho/do/projeto --deep          # análise extra-lenta e detalhada
    python analyze_django_project.py /caminho/do/projeto --json          # também gera .json com dados brutos
"""

import ast
import hashlib
import importlib.util
import os
import re
import subprocess
import sys
import textwrap
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from django_ratelimit import decorators

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

import argparse
import json

# ────────────────────────────────────────────────────────────────
# CONSTANTES
# ────────────────────────────────────────────────────────────────

# Adicione esta linha após os imports (perto da linha 45)
_THIS_SCRIPT = Path(__file__).resolve()

IGNORE_DIRS = {
    "migrations", "__pycache__", ".git", "venv", "env", ".venv",
    "node_modules", "staticfiles", ".tox", ".mypy_cache", ".pytest_cache",
    "htmlcov", ".coverage", "dist", "build", "*.egg-info",
}

DJANGO_HTTP_DECORATORS = {
    "login_required", "permission_required", "staff_member_required",
}

DJANGO_CLASS_DECORATORS = {
    "method_decorator", "login_required", "permission_required",
}


# ────────────────────────────────────────────────────────────────
# UTILITÁRIOS
# ────────────────────────────────────────────────────────────────

def find_project_root(path: Path) -> Path:
    """Detecta a raiz do projeto Django (onde manage.py está)."""
    for p in [path] + list(path.parents):
        if (p / "manage.py").exists():
            return p.resolve()
    return path.resolve()


def is_ignored(part: str) -> bool:
    return part in IGNORE_DIRS or part.startswith(".")


def collect_python_files(root: Path) -> list[Path]:
    files = []
    for f in root.rglob("*.py"):
        if f.resolve() == _THIS_SCRIPT:  # ← ADICIONE ESTA LINHA
            continue                      # ← ADICIONE ESTA LINHA
        if not any(is_ignored(p) for p in f.parts):
            files.append(f)
    return sorted(files)


def collect_template_files(root: Path) -> list[Path]:
    return sorted(
        f for f in root.rglob("*.html")
        if not any(is_ignored(p) for p in f.parts)
    )


def collect_static_files(root: Path) -> list[Path]:
    exts = {".css", ".js", ".scss", ".less", ".sass", ".ts", ".jsx", ".tsx"}
    return sorted(
        f for f in root.rglob("*")
        if f.suffix in exts and not any(is_ignored(p) for p in f.parts)
    )


def read_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def parse_safe(code: str):
    try:
        return ast.parse(code)
    except SyntaxError:
        return None


def count_lines(path: Path) -> int:
    try:
        return sum(1 for _ in open(path, encoding="utf-8", errors="replace"))
    except Exception:
        return 0


def get_complexity_estimate(node: ast.AST) -> int:
    """Estimativa simples de complexidade ciclomática."""
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
        elif isinstance(child, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            complexity += 1
        if isinstance(child, ast.IfExp):
            complexity += 1
    return complexity


def get_django_version(root: Path) -> str | None:
    """Tenta detectar a versão do Django."""
    req = root / "requirements.txt"
    if req.exists():
        content = read_safe(req)
        m = re.search(r"Django[=<>!~]+(\d+\.\d+)", content, re.IGNORECASE)
        if m:
            return f"Django {m.group(1)}.x"
    pipfile = root / "Pipfile"
    if pipfile.exists():
        content = read_safe(pipfile)
        m = re.search(r'Django\s*=\s*"(\d+\.\d+)', content)
        if m:
            return f"Django {m.group(1)}.x"
    pyproject = root / "pyproject.toml"
    if pyproject.exists() and tomllib:
        try:
            data = tomllib.loads(read_safe(pyproject))
            deps = data.get("project", {}).get("dependencies", [])
            for d in deps:
                m = re.search(r"[Dd]ango[=<>!~]+(\d+\.\d+)", d)
                if m:
                    return f"Django {m.group(1)}.x"
        except Exception:
            pass
    return None


def file_hash(path: Path) -> str:
    """Hash MD5 rápido do conteúdo do arquivo."""
    content = read_safe(path).encode("utf-8")
    return hashlib.md5(content).hexdigest()[:12]


# ────────────────────────────────────────────────────────────────
# 1. ANÁLISE DE VIEWS (profunda)
# ────────────────────────────────────────────────────────────────

class ViewsAnalyzer:
    def __init__(self, root: Path):
        self.root = root
        self.results: dict[str, dict] = {}

    def find_views_files(self) -> list[Path]:
        """Encontra views.py e também arquivos dentro de views/."""
        candidates = set()
        for f in self.root.rglob("*.py"):
            if any(is_ignored(p) for p in f.parts):
                continue
            parts = f.parts
            if "views.py" in parts or "views" in parts:
                candidates.add(f)
        return sorted(candidates)

    def _analyze_function(self, node: ast.FunctionDef, file_content: str) -> dict:
        decorators = []
        for d in node.decorator_list:
            try:
                decorators.append(ast.unparse(d))
            except Exception:
                decorators.append("<complex decorator>")

        args = [a.arg for a in node.args.args]
        has_request = "request" in args
        has_return = any(isinstance(n, ast.Return) for n in ast.walk(node))
        has_render = any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "render"
            for n in ast.walk(node)
        )
        has_json_response = any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "JsonResponse"
            for n in ast.walk(node)
        )
        has_redirect = any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "redirect"
            for n in ast.walk(node)
        )
        has_get_or_404 = any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "get_object_or_404"
            for n in ast.walk(node)
        )
        has_get_list_or_404 = any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "get_list_or_404"
            for n in ast.walk(node)
        )

        # Detectar queries dentro de loops (anti-padrão N+1 indireto)
        loop_queries = []
        for child in ast.walk(node):
            if isinstance(child, (ast.For, ast.While)):
                for inner in ast.walk(child):
                    if isinstance(inner, ast.Call):
                        fn_name = ""
                        if isinstance(inner.func, ast.Attribute):
                            fn_name = inner.func.attr
                        elif isinstance(inner.func, ast.Name):
                            fn_name = inner.func.id
                        if fn_name in ("filter", "get", "exclude", "all", "count"):
                            loop_queries.append(fn_name)

        # Detectar try/except muito largo
        bare_except = any(
            isinstance(n, ast.ExceptHandler) and n.type is None
            for n in ast.walk(node)
        )
        broad_except = any(
            isinstance(n, ast.ExceptHandler) and isinstance(n.type, ast.Name) and n.type.id == "Exception"
            for n in ast.walk(node)
        )

        # Detectar manipulação direta de POST sem form
        has_request_post = False
        has_form_usage = False
        for child in ast.walk(node):
            if isinstance(child, ast.Attribute):
                if child.attr == "POST" and isinstance(child.value, ast.Name) and child.value.id == "request":
                    has_request_post = True
                if child.attr in ("is_valid", "save", "cleaned_data") and isinstance(child.value, ast.Name):
                    has_form_usage = True

        body_lines = (node.end_lineno or node.lineno) - node.lineno
        complexity = get_complexity_estimate(node)
        has_docstring = (
            ast.get_docstring(node) is not None
        )

        issues = []
        if has_request and not any(d for d in decorators if "login_required" in d or "permission_required" in d):
            if node.name not in ("login", "logout", "register", "signup", "password_reset",
                                  "password_reset_done", "password_reset_confirm",
                                  "password_reset_complete", "password_change",
                                  "password_change_done"):
                issues.append("🔒 Sem @login_required/@permission_required — verificar se é pública")

        if body_lines > 80:
            issues.append(f"📏 Função muito longa ({body_lines} linhas) — extrair lógica")
        if body_lines > 150:
            issues.append(f"🔴 Função gigante ({body_lines} linhas) — refatoração urgente")

        if complexity > 15:
            issues.append(f"🧠 Complexidade estimada: {complexity} — muito alta, simplificar")
        elif complexity > 10:
            issues.append(f"🧠 Complexidade estimada: {complexity} — considere simplificar")

        if not has_return:
            issues.append("⚠️ Função sem return explícito")

        if loop_queries:
            issues.append(f"🔴 Queries dentro de loop: {', '.join(set(loop_queries))} — provável N+1")

        if bare_except:
            issues.append("🔴 except: nuu — captura toda exceção, incluindo KeyboardInterrupt")
        if broad_except and not bare_except:
            issues.append("🟡 except Exception: amplo — prefira exceções específicas")

        if has_request_post and not has_form_usage and "form" not in node.name.lower():
            issues.append("🟡 POST sem Form — validação manual? Use Django Forms")

        if not has_docstring:
            issues.append("📝 Sem docstring")

        return {
            "name": node.name,
            "line": node.lineno,
            "end_line": node.end_lineno or node.lineno,
            "decorators": decorators,
            "args": args,
            "body_lines": body_lines,
            "complexity": complexity,
            "has_docstring": has_docstring,
            "has_render": has_render,
            "has_json_response": has_json_response,
            "has_redirect": has_redirect,
            "has_get_or_404": has_get_or_404,
            "has_request_post": has_request_post,
            "has_form_usage": has_form_usage,
            "loop_queries": loop_queries,
            "bare_except": bare_except,
            "issues": issues,
        }

    def _analyze_class(self, node: ast.ClassDef) -> dict:
        bases = []
        for b in node.bases:
            try:
                bases.append(ast.unparse(b))
            except Exception:
                bases.append("<complex>")

        methods = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods.append(item.name)

        is_cbv = any("View" in b for b in bases)
        body_lines = (node.end_lineno or node.lineno) - node.lineno
        has_docstring = ast.get_docstring(node) is not None

        issues = []
        if not any(d for d in node.decorator_list if "login_required" in str(d) or "permission_required" in str(d)):
                # Verificar se é um mixin ou base
                if not any("Mixin" in b or "Base" in b for b in bases):
                    if node.name not in ("LoginView", "LogoutView", "PasswordResetView"):
                        issues.append("🔒 CBV sem @method_decorator(login_required) — verificar")

        if body_lines > 200:
            issues.append(f"📏 Classe muito longa ({body_lines} linhas)")

        if not has_docstring:
            issues.append("📝 Sem docstring")

        return {
            "name": node.name,
            "line": node.lineno,
            "end_line": node.end_lineno or node.lineno,
            "bases": bases,
            "is_cbv": is_cbv,
            "methods": methods,
            "body_lines": body_lines,
            "has_docstring": has_docstring,
            "issues": issues,
        }

    def analyze_file(self, path: Path) -> dict:
        content = read_safe(path)
        lines = content.splitlines()
        info = {
            "path": str(path.relative_to(self.root)),
            "absolute_path": str(path),
            "total_lines": len(lines),
            "file_hash": file_hash(path),
            "functions": [],
            "classes": [],
            "imports": [],
            "issues": [],
            "metrics": {
                "total_functions": 0,
                "total_classes": 0,
                "avg_function_lines": 0,
                "max_function_lines": 0,
                "avg_complexity": 0,
                "max_complexity": 0,
                "functions_without_docstring": 0,
                "classes_without_docstring": 0,
                "total_issues": 0,
            },
        }

        tree = parse_safe(content)
        if tree is None:
            info["issues"].append("🔴 Erro de sintaxe — arquivo não pôde ser parseado")
            return info

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                fn = self._analyze_function(node, content)
                info["functions"].append(fn)
            elif isinstance(node, ast.ClassDef):
                cls = self._analyze_class(node)
                info["classes"].append(cls)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                try:
                    info["imports"].append(ast.unparse(node))
                except Exception:
                    pass

        # Imports não utilizados (análise simples)
        used_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)

        for imp_str in info["imports"]:
            # Extrair o nome importado
            if "import" in imp_str:
                parts = imp_str.split("import")
                if len(parts) > 1:
                    name = parts[-1].strip().split(",")[0].strip().split(" as ")[0].strip()
                    if name and name not in used_names and name not in ("*",):
                        info["issues"].append(f"🟡 Import possivelmente não utilizado: `{name}`")

        # Métricas
        fns = info["functions"]
        clss = info["classes"]
        info["metrics"]["total_functions"] = len(fns)
        info["metrics"]["total_classes"] = len(clss)
        if fns:
            info["metrics"]["avg_function_lines"] = round(sum(f["body_lines"] for f in fns) / len(fns), 1)
            info["metrics"]["max_function_lines"] = max(f["body_lines"] for f in fns)
            info["metrics"]["avg_complexity"] = round(sum(f["complexity"] for f in fns) / len(fns), 1)
            info["metrics"]["max_complexity"] = max(f["complexity"] for f in fns)
            info["metrics"]["functions_without_docstring"] = sum(1 for f in fns if not f["has_docstring"])
        info["metrics"]["classes_without_docstring"] = sum(1 for c in clss if not c["has_docstring"])

        # Issues de arquivo
        if len(lines) > 400:
            info["issues"].append(f"⚠️ Arquivo grande ({len(lines)} linhas) — considerar dividir")
        if len(lines) > 800:
            info["issues"].append(f"🔴 Arquivo muito grande ({len(lines)} linhas) — divisão urgente")

        all_fn_issues = sum(len(f["issues"]) for f in fns)
        all_cls_issues = sum(len(c["issues"]) for c in clss)
        info["metrics"]["total_issues"] = len(info["issues"]) + all_fn_issues + all_cls_issues

        # Coletar issues das funções e classes no nível do arquivo
        for fn in fns:
            info["issues"].extend(fn["issues"])
        for cls in clss:
            info["issues"].extend(cls["issues"])

        return info

    def run(self) -> dict:
        for path in self.find_views_files():
            self.results[str(path)] = self.analyze_file(path)
        return self.results


# ────────────────────────────────────────────────────────────────
# 2. ANÁLISE DE MODELS (profunda)
# ────────────────────────────────────────────────────────────────

class ModelsAnalyzer:
    def __init__(self, root: Path):
        self.root = root
        self.results: dict[str, dict] = {}

    def find_models_files(self) -> list[Path]:
        return sorted(
            f for f in self.root.rglob("models.py")
            if not any(is_ignored(p) for p in f.parts)
        )

    def _analyze_field(self, node: ast.Assign) -> dict:
        """Analisa uma atribuição que provavelmente é um campo de modelo."""
        info = {"name": "", "type": "", "issues": []}
        if not isinstance(node.targets[0], ast.Name):
            return info
        info["name"] = node.targets[0].id

        # Detectar tipo do campo
        if isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Name):
                info["type"] = node.value.func.id
            elif isinstance(node.value.func, ast.Attribute):
                info["type"] = node.value.func.attr

            # Detectar argumentos
            for kw in node.value.keywords:
                if kw.arg == "null":
                    if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        pass  # null=True encontrado
                elif kw.arg == "blank":
                    pass
                elif kw.arg == "default":
                    if isinstance(kw.value, ast.Constant) and kw.value.value is not None:
                        info["has_default"] = True
                elif kw.arg == "db_index":
                    info["has_index"] = True
                elif kw.arg == "unique":
                    info["is_unique"] = True
                elif kw.arg == "related_name":
                    info["has_related_name"] = True

        # Regras
        field_type = info["type"]
        if field_type == "CharField":
            has_max_length = False
            if isinstance(node.value, ast.Call):
                for kw in node.value.keywords:
                    if kw.arg == "max_length":
                        has_max_length = True
            if not has_max_length:
                info["issues"].append("🔴 CharField sem max_length")

        if field_type == "ForeignKey":
            if "has_related_name" not in info:
                info["issues"].append("🟡 ForeignKey sem related_name — acessos reversos usarão app_model_set")

        if field_type == "TextField" and info["name"] in ("name", "title", "slug", "code", "email"):
            info["issues"].append(f"🟡 TextField para `{info['name']}` — CharField é mais apropriado")

        if field_type == "DateTimeField":
            has_auto = False
            if isinstance(node.value, ast.Call):
                for kw in node.value.keywords:
                    if kw.arg in ("auto_now", "auto_now_add"):
                        has_auto = True
            if not has_auto and info["name"] in ("created_at", "updated_at", "created", "modified"):
                info["issues"].append(f"🟡 `{info['name']}` sem auto_now/auto_now_add")

        if field_type in ("DateField", "DateTimeField") and info["name"] in ("created_at", "updated_at"):
            if "has_index" not in info:
                info["issues"].append(f"🟡 `{info['name']}` sem db_index — consultas por data são comuns")

        return info

    def _analyze_model_class(self, node: ast.ClassDef) -> dict:
        info = {
            "name": node.name,
            "line": node.lineno,
            "bases": [],
            "fields": [],
            "methods": [],
            "meta_options": [],
            "has_str": False,
            "has_absolute_url": False,
            "has_meta": False,
            "has_clean": False,
            "has_save": False,
            "has_docstring": ast.get_docstring(node) is not None,
            "field_count": 0,
            "issues": [],
            "body_lines": (node.end_lineno or node.lineno) - node.lineno,
        }

        for b in node.bases:
            try:
                info["bases"].append(ast.unparse(b))
            except Exception:
                info["bases"].append("<complex>")

        is_model = any("Model" in b for b in info["bases"])
        if not is_model:
            return None

        for item in node.body:
            if isinstance(item, ast.Assign):
                field = self._analyze_field(item)
                if field["type"] and any(
                    t in field["type"]
                    for t in ("Field", "ForeignKey", "OneToOne", "ManyToMany")
                ):
                    info["fields"].append(field)
                    info["field_count"] += 1
                    info["issues"].extend(field["issues"])
            elif isinstance(item, ast.FunctionDef):
                info["methods"].append(item.name)
                if item.name == "__str__":
                    info["has_str"] = True
                elif item.name == "get_absolute_url":
                    info["has_absolute_url"] = True
                elif item.name == "clean":
                    info["has_clean"] = True
                elif item.name == "save":
                    info["has_save"] = True
            elif isinstance(item, ast.ClassDef) and item.name == "Meta":
                info["has_meta"] = True
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        try:
                            name = meta_item.targets[0].id if isinstance(meta_item.targets[0], ast.Name) else ""
                            info["meta_options"].append(name)
                        except Exception:
                            pass

        # Regras de modelo
        if not info["has_str"]:
            info["issues"].append("🟡 Sem __str__ — representação padrão será 'ModelName object'")

        if not info["has_meta"]:
            info["issues"].append("🟡 Sem classe Meta — adicionar ordering, verbose_name, etc.")
        else:
            if "ordering" not in info["meta_options"]:
                info["issues"].append("🟡 Meta sem ordering — queryset padrão sem ordem definida")
            if "verbose_name" not in info["meta_options"] and "verbose_name_plural" not in info["meta_options"]:
                info["issues"].append("🟡 Meta sem verbose_name — nomes no admin serão automáticos")

        if info["field_count"] > 20:
            info["issues"].append(f"🔴 Modelo com {info['field_count']} campos — considerar dividir")

        if info["field_count"] > 0 and not info["has_clean"]:
            info["issues"].append("🟡 Sem método clean() — validações que cruzam campos não são feitas")

        if not info["has_docstring"]:
            info["issues"].append("📝 Sem docstring")

        if info["has_save"] and "super()" not in read_safe(
            self.root / next((k for k, v in self.results.items() if False), "")
        ):
            info["issues"].append("🟡 save() sobrescrito — verificar se chama super().save()")

        # Verificar se save chama super
        if info["has_save"]:
            content = read_safe(self.root / next(iter(self.results), ""))
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "save":
                    has_super = any(
                        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "save"
                        for n in ast.walk(item)
                    )
                    if not has_super:
                        info["issues"].append("🔴 save() não chama super().save() — dados podem não ser salvos")

        return info

    def analyze_file(self, path: Path) -> dict:
        content = read_safe(path)
        lines = content.splitlines()
        info = {
            "path": str(path.relative_to(self.root)),
            "total_lines": len(lines),
            "models": [],
            "issues": [],
            "metrics": {
                "total_models": 0,
                "models_without_str": 0,
                "models_without_meta": 0,
                "total_fields": 0,
                "big_models": 0,
            },
        }

        tree = parse_safe(content)
        if tree is None:
            info["issues"].append("🔴 Erro de sintaxe")
            return info

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                model = self._analyze_model_class(node)
                if model:
                    info["models"].append(model)
                    info["issues"].extend(model["issues"])

        info["metrics"]["total_models"] = len(info["models"])
        info["metrics"]["models_without_str"] = sum(1 for m in info["models"] if not m["has_str"])
        info["metrics"]["models_without_meta"] = sum(1 for m in info["models"] if not m["has_meta"])
        info["metrics"]["total_fields"] = sum(m["field_count"] for m in info["models"])
        info["metrics"]["big_models"] = sum(1 for m in info["models"] if m["field_count"] > 15)

        if len(lines) > 500:
            info["issues"].append(f"⚠️ models.py grande ({len(lines)} linhas) — considere dividir em models/")

        return info

    def run(self) -> dict:
        for path in self.find_models_files():
            self.results[str(path)] = self.analyze_file(path)
        return self.results


# ────────────────────────────────────────────────────────────────
# 3. ANÁLISE DE URLs (profunda)
# ────────────────────────────────────────────────────────────────

class UrlsAnalyzer:
    def __init__(self, root: Path):
        self.root = root
        self.results: dict[str, dict] = {}

    def find_url_files(self) -> list[Path]:
        return sorted(
            f for f in self.root.rglob("urls.py")
            if not any(is_ignored(p) for p in f.parts)
        )

    def analyze_file(self, path: Path) -> dict:
        content = read_safe(path)
        lines = content.splitlines()
        info = {
            "path": str(path.relative_to(self.root)),
            "total_lines": len(lines),
            "patterns": [],
            "includes": [],
            "has_app_name": False,
            "has_namespace": False,
            "uses_path": False,
            "uses_re_path": False,
            "uses_url": False,  # antigo
            "issues": [],
        }

        tree = parse_safe(content)
        if tree is None:
            info["issues"].append("🔴 Erro de sintaxe")
            return info

        # Detectar app_name e namespace
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if isinstance(node.targets[0], ast.Name):
                    if node.targets[0].id == "app_name":
                        info["has_app_name"] = True
                    elif node.targets[0].id == "urlpatterns" and isinstance(node.value, ast.List):
                        for item in node.value.elts:
                            if isinstance(item, ast.Call):
                                func_name = ""
                                if isinstance(item.func, ast.Name):
                                    func_name = item.func.id
                                elif isinstance(item.func, ast.Attribute):
                                    func_name = item.func.attr

                                pattern_info = {"type": func_name, "line": item.lineno}

                                # Extrair argumentos
                                if item.args:
                                    try:
                                        pattern_info["route"] = ast.unparse(item.args[0])
                                    except Exception:
                                        pass

                                # Detectar namespace em include
                                for kw in item.keywords:
                                    if kw.arg == "namespace":
                                        info["has_namespace"] = True
                                        try:
                                            pattern_info["namespace"] = ast.unparse(kw.value)
                                        except Exception:
                                            pass

                                if func_name == "include":
                                    info["includes"].append(pattern_info)
                                else:
                                    info["patterns"].append(pattern_info)

                                if func_name == "path":
                                    info["uses_path"] = True
                                elif func_name == "re_path":
                                    info["uses_re_path"] = True
                                elif func_name == "url":
                                    info["uses_url"] = True

        # Issues
        if info["uses_url"]:
            info["issues"].append("🔴 url() descontinuado — migrar para path()")

        if info["uses_re_path"] and not info["uses_path"]:
            info["issues"].append("🟡 Usando re_path() — path() é preferível para rotas simples")

        if "urls.py" not in path.parts[-1]:
            pass
        elif not info["has_app_name"] and path != self.root / "urls.py":
            info["issues"].append("🟡 Sem app_name — namespacing de URLs será inconsistente")

        if not info["patterns"] and not info["includes"]:
            info["issues"].append("🟡 urlpatterns vazio ou não detectado")

        # Verificar rotas sem trailing slash
                # Verificar rotas sem trailing slash
        for p in info["patterns"]:
            route = p.get("route", "")
            route_clean = route.strip("'\"")
            if isinstance(route_clean, str) and route_clean and not route_clean.endswith("/") and not route_clean.startswith("<"):
                info["issues"].append(f"🟡 Rota sem / final: `{route_clean}` — Django geralmente espera /")

        return info

    def run(self) -> dict:
        for path in self.find_url_files():
            self.results[str(path)] = self.analyze_file(path)
        return self.results


# ────────────────────────────────────────────────────────────────
# 4. ANÁLISE DE TEMPLATES (profunda)
# ────────────────────────────────────────────────────────────────

class TemplatesAnalyzer:
    SECURITY_PATTERNS = [
        (r"\{\{[^}]+\|\s*safe\s*\}\}", "Uso de |safe — possível XSS se dados vierem do usuário"),
        (r"\{\{[^}]+\|\s*force_escape\s*\}\}", "|force_escape encontrado — verifique se é necessário"),
        (r"<script[^>]*>[^<]*\{\{", "<script> com variável Django inline — risco XSS alto"),
        (r"mark_safe\s*\(", "mark_safe() — revisar se entrada é confiável"),
        (r"\{\%\s*autoescape\s+off\s*\%\}", "autoescape desligado — XSS garantido se houver input de usuário"),
        (r"href\s*=\s*['\"]javascript:", "href com javascript: — risco XSS"),
        (r"onclick\s*=\s*['\"][^'\"]*\{\{", "onclick com variável Django — risco XSS"),
    ]

    DESIGN_PATTERNS = [
        (r"style\s*=\s*['\"]", "CSS inline — mover para arquivo .css"),
        (r"<center>", "<center> obsoleta — usar CSS flexbox/grid"),
        (r"<font\s", "<font> obsoleta — usar CSS"),
        (r"<b>(?!</b>)", "<b> sem fechamento imediato — usar <strong>"),
        (r"<i>(?!</i>)", "<i> sem fechamento imediato — usar <em>"),
        (r"<u>(?!</u>)", "<u> obsoleta — usar CSS text-decoration"),
        (r"<marquee", "<marquee> obsoleta — remover"),
        (r"<blink", "<blink> obsoleta — remover"),
        (r"!\s*important", "!important no CSS — sinal de specificity mal resolvida"),
        (r"align\s*=\s*['\"]", "Atributo align obsoleto — usar CSS"),
        (r"bgcolor\s*=\s*['\"]", "bgcolor obsoleto — usar CSS background-color"),
        (r"valign\s*=\s*['\"]", "valign obsoleto — usar CSS vertical-align"),
    ]

    PERFORMANCE_PATTERNS = [
        (r"\{\%\s*for.*\%\}.*\{\{\s*forloop\.counter", "Loop com contador — verifique se pode ser otimizado"),
        (r"\{\%\s*for.*\%\}.*\{\%\s*if.*forloop", "If dentro de for baseado em forloop — pode ser simplificado"),
        (r"\{\{.*\.(all|filter|exclude)\(", "Query no template — DESASTRE de performance, mover para view"),
    ]

    def __init__(self, root: Path):
        self.root = root

    def find_template_dirs(self) -> dict:
        dirs = defaultdict(list)
        for f in collect_template_files(self.root):
            rel = f.relative_to(self.root)
            parts = rel.parts
            if "templates" in parts:
                idx = parts.index("templates")
                parent = "/".join(parts[: idx + 2]) if len(parts) > idx + 1 else "/".join(parts[: idx + 1])
                dirs[parent].append(str(rel))
            else:
                dirs["raiz/"].append(str(rel))
        return dict(dirs)

    def analyze_template(self, path: Path) -> dict:
        content = read_safe(path)
        lines = content.splitlines()
        issues = []

        extends = re.findall(r"\{%\s*extends\s+['\"](.+?)['\"]\s*%\}", content)
        blocks = re.findall(r"\{%\s*block\s+(\w+)\s*%\}", content)
        includes = re.findall(r"\{%\s*include\s+['\"](.+?)['\"]\s*%\}", content)
        static_tags = re.findall(r"\{%\s*static\s+['\"](.+?)['\"]\s*%\}", content)

        # Segurança
        for pattern, msg in self.SECURITY_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            if matches:
                issues.append(f"🔒 {msg} ({len(matches)}x)")

        # Design
        for pattern, msg in self.DESIGN_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                issues.append(f"🎨 {msg} ({len(matches)}x)")

        # Performance
        for pattern, msg in self.PERFORMANCE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                issues.append(f"⚡ {msg}")

        # Estrutura
        if not extends and "<!DOCTYPE" not in content and "<html" not in content.lower():
            if "{%" in content:
                issues.append("📁 Template com tags Django mas sem {% extends %} nem DOCTYPE — pode ser fragmento ou órfão")

        if len(lines) > 200:
            issues.append(f"📏 Template longo ({len(lines)} linhas) — considerar '{{% include %}}'")
        if len(lines) > 500:
            issues.append(f"🔴 Template muito longo ({len(lines)} linhas) — divisão urgente")

        # Verificar se tem form sem csrf_token
        has_form = "<form" in content.lower()
        has_csrf = "{% csrf_token %}" in content
        if has_form and not has_csrf:
            issues.append("🔴 <form> sem {% csrf_token %} — CSRF desabilitado nesta página")

        # Verificar se tem POST sem csrf
        if has_form and 'method="post"' in content.lower() and not has_csrf:
            issues.append("🔴 Formulário POST sem {% csrf_token %} — proteção CSRF ausente")

        # Detectar variáveis não escapadas em contextos perigosos
        unescaped_in_attr = re.findall(r"<[^>]+\{\{\s*([^}|]+)\s*\}\}", content)
        for var in unescaped_in_attr:
            if "|safe" not in var and "|escape" not in var:
                issues.append(f"🟡 Variável `{{{var}}}` em atributo HTML — garantir que está escapada")

        return {
            "path": str(path.relative_to(self.root)),
            "extends": extends,
            "blocks": blocks,
            "includes": includes,
            "static_tags": static_tags,
            "line_count": len(lines),
            "has_form": has_form,
            "has_csrf": has_csrf,
            "issues": issues,
        }

    def run(self) -> dict:
        files = collect_template_files(self.root)
        analyzed = [self.analyze_template(f) for f in files]
        dirs = self.find_template_dirs()

        # Detectar templates duplicados (mesmo nome em dirs diferentes)
        names = Counter(str(Path(f["path"]).name) for f in analyzed)
        duplicates = {name: count for name, count in names.items() if count > 1}

        # Detectar statics quebrados (arquivo referenciado não existe)
        broken_statics = set()
        for tf in analyzed:
            for static_path in tf["static_tags"]:
                # Procurar em todos os dirs static/
                found = False
                for static_dir in self.root.rglob("static"):
                    if any(is_ignored(p) for p in static_dir.parts):
                        continue
                    if (static_dir / static_path).exists():
                        found = True
                        break
                if not found:
                    broken_statics.add(static_path)

        return {
            "dirs": dirs,
            "files": analyzed,
            "total": len(files),
            "duplicates": duplicates,
            "broken_statics": sorted(broken_statics),
            "total_issues": sum(len(f["issues"]) for f in analyzed),
        }


# ────────────────────────────────────────────────────────────────
# 5. ANÁLISE DE FORMS (profunda)
# ────────────────────────────────────────────────────────────────

class FormsAnalyzer:
    def __init__(self, root: Path):
        self.root = root
        self.results: dict[str, dict] = {}

    def find_forms_files(self) -> list[Path]:
        return sorted(
            f for f in self.root.rglob("forms.py")
            if not any(is_ignored(p) for p in f.parts)
        )

    def analyze_file(self, path: Path) -> dict:
        content = read_safe(path)
        lines = content.splitlines()
        info = {
            "path": str(path.relative_to(self.root)),
            "total_lines": len(lines),
            "forms": [],
            "issues": [],
        }

        tree = parse_safe(content)
        if tree is None:
            info["issues"].append("🔴 Erro de sintaxe")
            return info

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                bases = []
                for b in node.bases:
                    try:
                        bases.append(ast.unparse(b))
                    except Exception:
                        bases.append("<complex>")

                is_form = any("Form" in b for b in bases)
                if not is_form:
                    continue

                fields = []
                has_clean = False
                has_save = False
                has_docstring = ast.get_docstring(node) is not None
                methods = []

                for item in node.body:
                    if isinstance(item, ast.Assign):
                        if isinstance(item.targets[0], ast.Name):
                            field_type = ""
                            if isinstance(item.value, ast.Call):
                                if isinstance(item.value.func, ast.Name):
                                    field_type = item.value.func.id
                                elif isinstance(item.value.func, ast.Attribute):
                                    field_type = item.value.func.attr
                            if "Field" in field_type:
                                fields.append({"name": item.targets[0].id, "type": field_type})
                    elif isinstance(item, ast.FunctionDef):
                        methods.append(item.name)
                        if item.name == "clean":
                            has_clean = True
                        elif item.name == "save":
                            has_save = True

                form_issues = []
                if not fields:
                    form_issues.append("🟡 Form sem campos — usar ModelForm?")
                if not has_clean:
                    form_issues.append("🟡 Sem clean() — validação cruzada não existe")
                if not has_docstring:
                    form_issues.append("📝 Sem docstring")

                # Verificar widgets customizados
                has_widget_override = False
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        code = ast.unparse(item) if hasattr(ast, "unparse") else ""
                        if "widget" in code:
                            has_widget_override = True

                info["forms"].append({
                    "name": node.name,
                    "bases": bases,
                    "fields": fields,
                    "methods": methods,
                    "has_clean": has_clean,
                    "has_save": has_save,
                    "has_widget_override": has_widget_override,
                    "has_docstring": has_docstring,
                    "issues": form_issues,
                })
                info["issues"].extend(form_issues)

        if not info["forms"]:
            info["issues"].append("🟡 Nenhum form encontrado neste arquivo")

        return info

    def run(self) -> dict:
        for path in self.find_forms_files():
            self.results[str(path)] = self.analyze_file(path)
        return self.results


# ────────────────────────────────────────────────────────────────
# 6. ANÁLISE DE ADMIN (profunda)
# ────────────────────────────────────────────────────────────────

class AdminAnalyzer:
    def __init__(self, root: Path, models: dict):
        self.root = root
        self.models = models  # vem do ModelsAnalyzer

    def find_admin_files(self) -> list[Path]:
        return sorted(
            f for f in self.root.rglob("admin.py")
            if not any(is_ignored(p) for p in f.parts)
        )

    def run(self) -> dict:
        all_models = set()
        registered_models = set()
        results = {}

        # Coletar todos os models
        for path, info in self.models.items():
            for model in info["models"]:
                all_models.add(model["name"])

        for path in self.find_admin_files():
            content = read_safe(path)
            info = {
                "path": str(path.relative_to(self.root)),
                "registered": [],
                "unregistered": [],
                "issues": [],
            }

            tree = parse_safe(content)
            if tree is None:
                info["issues"].append("🔴 Erro de sintaxe")
                results[str(path)] = info
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = ""
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr

                    if func_name == "register":
                        if node.args:
                            try:
                                model_name = ast.unparse(node.args[0])
                                # Pode ser um nome ou uma classe
                                if isinstance(node.args[0], ast.Name):
                                    registered_models.add(node.args[0].id)
                                info["registered"].append(model_name)
                            except Exception:
                                pass

                        # Verificar se tem ModelAdmin customizado
                        if len(node.args) > 1:
                            try:
                                admin_class = ast.unparse(node.args[1])
                                info["registered"][-1] = f"{info['registered'][-1]} → {admin_class}" if info["registered"] else admin_class
                            except Exception:
                                pass

            # Verificar unregister
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = ""
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    if func_name == "unregister":
                        if node.args:
                            try:
                                model_name = ast.unparse(node.args[0])
                                if isinstance(node.args[0], ast.Name):
                                    registered_models.discard(node.args[0].id)
                            except Exception:
                                pass

            # Detectar ModelAdmin classes e suas configs
            admin_classes = []
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef):
                    bases = []
                    for b in node.bases:
                        try:
                            bases.append(ast.unparse(b))
                        except Exception:
                            pass
                    if any("Admin" in b for b in bases):
                        attrs = []
                        for item in node.body:
                            if isinstance(item, ast.Assign):
                                try:
                                    attrs.append(ast.unparse(item).split("=")[0].strip())
                                except Exception:
                                    pass
                        admin_classes.append({
                            "name": node.name,
                            "bases": bases,
                            "attributes": attrs,
                        })

                        # Verificar se tem list_display, search_fields, etc.
                        has_list_display = "list_display" in attrs
                        has_search_fields = "search_fields" in attrs
                        has_list_filter = "list_filter" in attrs
                        has_actions = any("action" in a for a in attrs)

                        if not has_list_display:
                            info["issues"].append(f"🟡 {node.name} sem list_display — listagem padrão feia")
                        if not has_search_fields:
                            info["issues"].append(f"🟡 {node.name} sem search_fields — sem busca no admin")
                        if not has_list_filter:
                            info["issues"].append(f"🟡 {node.name} sem list_filter — sem filtros laterais")

            info["admin_classes"] = admin_classes

            # Models não registrados
            unregistered = all_models - registered_models
            if unregistered:
                info["unregistered"] = sorted(unregistered)
                info["issues"].append(f"🟡 {len(unregistered)} model(s) não registrado(s) no admin: {', '.join(sorted(unregistered))}")

            results[str(path)] = info

        return results


# ────────────────────────────────────────────────────────────────
# 7. ANÁLISE DE SIGNALS
# ────────────────────────────────────────────────────────────────

class SignalsAnalyzer:
    def __init__(self, root: Path):
        self.root = root

    def run(self) -> dict:
        results = {}
        for path in self.root.rglob("signals.py"):
            if any(is_ignored(p) for p in path.parts):
                continue
            content = read_safe(path)
            info = {
                "path": str(path.relative_to(self.root)),
                "signals": [],
                "issues": [],
            }

            tree = parse_safe(content)
            if tree is None:
                info["issues"].append("🔴 Erro de sintaxe")
                results[str(path)] = info
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = ""
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr

                    if func_name in ("post_save", "pre_save", "post_delete", "pre_delete",
                                      "m2m_changed", "request_started", "request_finished"):
                        receiver = ""
                        sender = ""
                        if node.args:
                            try:
                                receiver = ast.unparse(node.args[0])
                            except Exception:
                                pass
                        for kw in node.keywords:
                            if kw.arg == "sender":
                                try:
                                    sender = ast.unparse(kw.value)
                                except Exception:
                                    pass

                        info["signals"].append({
                            "signal": func_name,
                            "receiver": receiver,
                            "sender": sender,
                            "line": node.lineno,
                        })

                        if not sender:
                            info["issues"].append(f"🟡 {func_name} sem sender explícito — pode disparar para models indesejados")

            # Verificar se signals.py é importado em apps.py
            apps_py = path.parent / "apps.py"
            if apps_py.exists():
                apps_content = read_safe(apps_py)
                if "signals" not in apps_content:
                    info["issues"].append("🔴 Signals não importados em apps.py — signals NÃO estão ativos!")

            if not info["signals"]:
                info["issues"].append("🟡 signals.py existe mas não define signals")

            results[str(path)] = info

        return results


# ────────────────────────────────────────────────────────────────
# 8. ANÁLISE DE SEGURANÇA (settings — expandida)
# ────────────────────────────────────────────────────────────────

class SecurityAnalyzer:
    DANGEROUS_PATTERNS = [
        (r"DEBUG\s*=\s*True", "🔴 DEBUG=True — stack traces expostos", "critical"),
        (r"ALLOWED_HOSTS\s*=\s*\[\s*\]", "🔴 ALLOWED_HOSTS=[] — host header injection", "critical"),
        (r"ALLOWED_HOSTS\s*=\s*\[\s*['\"]\*['\"]\s*\]", "🟡 ALLOWED_HOSTS=['*'] — vulnerável em produção", "high"),
        (r"CORS_ALLOW_ALL_ORIGINS\s*=\s*True", "🟡 CORS aberto para todas as origens", "high"),
        (r"SESSION_COOKIE_SECURE\s*=\s*False", "🔴 Cookie de sessão sem Secure flag", "high"),
        (r"CSRF_COOKIE_SECURE\s*=\s*False", "🔴 Cookie CSRF sem Secure flag", "high"),
        (r"SESSION_COOKIE_HTTPONLY\s*=\s*False", "🟡 Cookie de sessão sem HttpOnly", "medium"),
        (r"CSRF_COOKIE_HTTPONLY\s*=\s*False", "🟡 Cookie CSRF sem HttpOnly", "medium"),
        (r"SECURE_SSL_REDIRECT\s*=\s*False", "🟡 SSL redirect desativado", "medium"),
        (r"X_FRAME_OPTIONS\s*=\s*['\"]SAMEORIGIN['\"]", "🟡 X-Frame-Options SAMEORIGIN — considere DENY", "low"),
        (r"PASSWORD_HASHERS.*MD5Password", "🔴 MD5 para senhas — inseguro", "critical"),
        (r"DEFAULT_AUTO_FIELD\s*=\s*['\"]", "", "info"),
    ]

    GOOD_SETTINGS = [
        ("SECURE_HSTS_SECONDS", "HSTS"),
        ("SECURE_SSL_REDIRECT", "SSL Redirect"),
        ("SECURE_CONTENT_TYPE_NOSNIFF", "Content-Type Nosniff"),
        ("SECURE_BROWSER_XSS_FILTER", "XSS Filter"),
        ("SECURE_REFERRER_POLICY", "Referrer Policy"),
        ("SESSION_COOKIE_SECURE", "Session Secure"),
        ("SESSION_COOKIE_HTTPONLY", "Session HttpOnly"),
        ("CSRF_COOKIE_SECURE", "CSRF Secure"),
        ("CSRF_COOKIE_HTTPONLY", "CSRF HttpOnly"),
        ("X_FRAME_OPTIONS", "X-Frame-Options"),
        ("SECURE_HSTS_INCLUDE_SUBDOMAINS", "HSTS Subdomains"),
        ("SECURE_HSTS_PRELOAD", "HSTS Preload"),
    ]

    AUTH_VALIDATORS = [
        "UserAttributeSimilarityValidator",
        "MinimumLengthValidator",
        "CommonPasswordValidator",
        "NumericPasswordValidator",
    ]

    def __init__(self, root: Path):
        self.root = root

    def find_settings(self) -> list[Path]:
        candidates = []
        for f in self.root.rglob("*.py"):
            if f.resolve() == _THIS_SCRIPT: # evitar analisar este script
                continue
            if any(is_ignored(p) for p in f.parts):
                continue
            content = read_safe(f)
            if "SECRET_KEY" in content and "INSTALLED_APPS" in content:
                candidates.append(f)
        if not candidates:
            candidates = list(self.root.rglob("settings.py"))
            candidates += list(self.root.rglob("settings/*.py"))
        return sorted(set(candidates))

    def analyze(self) -> dict:
        issues = []
        good = []
        settings_files = self.find_settings()
        all_content = ""

        for sf in settings_files:
            content = read_safe(sf)
            all_content += content + "\n"
            rel = str(sf.relative_to(self.root))

            # SECRET_KEY hardcoded
            sk_matches = re.findall(r"SECRET_KEY\s*=\s*['\"]([^'\"]{10,})['\"]", content)
            for sk in sk_matches:
                if not any(x in sk.lower() for x in ["os", "env", "config", "get"]):
                    issues.append({
                        "severity": "critical",
                        "msg": f"`{rel}`: SECRET_KEY hardcoded — usar variável de ambiente",
                    })

            # Padrões perigosos
            for pattern, msg, severity in self.DANGEROUS_PATTERNS:
                if msg and re.search(pattern, content):
                    issues.append({"severity": severity, "msg": f"`{rel}`: {msg}"})

            # Boas práticas
            for setting, label in self.GOOD_SETTINGS:
                if setting in content:
                    good.append(label)

            # Verificar AUTH_PASSWORD_VALIDATORS
            validators_found = []
            for validator in self.AUTH_VALIDATORS:
                if validator in content:
                    validators_found.append(validator)

            missing_validators = set(self.AUTH_VALIDATORS) - set(validators_found)
            if missing_validators:
                issues.append({
                    "severity": "high",
                    "msg": f"`{rel}`: Validadores de senha ausentes: {', '.join(missing_validators)}",
                })

            # Verificar se é settings de produção
            is_prod = any(x in content.lower() for x in ["production", "prod", "deploy"])
            is_dev = any(x in content.lower() for x in ["development", "dev", "local"])

            if is_prod and "DEBUG = True" in content:
                issues.append({
                    "severity": "critical",
                    "msg": f"`{rel}`: DEBUG=True em settings de PRODUÇÃO!",
                })

            # Verificar uso de env vars
            uses_env = "os.environ" in content or "environ" in content or "decouple" in content or "config(" in content
            if not uses_env:
                issues.append({
                    "severity": "high",
                    "msg": f"`{rel}`: Sem variáveis de ambiente — segredos provavelmente hardcoded",
                })

            # Verificar MIDDLEWARE de segurança
            middleware_match = re.search(r"MIDDLEWARE\s*=\s*\[(.*?)\]", content, re.DOTALL)
            if middleware_match:
                middleware_block = middleware_match.group(1)
                security_middleware = [
                    "SecurityMiddleware",
                    "SessionMiddleware",
                    "CsrfViewMiddleware",
                    "AuthenticationMiddleware",
                ]
                for mw in security_middleware:
                    if mw not in middleware_block:
                        issues.append({
                            "severity": "high",
                            "msg": f"`{rel}`: {mw} não encontrado em MIDDLEWARE",
                        })

            # Verificar DATABASES — SSL
            if "DATABASES" in content:
                if "SSL" not in content and "ssl" not in content.lower():
                    if is_prod:
                        issues.append({
                            "severity": "high",
                            "msg": f"`{rel}`: DATABASES sem SSL em settings de produção",
                        })

        # Verificar .env existe
        env_file = self.root / ".env"
        env_example = self.root / ".env.example"
        if env_file.exists():
            good.append(".env existe")
        if env_example.exists():
            good.append(".env.example existe")
        else:
            issues.append({
                "severity": "medium",
                "msg": ".env.example não encontrado — novo desenvolvedor não sabe quais variáveis precisa",
            })

        # Verificar .gitignore
        gitignore = self.root / ".gitignore"
        if gitignore.exists():
            gi_content = read_safe(gitignore)
            critical_ignores = [".env", "*.sqlite3", "db.sqlite3", "__pycache__", "*.pyc", "media/"]
            missing_ignores = [c for c in critical_ignores if c not in gi_content]
            if missing_ignores:
                issues.append({
                    "severity": "high",
                    "msg": f".gitignore não inclui: {', '.join(missing_ignores)}",
                })
        else:
            issues.append({"severity": "critical", "msg": ".gitignore não existe!"})

        # Severidade
        severity_counts = Counter(i["severity"] for i in issues)

        return {
            "files": [str(f.relative_to(self.root)) for f in settings_files],
            "issues": issues,
            "good": list(set(good)),
            "severity_counts": dict(severity_counts),
        }


# ────────────────────────────────────────────────────────────────
# 9. ANÁLISE DE TESTES
# ────────────────────────────────────────────────────────────────

class TestsAnalyzer:
    def __init__(self, root: Path):
        self.root = root

    def run(self) -> dict:
        test_files = sorted(
            f for f in self.root.rglob("*.py")
            if not any(is_ignored(p) for p in f.parts)
            and ("test" in f.stem or f.parent.name == "tests")
        )

        info = {
            "total_test_files": len(test_files),
            "test_files": [],
            "total_test_functions": 0,
            "total_test_classes": 0,
            "uses_pytest": False,
            "uses_unittest": False,
            "uses_factory_boy": False,
            "uses_mock": False,
            "has_fixtures": False,
            "issues": [],
            "coverage_estimate": "desconhecida",
        }

        for tf in test_files:
            content = read_safe(tf)
            file_info = {
                "path": str(tf.relative_to(self.root)),
                "lines": count_lines(tf),
                "test_functions": 0,
                "test_classes": 0,
            }

            tree = parse_safe(content)
            if tree is None:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                    file_info["test_functions"] += 1
                elif isinstance(node, ast.ClassDef) and any("Test" in b for b in
                    [ast.unparse(b) if hasattr(ast, "unparse") else "" for b in node.bases]):
                    file_info["test_classes"] += 1

            info["total_test_functions"] += file_info["test_functions"]
            info["total_test_classes"] += file_info["test_classes"]
            info["test_files"].append(file_info)

            # Detectar frameworks
            if "pytest" in content:
                info["uses_pytest"] = True
            if "unittest" in content or "TestCase" in content:
                info["uses_unittest"] = True
            if "factory" in content.lower() or "Factory" in content:
                info["uses_factory_boy"] = True
            if "Mock" in content or "patch" in content or "mock" in content:
                info["uses_mock"] = True
            if "fixtures" in content.lower() or "fixture" in content.lower():
                info["has_fixtures"] = True

        # Tentar rodar testes
        manage_py = self.root / "manage.py"
        if manage_py.exists() and info["total_test_functions"] > 0:
            try:
                result = subprocess.run(
                    [sys.executable, "manage.py", "test", "--no-input", "-v0"],
                    capture_output=True, text=True, timeout=60,
                    cwd=str(self.root),
                    encoding="utf-8", errors="replace",
                )
                if result.returncode == 0:
                    info["test_run_result"] = "✅ Todos os testes passaram"
                else:
                    info["test_run_result"] = f"❌ Testes falharam (exit code {result.returncode})"
                    # Extrair resumo
                    last_lines = result.stderr.strip().splitlines()[-5:]
                    info["test_run_summary"] = "\n".join(last_lines)
            except subprocess.TimeoutExpired:
                info["test_run_result"] = "⏰ Timeout — testes demoraram mais de 60s"
            except Exception as e:
                info["test_run_result"] = f"⚠️ Não foi possível rodar: {e}"

        # Tentar rodar cobertura
        if info["total_test_functions"] > 0:
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "coverage", "report", "--json"],
                    capture_output=True, text=True, timeout=60,
                    cwd=str(self.root),
                )
                if result.returncode == 0:
                    cov_data = json.loads(result.stdout)
                    info["coverage_estimate"] = f"{cov_data.get('totals', {}).get('percent_covered', 0):.1f}%"
            except Exception:
                pass

        # Issues
        if info["total_test_files"] == 0:
            info["issues"].append("🔴 NENHUM teste encontrado — risco crítico ao refatorar")
        elif info["total_test_functions"] < 5:
            info["issues"].append(f"🟡 Apenas {info['total_test_functions']} teste(s) — cobertura provavelmente baixa")

        if not info["uses_pytest"] and info["total_test_files"] > 0:
            info["issues"].append("🟡 Não usa pytest — migração recomendada para melhor DX")

        if not info["uses_factory_boy"] and info["total_test_functions"] > 10:
            info["issues"].append("🟡 Sem factory_boy — fixtures manuais podem ficar difíceis de manter")

        if not info["uses_mock"] and info["total_test_functions"] > 10:
            info["issues"].append("🟡 Sem mocks — testes podem ser lentos se batem em APIs externas")

        return info


# ────────────────────────────────────────────────────────────────
# 10. ANÁLISE DE ESTRUTURA GERAL (expandida)
# ────────────────────────────────────────────────────────────────

class StructureAnalyzer:
    def __init__(self, root: Path):
        self.root = root

    def get_apps(self) -> list[str]:
        apps = []
        for f in self.root.iterdir():
            if f.is_dir() and (f / "apps.py").exists():
                apps.append(f.name)
        return sorted(apps)

    def get_models_summary(self, models: dict) -> dict:
        summary = {}
        for path, info in models.items():
            for model in info["models"]:
                summary[model["name"]] = {
                    "file": path,
                    "fields": model["field_count"],
                    "issues": len(model["issues"]),
                }
        return summary

    def check_requirements(self) -> dict:
        req_file = self.root / "requirements.txt"
        pipfile = self.root / "Pipfile"
        pyproject = self.root / "pyproject.toml"

        found = {"arquivo": None, "content": "", "packages": []}
        if req_file.exists():
            found["arquivo"] = "requirements.txt"
            found["content"] = read_safe(req_file)
        elif pipfile.exists():
            found["arquivo"] = "Pipfile"
            found["content"] = read_safe(pipfile)
        elif pyproject.exists():
            found["arquivo"] = "pyproject.toml"
            found["content"] = read_safe(pyproject)

        content = found["content"]

        # Extrair pacotes
        found["packages"] = re.findall(r"^([a-zA-Z0-9_-]+)", content, re.MULTILINE)
        found["packages"] = [p.lower() for p in found["packages"] if len(p) > 2]

        # Categorias
        security_packages = ["django-csp", "django-axes", "django-ratelimit", "python-decouple",
                             "django-environ", "django-secure", "bandit"]
        testing_packages = ["pytest", "pytest-django", "pytest-cov", "factory-boy",
                            "coverage", "model-bakery", "freezegun"]
        quality_packages = ["flake8", "black", "isort", "mypy", "pylint", "ruff",
                            "django-stubs", "pre-commit"]
        perf_packages = ["django-debug-toolbar", "django-silk", "django-extensions",
                         "whitenoise", "django-compressor", "django-minify-html"]

        found["security_missing"] = [p for p in security_packages if p not in content.lower()]
        found["testing_present"] = [p for p in testing_packages if p in content.lower()]
        found["quality_present"] = [p for p in quality_packages if p in content.lower()]
        found["perf_present"] = [p for p in perf_packages if p in content.lower()]
        found["testing_missing"] = [p for p in testing_packages if p not in content.lower()]
        found["quality_missing"] = [p for p in quality_packages if p not in content.lower()]

        return found

    def detect_patterns(self) -> dict:
        has_services = bool(list(self.root.rglob("services.py")) or list(self.root.rglob("services/")))
        has_forms = bool(list(self.root.rglob("forms.py")))
        has_serializers = bool(list(self.root.rglob("serializers.py")))
        has_signals = bool(list(self.root.rglob("signals.py")))
        has_celery = bool((self.root / "celery.py").exists() or list(self.root.rglob("tasks.py")))
        has_api = has_serializers or (self.root / "api.py").exists() or (self.root / "api").is_dir()
        has_docker = bool((self.root / "Dockerfile").exists())
        has_docker_compose = bool((self.root / "docker-compose.yml").exists() or (self.root / "docker-compose.yaml").exists())
        has_ci = bool(
            (self.root / ".github" / "workflows").exists()
            or (self.root / ".gitlab-ci.yml").exists()
            or (self.root / ".circleci").exists()
            or (self.root / "Jenkinsfile").exists()
        )
        has_pre_commit = bool((self.root / ".pre-commit-config.yaml").exists())
        has_makefile = bool((self.root / "Makefile").exists())
        has_readme = bool((self.root / "README.md").exists())
        has_conventional_commits = has_pre_commit  # aproximação

        # Detectar padrão de projeto
        pattern = "desconhecido"
        if has_services and has_forms:
            pattern = "service-layer"
        elif has_forms:
            pattern = "fat-models-thin-views"
        if has_api and has_serializers:
            pattern = f"{pattern}+api" if pattern != "desconhecido" else "api-first"

        return {
            "pattern": pattern,
            "services_layer": has_services,
            "forms": has_forms,
            "api": has_api,
            "signals": has_signals,
            "celery": has_celery,
            "docker": has_docker,
            "docker_compose": has_docker_compose,
            "ci": has_ci,
            "pre_commit": has_pre_commit,
            "makefile": has_makefile,
            "readme": has_readme,
        }

    def count_lines_of_code(self) -> dict:
        """Contagem aproximada de linhas de código."""
        py_files = collect_python_files(self.root)
        template_files = collect_template_files(self.root)
        static_files = collect_static_files(self.root)

        py_lines = sum(count_lines(f) for f in py_files)
        template_lines = sum(count_lines(f) for f in template_files)
        static_lines = sum(count_lines(f) for f in static_files)

        return {
            "python_files": len(py_files),
            "python_lines": py_lines,
            "template_files": len(template_files),
            "template_lines": template_lines,
            "static_files": len(static_files),
            "static_lines": static_lines,
            "total_files": len(py_files) + len(template_files) + len(static_files),
            "total_lines": py_lines + template_lines + static_lines,
        }

    def detect_duplicate_code(self) -> dict:
        """Detecta funções com mesmo nome em arquivos diferentes (possível duplicação)."""
        func_map = defaultdict(list)
        for f in collect_python_files(self.root):
            content = read_safe(f)
            tree = parse_safe(content)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if not node.name.startswith("_"):
                        func_map[node.name].append(str(f.relative_to(self.root)))

        duplicates = {name: locs for name, locs in func_map.items() if len(locs) > 1}
        return dict(sorted(duplicates.items()))

    def run(self, models: dict) -> dict:
        return {
            "apps": self.get_apps(),
            "models_summary": self.get_models_summary(models),
            "requirements": self.check_requirements(),
            "patterns": self.detect_patterns(),
            "loc": self.count_lines_of_code(),
            "duplicate_functions": self.detect_duplicate_code(),
            "django_version": get_django_version(self.root),
        }


# ────────────────────────────────────────────────────────────────
# 11. ANÁLISE DE MIDDLEWARE (extraída dos settings)
# ────────────────────────────────────────────────────────────────

class MiddlewareAnalyzer:
    RECOMMENDED = [
        "SecurityMiddleware",
        "SessionMiddleware",
        "CommonMiddleware",
        "CsrfViewMiddleware",
        "AuthenticationMiddleware",
        "MessageMiddleware",
    ]

    OPTIONAL_GOOD = [
        "XFrameOptionsMiddleware",
        "LocaleMiddleware",
        "ClickjackingMiddleware",
    ]

    def __init__(self, root: Path):
        self.root = root

    def run(self) -> dict:
        middlewares = []
        settings_files = list(self.root.rglob("settings*.py"))
        if not settings_files:
            settings_files = list(self.root.rglob("settings/*.py"))

        for sf in settings_files:
            content = read_safe(sf)
            match = re.search(r"MIDDLEWARE\s*=\s*\[(.*?)\]", content, re.DOTALL)
            if match:
                block = match.group(1)
                for line in block.split("\n"):
                    line = line.split("#")[0].strip().strip("'\"").strip(",")
                    if line and not line.startswith("#"):
                        middlewares.append(line)

        issues = []
        for mw in self.RECOMMENDED:
            if not any(mw in m for m in middlewares):
                issues.append(f"🟡 Middleware recomendado ausente: {mw}")

        # Detectar ordem incorreta
        order_issues = []
        if "CsrfViewMiddleware" in str(middlewares) and "AuthenticationMiddleware" in str(middlewares):
            csrf_idx = next((i for i, m in enumerate(middlewares) if "CsrfViewMiddleware" in m), -1)
            auth_idx = next((i for i, m in enumerate(middlewares) if "AuthenticationMiddleware" in m), -1)
            if csrf_idx > auth_idx:
                order_issues.append("CsrfViewMiddleware depois de AuthenticationMiddleware — ordem incorreta")

        if order_issues:
            issues.append(f"🔴 Ordem de middleware: {', '.join(order_issues)}")

        return {
            "middlewares": middlewares,
            "issues": issues,
        }


# ────────────────────────────────────────────────────────────────
# 12. ANÁLISE DE SERIALIZERS/API (se existir)
# ────────────────────────────────────────────────────────────────

class ApiAnalyzer:
    def __init__(self, root: Path):
        self.root = root

    def run(self) -> dict:
        results = {}
        for path in list(self.root.rglob("serializers.py")) + list(self.root.rglob("api.py")):
            if any(is_ignored(p) for p in path.parts):
                continue
            content = read_safe(path)
            info = {
                "path": str(path.relative_to(self.root)),
                "serializers": [],
                "views": [],
                "issues": [],
                "uses_drf": "rest_framework" in content or "DRF" in content,
            }

            tree = parse_safe(content)
            if tree is None:
                continue

            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef):
                    bases = [ast.unparse(b) for b in node.bases]
                    is_serializer = any("Serializer" in b for b in bases)
                    is_viewset = any("ViewSet" in b or "View" in b for b in bases)

                    if is_serializer:
                        fields = []
                        for item in node.body:
                            if isinstance(item, ast.Assign) and isinstance(item.targets[0], ast.Name):
                                fields.append(item.targets[0].id)
                        info["serializers"].append({
                            "name": node.name,
                            "bases": bases,
                            "fields": fields,
                        })
                        if not fields:
                            info["issues"].append(f"🟡 {node.name} sem campos explícitos — usar Meta.model?")
                    elif is_viewset:
                        info["views"].append({"name": node.name, "bases": bases})

            if info["serializers"] or info["views"]:
                results[str(path)] = info

        return results


# ────────────────────────────────────────────────────────────────
# GERADOR DE RELATÓRIO MARKDOWN (completo)
# ────────────────────────────────────────────────────────────────

class ReportGenerator:
    def __init__(self, root: Path, data: dict):
        self.root = root
        self.data = data
        self.now = datetime.now().strftime("%d/%m/%Y %H:%M")

    def _h(self, text: str, level: int = 2) -> str:
        return f"\n{'#' * level} {text}\n"

    def _badge(self, count: int, zero: str = "✅", low: str = "🟢", mid: str = "🟡", high: str = "🔴") -> str:
        if count == 0:
            return zero
        if count <= 2:
            return f"{low} {count}"
        if count <= 5:
            return f"{mid} {count}"
        return f"{high} {count}"

    def _issue_list(self, issues: list[str], indent: int = 0) -> str:
        if not issues:
            return ""
        prefix = "  " * indent
        return "\n".join(f"{prefix}- {i}" for i in issues) + "\n"

    def _code(self, code: str, lang: str = "python") -> str:
        return f"\n```{lang}\n{code}\n```\n"

    def generate(self) -> str:
        r = []
        r.append(f"# 🔬 Relatório Completo de Análise — Projeto Django")
        r.append(f"\n> **Gerado em:** {self.now}")
        r.append(f"> **Projeto:** `{self.root}`")
        dv = self.data.get("structure", {}).get("django_version")
        if dv:
            r.append(f"> **Versão detectada:** {dv}")
        r.append(f"> **LOC total:** ~{self.data.get('structure', {}).get('loc', {}).get('total_lines', '?')} linhas")
        r.append("")

        r.append("---\n")

        # SUMÁRIO EXECUTIVO
        r.append(self._h("📋 Sumário Executivo", 2))
        sec = self.data.get("security", {})
        sev = sec.get("severity_counts", {})
        total_crit = sev.get("critical", 0)
        total_high = sev.get("high", 0)
        total_med = sev.get("medium", 0)
        total_low = sev.get("low", 0)

        views_issues = sum(len(v["issues"]) for v in self.data.get("views", {}).values())
        models_issues = sum(len(m["issues"]) for m in self.data.get("models", {}).values())
        tpl_issues = self.data.get("templates", {}).get("total_issues", 0)
        tests = self.data.get("tests", {})

        r.append("| Área | Problemas | Status |")
        r.append("|------|-----------|--------|")
        r.append(f"| 🔐 Segurança | {total_crit} críticos, {total_high} altos, {total_med} médios | {self._badge(total_crit + total_high, '✅ Seguro', '🟢 Ok', '🟡 Revisar', '🔴 Urgente')} |")
        r.append(f"| 📂 Views | {views_issues} | {self._badge(views_issues)} |")
        r.append(f"| 🗃️ Models | {models_issues} | {self._badge(models_issues)} |")
        r.append(f"| 🎨 Templates | {tpl_issues} | {self._badge(tpl_issues)} |")
        r.append(f"| 🧪 Testes | {tests.get('total_test_functions', 0)} testes | {self._badge(tests.get('total_test_functions', 0), '❌ Zero', '🟡 Poucos', '🟢 Ok', '🟢 Bom')} |")
        r.append("")

        if total_crit > 0:
            r.append(f"### 🚨 CRÍTICO — {total_crit} problema(s) que precisam de correção IMEDIATA\n")
            for issue in sec.get("issues", []):
                if issue.get("severity") == "critical":
                    r.append(f"- {issue['msg']}")
            r.append("")

        # VIEWS
        r.append("---\n")
        r.append(self._h("📂 Análise de Views", 2))
        views_data = self.data.get("views", {})
        if views_data:
            # Métricas globais
            total_fns = sum(v["metrics"]["total_functions"] for v in views_data.values())
            total_cbvs = sum(v["metrics"]["total_classes"] for v in views_data.values())
            avg_complexity = sum(v["metrics"]["avg_complexity"] for v in views_data.values() if v["metrics"]["avg_complexity"]) / max(len([v for v in views_data.values() if v["metrics"]["avg_complexity"]]), 1)
            max_complexity = max((v["metrics"]["max_complexity"] for v in views_data.values()), default=0)
            avg_lines = sum(v["metrics"]["avg_function_lines"] for v in views_data.values() if v["metrics"]["avg_function_lines"]) / max(len([v for v in views_data.values() if v["metrics"]["avg_function_lines"]]), 1)

            r.append("### Métricas Globais\n")
            r.append(f"| Métrica | Valor |")
            r.append(f"|---------|-------|")
            r.append(f"| Funções (FBVs) | {total_fns} |")
            r.append(f"| Classes (CBVs) | {total_cbvs} |")
            r.append(f"| Complexidade média | {avg_complexity:.1f} |")
            r.append(f"| Complexidade máxima | {max_complexity} |")
            r.append(f"| Tamanho médio (linhas) | {avg_lines:.0f} |")
            no_docstring = sum(v["metrics"]["functions_without_docstring"] for v in views_data.values())
            r.append(f"| Sem docstring | {no_docstring}/{total_fns} |")
            r.append("")

            for path, info in views_data.items():
                r.append(f"### `{info['path']}` ({info['total_lines']} linhas)\n")
                if info["issues"]:
                    r.append(self._issue_list(info["issues"]))

                # Top funções por complexidade
                all_fns = sorted(info["functions"], key=lambda x: x["complexity"], reverse=True)[:10]
                if all_fns:
                    r.append("**Funções mais complexas:**\n")
                    r.append("| Função | Linha | LOC | Complexidade | Problemas |")
                    r.append("|--------|-------|-----|-------------|-----------|")
                    for fn in all_fns:
                        issues_count = len(fn["issues"])
                        issues_str = f"{self._badge(issues_count)}" if issues_count > 0 else "✅"
                        r.append(f"| `{fn['name']}` | {fn['line']} | {fn['body_lines']} | {fn['complexity']} | {issues_str} |")
                    r.append("")

                # CBVs
                for cls in info["classes"]:
                    if cls["is_cbv"]:
                        if cls["issues"]:
                            r.append(f"**CBV `{cls['name']}`** ({cls['body_lines']} linhas):")
                            r.append(self._issue_list(cls["issues"]))

            # Plano de divisão
            r.append(self._h("🗂️ Plano de Divisão de Views", 3))
            r.append(self._code(textwrap.dedent("""\
                seu_app/
                └── views/
                    ├── __init__.py          ← re-exporta TUDO (zero breaking changes)
                    ├── auth_views.py         ← login, logout, registro
                    ├── dashboard_views.py    ← home, painel
                    ├── crud_views.py         ← CRUD genérico
                    ├── report_views.py       ← relatórios, exportações
                    ├── api_views.py          ← endpoints AJAX/JSON
                    └── mixins.py             ← mixins compartilhados
            """), "text"))
            r.append(self._code(textwrap.dedent("""\
                # views/__init__.py — MANTÉM COMPATIBILIDADE
                from .auth_views import *       # noqa: F401,F403
                from .dashboard_views import *  # noqa: F401,F403
                from .crud_views import *       # noqa: F401,F403
                from .report_views import *     # noqa: F401,F403
                from .api_views import *        # noqa: F401,F403
            """)))
            r.append("> ⚠️ **NÃO altere urls.py** — a re-exportação garante que todos os imports continuam funcionando.\n")
        else:
            r.append("*Nenhum arquivo de views encontrado.*\n")

        # MODELS
        r.append("---\n")
        r.append(self._h("🗃️ Análise de Models", 2))
        models_data = self.data.get("models", {})
        if models_data:
            total_models = sum(m["metrics"]["total_models"] for m in models_data.values())
            total_fields = sum(m["metrics"]["total_fields"] for m in models_data.values())
            no_str = sum(m["metrics"]["models_without_str"] for m in models_data.values())
            no_meta = sum(m["metrics"]["models_without_meta"] for m in models_data.values())
            big_models = sum(m["metrics"]["big_models"] for m in models_data.values())

            r.append("### Métricas Globais\n")
            r.append(f"| Métrica | Valor |")
            r.append(f"|---------|-------|")
            r.append(f"| Models | {total_models} |")
            r.append(f"| Campos totais | {total_fields} |")
            r.append(f"| Sem __str__ | {no_str}/{total_models} |")
            r.append(f"| Sem Meta | {no_meta}/{total_models} |")
            r.append(f"| Models grandes (>15 campos) | {big_models} |")
            r.append("")

            for path, info in models_data.items():
                r.append(f"### `{info['path']}` ({info['total_lines']} linhas)\n")
                for model in info["models"]:
                    r.append(f"**`{model['name']}`** — {model['field_count']} campos, {model['body_lines']} linhas")
                    if model["issues"]:
                        r.append(self._issue_list(model["issues"], 1))
                    # Campos com problemas
                    field_issues = [f for f in model["fields"] if f["issues"]]
                    if field_issues:
                        for f in field_issues:
                            for issue in f["issues"]:
                                r.append(f"  - Campo `{f['name']}` ({f['type']}): {issue}")
                if info["issues"]:
                    r.append("\n**Issues do arquivo:**")
                    r.append(self._issue_list(info["issues"]))
                r.append("")
        else:
            r.append("*Nenhum models.py encontrado.*\n")

        # URLS
        r.append("---\n")
        r.append(self._h("🔗 Análise de URLs", 2))
        urls_data = self.data.get("urls", {})
        if urls_data:
            total_patterns = sum(len(u["patterns"]) for u in urls_data.values())
            total_includes = sum(len(u["includes"]) for u in urls_data.values())
            r.append(f"**Total de padrões de URL:** {total_patterns} | **Includes:** {total_includes}\n")
            for path, info in urls_data.items():
                if info["issues"]:
                    r.append(f"**`{info['path']}`:**")
                    r.append(self._issue_list(info["issues"]))
        else:
            r.append("*Nenhum urls.py encontrado.*\n")

        # TEMPLATES
        r.append("---\n")
        r.append(self._h("🎨 Análise de Templates", 2))
        tpl_data = self.data.get("templates", {})
        if tpl_data and tpl_data.get("total", 0) > 0:
            r.append(f"**Total:** {tpl_data['total']} templates\n")

            # Diretórios
            r.append("### Diretórios de templates\n")
            for d, files in tpl_data.get("dirs", {}).items():
                r.append(f"- `{d}/` — {len(files)} arquivo(s)")
            r.append("")

            # Duplicados
            if tpl_data.get("duplicates"):
                r.append("### ⚠️ Templates com nome duplicado\n")
                for name, count in tpl_data["duplicates"].items():
                    r.append(f"- `{name}` aparece {count} vezes — Django pode carregar o errado")
                r.append("")

            # Statics quebrados
            if tpl_data.get("broken_statics"):
                r.append("### 🔴 Statics referenciados mas não encontrados\n")
                for s in tpl_data["broken_statics"][:20]:
                    r.append(f"- `{s}`")
                if len(tpl_data["broken_statics"]) > 20:
                    r.append(f"- ... e mais {len(tpl_data['broken_statics']) - 20}")
                r.append("")

            # Issues agrupados
            all_issues = []
            for tf in tpl_data.get("files", []):
                for issue in tf["issues"]:
                    all_issues.append((issue, tf["path"]))

            sec_issues = [(i, p) for i, p in all_issues if "🔒" in i]
            perf_issues = [(i, p) for i, p in all_issues if "⚡" in i]
            design_issues = [(i, p) for i, p in all_issues if "🎨" in i]
            other_issues = [(i, p) for i, p in all_issues if "🔒" not in i and "⚡" not in i and "🎨" not in i]

            if sec_issues:
                r.append("### 🔒 Problemas de Segurança\n")
                seen = set()
                for issue, path in sec_issues:
                    if issue not in seen:
                        r.append(f"- {issue} — `{path}`")
                        seen.add(issue)
                r.append("")

            if perf_issues:
                r.append("### ⚡ Problemas de Performance\n")
                seen = set()
                for issue, path in perf_issues:
                    if issue not in seen:
                        r.append(f"- {issue} — `{path}`")
                        seen.add(issue)
                r.append("")

            if design_issues:
                r.append("### 🎨 Problemas de Design\n")
                seen = set()
                for issue, path in design_issues:
                    if issue not in seen:
                        r.append(f"- {issue}")
                        seen.add(issue)
                r.append("")

            if other_issues:
                r.append("### Outros problemas\n")
                seen = set()
                for issue, path in other_issues:
                    if issue not in seen:
                        r.append(f"- {issue} — `{path}`")
                        seen.add(issue)
                r.append("")

            # Estrutura recomendada
            r.append("### 📐 Estrutura recomendada\n")
            r.append(self._code(textwrap.dedent("""\
                templates/
                ├── base/
                │   ├── base.html
                │   ├── base_auth.html
                │   └── base_dashboard.html
                ├── components/
                │   ├── navbar.html
                │   ├── sidebar.html
                │   ├── footer.html
                │   ├── alerts.html
                │   └── pagination.html
                ├── auth/
                │   ├── login.html
                │   └── register.html
                └── <app_name>/
                    ├── list.html
                    ├── detail.html
                    ├── form.html
                    └── confirm_delete.html
            """), "text"))
        else:
            r.append("*Nenhum template encontrado.*\n")

        # FORMS
        r.append("---\n")
        r.append(self._h("📝 Análise de Forms", 2))
        forms_data = self.data.get("forms", {})
        if forms_data:
            for path, info in forms_data.items():
                r.append(f"**`{info['path']}`:** {len(info['forms'])} form(s)")
                if info["issues"]:
                    r.append(self._issue_list(info["issues"]))
                for form in info["forms"]:
                    if form["issues"]:
                        r.append(f"  - `{form['name']}`: {'; '.join(form['issues'])}")
                r.append("")
        else:
            r.append("❌ **Nenhum forms.py encontrado** — validações provavelmente nas views\n")

        # ADMIN
        r.append("---\n")
        r.append(self._h("🔧 Análise de Admin", 2))
        admin_data = self.data.get("admin", {})
        if admin_data:
            for path, info in admin_data.items():
                r.append(f"**`{info['path']}`:**")
                if info["registered"]:
                    r.append(f"  - Registrados: {', '.join(info['registered'][:10])}")
                if info["unregistered"]:
                    r.append(f"  - **Não registrados:** {', '.join(info['unregistered'])}")
                if info["issues"]:
                    r.append(self._issue_list(info["issues"], 1))
                for ac in info.get("admin_classes", []):
                    attrs = ", ".join(ac["attributes"][:5])
                    r.append(f"  - `{ac['name']}` — atributos: {attrs}")
                r.append("")
        else:
            r.append("*Nenhum admin.py encontrado.*\n")

        # SIGNALS
        r.append("---\n")
        r.append(self._h("📡 Análise de Signals", 2))
        signals_data = self.data.get("signals", {})
        if signals_data:
            for path, info in signals_data.items():
                r.append(f"**`{info['path']}`:** {len(info['signals'])} signal(s)")
                for sig in info["signals"]:
                    r.append(f"  - `{sig['signal']}` → `{sig['receiver']}` (sender: {sig['sender'] or 'NENHUM'})")
                if info["issues"]:
                    r.append(self._issue_list(info["issues"], 1))
                r.append("")
        else:
            r.append("*Nenhum signals.py encontrado.*\n")

        # API
        r.append("---\n")
        r.append(self._h("🌐 Análise de API", 2))
        api_data = self.data.get("api", {})
        if api_data:
            for path, info in api_data.items():
                drf = "✅ DRF" if info["uses_drf"] else "❌ Sem DRF"
                r.append(f"**`{info['path']}`** ({drf}): {len(info['serializers'])} serializer(s), {len(info['views'])} view(s)")
                if info["issues"]:
                    r.append(self._issue_list(info["issues"]))
                r.append("")
        else:
            r.append("*Nenhuma API detectada.*\n")

        # SEGURANÇA
        r.append("---\n")
        r.append(self._h("🔐 Análise de Segurança", 2))
        if sec:
            r.append("### Arquivos de settings analisados\n")
            for f in sec.get("files", []):
                r.append(f"- `{f}`")
            r.append("")

            # Por severidade
            for sev_level, label in [("critical", "🔴 CRÍTICO"), ("high", "🟠 ALTO"), ("medium", "🟡 MÉDIO"), ("low", "🟢 BAIXO")]:
                issues_at_level = [i for i in sec.get("issues", []) if i.get("severity") == sev_level]
                if issues_at_level:
                    r.append(f"### {label}\n")
                    for issue in issues_at_level:
                        r.append(f"- {issue['msg']}")
                    r.append("")

            if sec.get("good"):
                r.append("### ✅ Configurações de segurança presentes\n")
                for g in sorted(set(sec["good"])):
                    r.append(f"- ✅ {g}")
                r.append("")

            # Checklist
            r.append("### 📋 Checklist de Segurança\n")
            checklist = [
                ("SECRET_KEY em variável de ambiente", "python-decouple ou django-environ"),
                ("DEBUG=False em produção", "Variável de ambiente"),
                ("ALLOWED_HOSTS configurado", "Lista explícita de domínios"),
                ("HTTPS forçado", "SECURE_SSL_REDIRECT = True"),
                ("HSTS", "SECURE_HSTS_SECONDS = 31536000"),
                ("Cookies seguros", "SESSION/CSRF_COOKIE_SECURE = True"),
                ("Cookies HttpOnly", "SESSION/CSRF_COOKIE_HTTPONLY = True"),
                ("X-Frame-Options", "X_FRAME_OPTIONS = 'DENY'"),
                ("CSP headers", "django-csp"),
                ("Rate limiting", "django-axes ou django-ratelimit"),
                ("Validadores de senha", "AUTH_PASSWORD_VALIDATORS completos"),
                (".gitignore completo", ".env, *.sqlite3, __pycache__, media/"),
                (".env.example", "Documentar variáveis necessárias"),
                ("DB com SSL em produção", "OPTIONS: {'sslmode': 'require'}"),
            ]
            for item, tip in checklist:
                r.append(f"- [ ] {item}")
                r.append(f"  > 💡 {tip}")
            r.append("")

            r.append("### Settings de produção recomendados\n")
            r.append(self._code(textwrap.dedent("""\
                # settings/production.py
                from decouple import config, Csv

                SECRET_KEY = config('SECRET_KEY')
                DEBUG = False
                ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())

                SECURE_SSL_REDIRECT = True
                SECURE_HSTS_SECONDS = 31536000
                SECURE_HSTS_INCLUDE_SUBDOMAINS = True
                SECURE_HSTS_PRELOAD = True
                SECURE_CONTENT_TYPE_NOSNIFF = True
                SECURE_BROWSER_XSS_FILTER = True
                SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

                SESSION_COOKIE_SECURE = True
                SESSION_COOKIE_HTTPONLY = True
                SESSION_EXPIRE_AT_BROWSER_CLOSE = True
                CSRF_COOKIE_SECURE = True
                CSRF_COOKIE_HTTPONLY = True
                CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', cast=Csv())

                X_FRAME_OPTIONS = 'DENY'

                DATABASES['default']['OPTIONS'] = {'sslmode': 'require'}
            """)))
        else:
            r.append("*Nenhum settings encontrado.*\n")

        # MIDDLEWARE
        r.append("---\n")
        r.append(self._h("🔀 Análise de Middleware", 2))
        mw_data = self.data.get("middleware", {})
        if mw_data:
            if mw_data.get("middlewares"):
                r.append("### Middleware configurado\n")
                for i, mw in enumerate(mw_data["middlewares"], 1):
                    r.append(f"{i}. `{mw}`")
                r.append("")
            if mw_data.get("issues"):
                r.append(self._issue_list(mw_data["issues"]))
        r.append("")

        # TESTES
        r.append("---\n")
        r.append(self._h("🧪 Análise de Testes", 2))
        if tests:
            r.append(f"| Métrica | Valor |")
            r.append(f"|---------|-------|")
            r.append(f"| Arquivos de teste | {tests['total_test_files']} |")
            r.append(f"| Funções de teste | {tests['total_test_functions']} |")
            r.append(f"| Classes de teste | {tests['total_test_classes']} |")
            r.append(f"| Usa pytest | {'✅' if tests['uses_pytest'] else '❌'} |")
            r.append(f"| Usa unittest | {'✅' if tests['uses_unittest'] else '❌'} |")
            r.append(f"| Usa factory_boy | {'✅' if tests['uses_factory_boy'] else '❌'} |")
            r.append(f"| Usa mocks | {'✅' if tests['uses_mock'] else '❌'} |")
            r.append(f"| Cobertura | {tests['coverage_estimate']} |")
            r.append("")

            if tests.get("test_run_result"):
                r.append(f"**Resultado da execução:** {tests['test_run_result']}\n")
                if tests.get("test_run_summary"):
                    r.append(self._code(tests["test_run_summary"], "text"))

            if tests["issues"]:
                r.append(self._issue_list(tests["issues"]))

            if tests["total_test_files"] == 0:
                r.append("### 🚨 Como criar testes de sanidade ANTES de refatorar\n")
                r.append(self._code(textwrap.dedent("""\
                    # tests/test_sanity.py
                    import pytest
                    from django.urls import reverse, resolve
                    from django.test import Client

                    @pytest.mark.django_db
                    class TestURLSanity:
                        # Verifica que todas as URLs resolvem sem erro.

                        def test_home(self, client):
                            resp = client.get(reverse('home'))
                            assert resp.status_code in (200, 302)

                        def test_all_urls_resolvable(self):
                            # Lista todas as URLs e verifica se resolvem.
                            from django.urls import get_resolver
                            for pattern in get_resolver().url_patterns:
                                if hasattr(pattern, 'name') and pattern.name:
                                    try:
                                        reverse(pattern.name)
                                    except Exception:
                                        pass  # URLs com parâmetros vão falhar, é normal
                """)))
        r.append("")

        # ESTRUTURA
        r.append("---\n")
        r.append(self._h("🏗️ Análise Estrutural", 2))
        struct = self.data.get("structure", {})
        if struct:
            apps = struct.get("apps", [])
            r.append(f"**Apps Django:** {', '.join(apps) if apps else 'nenhum detectado na raiz'}\n")

            loc = struct.get("loc", {})
            r.append("### Linhas de Código\n")
            r.append("| Tipo | Arquivos | Linhas |")
            r.append("|------|----------|--------|")
            r.append(f"| Python | {loc.get('python_files', 0)} | {loc.get('python_lines', 0):,} |")
            r.append(f"| Templates | {loc.get('template_files', 0)} | {loc.get('template_lines', 0):,} |")
            r.append(f"| Estáticos | {loc.get('static_files', 0)} | {loc.get('static_lines', 0):,} |")
            r.append(f"| **Total** | **{loc.get('total_files', 0)}** | **{loc.get('total_lines', 0):,}** |")
            r.append("")

            # Padrões
            patterns = struct.get("patterns", {})
            r.append("### Padrões e Ferramentas Detectados\n")
            r.append("| Item | Status |")
            r.append("|------|--------|")
            r.append(f"| Padrão arquitetural | `{patterns.get('pattern', 'desconhecido')}` |")
            flags = [
                ("services_layer", "Camada de serviços"),
                ("forms", "Forms Django"),
                ("api", "API / Serializers"),
                ("signals", "Signals"),
                ("celery", "Celery / Tasks"),
                ("docker", "Docker"),
                ("docker_compose", "Docker Compose"),
                ("ci", "CI/CD"),
                ("pre_commit", "Pre-commit hooks"),
                ("makefile", "Makefile"),
                ("readme", "README.md"),
            ]
            for key, label in flags:
                status = "✅" if patterns.get(key) else "❌"
                r.append(f"| {label} | {status} |")
            r.append("")

            # Dependências
            req = struct.get("requirements", {})
            if req.get("arquivo"):
                r.append(f"### Dependências (`{req['arquivo']}`)\n")
                if req.get("security_missing"):
                    r.append("**Pacotes de segurança ausentes:**")
                    for p in req["security_missing"]:
                        r.append(f"  - `{p}`")
                    r.append("")
                if req.get("testing_missing"):
                    r.append("**Pacotes de teste ausentes:**")
                    for p in req["testing_missing"]:
                        r.append(f"  - `{p}`")
                    r.append("")
                if req.get("quality_missing"):
                    r.append("**Pacotes de qualidade ausentes:**")
                    for p in req["quality_missing"]:
                        r.append(f"  - `{p}`")
                    r.append("")
                if req.get("quality_present"):
                    r.append("**Ferramentas de qualidade presentes:**")
                    for p in req["quality_present"]:
                        r.append(f"  - ✅ `{p}`")
                    r.append("")

            # Funções duplicadas
            dups = struct.get("duplicate_functions", {})
            if dups:
                r.append("### ⚠️ Funções com nome duplicado em arquivos diferentes\n")
                for name, locs in list(dups.items())[:20]:
                    r.append(f"- `{name}` em: {', '.join(locs)}")
                r.append("")

        # EFICIÊNCIA
        r.append("---\n")
        r.append(self._h("⚡ Melhorias de Eficiência", 2))
        r.append("### ORM / Banco de Dados\n")
        r.append(self._code(textwrap.dedent("""\
            # ❌ N+1 — uma query por iteração
            for obj in MyModel.objects.all():
                print(obj.related.name)

            # ✅ select_related — 1 query para FKs
            for obj in MyModel.objects.select_related('related').all():
                print(obj.related.name)

            # ✅ prefetch_related — para M2M e reverse FKs
            for obj in MyModel.objects.prefetch_related('tags').all():
                print([t.name for t in obj.tags.all()])
        """)))
        r.append(self._code(textwrap.dedent("""\
            # ✅ Paginação obrigatória
            from django.core.paginator import Paginator
            paginator = Paginator(queryset, 25)
            page = paginator.get_page(request.GET.get('page'))
        """)))
        r.append(self._code(textwrap.dedent("""\
            # ✅ Índices em campos filtrados frequentemente
            class MyModel(models.Model):
                status = models.CharField(max_length=20, db_index=True)
                created_at = models.DateTimeField(db_index=True)

                class Meta:
                    indexes = [
                        models.Index(fields=['status', 'created_at']),
                    ]
        """)))
        r.append(self._code(textwrap.dedent("""\
            # ✅ Only/Defer — carregar só o necessário
            MyModel.objects.only('id', 'name')  # só estes campos
            MyModel.objects.defer('big_text_field')  # todos exceto este
        """)))
        r.append(self._code(textwrap.dedent("""\
            # ✅ Cache para queries custosas
            from django.core.cache import cache

            def get_expensive_data():
                data = cache.get('expensive_data')
                if data is None:
                    data = MyModel.objects.annotate(...).filter(...)
                    cache.set('expensive_data', data, 300)
                return data
        """)))
        r.append("")

        # PLANO DE MIGRAÇÃO
        r.append("---\n")
        r.append(self._h("🚀 Plano de Migração Segura", 2))
        r.append("> **Princípio:** Cada passo deve ser testável isoladamente.\n")
        r.append("> ** Nunca refatore views + templates + models simultaneamente.\n")

        steps = [
            ("0", "🔴 CORRIGIR problemas críticos de segurança PRIMEIRO",
             ["Mover SECRET_KEY para .env", "Configurar ALLOWED_HOSTS", "Adicionar .env ao .gitignore",
              "Criar .env.example"]),
            ("1", "🧪 Criar testes de sanidade",
             ["pip install pytest pytest-django", "Criar tests/test_sanity.py com teste para cada URL",
              "Rodar e garantir que passam", "Este é seu PARAQUEDAS — não pule este passo"]),
            ("2", "📂 Dividir views.py em views/",
             ["Criar views/__init__.py com re-exportação", "Mover funções por tema",
              "Rodar testes após cada movimentação", "NÃO altere urls.py"]),
            ("3", "🗑️ Extrair lógica de negócio para services.py",
             ["Criar services.py em cada app", "Mover lógica das views para services",
              "Views ficam finas: request → service → response"]),
            ("4", "🎨 Reorganizar templates",
             ["Criar estrutura base/components/app", "Criar base.html extraindo HTML repetido",
              "Converter templates um por um", "Teste cada um no browser"]),
            ("5", "📝 Criar/organizar Forms",
             ["Mover validações das views para forms.py", "Criar ModelForms para CRUD",
              "Adicionar clean() para validação cruzada"]),
            ("6", "⚙️ Dividir settings",
             ["Criar settings/base.py, dev.py, production.py", "Mover segredos para .env",
              "Atualizar manage.py e wsgi.py para apontar para o settings correto"]),
            ("7", "🔐 Hardening de segurança",
             ["python manage.py check --deploy", "Revisar todos os |safe nos templates",
              "Configurar django-csp", "Instalar django-axes para rate limiting"]),
            ("8", "📊 Adicionar ferramentas de qualidade",
             ["pip install pre-commit black isort flake8 mypy django-stubs",
              "pre-commit autoupdate && pre-commit install",
              "Adicionar Makefile com comandos comuns"]),
        ]

        for num, title, items in steps:
            r.append(f"### Passo {num}: {title}\n")
            for item in items:
                r.append(f"- {item}")
            r.append("")

        # RECURSOS
        r.append("---\n")
        r.append(self._h("📚 Recursos", 2))
        resources = [
            ("Django Design Philosophies", "https://docs.djangoproject.com/en/stable/misc/design-philosophies/"),
            ("Two Scoops of Django 3.x", "https://www.feldroy.com/books/two-scoops-of-django-3-x"),
            ("Django Deployment Checklist", "https://docs.djangoproject.com/en/stable/howto/deployment/checklist/"),
            ("django-csp", "https://django-csp.readthedocs.io/"),
            ("django-axes", "https://django-axes.readthedocs.io/"),
            ("pytest-django", "https://pytest-django.readthedocs.io/"),
            ("Django Debug Toolbar", "https://django-debug-toolbar.readthedocs.io/"),
            ("Django Silk (profiling)", "https://github.com/jazzband/django-silk"),
            ("Common Weakness Enumeration", "https://cwe.mitre.org/"),
        ]
        for name, url in resources:
            r.append(f"- [{name}]({url})")
        r.append("")
        r.append("---\n")
        r.append(f"*Relatório gerado por `analyze_django_project.py` — execute novamente após as melhorias para acompanhar o progresso.*\n")

        return "\n".join(r)


# ────────────────────────────────────────────────────────────────
# GERADOR DE JSON (dados brutos)
# ────────────────────────────────────────────────────────────────

def generate_json(data: dict) -> str:
    """Serializa os dados para JSON, convertendo Path para str."""
    def convert(obj):
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [convert(i) for i in obj]
        return obj
    return json.dumps(convert(data), indent=2, ensure_ascii=False)


# ────────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Varredura REAL e completa de um projeto Django",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Exemplos:
              python analyze_django_project.py /meu/projeto
              python analyze_django_project.py /meu/projeto -o relatorio.md
              python analyze_django_project.py /meu/projeto --json
              python analyze_django_project.py /meu/projeto --deep
        """),
    )
    parser.add_argument("project_path", nargs="?", default=".", help="Caminho do projeto Django")
    parser.add_argument("--output", "-o", default="relatorio_django.md", help="Arquivo .md de saída")
    parser.add_argument("--json", action="store_true", help="Também gera .json com dados brutos")
    parser.add_argument("--json-only", action="store_true", help="Gera apenas .json (sem .md)")
    parser.add_argument("--deep", action="store_true", help="Análise extra: tenta rodar testes e cobertura")
    args = parser.parse_args()

    project_path = Path(args.project_path).resolve()
    root = find_project_root(project_path)

    if not (root / "manage.py").exists():
        print(f"❌ manage.py não encontrado em {root}")
        print("   Certifique-se de que o caminho aponta para a raiz do projeto Django.")
        sys.exit(1)

    print(f"\n🔬 Análise profunda do projeto Django")
    print(f"   Projeto: {root}")
    print("=" * 60)

    # 1. Views
    print("📂 Views... ", end="", flush=True)
    va = ViewsAnalyzer(root)
    views = va.run()
    total_fns = sum(v["metrics"]["total_functions"] for v in views.values())
    print(f"{len(views)} arquivo(s), {total_fns} função(ões)")

    # 2. Models
    print("🗃️ Models... ", end="", flush=True)
    ma = ModelsAnalyzer(root)
    models = ma.run()
    total_models = sum(m["metrics"]["total_models"] for m in models.values())
    print(f"{len(models)} arquivo(s), {total_models} model(s)")

    # 3. URLs
    print("🔗 URLs... ", end="", flush=True)
    ua = UrlsAnalyzer(root)
    urls = ua.run()
    total_patterns = sum(len(u["patterns"]) for u in urls.values())
    print(f"{len(urls)} arquivo(s), {total_patterns} padrão(ões)")

    # 4. Templates
    print("🎨 Templates... ", end="", flush=True)
    ta = TemplatesAnalyzer(root)
    templates = ta.run()
    print(f"{templates['total']} arquivo(s), {templates['total_issues']} problema(s)")

    # 5. Forms
    print("📝 Forms... ", end="", flush=True)
    fa = FormsAnalyzer(root)
    forms = fa.run()
    total_forms = sum(len(f["forms"]) for f in forms.values())
    print(f"{len(forms)} arquivo(s), {total_forms} form(s)")

    # 6. Admin
    print("🔧 Admin... ", end="", flush=True)
    aa = AdminAnalyzer(root, models)
    admin = aa.run()
    print(f"{len(admin)} arquivo(s) analisado(s)")

    # 7. Signals
    print("📡 Signals... ", end="", flush=True)
    sa = SignalsAnalyzer(root)
    signals = sa.run()
    total_sigs = sum(len(s["signals"]) for s in signals.values())
    print(f"{len(signals)} arquivo(s), {total_sigs} signal(s)")

    # 8. Segurança
    print("🔐 Segurança... ", end="", flush=True)
    sec = SecurityAnalyzer(root)
    security = sec.analyze()
    sev = security.get("severity_counts", {})
    print(f"{len(security['issues'])} problema(s) ({sev.get('critical', 0)} críticos)")

    # 9. Middleware
    print("🔀 Middleware... ", end="", flush=True)
    mwa = MiddlewareAnalyzer(root)
    middleware = mwa.run()
    print(f"{len(middleware['middlewares'])} middleware(s)")

    # 10. API
    print("🌐 API... ", end="", flush=True)
    apa = ApiAnalyzer(root)
    api = apa.run()
    total_serializers = sum(len(a["serializers"]) for a in api.values())
    print(f"{len(api)} arquivo(s), {total_serializers} serializer(s)")

    # 11. Testes
    print("🧪 Testes... ", end="", flush=True)
    tea = TestsAnalyzer(root)
    tests = tea.run()
    print(f"{tests['total_test_functions']} teste(s) em {tests['total_test_files']} arquivo(s)")
    if tests.get("test_run_result"):
        print(f"   Resultado: {tests['test_run_result']}")
    if tests["coverage_estimate"] != "desconhecida":
        print(f"   Cobertura: {tests['coverage_estimate']}")

    # 12. Estrutura
    print("🏗️ Estrutura... ", end="", flush=True)
    stra = StructureAnalyzer(root)
    structure = stra.run(models)
    loc = structure.get("loc", {})
    print(f"{structure['apps']} app(s), {loc.get('total_lines', 0):,} LOC")

    # Montar dados
    data = {
        "root": str(root),
        "timestamp": datetime.now().isoformat(),
        "views": views,
        "models": models,
        "urls": urls,
        "templates": templates,
        "forms": forms,
        "admin": admin,
        "signals": signals,
        "security": security,
        "middleware": middleware,
        "api": api,
        "tests": tests,
        "structure": structure,
    }

    # Gerar JSON
    if args.json or args.json_only:
        json_path = Path(args.output).with_suffix(".json")
        json_path.write_text(generate_json(data), encoding="utf-8")
        print(f"\n💾 JSON salvo: {json_path.resolve()}")

    # Gerar Markdown
    if not args.json_only:
        gen = ReportGenerator(root, data)
        report = gen.generate()
        output_path = Path(args.output)
        output_path.write_text(report, encoding="utf-8")
        print(f"💾 Relatório salvo: {output_path.resolve()}")
        print(f"   Tamanho: {len(report.splitlines())} linhas")

    # Resumo final
    total_issues = (
        sum(len(v["issues"]) for v in views.values())
        + sum(len(m["issues"]) for m in models.values())
        + templates.get("total_issues", 0)
        + len(security.get("issues", []))
        + len(middleware.get("issues", []))
        + len(tests.get("issues", []))
        + sum(len(f["issues"]) for f in forms.values())
        + sum(len(a["issues"]) for a in admin.values())
        + sum(len(s["issues"]) for s in signals.values())
    )

    print(f"\n{'=' * 60}")
    print(f"📊 RESUMO FINAL: {total_issues} problema(s) encontrado(s)")
    print(f"   🔴 Críticos: {sev.get('critical', 0)}")
    print(f"   🟠 Altos: {sev.get('high', 0)}")
    print(f"   🟡 Médios: {sev.get('medium', 0)}")
    print(f"   🟢 Baixos: {sev.get('low', 0)}")
    if not tests.get("total_test_functions"):
        print(f"\n⚠️  ATENÇÃO: Zero testes — CRIE TESTES ANTES DE REFACTORAR!")
    if sev.get("critical", 0) > 0:
        print(f"\n🚨 ATENÇÃO: {sev.get('critical', 0)} problema(s) CRÍTICO(S) de segurança!")
    print()


if __name__ == "__main__":
    main()