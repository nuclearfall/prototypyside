# trace_deps_runtime.py
# Usage:  python trace_deps_runtime.py path/to/your_main.py [args...]
import sys, runpy, builtins, importlib.util, importlib.metadata as im, pathlib

# stdlib names (3.10+). If on older Python, fall back to an allowlist/file.
STDLIB = set(getattr(sys, "stdlib_module_names", ()))

seen_mods = set()
seen_top = set()
orig_import = builtins.__import__

def top_name(modname: str) -> str:
    return modname.split(".", 1)[0]

def logging_import(name, globals=None, locals=None, fromlist=(), level=0):
    mod = orig_import(name, globals, locals, fromlist, level)
    # record base package for the newly imported module and any fromlist children
    names = {name, *(f"{name}.{x}" for x in fromlist or [])}
    for n in names:
        t = top_name(n)
        if t and t not in STDLIB:
            seen_mods.add(n)
            seen_top.add(t)
    return mod

def module_to_dist(modname: str) -> str | None:
    """Map top-level module to its installed distribution."""
    # 1) quick mapping
    pd = im.packages_distributions()
    for key in (modname, modname.replace("-", "_")):
        dists = pd.get(key)
        if dists:
            return sorted(dists)[0]
    # 2) path-based fallback
    try:
        spec = importlib.util.find_spec(modname)
    except Exception:
        spec = None
    if spec and spec.origin:
        origin = pathlib.Path(spec.origin).resolve()
        for dist in im.distributions():
            try:
                files = dist.files or ()
                for f in files:
                    p = (pathlib.Path(dist.locate_file(f))).resolve()
                    if origin.is_relative_to(p.parent):  # heuristic
                        return dist.metadata["Name"]
            except Exception:
                pass
    return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python trace_deps_runtime.py <script.py> [args...]")
        sys.exit(2)
    script, *args = sys.argv[1:]
    sys.argv = [script, *args]
    builtins.__import__ = logging_import
    try:
        runpy.run_path(script, run_name="__main__")
    finally:
        builtins.__import__ = orig_import

    dists = {module_to_dist(t) or t for t in seen_top}
    # Filter Nones and stdlib
    dists = sorted(x for x in dists if x and x not in STDLIB)

    print("\n=== Top-level imported modules ===")
    for t in sorted(seen_top):
        print(t)
    print("\n=== Distributions used at runtime ===")
    for d in dists:
        print(d)

if __name__ == "__main__":
    main()
