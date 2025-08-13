#!/usr/bin/env python3
"""
Install Git hooks for automatic code quality checks.

This script sets up pre-commit hooks that run the same checks as GitHub Actions,
preventing CI failures by catching issues locally.
"""

import os
import stat
import subprocess
import sys
from pathlib import Path


def install_pre_commit_hook():
    """Install Git pre-commit hook."""
    git_dir = Path(".git")
    if not git_dir.exists():
        print("❌ Not a Git repository. Run this from the project root.")
        return False
    
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    
    hook_file = hooks_dir / "pre-commit"
    
    # Pre-commit hook script
    hook_content = '''#!/bin/bash
# Auto-generated pre-commit hook for code quality checks
# This runs fast local checks before commit

echo "🔍 Running pre-commit code quality checks..."

# Run fast local CI checks (formatting, syntax, imports)
python scripts/ci-checks.py --fix

# Capture exit code
exit_code=$?

if [ $exit_code -ne 0 ]; then
    echo ""
    echo "💥 Pre-commit checks failed!"
    echo "Fix the issues above before committing."
    echo ""
    echo "💡 To run full CI simulation:"
    echo "  python scripts/local-ci.py --ci"
    echo ""
    echo "To skip these checks (not recommended):"
    echo "  git commit --no-verify"
    echo ""
    exit 1
fi

echo "✅ All pre-commit checks passed!"
echo "💡 Run 'python scripts/local-ci.py --ci' for full CI simulation"
exit 0
'''
    
    # Write hook file
    with open(hook_file, 'w') as f:
        f.write(hook_content)
    
    # Make executable
    hook_file.chmod(hook_file.stat().st_mode | stat.S_IEXEC)
    
    print(f"✅ Pre-commit hook installed: {hook_file}")
    return True


def install_pre_push_hook():
    """Install Git pre-push hook for additional checks."""
    git_dir = Path(".git")
    hooks_dir = git_dir / "hooks"
    hook_file = hooks_dir / "pre-push"
    
    # Pre-push hook script (comprehensive CI simulation)
    hook_content = '''#!/bin/bash
# Auto-generated pre-push hook for comprehensive CI checks
# This runs full CI simulation using nektos/act before pushing

echo "🚀 Running pre-push CI simulation..."

# Check if act is available for full CI simulation
if command -v act >/dev/null 2>&1; then
    echo "🤖 Running full CI pipeline with act..."
    python scripts/local-ci.py --ci
    ci_exit_code=$?
    
    if [ $ci_exit_code -ne 0 ]; then
        echo ""
        echo "❌ CI simulation failed!"
        echo "Your push will likely fail in GitHub Actions."
        echo "Fix issues above before pushing."
        echo ""
        echo "To skip CI simulation (not recommended):"
        echo "  git push --no-verify"
        echo ""
        exit 1
    fi
    
    echo "✅ CI simulation passed!"
else
    echo "⚠️  act not available, running basic checks..."
    python scripts/ci-checks.py --ci
    
    if [ $? -ne 0 ]; then
        echo ""
        echo "❌ Basic checks failed!"
        echo ""
        echo "💡 Install act for full CI simulation:"
        echo "  brew install act  # macOS"
        echo "  https://github.com/nektos/act#installation"
        echo ""
        exit 1
    fi
fi

# Show push information
branch=$(git rev-parse --abbrev-ref HEAD)
remote_branch="origin/$branch"

if git rev-parse --verify "$remote_branch" >/dev/null 2>&1; then
    ahead=$(git rev-list --count "$remote_branch..HEAD")
    if [ "$ahead" -gt 0 ]; then
        echo "📊 Pushing $ahead new commit(s) to $remote_branch"
    fi
fi

echo "✅ All pre-push checks passed! Your code should pass CI."
exit 0
'''
    
    # Write hook file
    with open(hook_file, 'w') as f:
        f.write(hook_content)
    
    # Make executable
    hook_file.chmod(hook_file.stat().st_mode | stat.S_IEXEC)
    
    print(f"✅ Pre-push hook installed: {hook_file}")
    return True


