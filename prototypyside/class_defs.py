import re
import os
import ast
from pathlib import Path

def find_classes_in_file(file_path):
    """Return a list of (class_name, file_path) tuples from a Python file."""
    classes = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            file_content = f.read()
        tree = ast.parse(file_content, filename=file_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append((node.name, file_path))
    except Exception as e:
        print(f"Failed to parse {file_path}: {e}")
    return classes

def find_all_classes(root_dir):
    """Recursively scan root_dir for Python files and collect all class definitions."""
    all_classes = []
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".py"):
                file_path = os.path.join(dirpath, filename)
                all_classes.extend(find_classes_in_file(file_path))
    return all_classes

def generate_prefix_for_classname(name: str, maxlen: int = 3) -> str:
    """Generate a lowercase prefix from the class name, without special casing."""
    name = re.sub(r'[^a-z]', '', name.lower())
    return name[:maxlen]

def generate_unique_prefixes(classes, maxlen=3):
    """Generate a unique prefix for each class."""
    prefix_map = {}
    used = set()

    for class_name, _ in classes:
        base = generate_prefix_for_classname(class_name, maxlen)
        candidate = base
        i = 1
        while candidate in used:
            candidate = f"{base[:maxlen-1]}{i}"
            i += 1
        prefix_map[candidate] = class_name
        used.add(candidate)

    return prefix_map

def write_prefix_map_to_file(prefix_map, output_path="output.txt"):
    """Write the prefix map to a file as nicely formatted text."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Auto-generated prefix map\n")
        f.write("PREFIXES = {\n")
        for prefix, clsname in sorted(prefix_map.items()):
            f.write(f"    \"{prefix}\": \"{clsname}\",\n")
        f.write("}\n")

if __name__ == "__main__":
    root = Path(__file__).parent  # or specify your project root here
    all_classes = find_all_classes(root)
    prefix_map = generate_unique_prefixes(all_classes)
    write_prefix_map_to_file(prefix_map)
    print(f"Wrote {len(prefix_map)} class prefixes to output.txt")
