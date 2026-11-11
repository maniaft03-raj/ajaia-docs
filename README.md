Ajaia Docs
Live app:
https://ajaia-docs-production-963c2a7f.up.railway.app
Repository:
https://github.com/maniaft03-raj/ajaia-docs
Requirements:
Node.js 22, Python 3.12, and npm.
Backend setup, from the project root:
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
Frontend setup, in a separate terminal from the project root:
cd frontend--
npm.cmd install
npm.cmd run dev
Open the local URL printed by Vite.
Automated test, from backend:
.\.venv\Scripts\python.exe -m pytest -q
Production frontend build, from frontend--:
npm.cmd run build
Demo users:
Mani, Alex, and Sam. Select a user from the sidebar.
No registration or password is required.
Features:
Create and rename documents; rich-text formatting; manual saving;
reopen saved documents; import .txt files smaller than 1 MB;
share with viewer or editor access; update and revoke access.
Deployment:
Railway builds the root Dockerfile.
DATABASE_PATH=/data/documents.db
A persistent volume is mounted at /data.
Limitations:
Demo identities are simulated, not secure authentication.
Import supports plain text only.
Collaboration uses manual save and reopen, not real-time synchronization.
Concurrent saves use last-write-wins behavior.
The deployment depends on available Railway trial credit.
