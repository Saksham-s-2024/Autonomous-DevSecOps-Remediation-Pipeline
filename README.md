# 🛡️ Autonomous DevSecOps Remediation Pipeline

**Automated vulnerability detection, patching, and self-healing CI/CD remediation — powered by a multi-agent LLM workflow.**

The pipeline reads a security alert, locates the vulnerable code, writes a fix, verifies the fix with a deterministic test suite, loops back to re-patch on failure, and — once a human approves — commits the change to a new git branch (with an optional draft PR on GitHub). No human ever touches the code directly; they only approve or reject the final, test-verified patch.

---

## ✨ Key Features

- **Automated triage** — a Scout agent reads the raw vulnerability alert and the codebase, then pinpoints the exact file, function, and line range at fault.
- **Self-healing patch generation** — a Coder agent produces a minimal `git diff` fix, and re-attempts automatically using the previous test failure as feedback.
- **Deterministic verification** — every candidate patch is applied in an isolated pass, exercised with `pytest`, and rolled back regardless of outcome so the working tree is never left dirty.
- **Bounded self-correction loop** — failed patches are routed back to the Coder with the sanitized stack trace, up to a configurable `max_iterations` before escalating to a human.
- **Human-in-the-loop (HITL) approval gate** — a verified patch is never merged automatically; a human engineer reviews the diff and explicitly approves or rejects it.
- **Automated git delivery** — on approval, the pipeline creates a `fix/<cwe-tag>-<timestamp>` branch, commits the patch, generates a Markdown PR summary, and (optionally) opens a draft PR on GitHub.
- **LLM gateway with guardrails** — inbound secret-scrubbing, outbound diff-sanitization, client-side rate limiting, and automatic failover between LLM providers.
- **Multi-provider resilience** — primary calls go to Google **Gemini**; if the primary provider errors out, the gateway transparently fails over to **Groq**.

---

##  Architecture

The system is a **LangGraph** state machine with three specialist agents, a resilient LLM gateway, and a sandboxed patch/test harness.

```
                         ┌─────────────┐
                         │   START     │
                         └──────┬──────┘
                                ▼
                        ┌───────────────┐
                        │  🔍 SCOUT     │  Triage: locate the vulnerable
                        │   (agent)     │  file / function / lines
                        └───────┬───────┘
                                ▼
                  ┌────────────────────────┐
              ┌──▶│  🛠️ CODER (agent)      │  Generate a minimal unified
              │   │  self-corrects on      │  git diff patch
              │   │  prior failures        │
              │   └───────────┬────────────┘
              │               ▼
              │   ┌────────────────────────┐
              │   │  🧪 TESTER (agent)      │  Apply patch → run pytest
              │   │  always rolls back      │  → capture pass/fail signal
              │   └───────────┬────────────┘
              │               ▼
              │      ┌─────────────────┐
              │      │ router_condition │
              │      └───┬─────┬───┬───┘
              │  tests    │     │   │ max_iterations
              │  failed & │     │   │ exceeded
              └───────────┘     │   ▼
                     tests      │  ┌───────────────────────┐
                     passed     │  │ ❌ failed_max_retries  │──▶ END
                                │  │  escalate to human     │
                                ▼  └───────────────────────┘
                     ┌────────────────────────┐
                     │ 🧑‍✈️ hitl_approval_node │
                     │ human reviews diff in   │
                     │ terminal, approves (y)  │
                     │ or rejects (n)          │
                     └───────────┬────────────┘
                                 ▼
                    approved ──▶ 🚀 GIT DELIVERY
                                 · create fix/<cwe>-<ts> branch
                                 · apply + commit patch
                                 · write PR_SUMMARY.md
                                 · optional draft PR (GitHub)
                                 ▼
                               END
```

### Agents (`agents/`)

| Agent | File | Responsibility |
|---|---|---|
| **Scout** | `agents/scout.py` | Reads every `.py` file in the target repo, sends the alert + numbered source to the LLM gateway, and parses a strict JSON response into a `VulnerabilityLocation`. |
| **Coder** | `agents/coder.py` | Loads the flagged source file, asks the LLM for a surgical unified diff, and sanitizes the output into a clean, `git apply`-ready patch. Accepts an optional failing stack trace to self-correct. |
| **Tester** | `agents/tester.py` | Backs up the target file, applies the candidate patch, runs the deterministic `pytest` suite, records the result, and **always** rolls the file back to its original state. |

