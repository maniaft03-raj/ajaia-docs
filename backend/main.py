import os
from fastapi.staticfiles import StaticFiles
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


app = FastAPI(title="Ajaia Docs API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE = Path(
    os.environ.get(
        "DATABASE_PATH",
        str(Path(__file__).with_name("documents.db")),
    )
)
DATABASE.parent.mkdir(parents=True, exist_ok=True)


USERS = [
    {"id": "mani", "name": "Mani", "email": "mani@example.com"},
    {"id": "alex", "name": "Alex", "email": "alex@example.com"},
    {"id": "sam", "name": "Sam", "email": "sam@example.com"},
]


@contextmanager
def database():
    connection = sqlite3.connect(DATABASE, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


with database() as connection:
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS shares (
            document_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('viewer', 'editor')),
            PRIMARY KEY (document_id, user_id),
            FOREIGN KEY (document_id)
                REFERENCES documents(id) ON DELETE CASCADE
        );
    """)


class DocumentInput(BaseModel):
    title: str = Field(default="Untitled document", max_length=200)
    content: dict = Field(
        default_factory=lambda: {
            "type": "doc",
            "content": [{"type": "paragraph"}],
        }
    )


class ShareInput(BaseModel):
    user_id: str
    role: Literal["viewer", "editor"]


def current_user(x_user_id: str = Header(default="mani")):
    if x_user_id not in {user["id"] for user in USERS}:
        raise HTTPException(status_code=401, detail="Unknown demo user")
    return x_user_id


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def encode_content(content):
    if content.get("type") != "doc":
        raise HTTPException(status_code=422, detail="Invalid document content")
    encoded = json.dumps(content)
    if len(encoded.encode("utf-8")) > 2_000_000:
        raise HTTPException(status_code=413, detail="Document is too large")
    return encoded


def accessible_document(connection, document_id, user_id):
    row = connection.execute(
        """
        SELECT d.*,
            CASE WHEN d.owner_id = ? THEN 'owner' ELSE s.role END AS role
        FROM documents d
        LEFT JOIN shares s ON s.document_id = d.id AND s.user_id = ?
        WHERE d.id = ?
        """,
        (user_id, user_id, document_id),
    ).fetchone()

    if row is None or row["role"] is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return row


def serialize(row):
    document = dict(row)
    document["content"] = json.loads(document["content"])
    return document


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/users")
def list_users():
    return USERS


@app.get("/documents")
def list_documents(user_id: str = Depends(current_user)):
    with database() as connection:
        rows = connection.execute(
            """
            SELECT d.*,
                CASE WHEN d.owner_id = ? THEN 'owner' ELSE s.role END AS role
            FROM documents d
            LEFT JOIN shares s ON s.document_id = d.id AND s.user_id = ?
            WHERE d.owner_id = ? OR s.user_id = ?
            ORDER BY d.updated_at DESC
            """,
            (user_id, user_id, user_id, user_id),
        ).fetchall()
        return [serialize(row) for row in rows]


@app.post("/documents", status_code=201)
def create_document(
    payload: DocumentInput,
    user_id: str = Depends(current_user),
):
    document_id = str(uuid4())
    content = encode_content(payload.content)

    with database() as connection:
        connection.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?)",
            (
                document_id,
                payload.title.strip() or "Untitled document",
                content,
                user_id,
                timestamp(),
            ),
        )
        return serialize(
            accessible_document(connection, document_id, user_id)
        )


@app.get("/documents/{document_id}")
def get_document(
    document_id: str,
    user_id: str = Depends(current_user),
):
    with database() as connection:
        return serialize(
            accessible_document(connection, document_id, user_id)
        )


@app.put("/documents/{document_id}")
def update_document(
    document_id: str,
    payload: DocumentInput,
    user_id: str = Depends(current_user),
):
    with database() as connection:
        document = accessible_document(connection, document_id, user_id)

        if document["role"] not in ("owner", "editor"):
            raise HTTPException(status_code=403, detail="Read-only access")

        connection.execute(
            """
            UPDATE documents
            SET title = ?, content = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.title.strip() or "Untitled document",
                encode_content(payload.content),
                timestamp(),
                document_id,
            ),
        )
        return serialize(
            accessible_document(connection, document_id, user_id)
        )


@app.get("/documents/{document_id}/shares")
def list_shares(
    document_id: str,
    user_id: str = Depends(current_user),
):
    with database() as connection:
        document = accessible_document(connection, document_id, user_id)

        if document["role"] != "owner":
            raise HTTPException(status_code=403, detail="Owner access required")

        rows = connection.execute(
            "SELECT user_id, role FROM shares WHERE document_id = ?",
            (document_id,),
        ).fetchall()
        return [dict(row) for row in rows]


@app.post("/documents/{document_id}/shares")
def share_document(
    document_id: str,
    payload: ShareInput,
    user_id: str = Depends(current_user),
):
    if payload.user_id not in {user["id"] for user in USERS}:
        raise HTTPException(status_code=400, detail="Unknown recipient")

    with database() as connection:
        document = accessible_document(connection, document_id, user_id)

        if document["role"] != "owner":
            raise HTTPException(status_code=403, detail="Only owners can share")

        if payload.user_id == document["owner_id"]:
            raise HTTPException(status_code=400, detail="Owner already has access")

        connection.execute(
            """
            INSERT INTO shares (document_id, user_id, role)
            VALUES (?, ?, ?)
            ON CONFLICT(document_id, user_id)
            DO UPDATE SET role = excluded.role
            """,
            (document_id, payload.user_id, payload.role),
        )
        return {"user_id": payload.user_id, "role": payload.role}


@app.delete("/documents/{document_id}/shares/{recipient_id}")
def revoke_share(
    document_id: str,
    recipient_id: str,
    user_id: str = Depends(current_user),
):
    with database() as connection:
        document = accessible_document(connection, document_id, user_id)

        if document["role"] != "owner":
            raise HTTPException(status_code=403, detail="Only owners can revoke")

        connection.execute(
            "DELETE FROM shares WHERE document_id = ? AND user_id = ?",
            (document_id, recipient_id),
        )
        return {"status": "revoked"}

FRONTEND_DIST = (
    Path(__file__).resolve().parent.parent / "frontend--" / "dist"
)

if FRONTEND_DIST.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIST), html=True),
        name="frontend",
    )

