#!/usr/bin/env python3
"""
CI Checks - Identical code quality checks for local and GitHub Actions.

This script contains the SAME checks that run in GitHub Actions,
ensuring local development matches CI exactly.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


class CIChecks:
    """Identical CI checks for local and GitHub Actions."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.failures = []
        self.warnings = []
        
    def log(self, message: str, level: str = "INFO"):
        """Log a message with appropriate formatting."""
        emoji = {"INFO": "ℹ️", "SUCCESS": "✅", "WARNING": "⚠️", "ERROR": "❌"}
        print(f"{emoji.get(level, '')} {message}")
        
    def run_check(self, cmd: List[str], name: str, critical: bool = True) -> bool:
        """Run a single check and track results."""
        self.log(f"Running {name}...", "INFO")
        
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=".", timeout=300
            )
            
            if result.returncode == 0:
                self.log(f"{name}: PASSED", "SUCCESS")
                if self.verbose and result.stdout.strip():
                    print(f"   Output: {result.stdout.strip()}")
                return True
            else:
                self.log(f"{name}: FAILED", "ERROR")
                error_output = result.stderr or result.stdout
                print(f"   Command: {' '.join(cmd)}")
                print(f"   Output: {error_output.strip()}")
                
                if critical:
                    self.failures.append((name, error_output))
                else:
                    self.warnings.append((name, error_output))
                return False
                
        except subprocess.TimeoutExpired:
            self.log(f"{name}: TIMEOUT", "ERROR")
            error_msg = f"Command timed out after 5 minutes"
            if critical:
                self.failures.append((name, error_msg))
            else:
                self.warnings.append((name, error_msg))
            return False
            
        except FileNotFoundError:
            self.log(f"{name}: TOOL NOT FOUND", "WARNING")
            self.warnings.append((name, "Tool not installed"))
            return True  # Don't fail if tool isn't available
            
        except Exception as e:
            self.log(f"{name}: ERROR - {str(e)}", "ERROR")
            if critical:
                self.failures.append((name, str(e)))
            else:
                self.warnings.append((name, str(e)))
            return False

    def check_black_formatting(self) -> bool:
        """Check Black code formatting - CRITICAL."""
        return self.run_check(
            ["black", "--check", "src/"],
            "Black formatting",
            critical=True
        )

    def check_isort_imports(self) -> bool:
        """Check import sorting - CRITICAL.""" 
        return self.run_check(
            ["isort", "--check-only", "src/"],
            "Import sorting",
            critical=True
        )

    def check_flake8_critical(self) -> bool:
        """Check critical flake8 errors - CRITICAL."""
        return self.run_check([
            "flake8", "src/", 
            "--count", "--select=E9,F63,F7,F82",
            "--show-source", "--statistics"
        ], "Critical lint errors", critical=True)

    def check_flake8_full(self) -> bool:
        """Full flake8 check - WARNING ONLY."""
        return self.run_check([
            "flake8", "src/",
            "--count", "--exit-zero", "--max-complexity=10",
            "--max-line-length=88", "--statistics"
        ], "Full lint check", critical=False)

    def check_python_syntax(self) -> bool:
        """Check Python syntax - CRITICAL."""
        python_files = list(Path("src").rglob("*.py"))
        syntax_errors = []
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    compile(f.read(), str(py_file), 'exec')
            except SyntaxError as e:
                syntax_errors.append(f"{py_file}:{e.lineno} - {e.msg}")
        
        if syntax_errors:
            self.log("Python syntax: FAILED", "ERROR")
            for error in syntax_errors:
                print(f"   {error}")
            self.failures.append(("Python syntax", "\n".join(syntax_errors)))
            return False
        else:
            self.log("Python syntax: PASSED", "SUCCESS")
            return True

    def check_imports(self) -> bool:
        """Check imports work - CRITICAL."""
        try:
            result = subprocess.run([
                sys.executable, "-c",
                "import sys; sys.path.insert(0, 'src'); import src.newsletter_bot"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.log("Import check: PASSED", "SUCCESS")
                return True
            else:
                self.log("Import check: FAILED", "ERROR")
                print(f"   Error: {result.stderr}")
                self.failures.append(("Import check", result.stderr))
                return False
                
        except Exception as e:
            self.log(f"Import check: ERROR - {str(e)}", "ERROR")
            self.failures.append(("Import check", str(e)))
            return False

    def check_required_files(self) -> bool:
        """Check required files exist - CRITICAL."""
        required_files = [
            "src/newsletter_bot.py",
            "src/core/newsletter.py",
            "src/models/settings.py",
            "pyproject.toml"
        ]
        
        missing = [f for f in required_files if not Path(f).exists()]
        
        if missing:
            self.log("Required files: FAILED", "ERROR")
            print(f"   Missing: {', '.join(missing)}")
            self.failures.append(("Required files", f"Missing: {missing}"))
            return False
        else:
            self.log("Required files: PASSED", "SUCCESS")
            return True

    def check_tests(self) -> bool:
        """Run tests if they exist - WARNING ONLY."""
        if not Path("tests").exists():
            self.log("Tests: SKIPPED (no tests directory)", "WARNING")
            return True
            
        return self.run_check([
            "pytest", "tests/", "-v", "--tb=short"
        ], "Unit tests", critical=False)

    def auto_fix_formatting(self) -> bool:
        """Auto-fix formatting issues."""
        print("\n🔧 Attempting to auto-fix formatting issues...")
        
        fixes_applied = []
        
        # Fix Black formatting
        try:
            result = subprocess.run(["black", "src/"], capture_output=True, text=True)
            if result.returncode == 0:
                fixes_applied.append("Black formatting")
                self.log("Applied Black formatting", "SUCCESS")
            else:
                self.log(f"Black auto-fix failed: {result.stderr}", "ERROR")
        except FileNotFoundError:
            self.log("Black not available for auto-fix", "WARNING")
        
        # Fix import sorting
        try:
            result = subprocess.run(["isort", "src/"], capture_output=True, text=True)
            if result.returncode == 0:
                fixes_applied.append("Import sorting")
                self.log("Applied import sorting", "SUCCESS")
            else:
                self.log(f"isort auto-fix failed: {result.stderr}", "ERROR")
        except FileNotFoundError:
            self.log("isort not available for auto-fix", "WARNING")
        
        if fixes_applied:
            print(f"\n✅ Auto-fixes applied: {', '.join(fixes_applied)}")
            print("Please review changes and commit them.")
            return True
        else:
            print("\n⚠️  No auto-fixes could be applied.")
            return False

    def run_all_checks(self) -> bool:
        """Run all CI checks in the same order as GitHub Actions."""
        print("🤖 Running CI Code Quality Checks")
        print("=" * 60)
        print("These are the EXACT same checks that run in GitHub Actions")
        print("=" * 60)
        
        # Critical checks that MUST pass
        critical_checks = [
            ("File structure", self.check_required_files),
            ("Python syntax", self.check_python_syntax),
            ("Import validation", self.check_imports),
            ("Black formatting", self.check_black_formatting),
            ("Import sorting", self.check_isort_imports),
            ("Critical linting", self.check_flake8_critical),
        ]
        
        # Non-critical checks (warnings only)
        warning_checks = [
            ("Full linting", self.check_flake8_full),
            ("Unit tests", self.check_tests),
        ]
        
        print(f"\n🎯 Critical Checks (must pass)")
        print("-" * 30)
        critical_passed = True
        for name, check_func in critical_checks:
            if not check_func():
                critical_passed = False
                
        print(f"\n⚠️  Warning Checks (informational)")
        print("-" * 30) 
        for name, check_func in warning_checks:
            check_func()  # Run but don't affect overall result
        
        # Display summary
        print(f"\n{'=' * 60}")
        print("📊 CI Check Results")
        print("=" * 60)
        
        if critical_passed:
            self.log("🎉 ALL CRITICAL CHECKS PASSED", "SUCCESS")
            if self.warnings:
                print(f"⚠️  {len(self.warnings)} warnings (non-blocking):")
                for name, _ in self.warnings:
                    print(f"   • {name}")
        else:
            self.log(f"💥 {len(self.failures)} CRITICAL FAILURES", "ERROR")
            for name, error in self.failures:
                print(f"   • {name}")
                
        if not critical_passed:
            print(f"\n🔧 To auto-fix formatting issues, run:")
            print(f"   python scripts/ci-checks.py --fix")
            
        return critical_passed

    def run_ci_simulation(self) -> bool:
        """Simulate exact GitHub Actions CI pipeline."""
        print("🤖 SIMULATING GITHUB ACTIONS CI PIPELINE")
        print("=" * 60)
        print("This runs the IDENTICAL checks that GitHub Actions will run.")
        print("If this passes, your PR will likely pass CI.")
        print("=" * 60)
        
        return self.run_all_checks()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Run identical CI checks locally and in GitHub Actions"
    )
    parser.add_argument(
        "--fix", action="store_true", 
        help="Auto-fix formatting issues"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--ci", action="store_true",
        help="Run in CI mode (exit codes for automation)"
    )
    
    args = parser.parse_args()
    
    checker = CIChecks(verbose=args.verbose)
    
    if args.fix:
        # Auto-fix mode
        print("🔧 AUTO-FIX MODE")
        print("=" * 40)
        checker.auto_fix_formatting()
        print("\nRe-running checks after auto-fix...\n")
        success = checker.run_all_checks()
    elif args.ci:
        # CI simulation mode
        success = checker.run_ci_simulation()
    else:
        # Normal mode
        success = checker.run_all_checks()
    
    # Exit with appropriate code
    if success:
        if args.ci:
            print("\n✅ CI SIMULATION PASSED - Your code is ready for GitHub!")
        sys.exit(0)
    else:
        if args.ci:
            print("\n❌ CI SIMULATION FAILED - Fix issues before pushing")
        sys.exit(1)


if __name__ == "__main__":
    main()