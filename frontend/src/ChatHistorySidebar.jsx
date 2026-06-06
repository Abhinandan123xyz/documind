import { useState, useEffect } from "react"
import api from "./api"

export default function ChatHistorySidebar({
  conversationId,
  onSelectConversation,
  onNewChat,
  refreshTrigger,
  userReady      // ← new prop
}) {
  const [conversations, setConversations] = useState([])
  const [loading, setLoading]             = useState(false)
  const [searchTerm, setSearchTerm]       = useState("")
  const [editingId, setEditingId]         = useState(null)
  const [editTitle, setEditTitle]         = useState("")

  useEffect(() => {
    if (!userReady) return   // don't fetch until token is available
    loadConversations()
  }, [refreshTrigger, userReady])

  const loadConversations = async () => {
    setLoading(true)
    try {
      const res = await api.get(`/api/chat/conversations`)
      setConversations(res.data.conversations || [])
    } catch (e) {
      console.error("Failed to load conversations:", e)
    }
    setLoading(false)
  }

  const deleteConversation = async (id, e) => {
    e.stopPropagation()
    if (!confirm("Delete this conversation?")) return
    try {
      await api.delete(`/api/chat/conversations/${id}`)
      setConversations(prev => prev.filter(c => c.id !== id))
      if (conversationId === id) onNewChat()
    } catch (e) {
      console.error("Failed to delete:", e)
    }
  }

  const startRename = (conv, e) => {
    e.stopPropagation()
    setEditingId(conv.id)
    setEditTitle(conv.title)
  }

  const saveRename = async (id) => {
    try {
      await api.patch(`/api/chat/conversations/${id}`, { title: editTitle })
      setConversations(prev => prev.map(c => c.id === id ? { ...c, title: editTitle } : c))
      setEditingId(null)
    } catch (e) {
      console.error("Failed to rename:", e)
    }
  }

  const filtered = conversations.filter(c =>
    c.title.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const groupByDate = (convs) => {
    const groups = { Today: [], Yesterday: [], "This Week": [], Older: [] }
    const now       = new Date()
    const today     = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const yesterday = new Date(today - 86400000)
    const weekAgo   = new Date(today - 7 * 86400000)
    convs.forEach(conv => {
      const d = new Date(conv.created_at)
      if (d >= today)     groups.Today.push(conv)
      else if (d >= yesterday) groups.Yesterday.push(conv)
      else if (d >= weekAgo)   groups["This Week"].push(conv)
      else                     groups.Older.push(conv)
    })
    return Object.entries(groups).filter(([, v]) => v.length > 0)
  }

  if (!userReady) {
    return <div className="history-loading">Loading...</div>
  }

  return (
    <div className="chat-history">
      <div className="history-header">
        <h3>Chat History</h3>
        <button className="refresh-btn" onClick={loadConversations} title="Refresh">↻</button>
      </div>
      <div className="history-search">
        <input type="text" placeholder="Search conversations..."
          value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
      </div>
      <div className="history-list">
        {loading ? (
          <div className="history-loading"><div className="loading-spinner" /><span>Loading...</span></div>
        ) : filtered.length === 0 ? (
          <div className="history-empty"><p>No conversations yet</p><p>Start a new chat!</p></div>
        ) : (
          groupByDate(filtered).map(([group, convs]) => (
            <div key={group} className="history-group">
              <div className="history-group-label">{group}</div>
              {convs.map(conv => (
                <div key={conv.id}
                  className={`history-item ${conv.id === conversationId ? "active" : ""}`}
                  onClick={() => onSelectConversation(conv.id)}>
                  <span className="history-icon">💬</span>
                  <div className="history-content">
                    {editingId === conv.id ? (
                      <input className="rename-input" value={editTitle}
                        onChange={e => setEditTitle(e.target.value)}
                        onBlur={() => saveRename(conv.id)}
                        onKeyDown={e => {
                          if (e.key === "Enter") saveRename(conv.id)
                          if (e.key === "Escape") setEditingId(null)
                        }}
                        onClick={e => e.stopPropagation()} autoFocus />
                    ) : (
                      <>
                        <span className="history-title">{conv.title}</span>
                        <span className="history-date">{new Date(conv.created_at).toLocaleDateString()}</span>
                      </>
                    )}
                  </div>
                  <div className="history-actions">
                    <button className="action-btn" onClick={e => startRename(conv, e)} title="Rename">✏️</button>
                    <button className="action-btn" onClick={e => deleteConversation(conv.id, e)} title="Delete">🗑️</button>
                  </div>
                </div>
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  )
}