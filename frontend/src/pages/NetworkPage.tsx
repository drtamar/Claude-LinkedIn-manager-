import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'
import { StreamingText } from '../components/ui/StreamingText'
import { useStreamingResponse } from '../hooks/useStreamingResponse'
import { Loader2, Users } from 'lucide-react'

const TABS = ['ICP Builder', 'Connection Queue', 'Sequences']

export function NetworkPage() {
  const [tab, setTab] = useState('ICP Builder')
  const [newUrl, setNewUrl] = useState('')
  const [newNote, setNewNote] = useState('')
  const [prospectName, setProspectName] = useState('')
  const [prospectTitle, setProspectTitle] = useState('')
  const [prospectCompany, setProspectCompany] = useState('')
  const qc = useQueryClient()

  const { text: icpText, isStreaming: icpStreaming, stream: streamICP, reset: resetICP } = useStreamingResponse()
  const { text: seqText, isStreaming: seqStreaming, stream: streamSeq, reset: resetSeq } = useStreamingResponse()

  const { data: connections } = useQuery({
    queryKey: ['connections'],
    queryFn: () => api.get('/api/network/connections').then((r) => r.data),
    enabled: tab === 'Connection Queue',
  })

  const { data: sequences } = useQuery({
    queryKey: ['sequences'],
    queryFn: () => api.get('/api/network/sequences').then((r) => r.data),
    enabled: tab === 'Sequences',
  })

  const { mutate: generateNote, isPending: noteLoading } = useMutation({
    mutationFn: () => api.post('/api/network/connections/generate-note', {
      prospect_name: prospectName,
      prospect_title: prospectTitle,
      prospect_company: prospectCompany,
    }).then((r) => r.data),
    onSuccess: (data) => setNewNote(data.note),
  })

  const { mutate: addConnection, isPending: addingConn } = useMutation({
    mutationFn: () => api.post('/api/network/connections', {
      linkedin_profile_url: newUrl,
      prospect_name: prospectName,
      prospect_title: prospectTitle,
      prospect_company: prospectCompany,
      connection_note: newNote,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['connections'] })
      setNewUrl('')
      setNewNote('')
      setProspectName('')
      setProspectTitle('')
      setProspectCompany('')
    },
  })

  const statusColors: Record<string, string> = {
    queued: 'bg-gray-100 text-gray-500',
    sent: 'bg-blue-100 text-blue-600',
    accepted: 'bg-green-100 text-green-600',
    declined: 'bg-red-100 text-red-500',
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Network Manager</h1>
        <p className="text-gray-500 text-sm mt-1">Build strategic connections with the right people</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 mb-6 w-fit">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              tab === t ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* ICP Builder */}
      {tab === 'ICP Builder' && (
        <div className="grid grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-900">Ideal Connection Profile</h2>
              <button
                onClick={() => { resetICP(); streamICP('/api/network/icp/generate') }}
                disabled={icpStreaming}
                className="flex items-center gap-1 text-xs bg-linkedin-blue text-white px-3 py-1.5 rounded-lg hover:bg-linkedin-dark transition-colors"
              >
                {icpStreaming ? <Loader2 className="w-3 h-3 animate-spin" /> : <Users className="w-3 h-3" />}
                Generate with AI
              </button>
            </div>
            <div className="bg-gray-50 rounded-lg p-4 min-h-64">
              <StreamingText
                text={icpText}
                isStreaming={icpStreaming}
                className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap"
                placeholder="Click Generate to build your Ideal Connection Profile based on your goals"
              />
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="font-semibold text-gray-900 mb-4">LinkedIn Algorithm: Connection Strategy</h2>
            <div className="space-y-3 text-sm text-gray-600">
              <div className="bg-linkedin-light rounded-lg p-3">
                <p className="font-medium text-linkedin-blue mb-1">Golden Rule</p>
                <p>Connect with people 1-2 degrees away from decision-makers. They have influence without gatekeepers.</p>
              </div>
              <div className="bg-yellow-50 rounded-lg p-3">
                <p className="font-medium text-yellow-700 mb-1">Rate Limit Warning</p>
                <p>Max 15 connection requests/day to avoid LinkedIn restrictions. Quality beats quantity.</p>
              </div>
              <div className="bg-green-50 rounded-lg p-3">
                <p className="font-medium text-green-700 mb-1">Acceptance Rate Hack</p>
                <p>Connection notes under 300 chars with a specific reference to their work get 3x more accepts.</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="font-medium text-gray-700 mb-1">First Message Timing</p>
                <p>Send your first follow-up message within 48-72 hours of acceptance for best response rates.</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Connection Queue */}
      {tab === 'Connection Queue' && (
        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-1 bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="font-semibold text-gray-900 mb-4">Add Prospect</h2>
            <div className="space-y-3">
              <input
                type="url"
                value={newUrl}
                onChange={(e) => setNewUrl(e.target.value)}
                placeholder="LinkedIn profile URL"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-linkedin-blue"
              />
              <input
                type="text"
                value={prospectName}
                onChange={(e) => setProspectName(e.target.value)}
                placeholder="Name"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-linkedin-blue"
              />
              <input
                type="text"
                value={prospectTitle}
                onChange={(e) => setProspectTitle(e.target.value)}
                placeholder="Job title"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-linkedin-blue"
              />
              <input
                type="text"
                value={prospectCompany}
                onChange={(e) => setProspectCompany(e.target.value)}
                placeholder="Company"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-linkedin-blue"
              />
              <button
                onClick={() => generateNote()}
                disabled={!prospectName || noteLoading}
                className="w-full border border-linkedin-blue text-linkedin-blue rounded-lg py-2 text-sm font-medium hover:bg-linkedin-light transition-colors disabled:opacity-50"
              >
                {noteLoading ? 'Generating...' : '✨ AI Generate Note'}
              </button>
              <textarea
                value={newNote}
                onChange={(e) => setNewNote(e.target.value)}
                placeholder="Connection note (max 300 chars)"
                maxLength={300}
                rows={3}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-linkedin-blue resize-none"
              />
              <div className="text-right text-xs text-gray-400">{newNote.length}/300</div>
              <button
                onClick={() => addConnection()}
                disabled={!newUrl || addingConn}
                className="w-full bg-linkedin-blue text-white rounded-lg py-2 text-sm font-medium hover:bg-linkedin-dark transition-colors disabled:opacity-50"
              >
                {addingConn ? 'Adding...' : 'Add to Queue'}
              </button>
            </div>
          </div>

          <div className="col-span-2 bg-white rounded-xl border border-gray-200">
            <div className="p-4 border-b border-gray-100 flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">Connection Queue</h2>
              <span className="text-xs text-gray-400">{connections?.length || 0} prospects</span>
            </div>
            <div className="divide-y divide-gray-50 max-h-96 overflow-y-auto">
              {connections?.length === 0 && (
                <p className="p-6 text-center text-gray-400 text-sm">Queue is empty. Add prospects above.</p>
              )}
              {connections?.map((c: any) => (
                <div key={c.id} className="p-4 flex items-center gap-4">
                  <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-xs font-medium text-gray-600">
                    {c.prospect_name?.charAt(0) || '?'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900">{c.prospect_name || 'Unknown'}</p>
                    <p className="text-xs text-gray-400 truncate">{c.prospect_title} · {c.prospect_company}</p>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusColors[c.status] || 'bg-gray-100 text-gray-500'}`}>
                    {c.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Sequences */}
      {tab === 'Sequences' && (
        <div className="grid grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-900">Generate Outreach Sequence</h2>
            </div>
            <div className="space-y-3 mb-4">
              <input
                type="text"
                placeholder="ICP name (e.g., 'Series A Founders')"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-linkedin-blue"
                id="icp-name-input"
              />
              <textarea
                placeholder="Describe the ICP (their role, company, pain points...)"
                rows={3}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-linkedin-blue resize-none"
                id="icp-desc-input"
              />
              <button
                onClick={() => {
                  const nameEl = document.getElementById('icp-name-input') as HTMLInputElement
                  const descEl = document.getElementById('icp-desc-input') as HTMLTextAreaElement
                  resetSeq()
                  streamSeq('/api/network/sequences/generate', {
                    icp_name: nameEl.value,
                    icp_description: descEl.value,
                  })
                }}
                disabled={seqStreaming}
                className="w-full bg-linkedin-blue text-white rounded-lg py-2 text-sm font-medium hover:bg-linkedin-dark transition-colors"
              >
                {seqStreaming ? 'Generating...' : '🔥 Generate 3-Step Sequence'}
              </button>
            </div>
            <div className="bg-gray-50 rounded-lg p-4 min-h-48">
              <StreamingText
                text={seqText}
                isStreaming={seqStreaming}
                className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap"
                placeholder="Your outreach sequence will appear here..."
              />
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200">
            <div className="p-4 border-b border-gray-100">
              <h2 className="font-semibold text-gray-900">Saved Sequences</h2>
            </div>
            <div className="divide-y divide-gray-50">
              {sequences?.length === 0 && (
                <p className="p-6 text-center text-gray-400 text-sm">No sequences yet. Generate one.</p>
              )}
              {sequences?.map((s: any) => (
                <div key={s.id} className="p-4">
                  <p className="font-medium text-sm text-gray-900 mb-1">{s.name}</p>
                  <div className="space-y-1">
                    <p className="text-xs text-gray-500">Step 1: {s.step_1_message?.slice(0, 80)}...</p>
                    <p className="text-xs text-gray-400">Step 2 (day {s.step_2_delay_days}): {s.step_2_message?.slice(0, 60)}...</p>
                    <p className="text-xs text-gray-400">Step 3 (day {s.step_3_delay_days}): {s.step_3_message?.slice(0, 60)}...</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
