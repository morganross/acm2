import { FileText, Loader2, X, ExternalLink, Github } from 'lucide-react'
import { useState } from 'react'
import type { Run } from '../../api'
import type { ExecutionStatus } from './types'
import { getScoreBadgeStyle } from './utils'
import { GitHubFileBrowser } from '@/components/github'
import { githubApi } from '@/api/github'
import { notify } from '@/stores/notifications'

interface EvaluationTabProps {
  currentRun: Run | null
  execStatus: ExecutionStatus
}

interface DocViewerState {
  isOpen: boolean
  docId: string
  model: string
  content: string | null
  loading: boolean
  error: string | null
}

export default function EvaluationTab({ currentRun, execStatus }: EvaluationTabProps) {
  // Document viewer modal state
  const [docViewer, setDocViewer] = useState<DocViewerState>({
    isOpen: false,
    docId: '',
    model: '',
    content: null,
    loading: false,
    error: null,
  })
  
  // GitHub export state
  const [showGithubExport, setShowGithubExport] = useState(false)
  const [exporting, setExporting] = useState(false)

  const openDocViewer = async (docId: string, model: string) => {
    if (!currentRun?.id) return
    
    setDocViewer({
      isOpen: true,
      docId,
      model,
      content: null,
      loading: true,
      error: null,
    })
    
    try {
      const response = await fetch(`/api/v1/runs/${currentRun.id}/generated/${encodeURIComponent(docId)}`)
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

  // Handle export to GitHub
  const handleGithubExport = async (connectionId: string, path: string) => {
    if (!docViewer.content) {
      notify.error('No content to export')
      return
    }
    
    setExporting(true)
    try {
      const result = await githubApi.exportFile(connectionId, {
        path,
        content: docViewer.content,
        commit_message: `Export generated document: ${docViewer.model}`,
      })
      
      notify.success(`Exported to GitHub: ${result.path}`)
      setShowGithubExport(false)
      
      // Optionally open the file in GitHub
      window.open(result.file_url, '_blank')
    } catch (err) {
      notify.error(err instanceof Error ? err.message : 'Failed to export to GitHub')
    } finally {
      setExporting(false)
    }
  }

  // Get new format data
  const preCombineEvals = currentRun?.pre_combine_evals || {}
  const postCombineEvals = currentRun?.post_combine_evals || {}
  const generatedDocs = currentRun?.generated_docs || []
  const combinedDocId = currentRun?.combined_doc_id
  const legacyEvalScores = currentRun?.eval_scores || {}
  
  // Check if we have new format data
  const hasNewFormatData = generatedDocs.length > 0 || Object.keys(preCombineEvals).length > 0
  
  // Extract unique judge models from new format eval results
  const judgeModels = new Set<string>()
  Object.values(preCombineEvals).forEach(scores => {
    if (typeof scores === 'object' && scores !== null) {
      Object.keys(scores).forEach(jm => judgeModels.add(jm))
    }
  })
  Object.values(postCombineEvals).forEach(scores => {
    Object.keys(scores).forEach(jm => judgeModels.add(jm))
  })
  const judgeModelList = Array.from(judgeModels)
  
  // ============= NEW FORMAT HEATMAP TABLE =============
  const renderNewFormatHeatmapTable = (
    title: string,
    docs: Array<{ id: string; model: string; generator: string; source_doc_id?: string }>,
    evalData: Record<string, Record<string, number>>,
    sectionColor: string
  ) => (
    <div>
      <h4 className="text-lg font-semibold mb-3 flex items-center gap-2" style={{ color: sectionColor }}>
        <FileText className="w-5 h-5" />
        {title}
      </h4>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              <th 
                className="text-left p-3 font-semibold text-sm"
                style={{ backgroundColor: '#f8f9fa', color: '#555', borderBottom: '2px solid #dee2e6' }}
              >
                Generated Document
              </th>
              <th 
                className="text-left p-3 font-semibold text-sm"
                style={{ backgroundColor: '#f8f9fa', color: '#555', borderBottom: '2px solid #dee2e6' }}
              >
                Generator
              </th>
              {judgeModelList.map((judgeModel) => (
                <th 
                  key={judgeModel} 
                  className="text-center p-3 font-semibold"
                  style={{ backgroundColor: '#f8f9fa', color: '#555', borderBottom: '2px solid #dee2e6' }}
                >
                  <div className="font-mono text-xs" title={judgeModel}>
                    {judgeModel.length > 15 ? judgeModel.substring(0, 15) + '...' : judgeModel}
                  </div>
                  <div className="text-[10px] text-gray-400">Judge</div>
                </th>
              ))}
              <th 
                className="text-center p-3 font-semibold text-sm"
                style={{ backgroundColor: '#f8f9fa', color: '#555', borderBottom: '2px solid #dee2e6' }}
              >
                Avg
              </th>
            </tr>
          </thead>
          <tbody>
            {docs.map((genDoc) => {
              const docEvals = evalData[genDoc.id] || {}
              const judgeScores = judgeModelList.map(jm => docEvals[jm])
              const validScores = judgeScores.filter(s => s !== undefined && s !== null) as number[]
              const docAvg = validScores.length > 0
                ? validScores.reduce((sum, s) => sum + s, 0) / validScores.length
                : undefined
              
              return (
                <tr key={genDoc.id} style={{ borderTop: '1px solid #e9ecef' }}>
                  <td className="p-3" style={{ backgroundColor: '#fafafa' }}>
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-gray-400" />
                      <button 
                        onClick={() => openDocViewer(genDoc.id, genDoc.model)}
                        className="font-medium truncate max-w-[200px] hover:underline cursor-pointer flex items-center gap-1"
                        style={{ color: '#2563eb', background: 'none', border: 'none', padding: 0, font: 'inherit' }}
                        title={`View ${genDoc.model}`}
                      >
                        {genDoc.model.length > 25 ? genDoc.model.substring(0, 25) + '...' : genDoc.model}
                        <ExternalLink className="w-3 h-3" />
                      </button>
                    </div>
                  </td>
                  <td className="p-2">
                    <span className="text-xs font-mono px-2 py-1 rounded" style={{ backgroundColor: genDoc.generator === 'fpf' ? '#e3f2fd' : '#fff3e0', color: genDoc.generator === 'fpf' ? '#1565c0' : '#e65100' }}>
                      {genDoc.generator.toUpperCase()}
                    </span>
                  </td>
                  {judgeModelList.map((judgeModel) => {
                    const score = docEvals[judgeModel]
                    const hasScore = score !== undefined && score !== null
                    const isRunning = currentRun?.status === 'running'
                    
                    const normalizedScore = hasScore ? (score > 1 ? score / 5 : score) : undefined
                    const scoreStyle = getScoreBadgeStyle(normalizedScore)
                    
                    return (
                      <td key={judgeModel} className="p-2 text-center">
                        <div 
                          className="rounded-lg p-3 transition-all cursor-pointer hover:scale-105"
                          style={{ 
                            backgroundColor: isRunning && !hasScore ? '#9b59b6' : scoreStyle.bg,
                            color: isRunning && !hasScore ? 'white' : scoreStyle.text,
                            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                            animation: isRunning && !hasScore ? 'pulse 1.5s infinite' : 'none'
                          }}
                          title={`${judgeModel} judging ${genDoc.model}${hasScore ? `: ${score.toFixed(2)}` : ''}`}
                        >
                          {hasScore ? (
                            <>
                              <div className="font-bold text-xl">{score.toFixed(2)}</div>
                              <div className="text-[10px] mt-1 opacity-80">{scoreStyle.label}</div>
                            </>
                          ) : isRunning ? (
                            <>
                              <Loader2 className="w-6 h-6 animate-spin mx-auto" />
                              <div className="text-[10px] mt-1">evaluating</div>
                            </>
                          ) : (
                            <>
                              <div className="text-xl">—</div>
                              <div className="text-[10px] mt-1">pending</div>
                            </>
                          )}
                        </div>
                      </td>
                    )
                  })}
                  <td className="p-2">
                    <div 
                      className="rounded-lg p-3 text-center"
                      style={{ backgroundColor: '#f8f9fa', border: '1px solid #dee2e6' }}
                    >
                      <div className="font-bold text-gray-700">
                        {docAvg !== undefined ? docAvg.toFixed(2) : '—'}
                      </div>
                    </div>
                  </td>
                </tr>
              )
            })}
            {/* Column averages row */}
            <tr style={{ borderTop: '2px solid #dee2e6', backgroundColor: '#f8f9fa' }}>
              <td className="p-3 font-semibold text-gray-600" colSpan={2}>Judge Average</td>
              {judgeModelList.map((judgeModel) => {
                const judgeScores = docs
                  .map(doc => evalData[doc.id]?.[judgeModel])
                  .filter(s => s !== undefined && s !== null) as number[]
                const judgeAvg = judgeScores.length > 0
                  ? judgeScores.reduce((sum, s) => sum + s, 0) / judgeScores.length
                  : undefined
                return (
                  <td key={judgeModel} className="p-2">
                    <div 
                      className="rounded-lg p-3 text-center"
                      style={{ backgroundColor: '#f8f9fa', border: '1px solid #dee2e6' }}
                    >
                      <div className="font-bold text-gray-700">
                        {judgeAvg !== undefined ? judgeAvg.toFixed(2) : '—'}
                      </div>
                    </div>
                  </td>
                )
              })}
              <td></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
  
  // ============= LEGACY FORMAT HEATMAP TABLE =============
  const renderLegacyHeatmapTable = () => {
    const sourceDocIds = Object.keys(legacyEvalScores)
    if (sourceDocIds.length === 0) return null
    
    const generatorModels = new Set<string>()
    Object.values(legacyEvalScores).forEach(docScores => {
      Object.keys(docScores).forEach(model => generatorModels.add(model))
    })
    const generatorModelList = Array.from(generatorModels)
    
    return (
      <div>
        <h4 className="text-lg font-semibold mb-3 flex items-center gap-2" style={{ color: '#2563eb' }}>
          <FileText className="w-5 h-5" />
          Evaluation Results by Generator Model
        </h4>
        <p className="text-sm text-gray-500 mb-4">
          Showing average scores for each generator model's output (legacy format - per-judge breakdown not available)
        </p>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                <th 
                  className="text-left p-3 font-semibold text-sm"
                  style={{ backgroundColor: '#f8f9fa', color: '#555', borderBottom: '2px solid #dee2e6' }}
                >
                  Generator Model
                </th>
                <th 
                  className="text-center p-3 font-semibold text-sm"
                  style={{ backgroundColor: '#f8f9fa', color: '#555', borderBottom: '2px solid #dee2e6' }}
                >
                  Average Score
                </th>
                <th 
                  className="text-center p-3 font-semibold text-sm"
                  style={{ backgroundColor: '#f8f9fa', color: '#555', borderBottom: '2px solid #dee2e6' }}
                >
                  Rating
                </th>
              </tr>
            </thead>
            <tbody>
              {generatorModelList.map((model) => {
                const scores = sourceDocIds
                  .map(docId => legacyEvalScores[docId]?.[model])
                  .filter(s => s !== undefined && s !== null) as number[]
                const avgScore = scores.length > 0
                  ? scores.reduce((sum, s) => sum + s, 0) / scores.length
                  : undefined
                
                const normalizedScore = avgScore !== undefined ? (avgScore > 1 ? avgScore / 5 : avgScore) : undefined
                const scoreStyle = getScoreBadgeStyle(normalizedScore)
                const isRunning = currentRun?.status === 'running'
                const hasScore = avgScore !== undefined
                
                return (
                  <tr key={model} style={{ borderTop: '1px solid #e9ecef' }}>
                    <td className="p-3" style={{ backgroundColor: '#fafafa' }}>
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-gray-400" />
                        <span className="text-gray-700 font-medium font-mono" title={model}>
                          {model}
                        </span>
                      </div>
                    </td>
                    <td className="p-2 text-center">
                      <div 
                        className="rounded-lg p-4 inline-block min-w-[80px] transition-all cursor-pointer hover:scale-105"
                        style={{ 
                          backgroundColor: isRunning && !hasScore ? '#9b59b6' : scoreStyle.bg,
                          color: isRunning && !hasScore ? 'white' : scoreStyle.text,
                          boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                          animation: isRunning && !hasScore ? 'pulse 1.5s infinite' : 'none'
                        }}
                      >
                        {hasScore ? (
                          <div className="font-bold text-2xl">{avgScore.toFixed(2)}</div>
                        ) : isRunning ? (
                          <Loader2 className="w-6 h-6 animate-spin mx-auto" />
                        ) : (
                          <div className="text-xl">—</div>
                        )}
                      </div>
                    </td>
                    <td className="p-2 text-center">
                      <span 
                        className="px-3 py-1 rounded-full text-sm font-semibold"
                        style={{ backgroundColor: scoreStyle.bg, color: scoreStyle.text }}
                      >
                        {scoreStyle.label}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    )
  }
  
  // ============= ACM1-STYLE CRITERIA HEATMAP =============
  const renderACM1StyleHeatmap = (
    title: string,
    docs: Array<{ id: string; model: string; generator: string }>,
    detailedData: Record<string, { evaluations: Array<{ judge_model: string; trial: number; scores: Array<{ criterion: string; score: number; reason: string }>; average_score: number }>; overall_average: number }>,
    sectionColor: string,
    criteriaList: string[],
    evaluatorList: string[]
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
    
    const maxPossible = criteriaList.length * evaluatorList.length * 5
    
    return (
      <div>
        <h4 className="text-lg font-semibold mb-3 flex items-center gap-2" style={{ color: sectionColor }}>
          <FileText className="w-5 h-5" />
          {title}
        </h4>
        
        <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: '#e9ecef' }}>
          <strong>Evaluators:</strong> {evaluatorList.join(', ')}
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full border-collapse" style={{ backgroundColor: 'white', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
            <thead>
              <tr>
                <th 
                  className="text-left p-3 font-semibold"
                  style={{ backgroundColor: '#f8f9fa', color: '#555', borderBottom: '2px solid #ddd' }}
                >
                  Document
                </th>
                {criteriaList.map((criterion) => (
                  <th 
                    key={criterion}
                    className="text-center p-3 font-semibold text-sm"
                    style={{ backgroundColor: '#f8f9fa', color: '#555', borderBottom: '2px solid #ddd' }}
                    title={criterion}
                  >
                    {criterion.length > 12 ? criterion.substring(0, 12) + '...' : criterion}
                  </th>
                ))}
                <th 
                  className="text-center p-3 font-semibold"
                  style={{ backgroundColor: '#f8f9fa', color: '#555', borderBottom: '2px solid #ddd' }}
                >
                  Total Score
                </th>
              </tr>
            </thead>
            <tbody>
              {docs.map((doc) => {
                const docScores = scoreLookup[doc.id] || {}
                
                let totalScore = 0
                let scoreCount = 0
                for (const criterion of criteriaList) {
                  const criterionScores = docScores[criterion] || {}
                  for (const judgeModel of evaluatorList) {
                    if (criterionScores[judgeModel]) {
                      totalScore += criterionScores[judgeModel].score
                      scoreCount++
                    }
                  }
                }
                const percentage = maxPossible > 0 ? (totalScore / maxPossible * 100).toFixed(1) : '0.0'
                
                return (
                  <tr key={doc.id} className="hover:bg-gray-50">
                    <td className="p-3" style={{ fontWeight: 'bold', borderBottom: '1px solid #ddd', backgroundColor: 'white' }}>
                      <div className="flex items-center gap-2">
                        <span 
                          className="text-xs font-mono px-2 py-0.5 rounded"
                          style={{ 
                            backgroundColor: doc.generator === 'fpf' ? '#e3f2fd' : doc.generator === 'gptr' ? '#fff3e0' : '#f3e5f5',
                            color: doc.generator === 'fpf' ? '#1565c0' : doc.generator === 'gptr' ? '#e65100' : '#7b1fa2'
                          }}
                        >
                          {doc.generator.toUpperCase()}
                        </span>
                        <button 
                          onClick={() => openDocViewer(doc.id, doc.model)}
                          className="truncate max-w-[150px] hover:underline cursor-pointer flex items-center gap-1"
                          style={{ color: '#2563eb', background: 'none', border: 'none', padding: 0, font: 'inherit', fontWeight: 'bold' }}
                          title={`View ${doc.model}`}
                        >
                          {doc.model.length > 20 ? doc.model.substring(0, 20) + '...' : doc.model}
                          <ExternalLink className="w-3 h-3" />
                        </button>
                      </div>
                    </td>
                    {criteriaList.map((criterion) => {
                      const criterionScores = docScores[criterion] || {}
                      
                      return (
                        <td key={criterion} className="p-2 text-center" style={{ borderBottom: '1px solid #ddd' }}>
                          <div className="flex justify-center gap-0.5">
                            {evaluatorList.map((judgeModel) => {
                              const scoreInfo = criterionScores[judgeModel]
                              if (!scoreInfo) {
                                return (
                                  <span 
                                    key={judgeModel}
                                    className="inline-block px-2 py-1 rounded text-xs font-bold cursor-help"
                                    style={{ backgroundColor: '#e9ecef', color: '#6c757d' }}
                                    title={`${judgeModel}: No score`}
                                  >
                                    —
                                  </span>
                                )
                              }
                              
                              let bgColor = '#e9ecef'
                              let textColor = '#6c757d'
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
                                  className="inline-block px-2 py-1 rounded text-xs font-bold cursor-help"
                                  style={{ backgroundColor: bgColor, color: textColor, minWidth: '20px' }}
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
                    <td className="p-3 text-center" style={{ fontWeight: 'bold', fontSize: '1.1em', borderBottom: '1px solid #ddd', color: '#374151' }}>
                      {percentage}% 
                      <span style={{ fontSize: '0.7em', color: '#777', marginLeft: '4px' }}>
                        ({totalScore}/{maxPossible})
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    )
  }
  
  // ============= RENDER LOGIC =============
  const preDetailedData = currentRun?.pre_combine_evals_detailed || {}
  const postDetailedData = currentRun?.post_combine_evals_detailed || {}
  const criteriaList = currentRun?.criteria_list || []
  const evaluatorList = currentRun?.evaluator_list || []
  const hasDetailedData = Object.keys(preDetailedData).length > 0 && criteriaList.length > 0
  
  let content: React.ReactNode
  
  if (hasDetailedData) {
    const preCombineDocs = generatedDocs.filter(d => d.id !== combinedDocId)
    const postCombineDocs = combinedDocId ? generatedDocs.filter(d => d.id === combinedDocId) : []
    
    content = (
      <>
        {preCombineDocs.length > 0 ? (
          renderACM1StyleHeatmap(
            'Pre-Combine Evaluations - Single Document Consensus Matrix',
            preCombineDocs,
            preDetailedData,
            '#2563eb',
            criteriaList,
            evaluatorList
          )
        ) : (
          <div className="text-center text-gray-500 py-8">
            <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No evaluation data available yet. Execute a run to see results.</p>
          </div>
        )}
        
        {postCombineDocs.length > 0 && Object.keys(postDetailedData).length > 0 && (
          <div className="mt-8 pt-6" style={{ borderTop: '2px solid #e9ecef' }}>
            {renderACM1StyleHeatmap(
              'Post-Combine Evaluations - Combined Document Matrix',
              postCombineDocs,
              postDetailedData,
              '#059669',
              criteriaList,
              evaluatorList
            )}
          </div>
        )}
      </>
    )
  } else if (hasNewFormatData) {
    const preCombineDocs = generatedDocs.filter(d => d.id !== combinedDocId)
    const postCombineDocs = combinedDocId ? generatedDocs.filter(d => d.id === combinedDocId) : []
    
    content = (
      <>
        {preCombineDocs.length > 0 || Object.keys(preCombineEvals).length > 0 ? (
          renderNewFormatHeatmapTable(
            'Pre-Combine Evaluations',
            preCombineDocs.length > 0 ? preCombineDocs : Object.keys(preCombineEvals).map(id => ({ id, model: id, generator: 'fpf', source_doc_id: '', iteration: 1 })),
            preCombineEvals,
            '#2563eb'
          )
        ) : (
          <div className="text-center text-gray-500 py-8">
            <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No evaluation data available yet. Execute a run to see results.</p>
          </div>
        )}
        
        {(postCombineDocs.length > 0 || Object.keys(postCombineEvals).length > 0) && (
          <div className="mt-8 pt-6" style={{ borderTop: '2px solid #e9ecef' }}>
            {renderNewFormatHeatmapTable(
              'Post-Combine Evaluations',
              postCombineDocs.length > 0 ? postCombineDocs : Object.keys(postCombineEvals).map(id => ({ id, model: 'Combined Document', generator: 'combine', source_doc_id: '', iteration: 1 })),
              postCombineEvals,
              '#059669'
            )}
          </div>
        )}
      </>
    )
  } else if (Object.keys(legacyEvalScores).length > 0) {
    content = renderLegacyHeatmapTable()
  } else {
    content = (
      <div className="text-center text-gray-500 py-8">
        <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
        <p>No evaluation data available yet. Execute a run to see results.</p>
      </div>
    )
  }

  return (
    <div className="p-5 space-y-8">
      {content}

      {/* Color Legend - ACM 1.0 style */}
      <div className="mt-5 pt-4 flex items-center justify-between text-sm" style={{ borderTop: '1px solid #e9ecef' }}>
        <div className="flex items-center gap-4">
          <span className="font-semibold text-gray-600">Score Legend (1-5 scale):</span>
          <div className="flex items-center gap-1">
            <div className="w-8 h-6 rounded flex items-center justify-center text-[10px] font-bold" style={{ backgroundColor: '#dc3545', color: 'white' }}>1</div>
            <div className="w-8 h-6 rounded flex items-center justify-center text-[10px] font-bold" style={{ backgroundColor: '#fd7e14', color: 'white' }}>2</div>
            <div className="w-8 h-6 rounded flex items-center justify-center text-[10px] font-bold" style={{ backgroundColor: '#ffc107', color: '#333' }}>3</div>
            <div className="w-8 h-6 rounded flex items-center justify-center text-[10px] font-bold" style={{ backgroundColor: '#90EE90', color: '#006400' }}>4</div>
            <div className="w-8 h-6 rounded flex items-center justify-center text-[10px] font-bold" style={{ backgroundColor: '#28a745', color: 'white' }}>5</div>
          </div>
          <div className="flex items-center gap-2 ml-4">
            <div className="w-8 h-6 rounded animate-pulse" style={{ backgroundColor: '#9b59b6' }}></div>
            <span className="text-gray-500">In Progress</span>
          </div>
        </div>
        <div className="text-gray-500">
          {execStatus.status === 'idle' ? 'Click Execute to start' : 
           execStatus.status === 'running' ? '⚡ Live updating...' : 
           execStatus.status === 'completed' ? '✓ Execution complete' : execStatus.status}
        </div>
      </div>

      {/* Document Viewer Modal */}
      {docViewer.isOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div 
            className="bg-white rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] flex flex-col"
            style={{ minHeight: '400px' }}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b">
              <div>
                <h3 className="text-lg font-semibold text-gray-800">Generated Document</h3>
                <p className="text-sm text-gray-500 font-mono">{docViewer.model}</p>
              </div>
              <button
                onClick={closeDocViewer}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>
            
            {/* Modal Body */}
            <div className="flex-1 overflow-auto p-4">
              {docViewer.loading ? (
                <div className="flex items-center justify-center h-full">
                  <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                  <span className="ml-2 text-gray-500">Loading document...</span>
                </div>
              ) : docViewer.error ? (
                <div className="text-center text-red-500 p-8">
                  <p className="font-semibold">Failed to load document</p>
                  <p className="text-sm mt-2">{docViewer.error}</p>
                </div>
              ) : (
                <pre 
                  className="whitespace-pre-wrap font-mono text-sm text-gray-700 leading-relaxed"
                  style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' }}
                >
                  {docViewer.content || '(Empty document)'}
                </pre>
              )}
            </div>
            
            {/* Modal Footer */}
            <div className="flex items-center justify-end gap-3 p-4 border-t bg-gray-50">
              <span className="text-sm text-gray-500 mr-auto">
                {docViewer.content ? `${docViewer.content.length.toLocaleString()} characters` : ''}
              </span>
              <button
                onClick={() => setShowGithubExport(true)}
                disabled={!docViewer.content || exporting}
                className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors disabled:opacity-50"
              >
                {exporting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Github className="w-4 h-4" />
                )}
                Export to GitHub
              </button>
              <button
                onClick={closeDocViewer}
                className="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* GitHub Export Browser */}
      <GitHubFileBrowser
        isOpen={showGithubExport}
        onClose={() => setShowGithubExport(false)}
        onSelectPath={handleGithubExport}
        mode="select-path"
        title="Export to GitHub"
        defaultFilename={`${docViewer.model?.replace(/[^a-zA-Z0-9-_]/g, '_') || 'output'}.md`}
      />
    </div>
  )
}
