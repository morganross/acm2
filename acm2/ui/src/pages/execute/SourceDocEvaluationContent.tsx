import { FileText, Loader2, X, ExternalLink, Target } from 'lucide-react'
import { useState } from 'react'
import type { SourceDocResult, GeneratedDocInfo, DocumentEvalDetail } from '../../api'
import { getScoreBadgeStyle } from './utils'

interface SourceDocEvaluationContentProps {
  sourceDocResult: SourceDocResult
  runId: string
  criteriaList: string[]
  evaluatorList: string[]
  evalDeviations?: Record<string, Record<string, number>>  // { judge_model: { criterion: deviation } }
}

interface DocViewerState {
  isOpen: boolean
  docId: string
  model: string
  content: string | null
  loading: boolean
  error: string | null
}

export default function SourceDocEvaluationContent({ 
  sourceDocResult, 
  runId,
  criteriaList,
  evaluatorList,
  evalDeviations,
}: SourceDocEvaluationContentProps) {
  const [docViewer, setDocViewer] = useState<DocViewerState>({
    isOpen: false,
    docId: '',
    model: '',
    content: null,
    loading: false,
    error: null,
  })

  const openDocViewer = async (docId: string, model: string) => {
    setDocViewer({
      isOpen: true,
      docId,
      model,
      content: null,
      loading: true,
      error: null,
    })
    
    try {
      const response = await fetch(`/api/v1/runs/${runId}/generated/${encodeURIComponent(docId)}`)
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to load document')
      }
      const data = await response.json()
      setDocViewer(prev => ({
        ...prev,
        content: data.content,
        loading: false,
      }))
    } catch (err) {
      setDocViewer(prev => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to load document',
      }))
    }
  }

  const closeDocViewer = () => {
    setDocViewer({
      isOpen: false,
      docId: '',
      model: '',
      content: null,
      loading: false,
      error: null,
    })
  }

  const { generated_docs, single_eval_scores, single_eval_detailed, combined_doc, combined_docs, post_combine_eval_scores, winner_doc_id } = sourceDocResult
  
  // Use combined_docs array if available, fallback to combined_doc for backward compat
  const allCombinedDocs = combined_docs?.length ? combined_docs : (combined_doc ? [combined_doc] : [])
  
  // No data state
  if (generated_docs.length === 0 && Object.keys(single_eval_scores).length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '32px', color: '#9ca3af' }}>
        <Target size={48} style={{ margin: '0 auto 12px', opacity: 0.5 }} />
        <p>No evaluation data available yet.</p>
        <p style={{ fontSize: '12px', marginTop: '8px' }}>
          Evaluations will appear here once document generation completes.
        </p>
      </div>
    )
  }

  const hasDetailedHeatmapData =
    !!single_eval_detailed &&
    Object.keys(single_eval_detailed).length > 0 &&
    criteriaList.length > 0 &&
    evaluatorList.length > 0

  const renderACM1StyleHeatmap = (
    title: string,
    docs: Array<{ id: string; model: string; generator: string }>,
    detailedData: Record<string, DocumentEvalDetail>,
    sectionColor: string,
    criteria: string[],
    evaluators: string[]
  ) => {
    if (docs.length === 0) return null

    // Build a lookup: { doc_id: { criterion: { judge_model: { score, reason } } } }
    const scoreLookup: Record<string, Record<string, Record<string, { score: number; reason: string }>>> = {}
    for (const docId of Object.keys(detailedData)) {
      scoreLookup[docId] = {}
      const detail = detailedData[docId]
      for (const evaluation of detail.evaluations) {
        for (const cs of evaluation.scores) {
          if (!scoreLookup[docId][cs.criterion]) {
            scoreLookup[docId][cs.criterion] = {}
          }
          scoreLookup[docId][cs.criterion][evaluation.judge_model] = {
            score: cs.score,
            reason: cs.reason,
          }
        }
      }
    }

    const maxPossible = criteria.length * evaluators.length * 5

    return (
      <div style={{ marginBottom: '16px' }}>
        <h4 style={{ color: sectionColor, fontSize: '14px', fontWeight: 600, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Target size={16} />
          {title}
        </h4>

        <div style={{ marginBottom: '12px', padding: '10px 12px', borderRadius: '8px', fontSize: '12px', backgroundColor: '#111827', border: '1px solid #374151', color: '#9ca3af' }}>
          <strong style={{ color: '#d1d5db' }}>Evaluators:</strong> {evaluators.join(', ')}
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', backgroundColor: '#111827', border: '1px solid #374151' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', padding: '12px', backgroundColor: '#374151', color: 'white', fontSize: '13px', borderBottom: '2px solid #4b5563' }}>
                  Document
                </th>
                {criteria.map((criterion) => (
                  <th
                    key={criterion}
                    style={{ textAlign: 'center', padding: '12px', backgroundColor: '#374151', color: 'white', fontSize: '12px', borderBottom: '2px solid #4b5563' }}
                    title={criterion}
                  >
                    {criterion.length > 12 ? criterion.substring(0, 12) + '...' : criterion}
                  </th>
                ))}
                <th style={{ textAlign: 'center', padding: '12px', backgroundColor: '#374151', color: 'white', fontSize: '13px', borderBottom: '2px solid #4b5563' }}>
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {docs.map((doc, rowIdx) => {
                const docScores = scoreLookup[doc.id] || {}

                let totalScore = 0
                let scoreCount = 0
                for (const criterion of criteria) {
                  const criterionScores = docScores[criterion] || {}
                  for (const judgeModel of evaluators) {
                    if (criterionScores[judgeModel]) {
                      totalScore += criterionScores[judgeModel].score
                      scoreCount++
                    }
                  }
                }
                const percentage = maxPossible > 0 ? ((totalScore / maxPossible) * 100).toFixed(1) : '0.0'

                return (
                  <tr key={doc.id} style={{ borderBottom: '1px solid #374151', backgroundColor: rowIdx % 2 === 0 ? '#111827' : '#1f2937' }}>
                    <td style={{ padding: '12px', fontWeight: 600, color: '#d1d5db' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span
                          style={{
                            fontSize: '10px',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            backgroundColor: doc.generator === 'fpf' ? '#1e3a5f' : doc.generator === 'gptr' ? '#5f3a1e' : '#3b235a',
                            color: doc.generator === 'fpf' ? '#93c5fd' : doc.generator === 'gptr' ? '#fdba74' : '#c4b5fd',
                          }}
                        >
                          {doc.generator.toUpperCase()}
                        </span>
                        <button
                          onClick={() => openDocViewer(doc.id, doc.model)}
                          style={{
                            color: '#60a5fa',
                            background: 'none',
                            border: 'none',
                            padding: 0,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            fontSize: '13px',
                            fontFamily: 'monospace',
                            fontWeight: 600,
                          }}
                          title={`View ${doc.model}`}
                        >
                          {doc.model.length > 20 ? doc.model.substring(0, 20) + '...' : doc.model}
                          <ExternalLink size={12} />
                        </button>
                        {/* Show cost if available */}
                        {sourceDocResult.generated_doc_costs?.[doc.id] !== undefined && (
                          <span
                            style={{
                              fontSize: '10px',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              backgroundColor: '#064e3b',
                              color: '#10b981',
                              fontWeight: 700,
                            }}
                            title={`Generation cost: $${sourceDocResult.generated_doc_costs[doc.id].toFixed(4)}`}
                          >
                            ${sourceDocResult.generated_doc_costs[doc.id].toFixed(4)}
                          </span>
                        )}
                      </div>
                    </td>

                    {criteria.map((criterion) => {
                      const criterionScores = docScores[criterion] || {}
                      return (
                        <td key={criterion} style={{ padding: '10px', textAlign: 'center' }}>
                          <div style={{ display: 'flex', justifyContent: 'center', gap: '4px', flexWrap: 'wrap' }}>
                            {evaluators.map((judgeModel) => {
                              const scoreInfo = criterionScores[judgeModel]
                              if (!scoreInfo) {
                                return (
                                  <span
                                    key={judgeModel}
                                    style={{
                                      display: 'inline-block',
                                      padding: '2px 6px',
                                      borderRadius: '4px',
                                      fontSize: '11px',
                                      fontWeight: 700,
                                      backgroundColor: '#374151',
                                      color: '#9ca3af',
                                    }}
                                    title={`${judgeModel}: No score`}
                                  >
                                    —
                                  </span>
                                )
                              }

                              let bgColor = '#374151'
                              let textColor = '#e5e7eb'
                              if (scoreInfo.score === 5) { bgColor = '#28a745'; textColor = 'white' }
                              else if (scoreInfo.score === 4) { bgColor = '#90EE90'; textColor = '#006400' }
                              else if (scoreInfo.score === 3) { bgColor = '#ffc107'; textColor = '#333' }
                              else if (scoreInfo.score === 2) { bgColor = '#fd7e14'; textColor = 'white' }
                              else if (scoreInfo.score === 1) { bgColor = '#dc3545'; textColor = 'white' }

                              const reasonPreview = scoreInfo.reason.length > 200
                                ? scoreInfo.reason.substring(0, 200) + '...'
                                : scoreInfo.reason

                              return (
                                <span
                                  key={judgeModel}
                                  style={{
                                    display: 'inline-block',
                                    padding: '2px 6px',
                                    borderRadius: '4px',
                                    fontSize: '11px',
                                    fontWeight: 800,
                                    backgroundColor: bgColor,
                                    color: textColor,
                                    minWidth: '20px',
                                    textAlign: 'center',
                                  }}
                                  title={`${judgeModel}: ${reasonPreview}`}
                                >
                                  {scoreInfo.score}
                                </span>
                              )
                            })}
                          </div>
                        </td>
                      )
                    })}

                    <td style={{ padding: '12px', textAlign: 'center', fontWeight: 800, color: '#d1d5db' }}>
                      {percentage}%
                      <span style={{ fontSize: '11px', color: '#9ca3af', marginLeft: '6px' }}>
                        ({totalScore}/{maxPossible})
                      </span>
                    </td>
                  </tr>
                )
              })}
              
              {/* Deviation Row */}
              {evalDeviations && Object.keys(evalDeviations).length > 0 && (
                <tr style={{ borderTop: '3px solid #4b5563', backgroundColor: '#1f2937' }}>
                  <td style={{ padding: '12px', fontWeight: 700, color: '#60a5fa', fontSize: '13px' }}>
                    DEVIATION
                  </td>
                  
                  {criteria.map((criterion) => (
                    <td key={criterion} style={{ padding: '10px', textAlign: 'center' }}>
                      <div style={{ display: 'flex', justifyContent: 'center', gap: '4px', flexWrap: 'wrap' }}>
                        {evaluators.map((judgeModel) => {
                          const deviation = evalDeviations[judgeModel]?.[criterion]
                          
                          if (deviation === undefined) {
                            return (
                              <span
                                key={judgeModel}
                                style={{
                                  display: 'inline-block',
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                  fontSize: '11px',
                                  fontWeight: 700,
                                  backgroundColor: '#374151',
                                  color: '#9ca3af',
                                }}
                                title={`${judgeModel}: No deviation data`}
                              >
                                —
                              </span>
                            )
                          }

                          // Color coding: positive = green, negative = red, near-zero = gray
                          let bgColor = '#6b7280'  // gray for near-zero
                          let textColor = 'white'
                          if (deviation > 1) { bgColor = '#22c55e'; textColor = 'white' }  // green
                          else if (deviation > 0) { bgColor = '#86efac'; textColor = '#166534' }  // light green
                          else if (deviation < -1) { bgColor = '#ef4444'; textColor = 'white' }  // red
                          else if (deviation < 0) { bgColor = '#fca5a5'; textColor = '#991b1b' }  // light red

                          // Format with explicit sign
                          const deviationStr = deviation > 0 ? `+${deviation}` : `${deviation}`

                          return (
                            <span
                              key={judgeModel}
                              style={{
                                display: 'inline-block',
                                padding: '2px 6px',
                                borderRadius: '4px',
                                fontSize: '11px',
                                fontWeight: 800,
                                backgroundColor: bgColor,
                                color: textColor,
                                minWidth: '24px',
                                textAlign: 'center',
                              }}
                              title={`${judgeModel}: ${deviationStr} from average`}
                            >
                              {deviationStr}
                            </span>
                          )
                        })}
                      </div>
                    </td>
                  ))}
                  
                  <td style={{ padding: '12px', textAlign: 'center' }}>
                    <div style={{ display: 'flex', justifyContent: 'center', gap: '4px', flexWrap: 'wrap' }}>
                      {evaluators.map((judgeModel) => {
                        const totalDeviation = evalDeviations[judgeModel]?.__TOTAL__
                        
                        if (totalDeviation === undefined) {
                          return (
                            <span
                              key={judgeModel}
                              style={{
                                display: 'inline-block',
                                padding: '2px 6px',
                                borderRadius: '4px',
                                fontSize: '11px',
                                fontWeight: 700,
                                backgroundColor: '#374151',
                                color: '#9ca3af',
                              }}
                              title={`${judgeModel}: No total deviation`}
                            >
                              —
                            </span>
                          )
                        }

                        // Color coding: positive = green, negative = red, near-zero = gray
                        let bgColor = '#6b7280'  // gray for near-zero
                        let textColor = 'white'
                        if (totalDeviation > 1) { bgColor = '#22c55e'; textColor = 'white' }  // green
                        else if (totalDeviation > 0) { bgColor = '#86efac'; textColor = '#166534' }  // light green
                        else if (totalDeviation < -1) { bgColor = '#ef4444'; textColor = 'white' }  // red
                        else if (totalDeviation < 0) { bgColor = '#fca5a5'; textColor = '#991b1b' }  // light red

                        // Format with explicit sign
                        const deviationStr = totalDeviation > 0 ? `+${totalDeviation}` : `${totalDeviation}`

                        return (
                          <span
                            key={judgeModel}
                            style={{
                              display: 'inline-block',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              fontSize: '11px',
                              fontWeight: 800,
                              backgroundColor: bgColor,
                              color: textColor,
                              minWidth: '24px',
                              textAlign: 'center',
                            }}
                            title={`${judgeModel}: ${deviationStr} total average deviation`}
                          >
                            {deviationStr}
                          </span>
                        )
                      })}
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  // Simple score display when no detailed data
  const renderSimpleScoreTable = () => (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', padding: '12px', backgroundColor: '#374151', color: 'white', fontSize: '13px' }}>
              Generated Document
            </th>
            <th style={{ textAlign: 'center', padding: '12px', backgroundColor: '#374151', color: 'white', fontSize: '13px' }}>
              Average Score
            </th>
            <th style={{ textAlign: 'center', padding: '12px', backgroundColor: '#374151', color: 'white', fontSize: '13px' }}>
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          {generated_docs.map((doc: GeneratedDocInfo, idx: number) => {
            const score = single_eval_scores[doc.id]
            const hasScore = score !== undefined && score !== null
            const isWinner = doc.id === winner_doc_id
            const scoreNum = hasScore ? score : 0
            const normalizedScore = hasScore ? (scoreNum > 1 ? scoreNum / 5 : scoreNum) : undefined
            const scoreStyle = getScoreBadgeStyle(normalizedScore)

            return (
              <tr 
                key={doc.id} 
                style={{ 
                  borderBottom: '1px solid #374151',
                  backgroundColor: isWinner ? 'rgba(134, 239, 172, 0.1)' : idx % 2 === 0 ? '#111827' : '#1f2937'
                }}
              >
                <td style={{ padding: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <FileText size={14} style={{ color: '#6b7280' }} />
                    <button 
                      onClick={() => openDocViewer(doc.id, doc.model)}
                      style={{ 
                        color: '#60a5fa', 
                        background: 'none', 
                        border: 'none', 
                        padding: 0, 
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '13px',
                        fontFamily: 'monospace'
                      }}
                      title={`View ${doc.model}`}
                    >
                      {doc.model.length > 30 ? doc.model.substring(0, 30) + '...' : doc.model}
                      <ExternalLink size={12} />
                    </button>
                    <span 
                      style={{ 
                        fontSize: '10px', 
                        padding: '2px 6px', 
                        borderRadius: '4px',
                        backgroundColor: doc.generator === 'fpf' ? '#1e3a5f' : '#5f3a1e',
                        color: doc.generator === 'fpf' ? '#93c5fd' : '#fdba74'
                      }}
                    >
                      {doc.generator.toUpperCase()}
                    </span>
                    {isWinner && (
                      <span style={{ 
                        fontSize: '10px', 
                        padding: '2px 6px', 
                        borderRadius: '4px',
                        backgroundColor: '#166534',
                        color: '#86efac'
                      }}>
                        WINNER
                      </span>
                    )}
                    {/* Show cost if available */}
                    {sourceDocResult.generated_doc_costs?.[doc.id] !== undefined && (
                      <span
                        style={{
                          fontSize: '10px',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          backgroundColor: '#064e3b',
                          color: '#10b981',
                          fontWeight: 700,
                        }}
                        title={`Generation cost: $${sourceDocResult.generated_doc_costs[doc.id].toFixed(4)}`}
                      >
                        ${sourceDocResult.generated_doc_costs[doc.id].toFixed(4)}
                      </span>
                    )}
                  </div>
                </td>
                <td style={{ padding: '12px', textAlign: 'center' }}>
                  {hasScore ? (
                    <div
                      style={{
                        display: 'inline-block',
                        padding: '8px 16px',
                        borderRadius: '8px',
                        backgroundColor: scoreStyle.bg,
                        color: scoreStyle.text,
                        fontWeight: 'bold',
                        fontSize: '16px',
                      }}
                    >
                      {scoreNum.toFixed(2)}
                      <div style={{ fontSize: '10px', opacity: 0.8, marginTop: '2px' }}>{scoreStyle.label}</div>
                    </div>
                  ) : (
                    <span style={{ color: '#6b7280' }}>—</span>
                  )}
                </td>
                <td style={{ padding: '12px', textAlign: 'center' }}>
                  <span 
                    style={{ 
                      fontSize: '11px', 
                      color: hasScore ? '#86efac' : '#9ca3af'
                    }}
                  >
                    {hasScore ? '✓ Evaluated' : 'Pending'}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )

  // Helper to get a display name from combined doc
  const getCombinedDocDisplayName = (docId: string): string => {
    // Format: "combined.shortid.uuid.provider_model"
    const parts = docId.split('.')
    if (parts.length >= 4) {
      const modelPart = parts.slice(3).join('.').replace('_', ':')
      const fileUuid = parts[2].slice(0, 8)
      return `${modelPart} [${fileUuid}]`
    }
    return docId
  }

  // Post-combine section - now shows all combined docs
  const renderPostCombineSection = () => {
    if (allCombinedDocs.length === 0) return null

    const entries = Object.entries(post_combine_eval_scores || {})
      .filter(([, v]) => v !== undefined && v !== null)
      .map(([k, v]) => [k, Number(v)] as const)
      .filter(([, v]) => !Number.isNaN(v))

    return (
      <div style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid #374151' }}>
        <h4 style={{ color: '#a78bfa', fontSize: '14px', fontWeight: 600, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Target size={16} />
          Combined Documents ({allCombinedDocs.length})
        </h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {allCombinedDocs.map((combinedDoc, idx) => (
            <div 
              key={combinedDoc.id}
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between',
                padding: '12px 16px',
                backgroundColor: '#111827',
                borderRadius: '8px',
                border: '1px solid #374151'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FileText size={14} style={{ color: '#a78bfa' }} />
                <button 
                  onClick={() => openDocViewer(combinedDoc.id, getCombinedDocDisplayName(combinedDoc.id))}
                  style={{ 
                    color: '#a78bfa', 
                    background: 'none', 
                    border: 'none', 
                    padding: 0, 
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontSize: '13px',
                  }}
                >
                  {getCombinedDocDisplayName(combinedDoc.id)}
                  <ExternalLink size={12} />
                </button>
                <span 
                  style={{ 
                    fontSize: '10px', 
                    padding: '2px 6px', 
                    borderRadius: '4px',
                    backgroundColor: '#5b21b6',
                    color: '#c4b5fd'
                  }}
                >
                  COMBINED
                </span>
              </div>
              {entries.length > 0 && idx === 0 ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                  {entries.map(([judgeModel, score]) => {
                    const ns = score > 1 ? score / 5 : score
                    const st = getScoreBadgeStyle(ns)
                    return (
                      <span
                        key={judgeModel}
                        style={{
                          padding: '6px 10px',
                          borderRadius: '999px',
                          backgroundColor: st.bg,
                          color: st.text,
                          fontWeight: 'bold',
                          fontSize: '12px',
                          fontFamily: 'monospace',
                        }}
                        title={judgeModel}
                      >
                        {judgeModel}: {score.toFixed(2)}
                      </span>
                    )
                  })}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div>
      {/* Pre-combine evaluations */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <h4 style={{ color: '#60a5fa', fontSize: '14px', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Target size={16} />
          Generated Documents ({generated_docs.length})
        </h4>
        {sourceDocResult.cost_usd > 0 && (
          <div style={{ fontSize: '13px', color: '#10b981', fontWeight: 700 }}>
            Total Cost: ${sourceDocResult.cost_usd.toFixed(4)}
          </div>
        )}
      </div>

      {hasDetailedHeatmapData
        ? renderACM1StyleHeatmap(
            'Pre-Combine Evaluations - Criteria Heatmap',
            generated_docs,
            (single_eval_detailed || {}) as Record<string, DocumentEvalDetail>,
            '#60a5fa',
            criteriaList,
            evaluatorList
          )
        : renderSimpleScoreTable()}
      {renderPostCombineSection()}

      {/* Document Viewer Modal */}
      {docViewer.isOpen && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={closeDocViewer}
        >
          <div
            style={{
              backgroundColor: '#1f2937',
              borderRadius: '12px',
              width: '80%',
              maxWidth: '900px',
              maxHeight: '80vh',
              overflow: 'hidden',
              border: '1px solid #374151',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '16px',
                borderBottom: '1px solid #374151',
              }}
            >
              <h3 style={{ color: 'white', margin: 0, fontSize: '16px' }}>
                {docViewer.model}
              </h3>
              <button
                onClick={closeDocViewer}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#9ca3af',
                  cursor: 'pointer',
                  padding: '4px',
                }}
              >
                <X size={20} />
              </button>
            </div>
            <div style={{ padding: '16px', overflowY: 'auto', maxHeight: 'calc(80vh - 60px)' }}>
              {docViewer.loading && (
                <div style={{ textAlign: 'center', padding: '32px', color: '#9ca3af' }}>
                  <Loader2 size={24} className="animate-spin" style={{ margin: '0 auto 8px' }} />
                  Loading document...
                </div>
              )}
              {docViewer.error && (
                <div style={{ color: '#fca5a5', padding: '16px', backgroundColor: '#7f1d1d', borderRadius: '8px' }}>
                  {docViewer.error}
                </div>
              )}
              {docViewer.content && (
                <pre
                  style={{
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    color: '#d1d5db',
                    fontSize: '13px',
                    lineHeight: '1.6',
                    margin: 0,
                  }}
                >
                  {docViewer.content}
                </pre>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
