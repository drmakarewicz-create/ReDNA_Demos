import pathlib
import re


def test_no_absolute_core_imports():
    root = pathlib.Path("ReDNACoreDemo/core")
    bad_paths: list[str] = []
    pattern = re.compile(r"(?<!\.)\b(from|import)\s+core\.")

    for path in root.rglob("*.py"):
        if ".bak" in path.name:
            continue
        content = path.read_text(encoding="utf-8")
        if pattern.search(content):
            bad_paths.append(str(path))

    assert not bad_paths, f"Absolute 'core.' imports found: {bad_paths}"
