from fastapi.testclient import TestClient

from src.api import log_api
from src.db.genesis_db import GenesisDB
from src.visualization import server


def test_logs_crud_and_ws_event():
    server._LOGS = []
    server._NEXT_LOG_ID = 1

    with TestClient(server.app) as client:
        with client.websocket_connect("/ws") as websocket:
            initial = websocket.receive_json()
            assert initial["type"] == "initial_state"

            create_response = client.post("/logs", json={"message": "log created", "level": "info"})
            assert create_response.status_code == 200
            log_entry = create_response.json()
            assert log_entry["id"] == 1

            list_logs = client.get("/logs").json()
            list_logs_api = client.get("/api/logs").json()
            assert list_logs == list_logs_api

            event_message = websocket.receive_json()
            assert event_message["type"] == "event"
            assert event_message["event"]["message"] == "log created"

            update_response = client.put(
                f"/logs/{log_entry['id']}",
                json={"message": "log updated", "level": "warning"},
            )
            assert update_response.status_code == 200
            assert update_response.json()["message"] == "log updated"

            delete_response = client.delete(f"/logs/{log_entry['id']}")
            assert delete_response.status_code == 200
            assert client.get("/logs").json() == []


def test_sql_api_parity(tmp_path):
    db_path = tmp_path / "genesis_db.json"
    db = GenesisDB(db_path=str(db_path))
    db.execute_sql(
        "INSERT INTO entries (entry_index, id, modality) VALUES (1, 'log-1', 'system')"
    )
    db.execute_sql(
        "INSERT INTO entries (entry_index, id, modality) VALUES (2, 'log-2', 'system')"
    )

    app = log_api.create_app(db_path=str(db_path))
    with TestClient(app) as client:
        sql = "SELECT entry_index, id, modality FROM entries ORDER BY entry_index"
        api_response = client.post("/query", json={"sql": sql, "params": []})
        assert api_response.status_code == 200
        payload = api_response.json()

    expected = db.execute_sql(sql)
    assert payload["rows"] == expected.rows
    assert payload["columns"] == expected.columns
    assert payload["row_count"] == len(expected.rows)
    assert payload["operation"] == expected.operation
