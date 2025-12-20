import { FileText, GitMerge, Trophy } from 'lucide-react'
import type { Run } from '../../api'

interface PairwiseTabProps {
  currentRun: Run | null
}

export default function PairwiseTab({ currentRun }: PairwiseTabProps) {
  const pairwiseResults = currentRun?.pairwise_results
  const postCombinePairwise = currentRun?.post_combine_pairwise
  const rankings = pairwiseResults?.rankings || []
  
  if (rankings.length === 0 && !postCombinePairwise) {
    return (
      <div className="p-5" style={{ color: '#0f172a' }}>
        <div className="text-center text-gray-500 py-8">
          <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>No pairwise comparison data available yet.</p>
          <p className="text-sm mt-2">Pairwise comparisons require at least 2 generated documents.</p>
        </div>
      </div>
    )
  }
  
  return (
    <div className="p-5" style={{ color: '#0f172a' }}>
      <div 
        className="mb-4 p-4 rounded-lg text-sm"
        style={{ backgroundColor: '#f1f5f9', color: '#0f172a', border: '1px solid #cbd5e1' }}
      >
        <strong>Pairwise Comparison Rankings:</strong> Documents ranked by ELO score from head-to-head comparisons.
        {pairwiseResults?.winner_doc_id && (
          <span className="ml-4 px-3 py-1 rounded" style={{ backgroundColor: '#28a745', color: 'white' }}>
            Winner: {pairwiseResults.winner_doc_id.length > 30 ? pairwiseResults.winner_doc_id.substring(0, 30) + '...' : pairwiseResults.winner_doc_id}
          </span>
        )}
      </div>
      
      {/* Rankings Table */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse" style={{ color: '#0f172a' }}>
          <thead>
            <tr>
              <th className="text-left p-3 font-semibold" style={{ backgroundColor: '#1f2937', color: 'white', borderBottom: '2px solid #0f172a' }}>
                Rank
              </th>
              <th className="text-left p-3 font-semibold" style={{ backgroundColor: '#1f2937', color: 'white', borderBottom: '2px solid #0f172a' }}>
                Document
              </th>
              <th className="text-center p-3 font-semibold" style={{ backgroundColor: '#1f2937', color: 'white', borderBottom: '2px solid #0f172a' }}>
                Wins
              </th>
              <th className="text-center p-3 font-semibold" style={{ backgroundColor: '#1f2937', color: 'white', borderBottom: '2px solid #0f172a' }}>
                Losses
              </th>
              <th className="text-center p-3 font-semibold" style={{ backgroundColor: '#1f2937', color: 'white', borderBottom: '2px solid #0f172a' }}>
                Win Rate
              </th>
              <th className="text-center p-3 font-semibold" style={{ backgroundColor: '#1f2937', color: 'white', borderBottom: '2px solid #0f172a' }}>
                ELO
              </th>
            </tr>
          </thead>
          <tbody>
            {rankings
              .sort((a, b) => b.elo - a.elo)
              .map((ranking, idx) => {
                const total = ranking.wins + ranking.losses
                const winRate = total > 0 ? (ranking.wins / total) * 100 : 0
                const isWinner = ranking.doc_id === pairwiseResults?.winner_doc_id
                
                return (
                  <tr 
                    key={ranking.doc_id} 
                    style={{ 
                      borderTop: '1px solid #e5e7eb',
                      backgroundColor: isWinner ? '#c8e6c9' : idx % 2 === 0 ? '#ffffff' : '#f5f7fb',
                      color: '#0f172a'
                    }}
                  >
                    <td className="p-3" style={{ color: '#0f172a' }}>
                      <div className="flex items-center gap-2">
                        {idx === 0 && <span className="text-2xl">🥇</span>}
                        {idx === 1 && <span className="text-2xl">🥈</span>}
                        {idx === 2 && <span className="text-2xl">🥉</span>}
                        {idx > 2 && <span className="text-lg text-gray-500">#{idx + 1}</span>}
                      </div>
                    </td>
                    <td className="p-3" style={{ color: '#0f172a' }}>
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-gray-400" />
                        <span className="font-mono text-sm truncate max-w-[300px]" title={ranking.doc_id}>
                          {ranking.doc_id.length > 40 ? ranking.doc_id.substring(0, 40) + '...' : ranking.doc_id}
                        </span>
                        {isWinner && (
                          <span className="ml-2 px-2 py-0.5 text-xs rounded" style={{ backgroundColor: '#28a745', color: 'white' }}>
                            WINNER
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="p-3 text-center">
                      <span className="font-semibold px-2 py-1 rounded" style={{ backgroundColor: '#e6f4ea', color: '#0b3d2e' }}>
                        {ranking.wins}
                      </span>
                    </td>
                    <td className="p-3 text-center">
                      <span className="font-semibold px-2 py-1 rounded" style={{ backgroundColor: '#fde8e8', color: '#7f1d1d' }}>
                        {ranking.losses}
                      </span>
                    </td>
                    <td className="p-3 text-center">
                      <div 
                        className="inline-block px-3 py-1 rounded"
                        style={{ 
                          backgroundColor: winRate >= 60 ? '#d4edda' : winRate >= 40 ? '#fff3cd' : '#f8d7da',
                          color: winRate >= 60 ? '#155724' : winRate >= 40 ? '#856404' : '#721c24'
                        }}
                      >
                        {winRate.toFixed(1)}%
                      </div>
                    </td>
                    <td className="p-3 text-center">
                      <span className="font-bold text-lg" style={{ color: '#0f172a' }}>{ranking.elo.toFixed(0)}</span>
                    </td>
                  </tr>
                )
              })}
          </tbody>
        </table>
      </div>
      
      {/* Summary */}
      <div className="mt-4 p-4 rounded-lg" style={{ backgroundColor: '#e3f2fd' }}>
        <div className="flex items-center justify-between text-sm">
          <span>
            <strong>Total Comparisons:</strong> {pairwiseResults?.total_comparisons || 0}
          </span>
          <span>
            <strong>Documents Compared:</strong> {rankings.length}
          </span>
        </div>
      </div>
      
      {/* Head-to-Head Comparison Matrix */}
      {pairwiseResults?.comparisons && pairwiseResults.comparisons.length > 0 && (
        <div className="mt-8 pt-6" style={{ borderTop: '2px solid #e9ecef' }}>
          <h4 className="text-lg font-semibold mb-4 flex items-center gap-2" style={{ color: '#4b5563' }}>
            <FileText className="w-5 h-5" />
            Head-to-Head Comparison Matrix
          </h4>
          
          {(() => {
            // Build matrix data from comparisons (net win delta per ACM1)
            const docIds = Array.from(new Set([
              ...pairwiseResults.comparisons.map(c => c.doc_id_a),
              ...pairwiseResults.comparisons.map(c => c.doc_id_b)
            ]))

            // For each pair, track: who won how many times (mirrored for both cells)
            const pairResults: Record<string, Record<string, { rowWins: number; colWins: number }>> = {}
            for (const docId of docIds) {
              pairResults[docId] = {}
              for (const otherId of docIds) {
                pairResults[docId][otherId] = { rowWins: 0, colWins: 0 }
              }
            }

            for (const comp of pairwiseResults.comparisons) {
              // For each comparison, update both cells symmetrically
              if (comp.winner === comp.doc_id_a) {
                pairResults[comp.doc_id_a][comp.doc_id_b].rowWins++
                pairResults[comp.doc_id_b][comp.doc_id_a].colWins++
              } else if (comp.winner === comp.doc_id_b) {
                pairResults[comp.doc_id_a][comp.doc_id_b].colWins++
                pairResults[comp.doc_id_b][comp.doc_id_a].rowWins++
              }
            }

            const getShortDocId = (docId: string) => {
              if (docId.length > 20) return docId.substring(0, 17) + '...'
              return docId
            }

            const getEloForDoc = (docId: string) => {
              const rec = pairwiseResults.rankings?.find(r => r.doc_id === docId)
              return rec?.elo ?? undefined
            }

            const winnerDocId = pairwiseResults.winner_doc_id

            const getNetCellStyle = (netScore: number): { bg: string; text: string } => {
              if (netScore > 0) {
                if (netScore >= 3) return { bg: '#28a745', text: 'white' }
                if (netScore >= 2) return { bg: '#5cb85c', text: 'white' }
                return { bg: '#dff0d8', text: '#3c763d' }
              } else if (netScore < 0) {
                if (netScore <= -3) return { bg: '#dc3545', text: 'white' }
                if (netScore <= -2) return { bg: '#d9534f', text: 'white' }
                return { bg: '#f2dede', text: '#a94442' }
              }
              return { bg: '#f9f9f9', text: '#999' }
            }

            return (
              <div className="overflow-x-auto">
                <table 
                  className="border-collapse"
                  style={{ backgroundColor: 'white', border: '1px solid #dee2e6' }}
                >
                  <thead>
                    <tr>
                      <th 
                        className="p-2 text-left font-semibold text-sm"
                        style={{ color: '#28a745', borderBottom: '2px solid #28a745', minWidth: '140px' }}
                      >
                        Row vs Column →
                      </th>
                      {docIds.map(colId => {
                        const label = getShortDocId(colId)
                        const elo = getEloForDoc(colId)
                        const isWinner = winnerDocId && colId === winnerDocId
                        const header = `${label}${elo ? `\nELO: ${elo.toFixed(0)}` : ''}`
                        return (
                          <th 
                            key={colId} 
                            className="text-center font-semibold text-xs"
                            style={{ color: '#dc3545', borderBottom: '2px solid #dc3545', borderLeft: '1px solid #eee', writingMode: 'vertical-rl', transform: 'rotate(180deg)', padding: '6px 4px', height: '150px', whiteSpace: 'nowrap' }}
                            title={colId}
                          >
                            {isWinner ? '🏆 ' : ''}{header}
                          </th>
                        )
                      })}
                    </tr>
                  </thead>
                  <tbody>
                    {docIds.map(rowId => {
                      const rowElo = getEloForDoc(rowId)
                      const isRowWinner = winnerDocId && rowId === winnerDocId
                      return (
                        <tr key={rowId}>
                          <th 
                            className="font-semibold text-sm"
                            style={{ color: '#28a745', borderRight: '2px solid #28a745', padding: '8px', whiteSpace: 'nowrap' }}
                            title={rowId}
                          >
                            {isRowWinner ? '🏆 ' : ''}{getShortDocId(rowId)}{rowElo ? `\nELO: ${rowElo.toFixed(0)}` : ''}
                          </th>
                          {docIds.map(colId => {
                            if (rowId === colId) {
                              return (
                                <td 
                                  key={colId} 
                                  className="text-center font-semibold"
                                  style={{ backgroundColor: '#f9f9f9', color: '#999', border: '1px solid #eee', width: '50px', height: '50px', minWidth: '50px', maxWidth: '50px' }}
                                >
                                  -
                                </td>
                              )
                            }
                            const pair = pairResults[rowId][colId]
                            // Net score: positive = row won more, negative = column won more
                            const netScore = pair.rowWins - pair.colWins
                            const { bg, text } = getNetCellStyle(netScore)
                            // Display signed value: +2 or -2
                            const displayVal = netScore > 0 ? `+${netScore}` : netScore.toString()
                            const tooltip = `${rowId} vs ${colId}: ${pair.rowWins} wins - ${pair.colWins} losses`
                            return (
                              <td 
                                key={colId} 
                                className="text-center text-sm font-semibold"
                                style={{ backgroundColor: bg, color: text, border: '1px solid #eee', width: '50px', height: '50px', minWidth: '50px', maxWidth: '50px', padding: 0, verticalAlign: 'middle' }}
                                title={tooltip}
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
                <div className="mt-2 text-xs" style={{ color: '#374151' }}>
                  Green = row won more, Red = column won more. Number shows net win margin.
                </div>
              </div>
            )
          })()}
        </div>
      )}
      
      {/* Post-Combine Pairwise: Combined Doc vs Winner */}
      {postCombinePairwise && postCombinePairwise.rankings.length > 0 && (
        <div className="mt-8 pt-6" style={{ borderTop: '3px solid #059669' }}>
          <h4 className="text-lg font-semibold mb-4 flex items-center gap-2" style={{ color: '#059669' }}>
            <GitMerge className="w-5 h-5" />
            Post-Combine Pairwise: Combined Document vs Original Winner
          </h4>
          
          <div 
            className="mb-4 p-4 rounded-lg text-sm"
            style={{ backgroundColor: '#ecfdf5', color: '#065f46', border: '1px solid #a7f3d0' }}
          >
            <strong>Combined Document Comparison:</strong> After combining the best documents, this pairwise comparison
            determines if the combined document is better than the original winner.
            {postCombinePairwise.winner_doc_id && (
              <span className="ml-4 px-3 py-1 rounded" style={{ backgroundColor: '#059669', color: 'white' }}>
                <Trophy className="w-4 h-4 inline mr-1" />
                Final Winner: {postCombinePairwise.winner_doc_id.includes('combined') ? 'Combined Document' : 'Original Winner'}
              </span>
            )}
          </div>
          
          {/* Rankings Table */}
          <div className="overflow-x-auto">
            <table className="w-full border-collapse" style={{ color: '#0f172a' }}>
              <thead>
                <tr>
                  <th className="text-left p-3 font-semibold" style={{ backgroundColor: '#059669', color: 'white' }}>
                    Rank
                  </th>
                  <th className="text-left p-3 font-semibold" style={{ backgroundColor: '#059669', color: 'white' }}>
                    Document
                  </th>
                  <th className="text-center p-3 font-semibold" style={{ backgroundColor: '#059669', color: 'white' }}>
                    Wins
                  </th>
                  <th className="text-center p-3 font-semibold" style={{ backgroundColor: '#059669', color: 'white' }}>
                    Losses
                  </th>
                  <th className="text-center p-3 font-semibold" style={{ backgroundColor: '#059669', color: 'white' }}>
                    Win Rate
                  </th>
                  <th className="text-center p-3 font-semibold" style={{ backgroundColor: '#059669', color: 'white' }}>
                    ELO
                  </th>
                </tr>
              </thead>
              <tbody>
                {postCombinePairwise.rankings
                  .sort((a, b) => b.elo - a.elo)
                  .map((ranking, idx) => {
                    const total = ranking.wins + ranking.losses
                    const winRate = total > 0 ? (ranking.wins / total) * 100 : 0
                    const isWinner = ranking.doc_id === postCombinePairwise.winner_doc_id
                    const isCombined = ranking.doc_id.includes('combined')
                    
                    return (
                      <tr 
                        key={ranking.doc_id} 
                        style={{ 
                          borderTop: '1px solid #e5e7eb',
                          backgroundColor: isWinner ? '#d1fae5' : idx % 2 === 0 ? '#ffffff' : '#f0fdf4',
                          color: '#0f172a'
                        }}
                      >
                        <td className="p-3" style={{ color: '#0f172a' }}>
                          <div className="flex items-center gap-2">
                            {idx === 0 && <span className="text-2xl">🏆</span>}
                            {idx > 0 && <span className="text-lg text-gray-500">#{idx + 1}</span>}
                          </div>
                        </td>
                        <td className="p-3" style={{ color: '#0f172a' }}>
                          <div className="flex items-center gap-2">
                            {isCombined ? <GitMerge className="w-4 h-4 text-emerald-600" /> : <FileText className="w-4 h-4 text-gray-400" />}
                            <span className="font-mono text-sm truncate max-w-[300px]" title={ranking.doc_id}>
                              {isCombined ? 'Combined Document' : (ranking.doc_id.length > 40 ? ranking.doc_id.substring(0, 40) + '...' : ranking.doc_id)}
                            </span>
                            {isWinner && (
                              <span className="ml-2 px-2 py-0.5 text-xs rounded" style={{ backgroundColor: '#059669', color: 'white' }}>
                                WINNER
                              </span>
                            )}
                            {isCombined && (
                              <span className="ml-2 px-2 py-0.5 text-xs rounded" style={{ backgroundColor: '#0891b2', color: 'white' }}>
                                MERGED
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="p-3 text-center">
                          <span className="font-semibold px-2 py-1 rounded" style={{ backgroundColor: '#d1fae5', color: '#065f46' }}>
                            {ranking.wins}
                          </span>
                        </td>
                        <td className="p-3 text-center">
                          <span className="font-semibold px-2 py-1 rounded" style={{ backgroundColor: '#fee2e2', color: '#991b1b' }}>
                            {ranking.losses}
                          </span>
                        </td>
                        <td className="p-3 text-center">
                          <div 
                            className="inline-block px-3 py-1 rounded"
                            style={{ 
                              backgroundColor: winRate >= 60 ? '#d1fae5' : winRate >= 40 ? '#fef3c7' : '#fee2e2',
                              color: winRate >= 60 ? '#065f46' : winRate >= 40 ? '#92400e' : '#991b1b'
                            }}
                          >
                            {winRate.toFixed(1)}%
                          </div>
                        </td>
                        <td className="p-3 text-center">
                          <span className="font-bold text-lg" style={{ color: '#0f172a' }}>{ranking.elo.toFixed(0)}</span>
                        </td>
                      </tr>
                    )
                  })}
              </tbody>
            </table>
          </div>
          
          {/* Post-Combine Head-to-Head Comparison Matrix */}
          {postCombinePairwise.comparisons && postCombinePairwise.comparisons.length > 0 && (
            <div className="mt-6 pt-4" style={{ borderTop: '1px solid #a7f3d0' }}>
              <h5 className="text-md font-semibold mb-4 flex items-center gap-2" style={{ color: '#047857' }}>
                <GitMerge className="w-4 h-4" />
                Head-to-Head Comparison Matrix
              </h5>
              
              {(() => {
                // Build matrix data from post-combine comparisons
                const docIds = Array.from(new Set([
                  ...postCombinePairwise.comparisons.map(c => c.doc_id_a),
                  ...postCombinePairwise.comparisons.map(c => c.doc_id_b)
                ]))

                // For each pair, track: who won how many times
                // pairResults[docA][docB] = { aWins: number, bWins: number }
                // This is symmetric: pairResults[A][B] and pairResults[B][A] show same matchup
                const pairResults: Record<string, Record<string, { rowWins: number; colWins: number }>> = {}
                for (const docId of docIds) {
                  pairResults[docId] = {}
                  for (const otherId of docIds) {
                    pairResults[docId][otherId] = { rowWins: 0, colWins: 0 }
                  }
                }

                for (const comp of postCombinePairwise.comparisons) {
                  // For each comparison, update both cells symmetrically
                  if (comp.winner === comp.doc_id_a) {
                    // doc_a won this comparison
                    pairResults[comp.doc_id_a][comp.doc_id_b].rowWins++  // A's cell: A won
                    pairResults[comp.doc_id_b][comp.doc_id_a].colWins++  // B's cell: A (the col) won
                  } else if (comp.winner === comp.doc_id_b) {
                    // doc_b won this comparison
                    pairResults[comp.doc_id_a][comp.doc_id_b].colWins++  // A's cell: B (the col) won
                    pairResults[comp.doc_id_b][comp.doc_id_a].rowWins++  // B's cell: B won
                  }
                }

                const getShortDocId = (docId: string) => {
                  // Extract model name from doc ID (e.g., "...openai_gpt-5-mini" or "...google_gemini-2.5-flash")
                  // Match provider_model pattern at the end, allowing dots in model names
                  const modelMatch = docId.match(/\.(openai_[\w.-]+|google_[\w.-]+|anthropic_[\w.-]+)$/)
                  const modelName = modelMatch ? modelMatch[1].replace('_', ':') : null
                  
                  if (docId.includes('combined')) {
                    return modelName ? `📦 ${modelName}` : '📦 Combined'
                  }
                  if (modelName) {
                    return modelName
                  }
                  if (docId.length > 20) return docId.substring(0, 17) + '...'
                  return docId
                }

                const getEloForDoc = (docId: string) => {
                  const rec = postCombinePairwise.rankings?.find(r => r.doc_id === docId)
                  return rec?.elo ?? undefined
                }

                const winnerDocId = postCombinePairwise.winner_doc_id

                const getNetCellStyle = (netScore: number): { bg: string; text: string } => {
                  if (netScore > 0) {
                    if (netScore >= 3) return { bg: '#059669', text: 'white' }
                    if (netScore >= 2) return { bg: '#10b981', text: 'white' }
                    return { bg: '#d1fae5', text: '#065f46' }
                  } else if (netScore < 0) {
                    if (netScore <= -3) return { bg: '#dc2626', text: 'white' }
                    if (netScore <= -2) return { bg: '#ef4444', text: 'white' }
                    return { bg: '#fee2e2', text: '#991b1b' }
                  }
                  return { bg: '#f9f9f9', text: '#999' }
                }

                return (
                  <div className="overflow-x-auto">
                    <table 
                      className="border-collapse"
                      style={{ backgroundColor: 'white', border: '1px solid #a7f3d0' }}
                    >
                      <thead>
                        <tr>
                          <th 
                            className="p-2 text-left font-semibold text-sm"
                            style={{ color: '#059669', borderBottom: '2px solid #059669', minWidth: '140px' }}
                          >
                            Row vs Column →
                          </th>
                          {docIds.map(colId => {
                            const label = getShortDocId(colId)
                            const elo = getEloForDoc(colId)
                            const isWinner = winnerDocId && colId === winnerDocId
                            const header = `${label}${elo ? `\nELO: ${elo.toFixed(0)}` : ''}`
                            return (
                              <th 
                                key={colId} 
                                className="text-center font-semibold text-xs"
                                style={{ color: '#dc2626', borderBottom: '2px solid #dc2626', borderLeft: '1px solid #eee', writingMode: 'vertical-rl', transform: 'rotate(180deg)', padding: '6px 4px', height: '120px', whiteSpace: 'nowrap' }}
                                title={colId}
                              >
                                {isWinner ? '🏆 ' : ''}{header}
                              </th>
                            )
                          })}
                        </tr>
                      </thead>
                      <tbody>
                        {docIds.map(rowId => {
                          const rowElo = getEloForDoc(rowId)
                          const isRowWinner = winnerDocId && rowId === winnerDocId
                          return (
                            <tr key={rowId}>
                              <th 
                                className="font-semibold text-sm"
                                style={{ color: '#059669', borderRight: '2px solid #059669', padding: '8px', whiteSpace: 'nowrap' }}
                                title={rowId}
                              >
                                {isRowWinner ? '🏆 ' : ''}{getShortDocId(rowId)}{rowElo ? ` (${rowElo.toFixed(0)})` : ''}
                              </th>
                              {docIds.map(colId => {
                                if (rowId === colId) {
                                  return (
                                    <td 
                                      key={colId} 
                                      className="text-center font-semibold"
                                      style={{ backgroundColor: '#f0fdf4', color: '#999', border: '1px solid #d1fae5', width: '60px', height: '60px', minWidth: '60px', maxWidth: '60px' }}
                                    >
                                      -
                                    </td>
                                  )
                                }
                                const pair = pairResults[rowId][colId]
                                // Net score: positive = row won more, negative = column won more
                                const netScore = pair.rowWins - pair.colWins
                                const { bg, text } = getNetCellStyle(netScore)
                                // Display signed value: +2 or -2
                                const displayVal = netScore > 0 ? `+${netScore}` : netScore.toString()
                                const tooltip = `${getShortDocId(rowId)} vs ${getShortDocId(colId)}: ${pair.rowWins} wins - ${pair.colWins} losses`
                                return (
                                  <td 
                                    key={colId} 
                                    className="text-center text-sm font-semibold"
                                    style={{ backgroundColor: bg, color: text, border: '1px solid #d1fae5', width: '60px', height: '60px', minWidth: '60px', maxWidth: '60px', padding: 0, verticalAlign: 'middle' }}
                                    title={tooltip}
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
                    <div className="mt-2 text-xs" style={{ color: '#065f46' }}>
                      Green = row won more, Red = column won more. Number shows net win margin.
                    </div>
                  </div>
                )
              })()}
            </div>
          )}
          
          {/* Post-combine comparison details */}
          {postCombinePairwise.comparisons && postCombinePairwise.comparisons.length > 0 && (
            <div className="mt-6">
              <h5 className="text-md font-semibold mb-3 flex items-center gap-2" style={{ color: '#047857' }}>
                <FileText className="w-4 h-4" />
                Comparison Details
              </h5>
              <div className="space-y-3">
                {postCombinePairwise.comparisons.map((comp, idx) => {
                  const isCombinedWinner = comp.winner.includes('combined')
                  return (
                    <div 
                      key={idx} 
                      className="p-4 rounded-lg"
                      style={{ 
                        backgroundColor: isCombinedWinner ? '#ecfdf5' : '#fef3c7', 
                        border: `1px solid ${isCombinedWinner ? '#a7f3d0' : '#fde68a'}` 
                      }}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium" style={{ color: '#4b5563' }}>
                          Judge: <span className="font-mono">{comp.judge_model}</span>
                        </span>
                        <span 
                          className="px-2 py-1 text-xs rounded font-semibold"
                          style={{ 
                            backgroundColor: isCombinedWinner ? '#059669' : '#f59e0b', 
                            color: 'white' 
                          }}
                        >
                          {isCombinedWinner ? '✓ Combined Wins' : '← Original Wins'}
                        </span>
                      </div>
                      <p className="text-sm" style={{ color: '#374151' }}>
                        {comp.reason}
                      </p>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
          
          {/* Summary */}
          <div className="mt-4 p-4 rounded-lg" style={{ backgroundColor: '#ecfdf5', border: '1px solid #a7f3d0' }}>
            <div className="flex items-center justify-between text-sm">
              <span style={{ color: '#065f46' }}>
                <strong>Total Comparisons:</strong> {postCombinePairwise.total_comparisons || 0}
              </span>
              <span style={{ color: '#065f46' }}>
                <strong>Result:</strong> {postCombinePairwise.winner_doc_id?.includes('combined') 
                  ? '✓ Combined document is the final winner!' 
                  : 'Original winner document remains the best'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
