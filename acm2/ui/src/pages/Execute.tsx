import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { 
  Play, Square, AlertCircle, Activity, Clock,
  FileText, Users, ChevronDown, Calendar, Target, Timer,
  XCircle, CheckCircle, Loader2
} from 'lucide-react';
import LogViewer from '../components/execution/LogViewer';
import type { Run } from '../api';
import { runsApi } from '../api';
import { formatTime, computeEndTime } from './execute/utils';
import EvaluationTab from './execute/EvaluationTab';
import PairwiseTab from './execute/PairwiseTab';
import TimelineTab from './execute/TimelineTab';
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
  const [runningRunsCount, setRunningRunsCount] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<'evaluation' | 'pairwise' | 'timeline'>('evaluation');
  const [error, setError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const handleRunUpdate = useCallback((updatedRun: Run) => {
    if (!updatedRun?.id) return;
    setCurrentRun(prev => {
      const merged: any = { ...(prev || {}), ...updatedRun };
      if (!updatedRun.fpf_stats && prev?.fpf_stats) {
        merged.fpf_stats = prev.fpf_stats;
      }
      return merged;
    });
    // Update running state based on status
    if (updatedRun.status === 'running' || updatedRun.status === 'pending') {
      setIsRunning(true);
    } else if (updatedRun.status === 'completed' || updatedRun.status === 'failed' || updatedRun.status === 'cancelled') {
      setIsRunning(false);
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
          setCurrentRun(prev => {
            const merged: any = { ...(prev || {}), ...run };
            if (!run.fpf_stats && prev?.fpf_stats) {
              merged.fpf_stats = prev.fpf_stats;
            }
            return merged;
          });
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

      {/* Tabs */}
      <div style={{ 
        display: 'flex', 
        gap: '4px', 
        marginBottom: '24px',
        backgroundColor: '#1f2937',
        padding: '4px',
        borderRadius: '8px',
        width: 'fit-content'
      }}>
        {[
          { id: 'evaluation' as const, label: 'Single Evaluation', icon: Target },
          { id: 'pairwise' as const, label: 'Pairwise Comparison', icon: Users },
          { id: 'timeline' as const, label: 'Timeline & Details', icon: Calendar }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 16px',
              backgroundColor: activeTab === tab.id ? '#374151' : 'transparent',
              border: 'none',
              borderRadius: '6px',
              color: activeTab === tab.id ? 'white' : '#9ca3af',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: activeTab === tab.id ? 500 : 400
            }}
          >
            <tab.icon size={16} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div style={{
        backgroundColor: '#1f2937',
        borderRadius: '12px',
        padding: '20px',
        border: '1px solid #374151',
        minHeight: '400px'
      }}>
        {activeTab === 'evaluation' && (
          <EvaluationTab 
            currentRun={currentRun}
            execStatus={{ id: 0, status: currentRun?.status || 'pending' }}
          />
        )}

        {activeTab === 'pairwise' && (
          <PairwiseTab currentRun={currentRun} />
        )}

        {activeTab === 'timeline' && (
          <TimelineTab currentRun={currentRun} />
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
