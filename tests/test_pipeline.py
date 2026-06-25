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


def test_pipeline_resolves_mac_wechat_image_resource(tmp_path: Path):
    account = tmp_path / "account"
    image_path = account / "msg" / "attach" / "chatabc" / "2026-06" / "Img" / "0123456789abcdef0123456789abcdef_t.dat"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(bytes.fromhex("070856320807000400000000000001d8"))

    resource_db = tmp_path / "message_resource.db"
    conn = sqlite3.connect(resource_db)
    conn.execute(
        "CREATE TABLE MessageResourceInfo(message_id INTEGER PRIMARY KEY, chat_id INTEGER, sender_id INTEGER, message_local_type INTEGER, message_create_time INTEGER, message_local_id INTEGER, message_svr_id INTEGER, message_origin_source INTEGER, packed_info BLOB)"
    )
    conn.execute(
        "INSERT INTO MessageResourceInfo(message_id, message_local_type, message_local_id, message_svr_id, packed_info) VALUES (?, ?, ?, ?, ?)",
        (1, 3, 7, 123456, b'\\x12\"\\n 0123456789abcdef0123456789abcdef'),
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
                        "local_id": 7,
                        "server_id": 123456,
                        "table": "Msg_chatabc",
                        "time": "2026-06-25 01:14:56",
                        "sender": "Alice",
                        "type": "图片",
                        "content": "[图片]",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    out = tmp_path / "out"
    assert (
        main(
            [
                "pipeline",
                str(source),
                "--account-dir",
                str(account),
                "--message-resource-db",
                str(resource_db),
                "--output-dir",
                str(out),
                "--copy-media",
            ]
        )
        == 0
    )
    resolved = json.loads((out / "conversation.resolved.json").read_text(encoding="utf-8"))
    attachment = resolved["messages"][0]["attachments"][0]
    assert attachment["status"] == "resolved"
    assert attachment["metadata"]["resource_index"] == "0123456789abcdef0123456789abcdef"
    assert Path(attachment["path"]).exists()
