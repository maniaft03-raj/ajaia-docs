import sqlite3

from fastapi.testclient import TestClient

import main


def test_document_permissions(tmp_path, monkeypatch):
    # Use an isolated database, never the app's real documents.
    test_database = tmp_path / "test.db"
    monkeypatch.setattr(main, "DATABASE", test_database)

    with sqlite3.connect(test_database) as connection:
        connection.executescript("""
            CREATE TABLE documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE shares (
                document_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('viewer', 'editor')),
                PRIMARY KEY (document_id, user_id),
                FOREIGN KEY (document_id)
                    REFERENCES documents(id) ON DELETE CASCADE
            );
        """)

    with TestClient(main.app) as client:
        owner = {"X-User-Id": "mani"}
        recipient = {"X-User-Id": "alex"}

        payload = {
            "title": "Permissions test",
            "content": {
                "type": "doc",
                "content": [{"type": "paragraph"}],
            },
        }

        # Create a document as its owner.
        response = client.post(
            "/documents", headers=owner, json=payload
        )
        assert response.status_code == 201
        document_id = response.json()["id"]
        path = f"/documents/{document_id}"

        # An unshared document must not be accessible to Alex.
        assert client.get(path, headers=recipient).status_code == 404

        # Grant read-only access.
        response = client.post(
            f"{path}/shares",
            headers=owner,
            json={"user_id": "alex", "role": "viewer"},
        )
        assert response.status_code == 200
        assert client.get(path, headers=recipient).status_code == 200

        # A viewer must not be allowed to save or share.
        assert client.put(
            path, headers=recipient, json=payload
        ).status_code == 403

        assert client.post(
            f"{path}/shares",
            headers=recipient,
            json={"user_id": "sam", "role": "viewer"},
        ).status_code == 403

        # Upgrade Alex to editor.
        response = client.post(
            f"{path}/shares",
            headers=owner,
            json={"user_id": "alex", "role": "editor"},
        )
        assert response.status_code == 200

        payload["title"] = "Updated by Alex"
        response = client.put(
            path, headers=recipient, json=payload
        )
        assert response.status_code == 200

        # The owner must see the saved update.
        response = client.get(path, headers=owner)
        assert response.json()["title"] == "Updated by Alex"

        # Revoking access must block reads and writes.
        response = client.delete(
            f"{path}/shares/alex", headers=owner
        )
        assert response.status_code == 200
        assert client.get(path, headers=recipient).status_code == 404
        assert client.put(
            path, headers=recipient, json=payload
        ).status_code == 404
