import { useState } from 'react'
import type { CreateScanPayload } from '../types'

const COURSES = [
  { id: 1, name: 'Mt Lorette' },
  { id: 2, name: 'Mt Kidd' },
]

function tomorrow(): string {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toISOString().slice(0, 10)
}

export default function CreateScanForm({ onSubmit }: { onSubmit: (p: CreateScanPayload) => Promise<void> }) {
  const [date, setDate] = useState(tomorrow())
  const [timeFrom, setTimeFrom] = useState('08:00')
  const [timeTo, setTimeTo] = useState('10:00')
  const [players, setPlayers] = useState(4)
  const [courses, setCourses] = useState<number[]>([1, 2])
  const [interval, setIntervalSecs] = useState(300)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const toggleCourse = (id: number) =>
    setCourses(prev => prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (courses.length === 0) { setError('Select at least one course.'); return }
    setError('')
    setLoading(true)
    try {
      await onSubmit({ date, time_from: timeFrom, time_to: timeTo, players, courses, interval })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h2 className="text-base font-semibold text-gray-900 mb-4">New scan</h2>
      <form onSubmit={handleSubmit} className="space-y-4">

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Date</label>
            <input
              type="date"
              value={date}
              min={new Date().toISOString().slice(0, 10)}
              onChange={e => setDate(e.target.value)}
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Players</label>
            <select
              value={players}
              onChange={e => setPlayers(Number(e.target.value))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
            >
              {[1, 2, 3, 4].map(n => (
                <option key={n} value={n}>{n} {n === 1 ? 'player' : 'players'}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Earliest tee time</label>
            <input
              type="time"
              value={timeFrom}
              onChange={e => setTimeFrom(e.target.value)}
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Latest tee time</label>
            <input
              type="time"
              value={timeTo}
              onChange={e => setTimeTo(e.target.value)}
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-600"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Courses</label>
          <div className="flex gap-5">
            {COURSES.map(c => (
              <label key={c.id} className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={courses.includes(c.id)}
                  onChange={() => toggleCourse(c.id)}
                  className="w-4 h-4 rounded accent-green-700"
                />
                <span className="text-sm text-gray-700">{c.name}</span>
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Poll every <span className="text-green-700 font-semibold">{interval / 60} min</span>
          </label>
          <input
            type="range"
            min={60}
            max={600}
            step={60}
            value={interval}
            onChange={e => setIntervalSecs(Number(e.target.value))}
            className="w-full accent-green-700"
          />
          <div className="flex justify-between text-xs text-gray-400 mt-0.5">
            <span>1 min</span><span>10 min</span>
          </div>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-green-700 hover:bg-green-800 disabled:opacity-60 text-white font-medium py-2.5 rounded-lg text-sm transition-colors"
        >
          {loading ? 'Starting…' : 'Start scan'}
        </button>
      </form>
    </div>
  )
}
