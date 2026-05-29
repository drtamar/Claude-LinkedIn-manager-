import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import api from '../lib/api'
import { StreamingText } from '../components/ui/StreamingText'
import { useStreamingResponse } from '../hooks/useStreamingResponse'
import { Loader2, Zap, Hash, Copy, CheckCircle, Star } from 'lucide-react'

const POST_TYPES = ['text', 'carousel', 'poll', 'article', 'document']

export function ContentStudioPage() {
  const [topic, setTopic] = useState('')
  const [postType, setPostType] = useState('text')
  const [selectedHook, setSelectedHook] = useState<any>(null)
  const [hooks, setHooks] = useState<any[]>([])
  const [hashtags, setHashtags] = useState<string[]>([])
  const [savedPostId, setSavedPostId] = useState<number | null>(null)
  const [copied, setCopied] = useState(false)
  const [score, setScore] = useState<any>(null)

  const { text: postText, isStreaming, stream, reset } = useStreamingResponse()
  const { text: ideasText, isStreaming: ideasStreaming, stream: streamIdeas, reset: resetIdeas } = useStreamingResponse()

  const { mutate: getHooks, isPending: hooksLoading } = useMutation({
    mutationFn: () => api.post('/api/content/generate/hooks', { topic }).then((r) => r.data),
    onSuccess: (data) => setHooks(data.hooks || []),
  })

  const { mutate: getHashtags } = useMutation({
    mutationFn: () => api.post('/api/content/generate/hashtags', { topic, content: postText }).then((r) => r.data),
    onSuccess: (data) => setHashtags(data.hashtags || []),
  })

  const { mutate: savePost, isPending: saving } = useMutation({
    mutationFn: () => api.post('/api/content/posts', {
      content: postText,
      post_type: postType,
      hook: selectedHook?.hook,
      hashtags,
    }).then((r) => r.data),
    onSuccess: (data) => setSavedPostId(data.id),
  })

  const { mutate: scorePost, isPending: scoring } = useMutation({
    mutationFn: () => api.post(`/api/content/posts/${savedPostId}/score`).then((r) => r.data),
    onSuccess: (data) => setScore(data),
    onError: () => {
      // Score without saving first
      api.post('/api/content/posts', { content: postText, post_type: postType }).then((r) => {
        setSavedPostId(r.data.id)
        return api.post(`/api/content/posts/${r.data.id}/score`)
      }).then((r) => setScore(r.data))
    }
  })

  function handleGenerate() {
    reset()
    stream('/api/content/generate/post', {
      topic,
      post_type: postType,
      hook: selectedHook?.hook,
    })
  }

  function copyPost() {
    const full = `${postText}\n\n${hashtags.join(' ')}`
    navigator.clipboard.writeText(full)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Content Studio</h1>
        <p className="text-gray-500 text-sm mt-1">Generate algorithm-optimized LinkedIn content with AI</p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Left: Controls */}
        <div className="space-y-6">
          {/* Topic */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="font-semibold text-gray-900 mb-4">1. What's your post about?</h2>
            <textarea
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g., The biggest mistake founders make when hiring their first sales team..."
              rows={3}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-linkedin-blue resize-none"
            />
            <div className="flex gap-2 mt-3">
              {POST_TYPES.map((t) => (
                <button
                  key={t}
                  onClick={() => setPostType(t)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    postType === t ? 'bg-linkedin-blue text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          {/* Hooks */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-900">2. Pick a Hook</h2>
              <button
                onClick={() => getHooks()}
                disabled={!topic || hooksLoading}
                className="flex items-center gap-1 text-xs text-linkedin-blue hover:text-linkedin-dark px-2 py-1 rounded border border-linkedin-blue disabled:opacity-50"
              >
                {hooksLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                Generate Hooks
              </button>
            </div>
            {hooks.length === 0 && (
              <p className="text-xs text-gray-400">Enter a topic and generate hooks first</p>
            )}
            <div className="space-y-2">
              {hooks.map((h, i) => (
                <button
                  key={i}
                  onClick={() => setSelectedHook(h)}
                  className={`w-full text-left p-3 rounded-lg border text-sm transition-all ${
                    selectedHook?.hook === h.hook
                      ? 'border-linkedin-blue bg-linkedin-light'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <span className="text-xs font-medium text-gray-400 uppercase mr-2">{h.type}</span>
                  {h.hook}
                </button>
              ))}
            </div>
          </div>

          {/* Generate */}
          <button
            onClick={handleGenerate}
            disabled={!topic || isStreaming}
            className="w-full bg-linkedin-blue text-white rounded-xl px-6 py-3 text-sm font-medium flex items-center justify-center gap-2 hover:bg-linkedin-dark transition-colors disabled:opacity-50"
          >
            {isStreaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
            {isStreaming ? 'Writing...' : 'Generate Post with AI'}
          </button>

          {/* Ideas button */}
          <button
            onClick={() => { resetIdeas(); streamIdeas('/api/content/ideas/generate') }}
            disabled={ideasStreaming}
            className="w-full bg-white border border-gray-200 text-gray-700 rounded-xl px-6 py-3 text-sm font-medium flex items-center justify-center gap-2 hover:bg-gray-50 transition-colors"
          >
            {ideasStreaming ? <Loader2 className="w-4 h-4 animate-spin" /> : '💡'}
            Get 10 Content Ideas
          </button>

          {ideasText && (
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <StreamingText text={ideasText} isStreaming={ideasStreaming} className="text-sm text-gray-700 leading-relaxed" />
            </div>
          )}
        </div>

        {/* Right: Preview */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-gray-200">
            <div className="p-4 border-b border-gray-100 flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">Post Preview</h2>
              <div className="flex gap-2">
                {postText && (
                  <>
                    <button
                      onClick={() => { getHashtags() }}
                      className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded border border-gray-200"
                    >
                      <Hash className="w-3 h-3" /> Hashtags
                    </button>
                    <button
                      onClick={copyPost}
                      className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded border border-gray-200"
                    >
                      {copied ? <CheckCircle className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
                      Copy
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* LinkedIn-style preview */}
            <div className="p-4">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-full bg-linkedin-blue flex items-center justify-center text-white text-sm font-medium">
                  Me
                </div>
                <div>
                  <div className="text-sm font-medium text-gray-900">Your Name</div>
                  <div className="text-xs text-gray-400">Your headline here</div>
                </div>
              </div>
              <div className="text-sm text-gray-900 leading-relaxed min-h-32">
                <StreamingText
                  text={postText}
                  isStreaming={isStreaming}
                  className="whitespace-pre-wrap"
                  placeholder="Your post will appear here..."
                />
              </div>
              {hashtags.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1">
                  {hashtags.map((h, i) => (
                    <span key={i} className="text-linkedin-blue text-xs">{h}</span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Score + Save */}
          {postText && !isStreaming && (
            <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    if (!savedPostId) {
                      api.post('/api/content/posts', { content: postText, post_type: postType })
                        .then((r) => {
                          setSavedPostId(r.data.id)
                          return api.post(`/api/content/posts/${r.data.id}/score`)
                        })
                        .then((r) => setScore(r.data))
                    } else {
                      scorePost()
                    }
                  }}
                  disabled={scoring}
                  className="flex-1 flex items-center justify-center gap-2 border border-gray-200 rounded-lg py-2 text-sm text-gray-700 hover:bg-gray-50"
                >
                  {scoring ? <Loader2 className="w-3 h-3 animate-spin" /> : <Star className="w-3 h-3" />}
                  Score Post
                </button>
                <button
                  onClick={() => savePost()}
                  disabled={saving || !!savedPostId}
                  className="flex-1 bg-linkedin-blue text-white rounded-lg py-2 text-sm font-medium hover:bg-linkedin-dark transition-colors disabled:opacity-50"
                >
                  {savedPostId ? '✓ Saved' : saving ? 'Saving...' : 'Save Draft'}
                </button>
              </div>

              {score && (
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <Star className="w-4 h-4 text-yellow-400 fill-yellow-400" />
                    <span className="font-semibold text-gray-900">{score.total_score}/100</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      score.estimated_engagement_level === 'viral' ? 'bg-green-100 text-green-600' :
                      score.estimated_engagement_level === 'high' ? 'bg-blue-100 text-blue-600' :
                      'bg-gray-100 text-gray-500'
                    }`}>
                      {score.estimated_engagement_level}
                    </span>
                  </div>
                  {score.improvements?.slice(0, 2).map((imp: string, i: number) => (
                    <p key={i} className="text-xs text-gray-600 flex gap-1">
                      <span className="text-orange-400">→</span> {imp}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
