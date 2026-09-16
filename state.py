from typing import List, Optional
from pydantic import BaseModel, Field

class VulnerabilityLocation(BaseModel):
    file_path: str = Field(description="Relative path to target file")
    function_name: str = Field(description="Name of the vulnerable function/method")
    line_start: int = Field(description="Starting line of the vulnerability")
    line_end: int = Field(description="Ending line of the vulnerability")
    vulnerability_type: str = Field(description="CWE identifier or classification")
    root_cause_summary: str = Field(description="Short technical explanation of the flaw")

class TestExecutionResult(BaseModel):
    tests_passed: bool = Field(description="True if test runner exit code == 0")
    exit_code: int = Field(description="Raw process exit code")
    sanitized_stack_trace: Optional[str] = Field(default=None, description="Condensed failure trace")

class PipelineState(BaseModel):
    repo_directory: str = "demo_repo"
    raw_security_alert: str
    triage_data: Optional[VulnerabilityLocation] = None
    current_git_diff: Optional[str] = None
    test_result: Optional[TestExecutionResult] = None
    iteration_count: int = Field(default=0)
    max_iterations: int = Field(default=3)
    human_approved: bool = Field(default=False)