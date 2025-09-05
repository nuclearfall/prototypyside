# valid_path.py
from __future__ import annotations

from os import fspath
from pathlib import Path
from typing import Callable, Optional, TypeVar, Union, Iterable

T = TypeVar("T")
Predicate = Callable[[Path], bool]
Transform = Callable[[Path], T]


class ValidPath:
    """Single-entry path validator: compose common checks with simple flags."""

    # -------- Internals --------
    @staticmethod
    def _to_path(pathlike: Union[str, Path]) -> Optional[Path]:
        """Convert to Path without leaking exceptions to callers."""
        try:
            return pathlike if isinstance(pathlike, Path) else Path(fspath(pathlike))
        except Exception:
            return None

    @staticmethod
    def _normalize(p: Path) -> Path:
        """Expand '~' and resolve to absolute path (non-strict)."""
        return p.expanduser().resolve()

    # -------- Predicates --------
    exists: Predicate   = staticmethod(lambda p: p.exists())
    is_file: Predicate  = staticmethod(lambda p: p.is_file())  # implies existence
    is_dir: Predicate   = staticmethod(lambda p: p.is_dir())

    @staticmethod
    def has_ext(ext: str) -> Predicate:
        """Match single last suffix, e.g. '.pdf' or 'pdf'."""
        want = ext if ext.startswith(".") else "." + ext
        want = want.lower()
        return lambda p: p.suffix.lower() == want

    @staticmethod
    def has_any_ext(exts: list[str]) -> Predicate:
        """Match any of the given last-suffix extensions."""
        canon = [(e if e.startswith(".") else "." + e).lower() for e in exts]
        return lambda p: p.suffix.lower() in canon

    @staticmethod
    def has_suffixes(suffixes: list[str]) -> Predicate:
        """Match the *full* suffix chain exactly, e.g. ['.tar', '.gz']."""
        want = [(s if s.startswith(".") else "." + s).lower() for s in suffixes]
        return lambda p: [s.lower() for s in p.suffixes] == want

    # -------- Core API --------
    @classmethod
    def check(
        cls,
        pathlike: Union[str, Path],
        *,
        must_exist: bool = False,
        require_file: bool = False,
        require_dir: bool = False,
        has_ext: Optional[Union[str, list[str]]] = None,
        normalize: bool = False,
        transform: Transform[Union[Path, str]] = lambda p: p,
    ) -> Optional[Union[Path, str]]:
        """
        Validate and optionally normalize/transform a path-like input.

        - must_exist: require that the path exists
        - require_file / require_dir: require file or directory (mutually exclusive)
        - has_ext: a str ('.pdf' or 'pdf') or list of allowable extensions
        - normalize: expand ~ and resolve() (non-strict) before transform
        - transform: final mapping (default: identity)
        """
        p = cls._to_path(pathlike)
        if not p:
            return None

        if normalize:
            p = cls._normalize(p)

        preds: list[Predicate] = []
        if must_exist:
            preds.append(cls.exists)
        if require_file:
            preds.append(cls.is_file)
        if require_dir:
            preds.append(cls.is_dir)
        if has_ext is not None:
            preds.append(
                cls.has_any_ext(has_ext) if isinstance(has_ext, list) else cls.has_ext(has_ext)
            )

        return (all(pred(p) for pred in preds) and transform(p)) or None

    @classmethod
    def file(
        cls,
        pathlike: Union[str, Path],
        *,
        must_exist: bool = False,
        ext: Optional[Union[str, list[str]]] = None,
        return_stem: bool = False,
        dotfiles_as_name: bool = True,
        normalize: bool = False,
    ) -> Optional[Union[Path, str]]:
        """
        Convenience: validate a file (optionally must exist and/or match extension).
        - If must_exist=True, uses is_file() (which implies existence).
        - If return_stem=True, returns stem (for dotfiles with no suffix, returns name[1:] if dotfiles_as_name).
        """
        # Build checks
        preds: list[Predicate] = []
        if must_exist:
            preds.append(cls.is_file)  # single syscall, implies existence
        if ext is not None:
            preds.append(cls.has_any_ext(ext) if isinstance(ext, list) else cls.has_ext(ext))

        # Transform
        if return_stem:
            def to_stem(p: Path) -> str:
                if dotfiles_as_name and p.name.startswith(".") and not p.suffix:
                    return p.name[1:]
                return p.stem
            transform: Transform[Union[Path, str]] = to_stem
        else:
            transform = lambda p: p

        return cls.check(pathlike, normalize=normalize, transform=transform, **{
            # only add checks if requested
            "must_exist": must_exist,
            "require_file": must_exist,  # is_file implies existence only when must_exist is True
            "has_ext": ext,
        })