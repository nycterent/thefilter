# Testing Protocol

This document establishes our "test locally first" protocol to prevent broken CI builds.

## Root Cause of Previous Issues

1. **Environment Mismatch**: Local environment (Python 3.10, missing deps) ≠ CI environment (Python 3.11, full deps)
2. **Incomplete Local Testing**: Ran some tools (Black) but not others (flake8, isort)
3. **Assumed Success**: Pushed without running the full CI pipeline locally

## Testing Protocol

### Before Every Push:

**ALWAYS use venv** - Never run commands without the virtual environment!

1. **Run Full Linting Suite**:
   ```bash
   # Check all code quality tools that CI runs (using venv)
   ./venv/bin/black --check src/
   ./venv/bin/isort --check-only src/
   ./venv/bin/flake8 src/
   ```

2. **Fix Issues Immediately**:
   ```bash
   # Auto-fix formatting (using venv)
   ./venv/bin/black src/
   ./venv/bin/isort src/
   
   # Manually fix flake8 issues (unused imports, long lines, etc.)
   ./venv/bin/flake8 src/
   ```

3. **Re-run Linting After Fixes**:
   ```bash
   # Always re-run the full linting suite after auto-formatting or manual fixes
   ./venv/bin/black --check src/
   ./venv/bin/isort --check-only src/
   ./venv/bin/flake8 src/
   ```

4. **Run Tests**:
   ```bash
   # Run full test suite (using venv)
   ./venv/bin/pytest tests/ -v
   ```

**Note:**
- If Black reports files to reformat, always run Black and repeat the linting steps before running tests or pushing.
- This ensures code is always properly formatted and linted before tests and CI.

4. **Test Basic CLI Functionality**:
   ```bash
   # Verify CLI works (using venv)
   ./venv/bin/python -m src.newsletter_bot --help
   ./venv/bin/python -m src.newsletter_bot config
   ```

5. **Use the Test Script**:
   ```bash
   # Run our comprehensive local CI test
   ./scripts/test-ci.sh
   ```

4. **Only Push When All Local Tests Pass**

### Environment Setup:

**The venv is already set up and should always be used:**

```bash
# Install/update dependencies in venv
./venv/bin/pip install -e ".[dev]"

# All commands must use venv:
./venv/bin/black src/         # ✅ Correct
black src/                    # ❌ Wrong - uses system Python

./venv/bin/pytest tests/     # ✅ Correct  
pytest tests/                 # ❌ Wrong - different environment
```

## Commitment

**"No push without local success"** - If the local tools (that we can run) don't pass, we don't push.

This prevents the cycle of:
- Push → CI fails → Fix → Push → CI fails → Fix → Push

And replaces it with:
- Fix locally → Test locally → Push → CI passes ✅

## Exception Handling

If environment limitations prevent full local testing:
1. Run what we can (linting, formatting)
2. Make a smaller, focused commit
3. Push only after careful manual code review
4. Monitor CI closely and fix immediately if it fails

The key is **intentionality** - knowing what we're pushing and why we believe it will work.