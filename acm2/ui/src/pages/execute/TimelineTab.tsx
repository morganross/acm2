import { Clock, FileText, CheckCircle, AlertCircle } from 'lucide-react'
import type { Run } from '../../api'
import { formatTime, computeEndTime } from './utils'

interface TimelineTabProps {
  currentRun: Run | null
}

export default function TimelineTab({ currentRun }: TimelineTabProps) {
  const timelineEvents = currentRun?.timeline_events || []
  const generationEvents = currentRun?.generation_events || []
  
  // Phase color mapping
  const phaseColors: Record<string, { bg: string; border: string; text: string }> = {
    initialization: { bg: '#dbeafe', border: '#3b82f6', text: '#1d4ed8' },
    generation: { bg: '#fef3c7', border: '#f59e0b', text: '#b45309' },
    evaluation: { bg: '#d1fae5', border: '#10b981', text: '#047857' },
    pairwise: { bg: '#e9d5ff', border: '#a855f7', text: '#7c3aed' },
    combination: { bg: '#fce7f3', border: '#ec4899', text: '#be185d' },
    completion: { bg: '#cffafe', border: '#06b6d4', text: '#0e7490' },
  }

  return (
    <div className="p-5 space-y-8">
      {/* Timeline Events */}
      <div>
        <h4 className="text-lg font-semibold mb-4 flex items-center gap-2" style={{ color: '#059669' }}>
          <Clock className="w-5 h-5" />
          Execution Timeline
        </h4>
        
        {timelineEvents.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <Clock className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No timeline events available yet.</p>
            <p className="text-sm mt-2">Timeline events will appear after run execution.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {timelineEvents.map((event, idx) => {
              const colors = phaseColors[event.phase] || phaseColors.initialization
              return (
                <div 
                  key={idx}
                  className="flex items-center gap-4 p-3 rounded-lg"
                  style={{ backgroundColor: colors.bg, borderLeft: `4px solid ${colors.border}` }}
                >
                  <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center" style={{ backgroundColor: colors.border }}>
                    <span className="text-white font-bold text-sm">{idx + 1}</span>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm" style={{ color: colors.text }}>
                        {event.phase.toUpperCase()}
                      </span>
                      <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: 'rgba(0,0,0,0.1)' }}>
                        {event.event_type}
                      </span>
                      {event.success ? (
                        <CheckCircle className="w-4 h-4 text-green-600" />
                      ) : (
                        <AlertCircle className="w-4 h-4 text-red-600" />
                      )}
                    </div>
                    <p className="text-sm text-gray-700 mt-1">{event.description}</p>
                  </div>
                  <div className="flex-shrink-0 text-right text-xs text-gray-500">
                    {event.model && <div className="font-mono">{event.model}</div>}
                    {event.duration_seconds != null && <div>{event.duration_seconds.toFixed(2)}s</div>}
                    {event.details?.cost_usd != null && event.details.cost_usd > 0 && (
                      <div className="font-mono text-green-700">${event.details.cost_usd.toFixed(4)}</div>
                    )}
                    {event.timestamp && <div>{new Date(event.timestamp).toLocaleTimeString()}</div>}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
      
      {/* Generation Details Table */}
      <div className="mt-8 pt-6" style={{ borderTop: '2px solid #e9ecef' }}>
        <h4 className="text-lg font-semibold mb-4 flex items-center gap-2" style={{ color: '#f59e0b' }}>
          <FileText className="w-5 h-5" />
          Generation Details
        </h4>
        
        {generationEvents.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No generation details available yet.</p>
            <p className="text-sm mt-2">Generation details will appear after document generation.</p>
          </div>
        ) : (
          <>
            {(() => {
              const totalDuration = generationEvents.reduce((sum, e) => sum + (e.duration_seconds || 0), 0)
              const totalCost = generationEvents.reduce((sum, e) => sum + (e.cost_usd || 0), 0)
              const maxDuration = Math.max(...generationEvents.map(e => e.duration_seconds || 0), 1)
              
              return (
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse" style={{ backgroundColor: 'white', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                    <thead>
                      <tr>
                        <th className="text-left p-3 font-semibold text-sm" style={{ backgroundColor: '#343a40', color: 'white', borderBottom: '2px solid #212529' }}>
                          Document ID
                        </th>
                        <th className="text-left p-3 font-semibold text-sm" style={{ backgroundColor: '#343a40', color: 'white', borderBottom: '2px solid #212529' }}>
                          Generator
                        </th>
                        <th className="text-left p-3 font-semibold text-sm" style={{ backgroundColor: '#343a40', color: 'white', borderBottom: '2px solid #212529' }}>
                          Model
                        </th>
                        <th className="text-center p-3 font-semibold text-sm" style={{ backgroundColor: '#343a40', color: 'white', borderBottom: '2px solid #212529' }}>
                          Start
                        </th>
                        <th className="text-center p-3 font-semibold text-sm" style={{ backgroundColor: '#343a40', color: 'white', borderBottom: '2px solid #212529' }}>
                          End
                        </th>
                        <th className="text-center p-3 font-semibold text-sm" style={{ backgroundColor: '#343a40', color: 'white', borderBottom: '2px solid #212529' }}>
                          Duration
                        </th>
                        <th className="text-center p-3 font-semibold text-sm" style={{ backgroundColor: '#343a40', color: 'white', borderBottom: '2px solid #212529', minWidth: '120px' }}>
                          Visual
                        </th>
                        <th className="text-center p-3 font-semibold text-sm" style={{ backgroundColor: '#343a40', color: 'white', borderBottom: '2px solid #212529' }}>
                          Cost
                        </th>
                        <th className="text-center p-3 font-semibold text-sm" style={{ backgroundColor: '#343a40', color: 'white', borderBottom: '2px solid #212529' }}>
                          Status
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {generationEvents.map((event, idx) => {
                        const barPct = event.duration_seconds ? Math.min(100, (event.duration_seconds / maxDuration) * 100) : 0
                        const barColor = event.success !== false ? '#28a745' : '#dc3545'
                        return (
                          <tr 
                            key={idx}
                            style={{ 
                              borderTop: '1px solid #e9ecef',
                              backgroundColor: idx % 2 === 0 ? '#fff' : '#fafafa'
                            }}
                          >
                            <td className="p-3">
                              <span className="font-mono text-sm truncate max-w-[200px] block" title={event.doc_id}>
                                {event.doc_id.length > 25 ? event.doc_id.substring(0, 22) + '...' : event.doc_id}
                              </span>
                            </td>
                            <td className="p-3">
                              <span 
                                className="px-2 py-1 rounded text-xs font-medium"
                                style={{ 
                                  backgroundColor: event.generator === 'fpf' ? '#dbeafe' : event.generator === 'gptr' ? '#fef3c7' : '#f3f4f6',
                                  color: event.generator === 'fpf' ? '#1d4ed8' : event.generator === 'gptr' ? '#b45309' : '#374151'
                                }}
                              >
                                {event.generator.toUpperCase()}
                              </span>
                            </td>
                            <td className="p-3">
                              <span className="text-sm text-gray-700">{event.model || '-'}</span>
                            </td>
                            <td className="p-3 text-center">
                              <span className="font-mono text-xs">{formatTime(event.started_at)}</span>
                            </td>
                            <td className="p-3 text-center">
                              <span className="font-mono text-xs">{formatTime(event.completed_at)}</span>
                            </td>
                            <td className="p-3 text-center">
                              <span className="font-mono text-sm">
                                {event.duration_seconds != null ? `${event.duration_seconds.toFixed(2)}s` : '-'}
                              </span>
                            </td>
                            <td className="p-3">
                              <div style={{ height: '16px', width: `${barPct}%`, backgroundColor: barColor, borderRadius: '3px', minWidth: '2px' }} />
                            </td>
                            <td className="p-3 text-center">
                              <span className="font-mono text-sm text-green-700">
                                {event.cost_usd != null ? `$${event.cost_usd.toFixed(4)}` : '-'}
                              </span>
                            </td>
                            <td className="p-3 text-center">
                              {event.success !== false ? (
                                <span className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium" style={{ backgroundColor: '#d1fae5', color: '#047857' }}>
                                  <CheckCircle className="w-3 h-3" /> ✓
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium" style={{ backgroundColor: '#fee2e2', color: '#dc2626' }}>
                                  <AlertCircle className="w-3 h-3" /> ✗
                                </span>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                    <tfoot>
                      <tr style={{ backgroundColor: '#343a40', borderTop: '2px solid #212529', color: 'white' }}>
                        <td colSpan={5} className="p-3 font-semibold text-sm">Totals</td>
                        <td className="p-3 text-center font-semibold text-sm font-mono">
                          {totalDuration.toFixed(2)}s
                        </td>
                        <td></td>
                        <td className="p-3 text-center font-semibold text-sm font-mono">
                          ${totalCost.toFixed(4)}
                        </td>
                        <td className="p-3 text-center font-semibold text-sm">
                          {generationEvents.filter(e => e.success !== false).length}/{generationEvents.length}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              )
            })()}
          </>
        )}
      </div>
      
      {/* Evaluation Details Table */}
      <div className="mt-8 pt-6" style={{ borderTop: '2px solid #e9ecef' }}>
        <h4 className="text-lg font-semibold mb-4 flex items-center gap-2" style={{ color: '#10b981' }}>
          <CheckCircle className="w-5 h-5" />
          Evaluation Details
        </h4>
        
        {(() => {
          const evalEvents = (currentRun?.timeline_events || []).filter(
            (e) => e.phase === 'evaluation' || e.phase === 'pairwise'
          )
          
          if (evalEvents.length === 0) {
            return (
              <div className="text-center text-gray-500 py-8">
                <CheckCircle className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>No evaluation details available yet.</p>
                <p className="text-sm mt-2">Evaluation details will appear after document evaluation.</p>
              </div>
            )
          }
          
          const totalDuration = evalEvents.reduce((sum, e) => sum + (e.duration_seconds || 0), 0 as number)
          const maxDuration = Math.max(...evalEvents.map((e) => e.duration_seconds || 0), 1)
          
          return (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse" style={{ backgroundColor: 'white', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                <thead>
                  <tr>
                    <th className="text-left p-3 font-semibold text-sm" style={{ backgroundColor: '#10b981', color: 'white', borderBottom: '2px solid #047857' }}>
                      Phase
                    </th>
                    <th className="text-left p-3 font-semibold text-sm" style={{ backgroundColor: '#10b981', color: 'white', borderBottom: '2px solid #047857' }}>
                      Description
                    </th>
                    <th className="text-left p-3 font-semibold text-sm" style={{ backgroundColor: '#10b981', color: 'white', borderBottom: '2px solid #047857' }}>
                      Model
                    </th>
                    <th className="text-center p-3 font-semibold text-sm" style={{ backgroundColor: '#10b981', color: 'white', borderBottom: '2px solid #047857' }}>
                      Start
                    </th>
                    <th className="text-center p-3 font-semibold text-sm" style={{ backgroundColor: '#10b981', color: 'white', borderBottom: '2px solid #047857' }}>
                      End
                    </th>
                    <th className="text-center p-3 font-semibold text-sm" style={{ backgroundColor: '#10b981', color: 'white', borderBottom: '2px solid #047857' }}>
                      Duration
                    </th>
                    <th className="text-center p-3 font-semibold text-sm" style={{ backgroundColor: '#10b981', color: 'white', borderBottom: '2px solid #047857', minWidth: '120px' }}>
                      Visual
                    </th>
                    <th className="text-center p-3 font-semibold text-sm" style={{ backgroundColor: '#10b981', color: 'white', borderBottom: '2px solid #047857' }}>
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {evalEvents.map((event, idx) => {
                    const barPct = event.duration_seconds ? Math.min(100, (event.duration_seconds / maxDuration) * 100) : 0
                    const barColor = event.phase === 'pairwise' ? '#a855f7' : '#10b981'
                    return (
                      <tr 
                        key={idx}
                        style={{ 
                          borderTop: '1px solid #e9ecef',
                          backgroundColor: idx % 2 === 0 ? '#fff' : '#fafafa'
                        }}
                      >
                        <td className="p-3">
                          <span 
                            className="px-2 py-1 rounded text-xs font-medium"
                            style={{ 
                              backgroundColor: event.phase === 'pairwise' ? '#e9d5ff' : '#d1fae5',
                              color: event.phase === 'pairwise' ? '#7c3aed' : '#047857'
                            }}
                          >
                            {event.phase.toUpperCase()}
                          </span>
                        </td>
                        <td className="p-3">
                          <span className="text-sm text-gray-700">{event.description}</span>
                        </td>
                        <td className="p-3">
                          <span className="text-sm font-mono text-gray-700">{event.model || '-'}</span>
                        </td>
                        <td className="p-3 text-center">
                          <span className="font-mono text-xs">{formatTime(event.timestamp)}</span>
                        </td>
                        <td className="p-3 text-center">
                          <span className="font-mono text-xs">{computeEndTime(event.timestamp, event.completed_at, event.duration_seconds)}</span>
                        </td>
                        <td className="p-3 text-center">
                          <span className="font-mono text-sm">
                            {event.duration_seconds != null ? `${event.duration_seconds.toFixed(2)}s` : '-'}
                          </span>
                        </td>
                        <td className="p-3">
                          <div style={{ height: '16px', width: `${barPct}%`, backgroundColor: barColor, borderRadius: '3px', minWidth: '2px' }} />
                        </td>
                        <td className="p-3 text-center">
                          {event.success !== false ? (
                            <span className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium" style={{ backgroundColor: '#d1fae5', color: '#047857' }}>
                              <CheckCircle className="w-3 h-3" /> ✓
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium" style={{ backgroundColor: '#fee2e2', color: '#dc2626' }}>
                              <AlertCircle className="w-3 h-3" /> ✗
                            </span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
                <tfoot>
                  <tr style={{ backgroundColor: '#10b981', borderTop: '2px solid #047857', color: 'white' }}>
                    <td colSpan={5} className="p-3 font-semibold text-sm">Totals</td>
                    <td className="p-3 text-center font-semibold text-sm font-mono">
                      {totalDuration.toFixed(2)}s
                    </td>
                    <td></td>
                    <td className="p-3 text-center font-semibold text-sm">
                      {evalEvents.filter((e: { success?: boolean }) => e.success !== false).length}/{evalEvents.length}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )
        })()}
      </div>
    </div>
  )
}
