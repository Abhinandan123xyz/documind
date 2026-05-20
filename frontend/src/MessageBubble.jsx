import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

const SourceBadge = ({ source }) => {
  const config = {
    document: { label: "📄 From your files", cls: "badge-doc" },
    web: { label: "🌐 Web search", cls: "badge-web" },
    general: { label: "🤖 AI knowledge", cls: "badge-ai" },
  }
  const c = config[source] || config.general
  return <span className={`badge ${c.cls}`}>{c.label}</span>
}

export default function MessageBubble({ message, index }) {
  const isUser = message.role === 'user'
  const isAssistant = message.role === 'assistant'

  return (
    <div className={`message ${message.role} ${message.isStreaming ? 'streaming' : ''}`}>
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
          </div>
        )}
        
        {message.source && isAssistant && <SourceBadge source={message.source} />}
      </div>
    </div>
  )
}