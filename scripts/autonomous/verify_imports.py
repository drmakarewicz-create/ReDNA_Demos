#!/usr/bin/env python3
"""
Import Verification Script

Checks for common import issues:
- Missing dependencies
- Circular imports
- Orphaned modules
- Syntax errors
"""

import os
import sys
import ast
import importlib.util
from pathlib import Path
from typing import List, Tuple, Set
import subprocess

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = PROJECT_ROOT / "ReDNACoreDemo" / "core"

def check_syntax(file_path: Path) -> Tuple[bool, str]:
    """Check if a Python file has valid syntax."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        return True, ""
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)

def get_imports(file_path: Path) -> Set[str]:
    """Extract all imports from a Python file."""
    imports = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
    except:
        pass

    return imports

def find_python_files(directory: Path) -> List[Path]:
    """Find all Python files in directory."""
    return list(directory.rglob("*.py"))

def main():
    print("🔍 Import Verification Report\n")
    print("=" * 60)

    issues_found = 0

    # 1. Syntax Check
    print("\n📝 Checking Python syntax...")
    syntax_errors = []

    for py_file in find_python_files(CORE_DIR):
        if "__pycache__" in str(py_file):
            continue

        valid, error = check_syntax(py_file)
        if not valid:
            relative_path = py_file.relative_to(PROJECT_ROOT)
            syntax_errors.append((relative_path, error))
            issues_found += 1

    if syntax_errors:
        print(f"  ❌ Found {len(syntax_errors)} syntax errors:")
        for path, error in syntax_errors[:10]:
            print(f"     {path}: {error}")
    else:
        print("  ✅ All files have valid syntax")

    # 2. Import Test
    print("\n🐍 Testing critical imports...")

    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT / "ReDNACoreDemo"))

    critical_imports = [
        "ReDNACoreDemo.core.api",
        "ReDNACoreDemo.core.storage",
        "ReDNACoreDemo.core.policy",
        "ReDNACoreDemo.core.hc_orchestrator",
        "ReDNACoreDemo.core.hc_learning",
    ]

    import_failures = []
    for module_name in critical_imports:
        try:
            __import__(module_name)
            print(f"  ✅ {module_name}")
        except Exception as e:
            print(f"  ❌ {module_name}: {str(e)[:60]}")
            import_failures.append((module_name, str(e)))
            issues_found += 1

    # 3. Cyclic Dependency Check (simple)
    print("\n🔄 Checking for potential circular imports...")

    # This is a simple heuristic - real cycle detection would require graph analysis
    core_files = find_python_files(CORE_DIR)
    mutual_imports = []

    for file_a in core_files:
        if "__pycache__" in str(file_a) or "test_" in file_a.name:
            continue

        imports_a = get_imports(file_a)
        module_a_name = file_a.stem

        for file_b in core_files:
            if file_a >= file_b or "__pycache__" in str(file_b):
                continue

            imports_b = get_imports(file_b)
            module_b_name = file_b.stem

            if module_b_name in imports_a and module_a_name in imports_b:
                mutual_imports.append((file_a.name, file_b.name))

    if mutual_imports:
        print(f"  ⚠️  Found {len(mutual_imports)} potential mutual imports:")
        for a, b in mutual_imports[:5]:
            print(f"     {a} ↔ {b}")
    else:
        print("  ✅ No obvious circular imports detected")

    # 4. Check for orphaned modules
    print("\n🗑️  Checking for potentially orphaned modules...")

    # Check if there are any .py files that aren't imported anywhere
    all_modules = {f.stem for f in find_python_files(CORE_DIR) if f.stem != "__init__"}
    imported_modules = set()

    for py_file in find_python_files(CORE_DIR):
        imported_modules.update(get_imports(py_file))

    potentially_orphaned = all_modules - imported_modules
    # Filter out common patterns that are okay to be "orphaned"
    potentially_orphaned = {m for m in potentially_orphaned
                           if not m.startswith('test_')
                           and m != 'api'
                           and m != 'ui_readonly'}

    if potentially_orphaned:
        print(f"  ℹ️  {len(potentially_orphaned)} modules not imported within core/")
        for mod in list(potentially_orphaned)[:10]:
            print(f"     - {mod}.py")
    else:
        print("  ✅ All modules are referenced")

    # Summary
    print("\n" + "=" * 60)
    print(f"\n📊 Summary: {issues_found} critical issues found\n")

    if issues_found == 0:
        print("✅ All import checks passed!")
        return 0
    else:
        print("⚠️  Some issues detected - review output above")
        return 1

if __name__ == "__main__":
    sys.exit(main())
