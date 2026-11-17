# Written by Abdulaziz Albastaki in November 2026
# This file is responsible for storing and retrieving facts from SQLite.

import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

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
                conn.execute("BEGIN IMMEDIATE")
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
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS canon_fact_history (
                        world_id TEXT NOT NULL,
                        fact_id TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        payload_json TEXT NOT NULL,
                        PRIMARY KEY (world_id, fact_id, revision)
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS canon_proposals (
                        proposal_id TEXT PRIMARY KEY,
                        world_id TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'approved')),
                        base_revision INTEGER
                    )
                """)
                columns = {
                    column[1]
                    for column in conn.execute("PRAGMA table_info(canon_proposals)")
                }
                if "base_revision" not in columns:
                    conn.execute(
                        "ALTER TABLE canon_proposals ADD COLUMN base_revision INTEGER"
                    )

    def _insert_fact(
        self, conn: sqlite3.Connection, world_id: str, fact: CanonFact
    ) -> None:
        conn.execute(
            """
            INSERT INTO canon_facts
                (fact_id, world_id, subject, predicate, status, revision, payload_json)
            VALUES (?, ?, ?, ?, 'approved', 1, ?)
            """,
            (fact.id, world_id, fact.subject, fact.predicate, fact.model_dump_json()),
        )

    def add_fact(self, world_id: str, fact: CanonFact) -> None:
        """Store a fact that has already been approved."""
        with closing(self._connect()) as conn:
            with conn:
                self._insert_fact(conn, world_id, fact)

    def get_fact(self, fact_id: str) -> CanonFact | None:
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

    def get_facts_by_world(self, world_id: str) -> list[CanonFact]:
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
        self, world_id: str, subject: str
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

    def propose_update(self, world_id: str, fact: CanonFact) -> str:
        """Save a pending proposal for a new fact."""
        proposal_id = uuid4().hex
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO canon_proposals (proposal_id, world_id, payload_json)
                    VALUES (?, ?, ?)
                    """,
                    (proposal_id, world_id, fact.model_dump_json()),
                )
        return proposal_id

    def propose_revision(self, world_id: str, revised_fact: CanonFact) -> str:
        """Save a pending edit based on the current canon revision."""
        proposal_id = uuid4().hex
        with closing(self._connect()) as conn:
            with conn:
                result = conn.execute(
                    """
                    INSERT INTO canon_proposals
                        (proposal_id, world_id, payload_json, base_revision)
                    SELECT ?, world_id, ?, revision
                    FROM canon_facts
                    WHERE world_id = ? AND fact_id = ? AND status = 'approved'
                    """,
                    (
                        proposal_id,
                        revised_fact.model_dump_json(),
                        world_id,
                        revised_fact.id,
                    ),
                )
                if result.rowcount == 0:
                    raise KeyError(
                        f"No approved fact {revised_fact.id!r} in world {world_id!r}"
                    )
        return proposal_id

    def approve_update(self, proposal_id: str) -> None:
        """Apply a pending proposal to accepted canon."""
        with closing(self._connect()) as conn:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    """
                    SELECT world_id, payload_json, status, base_revision
                    FROM canon_proposals
                    WHERE proposal_id = ?
                    """,
                    (proposal_id,),
                ).fetchone()

                if row is None:
                    raise KeyError(f"Unknown proposal: {proposal_id}")

                world_id, payload_json, status, base_revision = row
                if status == "approved":
                    return

                fact = CanonFact.model_validate_json(payload_json)
                if base_revision is None:
                    self._insert_fact(conn, world_id, fact)
                else:
                    self._apply_revision(conn, world_id, fact, base_revision)

                conn.execute(
                    """
                    UPDATE canon_proposals
                    SET status = 'approved'
                    WHERE proposal_id = ?
                    """,
                    (proposal_id,),
                )

    def _apply_revision(
        self,
        conn: sqlite3.Connection,
        world_id: str,
        fact: CanonFact,
        base_revision: int,
    ) -> None:
        archived = conn.execute(
            """
            INSERT INTO canon_fact_history
                (world_id, fact_id, revision, payload_json)
            SELECT world_id, fact_id, revision, payload_json
            FROM canon_facts
            WHERE world_id = ? AND fact_id = ? AND revision = ?
              AND status = 'approved'
            """,
            (world_id, fact.id, base_revision),
        )
        if archived.rowcount == 0:
            raise ValueError(
                f"Stale revision for fact {fact.id!r} in world {world_id!r}. "
                "Propose the edit again against the current canon."
            )

        conn.execute(
            """
            UPDATE canon_facts
            SET subject = ?, predicate = ?, payload_json = ?, revision = revision + 1
            WHERE world_id = ? AND fact_id = ?
            """,
            (fact.subject, fact.predicate, fact.model_dump_json(), world_id, fact.id),
        )

    def get_fact_history(
        self, world_id: str, fact_id: str
    ) -> list[tuple[int, CanonFact]]:
        """Return superseded versions in revision order."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT revision, payload_json
                FROM canon_fact_history
                WHERE world_id = ? AND fact_id = ?
                ORDER BY revision
                """,
                (world_id, fact_id),
            ).fetchall()

        return [
            (revision, CanonFact.model_validate_json(payload_json))
            for revision, payload_json in rows
        ]
