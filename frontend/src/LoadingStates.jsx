export function TypingIndicator() {
  return (
    <div className="message assistant">
      <div className="msg-avatar">🧠</div>
      <div className="msg-body">
        <div className="typing-indicator">
          <span className="typing-dot" />
          <span className="typing-dot" />
          <span className="typing-dot" />
          <span className="typing-text">Thinking...</span>
        </div>
      </div>
    </div>
  )
}

export function UploadProgress({ fileName, progress }) {
  return (
    <div className="upload-progress">
      <div className="upload-progress-header">
        <span>📤 Uploading {fileName}...</span>
        <span>{progress}%</span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>
    </div>
  )
}

export function ProcessingIndicator({ fileName }) {
  return (
    <div className="message assistant processing-message">
      <div className="msg-avatar">🧠</div>
      <div className="msg-body">
        <div className="processing-content">
          <div className="processing-spinner" />
          <div>
            <p className="processing-title">Processing {fileName}...</p>
            <p className="processing-subtitle">Extracting text, generating embeddings</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export function ErrorMessage({ message, onRetry }) {
  return (
    <div className="error-message">
      <div className="error-icon">⚠️</div>
      <div className="error-content">
        <p className="error-title">Something went wrong</p>
        <p className="error-detail">{message}</p>
        {onRetry && (
          <button className="retry-btn" onClick={onRetry}>
            🔄 Try Again
          </button>
        )}
      </div>
    </div>
  )
}

export function EmptyState() {
  return (
    <div className="empty-state">
      <div className="empty-icon">🧠</div>
      <h2>Welcome to DocuMind AI</h2>
      <p>Your intelligent document assistant</p>
      <div className="empty-suggestions">
        <div className="suggestion-card">
          <span className="suggestion-icon">📄</span>
          <h3>Upload Documents</h3>
          <p>PDF, DOCX, PPTX, Excel, CSV</p>
        </div>
        <div className="suggestion-card">
          <span className="suggestion-icon">🔗</span>
          <h3>Paste URLs</h3>
          <p>Scrape and analyze web content</p>
        </div>
        <div className="suggestion-card">
          <span className="suggestion-icon">💬</span>
          <h3>Ask Questions</h3>
          <p>Get answers with cited sources</p>
        </div>
      </div>
    </div>
  )
}