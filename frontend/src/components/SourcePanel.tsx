import type { SourceChunk } from '../types'
import {
  X,
  ExternalLink,
  BookOpen,
  Calendar,
  Building2,
  FileText,
  ChevronRight,
} from 'lucide-react'

interface Props {
  source: SourceChunk | null
  onClose: () => void
}

function MetaRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="meta-row">
      <span className="meta-label">{label}</span>
      <span className={`meta-value${mono ? ' meta-mono' : ''}`}>{value}</span>
    </div>
  )
}

export function SourcePanel({ source, onClose }: Props) {
  if (!source) {
    return (
      <aside className="source-panel source-panel--empty">
        <div className="source-empty">
          <BookOpen size={28} className="source-empty-icon" />
          <p className="source-empty-title">No source selected</p>
          <p className="source-empty-hint">
            Click a citation chip beneath a response to view the referenced source
            section.
          </p>
        </div>
      </aside>
    )
  }

  const hasDateRange = source.effective_from || source.effective_to

  return (
    <aside className="source-panel">
      <div className="source-panel-header">
        <div className="source-panel-title">
          {source.section_citation && (
            <span className="source-citation-badge">{source.section_citation}</span>
          )}
          {source.doc_type && (
            <span className="source-doctype">{source.doc_type}</span>
          )}
        </div>
        <button className="source-close" onClick={onClose} aria-label="Close">
          <X size={14} />
        </button>
      </div>

      <div className="source-panel-body">
        {source.section_path && source.section_path.length > 0 && (
          <div className="source-breadcrumb">
            {source.section_path.map((part, i) => (
              <span key={i} className="source-breadcrumb-item">
                {i > 0 && <ChevronRight size={9} className="source-breadcrumb-sep" />}
                {part}
              </span>
            ))}
          </div>
        )}

        <div className="source-text-block">
          <div className="source-text-label">Excerpt</div>
          <blockquote className="source-text">{source.text}</blockquote>
        </div>

        {(source.agency ||
          source.jurisdiction ||
          source.doc_id ||
          source.version_label ||
          source.retrieval_date ||
          hasDateRange) && (
          <div className="source-meta">
            {source.agency && (
              <div className="meta-row">
                <span className="meta-label">
                  <Building2 size={10} />
                  Agency
                </span>
                <span className="meta-value">{source.agency}</span>
              </div>
            )}
            {source.jurisdiction && (
              <MetaRow label="Jurisdiction" value={source.jurisdiction} />
            )}
            {source.doc_id && (
              <div className="meta-row">
                <span className="meta-label">
                  <FileText size={10} />
                  Document
                </span>
                <span className="meta-value meta-mono">{source.doc_id}</span>
              </div>
            )}
            {source.version_label && (
              <MetaRow label="Version" value={source.version_label} />
            )}
            {source.retrieval_date && (
              <div className="meta-row">
                <span className="meta-label">
                  <Calendar size={10} />
                  Retrieved
                </span>
                <span className="meta-value meta-mono">{source.retrieval_date}</span>
              </div>
            )}
            {hasDateRange && (
              <MetaRow
                label="Effective"
                value={`${source.effective_from ?? '—'} → ${source.effective_to ?? 'present'}`}
                mono
              />
            )}
          </div>
        )}

        {source.source_url && (
          <a
            href={source.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="source-url-link"
          >
            <ExternalLink size={12} />
            View official source
          </a>
        )}
      </div>
    </aside>
  )
}
