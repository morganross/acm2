import { Clock, FileText, CheckCircle, AlertCircle } from 'lucide-react'
import type { SourceDocResult } from '../../api'

interface SourceDocTimelineContentProps {
  sourceDocResult: SourceDocResult
}

export default function SourceDocTimelineContent({ sourceDocResult }: SourceDocTimelineContentProps) {
  const timelineEvents = sourceDocResult.timeline_events || []
  
  // Phase color mapping (dark mode compatible)
  const phaseColors: Record<string, { bg: string; border: string; text: string }> = {
    initialization: { bg: '#1e3a5f', border: '#3b82f6', text: '#93c5fd' },
    generation: { bg: '#422006', border: '#f59e0b', text: '#fcd34d' },
    evaluation: { bg: '#064e3b', border: '#10b981', text: '#6ee7b7' },
    pairwise: { bg: '#3b0764', border: '#a855f7', text: '#d8b4fe' },
    combination: { bg: '#500724', border: '#ec4899', text: '#f9a8d4' },
    completion: { bg: '#083344', border: '#06b6d4', text: '#67e8f9' },
  }

  // Format duration
  const formatDuration = (seconds?: number) => {
    if (seconds === undefined || seconds === null) return null
    if (seconds < 60) return `${seconds.toFixed(2)}s`
    const mins = Math.floor(seconds / 60)
    const secs = (seconds % 60).toFixed(1)
    return `${mins}m ${secs}s`
  }

  return (
    <div style={{ color: '#e5e7eb' }}>
      {/* Header Stats */}
      <div style={{ 
        display: 'flex', 
        gap: '24px', 
        marginBottom: '16px',
        padding: '12px 16px',
        backgroundColor: '#111827',
        borderRadius: '8px'
      }}>
        {sourceDocResult.started_at && (
          <div>
            <span style={{ color: '#9ca3af', fontSize: '12px' }}>Started:</span>
            <div style={{ fontSize: '14px', fontWeight: 500 }}>
              {new Date(sourceDocResult.started_at).toLocaleTimeString()}
            </div>
          </div>
        )}
        {sourceDocResult.completed_at && (
          <div>
            <span style={{ color: '#9ca3af', fontSize: '12px' }}>Completed:</span>
            <div style={{ fontSize: '14px', fontWeight: 500 }}>
              {new Date(sourceDocResult.completed_at).toLocaleTimeString()}
            </div>
          </div>
        )}
        {sourceDocResult.duration_seconds > 0 && (
          <div>
            <span style={{ color: '#9ca3af', fontSize: '12px' }}>Duration:</span>
            <div style={{ fontSize: '14px', fontWeight: 500 }}>
              {formatDuration(sourceDocResult.duration_seconds)}
            </div>
          </div>
        )}
        {sourceDocResult.cost_usd > 0 && (
          <div>
            <span style={{ color: '#9ca3af', fontSize: '12px' }}>Cost:</span>
            <div style={{ fontSize: '14px', fontWeight: 500, color: '#fcd34d' }}>
              ${sourceDocResult.cost_usd.toFixed(4)}
            </div>
          </div>
        )}
      </div>

      {/* Timeline Events */}
      <h4 style={{ 
        fontSize: '14px', 
        fontWeight: 600, 
        marginBottom: '12px', 
        display: 'flex', 
        alignItems: 'center', 
        gap: '8px',
        color: '#10b981'
      }}>
        <Clock size={16} />
        Execution Timeline
      </h4>
      
      {timelineEvents.length === 0 ? (
        <div style={{ 
          textAlign: 'center', 
          color: '#6b7280', 
          padding: '32px 0' 
        }}>
          <Clock size={32} style={{ opacity: 0.5, marginBottom: '8px' }} />
          <p style={{ fontSize: '14px' }}>No timeline events available yet.</p>
          <p style={{ fontSize: '12px', marginTop: '4px' }}>
            Events will appear as this document is processed.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {timelineEvents.map((event, idx) => {
            const colors = phaseColors[event.phase] || phaseColors.initialization
            return (
              <div 
                key={idx}
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '12px', 
                  padding: '10px 12px',
                  borderRadius: '6px',
                  backgroundColor: colors.bg,
                  borderLeft: `3px solid ${colors.border}`
                }}
              >
                <div style={{ 
                  flexShrink: 0, 
                  width: '24px', 
                  height: '24px', 
                  borderRadius: '50%', 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center',
                  backgroundColor: colors.border,
                  color: 'white',
                  fontWeight: 'bold',
                  fontSize: '11px'
                }}>
                  {idx + 1}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ 
                      fontWeight: 600, 
                      fontSize: '12px', 
                      color: colors.text,
                      textTransform: 'uppercase'
                    }}>
                      {event.phase}
                    </span>
                    <span style={{ 
                      fontSize: '11px', 
                      padding: '2px 6px', 
                      borderRadius: '4px',
                      backgroundColor: 'rgba(0,0,0,0.2)',
                      color: '#d1d5db'
                    }}>
                      {event.event_type}
                    </span>
                    {event.success !== undefined && (
                      event.success ? (
                        <CheckCircle size={14} style={{ color: '#22c55e' }} />
                      ) : (
                        <AlertCircle size={14} style={{ color: '#ef4444' }} />
                      )
                    )}
                  </div>
                  <p style={{ fontSize: '12px', color: '#d1d5db', marginTop: '4px' }}>
                    {event.description}
                  </p>
                </div>
                <div style={{ 
                  flexShrink: 0, 
                  textAlign: 'right', 
                  fontSize: '11px', 
                  color: '#9ca3af' 
                }}>
                  {event.model && (
                    <div style={{ fontFamily: 'monospace' }}>{event.model}</div>
                  )}
                  {event.duration_seconds != null && (
                    <div>{event.duration_seconds.toFixed(2)}s</div>
                  )}
                  {event.timestamp && (
                    <div>{new Date(event.timestamp).toLocaleTimeString()}</div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Generated Docs Summary */}
      {sourceDocResult.generated_docs.length > 0 && (
        <div style={{ marginTop: '20px' }}>
          <h4 style={{ 
            fontSize: '14px', 
            fontWeight: 600, 
            marginBottom: '12px', 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px',
            color: '#f59e0b'
          }}>
            <FileText size={16} />
            Generated Documents ({sourceDocResult.generated_docs.length})
          </h4>
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
            gap: '8px'
          }}>
            {sourceDocResult.generated_docs.map((doc, idx) => (
              <div 
                key={doc.id || idx}
                style={{
                  padding: '10px 12px',
                  backgroundColor: '#111827',
                  borderRadius: '6px',
                  border: doc.id === sourceDocResult.winner_doc_id 
                    ? '2px solid #22c55e' 
                    : '1px solid #374151'
                }}
              >
                <div style={{ 
                  fontSize: '12px', 
                  fontWeight: 500,
                  color: doc.id === sourceDocResult.winner_doc_id ? '#86efac' : '#e5e7eb',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}>
                  {doc.id === sourceDocResult.winner_doc_id && (
                    <CheckCircle size={14} style={{ color: '#22c55e' }} />
                  )}
                  {doc.generator || doc.model || 'Document'}
                </div>
                <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '4px' }}>
                  {doc.model && <div>Model: {doc.model}</div>}
                  <div>Iteration: {doc.iteration}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
