#!/usr/bin/env python3
"""
Genera PROJECT_SNAPSHOT_AUDIT.txt — snapshot textual para Virtual Data Room / auditoría M&A.

Uso (desde la raíz del repositorio):

  python scripts/generate_audit_snapshot.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = REPO_ROOT / "PROJECT_SNAPSHOT_AUDIT.txt"

EXCLUDED_DIR_NAMES = frozenset(
    {
        "node_modules",
        ".git",
        ".venv",
        "__pycache__",
        "dist",
        "build",
        ".next",
    }
)

EXCLUDED_SUFFIXES = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".pdf",
        ".ico",
        ".bmp",
        ".tiff",
        ".tif",
        ".pyc",
        ".pyo",
        ".so",
        ".dylib",
        ".dll",
        ".exe",
        ".bin",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".otf",
        ".mp4",
        ".webm",
        ".zip",
        ".gz",
        ".7z",
        ".rar",
        ".mo",  # gettext binaries
    }
)

EXCLUDED_FILENAMES = frozenset(
    {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        ".env",
        ".env.local",
    }
)


def _path_has_excluded_segment(rel: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in rel.parts)


def _is_excluded_env_file(rel: Path) -> bool:
    n = rel.name.lower()
    if n.endswith(".env.example") or n.endswith("env.example"):
        return False
    if n in (".env", ".env.local"):
        return True
    if n.startswith(".env."):
        return True
    return False


def _should_skip_file(rel: Path) -> bool:
    if rel.name in EXCLUDED_FILENAMES:
        return True
    if _is_excluded_env_file(rel):
        return True
    if rel.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    if _path_has_excluded_segment(rel):
        return True
    return False


def collect_paths_from_tree(root: Path) -> list[Path]:
    out: list[Path] = []
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        try:
            rel = p.resolve().relative_to(REPO_ROOT)
        except ValueError:
            continue
        if _should_skip_file(rel):
            continue
        out.append(p)
    return out


def collect_strategic_files() -> list[Path]:
    candidates: list[Path] = []

    def add(p: Path) -> None:
        if p.is_file():
            candidates.append(p.resolve())

    # Documentación
    for name in ("SCRATCHPAD.md", "README_SECURITY.md"):
        add(REPO_ROOT / name)
    add(REPO_ROOT / "docs" / "DOSSIER_TECNICO_AB_LOGISTICS_OS.md")
    ops = REPO_ROOT / "docs" / "operations"
    candidates.extend(collect_paths_from_tree(ops))

    # Backend
    for sub in ("backend/app/core", "backend/app/services", "backend/app/api/v1"):
        candidates.extend(collect_paths_from_tree(REPO_ROOT / sub))
    add(REPO_ROOT / "backend" / "app" / "main.py")

    # Frontend
    add(REPO_ROOT / "frontend" / "src" / "lib" / "api.ts")
    for sub in ("frontend/src/i18n", "frontend/src/components/bi", "frontend/src/components/maps"):
        candidates.extend(collect_paths_from_tree(REPO_ROOT / sub))

    # Mobile
    add(REPO_ROOT / "mobile" / "src" / "services" / "sync_service.ts")

    # DB
    mig = REPO_ROOT / "supabase" / "migrations"
    if mig.is_dir():
        for p in sorted(mig.glob("*.sql")):
            if p.is_file():
                rel = p.resolve().relative_to(REPO_ROOT)
                if not _should_skip_file(rel):
                    candidates.append(p.resolve())

    # Dedupe + orden estable
    seen: set[str] = set()
    ordered: list[Path] = []
    for p in candidates:
        key = str(p)
        if key not in seen:
            seen.add(key)
            ordered.append(p)
    ordered.sort(key=lambda x: str(x.relative_to(REPO_ROOT)).replace("\\", "/"))
    return ordered


# Patrones de ofuscación (orden importa: más específicos primero)
_OBFUSCATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"-----BEGIN [A-Z0-9 ]+PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]+PRIVATE KEY-----"
        ),
        "[REDACTED_PEM_PRIVATE_KEY]",
    ),
    (
        re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{10,}\b"),
        "[REDACTED_STRIPE_SECRET]",
    ),
    (
        re.compile(r"\brk_(?:live|test)_[A-Za-z0-9]{10,}\b"),
        "[REDACTED_STRIPE_RESTRICTED]",
    ),
    (
        re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
        "[REDACTED_GOOGLE_API_KEY]",
    ),
    (
        re.compile(r"\bv-[A-Za-z0-9_-]{24,}\b"),
        "[REDACTED_V_PREFIX_TOKEN]",
    ),
    (
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[REDACTED_AWS_ACCESS_KEY_ID]",
    ),
    (
        re.compile(r"\bASIA[0-9A-Z]{16}\b"),
        "[REDACTED_AWS_STS_KEY_ID]",
    ),
    (
        re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
        "[REDACTED_GITHUB_TOKEN]",
    ),
    (
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
        "[REDACTED_SLACK_TOKEN]",
    ),
]


def obfuscate_secrets(text: str) -> str:
    out = text
    for pat, repl in _OBFUSCATION_PATTERNS:
        out = pat.sub(repl, out)
    return out


def read_text_safe(path: Path) -> str:
    raw = path.read_bytes()
    if b"\x00" in raw[:8192]:
        return "[SKIPPED_BINARY_DETECTED]\n"
    for enc in ("utf-8", "utf-8-sig"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def main() -> int:
    paths = collect_strategic_files()
    if not paths:
        print("No se encontraron archivos para el snapshot.", file=sys.stderr)
        return 1

    rel_strs = [str(p.relative_to(REPO_ROOT)).replace("\\", "/") for p in paths]

    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("PROJECT SNAPSHOT — TECHNICAL AUDIT (Virtual Data Room)")
    lines.append(f"Raíz del repositorio: {REPO_ROOT}")
    lines.append(f"Total de archivos: {len(paths)}")
    lines.append("=" * 72)
    lines.append("")
    lines.append("ÍNDICE DE ARCHIVOS")
    lines.append("-" * 72)
    for i, r in enumerate(rel_strs, start=1):
        lines.append(f"{i:4d}. {r}")
    lines.append("")
    lines.append("=" * 72)
    lines.append("")

    for p in paths:
        rel = str(p.relative_to(REPO_ROOT)).replace("\\", "/")
        lines.append(f"--- FILE: {rel} ---")
        lines.append("")
        body = read_text_safe(p)
        body = obfuscate_secrets(body)
        if not body.endswith("\n"):
            body += "\n"
        lines.append(body)
        lines.append("")

    OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"Escrito: {OUTPUT_FILE} ({len(paths)} archivos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
