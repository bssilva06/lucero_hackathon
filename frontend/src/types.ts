export interface SourceChunk {
  chunk_id: string
  section_citation: string | null
  source_url: string | null
  text: string
  doc_id: string | null
  doc_type: string | null
  agency: string | null
  jurisdiction: string | null
  section_path: string[]
  version_label: string | null
  retrieval_date: string | null
  effective_from: string | null
  effective_to: string | null
  content_hash: string | null
  score: unknown
}

export interface ToolTrace {
  name: string
  arguments: Record<string, unknown>
  response: unknown
}

export interface ChatResponse {
  response: string
  tool_calls: ToolTrace[]
  sources: SourceChunk[]
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: SourceChunk[]
  tool_calls?: ToolTrace[]
  timestamp: Date
}
