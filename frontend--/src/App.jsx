import { useEffect, useState } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import './App.css'

const API =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV
    ? 'http://localhost:8000'
    : window.location.origin)

const USERS = [
  { id: 'mani', name: 'Mani' },
  { id: 'alex', name: 'Alex' },
  { id: 'sam', name: 'Sam' },
]

export default function App() {
  const [user, setUser] = useState('mani')
  const [documents, setDocuments] = useState([])
  const [active, setActive] = useState(null)
  const [title, setTitle] = useState('')
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [shares, setShares] = useState([])
  const [recipient, setRecipient] = useState('alex')
  const [shareRole, setShareRole] = useState('viewer')

  const canEdit = active?.role === 'owner' || active?.role === 'editor'

  const editor = useEditor({
    extensions: [StarterKit],
    content: '',
    editable: Boolean(canEdit) && !busy,

    onUpdate: () => {
      setDirty(true)
      setMessage('Unsaved changes')
    },
  })

  async function request(path, method = 'GET', body, identity = user) {
    const response = await fetch(`${API}${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': identity,
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    })

    const data = await response.json().catch(() => null)

    if (!response.ok) {
      throw new Error(
        typeof data?.detail === 'string'
          ? data.detail
          : `Request failed (${response.status})`
      )
    }

    return data
  }

  useEffect(() => {
    let cancelled = false

    setActive(null)
    setTitle('')
    setDirty(false)
    setShares([])
    setDocuments([])
    setBusy(true)
    setMessage('Loading documents…')

    request('/documents', 'GET', undefined, user)
      .then((data) => {
        if (!cancelled) {
          setDocuments(data)
          setMessage('')
        }
      })
      .catch((error) => {
        if (!cancelled) setMessage(error.message)
      })
      .finally(() => {
        if (!cancelled) setBusy(false)
      })

    return () => {
      cancelled = true
    }
  }, [user])

  useEffect(() => {
    
  }, [editor, canEdit, busy])

  function confirmDiscard() {
    return !dirty || window.confirm('Discard your unsaved changes?')
  }

  async function perform(action) {
    setBusy(true)
    try {
      await action()
    } catch (error) {
      setMessage(error.message || 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  function selectDocument(document) {
    setActive(document)
    setTitle(document.title)
    editor.commands.setContent(document.content, { emitUpdate: false })
    setDirty(false)
    setShares([])
    setMessage(
      document.role === 'viewer'
        ? 'Read-only access'
        : 'Saved to database'
    )
  }

  async function refreshList() {
    setDocuments(await request('/documents'))
  }

  function openDocument(id) {
    if (!confirmDiscard()) return

    perform(async () => {
      const document = await request(`/documents/${id}`)
      selectDocument(document)

      if (document.role === 'owner') {
        setShares(await request(`/documents/${id}/shares`))
      }
    })
  }

  function createDocument() {
    if (!confirmDiscard()) return

    perform(async () => {
      const document = await request('/documents', 'POST', {
        title: 'Untitled document',
        content: {
          type: 'doc',
          content: [{ type: 'paragraph' }],
        },
      })

      selectDocument(document)
      setDocuments((previous) => [document, ...previous])
    })
  }

  function saveDocument() {
    if (!active || !canEdit) return

    perform(async () => {
      const updated = await request(`/documents/${active.id}`, 'PUT', {
        title: title.trim() || 'Untitled document',
        content: editor.getJSON(),
      })

      setActive(updated)
      setTitle(updated.title)
      setDirty(false)
      setDocuments((previous) =>
        previous.map((document) =>
          document.id === updated.id ? updated : document
        )
      )
      setMessage('Saved to database')
    })
  }

  async function importFile(event) {
    const file = event.target.files?.[0]
    event.target.value = ''

    if (!file || !confirmDiscard()) return

    if (!file.name.toLowerCase().endsWith('.txt')) {
      setMessage('Only .txt files are supported.')
      return
    }

    if (file.size > 1024 * 1024) {
      setMessage('The file must be smaller than 1 MB.')
      return
    }

    perform(async () => {
      const text = await file.text()
      const document = await request('/documents', 'POST', {
        title: file.name.replace(/\.txt$/i, '').slice(0, 200),
        content: {
          type: 'doc',
          content: text.split(/\r?\n/).map((line) => ({
            type: 'paragraph',
            ...(line
              ? { content: [{ type: 'text', text: line }] }
              : {}),
          })),
        },
      })

      selectDocument(document)
      setDocuments((previous) => [document, ...previous])
    })
  }

  function grantAccess() {
    perform(async () => {
      await request(`/documents/${active.id}/shares`, 'POST', {
        user_id: recipient,
        role: shareRole,
      })

      setShares(await request(`/documents/${active.id}/shares`))
      setMessage('Sharing permissions updated')
    })
  }

  function revokeAccess(id) {
    perform(async () => {
      await request(`/documents/${active.id}/shares/${id}`, 'DELETE')
      setShares(await request(`/documents/${active.id}/shares`))
      setMessage('Access revoked')
    })
  }

  function changeUser(event) {
    if (!confirmDiscard()) return

    const nextUser = event.target.value
    setRecipient(USERS.find((person) => person.id !== nextUser).id)
    setUser(nextUser)
  }

  const tools = [
    ['Bold', () => editor.chain().focus().toggleBold().run()],
    ['Italic', () => editor.chain().focus().toggleItalic().run()],
    ['Underline', () => editor.chain().focus().toggleUnderline().run()],
    ['Heading', () =>
      editor.chain().focus().toggleHeading({ level: 2 }).run()],
    ['Paragraph', () => editor.chain().focus().setParagraph().run()],
    ['Bullets', () => editor.chain().focus().toggleBulletList().run()],
    ['Numbers', () => editor.chain().focus().toggleOrderedList().run()],
    ['Undo', () => editor.chain().focus().undo().run()],
    ['Redo', () => editor.chain().focus().redo().run()],
  ]

  return (
    <div className="layout">
      <aside className="sidebar">
        <h2>Ajaia Docs</h2>
        <p className="muted">Your document workspace</p>

        <label className="field">
          Demo user
          <select value={user} onChange={changeUser} disabled={busy}>
            {USERS.map((person) => (
              <option key={person.id} value={person.id}>
                {person.name}
              </option>
            ))}
          </select>
        </label>

        <p className="demo-note">
          Demo identities only. This is not secure login.
        </p>

        <button
          className="primary wide"
          disabled={busy || !editor}
          onClick={createDocument}
        >
          + New document
        </button>

        <label className="upload">
          Import .txt file
          <input
            type="file"
            accept=".txt,text/plain"
            disabled={busy || !editor}
            onChange={importFile}
          />
        </label>

        <button
          className="wide"
          disabled={busy}
          onClick={() => perform(refreshList)}
        >
          Refresh document list
        </button>

        <div className="doc-list">
          {!documents.length && !busy && (
            <p className="muted">No accessible documents yet.</p>
          )}

          {documents.map((document) => (
            <button
              key={document.id}
              disabled={busy || !editor}
              className={`doc-item ${
                active?.id === document.id ? 'selected' : ''
              }`}
              onClick={() => openDocument(document.id)}
            >
              <strong>{document.title}</strong>
              <small>{document.role}</small>
            </button>
          ))}
        </div>
      </aside>

      <main>
        <p className="status" role="status">
          {busy ? 'Working…' : message}
        </p>

        {active ? (
          <>
            <div className="topbar">
              <input
                className="title"
                aria-label="Document title"
                value={title}
                maxLength={200}
                disabled={!canEdit || busy}
                onChange={(event) => {
                  setTitle(event.target.value)
                  setDirty(true)
                  setMessage('Unsaved changes')
                }}
              />

              <button
                className="primary"
                disabled={!canEdit || busy}
                onClick={saveDocument}
              >
                Save
              </button>
            </div>

            <p className="muted">
              Access: {active.role}
              {dirty ? ' · Unsaved changes' : ''}
            </p>

            <div className="toolbar" aria-label="Formatting tools">
              {tools.map(([label, action]) => (
                <button
                  key={label}
                  disabled={!editor || !canEdit || busy}
                  onClick={action}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="paper">
              <EditorContent editor={editor} />
            </div>

            {active.role === 'owner' && (
              <section className="sharing">
                <h3>Share this document</h3>
                <p className="muted">
                  Viewers can read. Editors can change and save.
                  Only the owner can manage access.
                </p>

                <div className="share-controls">
                  <select
                    aria-label="Share with"
                    value={recipient}
                    disabled={busy}
                    onChange={(event) => setRecipient(event.target.value)}
                  >
                    {USERS.filter((person) => person.id !== user).map(
                      (person) => (
                        <option key={person.id} value={person.id}>
                          {person.name}
                        </option>
                      )
                    )}
                  </select>

                  <select
                    aria-label="Permission"
                    value={shareRole}
                    disabled={busy}
                    onChange={(event) => setShareRole(event.target.value)}
                  >
                    <option value="viewer">Viewer</option>
                    <option value="editor">Editor</option>
                  </select>

                  <button disabled={busy} onClick={grantAccess}>
                    Grant / update access
                  </button>
                </div>

                {shares.length === 0 && (
                  <p className="muted">Not shared with anyone yet.</p>
                )}

                {shares.map((share) => (
                  <div className="share-row" key={share.user_id}>
                    <span>
                      {USERS.find((person) =>
                        person.id === share.user_id
                      )?.name || share.user_id}
                      {' · '}{share.role}
                    </span>

                    <button
                      disabled={busy}
                      onClick={() => revokeAccess(share.user_id)}
                    >
                      Revoke
                    </button>
                  </div>
                ))}
              </section>
            )}
          </>
        ) : (
          <div className="empty">
            <h1>Welcome to Ajaia Docs</h1>
            <p>Create, import, or open a document to get started.</p>
          </div>
        )}
      </main>
    </div>
  )
}
