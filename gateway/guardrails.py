import re

# Regex patterns matching common secret and credential signatures
SECRET_PATTERNS = [
    r"(?i)(api[_-]?key|secret|token|password|auth)\s*[:=]\s*['\"][A-Za-z0-9_\-\.]{8,}['\"]",
    r"ghp_[A-Za-z0-9]{36}",                # GitHub Personal Access Token
    r"AIza[0-9A-Za-z-_]{35}",              # Google Cloud / AI Studio API Key
    r"gsk_[A-Za-z0-9]{48}",                # Groq Cloud API Key
    r"sk-lf-[A-Za-z0-9_\-]{32,}",          # Langfuse Secret Key
]

def scrub_secrets(text: str) -> str:
    """
    Inbound Guardrail: Scans text for sensitive tokens and redacts them
    before they are dispatched to external LLM APIs.
    """
    scrubbed = text
    for pattern in SECRET_PATTERNS:
        scrubbed = re.sub(pattern, "[REDACTED_SECRET]", scrubbed)
    return scrubbed

def sanitize_diff_output(raw_output: str) -> str:
    """
    Outbound Guardrail: Strips conversational markdown wrapper text and code fences,
    ensuring the diff begins with valid git diff headers (--- a/ or diff --git).
    """
    cleaned = re.sub(r"^```(?:diff)?\s*", "", raw_output.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()

    header_idx = cleaned.find("--- a/")
    if header_idx == -1:
        header_idx = cleaned.find("diff --git")

    if header_idx != -1:
        cleaned = cleaned[header_idx:]

    return cleaned.strip()