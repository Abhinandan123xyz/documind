import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { useState } from 'react'

const SourceBadge = ({ source }) => {
  const config = {
    document: { label: "📄 From your files", cls: "badge-doc" },
    web: { label: "🌐 Web search", cls: "badge-web" },
    general: { label: "🤖 AI knowledge", cls: "badge-ai" },
  }
  const c = config[source] || config.general
  return <span className={`badge ${c.cls}`}>{c.label}</span>
}

const CitationsList = ({ citations }) => {
  const [expanded, setExpanded] = useState(false)
  
  if (!citations || citations.length === 0) return null
  
  return (
    <div className="citations-container">
      <button 
        className="citations-toggle"
        onClick={() => setExpanded(!expanded)}
      >
        📚 {citations.length} source{citations.length > 1 ? 's' : ''}
        <span className={`toggle-arrow ${expanded ? 'expanded' : ''}`}>▾</span>
      </button>
      
      {expanded && (
        <div className="citations-list">
          {citations.map((citation) => (
            <div 
              key={citation.number} 
              className="citation-item"
              id={`citation-${citation.number}`}
            >
              <span className="citation-number">[{citation.number}]</span>
              <div className="citation-details">
                <span className="citation-source">{citation.source}</span>
                {citation.page && citation.page !== '?' && (
                  <span className="citation-page"> · Page {citation.page}</span>
                )}
                {citation.text && (
                  <p className="citation-text">"{citation.text}"</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const StreamingCursor = () => (
  <span className="streaming-cursor">▊</span>
)

export default function MessageBubble({ message }) {
  const isUser = message.role === 'user'
  const isAssistant = message.role === 'assistant'
  const isStreaming = message.isStreaming

  // Custom renderer for citation links like [1], [2,3], [1][3]
  const renderContent = (content) => {
    if (!content) return ''
    
    // Replace citation patterns with clickable spans
    return content.replace(
      /\[(\d+(?:,\d+)*)\]/g,
      (match, numbers) => {
        const nums = numbers.split(',')
        return nums.map(n => 
          `<a href="#citation-${n.trim()}" class="citation-link" data-citation="${n.trim()}">[${n.trim()}]</a>`
        ).join('')
      }
    )
  }

  return (
    <div className={`message ${message.role} ${isStreaming ? 'streaming' : ''}`}>
      <div className="msg-avatar">
        {isUser ? '👤' : '🧠'}
      </div>
      <div className="msg-body">
        {isUser ? (
          <div className="msg-content user-content">
            {message.content}
          </div>
        ) : (
          <div className="msg-content assistant-content">
            {isStreaming && !message.content ? (
              <StreamingCursor />
            ) : (
              <>
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    code({ node, inline, className, children, ...props }) {
                      const match = /language-(\w+)/.exec(className || '')
                      return !inline && match ? (
                        <div className="code-block">
                          <div className="code-header">
                            <span className="code-lang">{match[1]}</span>
                            <button 
                              className="copy-btn"
                              onClick={() => navigator.clipboard.writeText(String(children))}
                            >
                              📋 Copy
                            </button>
                          </div>
                          <SyntaxHighlighter
                            style={oneDark}
                            language={match[1]}
                            PreTag="div"
                            {...props}
                          >
                            {String(children).replace(/\n$/, '')}
                          </SyntaxHighlighter>
                        </div>
                      ) : (
                        <code className={className} {...props}>
                          {children}
                        </code>
                      )
                    },
                    table({ children }) {
                      return (
                        <div className="table-wrapper">
                          <table>{children}</table>
                        </div>
                      )
                    },
                    th({ children }) {
                      return <th>{children}</th>
                    },
                    td({ children }) {
                      return <td>{children}</td>
                    },
                    a({ href, children }) {
                      // Make citation links scroll to the citation
                      if (href && href.startsWith('#citation-')) {
                        return (
                          <a 
                            href={href} 
                            className="citation-link"
                            onClick={(e) => {
                              e.preventDefault()
                              const el = document.querySelector(href)
                              if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
                            }}
                          >
                            {children}
                          </a>
                        )
                      }
                      return (
                        <a href={href} target="_blank" rel="noopener noreferrer">
                          {children} 🔗
                        </a>
                      )
                    },
                    blockquote({ children }) {
                      return <blockquote>{children}</blockquote>
                    },
                    img({ src, alt }) {
                      return <img src={src} alt={alt} className="msg-image" loading="lazy" />
                    }
                  }}
                >
                  {message.content}
                </ReactMarkdown>
                {isStreaming && <StreamingCursor />}
              </>
            )}
          </div>
        )}
        
        {isAssistant && !isStreaming && (
          <>
            <SourceBadge source={message.source} />
            <CitationsList citations={message.citations} />
          </>
        )}
      </div>
    </div>
  )
}