# ReDNA Testing Guide

**Last Updated:** 2025-10-04

Complete guide for running tests, interpreting results, and integrating with CI/CD.

---

## 🎯 Quick Start

```bash
# Run all tests (requires user confirmation if WRITE_PROTECT not set)
./scripts/run_tests.sh

# Quick mode (skip slow integration tests)
./scripts/run_tests.sh --quick

# Force safe mode (no disk writes)
./scripts/run_tests.sh --write-protect

# Run specific test file
python3 -m pytest ExplorerFinal/tests/test_nudge_store.py -v

# Run golden path regression only
python3 scripts/golden_path_test.py
```

---

## 📦 Test Suite Overview

| Test Suite | File | Test Count | Purpose |
|------------|------|------------|---------|
| **Nudge Store** | `ExplorerFinal/tests/test_nudge_store.py` | 30+ | CRUD, TTL, cohorts, feedback |
| **RR Baselines** | `ExplorerDev/tests/test_rr_baseline_utils.py` | 20+ | Recalculation, validation, I/O |
| **CReDNA Ops** | `ExplorerDev/tests/test_credna_ops.py` | 25+ | Import/export, versioning, rollback |
| **Golden Path** | `scripts/golden_path_test.py` | 2 workflows | End-to-end regression |
| **Total** | | **75+** | |

---

## 🔧 Environment Setup

### Prerequisites

```bash
# Ensure Python 3.9+
python3 --version

# Install test dependencies
pip install pytest pytest-cov pyyaml

# Optional: Install all dev dependencies
pip install -r requirements-dev.txt
```

### Environment Variables

```bash
# CRITICAL: Set write protection for safe testing
export WRITE_PROTECT=true

# Optional: Control test verbosity
export PYTEST_VERBOSITY=2

# Optional: Holistic scheduler (disable during tests)
export HOLISTIC_SCHEDULER_ENABLED=false
```

---

## 📋 Test Categories

### 1. Nudge Store Tests

**File:** [ExplorerFinal/tests/test_nudge_store.py](../ExplorerFinal/tests/test_nudge_store.py)

**Coverage:**
- ✅ CRUD operations (add, list, accept, dismiss, undo)
- ✅ TTL functionality (expiry, auto-dismissal)
- ✅ Cohort management (A/B testing)
- ✅ Ops scheduling (cron-like schedules)
- ✅ Rate limiting
- ✅ Feedback logging and aggregation
- ✅ Write-protect mode
- ✅ Export (CSV/JSON)
- ✅ Bundle hashing and deduplication

**Run:**
```bash
pytest ExplorerFinal/tests/test_nudge_store.py -v
```

**Example Output:**
```
test_nudge_store.py::TestNudgeStoreCRUD::test_add_bundle_success PASSED
test_nudge_store.py::TestNudgeStoreCRUD::test_add_duplicate_bundle_rejected PASSED
test_nudge_store.py::TestNudgeTTL::test_expired_nudge_marked_expired PASSED
...
====== 30 passed in 2.45s ======
```

---

### 2. RR Baseline Utilities Tests

**File:** [ExplorerDev/tests/test_rr_baseline_utils.py](../ExplorerDev/tests/test_rr_baseline_utils.py)

**Coverage:**
- ✅ Loading canonical baselines from Core
- ✅ Demo configuration management
- ✅ Validation (ranges, types)
- ✅ Cascade resolution logic
- ✅ Effective baseline computation
- ✅ Save/load operations with backups
- ✅ Change logging
- ✅ CSV export
- ✅ Preflight import validation

**Run:**
```bash
pytest ExplorerDev/tests/test_rr_baseline_utils.py -v
```

---

### 3. CReDNA Ops Tests

**File:** [ExplorerDev/tests/test_credna_ops.py](../ExplorerDev/tests/test_credna_ops.py)

**Coverage:**
- ✅ Coach listing and retrieval
- ✅ Trait iteration
- ✅ Persona resolution
- ✅ Template retrieval with fallback
- ✅ Coverage computation
- ✅ Curiosity calculation
- ✅ Store operations (save/load)
- ✅ Versioning and provenance
- ✅ Automatic backups
- ✅ Gap detection
- ✅ Write protection
- ✅ Import/export

