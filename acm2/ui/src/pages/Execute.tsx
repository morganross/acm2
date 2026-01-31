import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { 
  Play, Square, AlertCircle, Activity, Clock,
  FileText, Users, ChevronDown, Timer,
  XCircle, CheckCircle, Loader2, RefreshCw
} from 'lucide-react';
import LogViewer from '../components/execution/LogViewer';
import type { Run } from '../api';
import { runsApi } from '../api';
import { formatTime, computeEndTime } from './execute/utils';
import SourceDocSection from './execute/SourceDocSection';
import useRunSocket from '../hooks/useRunSocket';
import { getConcurrencySettings } from './Settings';

interface Preset {
  id: string;
  name: string;
  description?: string;
  document_count?: number;
  model_count?: number;
  documents?: string[];
  evaluators?: string[];
  log_level?: string;
  general_config?: {
    log_level?: string;
  };
}

export default function Execute() {
  const { runId } = useParams<{ runId?: string }>();
  const [presets, setPresets] = useState<Preset[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<Preset | null>(null);
  const [fullPresetData, setFullPresetData] = useState<Preset | null>(null);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [currentRun, setCurrentRun] = useState<Run | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isReevaluating, setIsReevaluating] = useState(false);
  const [runningRunsCount, setRunningRunsCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Helper to check if a value is "empty" (null, undefined, empty object, or empty array)
  const isEmpty = (val: unknown): boolean => {
    if (val === null || val === undefined) return true;
    if (Array.isArray(val)) return val.length === 0;
    if (typeof val === 'object') return Object.keys(val as object).length === 0;
    return false;
  };

  // Merge run updates while preserving non-empty data
  // If the new value is empty but the old value had data, keep the old data
  const mergeRun = (prev: Run | null, updated: Run): Run => {
    const merged: any = { ...(prev || {}), ...updated };
    
    // Fields that should be preserved if the update is empty but prev had data
    const preserveFields = [
      'fpf_stats',
      'pre_combine_evals_detailed',
      'post_combine_evals_detailed',
      'criteria_list',
      'evaluator_list',
      'timeline_events',
      'generation_events',
      'generated_docs',
      'pre_combine_evals',
      'post_combine_evals',
      'pairwise_results',
      'tasks',
      'source_doc_results',
    ];

    for (const field of preserveFields) {
      const prevVal = (prev as any)?.[field];
      const newVal = (updated as any)?.[field];
      // If new value is empty but prev had data, keep prev
      if (isEmpty(newVal) && !isEmpty(prevVal)) {
        merged[field] = prevVal;
      }
    }

    return merged;
  };

  const handleRunUpdate = useCallback((updatedRun: Run) => {
    if (!updatedRun?.id) return;
    
    // If run just completed, re-fetch from API to get full data (WebSocket may have incomplete data)
    if (updatedRun.status === 'completed' || updatedRun.status === 'failed' || updatedRun.status === 'cancelled') {
      setIsRunning(false);
      runsApi.get(updatedRun.id).then(fullRun => {
        setCurrentRun(prev => mergeRun(prev, fullRun));
      }).catch(err => {
        console.error('Failed to re-fetch run on completion:', err);
        // Fall back to WebSocket data
        setCurrentRun(prev => mergeRun(prev, updatedRun));
      });
      return;
    }
    
    setCurrentRun(prev => mergeRun(prev, updatedRun));
    // Update running state based on status
    if (updatedRun.status === 'running' || updatedRun.status === 'pending') {
      setIsRunning(true);
    }
  }, []);

  const handleStatsUpdate = useCallback((stats: any) => {
    setCurrentRun(prev => (prev ? { ...prev, fpf_stats: stats } : prev));
  }, []);

  const handleGenComplete = useCallback((genDoc: any) => {
    // Add generated doc to local state for immediate heatmap row display
    setCurrentRun(prev => {
      if (!prev) return prev;
      const generatedDocs = prev.generated_docs || [];
      // Avoid duplicates
      if (generatedDocs.some((d: any) => d.id === genDoc.id)) {
        return prev;
      }
      return { ...prev, generated_docs: [...generatedDocs, genDoc] };
    });
  }, []);

  const handleTaskUpdate = useCallback((task: any) => {
    setCurrentRun(prev => {
      if (!prev) return prev;
      const tasks = (prev.tasks || []).map((t: any) => (t.id === task.id ? { ...t, ...task } : t));
      return { ...prev, tasks };
    });
  }, []);

  const handleTasksInit = useCallback((tasks: any[]) => {
    setCurrentRun(prev => (prev ? { ...prev, tasks } : prev));
  }, []);

  // WebSocket for real-time updates
  useRunSocket(currentRun?.id, {
    onRunUpdate: handleRunUpdate,
    onTaskUpdate: handleTaskUpdate,
    onTasksInit: handleTasksInit,
    onStatsUpdate: handleStatsUpdate,
    onGenComplete: handleGenComplete,
  });

  // Load run from URL if runId is provided (initial load only - WebSocket handles updates)
  useEffect(() => {
    if (runId) {
      runsApi.get(runId)
        .then(async run => {
          setCurrentRun(prev => mergeRun(prev, run));
          setIsRunning(run.status === 'running' || run.status === 'pending');
          
          // Also fetch preset data if run has preset_id
          if (run.preset_id) {
            try {
              const presetResponse = await fetch(`/api/v1/presets/${run.preset_id}`);
              if (presetResponse.ok) {
                const presetData = await presetResponse.json();
                setFullPresetData(presetData);
              }
            } catch (err) {
              console.error('Failed to fetch preset for run:', err);
            }
          }
        })
        .catch(err => {
          console.error('Failed to load run:', err);
          setError('Failed to load run');
        });
    }
  }, [runId]);

  // Fetch running runs count
  const fetchRunningCount = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/runs/count?status=running');
      if (res.ok) {
        const data = await res.json();
        setRunningRunsCount(data.total);
      }
    } catch (err) {
      console.error('Failed to fetch running count:', err);
    }
  }, []);

  // Poll for running count every 10s
  useEffect(() => {
    fetchRunningCount();
    const interval = setInterval(fetchRunningCount, 10000);
    return () => clearInterval(interval);
  }, [fetchRunningCount]);

  // Fetch presets on mount
  useEffect(() => {
    fetch('/api/v1/presets')
      .then(res => res.json())
      .then(data => {
        const presetList = data.items || data.presets || data || [];
        setPresets(presetList);
        if (presetList.length > 0 && !selectedPreset) {
          setSelectedPreset(presetList[0]);
        }
      })
      .catch(err => {
        console.error('Failed to load presets:', err);
        setError('Failed to load presets');
      });
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const startExecution = async () => {
    if (!selectedPreset) return;
    
    setError(null);
    setIsRunning(true);
    setCurrentRun(null);
    
    try {
      // Fetch full preset to get documents
      const presetResponse = await fetch(`/api/v1/presets/${selectedPreset.id}`);
      if (!presetResponse.ok) {
        throw new Error('Failed to fetch preset details');
      }
      const presetData = await presetResponse.json();
      setFullPresetData(presetData);
      
      // Create a new run
      // Get concurrency settings from localStorage
      const concurrencySettings = getConcurrencySettings();
      
      const createResponse = await fetch('/api/v1/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: `${selectedPreset.name} - ${new Date().toLocaleString()}`,
          preset_id: selectedPreset.id,
          document_ids: presetData.documents || [],
          // Pass concurrency settings as config overrides
          config_overrides: {
            concurrency: {
              generation_concurrency: concurrencySettings.generationConcurrency,
              eval_concurrency: concurrencySettings.evalConcurrency,
              request_timeout: concurrencySettings.requestTimeout,
              eval_timeout: concurrencySettings.evalTimeout,
              max_retries: concurrencySettings.maxRetries,
              retry_delay: concurrencySettings.retryDelay
            }
          }
        })
      });
      
      if (!createResponse.ok) {
        const errorData = await createResponse.json().catch(() => ({}));
        throw new Error(errorData.detail?.[0]?.msg || 'Failed to create run');
      }
      
      const runData = await createResponse.json();
      const runId = runData.id;

      setCurrentRun(prev => {
        const merged: any = { ...(prev || {}), ...runData };
        if (!runData.fpf_stats && prev?.fpf_stats) {
          merged.fpf_stats = prev.fpf_stats;
        }
        return merged;
      });

      // Wait for React to render and WebSocket to connect before starting
      // This prevents the race condition where stats are broadcast before WS connects
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Start the run
      const startResponse = await fetch(`/api/v1/runs/${runId}/start`, {
        method: 'POST'
      });
      
      if (!startResponse.ok) {
        throw new Error('Failed to start run');
      }
      
      // Re-fetch the run to get source_doc_results that was initialized during start
      // This ensures collapsible sections appear immediately
      const updatedRunResponse = await fetch(`/api/v1/runs/${runId}`);
      if (updatedRunResponse.ok) {
        const updatedRunData = await updatedRunResponse.json();
        setCurrentRun(prev => ({
          ...(prev || {}),
          ...updatedRunData,
        }));
        console.log('[Execute] Re-fetched run after start, source_doc_results:', updatedRunData.source_doc_results);
      }
      
      // WebSocket handles all real-time updates - no polling needed
      
    } catch (err) {
      console.error('Failed to start execution:', err);
      setError(err instanceof Error ? err.message : 'Failed to start execution');
      setIsRunning(false);
    }
  };

  const stopExecution = async () => {
    if (currentRun?.id) {
      try {
        await fetch(`/api/v1/runs/${currentRun.id}/cancel`, {
          method: 'POST'
        });
      } catch (err) {
        console.error('Failed to cancel run:', err);
      }
    }
    
    setIsRunning(false);
  };

  const reevaluateRun = async () => {
    if (!currentRun?.id) return;
    
    setIsReevaluating(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/v1/runs/${currentRun.id}/reevaluate`, {
        method: 'POST'
      });
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to start re-evaluation');
      }
      
      // Poll for updated run data after a short delay
      setTimeout(async () => {
        try {
          const updatedRun = await runsApi.get(currentRun.id);
          setCurrentRun(updatedRun);
        } catch (err) {
          console.error('Failed to refresh run:', err);
        }
        setIsReevaluating(false);
      }, 5000); // Wait 5s before first check
      
    } catch (err) {
      console.error('Failed to re-evaluate:', err);
      setError(err instanceof Error ? err.message : 'Failed to re-evaluate');
      setIsReevaluating(false);
    }
  };

  const getStatusIcon = () => {
    if (!currentRun) return <Activity size={20} />;
    switch (currentRun.status) {
      case 'running': return <Loader2 size={20} className="animate-spin" />;
      case 'completed': return <CheckCircle size={20} />;
      case 'failed': return <XCircle size={20} />;
      case 'cancelled': return <XCircle size={20} />;
      default: return <Clock size={20} />;
    }
  };

  const getStatusColor = () => {
    if (!currentRun) return '#6b7280';
    switch (currentRun.status) {
      case 'running': return '#3b82f6';
      case 'completed': return '#22c55e';
      case 'failed': return '#ef4444';
      case 'cancelled': return '#f59e0b';
      default: return '#6b7280';
    }
  };

  return (
    <div style={{ padding: '24px', backgroundColor: '#111827', minHeight: '100vh' }}>
      {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: 'white', margin: 0 }}>
              Execute Evaluation
            </h1>
            <p style={{ color: '#9ca3af', marginTop: '8px' }}>
              Run document generation and evaluation workflows
            </p>
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            {isRunning ? (
              <button
                onClick={stopExecution}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '10px 20px',
                  backgroundColor: '#dc2626',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                <Square size={18} />
                Stop Execution
              </button>
            ) : (
              <button
                onClick={startExecution}
                disabled={!selectedPreset}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '10px 20px',
                  backgroundColor: selectedPreset ? '#22c55e' : '#374151',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: selectedPreset ? 'pointer' : 'not-allowed',
                  fontSize: '14px',
                  opacity: selectedPreset ? 1 : 0.5
                }}
              >
                <Play size={18} />
                Start Execution
              </button>
            )}
            {/* Re-evaluate button - shown when run is completed/failed */}
            {currentRun && (currentRun.status === 'completed' || currentRun.status === 'failed') && (
              <button
                onClick={reevaluateRun}
                disabled={isReevaluating}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '10px 20px',
                  backgroundColor: isReevaluating ? '#374151' : '#6366f1',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: isReevaluating ? 'not-allowed' : 'pointer',
                  fontSize: '14px',
                  opacity: isReevaluating ? 0.7 : 1
                }}
              >
                <RefreshCw size={18} className={isReevaluating ? 'animate-spin' : ''} />
                {isReevaluating ? 'Re-evaluating...' : 'Re-evaluate'}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '16px',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: '8px',
          marginBottom: '24px'
        }}>
          <AlertCircle size={20} style={{ color: '#ef4444' }} />
          <span style={{ color: '#fca5a5' }}>{error}</span>
        </div>
      )}

      {/* Preset Selector Card */}
      <div style={{
        backgroundColor: '#1f2937',
        borderRadius: '12px',
        padding: '20px',
        marginBottom: '24px',
        border: '1px solid #374151'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '300px' }}>
            <label style={{ color: '#9ca3af', fontSize: '14px', marginBottom: '8px', display: 'block' }}>
              Select Preset
            </label>
            <div ref={dropdownRef} style={{ position: 'relative' }}>
              <button
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                style={{
                  width: '100%',
                  padding: '12px 16px',
                  backgroundColor: '#374151',
                  border: '1px solid #4b5563',
                  borderRadius: '8px',
                  color: 'white',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  cursor: 'pointer'
                }}
              >
                <span>{selectedPreset?.name || 'Select a preset...'}</span>
                <ChevronDown size={18} style={{ 
                  transform: isDropdownOpen ? 'rotate(180deg)' : 'none',
                  transition: 'transform 0.2s'
                }} />
              </button>
              {isDropdownOpen && (
                <div style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  marginTop: '4px',
                  backgroundColor: '#374151',
                  border: '1px solid #4b5563',
                  borderRadius: '8px',
                  zIndex: 50,
                  maxHeight: '300px',
                  overflowY: 'auto'
                }}>
                  {presets.map(preset => (
                    <button
                      key={preset.id}
                      onClick={() => {
                        setSelectedPreset(preset);
                        setIsDropdownOpen(false);
                      }}
                      style={{
                        width: '100%',
                        padding: '12px 16px',
                        backgroundColor: selectedPreset?.id === preset.id ? '#4b5563' : 'transparent',
                        border: 'none',
                        color: 'white',
                        textAlign: 'left',
                        cursor: 'pointer',
                        display: 'block'
                      }}
                      onMouseEnter={(e) => {
                        if (selectedPreset?.id !== preset.id) {
                          e.currentTarget.style.backgroundColor = '#4b556380';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (selectedPreset?.id !== preset.id) {
                          e.currentTarget.style.backgroundColor = 'transparent';
                        }
                      }}
                    >
                      <div style={{ fontWeight: 500 }}>{preset.name}</div>
                      {preset.description && (
                        <div style={{ color: '#9ca3af', fontSize: '12px', marginTop: '4px' }}>
                          {preset.description}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          
          {selectedPreset && (
            <>
              <div style={{ textAlign: 'center', padding: '0 20px' }}>
                <div style={{ color: '#9ca3af', fontSize: '12px' }}>Documents</div>
                <div style={{ color: 'white', fontSize: '24px', fontWeight: 'bold' }}>
                  {selectedPreset.document_count || '-'}
                </div>
              </div>
              <div style={{ textAlign: 'center', padding: '0 20px' }}>
                <div style={{ color: '#9ca3af', fontSize: '12px' }}>Models</div>
                <div style={{ color: 'white', fontSize: '24px', fontWeight: 'bold' }}>
                  {selectedPreset.model_count || '-'}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Stats Cards */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
        gap: '16px',
        marginBottom: '24px'
      }}>
        <div style={{
          backgroundColor: '#1f2937',
          borderRadius: '12px',
          padding: '20px',
          border: '1px solid #374151'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ 
              padding: '10px', 
              backgroundColor: `${getStatusColor()}20`,
              borderRadius: '8px'
            }}>
              {getStatusIcon()}
            </div>
            <div>
              <div style={{ color: '#9ca3af', fontSize: '14px' }}>Status</div>
              <div style={{ color: getStatusColor(), fontSize: '18px', fontWeight: 'bold', textTransform: 'capitalize' }}>
                {currentRun?.status || 'Idle'}
              </div>
            </div>
          </div>
        </div>

        <div style={{
          backgroundColor: '#1f2937',
          borderRadius: '12px',
          padding: '20px',
          border: '1px solid #374151'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ padding: '10px', backgroundColor: '#3b82f620', borderRadius: '8px' }}>
              <FileText size={20} style={{ color: '#3b82f6' }} />
            </div>
            <div>
              <div style={{ color: '#9ca3af', fontSize: '14px' }}>Evaluations</div>
              <div style={{ color: 'white', fontSize: '18px', fontWeight: 'bold' }}>
                {currentRun?.progress?.completed_tasks || 0} / {currentRun?.progress?.total_tasks || 0}
              </div>
            </div>
          </div>
        </div>

        <div style={{
          backgroundColor: '#1f2937',
          borderRadius: '12px',
          padding: '20px',
          border: '1px solid #374151'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ padding: '10px', backgroundColor: '#8b5cf620', borderRadius: '8px' }}>
              <Users size={20} style={{ color: '#8b5cf6' }} />
            </div>
            <div>
              <div style={{ color: '#9ca3af', fontSize: '14px' }}>Pairwise</div>
              <div style={{ color: 'white', fontSize: '18px', fontWeight: 'bold' }}>
                {currentRun?.pairwise_results?.rankings?.length || 0}
              </div>
            </div>
          </div>
        </div>

        <div style={{
          backgroundColor: '#1f2937',
          borderRadius: '12px',
          padding: '20px',
          border: '1px solid #374151'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ padding: '10px', backgroundColor: '#22c55e20', borderRadius: '8px' }}>
              <Timer size={20} style={{ color: '#22c55e' }} />
            </div>
            <div>
              <div style={{ color: '#9ca3af', fontSize: '14px' }}>Duration</div>
              <div style={{ color: 'white', fontSize: '18px', fontWeight: 'bold' }}>
                {currentRun?.started_at 
                  ? (currentRun.status === 'running' || currentRun.status === 'pending'
                      ? computeEndTime(currentRun.started_at, null, currentRun.duration_seconds)
                      : `${formatTime(currentRun.started_at)} - ${formatTime(currentRun.completed_at)}`)
                  : '--:--'}
              </div>
            </div>
          </div>
        </div>
        {/* FPF Stats Card */}
        <div style={{
          backgroundColor: '#1f2937',
          borderRadius: '12px',
          padding: '20px',
          border: '1px solid #374151',
          gridColumn: '1 / -1' // Span full width
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
            <div style={{ padding: '10px', backgroundColor: '#f59e0b20', borderRadius: '8px' }}>
              <Activity size={20} style={{ color: '#f59e0b' }} />
            </div>
            <div>
              <div style={{ color: '#9ca3af', fontSize: '14px' }}>FPF Live Stats</div>
              <div style={{ color: 'white', fontSize: '18px', fontWeight: 'bold' }}>
                {runningRunsCount !== null ? `${runningRunsCount} Active Runs` : 'Checking...'}
              </div>
            </div>
          </div>
          
          {currentRun?.fpf_stats?.current_call && (
            <div style={{ 
              backgroundColor: '#111827', 
              padding: '8px 12px', 
              borderRadius: '6px',
              fontSize: '13px',
              color: '#d1d5db',
              borderLeft: '3px solid #3b82f6'
            }}>
              <span style={{ color: '#60a5fa', fontWeight: 'bold' }}>Running:</span> {currentRun.fpf_stats.current_call}
            </div>
          )}
          
          {currentRun?.fpf_stats?.last_error && (
            <div style={{ 
              backgroundColor: '#111827', 
              padding: '8px 12px', 
              borderRadius: '6px',
              fontSize: '13px',
              color: '#fca5a5',
              marginTop: '8px',
              borderLeft: '3px solid #ef4444'
            }}>
              <span style={{ color: '#f87171', fontWeight: 'bold' }}>Last Error:</span> {currentRun.fpf_stats.last_error}
            </div>
          )}
        </div>      </div>

      {/* Results Content - Per-Source-Document Sections with Internal Tabs */}
      <div style={{
        backgroundColor: '#1f2937',
        borderRadius: '12px',
        padding: '20px',
        border: '1px solid #374151',
        minHeight: '400px'
      }}>
        {/* Multi-doc view: Show per-source-document sections */}
        {currentRun?.source_doc_results && Object.keys(currentRun.source_doc_results).length > 0 ? (
          <div>
            {/* Only show multi-doc info banner when there are 2+ documents */}
            {Object.keys(currentRun.source_doc_results).length > 1 && (
              <div style={{ 
                marginBottom: '16px', 
                padding: '12px 16px', 
                backgroundColor: '#111827', 
                borderRadius: '8px',
                borderLeft: '3px solid #3b82f6',
                display: 'flex',
                alignItems: 'center',
                gap: '12px'
              }}>
                <FileText size={18} style={{ color: '#60a5fa' }} />
                <span style={{ color: '#d1d5db', fontSize: '14px' }}>
                  <strong>Multi-Document Run:</strong> Each input document runs its own independent pipeline with separate evaluations.
                </span>
                <span style={{ 
                  marginLeft: 'auto', 
                  color: '#9ca3af', 
                  fontSize: '13px' 
                }}>
                  {Object.keys(currentRun.source_doc_results).length} source documents
                </span>
              </div>
            )}
            {Object.entries(currentRun.source_doc_results).map(([sourceDocId, sourceDocResult]) => (
              <SourceDocSection
                key={sourceDocId}
                sourceDocId={sourceDocId}
                sourceDocResult={sourceDocResult}
                currentRun={currentRun}
                defaultExpanded={Object.keys(currentRun.source_doc_results!).length <= 3}
                hideHeader={Object.keys(currentRun.source_doc_results!).length === 1}
              />
            ))}
          </div>
        ) : currentRun ? (
          /* ERROR: source_doc_results is missing - this should never happen */
          (() => {
            // Log error to console
            console.error('[FATAL] source_doc_results is missing or empty!', {
              runId: currentRun.id,
              status: currentRun.status,
              hasSourceDocResults: !!currentRun.source_doc_results,
              sourceDocResultsKeys: currentRun.source_doc_results ? Object.keys(currentRun.source_doc_results) : [],
              fullRun: currentRun
            });
            return (
              <div style={{
                padding: '40px',
                textAlign: 'center',
                backgroundColor: '#7f1d1d',
                borderRadius: '8px',
                border: '2px solid #dc2626'
              }}>
                <div style={{ color: '#fca5a5', fontSize: '24px', fontWeight: 'bold', marginBottom: '16px' }}>
                  ⚠️ FATAL ERROR: source_doc_results is missing
                </div>
                <div style={{ color: '#fecaca', fontSize: '14px', marginBottom: '12px' }}>
                  The API response does not contain source_doc_results. This is a backend bug.
                </div>
                <div style={{ 
                  backgroundColor: '#450a0a', 
                  padding: '16px', 
                  borderRadius: '4px', 
                  textAlign: 'left',
                  fontFamily: 'monospace',
                  fontSize: '12px',
                  color: '#fca5a5',
                  overflow: 'auto',
                  maxHeight: '300px'
                }}>
                  <div><strong>Run ID:</strong> {currentRun.id}</div>
                  <div><strong>Status:</strong> {currentRun.status}</div>
                  <div><strong>source_doc_results exists:</strong> {String(!!currentRun.source_doc_results)}</div>
                  <div><strong>source_doc_results keys:</strong> {currentRun.source_doc_results ? Object.keys(currentRun.source_doc_results).join(', ') || '(empty object)' : '(null/undefined)'}</div>
                  <div style={{ marginTop: '12px' }}><strong>Full currentRun object:</strong></div>
                  <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                    {JSON.stringify(currentRun, null, 2)}
                  </pre>
                </div>
              </div>
            );
          })()
        ) : (
          /* No run started yet - show placeholder */
          <div style={{ 
            padding: '40px', 
            textAlign: 'center', 
            color: '#9ca3af' 
          }}>
            <div style={{ fontSize: '18px', marginBottom: '8px' }}>No run in progress</div>
            <div style={{ fontSize: '14px' }}>Select a preset and click "Start Execution" to begin</div>
          </div>
        )}
      </div>

      {/* Log Viewer */}
      {currentRun?.id && (
        <div style={{ marginTop: '24px' }}>
          <LogViewer 
            runId={String(currentRun.id)} 
            isRunning={isRunning} 
            logLevel={currentRun?.log_level || fullPresetData?.general_config?.log_level || fullPresetData?.log_level || 'INFO'}
          />
        </div>
      )}
    </div>
  );
}
