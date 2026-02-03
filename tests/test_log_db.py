import os

from src.db.genesis_db import GenesisDB


def test_log_db_crud_and_indexes(tmp_path):
    db_path = tmp_path / "genesis_db.json"
    db = GenesisDB(db_path=str(db_path))

    insert_result = db.execute_sql(
        "INSERT INTO entries (entry_index, id, modality) VALUES (1, 'log-1', 'system')"
    )
    assert insert_result.affected_rows == 1

    select_result = db.execute_sql(
        "SELECT entry_index, id, modality FROM entries WHERE entry_index = 1"
    )
    assert select_result.rows == [
        {"entry_index": 1, "id": "log-1", "modality": "system"}
    ]

    update_result = db.execute_sql(
        "UPDATE entries SET modality = 'audit' WHERE id = 'log-1'"
    )
    assert update_result.affected_rows == 1
    updated = db.execute_sql("SELECT modality FROM entries WHERE id = 'log-1'")
    assert updated.rows == [{"modality": "audit"}]

    delete_result = db.execute_sql("DELETE FROM entries WHERE id = 'log-1'")
    assert delete_result.affected_rows == 1
    empty = db.execute_sql("SELECT id FROM entries WHERE id = 'log-1'")
    assert empty.rows == []

    db.execute_sql(
        "INSERT INTO entries (entry_index, id, modality) VALUES (2, 'log-2', 'system')"
    )
    db.execute_sql(
        "INSERT INTO entries (entry_index, id, modality) VALUES (3, 'log-3', 'system')"
    )
    db._index_by_entry_index = {}
    db._index_by_id = {}
    db._rebuild_indexes()
    assert db._index_by_entry_index[2]["id"] == "log-2"
    assert db._index_by_id["log-3"]["entry_index"] == 3


def test_log_db_atomic_write(tmp_path, monkeypatch):
    db_path = tmp_path / "genesis_db.json"
    calls: list[tuple[str, str]] = []
    original_replace = os.replace

    def tracked_replace(src: str, dst: str) -> None:
        calls.append((src, dst))
        original_replace(src, dst)

    monkeypatch.setattr(os, "replace", tracked_replace)

    db = GenesisDB(db_path=str(db_path))
    db.execute_sql(
        "INSERT INTO entries (entry_index, id, modality) VALUES (1, 'log-atomic', 'system')"
    )

    assert calls
    src, dst = calls[-1]
    assert src.endswith(".tmp")
    assert dst == str(db_path)
    assert db_path.exists()
    assert not (tmp_path / "genesis_db.json.tmp").exists()
