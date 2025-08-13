#!/usr/bin/env python3
"""
Local CI Runner using nektos/act.

This script uses `act` to run GitHub Actions locally, providing identical
CI environment to catch issues before pushing to GitHub.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


class LocalCIRunner:
    """Run GitHub Actions locally using nektos/act."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.act_installed = self._check_act_installation()
        
    def _check_act_installation(self) -> bool:
        """Check if act is installed."""
        try:
            result = subprocess.run(
                ["act", "--version"], 
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                print(f"✅ act is installed: {version}")
                return True
            else:
                print("❌ act is installed but not working properly")
                return False
        except FileNotFoundError:
            print("❌ act is not installed")
            return False
        except Exception as e:
            print(f"⚠️  Error checking act installation: {e}")
            return False
    
    def install_act_instructions(self):
        """Show instructions for installing act."""
        print("""
📦 Install nektos/act to run GitHub Actions locally:

🍎 macOS:
   brew install act

🐧 Linux:
   curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

🪟 Windows:
   choco install act-cli
   # or download from: https://github.com/nektos/act/releases

🐳 Docker (any OS):
   docker run --rm -it -v $(pwd):/workspace -w /workspace ghcr.io/nektos/act:latest

📚 More info: https://github.com/nektos/act#installation
        """)

    def create_act_secrets_file(self) -> Path:
        """Create .secrets file for act with dummy values."""
        secrets_file = Path(".secrets")
        
        # Define dummy secrets for local testing
        dummy_secrets = {
            "READWISE_API_KEY": "dummy_readwise_key_for_local_testing",
            "GLASP_API_KEY": "dummy_glasp_key_for_local_testing", 
            "RSS_FEEDS": "https://example.com/rss",
            "BUTTONDOWN_API_KEY": "dummy_buttondown_key_for_local_testing",
            "OPENROUTER_API_KEY": "dummy_openrouter_key_for_local_testing",
            "UNSPLASH_API_KEY": "dummy_unsplash_key_for_local_testing",
            "SMTP_SERVER": "smtp.example.com",
            "SMTP_USERNAME": "test@example.com",
            "SMTP_PASSWORD": "dummy_password",
        }
        
        with open(secrets_file, 'w') as f:
            for key, value in dummy_secrets.items():
                f.write(f"{key}={value}\n")
        
        print(f"📝 Created {secrets_file} with dummy secrets for local testing")
        
        # Add to .gitignore if not already there
        gitignore = Path(".gitignore")
        if gitignore.exists():
            content = gitignore.read_text()
            if ".secrets" not in content:
                with open(gitignore, 'a') as f:
                    f.write("\n# Local CI secrets\n.secrets\n")
                print("📝 Added .secrets to .gitignore")
        
        return secrets_file

    def run_workflow_locally(self, workflow: str, event: str = "push", dry_run: bool = False) -> bool:
        """Run a specific workflow locally using act."""
        if not self.act_installed:
            print("❌ Cannot run workflow: act is not installed")
            self.install_act_instructions()
            return False
        
        # Ensure secrets file exists
        secrets_file = self.create_act_secrets_file()
        
        # Build act command
        cmd = ["act", event]
        
        if workflow:
            cmd.extend(["--workflows", f".github/workflows/{workflow}"])
        
        # Add secrets file
        cmd.extend(["--secret-file", str(secrets_file)])
        
        # Add verbose flag if requested
        if self.verbose:
            cmd.append("--verbose")
        
        # Add dry run flag
        if dry_run:
            cmd.append("--dry-run")
        
        # Use smaller runner image for faster startup
        cmd.extend(["--container-architecture", "linux/amd64"])
        cmd.extend(["-P", "ubuntu-latest=catthehacker/ubuntu:act-latest"])
        
        print(f"🚀 Running workflow locally: {workflow or 'all workflows'}")
        print(f"Command: {' '.join(cmd)}")
        print("=" * 60)
        
        try:
            # Run act command
            result = subprocess.run(cmd, cwd=".")
            
            if result.returncode == 0:
                print("✅ Workflow completed successfully!")
                return True
            else:
                print(f"❌ Workflow failed with exit code {result.returncode}")
                return False
                
        except KeyboardInterrupt:
            print("\n⚠️  Workflow interrupted by user")
            return False
        except Exception as e:
            print(f"❌ Error running workflow: {e}")
            return False

    def list_available_workflows(self) -> List[str]:
        """List available GitHub Actions workflows."""
        workflows_dir = Path(".github/workflows")
        if not workflows_dir.exists():
            print("❌ No .github/workflows directory found")
            return []
        
        workflows = []
        for file in workflows_dir.glob("*.yml"):
            workflows.append(file.name)
        
        if workflows:
            print("📋 Available workflows:")
            for i, workflow in enumerate(workflows, 1):
                print(f"   {i}. {workflow}")
        else:
            print("❌ No workflow files found")
        
        return workflows

    def run_ci_pipeline(self) -> bool:
        """Run the main CI pipeline locally."""
        print("🤖 Running CI Pipeline Locally with nektos/act")
        print("=" * 60)
        
        # Look for CI workflow file
        ci_workflows = [
            "ci.yml", "test.yml", "main.yml", 
            "code-quality.yml", "newsletter.yml"
        ]
        
        workflows_dir = Path(".github/workflows")
        available_workflows = [f.name for f in workflows_dir.glob("*.yml")]
        
        # Find the best CI workflow to run
        target_workflow = None
        for workflow in ci_workflows:
            if workflow in available_workflows:
                target_workflow = workflow
                break
        
        if not target_workflow:
            print("⚠️  No standard CI workflow found, running all workflows...")
            return self.run_workflow_locally("", "push")
        
        return self.run_workflow_locally(target_workflow, "push")

    def simulate_pr_check(self) -> bool:
        """Simulate a PR check by running on pull_request event."""
        print("🔍 Simulating Pull Request Checks")
        print("=" * 60)
        
        # Run workflows that trigger on pull_request
        return self.run_workflow_locally("", "pull_request")

    def test_specific_workflow(self, workflow_name: str) -> bool:
        """Test a specific workflow file."""
        workflows_dir = Path(".github/workflows")
        workflow_file = workflows_dir / workflow_name
        
        if not workflow_file.exists():
            print(f"❌ Workflow not found: {workflow_name}")
            self.list_available_workflows()
            return False
        
        return self.run_workflow_locally(workflow_name, "push")

    def dry_run_workflow(self, workflow_name: str = "") -> bool:
        """Perform a dry run of workflow (shows what would run without executing)."""
        print("🔍 Dry Run Mode - Showing what would execute")
        print("=" * 60)
        
        return self.run_workflow_locally(workflow_name, "push", dry_run=True)


def main():
    """Main CLI interface."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Run GitHub Actions locally using nektos/act"
    )
    
    parser.add_argument(
        "--workflow", "-w", 
        help="Specific workflow file to run (e.g., ci.yml)"
    )
    parser.add_argument(
        "--event", "-e", default="push",
        help="GitHub event to simulate (push, pull_request, etc.)"
    )
    parser.add_argument(
        "--list", "-l", action="store_true",
        help="List available workflows"
    )
    parser.add_argument(
        "--ci", action="store_true",
        help="Run main CI pipeline"
    )
    parser.add_argument(
        "--pr", action="store_true",
        help="Simulate pull request checks"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would run without executing"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--install-guide", action="store_true",
        help="Show act installation instructions"
    )
    
    args = parser.parse_args()
    
    runner = LocalCIRunner(verbose=args.verbose)
    
    # Handle different modes
    if args.install_guide:
        runner.install_act_instructions()
        return
    
    if args.list:
        runner.list_available_workflows()
        return
    
    if not runner.act_installed:
        print("❌ act is required but not installed")
        runner.install_act_instructions()
        sys.exit(1)
    
    success = False
    
    if args.dry_run:
        success = runner.dry_run_workflow(args.workflow or "")
    elif args.ci:
        success = runner.run_ci_pipeline()
    elif args.pr:
        success = runner.simulate_pr_check()
    elif args.workflow:
        success = runner.test_specific_workflow(args.workflow)
    else:
        # Default: run main CI pipeline
        print("🎯 Running default CI pipeline")
        success = runner.run_ci_pipeline()
    
    if success:
        print("\n🎉 Local CI run completed successfully!")
        print("Your code should pass GitHub Actions CI ✅")
        sys.exit(0)
    else:
        print("\n❌ Local CI run failed!")
        print("Fix issues before pushing to GitHub 🔧")
        sys.exit(1)


if __name__ == "__main__":
    main()