**Run:**
```bash
pytest ExplorerDev/tests/test_credna_ops.py -v
```

---

### 4. Golden Path Regression

**File:** [scripts/golden_path_test.py](../scripts/golden_path_test.py)

**Workflow 1: Nudge Lifecycle**
1. Enqueue a test nudge
2. Verify nudge appears in inbox
3. Accept the nudge
4. Verify nudge status changed to 'accepted'
5. Verify entries in Draft Chat
6. Undo the acceptance
7. Verify nudge back in inbox
8. Verify Draft Chat entries removed
9. Cleanup - dismiss test nudge

**Workflow 2: Feedback**
1. Create test nudge
2. Log helpful feedback
3. Log not_helpful feedback
4. Load feedback entries
5. Load feedback aggregates
6. Verify scores calculated correctly

**Run:**
```bash
python3 scripts/golden_path_test.py
```

**Example Output:**
```
═══════════════════════════════════════════════════
Golden Path Test: Enqueue → Accept → Undo → Draft Chat
═══════════════════════════════════════════════════

[Step 1] Enqueue a test nudge
✓ Nudge enqueued: nudge_2025-10-04T12-34-56_a1b2

[Step 2] Verify nudge appears in inbox
✓ Nudge found in inbox (status: inbox)

...

All tests PASSED ✓
```

---

## 🧪 Running Tests

### All Tests (Recommended)

```bash
./scripts/run_tests.sh
```

This runs:
1. Nudge store tests
2. RR baseline tests
3. CReDNA ops tests
4. Golden path regression
5. (Optional) Existing Core integration tests
6. (Optional) Existing Explorer integration tests

### Quick Mode (Skip Slow Tests)

```bash
./scripts/run_tests.sh --quick
```

Skips Core and Explorer integration tests, runs only new test suites (~10 seconds).

### Write-Protected Mode (Dry Run)

```bash
./scripts/run_tests.sh --write-protect
```

Forces `WRITE_PROTECT=true`, no disk writes. Safe for production systems.

### Single Test Class

```bash
pytest ExplorerFinal/tests/test_nudge_store.py::TestNudgeStoreCRUD -v
```

### Single Test Method

```bash
pytest ExplorerFinal/tests/test_nudge_store.py::TestNudgeStoreCRUD::test_add_bundle_success -v
```

### With Coverage

```bash
pytest ExplorerFinal/tests/test_nudge_store.py --cov=ExplorerFinal.core.nudge_store --cov-report=html
```

View coverage: `open htmlcov/index.html`

---

## 🚦 Interpreting Results

### Success

```
====== 30 passed in 2.45s ======
```

All tests passed. Safe to proceed.

### Failure

```
FAILED test_nudge_store.py::TestNudgeStoreCRUD::test_add_bundle_success
```

**Action:**
1. Check error message for details
2. Run with `-vv` for more verbosity
3. Run with `--tb=long` for full traceback
4. Fix issue and re-run

### Write-Protect Warning

```
⚠ WRITE_PROTECT not set (defaulting to false)
⚠ Tests will modify disk state!
Continue? (y/N)
```

**Action:** Press `N` and set `WRITE_PROTECT=true` or accept risk.

---

## 🔄 CI/CD Integration

### GitHub Actions Example

```yaml
name: ReDNA Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'

    - name: Install dependencies
      run: |
        pip install pytest pyyaml

    - name: Run tests (write-protected)
      env:
        WRITE_PROTECT: true
      run: |
        ./scripts/run_tests.sh --quick
```

### Exit Codes

- `0`: All tests passed
- `1`: One or more tests failed
- `2`: Test collection error

---

## 📊 Test Data Management

### Temporary Data

Tests use `tempfile.TemporaryDirectory()` for isolation:

```python
@pytest.fixture
def temp_data_dir(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        # Override paths for testing
        monkeypatch.setattr(nudge_store, "MAILBOX_ROOT", Path(tmpdir) / "mailbox")
        yield tmpdir
    # Auto-cleanup on exit
```

**Benefits:**
- ✅ No pollution of real data
- ✅ Automatic cleanup
- ✅ Parallel test execution safe

