# Written by Abdulaziz Albastaki in November 2026
# This file is responsible for storing and retrieving facts from SQLite


import sqlite3
from pathlib import Path
from contextlib import closing

from shared.schemas import CanonFact

class CanonStore:
    def __init__(self, db_path="data/canon.db"):
        self.db_path = str(db_path)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _create_tables(self):
        with closing(self._connect()) as conn:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS canon_facts (
                        fact_id TEXT PRIMARY KEY,
                        world_id TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        predicate TEXT NOT NULL,
                        status TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        payload_json TEXT NOT NULL
                    )
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_facts_world
                    ON canon_facts(world_id)
                """)


    def add_fact(self, world_id: str, fact: CanonFact):
        """Store a fact that has already been approved."""

        with closing(self._connect()) as conn:
            with conn:
                conn.execute("""
                    INSERT INTO canon_facts
                    (fact_id, world_id, subject, predicate,
                    status, revision, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    fact.id,
                    world_id,
                    fact.subject,
                    fact.predicate,
                    "approved",
                    1,
                    fact.model_dump_json()
                ))


    def get_fact(self, fact_id: str):
        """Retrieve a fact by its unique ID."""

        with closing(self._connect()) as conn:
            row = conn.execute("""
                SELECT payload_json
                FROM canon_facts
                WHERE fact_id = ? AND status = 'approved'
            """, (fact_id,)).fetchone()

        if row is None:
            return None

        return CanonFact.model_validate_json(row[0])

    def get_facts_by_world(self, world_id: str):
        """Retrieve all approved facts from a world."""

        with closing(self._connect()) as conn:
            rows = conn.execute("""
                SELECT payload_json
                FROM canon_facts
                WHERE world_id = ? AND status = 'approved'
                ORDER BY fact_id
            """, (world_id,)).fetchall()

        return [
            CanonFact.model_validate_json(row[0])
            for row in rows
        ]

    def get_facts_by_subject(
        self,
        world_id: str,
        subject: str
    ) -> list[CanonFact]:
        """Retrieve approved facts about a specific subject."""

        with closing(self._connect()) as conn:
            rows = conn.execute("""
                SELECT payload_json
                FROM canon_facts
                WHERE world_id = ?
                AND subject = ?
                AND status = 'approved'
                ORDER BY fact_id
            """, (world_id, subject)).fetchall()

        return [
            CanonFact.model_validate_json(row[0])
            for row in rows
        ]
