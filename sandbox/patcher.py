import subprocess
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def apply_diff_patch(diff_content: str, target_dir: str = "demo_repo") -> dict:
    """
    Applies a unified git diff patch using git apply.
    Includes --recount and --ignore-whitespace to accommodate LLM line-number offsets.
    """
    patch_path = PROJECT_ROOT / "temp_fix.patch"
    with open(patch_path, "w", encoding="utf-8") as f:
        f.write(diff_content.strip() + "\n")

    # Command flags that make git apply tolerant of LLM hunk-header inaccuracies
    flags = ["--recount", "--ignore-space-change", "--ignore-whitespace", "--whitespace=nowarn"]

    try:
        # Step 1: Check applicability
        check_cmd = ["git", "apply", "--check"] + flags + [str(patch_path)]
        check_proc = subprocess.run(
            check_cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )

        if check_proc.returncode != 0:
            # Fallback attempt: try 3-way merge application if available
            check_cmd_3way = ["git", "apply", "--check", "-3"] + flags + [str(patch_path)]
            check_proc_3way = subprocess.run(
                check_cmd_3way,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True
            )
            if check_proc_3way.returncode != 0:
                return {
                    "success": False,
                    "error": f"Patch check failed: {check_proc.stderr or check_proc.stdout}"
                }

        # Step 2: Apply the patch
        apply_cmd = ["git", "apply"] + flags + [str(patch_path)]
        apply_proc = subprocess.run(
            apply_cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )

        return {
            "success": apply_proc.returncode == 0,
            "error": apply_proc.stderr if apply_proc.returncode != 0 else None
        }

    finally:
        if patch_path.exists():
            patch_path.unlink()

def backup_file(file_path: str) -> str:
    """Reads and returns the current content of a file as an in-memory backup."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def rollback_file(file_path: str, backup_content: str):
    """Restores the file to its exact backup content."""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(backup_content)