### Write-Protect Mode

When `WRITE_PROTECT=true`:
- All writes go to in-memory caches
- No files created/modified
- State resets between tests

**Usage:**
```python
result = nudge_store.add_bundle(user_id, payload, write_protect=True)
# Result returned but nothing written to disk
```

---

## 🐛 Debugging Failed Tests

### Increase Verbosity

```bash
pytest ExplorerFinal/tests/test_nudge_store.py -vv --tb=long
```

### Run Single Failing Test

```bash
pytest ExplorerFinal/tests/test_nudge_store.py::TestNudgeTTL::test_expired_nudge_marked_expired -vv
```

### Use Print Debugging

```python
def test_something(temp_data_dir):
    result = do_thing()
    print(f"DEBUG: result = {result}")  # Will show in pytest output with -s
    assert result["ok"]
```

Run with `-s` to see prints:
```bash
pytest test_file.py::test_something -s
```

### Use PDB

```python
def test_something():
    result = do_thing()
    import pdb; pdb.set_trace()  # Breakpoint
    assert result["ok"]
```

### Check Logs

```bash
# Check test execution logs
tail -f data/dev_logs/trace_devexp.jsonl

# Check nudge action logs
tail -f data/dev_logs/nudge_actions.jsonl
```

---

## 📝 Writing New Tests

### Test Structure

```python
import pytest
from module import function_to_test

@pytest.fixture
def sample_data():
    """Fixture providing test data."""
    return {"key": "value"}

def test_function_success(sample_data):
    """Test successful case with descriptive name."""
    result = function_to_test(sample_data)

    assert result["ok"] is True
    assert result["value"] == "expected"

def test_function_failure():
    """Test failure case."""
    with pytest.raises(ValueError, match="Invalid input"):
        function_to_test(None)
```

### Best Practices

1. **One assertion concept per test** - Test one thing at a time
2. **Descriptive names** - `test_add_bundle_with_invalid_ttl_raises_error`
3. **Use fixtures** - Share setup code cleanly
4. **Test edge cases** - Empty lists, None values, negative numbers
5. **Test error paths** - Not just happy path
6. **Clean up** - Use temp directories or write_protect mode
7. **Document why** - Comments explaining non-obvious assertions

---

## 🎯 Coverage Goals

Target coverage by module:

| Module | Target | Current |
|--------|--------|---------|
| `nudge_store.py` | 85% | ~90% |
| `rr_baseline_utils.py` | 80% | ~85% |
| `credna_ops.py` | 75% | ~80% |
| Overall | 80% | ~85% |

**Check coverage:**
```bash
pytest --cov=ExplorerFinal.core --cov=ExplorerDev --cov-report=term-missing
```

---

## 🔐 Pre-Demo Checklist

Before running demos with `WRITE_PROTECT=false`:

```bash
# 1. Run full test suite
./scripts/run_tests.sh

# 2. Run golden path specifically
python3 scripts/golden_path_test.py

# 3. Verify all pass
# Exit code should be 0

# 4. Create backup
./quick_backup_to_icloud.sh

# 5. Set WRITE_PROTECT appropriately
export WRITE_PROTECT=false  # Only if you want persistence

# 6. Run demo
# ...

# 7. Re-enable protection after demo
export WRITE_PROTECT=true
```

---

## 📞 Troubleshooting

### Import Errors

```
ModuleNotFoundError: No module named 'ExplorerFinal'
```

**Fix:** Run from repo root
```bash
cd /Users/davidmakarewicz/Documents/ReDNA_Demos
pytest ExplorerFinal/tests/test_nudge_store.py
```

### Permission Errors

```
PermissionError: write-protected
```

**Fix:** Set `WRITE_PROTECT=false` or use in-memory mode

### Fixture Errors

```
fixture 'temp_data_dir' not found
```

**Fix:** Ensure fixture is defined in same file or `conftest.py`

---

## 📚 Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Coverage.py Guide](https://coverage.readthedocs.io/)
- [Golden Path Test Source](../scripts/golden_path_test.py)
- [Rollback Procedures](./Rollback_Procedures.md)

---

**End of Testing Guide**
