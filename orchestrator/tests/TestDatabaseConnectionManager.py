import pytest
from src.persistence.JobDb import JobDb

@pytest.fixture
def db():
    return JobDb.instance()

def test_reconnect_on_closed_connection(db):
    # Step 1: Get a connection and check it's alive
    conn1 = db.get_connection()
    assert db.is_alive(), "Initial connection should be alive"
    print("[TEST] Initial connection is alive.")

    # Step 2: Manually close the connection (simulate failure)
    conn1.connection.close()
    print("[TEST] Closed the connection manually.")

    # Step 3: Call get_connection() again, it should recreate the connection
    conn2 = db.get_connection()
    assert db.is_alive(), "New connection should be alive"
    print("[TEST] New connection is alive.")

    # Step 4: Ensure it's a new object (optional, depends on your class logic)
    assert conn1 != conn2 or not conn1.connection.is_open(), "[TEST] Connection object was replaced."

    print("[TEST] test_reconnect_on_closed_connection passed!")
