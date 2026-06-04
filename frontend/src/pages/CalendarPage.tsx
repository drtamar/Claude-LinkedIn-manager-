import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'
import { ChevronLeft, ChevronRight, Calendar, Loader2, Zap } from 'lucide-react'
import { format, startOfMonth, endOfMonth, eachDayOfInterval, getDay, isSameDay, isToday } from 'date-fns'

export function CalendarPage() {
  const [currentMonth, setCurrentMonth] = useState(new Date())
  const qc = useQueryClient()

  const { data: calendar } = useQuery({
    queryKey: ['calendar', format(currentMonth, 'yyyy-MM')],
    queryFn: () => api.get('/api/schedule/calendar').then((r) => r.data),
  })

  const { data: optimalTimes } = useQuery({
    queryKey: ['optimal-times'],
    queryFn: () => api.get('/api/schedule/optimal-times').then((r) => r.data),
  })

  const { mutate: autoPlan, isPending: planning } = useMutation({
    mutationFn: () => api.post('/api/schedule/auto-plan'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['calendar'] }),
  })

  const monthStart = startOfMonth(currentMonth)
  const monthEnd = endOfMonth(currentMonth)
  const days = eachDayOfInterval({ start: monthStart, end: monthEnd })
  const startDow = getDay(monthStart)

  const statusColors: Record<string, string> = {
    published: 'bg-green-500',
    confirmed: 'bg-linkedin-blue',
    planned: 'bg-yellow-400',
    missed: 'bg-red-400',
  }

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Content Calendar</h1>
          <p className="text-gray-500 text-sm mt-1">Plan and schedule your LinkedIn content</p>
        </div>
        <button
          onClick={() => autoPlan()}
          disabled={planning}
          className="flex items-center gap-2 bg-linkedin-blue text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-linkedin-dark transition-colors"
        >
          {planning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
          AI Auto-Plan 30 Days
        </button>
      </div>

      <div className="grid grid-cols-4 gap-6">
        {/* Calendar */}
        <div className="col-span-3 bg-white rounded-xl border border-gray-200">
          {/* Month navigation */}
          <div className="p-4 border-b border-gray-100 flex items-center justify-between">
            <button
              onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1))}
              className="p-1 rounded hover:bg-gray-100"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <h2 className="font-semibold text-gray-900">{format(currentMonth, 'MMMM yyyy')}</h2>
            <button
              onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1))}
              className="p-1 rounded hover:bg-gray-100"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <div className="p-4">
            {/* Day headers */}
            <div className="grid grid-cols-7 mb-2">
              {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => (
                <div key={d} className="text-center text-xs font-medium text-gray-400 py-2">{d}</div>
              ))}
            </div>

            {/* Days grid */}
            <div className="grid grid-cols-7 gap-1">
              {Array.from({ length: startDow }).map((_, i) => (
                <div key={`empty-${i}`} className="aspect-square" />
              ))}
              {days.map((day) => {
                const dayEntries = calendar?.filter((e: any) =>
                  e.scheduled_date && isSameDay(new Date(e.scheduled_date), day)
                ) || []

                return (
                  <div
                    key={day.toISOString()}
                    className={`aspect-square rounded-lg p-1 border transition-colors ${
                      isToday(day)
                        ? 'border-linkedin-blue bg-linkedin-light'
                        : 'border-transparent hover:border-gray-200 hover:bg-gray-50'
                    }`}
                  >
                    <div className={`text-xs font-medium mb-1 ${isToday(day) ? 'text-linkedin-blue' : 'text-gray-500'}`}>
                      {format(day, 'd')}
                    </div>
                    <div className="space-y-0.5">
                      {dayEntries.slice(0, 2).map((entry: any) => (
                        <div
                          key={entry.id}
                          className={`h-1.5 rounded-full ${statusColors[entry.status] || 'bg-gray-300'}`}
                          title={entry.notes || entry.status}
                        />
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Legend */}
          <div className="px-4 pb-4 flex items-center gap-4">
            {Object.entries(statusColors).map(([status, color]) => (
              <div key={status} className="flex items-center gap-1.5">
                <div className={`w-2 h-2 rounded-full ${color}`} />
                <span className="text-xs text-gray-500 capitalize">{status}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Optimal Times */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Calendar className="w-4 h-4 text-linkedin-blue" />
              Best Times to Post
            </h2>
            {optimalTimes ? (
              <div className="space-y-3">
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase mb-2">Best Days</p>
                  <div className="flex flex-wrap gap-1">
                    {(optimalTimes.best_days || optimalTimes.recommendation?.best_days || []).map((d: string) => (
                      <span key={d} className="px-2 py-1 bg-linkedin-light text-linkedin-blue text-xs rounded-full">{d}</span>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase mb-2">Best Times</p>
                  <div className="space-y-1">
                    {(optimalTimes.best_times || optimalTimes.recommendation?.best_times || []).map((t: string) => (
                      <span key={t} className="block text-sm text-gray-700">{t}</span>
                    ))}
                  </div>
                </div>
                {optimalTimes.note || optimalTimes.recommendation?.timezone_note ? (
                  <p className="text-xs text-gray-400 mt-2">
                    {optimalTimes.note || optimalTimes.recommendation?.timezone_note}
                  </p>
                ) : null}
              </div>
            ) : (
              <p className="text-sm text-gray-400">Loading optimal times...</p>
            )}
          </div>

          <div className="bg-linkedin-light rounded-xl p-4">
            <p className="text-xs font-medium text-linkedin-dark mb-2">LinkedIn Algorithm Tip</p>
            <p className="text-xs text-gray-600 leading-relaxed">
              Consistency beats frequency. Posting 3x/week at the same times trains both the algorithm and your audience when to expect your content.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
