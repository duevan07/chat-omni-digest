import sqlite3
from pathlib import Path

from chat_omni_digest.hardlink import HardlinkResolver


def test_resolve_v3_image(tmp_path: Path):
    account = tmp_path / "account"
    image_path = account / "msg" / "attach" / "dirA" / "2026-06" / "Img" / "pic.dat"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake")

    db_path = tmp_path / "hardlink.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE dir2id(username TEXT)")
    conn.execute("INSERT INTO dir2id(rowid, username) VALUES (1, 'dirA')")
    conn.execute("INSERT INTO dir2id(rowid, username) VALUES (2, '2026-06')")
    conn.execute(
        "CREATE TABLE image_hardlink_info_v3(md5 TEXT, file_size INTEGER, type INTEGER, file_name TEXT, dir1 INTEGER, dir2 INTEGER, extra_buffer BLOB, modify_time INTEGER)"
    )
    conn.execute(
        "INSERT INTO image_hardlink_info_v3(md5, file_size, type, file_name, dir1, dir2) VALUES (?, ?, ?, ?, ?, ?)",
        ("0123456789abcdef0123456789abcdef", 4, 0, "pic.dat", 1, 2),
    )
    conn.commit()
    conn.close()

    resolver = HardlinkResolver(account, db_path)
    result = resolver.resolve("image", "0123456789abcdef0123456789abcdef")
    assert result is not None
    assert result.status == "resolved"
    assert result.path == image_path

