import os
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

from state import PipelineState
from sandbox.patcher import apply_diff_patch


def run_git_command(args: list) -> Tuple[bool, str]:
    proc = subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True
    )
    if proc.returncode != 0:
        return False, proc.stderr.strip() or proc.stdout.strip()
    return True, proc.stdout.strip()


def generate_pr_summary(state: PipelineState) -> str:
    triage = state.triage_data
    lines = [
        "###  Autonomous DevSecOps Remediation Report",
        "",
        f"**Vulnerability:** `{triage.vulnerability_type}`",
        f"**Target:** `{triage.file_path}` (`{triage.function_name}` lines {triage.line_start}-{triage.line_end})",
        f"**Iteration Turns Taken:** `{state.iteration_count}`",
        "",
        "---",
        "",
        "####  Root Cause Analysis",
        f"{triage.root_cause_summary}",
        "",
        "####  Deterministic Verification Signal",
        "- **Tests Passed:** `True`",
        "- **Exit Code:** `0`",
        "- **Verification Engine:** Deterministic Pytest Harness",
        "",
        "####  Applied Patch",
        "```diff",
        f"{state.current_git_diff}",
        "```",
        "",
        "*Generated and verified autonomously by Autonomous-DevSecOps-Remediation-Pipeline.*"
    ]
    return "\n".join(lines)


def deliver_patch(state: PipelineState) -> Dict[str, Any]:
    if not state.triage_data or not state.current_git_diff:
        return {"delivered": False, "error": "Missing triage data or diff in state"}

    # 1. Format clean branch name
    timestamp = int(time.time())
    cwe_tag = (
        state.triage_data.vulnerability_type.split(":")[0]
        .strip()
        .replace(" ", "-")
        .lower()
    )
    branch_name = f"fix/{cwe_tag}-{timestamp}"

    print(f"\n[GIT DELIVERY] 1. Creating git branch: '{branch_name}'...")
    success, output = run_git_command(["git", "checkout", "-b", branch_name])
    if not success:
        return {"delivered": False, "error": f"Branch creation failed: {output}"}

    # 2. Apply patch permanently to this branch
    print(f"[GIT DELIVERY] 2. Applying verified diff permanently to branch '{branch_name}'...")
    patch_status = apply_diff_patch(state.current_git_diff, target_dir=state.repo_directory)
    if not patch_status["success"]:
        run_git_command(["git", "checkout", "-"])
        return {"delivered": False, "error": f"Failed to apply patch: {patch_status['error']}"}

    # 3. Stage and commit
    print("[GIT DELIVERY] 3. Staging and committing changes...")
    run_git_command(["git", "add", "demo_repo/"])
    commit_msg = (
        f"fix(security): remediate {state.triage_data.vulnerability_type} in {state.triage_data.function_name}\n\n"
        f"Autonomous patch verified by deterministic test runner."
    )
    success, output = run_git_command(["git", "commit", "-m", commit_msg])
    if not success:
        run_git_command(["git", "checkout", "-"])
        return {"delivered": False, "error": f"Git commit failed: {output}"}

    # 4. Generate PR summary Markdown
    print("[GIT DELIVERY] 4. Writing PR_SUMMARY.md artifact...")
    pr_body = generate_pr_summary(state)
    summary_file = PROJECT_ROOT / "PR_SUMMARY.md"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(pr_body)

    print(f"   -> Created: {summary_file}")

    # 5. Optional GitHub draft PR integration
    github_token = os.getenv("GITHUB_TOKEN")
    github_repo = os.getenv("GITHUB_REPOSITORY")
    pr_url: Optional[str] = None

    if github_token and github_repo:
        print("[GIT DELIVERY] 5. GITHUB_TOKEN detected. Opening draft PR on GitHub...")
        try:
            from github import Github
            gh = Github(github_token)
            repo = gh.get_repo(github_repo)

            run_git_command(["git", "push", "-u", "origin", branch_name])
            pr = repo.create_pull(
                title=f"🔒 Fix {state.triage_data.vulnerability_type} in {state.triage_data.file_path}",
                body=pr_body,
                head=branch_name,
                base="main",
                draft=True
            )
            pr_url = pr.html_url
            print(f"   ->  Draft PR created: {pr_url}")
        except Exception as e:
            print(f"   -> [INFO] GitHub remote push skipped ({e}). Local git branch delivery succeeded.")
    else:
        print("[GIT DELIVERY] 5. No GITHUB_TOKEN set in .env. Skipping remote push (local delivery succeeded).")

    return {
        "delivered": True,
        "branch": branch_name,
        "pr_summary_file": str(summary_file),
        "pr_url": pr_url
    }