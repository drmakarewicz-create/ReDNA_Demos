#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import importlib

importlib.import_module("ReDNACoreDemo.core.resolver")
importlib.import_module("ReDNACoreDemo.core.resolver.impl")
print("resolver imports OK")
PY