### Gateway (`gateway/`)

| Module | Responsibility |
|---|---|
| `router.py` | Single entry point for all LLM calls (`call_llm_gateway`). Handles client-side rate limiting, calls the primary model (`gemini/gemini-2.5-flash`), and fails over to the backup model (`groq/llama-3.3-70b-versatile`) on error, via [LiteLLM](https://github.com/BerriAI/litellm). |
| `guardrails.py` | `scrub_secrets` redacts API keys/tokens/passwords from any text sent to an LLM. `sanitize_diff_output` strips markdown fences/preamble so the model's response is a clean unified diff. |
| `git_delivery.py` | On human approval: creates a timestamped fix branch, applies + commits the patch, writes `PR_SUMMARY.md`, and opens a draft PR via `PyGithub` if `GITHUB_TOKEN` / `GITHUB_REPOSITORY` are set. |

### Sandbox (`sandbox/`)

| Module | Responsibility |
|---|---|
| `patcher.py` | Writes the diff to a temp `.patch` file and applies it with `git apply` (using `--recount`, `--ignore-whitespace`, and a 3-way merge fallback to tolerate LLM line-offset errors). Also provides in-memory `backup_file` / `rollback_file` helpers. |
| `runner.py` | Runs `pytest` against the target directory and condenses the output down to the `FAILURES`/`FAILED` section for compact, LLM-friendly feedback. |

### State (`state.py`)

Pydantic models define the shared graph state:

- `VulnerabilityLocation` — Scout's triage output (file, function, line range, CWE type, root cause).
- `TestExecutionResult` — Tester's verdict (pass/fail, exit code, sanitized trace).
- `PipelineState` — the full LangGraph state: alert, repo directory, triage data, current diff, test result, iteration counter, retry budget, and human-approval flag.

### Demo target (`demo_repo/`)

A small intentionally-vulnerable app used to exercise the pipeline end-to-end:

- `app.py` — `get_user_role()` builds a SQL query with an f-string, making it vulnerable to **CWE-89 (SQL Injection)**.
- `test_app.py` — a `pytest` suite with a security regression test (`test_sql_injection_remediation`) that **fails on the vulnerable code** and only passes once the injection is fixed with parameterized queries.

---

## 📋 Prerequisites

- Python **3.14** (a pre-built virtual environment is bundled under `venv/`, but see [Setup](#-setup) to create your own)
- `git` available on your `PATH` (used for patch application and branch delivery)
- API keys for at least one LLM provider:
  - **Google Gemini** — [Google AI Studio](https://aistudio.google.com/) → `GEMINI_API_KEY`
  - **Groq** (fallback) — [Groq Console](https://console.groq.com/) → `GROQ_API_KEY`
- *(Optional)* A GitHub personal access token if you want the pipeline to open draft PRs automatically.

---

## ⚙️ Setup

1. **Clone the repository and enter it**
   ```bash
   git clone <your-repo-url>
   cd Autonomous-DevSecOps-Remediation-Pipeline
   ```

2. **Create a virtual environment and install dependencies**
   ```bash
   python3 -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate

   pip install langgraph langchain-core litellm pydantic pydantic-settings \
               python-dotenv pytest requests PyGithub
   ```

3. **Configure environment variables**

   Create a `.env` file in the project root:
   ```ini
   # Primary LLM provider
   GEMINI_API_KEY=your_gemini_api_key_here

   # Fallback LLM provider
   GROQ_API_KEY=your_groq_api_key_here

   # Optional — enables automatic draft PR creation on GitHub
   GITHUB_TOKEN=your_github_pat_here
   GITHUB_REPOSITORY=your-org/your-repo
   ```

4. **(Optional) Sanity-check your API keys**
   ```bash
   python test_connections.py
   ```
   This pings Gemini directly, lists the models your key can access, sends a smoke-test prompt, and falls back to Groq if Gemini is unreachable.

---

## ▶️ Usage

### Run the full pipeline end-to-end

```bash
python workflow.py
```

This kicks off the default scenario — a `CWE-89: SQL Injection` alert against `demo_repo/` — and will:

1. **Scout** triages the alert and identifies `demo_repo/app.py::get_user_role`.
2. **Coder** generates a parameterized-query patch as a unified diff.
3. **Tester** applies the patch in isolation, runs `pytest`, and reports pass/fail.
4. If tests fail, the failure trace is fed back to **Coder** and the loop repeats (up to `max_iterations`, default `3`).
5. Once tests pass, you'll be prompted in the terminal:
   ```
   Do you approve committing this patch to a remediation branch? (y/n):
   ```
6. On `y`, the pipeline creates a `fix/cwe-89-<timestamp>` branch, commits the patch, and writes `PR_SUMMARY.md`. If `GITHUB_TOKEN`/`GITHUB_REPOSITORY` are set, it also pushes the branch and opens a draft PR.

### Run an individual agent in isolation

Each agent module is independently runnable for debugging:

```bash
python -m agents.scout    # Triage only
python -m agents.coder    # Triage + patch generation
python -m agents.tester   # Triage + patch + verification
```

### Point the pipeline at your own vulnerability

Edit the `__main__` block of `workflow.py`:

```python
initial_state = PipelineState(
    raw_security_alert="CRITICAL CWE-79: Reflected XSS in the search endpoint.",
    repo_directory="path/to/your/repo",
    max_iterations=5
)
```

---

## Example Output

Running the default demo produces a generated `PR_SUMMARY.md` like this:

```markdown
### Autonomous DevSecOps Remediation Report

**Vulnerability:** `CWE-89: SQL Injection`
**Target:** `demo_repo/app.py` (`get_user_role` lines 18-18)
**Iteration Turns Taken:** `1`

#### Root Cause Analysis
The SQL query is constructed using f-string formatting, directly embedding
user-controlled input without sanitization, leading to SQL injection.

####  Deterministic Verification Signal
- Tests Passed: True
- Exit Code: 0
- Verification Engine: Deterministic Pytest Harness

####  Applied Patch
- cursor.execute(f"SELECT role FROM users WHERE username = '{username}'")
+ cursor.execute("SELECT role FROM users WHERE username = ?", (username,))
```

---

##  Project Structure

```
.
├── workflow.py            # LangGraph state machine: wires agents, routing, HITL & delivery
├── state.py                # Pydantic models: VulnerabilityLocation, TestExecutionResult, PipelineState
├── test_connections.py     # Standalone script to verify Gemini/Groq API keys
├── PR_SUMMARY.md            # Auto-generated report from the most recent successful run
├── agents/
│   ├── scout.py             # Vulnerability triage agent
│   ├── coder.py             # Patch-generation agent
│   └── tester.py            # Patch verification agent
├── gateway/
│   ├── router.py            # Multi-provider LLM gateway with failover + rate limiting
│   ├── guardrails.py        # Secret scrubbing + diff output sanitization
│   └── git_delivery.py      # Branch creation, commit, PR summary, optional draft PR
├── sandbox/
│   ├── patcher.py           # git apply wrapper + backup/rollback helpers
│   └── runner.py            # pytest execution + failure-trace condensation
└── demo_repo/
    ├── app.py                # Intentionally vulnerable demo target (CWE-89)
    └── test_app.py           # Pytest suite, incl. a security regression test
```

---

##  Design Notes

- **Deterministic verification, not LLM self-assessment.** The pipeline never trusts the LLM's opinion that a fix "looks correct" — every patch is judged solely by whether `pytest` exits `0`.
- **Stateless, rollback-safe testing.** `sandbox/patcher.py` always restores the original file in a `finally` block, so a failed or rejected patch attempt never leaves the working tree modified.
- **Bounded autonomy.** The Coder/Tester loop is capped by `max_iterations`; if the model can't produce a passing patch within budget, the pipeline stops and escalates rather than looping forever.
- **A human always has the final word.** Even a fully verified, test-passing patch is never committed without an explicit `y` from a human at the `hitl_approval_node` gate.
- **Provider resilience by design.** The gateway is a single choke point for all model calls, making it straightforward to add new providers, models, or additional guardrails without touching agent logic.

---

##  Roadmap Ideas

- [ ] Support multi-file / multi-hunk patches spanning more than one vulnerable file per alert
- [ ] Pluggable static-analysis alert sources (e.g. Semgrep, CodeQL, Snyk) instead of a raw text alert string
- [ ] Web UI for the human-in-the-loop approval step instead of a terminal prompt
- [ ] Structured logging / tracing of each pipeline run for audit trails
- [ ] Configurable per-CWE test-suite targeting

---

## ⚠️ Disclaimer

`demo_repo/` contains **intentionally vulnerable code** for demonstration and testing purposes only. Do not deploy it or reuse its patterns in production systems.
