import { useState, useCallback } from 'react'
import { Scale } from 'lucide-react'
import type { Message, SourceChunk, ToolTrace } from './types'
import { sendChatMessage } from './api'
import { ChatPane } from './components/ChatPane'
import { SourcePanel } from './components/SourcePanel'

function uid(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

const INITIAL_SESSION = `session-${Date.now()}`

export function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedSource, setSelectedSource] = useState<SourceChunk | null>(null)
  const [sessionId] = useState(INITIAL_SESSION)
  const [mobileTab, setMobileTab] = useState<'chat' | 'source'>('chat')

  const latestToolCalls: ToolTrace[] = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i]
      if (m.role === 'assistant' && m.tool_calls && m.tool_calls.length > 0) {
        return m.tool_calls
      }
    }
    return []
  })()

  const handleSend = useCallback(
    async (text: string) => {
      if (!text.trim() || loading) return

      const userMsg: Message = {
        id: uid(),
        role: 'user',
        content: text.trim(),
        timestamp: new Date(),
      }

      setMessages(prev => [...prev, userMsg])
      setLoading(true)
      setError(null)

      try {
        const data = await sendChatMessage(text.trim(), sessionId, 'practitioner')

        const assistantMsg: Message = {
          id: uid(),
          role: 'assistant',
          content: data.response || '(No response text returned.)',
          sources: data.sources,
          tool_calls: data.tool_calls,
          timestamp: new Date(),
        }

        setMessages(prev => [...prev, assistantMsg])
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err)
        const isNetwork =
          msg.includes('fetch') ||
          msg.includes('Failed to fetch') ||
          msg.includes('NetworkError') ||
          msg.includes('ECONNREFUSED')

        setError(
          isNetwork
            ? 'Cannot reach the research service. Verify the backend is running on port 8080.'
            : `Request failed: ${msg}`,
        )
      } finally {
        setLoading(false)
      }
    },
    [loading, sessionId],
  )

  const handleSelectSource = useCallback((source: SourceChunk) => {
    setSelectedSource(source)
    setMobileTab('source')
  }, [])

  const sessionShort = sessionId.slice(-8)

  return (
    <div className="app">
      <header className="header">
        <div className="header-brand">
          <Scale size={17} className="header-icon" />
          <span className="header-name">LUCERO</span>
          <span className="header-dot">·</span>
          <span className="header-subtitle">Immigration Research</span>
        </div>
        <div className="header-sep" />
        <span className="header-session">{sessionShort}</span>
      </header>

      <main className="workspace" data-mobile-tab={mobileTab}>
        <ChatPane
          messages={messages}
          loading={loading}
          error={error}
          onSend={handleSend}
          onSelectSource={handleSelectSource}
          selectedSourceId={selectedSource?.chunk_id ?? null}
          latestToolCalls={latestToolCalls}
        />
        <SourcePanel
          source={selectedSource}
          onClose={() => setSelectedSource(null)}
        />
      </main>

      <div className="mobile-tabs">
        <button
          className={`mobile-tab${mobileTab === 'chat' ? ' mobile-tab--active' : ''}`}
          onClick={() => setMobileTab('chat')}
        >
          Chat
        </button>
        <button
          className={`mobile-tab${mobileTab === 'source' ? ' mobile-tab--active' : ''}`}
          onClick={() => setMobileTab('source')}
        >
          Sources
        </button>
      </div>

      <footer className="footer">
        <span className="footer-icon">⚖</span>
        <span className="footer-text">
          Research aid only — verify all authority before client use.
        </span>
      </footer>
    </div>
  )
}
