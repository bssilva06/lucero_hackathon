import { useState } from 'react'
import type { ToolTrace } from '../types'
import { ChevronDown, ChevronRight, Terminal, Database } from 'lucide-react'

interface Props {
  toolCalls: ToolTrace[]
}

interface ToolCallRowProps {
  call: ToolTrace
  index: number
}

function getResultCount(response: unknown): number | null {
  if (!response || typeof response !== 'object') return null
  const r = response as Record<string, unknown>
  if (Array.isArray(r['results'])) return (r['results'] as unknown[]).length
  return null
}

function ToolCallRow({ call, index }: ToolCallRowProps) {
  const [open, setOpen] = useState(false)

  const argsJson = JSON.stringify(call.arguments, null, 2)
  const respJson =
    call.response !== null && call.response !== undefined
      ? JSON.stringify(call.response, null, 2)
      : null
  const resultCount = getResultCount(call.response)

  return (
    <div className="tool-call">
      <button
        className="tool-call-header"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
      >
        <span className="tool-call-chevron">
          {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        </span>
        <Database size={11} className="tool-call-icon" />
        <span className="tool-call-name">{call.name}</span>
        {resultCount !== null && (
          <span className="tool-call-badge">{resultCount} results</span>
        )}
        <span className="tool-call-num">#{index + 1}</span>
      </button>

      {open && (
        <div className="tool-call-body">
          {Object.keys(call.arguments).length > 0 && (
            <div>
              <div className="tool-call-section-label">Arguments</div>
              <pre className="tool-call-json">{argsJson}</pre>
            </div>
          )}
          {respJson && (
            <div>
              <div className="tool-call-section-label">Response</div>
              <pre className="tool-call-json tool-call-json--response">
                {respJson.length > 2000
                  ? respJson.slice(0, 2000) + '\n… (truncated)'
                  : respJson}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function ToolTraceLog({ toolCalls }: Props) {
  const [open, setOpen] = useState(false)

  return (
    <div className="tool-trace">
      <button
        className="tool-trace-header"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
      >
        <Terminal size={12} className="tool-trace-icon" />
        <span className="tool-trace-title">Tool Trace</span>
        <span className="tool-trace-count">
          {toolCalls.length} {toolCalls.length === 1 ? 'call' : 'calls'}
        </span>
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
      </button>

      {open && (
        <div className="tool-trace-body">
          {toolCalls.map((call, i) => (
            <ToolCallRow key={`${call.name}-${i}`} call={call} index={i} />
          ))}
        </div>
      )}
    </div>
  )
}
