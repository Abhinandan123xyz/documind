import { useState, useRef, useEffect, useCallback } from "react"
import axios from "axios"
import ChatHistorySidebar from "./ChatHistorySidebar"
import MessageBubble from "./MessageBubble"
import { TypingIndicator, UploadProgress, ProcessingIndicator, ErrorMessage, EmptyState } from "./LoadingStates"
import ErrorBoundary from "./ErrorBoundary"
import "./App.css"

const API = "http://localhost:8000"

export default function App() {
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [documents, setDocuments] = useState([])
  const [urlInput, setUrlInput] = useState("")
  const [urlLoading, setUrlLoading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState(null)
  const [uploadProgress, setUploadProgress] = useState(null)
  const [processingFile, setProcessingFile] = useState(null)
  const [refreshTrigger, setRefreshTrigger] = useState(0)
  const [showHistory, setShowHistory] = useState(true)
  
  const bottomRef = useRef(null)
  const fileRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  useEffect(() => {
    inputRef.current?.focus()
  }, [conversationId])

  const createNewChat = useCallback(async () => {
    try {
      const res = await axios.post(`${API}/api/chat/conversations`, {
        title: "New Conversation",
        user_id: "default_user"
      })
      
      const newConvId = res.data.conversation_id
      setConversationId(newConvId)
      setMessages([])
      setDocuments([])
      setError(null)
      setRefreshTrigger(prev => prev + 1)
      
    } catch (e) {
      setError("Failed to create new conversation")
    }
  }, [])

  const loadConversation = async (convId) => {
    try {
      setConversationId(convId)
      setLoading(true)
      
      const res = await axios.get(`${API}/api/chat/conversations/${convId}/messages`)
      
      if (res.data.messages && res.data.messages.length > 0) {
        setMessages(res.data.messages.map(msg => ({
          role: msg.role,
          content: msg.content,
          source: msg.source || "general"
        })))
      } else {
        setMessages([])
      }
      
      setDocuments([])
      setError(null)
      
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
    setMessages(m => [...m, { role: "user", content: question }])
    setLoading(true)
    setError(null)
    
    try {
      const res = await axios.post(`${API}/api/chat/`, {
        message: question,
        conversation_id: conversationId,
        user_id: "default_user"
      })
      
      setMessages(m => [...m, {
        role: "assistant",
        content: res.data.reply,
        source: res.data.source || "general"
      }])
      
      if (!conversationId && res.data.conversation_id) {
        setConversationId(res.data.conversation_id)
        setRefreshTrigger(prev => prev + 1)
      }
      
    } catch (e) {
      const errorMsg = e.response?.data?.detail || "Sorry, something went wrong. Please try again."
      setMessages(m => [...m, {
        role: "assistant",
        content: `❌ ${errorMsg}`,
        source: "general"
      }])
      setError(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  const uploadFile = async (file) => {
    if (!conversationId) {
      await createNewChat()
    }
    
    setUploadProgress({ fileName: file.name, progress: 0 })
    setProcessingFile(file.name)
    
    const form = new FormData()
    form.append("file", file)
    form.append("conversation_id", conversationId || "default")
    form.append("user_id", "default_user")
    
    try {
      const res = await axios.post(`${API}/api/documents/upload`, form, {
        onUploadProgress: (progressEvent) => {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          setUploadProgress({ fileName: file.name, progress: percent })
        }
      })
      
      const ext = file.name.split(".").pop()
      setDocuments(d => [...d, {
        name: file.name,
        type: ext,
        id: res.data.document_id,
        chunks: res.data.chunk_count
      }])
      
      setMessages(m => [...m, {
        role: "assistant",
        content: `✅ **${file.name}** has been indexed successfully!\n\n- **Chunks**: ${res.data.chunk_count}\n- **Status**: Ready for queries\n\nYou can now ask me anything about this document.`,
        source: "document"
      }])
      
    } catch (e) {
      setMessages(m => [...m, {
        role: "assistant",
        content: `❌ Failed to process **${file.name}**: ${e.response?.data?.detail || "Unknown error occurred"}`,
        source: "general"
      }])
    } finally {
      setUploadProgress(null)
      setProcessingFile(null)
    }
  }

  const handleFileChange = (e) => {
    Array.from(e.target.files).forEach(uploadFile)
    e.target.value = ""
  }
  
  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    Array.from(e.dataTransfer.files).forEach(uploadFile)
  }

  const uploadURL = async () => {
    if (!urlInput.trim()) return
    setUrlLoading(true)
    
    try {
      const res = await axios.post(`${API}/api/documents/upload-url`, {
        url: urlInput,
        conversation_id: conversationId || "default",
        user_id: "default_user"
      })
      
      setDocuments(d => [...d, {
        name: urlInput.length > 40 ? urlInput.slice(0, 40) + "…" : urlInput,
        type: "url",
        id: res.data.document_id,
        chunks: res.data.chunk_count
      }])
      
      setMessages(m => [...m, {
        role: "assistant",
        content: `✅ **Web content scraped!**\n\n- **Chunks**: ${res.data.chunk_count}\n- **URL**: ${urlInput}\n\nAsk me anything about this page.`,
        source: "web"
      }])
      
      setUrlInput("")
    } catch (e) {
      setMessages(m => [...m, {
        role: "assistant",
        content: `❌ Failed to scrape URL: ${e.response?.data?.detail || "Could not reach that page"}`,
        source: "general"
      }])
    } finally {
      setUrlLoading(false)
    }
  }

  return (
    <ErrorBoundary>
      <div className="app">
        {/* Sidebar */}
        <aside className="sidebar">
          <div className="sidebar-logo">
            <span className="logo-icon">🧠</span>
            <span className="logo-text">DocuMind AI</span>
          </div>
          
          <button className="new-chat-btn" onClick={createNewChat}>
            <span className="new-chat-icon">+</span>
            New Chat
          </button>
          
          {/* Chat History */}
          <ChatHistorySidebar
            conversationId={conversationId}
            onSelectConversation={loadConversation}
            onNewChat={createNewChat}
            refreshTrigger={refreshTrigger}
          />
          
          {/* Knowledge Base */}
          <div className="sidebar-section">
            <p className="sidebar-label">Knowledge Base</p>
            <div 
              className={`drop-zone ${dragOver ? "drag-over" : ""}`}
              onClick={() => fileRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
            >
              <span className="drop-icon">⬆️</span>
              <p>Drop files or click to upload</p>
              <p className="drop-sub">PDF · DOCX · PPTX · Excel · CSV</p>
            </div>
            <input 
              ref={fileRef} 
              type="file" 
              multiple 
              accept=".pdf,.docx,.pptx,.xlsx,.xls,.csv" 
              onChange={handleFileChange} 
              style={{ display: "none" }} 
            />
            
            {/* Upload Progress */}
            {uploadProgress && (
              <UploadProgress 
                fileName={uploadProgress.fileName} 
                progress={uploadProgress.progress} 
              />
            )}
            
            {/* Processing Indicator */}
            {processingFile && (
              <ProcessingIndicator fileName={processingFile} />
            )}
            
            {/* URL Input */}
            <div className="url-input-row">
              <input 
                className="url-input" 
                placeholder="Paste a URL to scrape…" 
                value={urlInput}
                onChange={e => setUrlInput(e.target.value)} 
                onKeyDown={e => e.key === "Enter" && uploadURL()} 
              />
              <button 
                className="url-btn" 
                onClick={uploadURL} 
                disabled={urlLoading}
              >
                {urlLoading ? "⏳" : "➕"}
              </button>
            </div>
          </div>
          
          {/* Indexed Files */}
          {documents.length > 0 && (
            <div className="doc-list">
              <p className="sidebar-label">Indexed Files</p>
              {documents.map((doc, i) => (
                <div key={i} className="doc-item">
                  <span className="doc-icon">
                    {doc.type === "pdf" ? "📄" : doc.type === "url" ? "🔗" : "📎"}
                  </span>
                  <div className="doc-info">
                    <span className="doc-name">{doc.name}</span>
                    <span className="doc-chunks">{doc.chunks} chunks</span>
                  </div>
                </div>
              ))}
            </div>
          )}
          
          <div className="sidebar-footer">
            <p>Powered by Groq + LLaMA 3.3</p>
            <p className="version">v1.0.0</p>
          </div>
        </aside>

        {/* Main Chat Area */}
        <main className="chat-main">
          {/* Error Message */}
          {error && (
            <ErrorMessage 
              message={error} 
              onRetry={() => setError(null)} 
            />
          )}
          
          {/* Messages */}
          <div className="chat-messages">
            {messages.length === 0 && !loading ? (
              <EmptyState />
            ) : (
              messages.map((msg, i) => (
                <MessageBubble key={i} message={msg} index={i} />
              ))
            )}
            
            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>
          
          {/* Input Area */}
          <div className="chat-input-area">
            <div className="input-row">
              <textarea
                ref={inputRef}
                className="chat-input"
                placeholder={conversationId ? "Ask anything about your documents…" : "Start a new chat to ask questions…"}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault()
                    sendMessage()
                  }
                }}
                rows={1}
                disabled={loading}
              />
              <button 
                className="send-btn" 
                onClick={sendMessage} 
                disabled={loading || !input.trim()}
                title="Send message"
              >
                {loading ? "⏳" : "↑"}
              </button>
            </div>
            <div className="input-footer">
              <p className="input-hint">
                <kbd>Enter</kbd> to send · <kbd>Shift + Enter</kbd> for new line
              </p>
              <p className="input-info">
                {conversationId ? '📄 Documents are isolated to this chat' : '💡 Start a new chat to upload documents'}
              </p>
            </div>
          </div>
        </main>
      </div>
    </ErrorBoundary>
  )
}