import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import { useAuthStore } from '../stores/authStore'
import { useNavigate } from 'react-router-dom'
import { TrendingUp, Users, BarChart2, FileText, Zap, Plus, ExternalLink } from 'lucide-react'
import { formatNumber } from '../lib/utils'

export function DashboardPage() {
  const { displayName } = useAuthStore()
  const navigate = useNavigate()

  const { data: stats } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.get('/api/analytics/dashboard').then((r) => r.data),
  })

  const { data: recentPosts } = useQuery({
    queryKey: ['posts', 'recent'],
    queryFn: () => api.get('/api/content/posts?limit=5').then((r) => r.data),
  })

  const { data: insights } = useQuery({
    queryKey: ['insights'],
    queryFn: () => api.get('/api/analytics/insights').then((r) => r.data),
  })

  const kpis = [
    {
      label: 'SSI Score',
      value: stats?.ssi_score || 0,
      suffix: '/100',
      icon: TrendingUp,
      color: 'text-blue-600',
      bg: 'bg-blue-50',
    },
    {
      label: 'Posts This Month',
      value: stats?.posts_this_month || 0,
      icon: FileText,
      color: 'text-purple-600',
      bg: 'bg-purple-50',
    },
    {
      label: 'New Connections',
      value: stats?.new_connections || 0,
      icon: Users,
      color: 'text-green-600',
      bg: 'bg-green-50',
    },
    {
      label: 'Avg Engagement',
      value: stats?.avg_engagement_rate || 0,
      suffix: '%',
      icon: BarChart2,
      color: 'text-orange-600',
      bg: 'bg-orange-50',
    },
  ]

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          Good morning, {displayName?.split(' ')[0]} 👋
        </h1>
        <p className="text-gray-500 text-sm mt-1">Here's your LinkedIn performance overview</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-6 mb-8">
        {kpis.map((kpi) => (
          <div key={kpi.label} className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm text-gray-500">{kpi.label}</span>
              <div className={`w-9 h-9 ${kpi.bg} rounded-lg flex items-center justify-center`}>
                <kpi.icon className={`w-4 h-4 ${kpi.color}`} />
              </div>
            </div>
            <div className="text-3xl font-bold text-gray-900">
              {formatNumber(kpi.value)}{kpi.suffix || ''}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Recent Posts */}
        <div className="col-span-2 bg-white rounded-xl border border-gray-200">
          <div className="p-6 border-b border-gray-100 flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">Recent Posts</h2>
            <button
              onClick={() => navigate('/content')}
              className="text-xs text-linkedin-blue hover:underline flex items-center gap-1"
            >
              View all <ExternalLink className="w-3 h-3" />
            </button>
          </div>
          <div className="divide-y divide-gray-50">
            {recentPosts?.length === 0 && (
              <div className="p-6 text-center text-gray-400 text-sm">
                No posts yet.{' '}
                <button onClick={() => navigate('/content')} className="text-linkedin-blue hover:underline">
                  Create your first post
                </button>
              </div>
            )}
            {recentPosts?.map((post: any) => (
              <div key={post.id} className="p-4 flex items-center gap-4">
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-900 truncate">{post.content}</p>
                  <div className="flex items-center gap-3 mt-1">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      post.status === 'published' ? 'bg-green-100 text-green-600' :
                      post.status === 'scheduled' ? 'bg-blue-100 text-blue-600' :
                      'bg-gray-100 text-gray-500'
                    }`}>
                      {post.status}
                    </span>
                    {post.ai_score > 0 && (
                      <span className="text-xs text-gray-400">Score: {post.ai_score}/100</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Quick Actions + Insights */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="font-semibold text-gray-900 mb-4">Quick Actions</h2>
            <div className="space-y-2">
              {[
                { label: 'Generate Post', icon: Plus, to: '/content' },
                { label: 'Add Connection', icon: Users, to: '/network' },
                { label: 'View Analytics', icon: BarChart2, to: '/analytics' },
                { label: 'Automation Status', icon: Zap, to: '/automation' },
              ].map(({ label, icon: Icon, to }) => (
                <button
                  key={label}
                  onClick={() => navigate(to)}
                  className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-700 hover:bg-gray-50 transition-colors text-left"
                >
                  <Icon className="w-4 h-4 text-linkedin-blue" />
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="font-semibold text-gray-900 mb-4">AI Insights</h2>
            <div className="space-y-3">
              {insights?.slice(0, 3).map((insight: any, i: number) => (
                <div key={i} className="bg-linkedin-light rounded-lg p-3">
                  <p className="text-xs text-gray-700">
                    {typeof insight.data === 'object' ? insight.data.insight || insight.insight : insight.insight}
                  </p>
                </div>
              ))}
              {(!insights || insights.length === 0) && (
                <p className="text-xs text-gray-400">Insights will appear after you publish posts.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
