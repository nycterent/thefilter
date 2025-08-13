#!/usr/bin/env python3
"""
Pre-commit Code Quality Checks - Ensure code passes CI before pushing.

This script runs the same checks as GitHub Actions locally to prevent CI failures.
Run before committing to catch issues early.
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


class CodeQualityChecker:
    def __init__(self):
        self.failed_checks = []
        self.warnings = []
        
    def run_command(self, cmd: List[str], description: str, critical: bool = True) -> bool:
        """Run a command and track results."""
        print(f"🔍 {description}...")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
            
            if result.returncode == 0:
                print(f"✅ {description}: PASSED")
                return True
            else:
                print(f"❌ {description}: FAILED")
                print(f"   Command: {' '.join(cmd)}")
                if result.stdout:
                    print(f"   Output: {result.stdout.strip()}")
                if result.stderr:
                    print(f"   Error: {result.stderr.strip()}")
                
                if critical:
                    self.failed_checks.append((description, result.stdout or result.stderr))
                else:
                    self.warnings.append((description, result.stdout or result.stderr))
                    
                return False
                
        except FileNotFoundError:
            print(f"⚠️  {description}: SKIPPED (tool not installed)")
            self.warnings.append((description, "Tool not available"))
            return True
        except Exception as e:
            print(f"💥 {description}: ERROR ({str(e)})")
            if critical:
                self.failed_checks.append((description, str(e)))
            return False

    def check_black_formatting(self) -> bool:
        """Check if code is properly formatted with Black."""
        return self.run_command(
            ["black", "--check", "src/"], 
            "Black formatting check"
        )

    def fix_black_formatting(self) -> bool:
        """Auto-fix Black formatting issues."""
        print("🔧 Auto-fixing Black formatting...")
        result = subprocess.run(["black", "src/"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Black formatting applied")
            return True
        else:
            print(f"❌ Black formatting failed: {result.stderr}")
            return False

    def check_isort_imports(self) -> bool:
        """Check if imports are properly sorted."""
        return self.run_command(
            ["isort", "--check-only", "src/"], 
            "Import sorting check"
        )

    def fix_isort_imports(self) -> bool:
        """Auto-fix import sorting."""
        print("🔧 Auto-fixing import sorting...")
        result = subprocess.run(["isort", "src/"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Import sorting applied")
            return True
        else:
            print(f"❌ Import sorting failed: {result.stderr}")
            return False

    def check_flake8_critical(self) -> bool:
        """Check for critical flake8 errors (same as CI)."""
        return self.run_command([
            "flake8", "src/", 
            "--count", "--select=E9,F63,F7,F82", 
            "--show-source", "--statistics"
        ], "Critical lint errors (flake8)")

    def check_flake8_full(self) -> bool:
        """Run full flake8 check (non-critical)."""
        return self.run_command([
            "flake8", "src/", 
            "--count", "--exit-zero", "--max-complexity=10", 
            "--max-line-length=88", "--statistics"
        ], "Full lint check (flake8)", critical=False)

    def check_mypy_types(self) -> bool:
        """Run mypy type checking (if configured)."""
        # Check if mypy is configured
        if not Path("pyproject.toml").exists():
            print("⚠️  mypy: SKIPPED (no pyproject.toml)")
            return True
            
        return self.run_command(
            ["mypy", "src/"], 
            "Type checking (mypy)", 
            critical=False  # Currently disabled in CI
        )

    def check_pytest_tests(self) -> bool:
        """Run pytest (if tests exist)."""
        if not Path("tests").exists():
            print("⚠️  pytest: SKIPPED (no tests directory)")
            return True
            
        return self.run_command([
            "pytest", "tests/", "-v", "--tb=short"
        ], "Unit tests (pytest)", critical=False)

    def check_file_structure(self) -> bool:
        """Ensure required files exist."""
        required_files = [
            "src/newsletter_bot.py",
            "src/core/newsletter.py", 
            "src/models/settings.py",
            "pyproject.toml",
            "CLAUDE.md"
        ]
        
        missing_files = []
        for file_path in required_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
                
        if missing_files:
            print(f"❌ Missing required files: {', '.join(missing_files)}")
            self.failed_checks.append(("File structure", f"Missing: {missing_files}"))
            return False
        else:
            print("✅ File structure: All required files present")
            return True

    def check_python_syntax(self) -> bool:
        """Check Python syntax of all files."""
        python_files = list(Path("src").rglob("*.py"))
        syntax_errors = []
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    compile(f.read(), py_file, 'exec')
            except SyntaxError as e:
                syntax_errors.append(f"{py_file}:{e.lineno} - {e.msg}")
                
        if syntax_errors:
            print(f"❌ Python syntax errors found:")
            for error in syntax_errors:
                print(f"   {error}")
            self.failed_checks.append(("Python syntax", "\n".join(syntax_errors)))
            return False
        else:
            print("✅ Python syntax: All files valid")
            return True

    def check_import_cycles(self) -> bool:
        """Check for circular imports."""
        try:
            result = subprocess.run([
                sys.executable, "-c", 
                "import sys; sys.path.insert(0, 'src'); import src.newsletter_bot"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Import cycles: No circular imports detected")
                return True
            else:
                print(f"❌ Import cycles: {result.stderr}")
                self.failed_checks.append(("Import cycles", result.stderr))
                return False
                
        except Exception as e:
            print(f"⚠️  Import cycles: Could not check ({e})")
            return True

    def run_all_checks(self, auto_fix: bool = False) -> bool:
        """Run all code quality checks."""
        print("🚀 Running Pre-Commit Code Quality Checks")
        print("=" * 50)
        
        # Structure and syntax checks (must pass)
        critical_checks = [
            self.check_file_structure,
            self.check_python_syntax,
            self.check_import_cycles,
        ]
        
        # Formatting checks (can auto-fix)
        formatting_checks = [
            (self.check_black_formatting, self.fix_black_formatting),
            (self.check_isort_imports, self.fix_isort_imports),
        ]
        
        # Quality checks
        quality_checks = [
            self.check_flake8_critical,  # Critical - must pass
            self.check_flake8_full,      # Warning only
            self.check_mypy_types,       # Warning only  
            self.check_pytest_tests,     # Warning only
        ]
        
        # Run critical checks first
        print("\n📋 Critical Checks")
        print("-" * 20)
        critical_passed = all(check() for check in critical_checks)
        
        if not critical_passed:
            print("\n💥 Critical checks failed. Fix these issues first:")
            for desc, error in self.failed_checks:
                if desc in ["File structure", "Python syntax", "Import cycles"]:
                    print(f"  • {desc}: {error}")
            return False
        
        # Run formatting checks with auto-fix option
        print("\n🎨 Formatting Checks")
        print("-" * 20)
        formatting_passed = True
        
        for check_func, fix_func in formatting_checks:
            if not check_func():
                formatting_passed = False
                if auto_fix:
                    print(f"🔧 Attempting to auto-fix...")
                    if fix_func():
                        print(f"✅ Auto-fix successful")
                        # Re-run check to verify
                        check_func()
                    else:
                        print(f"❌ Auto-fix failed")
        
        # Run quality checks
        print("\n🔍 Quality Checks")
        print("-" * 20)
        for check in quality_checks:
            check()
        
        # Summary
        print("\n" + "=" * 50)
        print("📊 Pre-Commit Check Summary")
        print("=" * 50)
        
        if self.failed_checks:
            print(f"❌ Failed Checks ({len(self.failed_checks)}):")
            for desc, _ in self.failed_checks:
                print(f"  • {desc}")
        
        if self.warnings:
            print(f"⚠️  Warnings ({len(self.warnings)}):")
            for desc, _ in self.warnings:
                print(f"  • {desc}")
        
        # Determine overall status
        critical_failures = [f for f, _ in self.failed_checks 
                           if f in ["File structure", "Python syntax", "Import cycles", "Critical lint errors (flake8)", "Black formatting check", "Import sorting check"]]
        
        if critical_failures:
            print("\n💥 BLOCKED: Fix critical issues before committing")
            print("\nTo auto-fix formatting issues, run:")
            print("  python scripts/pre-commit-checks.py --fix")
            return False
        elif self.failed_checks or self.warnings:
            print("\n⚠️  READY WITH WARNINGS: Some issues detected but not blocking")
            return True
        else:
            print("\n🎉 ALL CHECKS PASSED: Ready to commit!")
            return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run pre-commit code quality checks")
    parser.add_argument("--fix", action="store_true", help="Auto-fix formatting issues")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings too")
    args = parser.parse_args()
    
    checker = CodeQualityChecker()
    success = checker.run_all_checks(auto_fix=args.fix)
    
    # Exit with appropriate code
    if not success:
        sys.exit(1)
    elif args.strict and (checker.failed_checks or checker.warnings):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()