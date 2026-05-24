import { useState, useRef, useEffect } from 'react'
import type { Message, SourceChunk, ToolTrace } from '../types'
import { MessageBubble } from './MessageBubble'
import { ToolTraceLog } from './ToolTraceLog'
import { Send, BookOpen } from 'lucide-react'

interface Props {
  messages: Message[]
  loading: boolean
  error: string | null
  onSend: (text: string) => void
  onSelectSource: (source: SourceChunk) => void
  selectedSourceId: string | null
  latestToolCalls: ToolTrace[]
}

export function ChatPane({
  messages,
  loading,
  error,
  onSend,
  onSelectSource,
  selectedSourceId,
  latestToolCalls,
}: Props) {
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, loading])

  const submit = () => {
    if (!input.trim() || loading) return
    onSend(input)
    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const onInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    const ta = e.target
    ta.style.height = 'auto'
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`
  }

  return (
    <div className="chat-pane">
      <div className="chat-messages" ref={scrollRef}>
        {messages.length === 0 && !loading && (
          <div className="chat-empty">
            <BookOpen size={30} className="chat-empty-icon" />
            <p className="chat-empty-title">Research session ready</p>
            <p className="chat-empty-hint">
              Ask about USCIS policy, visa categories, procedural requirements,
              or any immigration law question. Cite-first answers with source
              panel on the right.
            </p>
          </div>
        )}

        {messages.map(msg => (
          <MessageBubble
            key={msg.id}
            message={msg}
            onSelectSource={onSelectSource}
            selectedSourceId={selectedSourceId}
          />
        ))}

        {loading && (
          <div className="msg msg--assistant">
            <div className="msg-role">Lucero</div>
            <div className="msg-content">
              <div className="typing-indicator">
                <span />
                <span />
                <span />
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="chat-error">
            <span className="chat-error-icon">!</span>
            {error}
          </div>
        )}
      </div>

      {latestToolCalls.length > 0 && (
        <ToolTraceLog toolCalls={latestToolCalls} />
      )}

      <div className="chat-composer">
        <textarea
          ref={textareaRef}
          className="chat-input"
          value={input}
          onChange={onInput}
          onKeyDown={onKeyDown}
          placeholder="Ask about immigration policy, visa categories, or procedural requirements…  (Enter to send)"
          rows={1}
          disabled={loading}
        />
        <button
          className="chat-send"
          onClick={submit}
          disabled={!input.trim() || loading}
          aria-label="Send message"
        >
          <Send size={15} />
        </button>
      </div>
    </div>
  )
}
