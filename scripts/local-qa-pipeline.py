#!/usr/bin/env python3
"""
Local QA Pipeline - Run comprehensive newsletter validation locally before deployment.

This script mimics and extends the GitHub Actions validation process,
ensuring maximum testing happens on the developer's machine.
"""

import asyncio
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import click

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class LocalQAAgent:
    """QA Agent for comprehensive local newsletter validation."""
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "overall_status": "pending",
            "critical_failures": [],
            "warnings": [],
            "recommendations": []
        }
        
    def log_check(self, check_name: str, status: str, details: str = "", critical: bool = False):
        """Log a check result."""
        self.results["checks"][check_name] = {
            "status": status,
            "details": details,
            "critical": critical,
            "timestamp": datetime.now().isoformat()
        }
        
        if status == "FAIL":
            if critical:
                self.results["critical_failures"].append(f"{check_name}: {details}")
            else:
                self.results["warnings"].append(f"{check_name}: {details}")
                
        logger.info(f"{'✅' if status == 'PASS' else '❌' if status == 'FAIL' else '⚠️'} {check_name}: {status}")
        if details and self.debug:
            logger.info(f"   Details: {details}")

    async def run_environment_checks(self) -> bool:
        """Validate local development environment."""
        logger.info("🔍 Running Environment Checks...")
        
        # Check Python version
        py_version = sys.version_info
        if py_version >= (3, 11):
            self.log_check("Python Version", "PASS", f"Python {py_version.major}.{py_version.minor}")
        else:
            self.log_check("Python Version", "FAIL", f"Python {py_version.major}.{py_version.minor} < 3.11 required", critical=True)
            
        # Check required packages
        required_packages = [
            "aiohttp", "click", "pydantic", "pydantic-settings", 
            "jinja2", "beautifulsoup4", "lxml"
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
                self.log_check(f"Package {package}", "PASS")
            except ImportError:
                missing_packages.append(package)
                self.log_check(f"Package {package}", "FAIL", "Not installed", critical=True)
        
        if missing_packages:
            self.results["recommendations"].append(
                f"Install missing packages: pip install {' '.join(missing_packages)}"
            )
            
        # Check virtual environment
        venv_active = hasattr(sys, 'real_prefix') or (
            hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
        )
        
        if venv_active:
            self.log_check("Virtual Environment", "PASS", "Active virtual environment detected")
        else:
            self.log_check("Virtual Environment", "WARN", "No virtual environment detected")
            self.results["recommendations"].append("Consider using a virtual environment")
            
        # Check project structure
        project_files = [
            "src/newsletter_bot.py", "src/core/newsletter.py", "src/models/settings.py",
            "scripts/check_briefing.py", "pyproject.toml", "CLAUDE.md"
        ]
        
        for file_path in project_files:
            if Path(file_path).exists():
                self.log_check(f"Project File {file_path}", "PASS")
            else:
                self.log_check(f"Project File {file_path}", "FAIL", "Missing", critical=True)
                
        return len(self.results["critical_failures"]) == 0

    async def run_code_quality_checks(self) -> bool:
        """Run code quality checks locally."""
        logger.info("🔍 Running Code Quality Checks...")
        
        # Black formatting check
        try:
            result = subprocess.run(['black', '--check', 'src/'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                self.log_check("Black Formatting", "PASS")
            else:
                self.log_check("Black Formatting", "FAIL", 
                              "Code not formatted. Run: black src/", critical=False)
        except FileNotFoundError:
            self.log_check("Black Formatting", "SKIP", "Black not installed")
            
        # Import sorting check
        try:
            result = subprocess.run(['isort', '--check-only', 'src/'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                self.log_check("Import Sorting", "PASS")
            else:
                self.log_check("Import Sorting", "FAIL", 
                              "Imports not sorted. Run: isort src/", critical=False)
        except FileNotFoundError:
            self.log_check("Import Sorting", "SKIP", "isort not installed")
            
        # Flake8 linting (critical errors only)
        try:
            result = subprocess.run([
                'flake8', 'src/', '--count', '--select=E9,F63,F7,F82', 
                '--show-source', '--statistics'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                self.log_check("Critical Lint Errors", "PASS")
            else:
                self.log_check("Critical Lint Errors", "FAIL", 
                              f"Critical lint errors found:\n{result.stdout}", critical=True)
        except FileNotFoundError:
            self.log_check("Critical Lint Errors", "SKIP", "flake8 not installed")
            
        return len([f for f in self.results["critical_failures"] 
                   if "Critical Lint Errors" in f]) == 0

    async def run_unit_tests(self) -> bool:
        """Run unit tests locally."""
        logger.info("🔍 Running Unit Tests...")
        
        try:
            result = subprocess.run(['pytest', 'tests/', '-v', '--tb=short'], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                self.log_check("Unit Tests", "PASS", "All tests passed")
                return True
            else:
                # Parse pytest output for details
                failed_tests = []
                for line in result.stdout.split('\n'):
                    if 'FAILED' in line:
                        failed_tests.append(line.strip())
                
                self.log_check("Unit Tests", "FAIL", 
                              f"Failed tests:\n" + "\n".join(failed_tests), critical=True)
                return False
                
        except FileNotFoundError:
            self.log_check("Unit Tests", "SKIP", "pytest not installed")
            return True

    async def run_newsletter_generation_test(self) -> bool:
        """Test newsletter generation locally."""
        logger.info("🔍 Running Newsletter Generation Test...")
        
        try:
            # Test dry-run generation
            result = subprocess.run([
                sys.executable, '-m', 'src.newsletter_bot', 
                'generate', '--dry-run'
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                self.log_check("Newsletter Generation", "PASS", "Dry-run completed successfully")
                
                # Check if draft was created
                if Path("newsletter_draft.md").exists():
                    draft_size = Path("newsletter_draft.md").stat().st_size
                    self.log_check("Draft Creation", "PASS", f"Draft created ({draft_size} bytes)")
                else:
                    self.log_check("Draft Creation", "WARN", "No draft file created")
                    
                return True
            else:
                error_details = result.stderr or result.stdout
                self.log_check("Newsletter Generation", "FAIL", 
                              f"Generation failed: {error_details}", critical=True)
                return False
                
        except subprocess.TimeoutExpired:
            self.log_check("Newsletter Generation", "FAIL", 
                          "Generation timed out after 5 minutes", critical=True)
            return False
        except Exception as e:
            self.log_check("Newsletter Generation", "FAIL", 
                          f"Unexpected error: {str(e)}", critical=True)
            return False

    async def run_content_quality_checks(self) -> bool:
        """Run content quality validation on generated newsletter."""
        logger.info("🔍 Running Content Quality Checks...")
        
        if not Path("newsletter_draft.md").exists():
            self.log_check("Content Quality", "SKIP", "No draft to validate")
            return True
            
        try:
            # Use the existing briefing checker
            result = subprocess.run([
                sys.executable, 'scripts/check_briefing.py', 
                'newsletter_draft.md', '--json', 'qa_results.json', '--verbose'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                self.log_check("Content Quality", "PASS", "All quality checks passed")
                
                # Load detailed results if available
                if Path("qa_results.json").exists():
                    with open("qa_results.json") as f:
                        qa_results = json.load(f)
                    
                    # Add detailed quality metrics
                    for report in qa_results.get("reports", []):
                        for result_item in report.get("results", []):
                            if not result_item["passed"]:
                                self.results["warnings"].append(
                                    f"Quality: {result_item['name']} - {result_item['count']} issues"
                                )
                                
                return True
            else:
                self.log_check("Content Quality", "FAIL", 
                              f"Quality validation failed: {result.stdout}", critical=False)
                return False
                
        except Exception as e:
            self.log_check("Content Quality", "FAIL", 
                          f"Quality check error: {str(e)}", critical=False)
            return False

    async def run_api_connectivity_tests(self) -> bool:
        """Test API connections without making actual calls."""
        logger.info("🔍 Running API Connectivity Tests...")
        
        try:
            # Test configuration loading
            result = subprocess.run([
                sys.executable, '-m', 'src.newsletter_bot', 'config'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.log_check("Configuration", "PASS", "Settings loaded successfully")
                
                # Parse config output for API key validation
                config_output = result.stdout
                if "Missing required API keys" in config_output:
                    missing_keys = [line.strip() for line in config_output.split('\n') 
                                   if "Missing" in line]
                    self.log_check("API Keys", "WARN", 
                                  f"Missing keys detected: {missing_keys}")
                else:
                    self.log_check("API Keys", "PASS", "All required keys configured")
                    
                return True
            else:
                self.log_check("Configuration", "FAIL", 
                              f"Config validation failed: {result.stderr}", critical=True)
                return False
                
        except subprocess.TimeoutExpired:
            self.log_check("Configuration", "FAIL", "Config check timed out", critical=True)
            return False
        except Exception as e:
            self.log_check("Configuration", "FAIL", 
                          f"Config error: {str(e)}", critical=True)
            return False

    async def run_security_checks(self) -> bool:
        """Run security validation checks."""
        logger.info("🔍 Running Security Checks...")
        
        security_issues = []
        
        # Check for secrets in code
        sensitive_patterns = [
            "api_key", "password", "secret", "token", "key"
        ]
        
        code_files = list(Path("src").rglob("*.py"))
        for file_path in code_files:
            try:
                content = file_path.read_text(encoding='utf-8')
                for line_num, line in enumerate(content.split('\n'), 1):
                    line_lower = line.lower()
                    if any(pattern in line_lower for pattern in sensitive_patterns):
                        if not line.strip().startswith('#') and '=' in line:
                            if '"' in line or "'" in line:
                                # Potential hardcoded secret
                                security_issues.append(
                                    f"{file_path}:{line_num} - Potential hardcoded secret"
                                )
            except Exception as e:
                logger.debug(f"Could not scan {file_path}: {e}")
                
        if security_issues:
            self.log_check("Security Scan", "WARN", 
                          f"Potential security issues:\n" + "\n".join(security_issues[:5]))
        else:
            self.log_check("Security Scan", "PASS", "No obvious security issues found")
            
        # Check .env file exclusion
        gitignore_path = Path(".gitignore")
        if gitignore_path.exists():
            gitignore_content = gitignore_path.read_text()
            if ".env" in gitignore_content:
                self.log_check("Environment File Protection", "PASS")
            else:
                self.log_check("Environment File Protection", "WARN", 
                              "Consider adding .env to .gitignore")
        else:
            self.log_check("Environment File Protection", "WARN", "No .gitignore found")
            
        return True

    async def generate_report(self) -> Dict:
        """Generate comprehensive QA report."""
        total_checks = len(self.results["checks"])
        passed_checks = len([c for c in self.results["checks"].values() if c["status"] == "PASS"])
        failed_checks = len([c for c in self.results["checks"].values() if c["status"] == "FAIL"])
        
        self.results.update({
            "summary": {
                "total_checks": total_checks,
                "passed": passed_checks,
                "failed": failed_checks,
                "warnings": len(self.results["warnings"]),
                "critical_failures": len(self.results["critical_failures"])
            },
            "overall_status": "PASS" if len(self.results["critical_failures"]) == 0 else "FAIL"
        })
        
        return self.results

    async def run_full_pipeline(self) -> bool:
        """Run complete local QA pipeline."""
        logger.info("🚀 Starting Local QA Pipeline...")
        logger.info("=" * 60)
        
        # Run all check categories
        checks = [
            ("Environment", self.run_environment_checks()),
            ("Code Quality", self.run_code_quality_checks()),
            ("Unit Tests", self.run_unit_tests()),
            ("Newsletter Generation", self.run_newsletter_generation_test()),
            ("Content Quality", self.run_content_quality_checks()),
            ("API Connectivity", self.run_api_connectivity_tests()),
            ("Security", self.run_security_checks())
        ]
        
        results = []
        for check_name, check_coro in checks:
            logger.info(f"\n📋 {check_name} Checks")
            logger.info("-" * 30)
            result = await check_coro
            results.append(result)
            
        # Generate final report
        final_report = await self.generate_report()
        
        # Display summary
        logger.info("\n" + "=" * 60)
        logger.info("🏁 QA Pipeline Summary")
        logger.info("=" * 60)
        
        summary = final_report["summary"]
        logger.info(f"✅ Passed: {summary['passed']}")
        logger.info(f"❌ Failed: {summary['failed']}")
        logger.info(f"⚠️  Warnings: {summary['warnings']}")
        logger.info(f"🚨 Critical: {summary['critical_failures']}")
        
        overall_status = final_report["overall_status"]
        if overall_status == "PASS":
            logger.info("🎉 Overall Status: READY FOR DEPLOYMENT")
        else:
            logger.error("💥 Overall Status: NOT READY - Fix critical issues")
            
        # Show critical failures
        if final_report["critical_failures"]:
            logger.error("\n🚨 Critical Issues to Fix:")
            for issue in final_report["critical_failures"]:
                logger.error(f"  • {issue}")
                
        # Show recommendations
        if final_report["recommendations"]:
            logger.info("\n💡 Recommendations:")
            for rec in final_report["recommendations"]:
                logger.info(f"  • {rec}")
                
        # Save detailed report
        report_file = Path("local_qa_report.json")
        with open(report_file, 'w') as f:
            json.dump(final_report, f, indent=2)
        logger.info(f"\n📄 Detailed report saved: {report_file}")
        
        return overall_status == "PASS"


@click.command()
@click.option('--debug', is_flag=True, help='Enable debug output')
@click.option('--report-only', is_flag=True, help='Only generate report, skip tests')
@click.option('--category', help='Run specific category: env,quality,tests,generation,content,api,security')
def main(debug: bool, report_only: bool, category: Optional[str]):
    """Run comprehensive local QA pipeline for newsletter system."""
    
    async def run_qa():
        qa_agent = LocalQAAgent(debug=debug)
        
        if report_only:
            logger.info("📊 Generating report from previous run...")
            if Path("local_qa_report.json").exists():
                with open("local_qa_report.json") as f:
                    report = json.load(f)
                logger.info(json.dumps(report, indent=2))
            else:
                logger.error("No previous report found. Run without --report-only first.")
            return
            
        if category:
            # Run specific category
            category_map = {
                'env': qa_agent.run_environment_checks,
                'quality': qa_agent.run_code_quality_checks,
                'tests': qa_agent.run_unit_tests,
                'generation': qa_agent.run_newsletter_generation_test,
                'content': qa_agent.run_content_quality_checks,
                'api': qa_agent.run_api_connectivity_tests,
                'security': qa_agent.run_security_checks
            }
            
            if category in category_map:
                logger.info(f"🎯 Running {category} checks only...")
                result = await category_map[category]()
                await qa_agent.generate_report()
                sys.exit(0 if result else 1)
            else:
                logger.error(f"Unknown category: {category}")
                logger.error(f"Available: {', '.join(category_map.keys())}")
                sys.exit(1)
        else:
            # Run full pipeline
            success = await qa_agent.run_full_pipeline()
            sys.exit(0 if success else 1)
    
    asyncio.run(run_qa())


if __name__ == "__main__":
    main()