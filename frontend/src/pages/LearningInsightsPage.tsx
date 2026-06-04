import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'
import { BrainCircuit, Loader2, ChevronDown, ChevronUp, Play } from 'lucide-react'

export function LearningInsightsPage() {
  const qc = useQueryClient()
  const [expandedCycle, setExpandedCycle] = useState<number | null>(null)

  const { data: cycles } = useQuery({
    queryKey: ['learning-cycles'],
    queryFn: () => api.get('/api/learning/cycles').then((r) => r.data),
  })

  const { data: prompts } = useQuery({
    queryKey: ['prompt-versions'],
    queryFn: () => api.get('/api/learning/prompts').then((r) => r.data),
  })

  const { mutate: runCycle, isPending: running } = useMutation({
    mutationFn: () => api.post('/api/learning/cycles/run').then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['learning-cycles'] }),
  })

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <BrainCircuit className="w-6 h-6 text-linkedin-blue" />
            AI Learning & Optimization
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            The system analyzes your content performance and automatically improves its prompts weekly
          </p>
        </div>
        <button
          onClick={() => runCycle()}
          disabled={running}
          className="flex items-center gap-2 bg-linkedin-blue text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-linkedin-dark transition-colors disabled:opacity-50"
        >
          {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          {running ? 'Running cycle...' : 'Run Learning Cycle Now'}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Learning Cycles */}
        <div className="bg-white rounded-xl border border-gray-200">
          <div className="p-4 border-b border-gray-100">
            <h2 className="font-semibold text-gray-900">Learning Cycle History</h2>
          </div>
          <div className="divide-y divide-gray-50">
            {cycles?.length === 0 && (
              <p className="p-6 text-center text-gray-400 text-sm">
                No cycles yet. Run a cycle after you have published posts.
              </p>
            )}
            {cycles?.map((cycle: any) => (
              <div key={cycle.id} className="p-4">
                <button
                  onClick={() => setExpandedCycle(expandedCycle === cycle.id ? null : cycle.id)}
                  className="w-full flex items-center justify-between"
                >
                  <div className="text-left">
                    <p className="text-sm font-medium text-gray-900">
                      {new Date(cycle.cycle_date).toLocaleDateString()} — {cycle.improvements_made} improvements
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        cycle.status === 'completed' ? 'bg-green-100 text-green-600' :
                        cycle.status === 'failed' ? 'bg-red-100 text-red-500' :
                        'bg-blue-100 text-blue-600'
                      }`}>
                        {cycle.status}
                      </span>
                      {cycle.modules_analyzed?.length > 0 && (
                        <span className="text-xs text-gray-400">
                          Modules: {cycle.modules_analyzed.join(', ')}
                        </span>
                      )}
                    </div>
                  </div>
                  {expandedCycle === cycle.id ? (
                    <ChevronUp className="w-4 h-4 text-gray-400" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-gray-400" />
                  )}
                </button>
                {expandedCycle === cycle.id && (
                  <div className="mt-3 bg-gray-50 rounded-lg p-3">
                    <pre className="text-xs text-gray-600 whitespace-pre-wrap overflow-x-auto">
                      {cycle.full_report || 'No report available'}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Prompt Versions */}
        <div className="bg-white rounded-xl border border-gray-200">
          <div className="p-4 border-b border-gray-100">
            <h2 className="font-semibold text-gray-900">Active Prompt Versions</h2>
          </div>
          <div className="divide-y divide-gray-50">
            {prompts?.length === 0 && (
              <p className="p-6 text-center text-gray-400 text-sm">No prompt versions loaded yet.</p>
            )}
            {prompts?.map((p: any) => (
              <div key={p.module} className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-900">{p.module}</p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      v{p.version} · {p.model} · {p.sample_count} posts
                    </p>
                  </div>
                  <div className="text-right">
                    {p.performance_score > 0 && (
                      <p className="text-sm font-medium text-linkedin-blue">
                        {(p.performance_score * 100).toFixed(1)}%
                      </p>
                    )}
                    <p className="text-xs text-gray-400">
                      {p.created_at ? new Date(p.created_at).toLocaleDateString() : ''}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* How Self-Learning Works */}
        <div className="col-span-2 bg-gradient-to-r from-linkedin-blue to-linkedin-dark rounded-xl p-6 text-white">
          <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
            <BrainCircuit className="w-5 h-5" />
            How the Self-Learning System Works
          </h2>
          <div className="grid grid-cols-4 gap-4">
            {[
              { step: '1', title: 'Collect', desc: 'Every post you publish is tracked with its LinkedIn performance metrics (impressions, engagement, comments)' },
              { step: '2', title: 'Analyze', desc: 'Weekly, Claude analyzes which prompt templates produced high-performing vs low-performing content' },
              { step: '3', title: 'Refine', desc: 'Claude rewrites the underperforming prompts to incorporate patterns from your top-performing content' },
              { step: '4', title: 'Improve', desc: 'All future AI generations use the refined prompts. Your outputs get better the more you use it.' },
            ].map(({ step, title, desc }) => (
              <div key={step} className="bg-white/10 rounded-lg p-4">
                <div className="w-6 h-6 bg-white/20 rounded-full flex items-center justify-center text-xs font-bold mb-2">
                  {step}
                </div>
                <p className="font-medium text-sm mb-1">{title}</p>
                <p className="text-xs text-white/75 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
