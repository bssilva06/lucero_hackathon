import type { Message, SourceChunk } from '../types'
import { ExternalLink, FileText } from 'lucide-react'

interface Props {
  message: Message
  onSelectSource: (source: SourceChunk) => void
  selectedSourceId: string | null
}

function getSourceLabel(src: SourceChunk, idx: number): string {
  if (src.section_citation) return src.section_citation
  if (src.section_path && src.section_path.length > 0)
    return src.section_path[src.section_path.length - 1]
  if (src.doc_type) return src.doc_type
  return `Source ${idx + 1}`
}

// ── Inline markdown renderer ────────────────────────────────────────────────

type InlineNode = string | React.ReactElement

function parseInline(text: string, k: string): InlineNode[] {
  const re = /(\*\*[^*\n]+?\*\*|\*[^*\n]+?\*|`[^`\n]+?`)/g
  const nodes: InlineNode[] = []
  let last = 0
  let i = 0
  let m: RegExpExecArray | null

  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index))
    const t = m[0]
    if (t.startsWith('**'))
      nodes.push(<strong key={`${k}-b${i++}`}>{t.slice(2, -2)}</strong>)
    else if (t.startsWith('*'))
      nodes.push(<em key={`${k}-e${i++}`}>{t.slice(1, -1)}</em>)
    else
      nodes.push(
        <code key={`${k}-c${i++}`} className="md-code">
          {t.slice(1, -1)}
        </code>,
      )
    last = m.index + t.length
  }
  if (last < text.length) nodes.push(text.slice(last))
  return nodes.length ? nodes : [text]
}

function renderBlock(block: string, bi: number): React.ReactElement {
  const t = block.trim()

  if (t.startsWith('### '))
    return (
      <h3 key={bi} className="md-h3">
        {parseInline(t.slice(4), `${bi}`)}
      </h3>
    )
  if (t.startsWith('## '))
    return (
      <h2 key={bi} className="md-h2">
        {parseInline(t.slice(3), `${bi}`)}
      </h2>
    )
  if (t.startsWith('# '))
    return (
      <h1 key={bi} className="md-h1">
        {parseInline(t.slice(2), `${bi}`)}
      </h1>
    )

  const lines = t.split('\n')
  const isBullet = lines.every(l => !l.trim() || /^[-*]\s/.test(l))
  const isNum = lines.some(l => /^\d+\.\s/.test(l.trim()))

  if (isBullet && lines.some(l => l.trim())) {
    return (
      <ul key={bi} className="md-ul">
        {lines
          .filter(l => l.trim())
          .map((l, j) => (
            <li key={j}>{parseInline(l.replace(/^[-*]\s+/, ''), `${bi}-${j}`)}</li>
          ))}
      </ul>
    )
  }

  if (isNum) {
    return (
      <ol key={bi} className="md-ol">
        {lines
          .filter(l => l.trim())
          .map((l, j) => (
            <li key={j}>{parseInline(l.replace(/^\d+\.\s+/, ''), `${bi}-${j}`)}</li>
          ))}
      </ol>
    )
  }

  return (
    <p key={bi} className="md-p">
      {parseInline(t.replace(/\n/g, ' '), `${bi}`)}
    </p>
  )
}

function Markdown({ text }: { text: string }) {
  const blocks = text.split(/\n\n+/).filter(b => b.trim())
  return <div className="markdown">{blocks.map(renderBlock)}</div>
}

// ── Component ───────────────────────────────────────────────────────────────

export function MessageBubble({ message, onSelectSource, selectedSourceId }: Props) {
  const isUser = message.role === 'user'

  return (
    <div className={`msg msg--${isUser ? 'user' : 'assistant'}`}>
      <div className="msg-role">{isUser ? 'You' : 'Lucero'}</div>

      <div className="msg-content">
        {isUser ? (
          <p className="msg-text">{message.content}</p>
        ) : (
          <Markdown text={message.content} />
        )}
      </div>

      {!isUser && message.sources && message.sources.length > 0 && (
        <div className="citation-area">
          <span className="citation-label">
            <FileText size={10} />
            Sources
          </span>
          <div className="citation-chips">
            {message.sources.map((src, idx) => (
              <button
                key={src.chunk_id}
                className={`citation-chip${selectedSourceId === src.chunk_id ? ' citation-chip--active' : ''}`}
                onClick={() => onSelectSource(src)}
                title={src.text.slice(0, 120)}
              >
                <span className="citation-chip-num">[{idx + 1}]</span>
                <span className="citation-chip-label">{getSourceLabel(src, idx)}</span>
                {src.source_url && <ExternalLink size={9} />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