def create_makefile_shortcuts():
    """Create Makefile with common development shortcuts."""
    makefile_content = '''# Newsletter Bot Development Shortcuts

.PHONY: check fix test hooks clean dev help ci ci-full pr-check act-install

# Default target
help:
\t@echo "📋 Available commands:"
\t@echo "  make check      - Run fast code quality checks"
\t@echo "  make fix        - Auto-fix formatting issues" 
\t@echo "  make test       - Run test suite"
\t@echo "  make ci         - Run full CI simulation with act"
\t@echo "  make pr-check   - Simulate pull request checks"
\t@echo "  make hooks      - Install Git hooks"
\t@echo "  make clean      - Clean up generated files"
\t@echo "  make dev        - Set up development environment"
\t@echo "  make act-install - Show act installation instructions"

# Run fast code quality checks
check:
\t@echo "🔍 Running fast code quality checks..."
\tpython scripts/ci-checks.py

# Auto-fix formatting issues
fix:
\t@echo "🔧 Auto-fixing code formatting..."
\tpython scripts/ci-checks.py --fix

# Run tests
test:
\t@echo "🧪 Running test suite..."
\t@if [ -d "tests" ]; then pytest tests/ -v --tb=short; else echo "No tests directory found"; fi

# Run full CI simulation with nektos/act
ci:
\t@echo "🤖 Running full CI simulation..."
\tpython scripts/local-ci.py --ci

# Run comprehensive CI checks (fallback without act)
ci-basic:
\t@echo "🤖 Running basic CI checks..."
\tpython scripts/ci-checks.py --ci

# Simulate pull request checks
pr-check:
\t@echo "🔍 Simulating pull request checks..."
\tpython scripts/local-ci.py --pr

# Show act installation instructions
act-install:
\tpython scripts/local-ci.py --install-guide

# Install Git hooks
hooks:
\t@echo "⚙️  Installing Git hooks..."
\tpython scripts/install-hooks.py

# Clean up generated files
clean:
\t@echo "🧹 Cleaning up..."
\trm -f *.log *.json newsletter_draft.md .secrets
\tfind . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
\tfind . -type f -name "*.pyc" -delete 2>/dev/null || true

# Development environment setup
dev: hooks
\t@echo "🛠️  Setting up development environment..."
\tpip install -e ".[dev]"
\t@echo ""
\t@echo "🎯 Recommended: Install nektos/act for local CI simulation:"
\t@echo "  brew install act  # macOS"
\t@echo "  make act-install  # Show all installation options"
\t@echo ""
\t@echo "✅ Development environment ready!"
\t@echo ""
\t@echo "🚀 Quick commands:"
\t@echo "  make check     - Fast code quality checks"
\t@echo "  make fix       - Auto-fix formatting issues"
\t@echo "  make ci        - Full CI simulation (requires act)"
\t@echo "  make ci-basic  - Basic CI checks (no act required)"
\t@echo "  make test      - Run tests"

# Pre-commit simulation (what runs on git commit)
pre-commit:
\t@echo "🎯 Simulating pre-commit hook..."
\tpython scripts/ci-checks.py --fix

# Pre-push simulation (what runs on git push)
pre-push:
\t@echo "🚀 Simulating pre-push hook..."
\t@if command -v act >/dev/null 2>&1; then \
\t\tpython scripts/local-ci.py --ci; \
\telse \
\t\techo "⚠️  act not installed, running basic checks..."; \
\t\tpython scripts/ci-checks.py --ci; \
\tfi
'''
    
    with open("Makefile", "w") as f:
        f.write(makefile_content)
    
    print("✅ Makefile created with development shortcuts")


def main():
    """Install development tools and hooks."""
    print("🛠️  Installing development tools and Git hooks...")
    print("=" * 50)
    
    # Check if we're in project root
    if not Path("src/newsletter_bot.py").exists():
        print("❌ Please run this from the project root directory")
        sys.exit(1)
    
    success = True
    
    # Install hooks
    if install_pre_commit_hook():
        print("✅ Pre-commit hook installed")
    else:
        success = False
    
    if install_pre_push_hook():
        print("✅ Pre-push hook installed")
    else:
        success = False
    
    # Create Makefile shortcuts
    create_makefile_shortcuts()
    
    # Make scripts executable
    script_files = [
        "scripts/pre-commit-checks.py",
        "scripts/install-hooks.py"
    ]
    
    for script in script_files:
        script_path = Path(script)
        if script_path.exists():
            script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Git hooks and development tools installed successfully!")
        print("")
        print("📋 What was installed:")
        print("  • Pre-commit hook (runs on every commit)")
        print("  • Pre-push hook (runs before pushing)")
        print("  • Makefile with development shortcuts")
        print("  • Executable permissions on scripts")
        print("")
        print("🚀 Quick start:")
        print("  make dev     # Set up development environment")
        print("  make check   # Run code quality checks")
        print("  make fix     # Auto-fix formatting issues")
        print("")
        print("💡 The hooks will now automatically run on git commit/push")
        print("   and catch issues before they hit GitHub Actions!")
    else:
        print("❌ Some installations failed. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()