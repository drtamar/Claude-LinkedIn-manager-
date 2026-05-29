import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts'
import { TrendingUp } from 'lucide-react'

export function AnalyticsPage() {
  const { data: ssi } = useQuery({
    queryKey: ['ssi'],
    queryFn: () => api.get('/api/analytics/ssi').then((r) => r.data),
  })

  const { data: postMetrics } = useQuery({
    queryKey: ['post-metrics'],
    queryFn: () => api.get('/api/analytics/posts?days=30').then((r) => r.data),
  })

  const { data: insights } = useQuery({
    queryKey: ['insights'],
    queryFn: () => api.get('/api/analytics/insights').then((r) => r.data),
  })

  const { data: heatmap } = useQuery({
    queryKey: ['heatmap'],
    queryFn: () => api.get('/api/analytics/heatmap').then((r) => r.data),
  })

  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
  const hours = Array.from({ length: 24 }, (_, i) => `${i}h`)

  const heatmapGrid = Array.from({ length: 7 }, (_, d) =>
    Array.from({ length: 24 }, (_, h) => {
      const cell = heatmap?.find((c: any) => c.day === d && c.hour === h)
      return cell?.avg_engagement || 0
    })
  )

  const maxEngagement = Math.max(...(heatmapGrid.flat().filter(Boolean)), 0.001)

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
        <p className="text-gray-500 text-sm mt-1">LinkedIn performance insights and trends</p>
      </div>

      <div className="grid grid-cols-2 gap-6 mb-6">
        {/* SSI Score Trend */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-4 h-4 text-linkedin-blue" />
            <h2 className="font-semibold text-gray-900">SSI Score Trend</h2>
          </div>
          {ssi?.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={ssi}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                <Tooltip />
                <Line type="monotone" dataKey="total" stroke="#0077B5" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-48 flex items-center justify-center text-gray-400 text-sm">
              Connect LinkedIn to track SSI score
            </div>
          )}
        </div>

        {/* Post Impressions */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold text-gray-900 mb-4">Post Impressions (30 days)</h2>
          {postMetrics?.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={postMetrics.slice(0, 10)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="title" tick={{ fontSize: 8 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Bar dataKey="impressions" fill="#0077B5" radius={4} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-48 flex items-center justify-center text-gray-400 text-sm">
              Publish posts to see analytics
            </div>
          )}
        </div>
      </div>

      {/* Engagement Heatmap */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <h2 className="font-semibold text-gray-900 mb-4">Engagement Heatmap (Best Times to Post)</h2>
        {heatmap?.length > 0 ? (
          <div className="overflow-x-auto">
            <div className="flex gap-1">
              <div className="flex flex-col gap-1 mr-2">
                <div className="h-4 w-8 text-xs text-gray-400"></div>
                {days.map((d) => (
                  <div key={d} className="h-4 w-8 text-xs text-gray-500 flex items-center">{d}</div>
                ))}
              </div>
              <div className="flex-1">
                <div className="flex gap-1 mb-1">
                  {hours.map((h) => (
                    <div key={h} className="w-4 text-xs text-gray-400 text-center" style={{ fontSize: 8 }}>{h}</div>
                  ))}
                </div>
                {heatmapGrid.map((row, d) => (
                  <div key={d} className="flex gap-1 mb-1">
                    {row.map((val, h) => (
                      <div
                        key={h}
                        className="w-4 h-4 rounded-sm"
                        style={{
                          backgroundColor: val > 0
                            ? `rgba(0, 119, 181, ${Math.min(val / maxEngagement, 1) * 0.9 + 0.1})`
                            : '#f3f4f6'
                        }}
                        title={`${days[d]} ${h}:00 — ${(val * 100).toFixed(1)}% engagement`}
                      />
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <p className="text-gray-400 text-sm text-center py-8">Post and track data to see optimal times</p>
        )}
      </div>

      {/* AI Insights */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-4">AI-Powered Insights</h2>
        <div className="grid grid-cols-3 gap-4">
          {insights?.map((insight: any, i: number) => (
            <div key={i} className="bg-linkedin-light rounded-lg p-4">
              <div className="text-xs font-medium text-linkedin-blue uppercase mb-2">{insight.type}</div>
              <p className="text-sm text-gray-700">
                {typeof insight.data === 'object' ? insight.data.insight || insight.insight : insight.insight}
              </p>
              {insight.confidence && (
                <div className="mt-2 flex items-center gap-1">
                  <div className="h-1 flex-1 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-linkedin-blue rounded-full"
                      style={{ width: `${insight.confidence * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-400">{Math.round(insight.confidence * 100)}%</span>
                </div>
              )}
            </div>
          ))}
          {(!insights || insights.length === 0) && (
            <p className="col-span-3 text-gray-400 text-sm text-center py-8">
              Insights will be generated after you publish and track posts
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
