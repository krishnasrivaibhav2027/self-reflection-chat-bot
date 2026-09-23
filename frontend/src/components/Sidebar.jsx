import { AlertTriangle, ChevronLeft, ChevronRight, Code2, LogOut, MessageSquare, Moon, PlusCircle, Sun, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { deleteChat, getThreads } from '../api/chatApi'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'

const formatRelativeTime = (isoString) => {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

// ─── Confirm Delete Popup ─────────────────────────────────────────────────────
const DeleteConfirmPopup = ({ thread, onConfirm, onCancel }) => (
  <div className="delete-popup-overlay" onClick={onCancel}>
    <div className="delete-popup" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="delete-popup-title">
      <div className="delete-popup__icon">
        <AlertTriangle size={22} />
      </div>
      <h3 className="delete-popup__title" id="delete-popup-title">Delete conversation?</h3>
      <p className="delete-popup__message">
        This conversation will be permanently deleted and cannot be recovered.
      </p>
      <div className="delete-popup__actions">
        <button className="delete-popup__btn delete-popup__btn--cancel" onClick={onCancel}>
          Cancel
        </button>
        <button className="delete-popup__btn delete-popup__btn--confirm" onClick={onConfirm}>
          <Trash2 size={13} />
          Delete
        </button>
      </div>
    </div>
  </div>
)

const Sidebar = ({ activeThreadId, onSelectThread, onNewChat, refreshSignal }) => {
  const { logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [threads, setThreads] = useState([])
  const [collapsed, setCollapsed] = useState(false)
  const [deletingId, setDeletingId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [confirmThread, setConfirmThread] = useState(null) // thread pending delete confirmation

  const loadThreads = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getThreads()
      const sorted = [...(data.threads || [])].sort(
        (a, b) => new Date(b.updated_at) - new Date(a.updated_at)
      )
      setThreads(sorted)
    } catch {
      // silently fail
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadThreads()
  }, [loadThreads, refreshSignal])

  // Step 1: show the confirm popup
  const handleDeleteClick = (e, thread) => {
    e.stopPropagation()
    setConfirmThread(thread)
  }

  // Step 2: user confirmed — actually delete
  const handleDeleteConfirm = async () => {
    const thread = confirmThread
    setConfirmThread(null)
    setDeletingId(thread.thread_id)
    try {
      await deleteChat(thread.thread_id)
      setThreads((prev) => prev.filter((t) => t.thread_id !== thread.thread_id))
      if (activeThreadId === thread.thread_id) onNewChat()
    } catch {
      // ignore
    } finally {
      setDeletingId(null)
    }
  }

  const handleDeleteCancel = () => setConfirmThread(null)

  const handleLogout = async () => {
    await logout()
  }

  return (
    <>
      <aside className={`sidebar ${collapsed ? 'sidebar--collapsed' : ''}`}>
        {/* Collapse toggle */}
        <button
          className="sidebar__collapse-btn"
          onClick={() => setCollapsed((v) => !v)}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>

        {/* Logo strip (visible when collapsed) */}
        {collapsed && (
          <div className="sidebar__logo-icon">
            <Code2 size={20} strokeWidth={1.5} />
          </div>
        )}

        {/* New Chat button */}
        <button
          className="sidebar__new-chat-btn"
          onClick={onNewChat}
          aria-label="New chat"
          title="New Chat"
        >
          <PlusCircle size={16} />
          {!collapsed && <span>New Chat</span>}
        </button>

        {/* Recents */}
        {!collapsed && (
          <div className="sidebar__recents">
            <p className="sidebar__recents-label">Recents</p>
            <div className="sidebar__recents-list">
              {loading && <p className="sidebar__hint">Loading…</p>}
              {!loading && threads.length === 0 && (
                <p className="sidebar__hint">No conversations yet</p>
              )}
              {threads.map((thread) => (
                <button
                  key={thread.thread_id}
                  className={`sidebar__thread-item ${activeThreadId === thread.thread_id ? 'sidebar__thread-item--active' : ''}`}
                  onClick={() => onSelectThread(thread.thread_id)}
                  title={thread.preview}
                >
                  <MessageSquare size={14} className="sidebar__thread-icon" />
                  <div className="sidebar__thread-info">
                    <span className="sidebar__thread-preview">
                      {thread.preview?.length > 38
                        ? thread.preview.slice(0, 38) + '…'
                        : thread.preview || 'Untitled'}
                    </span>
                    <span className="sidebar__thread-time">
                      {formatRelativeTime(thread.updated_at)}
                    </span>
                  </div>
                  <button
                    className="sidebar__delete-btn"
                    onClick={(e) => handleDeleteClick(e, thread)}
                    aria-label="Delete conversation"
                    disabled={deletingId === thread.thread_id}
                  >
                    <Trash2 size={13} />
                  </button>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Theme toggle */}
        <button
          className="theme-toggle-btn"
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          {!collapsed && <span>{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>}
        </button>

        {/* Logout */}
        <button
          className="sidebar__logout-btn"
          onClick={handleLogout}
          aria-label="Logout"
          title="Logout"
        >
          <LogOut size={16} />
          {!collapsed && <span>Logout</span>}
        </button>
      </aside>

      {/* Delete confirm popup — rendered outside aside so it overlays everything */}
      {confirmThread && (
        <DeleteConfirmPopup
          thread={confirmThread}
          onConfirm={handleDeleteConfirm}
          onCancel={handleDeleteCancel}
        />
      )}
    </>
  )
}

export default Sidebar
