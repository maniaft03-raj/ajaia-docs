Architecture
Frontend:
React and Vite, with Tiptap for rich-text editing.
Documents are represented as Tiptap JSON.
The production frontend calls the API on the same origin.
Backend:
FastAPI validates requests and enforces document permissions.
SQLite stores documents, ownership, and sharing roles.
Database operations use parameterized SQL.
Permissions:
Owners can edit and manage sharing.
Editors can read and save changes.
Viewers can read but cannot save.
Revoked users lose API access.
X-User-Id selects a simulated identity; it is not authentication.
Deployment:
A multi-stage Dockerfile builds the frontend and packages the API.
FastAPI serves both API routes and the compiled frontend.
Railway provides the public domain.
SQLite is configured to use the attached /data volume.
Tradeoffs:
SQLite and simulated users keep the assignment focused.
Production improvements would include real authentication,
conflict detection, backups, and richer automated coverage.
