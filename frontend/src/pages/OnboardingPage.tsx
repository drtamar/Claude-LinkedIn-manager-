import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../lib/api'
import { Network as Linkedin, ChevronRight, Loader2 } from 'lucide-react'

interface Question {
  step_id: string
  question: string
  question_type: string
  options?: string[]
  placeholder?: string
  scale_min?: number
  scale_max?: number
}

export function OnboardingPage() {
  const navigate = useNavigate()
  const [sessionToken, setSessionToken] = useState<string | null>(null)
  const [currentStep, setCurrentStep] = useState(0)
  const [totalSteps] = useState(35)
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null)
  const [answer, setAnswer] = useState('')
  const [selectedOptions, setSelectedOptions] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [completing, setCompleting] = useState(false)
  useEffect(() => {
    startSession()
  }, [])

  async function startSession() {
    setLoading(true)
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
