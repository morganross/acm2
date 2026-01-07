import { FileText, Trophy, Users, ExternalLink, X, Loader2, GitMerge } from 'lucide-react'
import { useState } from 'react'
import type { SourceDocResult, PairwiseRanking } from '../../api'

interface SourceDocPairwiseContentProps {
  sourceDocResult: SourceDocResult
  runId: string
}

interface DocViewerState {
  isOpen: boolean
  docId: string
  model: string
  content: string | null
  loading: boolean
  error: string | null
}

export default function SourceDocPairwiseContent({ sourceDocResult, runId }: SourceDocPairwiseContentProps) {
  const { pairwise_results, post_combine_pairwise, winner_doc_id } = sourceDocResult
  const rankings = pairwise_results?.rankings || []

  const comparisons = pairwise_results?.comparisons || []
  
  // Document viewer modal state
  const [docViewer, setDocViewer] = useState<DocViewerState>({
    isOpen: false,
    docId: '',
    model: '',
    content: null,
    loading: false,
    error: null,
  })

  const openDocViewer = async (docId: string, model: string) => {
    if (!runId) return
    
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
  
  // Helper to get a short display name from a doc ID
  const getDocDisplayName = (docId: string): string => {
    if (docId.includes('combined')) {
      return '📦 Combined'
    }
    // Try to extract model name from doc ID patterns like "abcd1234.5678.gptr.1.openai_gpt-4o"
    const parts = docId.split('.')
    if (parts.length >= 5) {
      const modelPart = parts.slice(4).join('.')
      // Format: provider_model -> provider:model
      const formatted = modelPart.replace('_', ':')
      return formatted
    }
    return docId
  }

  const getShortDocId = (docId: string) => {
    return docId
  }

  const getEloForDoc = (docId: string) => {
    const rec = rankings.find(r => r.doc_id === docId)
    return rec?.elo
  }

  const getNetCellStyle = (netScore: number): { bg: string; text: string } => {
    if (netScore > 0) {
      if (netScore >= 3) return { bg: '#16a34a', text: 'white' }
      if (netScore >= 2) return { bg: '#4ade80', text: '#064e3b' }
      return { bg: 'rgba(134, 239, 172, 0.25)', text: '#86efac' }
    } else if (netScore < 0) {
      if (netScore <= -3) return { bg: '#dc2626', text: 'white' }
      if (netScore <= -2) return { bg: '#f87171', text: '#7f1d1d' }
      return { bg: 'rgba(252, 165, 165, 0.20)', text: '#fca5a5' }
    }
    return { bg: '#111827', text: '#9ca3af' }
  }
  
  // No data state
  if (rankings.length === 0 && !post_combine_pairwise) {
    return (
      <div style={{ textAlign: 'center', padding: '32px', color: '#9ca3af' }}>
        <Users size={48} style={{ margin: '0 auto 12px', opacity: 0.5 }} />
        <p>No pairwise comparison data available yet.</p>
        <p style={{ fontSize: '12px', marginTop: '8px' }}>
          Pairwise comparisons require at least 2 generated documents.
        </p>
      </div>
    )
  }

  return (
    <div>
      {/* Info banner */}
      <div
        style={{
          padding: '12px 16px',
          backgroundColor: '#111827',
          borderRadius: '8px',
          marginBottom: '16px',
          fontSize: '13px',
          color: '#d1d5db',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          border: '1px solid #374151',
        }}
      >
        <Trophy size={16} style={{ color: '#fbbf24' }} />
        <span>
          <strong>Pairwise Rankings:</strong> Documents ranked by ELO score from head-to-head comparisons.
        </span>
        {winner_doc_id && (
          <span
            style={{
              marginLeft: 'auto',
              padding: '4px 12px',
              borderRadius: '16px',
              backgroundColor: '#166534',
              color: '#86efac',
              fontSize: '12px',
              fontWeight: 500,
            }}
          >
            Winner: {getDocDisplayName(winner_doc_id)}
          </span>
        )}
      </div>

      {/* Rankings Table */}
      {rankings.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', padding: '12px', backgroundColor: '#374151', color: 'white', fontSize: '13px' }}>
                  Rank
                </th>
                <th style={{ textAlign: 'left', padding: '12px', backgroundColor: '#374151', color: 'white', fontSize: '13px' }}>
                  Document
                </th>
                <th style={{ textAlign: 'center', padding: '12px', backgroundColor: '#374151', color: 'white', fontSize: '13px' }}>
                  Wins
                </th>
                <th style={{ textAlign: 'center', padding: '12px', backgroundColor: '#374151', color: 'white', fontSize: '13px' }}>
                  Losses
                </th>
                <th style={{ textAlign: 'center', padding: '12px', backgroundColor: '#374151', color: 'white', fontSize: '13px' }}>
                  Win Rate
                </th>
                <th style={{ textAlign: 'center', padding: '12px', backgroundColor: '#374151', color: 'white', fontSize: '13px' }}>
                  ELO
                </th>
              </tr>
            </thead>
            <tbody>
              {rankings
                .sort((a: PairwiseRanking, b: PairwiseRanking) => b.elo - a.elo)
                .map((ranking: PairwiseRanking, idx: number) => {
                  const total = ranking.wins + ranking.losses
                  const winRate = total > 0 ? (ranking.wins / total) * 100 : 0
                  const isWinner = ranking.doc_id === winner_doc_id

                  return (
                    <tr
                      key={ranking.doc_id}
                      style={{
                        borderBottom: '1px solid #374151',
                        backgroundColor: isWinner 
                          ? 'rgba(134, 239, 172, 0.1)' 
                          : idx % 2 === 0 ? '#111827' : '#1f2937',
                      }}
                    >
                      <td style={{ padding: '12px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          {idx === 0 && <span style={{ fontSize: '20px' }}>🥇</span>}
                          {idx === 1 && <span style={{ fontSize: '20px' }}>🥈</span>}
                          {idx === 2 && <span style={{ fontSize: '20px' }}>🥉</span>}
                          {idx > 2 && <span style={{ color: '#6b7280', fontSize: '14px' }}>#{idx + 1}</span>}
                        </div>
                      </td>
                      <td style={{ padding: '12px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <FileText size={14} style={{ color: '#6b7280' }} />
                          <button
                            onClick={() => openDocViewer(ranking.doc_id, getDocDisplayName(ranking.doc_id))}
                            style={{
                              fontFamily: 'monospace',
                              fontSize: '12px',
                              color: '#60a5fa',
                              background: 'none',
                              border: 'none',
                              padding: 0,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                            title={`View ${ranking.doc_id}`}
                          >
                            {getDocDisplayName(ranking.doc_id)}
                            <ExternalLink size={12} />
                          </button>
                          {isWinner && (
                            <span
                              style={{
                                fontSize: '10px',
                                padding: '2px 6px',
                                borderRadius: '4px',
                                backgroundColor: '#166534',
                                color: '#86efac',
                              }}
                            >
                              WINNER
                            </span>
                          )}
                        </div>
                      </td>
                      <td style={{ padding: '12px', textAlign: 'center', color: '#86efac', fontWeight: 500 }}>
                        {ranking.wins}
                      </td>
                      <td style={{ padding: '12px', textAlign: 'center', color: '#fca5a5', fontWeight: 500 }}>
                        {ranking.losses}
                      </td>
                      <td style={{ padding: '12px', textAlign: 'center' }}>
                        <div
                          style={{
                            display: 'inline-block',
                            padding: '4px 10px',
                            borderRadius: '12px',
                            backgroundColor: winRate >= 50 ? 'rgba(134, 239, 172, 0.2)' : 'rgba(252, 165, 165, 0.2)',
                            color: winRate >= 50 ? '#86efac' : '#fca5a5',
                            fontSize: '12px',
                            fontWeight: 500,
                          }}
                        >
                          {winRate.toFixed(0)}%
                        </div>
                      </td>
                      <td style={{ padding: '12px', textAlign: 'center' }}>
                        <span
                          style={{
                            fontWeight: 'bold',
                            fontSize: '14px',
                            color: idx === 0 ? '#fbbf24' : '#d1d5db',
                          }}
                        >
                          {Math.round(ranking.elo)}
                        </span>
                      </td>
                    </tr>
                  )
                })}
            </tbody>
          </table>
        </div>
      )}

      {/* Head-to-Head Comparison Matrix */}
      {comparisons.length > 0 && (
        <div style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid #374151' }}>
          <h4
            style={{
              color: '#60a5fa',
              fontSize: '14px',
              fontWeight: 600,
              marginBottom: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <FileText size={16} />
            Head-to-Head Comparison Matrix
          </h4>

          {(() => {
            const docIds = Array.from(
              new Set([
                ...comparisons.map(c => c.doc_id_a),
                ...comparisons.map(c => c.doc_id_b),
              ])
            )

            const pairResults: Record<string, Record<string, { rowWins: number; colWins: number }>> = {}
            for (const docId of docIds) {
              pairResults[docId] = {}
              for (const otherId of docIds) {
                pairResults[docId][otherId] = { rowWins: 0, colWins: 0 }
              }
            }

            for (const comp of comparisons) {
              if (!comp?.doc_id_a || !comp?.doc_id_b) continue
              if (comp.winner === comp.doc_id_a) {
                pairResults[comp.doc_id_a][comp.doc_id_b].rowWins++
                pairResults[comp.doc_id_b][comp.doc_id_a].colWins++
              } else if (comp.winner === comp.doc_id_b) {
                pairResults[comp.doc_id_a][comp.doc_id_b].colWins++
                pairResults[comp.doc_id_b][comp.doc_id_a].rowWins++
              }
            }

            return (
              <div style={{ overflowX: 'auto' }}>
                <table
                  style={{
                    borderCollapse: 'collapse',
                    backgroundColor: '#0b1220',
                    border: '1px solid #374151',
                  }}
                >
                  <thead>
                    <tr>
                      <th
                        style={{
                          padding: '8px 10px',
                          textAlign: 'left',
                          fontSize: '12px',
                          color: '#86efac',
                          borderBottom: '2px solid #16a34a',
                          minWidth: '140px',
                          backgroundColor: '#111827',
                        }}
                      >
                        Row vs Column →
                      </th>
                      {docIds.map(colId => {
                        const label = getShortDocId(colId)
                        const elo = getEloForDoc(colId)
                        const isWinner = winner_doc_id && colId === winner_doc_id
                        return (
                          <th
                            key={colId}
                            title={colId}
                            style={{
                              padding: '6px 4px',
                              textAlign: 'center',
                              fontSize: '11px',
                              color: '#fca5a5',
                              borderBottom: '2px solid #dc2626',
                              borderLeft: '1px solid #374151',
                              writingMode: 'vertical-rl',
                              transform: 'rotate(180deg)',
                              height: '150px',
                              whiteSpace: 'nowrap',
                              backgroundColor: '#111827',
                            }}
                          >
                            {isWinner ? '🏆 ' : ''}
                            {label}
                            {typeof elo === 'number' ? `\nELO: ${elo.toFixed(0)}` : ''}
                          </th>
                        )
                      })}
                    </tr>
                  </thead>
                  <tbody>
                    {docIds.map(rowId => {
                      const rowElo = getEloForDoc(rowId)
                      const isRowWinner = winner_doc_id && rowId === winner_doc_id
                      return (
                        <tr key={rowId}>
                          <td
                            title={rowId}
                            style={{
                              padding: '8px 10px',
                              fontSize: '12px',
                              color: '#d1d5db',
                              borderRight: '2px solid #16a34a',
                              borderBottom: '1px solid #374151',
                              backgroundColor: '#111827',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {isRowWinner ? '🏆 ' : ''}
                            {getShortDocId(rowId)}
                            {typeof rowElo === 'number' ? (
                              <span style={{ color: '#9ca3af' }}>{` (ELO: ${rowElo.toFixed(0)})`}</span>
                            ) : null}
                          </td>

                          {docIds.map(colId => {
                            if (rowId === colId) {
                              return (
                                <td
                                  key={colId}
                                  style={{
                                    padding: '8px',
                                    textAlign: 'center',
                                    fontSize: '12px',
                                    color: '#6b7280',
                                    borderBottom: '1px solid #374151',
                                    borderLeft: '1px solid #374151',
                                    backgroundColor: '#0b1220',
                                  }}
                                >
                                  —
                                </td>
                              )
                            }

                            const cell = pairResults[rowId]?.[colId]
                            const net = cell ? cell.rowWins - cell.colWins : 0
                            const style = getNetCellStyle(net)
                            const tooltip = `Row wins: ${cell?.rowWins ?? 0}\nColumn wins: ${cell?.colWins ?? 0}`

                            return (
                              <td
                                key={colId}
                                title={tooltip}
                                style={{
                                  padding: '6px',
                                  textAlign: 'center',
                                  fontSize: '12px',
                                  fontWeight: 700,
                                  borderBottom: '1px solid #374151',
                                  borderLeft: '1px solid #374151',
                                  backgroundColor: style.bg,
                                  color: style.text,
                                  minWidth: '48px',
                                }}
                              >
                                {net > 0 ? `+${net}` : net}
                              </td>
                            )
                          })}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )
          })()}
        </div>
      )}

      {/* Post-combine pairwise section - Full Rankings & Matrix */}
      {post_combine_pairwise && post_combine_pairwise.rankings && post_combine_pairwise.rankings.length > 0 && (
        <div style={{ marginTop: '24px', paddingTop: '16px', borderTop: '3px solid #059669' }}>
          <h4
            style={{
              color: '#10b981',
              fontSize: '16px',
              fontWeight: 600,
              marginBottom: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <GitMerge size={18} />
            Post-Combine Pairwise: Combined Document vs Original Winner
          </h4>
          
          {/* Info Banner */}
          <div
            style={{
              padding: '12px 16px',
              backgroundColor: '#064e3b',
              borderRadius: '8px',
              marginBottom: '16px',
              fontSize: '13px',
              color: '#a7f3d0',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              flexWrap: 'wrap',
              border: '1px solid #059669',
            }}
          >
            <span>
              <strong>Combined Document Comparison:</strong> After combining the best documents, this pairwise comparison
              determines if the combined document is better than the original winner.
            </span>
            {post_combine_pairwise.winner_doc_id && (
              <span
                style={{
                  marginLeft: 'auto',
                  padding: '4px 12px',
                  borderRadius: '16px',
                  backgroundColor: '#059669',
                  color: 'white',
                  fontSize: '12px',
                  fontWeight: 500,
                }}
              >
                <Trophy size={12} style={{ display: 'inline', marginRight: '4px', verticalAlign: 'middle' }} />
                Final Winner: {post_combine_pairwise.winner_doc_id.includes('combined') ? 'Combined Document' : 'Original Winner'}
              </span>
            )}
          </div>

          {/* Rankings Table */}
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', padding: '12px', backgroundColor: '#059669', color: 'white', fontSize: '13px' }}>
                    Rank
                  </th>
                  <th style={{ textAlign: 'left', padding: '12px', backgroundColor: '#059669', color: 'white', fontSize: '13px' }}>
                    Document
                  </th>
                  <th style={{ textAlign: 'center', padding: '12px', backgroundColor: '#059669', color: 'white', fontSize: '13px' }}>
                    Wins
                  </th>
                  <th style={{ textAlign: 'center', padding: '12px', backgroundColor: '#059669', color: 'white', fontSize: '13px' }}>
                    Losses
                  </th>
                  <th style={{ textAlign: 'center', padding: '12px', backgroundColor: '#059669', color: 'white', fontSize: '13px' }}>
                    Win Rate
                  </th>
                  <th style={{ textAlign: 'center', padding: '12px', backgroundColor: '#059669', color: 'white', fontSize: '13px' }}>
                    ELO
                  </th>
                </tr>
              </thead>
              <tbody>
                {post_combine_pairwise.rankings
                  .sort((a: PairwiseRanking, b: PairwiseRanking) => b.elo - a.elo)
                  .map((ranking: PairwiseRanking, idx: number) => {
                    const total = ranking.wins + ranking.losses
                    const winRate = total > 0 ? (ranking.wins / total) * 100 : 0
                    const isWinner = ranking.doc_id === post_combine_pairwise.winner_doc_id
                    const isCombined = ranking.doc_id.includes('combined')

                    return (
                      <tr
                        key={ranking.doc_id}
                        style={{
                          borderBottom: '1px solid #374151',
                          backgroundColor: isWinner 
                            ? 'rgba(16, 185, 129, 0.2)' 
                            : idx % 2 === 0 ? '#111827' : '#1f2937',
                        }}
                      >
                        <td style={{ padding: '12px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            {idx === 0 && <span style={{ fontSize: '20px' }}>🏆</span>}
                            {idx > 0 && <span style={{ color: '#6b7280', fontSize: '14px' }}>#{idx + 1}</span>}
                          </div>
                        </td>
                        <td style={{ padding: '12px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            {isCombined ? <GitMerge size={14} style={{ color: '#10b981' }} /> : <FileText size={14} style={{ color: '#6b7280' }} />}
                            <button
                              onClick={() => openDocViewer(ranking.doc_id, isCombined ? '📦 Combined' : getDocDisplayName(ranking.doc_id))}
                              style={{
                                fontFamily: 'monospace',
                                fontSize: '12px',
                                color: '#60a5fa',
                                background: 'none',
                                border: 'none',
                                padding: 0,
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                              }}
                              title={`View ${ranking.doc_id}`}
                            >
                              {isCombined ? '📦 Combined' : getDocDisplayName(ranking.doc_id)}
                              <ExternalLink size={12} />
                            </button>
                            {isWinner && (
                              <span
                                style={{
                                  fontSize: '10px',
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                  backgroundColor: '#059669',
                                  color: 'white',
                                }}
                              >
                                WINNER
                              </span>
                            )}
                            {isCombined && (
                              <span
                                style={{
                                  fontSize: '10px',
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                  backgroundColor: '#0891b2',
                                  color: 'white',
                                }}
                              >
                                MERGED
                              </span>
                            )}
                          </div>
                        </td>
                        <td style={{ padding: '12px', textAlign: 'center', color: '#86efac', fontWeight: 500 }}>
                          {ranking.wins}
                        </td>
                        <td style={{ padding: '12px', textAlign: 'center', color: '#fca5a5', fontWeight: 500 }}>
                          {ranking.losses}
                        </td>
                        <td style={{ padding: '12px', textAlign: 'center' }}>
                          <div
                            style={{
                              display: 'inline-block',
                              padding: '4px 10px',
                              borderRadius: '12px',
                              backgroundColor: winRate >= 60 ? 'rgba(16, 185, 129, 0.2)' : winRate >= 40 ? 'rgba(251, 191, 36, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                              color: winRate >= 60 ? '#86efac' : winRate >= 40 ? '#fbbf24' : '#fca5a5',
                              fontSize: '12px',
                              fontWeight: 500,
                            }}
                          >
                            {winRate.toFixed(1)}%
                          </div>
                        </td>
                        <td style={{ padding: '12px', textAlign: 'center' }}>
                          <span style={{ fontWeight: 'bold', fontSize: '14px', color: '#fbbf24' }}>{ranking.elo.toFixed(0)}</span>
                        </td>
                      </tr>
                    )
                  })}
              </tbody>
            </table>
          </div>

          {/* Post-Combine Head-to-Head Matrix */}
          {post_combine_pairwise.comparisons && post_combine_pairwise.comparisons.length > 0 && (
            <div style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid #059669' }}>
              <h5
                style={{
                  color: '#10b981',
                  fontSize: '14px',
                  fontWeight: 600,
                  marginBottom: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <GitMerge size={16} />
                Head-to-Head Comparison Matrix
              </h5>

              {(() => {
                // Build matrix data from post-combine comparisons
                const docIds = Array.from(new Set([
                  ...post_combine_pairwise.comparisons.map((c: { doc_id_a: string }) => c.doc_id_a),
                  ...post_combine_pairwise.comparisons.map((c: { doc_id_b: string }) => c.doc_id_b)
                ]))

                const pairResults: Record<string, Record<string, { rowWins: number; colWins: number }>> = {}
                for (const docId of docIds) {
                  pairResults[docId] = {}
                  for (const otherId of docIds) {
                    pairResults[docId][otherId] = { rowWins: 0, colWins: 0 }
                  }
                }

                for (const comp of post_combine_pairwise.comparisons) {
                  if (comp.winner === comp.doc_id_a) {
                    pairResults[comp.doc_id_a][comp.doc_id_b].rowWins++
                    pairResults[comp.doc_id_b][comp.doc_id_a].colWins++
                  } else if (comp.winner === comp.doc_id_b) {
                    pairResults[comp.doc_id_a][comp.doc_id_b].colWins++
                    pairResults[comp.doc_id_b][comp.doc_id_a].rowWins++
                  }
                }

                const getPostCombineShortDocId = (docId: string) => {
                  if (docId.includes('combined')) {
                    const parts = docId.split('.')
                    if (parts.length >= 5) {
                      const modelPart = parts.slice(4).join('.')
                      const formatted = modelPart.replace('_', ':')
                      return `📦 ${formatted}`
                    }
                    return '📦 Combined'
                  }
                  const parts = docId.split('.')
                  if (parts.length >= 5) {
                    const modelPart = parts.slice(4).join('.')
                    return modelPart.replace('_', ':')
                  }
                  return docId
                }

                const getPostCombineElo = (docId: string) => {
                  const rec = post_combine_pairwise.rankings?.find((r: PairwiseRanking) => r.doc_id === docId)
                  return rec?.elo
                }

                const winnerDocId = post_combine_pairwise.winner_doc_id

                const getPostCombineNetCellStyle = (netScore: number): { bg: string; text: string } => {
                  if (netScore > 0) {
                    if (netScore >= 3) return { bg: '#16a34a', text: 'white' }
                    if (netScore >= 2) return { bg: '#4ade80', text: '#064e3b' }
                    return { bg: 'rgba(134, 239, 172, 0.25)', text: '#86efac' }
                  } else if (netScore < 0) {
                    if (netScore <= -3) return { bg: '#dc2626', text: 'white' }
                    if (netScore <= -2) return { bg: '#f87171', text: '#7f1d1d' }
                    return { bg: 'rgba(252, 165, 165, 0.20)', text: '#fca5a5' }
                  }
                  return { bg: '#111827', text: '#9ca3af' }
                }

                return (
                  <div style={{ overflowX: 'auto' }}>
                    <table
                      style={{
                        borderCollapse: 'collapse',
                        backgroundColor: '#0b1220',
                        border: '1px solid #374151',
                      }}
                    >
                      <thead>
                        <tr>
                          <th
                            style={{
                              padding: '8px 10px',
                              textAlign: 'left',
                              fontSize: '12px',
                              color: '#10b981',
                              borderBottom: '2px solid #16a34a',
                              minWidth: '140px',
                              backgroundColor: '#111827',
                            }}
                          >
                            Row vs Column →
                          </th>
                          {docIds.map(colId => {
                            const label = getPostCombineShortDocId(colId)
                            const elo = getPostCombineElo(colId)
                            const isWinner = winnerDocId && colId === winnerDocId
                            return (
                              <th
                                key={colId}
                                title={colId}
                                style={{
                                  padding: '6px 4px',
                                  textAlign: 'center',
                                  fontSize: '11px',
                                  color: '#fca5a5',
                                  borderBottom: '2px solid #dc2626',
                                  borderLeft: '1px solid #374151',
                                  writingMode: 'vertical-rl',
                                  transform: 'rotate(180deg)',
                                  height: '120px',
                                  whiteSpace: 'nowrap',
                                  backgroundColor: '#111827',
                                }}
                              >
                                {isWinner ? '🏆 ' : ''}{label}
                                {elo ? `\nELO: ${elo.toFixed(0)}` : ''}
                              </th>
                            )
                          })}
                        </tr>
                      </thead>
                      <tbody>
                        {docIds.map(rowId => {
                          const rowElo = getPostCombineElo(rowId)
                          const isRowWinner = winnerDocId && rowId === winnerDocId
                          return (
                            <tr key={rowId}>
                              <td
                                title={rowId}
                                style={{
                                  padding: '8px 10px',
                                  fontSize: '12px',
                                  color: '#d1d5db',
                                  borderRight: '2px solid #16a34a',
                                  borderBottom: '1px solid #374151',
                                  backgroundColor: '#111827',
                                  whiteSpace: 'nowrap',
                                }}
                              >
                                {isRowWinner ? '🏆 ' : ''}{getPostCombineShortDocId(rowId)}
                                <span style={{ color: '#9ca3af' }}>{rowElo ? ` (ELO: ${rowElo.toFixed(0)})` : ''}</span>
                              </td>
                              {docIds.map(colId => {
                                if (rowId === colId) {
                                  return (
                                    <td
                                      key={colId}
                                      style={{
                                        padding: '8px',
                                        textAlign: 'center',
                                        fontSize: '12px',
                                        color: '#6b7280',
                                        borderBottom: '1px solid #374151',
                                        borderLeft: '1px solid #374151',
                                        backgroundColor: '#0b1220',
                                      }}
                                    >
                                      —
                                    </td>
                                  )
                                }
                                const pair = pairResults[rowId][colId]
                                const netScore = pair.rowWins - pair.colWins
                                const { bg, text } = getPostCombineNetCellStyle(netScore)
                                const displayVal = netScore > 0 ? `+${netScore}` : netScore.toString()
                                const tooltip = `Row wins: ${pair.rowWins}\nColumn wins: ${pair.colWins}`
                                return (
                                  <td
                                    key={colId}
                                    title={tooltip}
                                    style={{
                                      padding: '6px',
                                      textAlign: 'center',
                                      fontSize: '12px',
                                      fontWeight: 700,
                                      borderBottom: '1px solid #374151',
                                      borderLeft: '1px solid #374151',
                                      backgroundColor: bg,
                                      color: text,
                                      minWidth: '48px',
                                    }}
                                  >
                                    {displayVal}
                                  </td>
                                )
                              })}
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                    <div style={{ marginTop: '8px', fontSize: '11px', color: '#6b7280' }}>
                      Green = row won more, Red = column won more. Number shows net win margin.
                    </div>
                  </div>
                )
              })()}
            </div>
          )}

          {/* Summary */}
          <div
            style={{
              marginTop: '16px',
              padding: '12px 16px',
              backgroundColor: '#064e3b',
              borderRadius: '8px',
              border: '1px solid #059669',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '13px' }}>
              <span style={{ color: '#a7f3d0' }}>
                <strong>Total Comparisons:</strong> {post_combine_pairwise.total_comparisons || 0}
              </span>
              <span style={{ color: '#a7f3d0' }}>
                <strong>Result:</strong> {post_combine_pairwise.winner_doc_id?.includes('combined') 
                  ? '✓ Combined document is the final winner!' 
                  : 'Original winner document remains the best'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Document Viewer Modal */}
      {docViewer.isOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '20px',
          }}
          onClick={closeDocViewer}
        >
          <div
            style={{
              backgroundColor: '#1f2937',
              borderRadius: '12px',
              width: '100%',
              maxWidth: '900px',
              maxHeight: '80vh',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              border: '1px solid #374151',
            }}
            onClick={e => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '16px 20px',
                borderBottom: '1px solid #374151',
                backgroundColor: '#111827',
              }}
            >
              <div>
                <h3 style={{ margin: 0, color: 'white', fontSize: '16px', fontWeight: 600 }}>
                  {docViewer.model}
                </h3>
                <p style={{ margin: '4px 0 0', color: '#9ca3af', fontSize: '12px', fontFamily: 'monospace' }}>
                  {docViewer.docId}
                </p>
              </div>
              <button
                onClick={closeDocViewer}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#9ca3af',
                  cursor: 'pointer',
                  padding: '8px',
                  borderRadius: '8px',
                }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Modal Content */}
            <div
              style={{
                flex: 1,
                overflow: 'auto',
                padding: '20px',
              }}
            >
              {docViewer.loading && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px' }}>
                  <Loader2 size={32} className="animate-spin" style={{ color: '#60a5fa' }} />
                </div>
              )}
              {docViewer.error && (
                <div style={{ textAlign: 'center', padding: '40px', color: '#f87171' }}>
                  <p>Error: {docViewer.error}</p>
                </div>
              )}
              {docViewer.content && (
                <div
                  style={{
                    color: '#d1d5db',
                    fontSize: '14px',
                    lineHeight: 1.7,
                    whiteSpace: 'pre-wrap',
                    fontFamily: 'system-ui, -apple-system, sans-serif',
                  }}
                >
                  {docViewer.content}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
