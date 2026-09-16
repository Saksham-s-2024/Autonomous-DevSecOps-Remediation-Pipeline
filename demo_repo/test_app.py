import pytest
from app import init_db, get_user_role

@pytest.fixture
def db_conn():
    return init_db()

def test_regular_user_lookup(db_conn):
    """Normal behavior: bob should return developer."""
    assert get_user_role(db_conn, "bob") == "developer"

def test_missing_user_lookup(db_conn):
    """Normal behavior: unknown user returns None."""
    assert get_user_role(db_conn, "charlie") is None

def test_sql_injection_remediation(db_conn):
    """
    SECURITY TEST:
    A SQL injection payload must NOT bypass query logic or leak the admin role.
    On the vulnerable code, this test MUST FAIL.
    """
    malicious_input = "' OR '1'='1"
    role = get_user_role(db_conn, malicious_input)
    
    # In secure code, the username "' OR '1'='1" does not exist, so it returns None.
    assert role is None, f"Vulnerability detected! Malicious payload retrieved role: {role}"
    
def test_strict_parameterized_format():
    """Deterministic check: Ensure parameterized syntax '?' is used and no string formatting remains."""
    with open("demo_repo/app.py", "r") as f:
        content = f.read()
    assert "f\"SELECT" not in content, "Vulnerable f-string query still exists!"
    assert "?" in content, "Query must use '?' parameter placeholders for SQLite safety."