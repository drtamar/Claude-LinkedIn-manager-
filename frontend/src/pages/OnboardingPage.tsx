import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../lib/api'
import { Network as Linkedin, ChevronRight, Loader2, Upload, FileText } from 'lucide-react'

interface Question {
  step_id: string
  question: string
  question_type: string
  options?: string[]
  placeholder?: string
  scale_min?: number
  scale_max?: number
}

type Mode = 'choose' | 'questionnaire' | 'import'

export function OnboardingPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>('choose')
  const [sessionToken, setSessionToken] = useState<string | null>(null)
  const [currentStep, setCurrentStep] = useState(0)
  const [totalSteps] = useState(35)
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null)
  const [answer, setAnswer] = useState('')
  const [selectedOptions, setSelectedOptions] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [completing, setCompleting] = useState(false)
  const [importText, setImportText] = useState('')
  const [importing, setImporting] = useState(false)
  const [importError, setImportError] = useState('')

  useEffect(() => {
    // Don't auto-start — wait for user to choose mode
  }, [])

  async function startSession() {
    setLoading(true)
    setMode('questionnaire')
    try {
      const { data } = await api.post('/api/questionnaire/start')
      setSessionToken(data.session_token)
      setCurrentQuestion(data.first_question)
    } catch (err) {
      console.error('Failed to start questionnaire', err)
    } finally {
      setLoading(false)
    }
  }

  async function importProfile() {
    if (importText.trim().length < 100) {
      setImportError('Please paste your full CV or LinkedIn export (at least 100 characters).')
      return
    }
    setImportError('')
    setImporting(true)
    try {
      await api.post('/api/questionnaire/import', { raw_text: importText })
      navigate('/profile')
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Import failed. Please try again.'
      setImportError(msg)
    } finally {
      setImporting(false)
    }
  }

  async function submitAnswer() {
    if (!sessionToken || !currentQuestion) return
    setLoading(true)

    const answerValue = currentQuestion.question_type === 'multi_select'
      ? JSON.stringify(selectedOptions)
      : answer

    try {
      const { data } = await api.post(`/api/questionnaire/session/${sessionToken}/answer`, {
        step_id: currentQuestion.step_id,
        question_text: currentQuestion.question,
        answer_value: answerValue,
        answer_type: currentQuestion.question_type,
      })

      setAnswer('')
      setSelectedOptions([])
      setCurrentStep(data.current_step)

      if (data.done) {
        await completeQuestionnaire()
      } else {
        setCurrentQuestion(data.next_question)
      }
    } catch (err) {
      console.error('Failed to submit answer', err)
    } finally {
      setLoading(false)
    }
  }

  async function completeQuestionnaire() {
    if (!sessionToken) return
    setCompleting(true)
    try {
      await api.post(`/api/questionnaire/session/${sessionToken}/complete`)
      navigate('/profile')
    } catch (err) {
      console.error('Failed to complete questionnaire', err)
    } finally {
      setCompleting(false)
    }
  }

  function toggleOption(opt: string) {
    setSelectedOptions((prev) =>
      prev.includes(opt) ? prev.filter((o) => o !== opt) : [...prev, opt]
    )
  }

  const progress = (currentStep / totalSteps) * 100

  // Mode chooser — first screen shown before anything starts
  if (mode === 'choose') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-linkedin-blue to-linkedin-dark flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-8">
          <div className="flex items-center gap-2 mb-6">
            <Linkedin className="w-6 h-6 text-linkedin-blue" />
            <span className="font-semibold text-gray-800">LinkedIn Strategy Setup</span>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">How would you like to start?</h2>
          <p className="text-gray-500 text-sm mb-8">
            Answer a short questionnaire so our AI can build your strategy from scratch, or paste your existing CV / LinkedIn export to skip ahead.
          </p>
          <div className="grid grid-cols-1 gap-4">
            <button
              onClick={startSession}
              className="flex items-start gap-4 border-2 border-gray-200 hover:border-linkedin-blue rounded-xl p-5 text-left transition-all group"
            >
              <div className="w-10 h-10 bg-linkedin-light rounded-lg flex items-center justify-center shrink-0 group-hover:bg-linkedin-blue/20">
                <ChevronRight className="w-5 h-5 text-linkedin-blue" />
              </div>
              <div>
                <p className="font-semibold text-gray-900 mb-1">Answer 35 questions</p>
                <p className="text-sm text-gray-500">Our AI interviews you step by step to craft a fully personalized LinkedIn strategy.</p>
              </div>
            </button>

            <button
              onClick={() => setMode('import')}
              className="flex items-start gap-4 border-2 border-gray-200 hover:border-linkedin-blue rounded-xl p-5 text-left transition-all group"
            >
              <div className="w-10 h-10 bg-green-50 rounded-lg flex items-center justify-center shrink-0 group-hover:bg-green-100">
                <Upload className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <p className="font-semibold text-gray-900 mb-1">Import from existing CV / LinkedIn</p>
                <p className="text-sm text-gray-500">Paste your CV or LinkedIn profile export and our AI will extract everything automatically — no questions needed.</p>
              </div>
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Import mode — paste CV / LinkedIn text
  if (mode === 'import') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-linkedin-blue to-linkedin-dark flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl">
          <div className="p-6 border-b border-gray-100 flex items-center gap-3">
            <button onClick={() => setMode('choose')} className="text-gray-400 hover:text-gray-600 text-sm">← Back</button>
            <div className="flex items-center gap-2 ml-auto">
              <FileText className="w-4 h-4 text-linkedin-blue" />
              <span className="text-sm font-medium text-gray-700">Import Profile</span>
            </div>
          </div>

          <div className="p-8">
            <h2 className="text-xl font-bold text-gray-900 mb-1">Paste your CV or LinkedIn export</h2>
            <p className="text-sm text-gray-500 mb-6">
              Include your full experience, skills, education and any achievements. The more you paste, the better the output. Plain text or formatted — both work.
            </p>

            <textarea
              value={importText}
              onChange={(e) => { setImportText(e.target.value); setImportError('') }}
              placeholder="Paste your CV or LinkedIn profile text here..."
              rows={14}
              className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-linkedin-blue resize-none font-mono"
            />

            {importError && (
              <p className="text-red-500 text-sm mt-2">{importError}</p>
            )}

            <div className="flex items-center justify-between mt-2 mb-6">
              <span className="text-xs text-gray-400">{importText.length} characters</span>
              {importText.length >= 100 && (
                <span className="text-xs text-green-600 font-medium">✓ Ready to import</span>
              )}
            </div>

            <button
              onClick={importProfile}
              disabled={importing || importText.trim().length < 100}
              className="w-full bg-linkedin-blue text-white rounded-xl px-6 py-3 text-sm font-medium flex items-center justify-center gap-2 hover:bg-linkedin-dark transition-colors disabled:opacity-50"
            >
              {importing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Extracting your profile with AI...
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4" />
                  Import &amp; Build Profile
                </>
              )}
            </button>
            {importing && (
              <p className="text-center text-xs text-gray-400 mt-3">
                Claude is reading your profile — this takes about 20–30 seconds.
              </p>
            )}
          </div>
        </div>
      </div>
    )
  }

  if (loading && !currentQuestion) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-linkedin-blue to-linkedin-dark">
        <div className="bg-white rounded-2xl p-8 text-center">
          <Loader2 className="w-8 h-8 text-linkedin-blue animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Preparing your LinkedIn strategy session...</p>
        </div>
      </div>
    )
  }

  if (completing) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-linkedin-blue to-linkedin-dark">
        <div className="bg-white rounded-2xl p-8 text-center max-w-md">
          <div className="w-16 h-16 bg-linkedin-light rounded-full flex items-center justify-center mx-auto mb-4">
            <Linkedin className="w-8 h-8 text-linkedin-blue" />
          </div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">Building Your Profile</h2>
          <p className="text-gray-500 text-sm mb-4">
            Our AI is synthesizing your answers into a powerful LinkedIn strategy...
          </p>
          <Loader2 className="w-6 h-6 text-linkedin-blue animate-spin mx-auto" />
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-linkedin-blue to-linkedin-dark flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl">
        {/* Header */}
        <div className="p-6 border-b border-gray-100">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Linkedin className="w-5 h-5 text-linkedin-blue" />
              <span className="text-sm font-medium text-gray-600">LinkedIn Strategy Setup</span>
            </div>
            <span className="text-xs text-gray-400">{currentStep}/{totalSteps}</span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-linkedin-blue rounded-full transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Question */}
        {currentQuestion && (
          <div className="p-8">
            <div className="mb-6">
              <p className="text-xs font-medium text-linkedin-blue uppercase tracking-wide mb-2">
                Question {currentStep + 1}
              </p>
              <h2 className="text-xl font-semibold text-gray-900 leading-relaxed">
                {currentQuestion.question}
              </h2>
            </div>

            {/* Answer input based on type */}
            <div className="space-y-3">
              {currentQuestion.question_type === 'text' && (
                <textarea
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  placeholder={currentQuestion.placeholder || 'Type your answer...'}
                  rows={4}
                  className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-linkedin-blue resize-none"
                />
              )}

              {currentQuestion.question_type === 'select' && currentQuestion.options && (
                <div className="grid grid-cols-1 gap-2">
                  {currentQuestion.options.map((opt) => (
                    <button
                      key={opt}
                      onClick={() => setAnswer(opt)}
                      className={`text-left px-4 py-3 rounded-xl border text-sm font-medium transition-all ${
                        answer === opt
                          ? 'border-linkedin-blue bg-linkedin-light text-linkedin-blue'
                          : 'border-gray-200 text-gray-700 hover:border-linkedin-blue hover:bg-gray-50'
                      }`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              )}

              {currentQuestion.question_type === 'multi_select' && currentQuestion.options && (
                <div className="grid grid-cols-2 gap-2">
                  {currentQuestion.options.map((opt) => (
                    <button
                      key={opt}
                      onClick={() => toggleOption(opt)}
                      className={`text-left px-3 py-2 rounded-lg border text-sm transition-all ${
                        selectedOptions.includes(opt)
                          ? 'border-linkedin-blue bg-linkedin-light text-linkedin-blue'
                          : 'border-gray-200 text-gray-700 hover:border-gray-300'
                      }`}
                    >
                      {selectedOptions.includes(opt) ? '✓ ' : ''}{opt}
                    </button>
                  ))}
                </div>
              )}

              {currentQuestion.question_type === 'scale' && (
                <div>
                  <input
                    type="range"
                    min={currentQuestion.scale_min || 1}
                    max={currentQuestion.scale_max || 10}
                    value={answer || '5'}
                    onChange={(e) => setAnswer(e.target.value)}
                    className="w-full accent-linkedin-blue"
                  />
                  <div className="flex justify-between text-xs text-gray-400 mt-1">
                    <span>{currentQuestion.scale_min || 1}</span>
                    <span className="font-medium text-linkedin-blue text-base">{answer || '5'}</span>
                    <span>{currentQuestion.scale_max || 10}</span>
                  </div>
                </div>
              )}

              {currentQuestion.question_type === 'boolean' && (
                <div className="flex gap-3">
                  {['Yes', 'No'].map((opt) => (
                    <button
                      key={opt}
                      onClick={() => setAnswer(opt)}
                      className={`flex-1 px-4 py-3 rounded-xl border text-sm font-medium transition-all ${
                        answer === opt
                          ? 'border-linkedin-blue bg-linkedin-light text-linkedin-blue'
                          : 'border-gray-200 text-gray-700 hover:border-linkedin-blue'
                      }`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <button
              onClick={submitAnswer}
              disabled={loading || (!answer && selectedOptions.length === 0)}
              className="mt-6 w-full bg-linkedin-blue text-white rounded-xl px-6 py-3 text-sm font-medium flex items-center justify-center gap-2 hover:bg-linkedin-dark transition-colors disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  {currentStep >= totalSteps - 1 ? 'Complete Setup' : 'Next'}
                  <ChevronRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
