"""Setup wizard endpoint tests."""

from types import SimpleNamespace


async def test_setup_init_db_blocked_when_already_complete(client, mock_db):
    mock_db.get.return_value = SimpleNamespace(is_complete=True, steps_completed=["db_init"])
    response = await client.post("/setup/init-db")
    assert response.status_code == 403
    assert "already complete" in response.json().get("detail", "").lower()


async def test_setup_create_admin_blocked_when_already_complete(client, mock_db):
    mock_db.get.return_value = SimpleNamespace(is_complete=True, steps_completed=["db_init"])
    response = await client.post(
        "/setup/create-admin",
        json={"email": "admin@example.com", "password": "password123"},
    )
    assert response.status_code == 403
    assert "already complete" in response.json().get("detail", "").lower()


async def test_setup_status_reports_complete_state(client, mock_db):
    mock_db.get.return_value = SimpleNamespace(is_complete=True, steps_completed=["db_init", "admin_created"])
    response = await client.get("/setup/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["is_complete"] is True
    assert "db_init" in payload["steps_completed"]
