import { useState, useRef, useEffect, useCallback } from "react"
import ChatHistorySidebar from "./ChatHistorySidebar"
import MessageBubble from "./MessageBubble"
import { TypingIndicator, UploadProgress, ProcessingIndicator, ErrorMessage, EmptyState } from "./LoadingStates"
import ErrorBoundary from "./ErrorBoundary"
import AuthPage from "./AuthPage"
import api from "./api"
import "./App.css"

const API = ""

export default function App() {
  // ── ALL HOOKS FIRST (order must never change) ──────────
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem("user")
      return stored ? JSON.parse(stored) : null
    } catch { return null }
  })
  const [userReady, setUserReady] = useState(false)
  const [conversationId, setConversationId]   = useState(null)
  const [messages, setMessages]               = useState([])
  const [input, setInput]                     = useState("")
  const [loading, setLoading]                 = useState(false)
  const [documents, setDocuments]             = useState([])
  const [urlInput, setUrlInput]               = useState("")
  const [urlLoading, setUrlLoading]           = useState(false)
  const [dragOver, setDragOver]               = useState(false)
  const [error, setError]                     = useState(null)
  const [uploadProgress, setUploadProgress]   = useState(null)
  const [processingFile, setProcessingFile]   = useState(null)
  const [refreshTrigger, setRefreshTrigger]   = useState(0)
  const [streamingMessageId, setStreamingMessageId] = useState(null)

  const bottomRef          = useRef(null)
  const fileRef            = useRef(null)
  const inputRef           = useRef(null)
  const abortControllerRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  useEffect(() => {
    inputRef.current?.focus()
  }, [conversationId])

  // ── Handlers (plain functions, not hooks) ─────────────
  const handleLogin = (data) => {
    localStorage.setItem("token", data.access_token)
    localStorage.setItem("user", JSON.stringify({
      id: data.user_id, username: data.username, email: data.email
    }))
    setUser({ id: data.user_id, username: data.username, email: data.email })
    setUserReady(true)
  }

  const handleLogout = () => {
    localStorage.removeItem("token")
    localStorage.removeItem("user")
    setUser(null)
    setUserReady(false)
    setMessages([])
    setConversationId(null)
    setDocuments([])
  }

  const ensureConversation = async (title = "New Conversation") => {
    if (conversationId) return conversationId
    const res = await api.post(`/api/chat/conversations`, { title })
    const newId = res.data.conversation_id
    setConversationId(newId)
    setRefreshTrigger(prev => prev + 1)
    return newId
  }

  const createNewChat = useCallback(async () => {
    if (abortControllerRef.current) abortControllerRef.current.abort()
    try {
      const res = await api.post(`/api/chat/conversations`, { title: "New Conversation" })
      setConversationId(res.data.conversation_id)
      setMessages([])
      setDocuments([])
      setError(null)
      setStreamingMessageId(null)
      setRefreshTrigger(prev => prev + 1)
    } catch (e) {
      setError("Failed to create new conversation")
    }
  }, [])

  const loadConversation = async (convId) => {
    if (abortControllerRef.current) abortControllerRef.current.abort()
    try {
      setConversationId(convId)
      setLoading(true)
      const res = await api.get(`/api/chat/conversations/${convId}/messages`)
      if (res.data.messages?.length > 0) {
        setMessages(res.data.messages.map(msg => ({
          id: msg.id || Date.now().toString(),
          role: msg.role,
          content: msg.content,
          source: msg.source || "general",
          citations: msg.citations || []
        })))
      } else {
        setMessages([])
      }
      setDocuments([])
      setError(null)
      setStreamingMessageId(null)
    } catch (e) {
      setError("Failed to load conversation")
    } finally {
      setLoading(false)
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || loading) return
    const question = input.trim()
    setInput("")
    setError(null)

    let currentConvId
    try {
      currentConvId = await ensureConversation(question.substring(0, 50))
    } catch { return }

    const userMsgId      = Date.now().toString()
    const assistantMsgId = (Date.now() + 1).toString()

    setMessages(m => [...m, { id: userMsgId, role: "user", content: question }])
    setMessages(m => [...m, { id: assistantMsgId, role: "assistant", content: "", source: "general", citations: [], isStreaming: true }])
    setStreamingMessageId(assistantMsgId)
    setLoading(true)

    abortControllerRef.current = new AbortController()

    try {
      const token = localStorage.getItem("token")
      const response = await fetch(`${API}/api/chat/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ message: question, conversation_id: currentConvId, stream: true }),
        signal: abortControllerRef.current.signal
      })

      const reader  = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() || ""

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === "metadata") {
              setMessages(m => m.map(msg =>
                msg.id === assistantMsgId ? { ...msg, source: data.source, citations: data.citations || [] } : msg
              ))
            } else if (data.type === "token") {
              setMessages(m => m.map(msg =>
                msg.id === assistantMsgId ? { ...msg, content: msg.content + data.content } : msg
              ))
            } else if (data.type === "done") {
              setMessages(m => m.map(msg =>
                msg.id === assistantMsgId ? { ...msg, isStreaming: false } : msg
              ))
              setRefreshTrigger(prev => prev + 1)
            } else if (data.type === "error") {
              setMessages(m => m.map(msg =>
                msg.id === assistantMsgId ? { ...msg, content: `Error: ${data.content}`, isStreaming: false } : msg
              ))
            }
          } catch { /* skip */ }
        }
      }
    } catch (e) {
      if (e.name !== "AbortError") {
        setMessages(m => m.map(msg =>
          msg.id === assistantMsgId ? { ...msg, content: "Sorry, an error occurred.", isStreaming: false } : msg
        ))
      }
    } finally {
      setLoading(false)
      setStreamingMessageId(null)
      abortControllerRef.current = null
    }
  }

  const stopStreaming = () => {
    if (abortControllerRef.current) abortControllerRef.current.abort()
  }

  const uploadFile = async (file) => {
    let currentConvId
    try { currentConvId = await ensureConversation() } catch { return }

    setUploadProgress({ fileName: file.name, progress: 0 })
    setProcessingFile(file.name)

    const form = new FormData()
    form.append("file", file)
    form.append("conversation_id", currentConvId)

    try {
      const res = await api.post(`/api/documents/upload`, form, {
        onUploadProgress: (e) => setUploadProgress({
          fileName: file.name, progress: Math.round((e.loaded * 100) / e.total)
        })
      })
      setDocuments(d => [...d, { name: file.name, type: file.name.split(".").pop(), id: res.data.document_id, chunks: res.data.chunk_count }])
      setMessages(m => [...m, { id: Date.now().toString(), role: "assistant", content: `✅ **${file.name}** indexed! (${res.data.chunk_count} chunks)\n\nAsk me anything about this file.`, source: "document", citations: [] }])
    } catch (e) {
      setMessages(m => [...m, { id: Date.now().toString(), role: "assistant", content: `❌ Failed to process **${file.name}**`, source: "general", citations: [] }])
    } finally {
      setUploadProgress(null)
      setProcessingFile(null)
    }
  }

  const handleFileChange = (e) => { Array.from(e.target.files).forEach(uploadFile); e.target.value = "" }
  const handleDrop = (e) => { e.preventDefault(); setDragOver(false); Array.from(e.dataTransfer.files).forEach(uploadFile) }

  const uploadURL = async () => {
    if (!urlInput.trim()) return
    let currentConvId
    try { currentConvId = await ensureConversation() } catch { return }
    setUrlLoading(true)
    try {
      const res = await api.post(`/api/documents/upload-url`, { url: urlInput, conversation_id: currentConvId })
      setDocuments(d => [...d, { name: urlInput.slice(0, 40) + "…", type: "url", id: res.data.document_id, chunks: res.data.chunk_count }])
      setMessages(m => [...m, { id: Date.now().toString(), role: "assistant", content: `✅ **URL scraped!** (${res.data.chunk_count} chunks)`, source: "web", citations: [] }])
      setUrlInput("")
    } catch {
      setMessages(m => [...m, { id: Date.now().toString(), role: "assistant", content: `❌ Failed to scrape URL`, source: "general", citations: [] }])
    } finally { setUrlLoading(false) }
  }

  // ── EARLY RETURN (after ALL hooks) ─────────────────────
  if (!user) {
    return <AuthPage onLogin={handleLogin} />
  }

  // ── Normal render ──────────────────────────────────────
  return (
    <ErrorBoundary key={user.id}>
      <div className="app">
        <aside className="sidebar">
          <div className="sidebar-logo">
            <span className="logo-icon">🧠</span>
            <span className="logo-text">DocuMind AI</span>
          </div>
          <button className="new-chat-btn" onClick={createNewChat}>
            <span className="new-chat-icon">+</span> New Chat
          </button>
          <ChatHistorySidebar
            conversationId={conversationId}
            onSelectConversation={loadConversation}
            onNewChat={createNewChat}
            refreshTrigger={refreshTrigger}
            userReady={userReady}
          />
          <div className="sidebar-section">
            <p className="sidebar-label">Knowledge Base</p>
            <div className={`drop-zone ${dragOver ? "drag-over" : ""}`}
              onClick={() => fileRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}>
              <span className="drop-icon">⬆️</span>
              <p>Drop files or click to upload</p>
              <p className="drop-sub">PDF · DOCX · PPTX · Excel · CSV</p>
            </div>
            <input ref={fileRef} type="file" multiple accept=".pdf,.docx,.pptx,.xlsx,.xls,.csv" onChange={handleFileChange} style={{ display: "none" }} />
            {uploadProgress && <UploadProgress fileName={uploadProgress.fileName} progress={uploadProgress.progress} />}
            {processingFile && <ProcessingIndicator fileName={processingFile} />}
            <div className="url-input-row">
              <input className="url-input" placeholder="Paste a URL to scrape…" value={urlInput}
                onChange={e => setUrlInput(e.target.value)} onKeyDown={e => e.key === "Enter" && uploadURL()} />
              <button className="url-btn" onClick={uploadURL} disabled={urlLoading}>
                {urlLoading ? "⏳" : "➕"}
              </button>
            </div>
          </div>
          {documents.length > 0 && (
            <div className="doc-list">
              <p className="sidebar-label">Indexed Files</p>
              {documents.map((doc, i) => (
                <div key={i} className="doc-item">
                  <span className="doc-icon">{doc.type === "pdf" ? "📄" : doc.type === "url" ? "🔗" : "📎"}</span>
                  <div className="doc-info">
                    <span className="doc-name">{doc.name}</span>
                    <span className="doc-chunks">{doc.chunks} chunks</span>
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="sidebar-footer">
            <button onClick={handleLogout} style={{
              width: "100%", padding: "8px 12px", background: "transparent",
              border: "1px solid #30363d", borderRadius: 8, color: "#8b949e",
              fontSize: 12, cursor: "pointer", marginBottom: 8, textAlign: "left"
            }}>
              👤 {user.username} · Sign out
            </button>
            <p>Powered by Groq + LLaMA 3.3</p>
            <p className="version">v2.0</p>
          </div>
        </aside>
        <main className="chat-main">
          {error && <ErrorMessage message={error} onRetry={() => setError(null)} />}
          <div className="chat-messages">
            {messages.length === 0 && !loading ? <EmptyState /> : (
              messages.map(msg => <MessageBubble key={msg.id} message={msg} />)
            )}
            {loading && !streamingMessageId && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>
          <div className="chat-input-area">
            <div className="input-row">
              <textarea ref={inputRef} className="chat-input"
                placeholder={conversationId ? "Ask anything about your documents…" : "Start a new chat…"}
                value={input} onChange={e => setInput(e.target.value)}
                onKeyDown={e => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault()
                    loading && streamingMessageId ? stopStreaming() : sendMessage()
                  }
                }} rows={1} />
              <button className={`send-btn ${loading && streamingMessageId ? "stop-btn" : ""}`}
                onClick={loading && streamingMessageId ? stopStreaming : sendMessage}
                disabled={!loading && !input.trim()}>
                {loading && streamingMessageId ? "■" : "↑"}
              </button>
            </div>
            <div className="input-footer">
              <p className="input-hint"><kbd>Enter</kbd> to send · <kbd>Shift + Enter</kbd> for new line</p>
              <p className="input-info">{conversationId ? "📄 Documents isolated to this chat" : "💡 Start a new chat to upload documents"}</p>
            </div>
          </div>
        </main>
      </div>
    </ErrorBoundary>
  )
}
