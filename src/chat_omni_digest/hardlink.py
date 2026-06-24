from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ResolvedMedia:
    kind: str
    md5: str
    path: Path | None
    filename: str | None = None
    status: str = "unresolved"
    candidates: list[Path] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class HardlinkResolver:
    """Resolve WeChat media/file md5 values into local filesystem paths.

    Supports both newer `*_hardlink_info_v3` tables and older
    `HardLink*Attribute` + `HardLink*ID` tables where possible.
    """

    def __init__(self, account_dir: str | Path, hardlink_db: str | Path | None = None):
        self.account_dir = Path(account_dir).expanduser()
        self.hardlink_db = (
            Path(hardlink_db).expanduser()
            if hardlink_db
            else self._find_hardlink_db(self.account_dir)
        )
        self._conn: sqlite3.Connection | None = None

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "HardlinkResolver":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def resolve(self, kind: str, md5: str | None) -> ResolvedMedia | None:
        if not md5:
            return None
        md5 = md5.lower()
        if len(md5) != 32:
            return None
        if not self.hardlink_db or not self.hardlink_db.exists():
            return ResolvedMedia(kind=kind, md5=md5, path=None, status="missing-hardlink-db")

        row = self._lookup_v3(kind, md5) or self._lookup_legacy(kind, md5)
        if not row:
            return ResolvedMedia(kind=kind, md5=md5, path=None, status="not-found")

        candidates = self._build_candidates(kind, row)
        existing = next((path for path in candidates if path.exists()), None)
        return ResolvedMedia(
            kind=kind,
            md5=md5,
            path=existing,
            filename=row.get("file_name") or row.get("FileName"),
            status="resolved" if existing else "candidate-only",
            candidates=candidates,
            metadata=row,
        )

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.hardlink_db))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    @staticmethod
    def _find_hardlink_db(account_dir: Path) -> Path | None:
        candidates = [
            account_dir / "hardlink.db",
            account_dir / "hardlink" / "hardlink.db",
            account_dir / "db_storage" / "hardlink" / "hardlink.db",
        ]
        return next((path for path in candidates if path.exists()), candidates[0])

    def _table_exists(self, name: str) -> bool:
        row = self._connect().execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
        return row is not None

    def _first_table_like(self, pattern: str) -> str | None:
        row = self._connect().execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ? ORDER BY name DESC LIMIT 1",
            (pattern,),
        ).fetchone()
        return row["name"] if row else None

    def _lookup_v3(self, kind: str, md5: str) -> dict[str, Any] | None:
        table = self._first_table_like(f"{kind}_hardlink_info%")
        if not table:
            return None
        rows = self._query_md5_table(table, md5)
        if not rows:
            return None
        row = dict(rows[0])
        row["_table"] = table
        for field in ("dir1", "dir2"):
            if field in row:
                row[f"{field}_name"] = self._resolve_dir(row[field])
        return row

    def _lookup_legacy(self, kind: str, md5: str) -> dict[str, Any] | None:
        names = {
            "image": "HardLinkImageAttribute",
            "video": "HardLinkVideoAttribute",
            "file": "HardLinkFileAttribute",
        }
        table = names.get(kind)
        if not table or not self._table_exists(table):
            return None
        rows = self._query_md5_table(table, md5, legacy=True)
        if not rows:
            return None
        row = dict(rows[0])
        row["_table"] = table
        row["DirName1"] = self._resolve_legacy_dir(kind, row.get("DirID1"))
        row["DirName2"] = self._resolve_legacy_dir(kind, row.get("DirID2"))
        return row

    def _query_md5_table(self, table: str, md5: str, legacy: bool = False) -> list[sqlite3.Row]:
        conn = self._connect()
        cols = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]
        md5_col = next((c for c in cols if c.lower() == "md5"), None)
        if not md5_col:
            return []
        attempts = [
            (f"SELECT * FROM {table} WHERE lower({md5_col}) = lower(?) LIMIT 3", (md5,)),
            (f"SELECT * FROM {table} WHERE lower(hex({md5_col})) = lower(?) LIMIT 3", (md5,)),
        ]
        if legacy:
            attempts.insert(0, (f"SELECT * FROM {table} WHERE {md5_col} = ? LIMIT 3", (bytes.fromhex(md5),)))
        for sql, args in attempts:
            try:
                rows = conn.execute(sql, args).fetchall()
            except sqlite3.DatabaseError:
                continue
            if rows:
                return rows
        return []

    def _resolve_dir(self, value: Any) -> str:
        conn = self._connect()
        for table in ("dir2id", "Dir2Id"):
            if not self._table_exists(table):
                continue
            cols = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]
            name_col = "username" if "username" in cols else "dir_name" if "dir_name" in cols else None
            id_col = "rowid" if "rowid" else None
            if not name_col:
                continue
            for sql in (
                f"SELECT {name_col} AS name FROM {table} WHERE rowid=? LIMIT 1",
                f"SELECT {name_col} AS name FROM {table} WHERE dir_id=? LIMIT 1",
                f"SELECT {name_col} AS name FROM {table} WHERE DirID=? LIMIT 1",
            ):
                try:
                    row = conn.execute(sql, (value,)).fetchone()
                except sqlite3.DatabaseError:
                    continue
                if row and row["name"]:
                    return str(row["name"])
        return str(value)

    def _resolve_legacy_dir(self, kind: str, value: Any) -> str:
        if value is None:
            return ""
        prefix = {"image": "HardLinkImageID", "file": "HardLinkFileID", "video": "HardLinkVideoID"}.get(kind)
        if not prefix or not self._table_exists(prefix):
            return str(value)
        try:
            row = self._connect().execute(
                f"SELECT Dir FROM {prefix} WHERE DirID=? LIMIT 1",
                (value,),
            ).fetchone()
        except sqlite3.DatabaseError:
            return str(value)
        return str(row["Dir"]) if row and row["Dir"] else str(value)

    def _build_candidates(self, kind: str, row: dict[str, Any]) -> list[Path]:
        filename = row.get("file_name") or row.get("FileName") or row.get("filename")
        if not filename:
            return []

        dir1 = str(row.get("dir1_name") or row.get("DirName1") or row.get("dir1") or row.get("DirID1") or "")
        dir2 = str(row.get("dir2_name") or row.get("DirName2") or row.get("dir2") or row.get("DirID2") or "")
        table = str(row.get("_table") or "")
        candidates: list[Path] = []

        def add(*parts: str) -> None:
            candidate = self.account_dir.joinpath(*[p for p in parts if p])
            if candidate not in candidates:
                candidates.append(candidate)

        if kind == "image":
            add("msg", "attach", dir1, dir2, "Img", str(filename))
            add("msg", "attach", dir1, dir2, "Rec", "Img", str(filename))
            add("FileStorage", "MsgAttach", dir1, "Image", dir2, str(filename))
            add("FileStorage", "Image", dir1, dir2, str(filename))
        elif kind == "video":
            add("msg", "video", dir1, str(filename))
            add("msg", "video", dir1, dir2, str(filename))
            add("msg", "attach", dir1, dir2, "Rec", "V", str(filename))
            add("FileStorage", "Video", dir1, str(filename))
        elif kind == "file":
            add("msg", "file", dir1, str(filename))
            add("msg", "file", dir1, dir2, str(filename))
            add("FileStorage", "File", dir2, str(filename))
            add("FileStorage", "File", dir1, str(filename))
            if "HardLinkFileAttribute" in table:
                add("FileStorage", "File", dir2, str(filename))
        else:
            add(str(filename))

        for candidate in list(candidates):
            if candidate.suffix:
                continue
            add(str(candidate.relative_to(self.account_dir)) + ".dat")
        return candidates

