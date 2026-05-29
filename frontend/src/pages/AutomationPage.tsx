import { useQuery, useMutation } from '@tanstack/react-query'
import api from '../lib/api'
import { Zap, Link2, CheckCircle, XCircle, Loader2, AlertTriangle, RefreshCw } from 'lucide-react'

export function AutomationPage() {
  const { data: status, refetch: refetchStatus } = useQuery({
    queryKey: ['automation-status'],
    queryFn: () => api.get('/api/automation/status').then((r) => r.data),
    refetchInterval: 30000,
  })

  const { data: linkedinStatus, refetch: refetchLinkedIn } = useQuery({
    queryKey: ['linkedin-status'],
    queryFn: () => api.get('/api/automation/linkedin/status').then((r) => r.data),
  })

  const { data: jobs } = useQuery({
    queryKey: ['automation-jobs'],
    queryFn: () => api.get('/api/automation/jobs').then((r) => r.data),
    refetchInterval: 10000,
  })

  const { mutate: disconnect } = useMutation({
    mutationFn: () => api.delete('/api/automation/linkedin/disconnect'),
    onSuccess: () => { refetchLinkedIn(); refetchStatus() },
  })

  const { mutate: triggerScrape } = useMutation({
    mutationFn: () => api.post('/api/analytics/refresh'),
  })

  const jobStatusColors: Record<string, string> = {
    queued: 'bg-gray-100 text-gray-500',
    running: 'bg-blue-100 text-blue-600',
    completed: 'bg-green-100 text-green-600',
    failed: 'bg-red-100 text-red-500',
    cancelled: 'bg-gray-100 text-gray-400',
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Automation Center</h1>
        <p className="text-gray-500 text-sm mt-1">Manage LinkedIn automation and scheduling</p>
      </div>

      <div className="grid grid-cols-3 gap-6 mb-6">
        {/* LinkedIn Connection Status */}
        <div className="col-span-1 bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Link2 className="w-4 h-4 text-linkedin-blue" />
            LinkedIn Session
          </h2>
          {linkedinStatus?.connected ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-green-600">
                <CheckCircle className="w-5 h-5" />
                <span className="text-sm font-medium">Connected</span>
              </div>
              <p className="text-xs text-gray-400">Session is active and ready for automation.</p>
              <button
                onClick={() => disconnect()}
                className="w-full border border-red-200 text-red-500 rounded-lg py-2 text-xs font-medium hover:bg-red-50 transition-colors"
              >
                Disconnect Session
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-gray-400">
                <XCircle className="w-5 h-5" />
                <span className="text-sm">Not connected</span>
              </div>
              <p className="text-xs text-gray-500 leading-relaxed">
                To connect LinkedIn, you'll need to provide your session cookies.
                Use a browser extension like "Cookie-Editor" to export your LinkedIn cookies and paste them via the API.
              </p>
              <div className="bg-yellow-50 rounded-lg p-3">
                <p className="text-xs text-yellow-700">
                  <AlertTriangle className="w-3 h-3 inline mr-1" />
                  Use automation responsibly. Respect LinkedIn's Terms of Service.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Daily Limits */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold text-gray-900 mb-4">Daily Limits</h2>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">Connections Sent</span>
                <span className="font-medium text-gray-900">
                  {status?.daily_limits?.connections_sent || 0}/{status?.daily_limits?.connections_limit || 15}
                </span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-linkedin-blue rounded-full transition-all"
                  style={{ width: `${((status?.daily_limits?.connections_sent || 0) / (status?.daily_limits?.connections_limit || 15)) * 100}%` }}
                />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">Posts Published</span>
                <span className="font-medium text-gray-900">
                  {status?.daily_limits?.posts_published || 0}/{status?.daily_limits?.posts_limit || 3}
                </span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-purple-500 rounded-full transition-all"
                  style={{ width: `${((status?.daily_limits?.posts_published || 0) / (status?.daily_limits?.posts_limit || 3)) * 100}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold text-gray-900 mb-4">Actions</h2>
          <div className="space-y-2">
            <button
              onClick={() => triggerScrape()}
              className="w-full flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <RefreshCw className="w-4 h-4 text-linkedin-blue" />
              Scrape Analytics Now
            </button>
          </div>

          <div className="mt-4 bg-blue-50 rounded-lg p-3">
            <p className="text-xs text-blue-700 font-medium mb-1">Safety Mode Active</p>
            <p className="text-xs text-blue-600">
              All actions use human-like delays and respect daily limits to protect your account.
            </p>
          </div>
        </div>
      </div>

      {/* Job Queue */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">Automation Job Queue</h2>
          <span className="text-xs text-gray-400">{jobs?.length || 0} recent jobs</span>
        </div>
        <div className="divide-y divide-gray-50 max-h-96 overflow-y-auto">
          {jobs?.length === 0 && (
            <p className="p-6 text-center text-gray-400 text-sm">No jobs yet. Use Content Studio to publish posts.</p>
          )}
          {jobs?.map((job: any) => (
            <div key={job.id} className="p-4 flex items-center gap-4">
              <div className="shrink-0">
                {job.status === 'running' ? (
                  <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
                ) : job.status === 'completed' ? (
                  <CheckCircle className="w-4 h-4 text-green-500" />
                ) : job.status === 'failed' ? (
                  <XCircle className="w-4 h-4 text-red-500" />
                ) : (
                  <Zap className="w-4 h-4 text-gray-400" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900">{job.job_type.replace('_', ' ').toUpperCase()}</p>
                {job.error_message && (
                  <p className="text-xs text-red-500 truncate">{job.error_message}</p>
                )}
              </div>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${jobStatusColors[job.status] || 'bg-gray-100 text-gray-500'}`}>
                {job.status}
              </span>
              <span className="text-xs text-gray-400 shrink-0">
                {job.queued_at ? new Date(job.queued_at).toLocaleTimeString() : ''}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
