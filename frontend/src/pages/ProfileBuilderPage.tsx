import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'
import { StreamingText } from '../components/ui/StreamingText'
import { useStreamingResponse } from '../hooks/useStreamingResponse'
import { Loader2, RefreshCw, Copy, CheckCircle, Star } from 'lucide-react'

const SECTIONS = ['Headline', 'About', 'Experience', 'Skills', 'Featured']

export function ProfileBuilderPage() {
  const qc = useQueryClient()
  const [activeSection, setActiveSection] = useState('Headline')
  const [copied, setCopied] = useState<string | null>(null)
  const { text: aboutText, isStreaming: aboutStreaming, stream: streamAbout, reset: resetAbout } = useStreamingResponse()

  const { data: profile, isLoading } = useQuery({
    queryKey: ['linkedin-profile'],
    queryFn: () => api.get('/api/profile/').then((r) => r.data),
  })

  const { data: score } = useQuery({
    queryKey: ['profile-score'],
    queryFn: () => api.get('/api/profile/score').then((r) => r.data),
    enabled: !!profile?.id,
  })

  const { mutate: generateProfile, isPending: generating } = useMutation({
    mutationFn: () => api.post('/api/profile/generate').then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['linkedin-profile'] }),
  })

  const { mutate: generateVariants, isPending: variantsLoading, data: variants } = useMutation({
    mutationFn: () => api.post('/api/profile/variants/headline').then((r) => r.data),
  })

  function copyToClipboard(text: string, key: string) {
    navigator.clipboard.writeText(text)
    setCopied(key)
    setTimeout(() => setCopied(null), 2000)
  }

  function handleStreamAbout() {
    resetAbout()
    streamAbout('/api/profile/stream/about')
  }

  if (isLoading) {
    return (
      <div className="p-8 flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-linkedin-blue animate-spin" />
      </div>
    )
  }

  if (!profile?.id) {
    return (
      <div className="p-8">
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center max-w-md mx-auto">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Generate Your LinkedIn Profile</h2>
          <p className="text-gray-500 text-sm mb-6">
            Our AI will create an optimized LinkedIn profile based on your onboarding answers.
          </p>
          <button
            onClick={() => generateProfile()}
            disabled={generating}
            className="bg-linkedin-blue text-white px-6 py-3 rounded-xl text-sm font-medium flex items-center gap-2 mx-auto hover:bg-linkedin-dark transition-colors disabled:opacity-50"
          >
            {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            {generating ? 'Generating...' : 'Generate Profile with AI'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Profile Builder</h1>
          <p className="text-gray-500 text-sm mt-1">AI-optimized LinkedIn profile sections</p>
        </div>
        {score && (
          <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-3">
            <Star className="w-5 h-5 text-yellow-400 fill-yellow-400" />
            <div>
              <div className="text-xl font-bold text-gray-900">{score.total_score}/100</div>
              <div className="text-xs text-gray-500">Profile Score</div>
            </div>
          </div>
        )}
      </div>

      <div className="flex gap-6">
        {/* Section Tabs */}
        <div className="w-48 shrink-0">
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            {SECTIONS.map((sec) => (
              <button
                key={sec}
                onClick={() => setActiveSection(sec)}
                className={`w-full text-left px-4 py-3 text-sm font-medium border-b border-gray-100 last:border-0 transition-colors ${
                  activeSection === sec
                    ? 'bg-linkedin-light text-linkedin-blue'
                    : 'text-gray-600 hover:bg-gray-50'
                }`}
              >
                {sec}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 bg-white rounded-xl border border-gray-200 p-6">
          {activeSection === 'Headline' && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-semibold text-gray-900">LinkedIn Headline</h2>
                <div className="flex gap-2">
                  <button
                    onClick={() => copyToClipboard(profile.headline || '', 'headline')}
                    className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded border border-gray-200"
                  >
                    {copied === 'headline' ? <CheckCircle className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
                    Copy
                  </button>
                  <button
                    onClick={() => generateVariants()}
                    disabled={variantsLoading}
                    className="flex items-center gap-1 text-xs text-linkedin-blue hover:text-linkedin-dark px-2 py-1 rounded border border-linkedin-blue"
                  >
                    {variantsLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                    Variants
                  </button>
                </div>
              </div>
              <div className="bg-linkedin-light rounded-lg p-4 mb-4">
                <p className="text-sm font-medium text-gray-900">{profile.headline}</p>
              </div>
              {variants?.variants && (
                <div className="space-y-3">
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">3 Variants</p>
                  {variants.variants.map((v: any, i: number) => (
                    <div key={i} className="border border-gray-200 rounded-lg p-3">
                      <p className="text-sm text-gray-900 mb-1">{v.headline}</p>
                      <p className="text-xs text-gray-400">{v.rationale}</p>
                      <button
                        onClick={() => copyToClipboard(v.headline, `variant-${i}`)}
                        className="text-xs text-linkedin-blue hover:underline mt-2"
                      >
                        {copied === `variant-${i}` ? '✓ Copied!' : 'Use this'}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeSection === 'About' && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-semibold text-gray-900">About Section</h2>
                <div className="flex gap-2">
                  {(profile.about_section || aboutText) && (
                    <button
                      onClick={() => copyToClipboard(aboutText || profile.about_section || '', 'about')}
                      className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded border border-gray-200"
                    >
                      {copied === 'about' ? <CheckCircle className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
                      Copy
                    </button>
                  )}
                  <button
                    onClick={handleStreamAbout}
                    disabled={aboutStreaming}
                    className="flex items-center gap-1 text-xs text-linkedin-blue hover:text-linkedin-dark px-2 py-1 rounded border border-linkedin-blue"
                  >
                    {aboutStreaming ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                    {profile.about_section ? 'Regenerate' : 'Generate'}
                  </button>
                </div>
              </div>
              <div className="bg-gray-50 rounded-lg p-4 min-h-48">
                <StreamingText
                  text={aboutText || profile.about_section || ''}
                  isStreaming={aboutStreaming}
                  className="text-sm text-gray-700 leading-relaxed"
                  placeholder="Click Generate to create your About section"
                />
              </div>
            </div>
          )}

          {activeSection === 'Skills' && (
            <div>
              <h2 className="font-semibold text-gray-900 mb-4">Skills (Top 40 — Algorithm-Optimized)</h2>
              <div className="flex flex-wrap gap-2">
                {profile.skills?.map((skill: string, i: number) => (
                  <span
                    key={i}
                    className="px-3 py-1 bg-linkedin-light text-linkedin-blue rounded-full text-sm font-medium"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}

          {activeSection === 'Experience' && (
            <div>
              <h2 className="font-semibold text-gray-900 mb-4">Experience</h2>
              <div className="space-y-4">
                {profile.experience?.map((exp: any, i: number) => (
                  <div key={i} className="border border-gray-200 rounded-lg p-4">
                    <div className="font-medium text-gray-900">{exp.title}</div>
                    <div className="text-sm text-gray-500">{exp.company} · {exp.duration}</div>
                    {exp.headline && <p className="text-sm text-linkedin-blue mt-2">{exp.headline}</p>}
                    <ul className="mt-2 space-y-1">
                      {exp.bullets?.map((b: string, j: number) => (
                        <li key={j} className="text-sm text-gray-600 flex gap-2">
                          <span className="text-linkedin-blue mt-0.5">•</span>
                          {b}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeSection === 'Featured' && (
            <div>
              <h2 className="font-semibold text-gray-900 mb-4">Featured Section</h2>
              <p className="text-sm text-gray-500">
                Add your best posts, articles, or media to the Featured section manually on LinkedIn.
                Recommended content to feature:
              </p>
              <ul className="mt-4 space-y-2 text-sm text-gray-600">
                <li className="flex gap-2"><span className="text-linkedin-blue">→</span> Your highest-performing LinkedIn post</li>
                <li className="flex gap-2"><span className="text-linkedin-blue">→</span> A case study or success story</li>
                <li className="flex gap-2"><span className="text-linkedin-blue">→</span> Your personal website or portfolio</li>
                <li className="flex gap-2"><span className="text-linkedin-blue">→</span> A media appearance or press mention</li>
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
