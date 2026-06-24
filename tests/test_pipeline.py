import json
import sqlite3
from pathlib import Path

from chat_omni_digest.cli import main


def test_pipeline_resolves_file_attachment(tmp_path: Path):
    account = tmp_path / "account"
    file_path = account / "msg" / "file" / "dirA" / "report.txt"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("hello attachment", encoding="utf-8")

    db_path = tmp_path / "hardlink.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE dir2id(username TEXT)")
    conn.execute("INSERT INTO dir2id(rowid, username) VALUES (1, 'dirA')")
    conn.execute(
        "CREATE TABLE file_hardlink_info_v3(md5 TEXT, file_size INTEGER, type INTEGER, file_name TEXT, dir1 INTEGER, dir2 INTEGER, extra_buffer BLOB, modify_time INTEGER)"
    )
    conn.execute(
        "INSERT INTO file_hardlink_info_v3(md5, file_size, type, file_name, dir1, dir2) VALUES (?, ?, ?, ?, ?, ?)",
        ("abcdefabcdefabcdefabcdefabcdefab", 16, 0, "report.txt", 1, 0),
    )
    conn.commit()
    conn.close()

    source = tmp_path / "chat.json"
    source.write_text(
        json.dumps(
            {
                "group": {"name": "Demo"},
                "messages": [
                    {
                        "local_id": 1,
                        "time": "2026-06-24 10:00:00",
                        "sender": "Alice",
                        "type": "文件",
                        "content": "<msg><appmsg><title>report.txt</title><appattach><filemd5>abcdefabcdefabcdefabcdefabcdefab</filemd5></appattach></appmsg></msg>",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out"
    assert main(["pipeline", str(source), "--account-dir", str(account), "--hardlink-db", str(db_path), "--output-dir", str(out)]) == 0
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "hello attachment" in report

