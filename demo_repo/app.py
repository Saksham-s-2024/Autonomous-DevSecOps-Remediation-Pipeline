import sqlite3

def init_db():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role TEXT)")
    cursor.execute("INSERT INTO users (username, role) VALUES ('admin', 'administrator')")
    cursor.execute("INSERT INTO users (username, role) VALUES ('alice', 'developer')")
    conn.commit()
    return conn

def get_user_role(conn, username: str):
    """
    Vulnerable function: Direct f-string interpolation leads to CWE-89 (SQL Injection).
    """
    cursor = conn.cursor()
    query = f"SELECT role FROM users WHERE username = '{username}'"
    cursor.execute(query)
    row = cursor.fetchone()
    return row[0] if row else None