from __future__ import annotations

import json
import os
from typing import Any


DEFAULT_DB_PATH = os.getenv("GENESIS_DB_PATH", "data/genesis_db.json")


def _mock_patient_rows() -> list[dict[str, Any]]:
    base_timestamp = 1710000000.0
    patients = [
        {
            "id": "patient-001",
            "name": "Avery Johnson",
            "age": 42,
            "sex": "F",
            "diagnosis": "Type 2 Diabetes",
            "last_visit": "2024-06-12",
            "status": "Stable",
            "assigned_clinician": "Dr. Patel",
        },
        {
            "id": "patient-002",
            "name": "Miles Chen",
            "age": 57,
            "sex": "M",
            "diagnosis": "Hypertension",
            "last_visit": "2024-05-28",
            "status": "Monitoring",
            "assigned_clinician": "Dr. Rivera",
        },
        {
            "id": "patient-003",
            "name": "Sofia Alvarez",
            "age": 36,
            "sex": "F",
            "diagnosis": "Asthma",
            "last_visit": "2024-06-02",
            "status": "Controlled",
            "assigned_clinician": "Dr. Kim",
        },
        {
            "id": "patient-004",
            "name": "Noah Williams",
            "age": 63,
            "sex": "M",
            "diagnosis": "Chronic Kidney Disease",
            "last_visit": "2024-05-15",
            "status": "Care plan",
            "assigned_clinician": "Dr. Shah",
        },
        {
            "id": "patient-005",
            "name": "Priya Singh",
            "age": 29,
            "sex": "F",
            "diagnosis": "Migraine",
            "last_visit": "2024-06-18",
            "status": "Follow-up",
            "assigned_clinician": "Dr. Osei",
        },
    ]

    rows: list[dict[str, Any]] = []
    for index, patient in enumerate(patients, start=1):
        metadata_json = json.dumps({"patient": patient}, indent=None)
        rows.append(
            {
                "entry_index": index,
                "id": patient["id"],
                "modality": "patient",
                "octave": 1,
                "fundamental_freq": 440.0 + index,
                "resonance_strength": 70 + index,
                "frequency_band": 2,
                "position_x": float(index),
                "position_y": float(index) * 1.2,
                "position_z": float(index) * 0.8,
                "coherence": 0.85,
                "timestamp": base_timestamp + (index * 86400),
                "current_state": "Active",
                "wavecube_x": None,
                "wavecube_y": None,
                "wavecube_z": None,
                "wavecube_w": None,
                "cross_modal_links": "",
                "cross_modal_links_json": "[]",
                "metadata_json": metadata_json,
                "proto_identity_json": "null",
                "frequency_json": "null",
                "position_json": "null",
                "mip_levels_json": "[]",
            }
        )
    return rows


def seed_mock_patients(db_path: str) -> bool:
    if os.path.exists(db_path):
        try:
            with open(db_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, list) and payload:
                return False
        except json.JSONDecodeError:
            pass

    rows = _mock_patient_rows()
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    tmp_path = f"{db_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2)
    os.replace(tmp_path, db_path)
    return True


if __name__ == "__main__":
    seed_mock_patients(DEFAULT_DB_PATH)
