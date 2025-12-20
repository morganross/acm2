import { useState, useEffect } from 'react'
import { 
  Scale, 
  FileText, 
  GitCompare, 
  Play, 
  AlertCircle,
  Loader2
} from 'lucide-react'
import { evaluationApi, type EvaluationCriteria } from '../api'

export default function Evaluation() {
  const [activeTab, setActiveTab] = useState<'criteria' | 'single' | 'pairwise'>('criteria')
  const [criteria, setCriteria] = useState<EvaluationCriteria[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadCriteria()
  }, [])

  async function loadCriteria() {
    try {
      setLoading(true)
      const response = await evaluationApi.getCriteria()
      setCriteria(response.criteria)
    } catch (err) {
      setError('Failed to load criteria')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Evaluation</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage evaluation criteria and run ad-hoc evaluations
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('criteria')}
            className={`${
              activeTab === 'criteria'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
            } whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium flex items-center`}
          >
            <Scale className="mr-2 h-4 w-4" />
            Criteria
          </button>
          <button
            onClick={() => setActiveTab('single')}
            className={`${
              activeTab === 'single'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
            } whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium flex items-center`}
          >
            <FileText className="mr-2 h-4 w-4" />
            Single Doc
          </button>
          <button
            onClick={() => setActiveTab('pairwise')}
            className={`${
              activeTab === 'pairwise'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
            } whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium flex items-center`}
          >
            <GitCompare className="mr-2 h-4 w-4" />
            Pairwise
          </button>
        </nav>
      </div>

      {/* Content */}
      <div className="bg-white shadow sm:rounded-lg p-6">
        {loading && activeTab === 'criteria' ? (
          <div className="flex justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
          </div>
        ) : error ? (
          <div className="rounded-md bg-red-50 p-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <AlertCircle className="h-5 w-5 text-red-400" aria-hidden="true" />
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-red-800">Error</h3>
                <div className="mt-2 text-sm text-red-700">
                  <p>{error}</p>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <>
            {activeTab === 'criteria' && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                  {criteria.map((c) => (
                    <div
                      key={c.name}
                      className="relative flex flex-col rounded-lg border border-gray-300 bg-white p-6 shadow-sm hover:border-gray-400 focus-within:ring-2 focus-within:ring-blue-500 focus-within:ring-offset-2"
                    >
                      <div className="flex items-center space-x-3">
                        <div className="flex-shrink-0">
                          <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-blue-600 font-bold">
                            {c.weight}x
                          </span>
                        </div>
                        <h3 className="text-lg font-medium text-gray-900 capitalize">
                          {c.name}
                        </h3>
                      </div>
                      <p className="mt-4 text-sm text-gray-500 flex-1">
                        {c.description}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === 'single' && (
              <SingleEvalForm criteria={criteria} />
            )}

            {activeTab === 'pairwise' && (
              <PairwiseEvalForm criteria={criteria} />
            )}
          </>
        )}
      </div>
    </div>
  )
}

function SingleEvalForm({ criteria }: { criteria: EvaluationCriteria[] }) {
  const [content, setContent] = useState('')
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  async function handleRun() {
    if (!content) return
    setLoading(true)
    try {
      const res = await evaluationApi.evaluateSingle({
        document_path: 'adhoc-doc',
        content,
        criteria
      })
      setResult(res)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700">
          Document Content
        </label>
        <div className="mt-1">
          <textarea
            rows={10}
            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm font-mono"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Paste document content here..."
          />
        </div>
      </div>

      <div className="flex justify-end">
        <button
          onClick={handleRun}
          disabled={loading || !content}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
        >
          {loading ? (
            <>
              <Loader2 className="animate-spin -ml-1 mr-2 h-4 w-4" />
              Evaluating...
            </>
          ) : (
            <>
              <Play className="-ml-1 mr-2 h-4 w-4" />
              Run Evaluation
            </>
          )}
        </button>
      </div>

      {result && (
        <div className="mt-8 border-t border-gray-200 pt-8">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Results</h3>
          <div className="bg-gray-50 rounded-lg p-6">
            <div className="flex items-center justify-between mb-6">
              <span className="text-sm text-gray-500">Total Score</span>
              <span className="text-3xl font-bold text-blue-600">
                {result.total_score.toFixed(2)}
              </span>
            </div>
            <div className="space-y-4">
              {Object.entries(result.scores).map(([key, score]) => (
                <div key={key} className="border-b border-gray-200 pb-4 last:border-0">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium capitalize">{key}</span>
                    <span className={`px-2 py-1 rounded text-xs font-bold ${
                      (score as number) >= 4 ? 'bg-green-100 text-green-800' :
                      (score as number) >= 3 ? 'bg-yellow-100 text-yellow-800' :
                      'bg-red-100 text-red-800'
                    }`}>
                      {score as number} / 5
                    </span>
                  </div>
                  <p className="text-sm text-gray-600">
                    {result.reasoning[key]}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function PairwiseEvalForm({ criteria }: { criteria: EvaluationCriteria[] }) {
  const [docA, setDocA] = useState('')
  const [docB, setDocB] = useState('')
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  async function handleRun() {
    if (!docA || !docB) return
    setLoading(true)
    try {
      const res = await evaluationApi.evaluatePairwise({
        doc_a_path: 'Doc A',
        doc_a_content: docA,
        doc_b_path: 'Doc B',
        doc_b_content: docB,
        criteria
      })
      setResult(res)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Document A
          </label>
          <div className="mt-1">
            <textarea
              rows={10}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm font-mono"
              value={docA}
              onChange={(e) => setDocA(e.target.value)}
              placeholder="Paste content for Document A..."
            />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Document B
          </label>
          <div className="mt-1">
            <textarea
              rows={10}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm font-mono"
              value={docB}
              onChange={(e) => setDocB(e.target.value)}
              placeholder="Paste content for Document B..."
            />
          </div>
        </div>
      </div>

      <div className="flex justify-end">
        <button
          onClick={handleRun}
          disabled={loading || !docA || !docB}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
        >
          {loading ? (
            <>
              <Loader2 className="animate-spin -ml-1 mr-2 h-4 w-4" />
              Comparing...
            </>
          ) : (
            <>
              <GitCompare className="-ml-1 mr-2 h-4 w-4" />
              Compare Documents
            </>
          )}
        </button>
      </div>

      {result && (
        <div className="mt-8 border-t border-gray-200 pt-8">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Comparison Result</h3>
          <div className={`rounded-lg p-6 ${
            result.winner === 'Tie' ? 'bg-gray-100' : 'bg-blue-50'
          }`}>
            <div className="flex items-center justify-center mb-6">
              <div className="text-center">
                <span className="block text-sm text-gray-500 uppercase tracking-wide">Winner</span>
                <span className="block text-4xl font-bold text-blue-900 mt-2">
                  {result.winner === 'A' ? 'Document A' : 
                   result.winner === 'B' ? 'Document B' : 'Tie'}
                </span>
              </div>
            </div>
            <div className="prose prose-sm max-w-none text-gray-700 bg-white p-4 rounded border border-gray-200">
              <p className="whitespace-pre-wrap">{result.reasoning}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
