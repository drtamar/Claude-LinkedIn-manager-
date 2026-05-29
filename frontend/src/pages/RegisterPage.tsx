import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import api from '../lib/api'
import { Network as Linkedin } from 'lucide-react'

const USER_TYPES = [
  { value: 'founder', label: '🚀 Founder / Entrepreneur' },
  { value: 'job_seeker', label: '🎯 Job Seeker' },
  { value: 'sales', label: '💼 Sales / BD Professional' },
  { value: 'creator', label: '✍️ Content Creator' },
]

export function RegisterPage() {
  const [form, setForm] = useState({ email: '', password: '', display_name: '', user_type: 'founder' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const login = useAuthStore((s) => s.login)
  const navigate = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const { data } = await api.post('/api/auth/register', form)
      login(data.access_token, data.user_id, data.display_name, data.user_type)
      navigate('/onboarding')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-linkedin-blue to-linkedin-dark">
      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 bg-linkedin-blue rounded-xl flex items-center justify-center mb-4">
            <Linkedin className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Get Started</h1>
          <p className="text-gray-500 text-sm mt-1">Create your LinkedIn Manager account</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red-50 text-red-600 text-sm p-3 rounded-lg">{error}</div>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
            <input
              type="text"
              value={form.display_name}
              onChange={(e) => setForm({ ...form, display_name: e.target.value })}
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-linkedin-blue"
              placeholder="Alex Johnson"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-linkedin-blue"
              placeholder="you@company.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required
              minLength={8}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-linkedin-blue"
              placeholder="Min 8 characters"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">I am a...</label>
            <div className="grid grid-cols-2 gap-2">
              {USER_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => setForm({ ...form, user_type: t.value })}
                  className={`text-left px-3 py-2 rounded-lg border text-xs font-medium transition-colors ${
                    form.user_type === t.value
                      ? 'border-linkedin-blue bg-linkedin-light text-linkedin-blue'
                      : 'border-gray-200 text-gray-600 hover:border-gray-300'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-linkedin-blue text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-linkedin-dark transition-colors disabled:opacity-50"
          >
            {loading ? 'Creating account...' : 'Create account & start setup'}
          </button>
        </form>

        <p className="text-center text-sm text-gray-500 mt-6">
          Already have an account?{' '}
          <Link to="/login" className="text-linkedin-blue hover:underline font-medium">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
