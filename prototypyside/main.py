#!/usr/bin/env python3
import sys
import argparse
import json
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication

from prototypyside.views.main_window import MainDesignerWindow
from prototypyside.services.proto_class import ProtoClass
from prototypyside.utils.valid_path import ValidPath  # <-- uses your one-stop validator

if TYPE_CHECKING:
    from pathlib import Path

pc = ProtoClass
# --- Helpers ---------------------------------------------------------------

def _norm(p):
    """Normalize a Path: expand ~ and resolve to absolute (non-strict)."""
    return p.expanduser().resolve()

def _die(msg: str, code: int = 2):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(code)

def _ensure_pdf_path(path_like) -> "Path":
    """
    Ensure the given path-like is (or will be) a PDF path.
    We don't require existence here because we're about to create it.
    """
    p = ValidPath.check(path_like, has_ext="pdf", transform=_norm)
    if p is None:
        _die(f"invalid PDF path: {path_like}")
    return p


# --- Argparse --------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="pts",
        description="Prototypyside CLI/GUI runner"
    )
    # Headless toggle (don’t use -h because argparse reserves it for help)
    p.add_argument("--headless", "-H", action="store_true", dest="is_headless",
                   help="Run without GUI (requires --export)")

    # Export target
    p.add_argument("--export", "-e", dest="export_path",
                   help="Directory (for CT PNGs) or file/dir (for LT PDFs)")

    # All templates go here
    p.add_argument("templates", nargs="*", help="template files (JSON)")

    # Bleed toggle for CTs
    p.add_argument("--bleed", "-b", action="store_true", dest="include_bleed",
                   help="Include bleed on ComponentTemplate exports")

    return p


# --- Type predicates delegated to MainDesignerWindow when available --------

def _is_ct(obj, mw: MainDesignerWindow) -> bool:
    fn = getattr(mw, "_is_component_template", None)
    if callable(fn):
        return fn(obj)
    # Fallback: loose heuristics
    return pc.isproto(obj, pc.CT)

def _is_lt(obj, mw: MainDesignerWindow) -> bool:
    fn = getattr(mw, "_is_layout_template", None)
    if callable(fn):
        return fn(obj)
    # Fallback: loose heuristics
    return pc.isproto(obj, pc.LT)


# --- Main ------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    parser = build_parser()
    args = parser.parse_args()
    pc = ProtoClass  # retained for any downstream use

    # Normalize and validate templates list: must exist & be files
    template_paths: list["Path"] = []
    if args.templates:
        for s in args.templates:
            p = ValidPath.check(s, must_exist=True, require_file=True, transform=_norm)
            if p is None:
                _die(f"template does not exist or is not a file: {s}")
            template_paths.append(p)

    # GUI MODE ---------------------------------------------------------------
    if not args.is_headless:
        mw = MainDesignerWindow(init_tabs=template_paths if template_paths else None, is_headless=False)
        mw.show()
        return app.exec()

    # HEADLESS MODE ----------------------------------------------------------
    if not args.export_path:
        _die("Headless mode requires --export")

    # Export path can be file or directory depending on LT/CT handling below.
    ep = ValidPath.check(args.export_path, transform=_norm)
    if ep is None:
        _die(f"invalid export path: {args.export_path}")

    if not template_paths:
        _die("Headless mode requires at least one template via --templates")

    mw = MainDesignerWindow(init_tabs=False)
    mw.is_headless = True

    # Load all templates; split into CT/LT buckets
    ct_templates = []
    lt_templates = []
    for path in template_paths:
        tmpl = mw.open_template(path=path)
        if _is_ct(tmpl, mw):
            # Apply bleed flag to CTs
            tmpl.include_bleed = bool(args.include_bleed)
            ct_templates.append(tmpl)
        elif _is_lt(tmpl, mw):
            lt_templates.append(tmpl)
        else:
            _die(f"Unknown template type: {path}")

if __name__ == "__main__":
    sys.exit(main())
