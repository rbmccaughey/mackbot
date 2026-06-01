import { useState } from 'react'
import type { CreateScanPayload } from '../types'
import DatePicker from './DatePicker'
import TimePicker from './TimePicker'

const SITES = {
  kananaskis: {
    label: 'Kananaskis',
    courses: [
      { id: 1, name: 'Mt Lorette' },
      { id: 2, name: 'Mt Kidd' },
    ],
  },
  calgary: {
    label: 'Calgary',
    courses: [
      { id: 3, name: 'Maple Ridge 18' },
      { id: 4, name: 'McCall Lake 18' },
      { id: 5, name: 'Shaganappi 18' },
      { id: 1, name: 'Confederation Park 9' },
      { id: 2, name: 'Lakeview 9' },
      { id: 6, name: 'Valley 9' },
      { id: 7, name: 'McCall Par 3' },
      { id: 11, name: 'Maple Ridge Back 9' },
      { id: 12, name: 'McCall Back 9' },
      { id: 8, name: 'Shaganappi Back 9' },
    ],
  },
}

type SiteKey = keyof typeof SITES

function tomorrow(): string {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toISOString().slice(0, 10)
}

const inputClass =
  'w-full bg-slate-800 border border-slate-700 text-slate-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 transition-colors'

const labelClass = 'block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5'

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}

export default function CreateScanForm({ onSubmit }: { onSubmit: (p: CreateScanPayload) => Promise<void> }) {
  const [site, setSite] = useState<SiteKey>('kananaskis')
  const [date, setDate] = useState(tomorrow())
  const [timeFrom, setTimeFrom] = useState('08:00')
  const [timeTo, setTimeTo] = useState('10:00')
  const [players, setPlayers] = useState(4)
  const [courses, setCourses] = useState<number[]>([1, 2])
  const [interval, setIntervalSecs] = useState(300)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSiteChange = (key: SiteKey) => {
    setSite(key)
    setCourses(SITES[key].courses.map(c => c.id))
  }

  const toggleCourse = (id: number) =>
    setCourses(prev => prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (courses.length === 0) { setError('Select at least one course.'); return }
    setError('')
    setLoading(true)
    try {
      await onSubmit({ date, time_from: timeFrom, time_to: timeTo, players, courses, interval, site })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }

  const siteConfig = SITES[site]

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
      <div className="flex items-center gap-2 mb-6">
        <h2 className="text-sm font-semibold text-white">New scan</h2>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className={labelClass}>Site</label>
          <div className="flex gap-2">
            {(Object.keys(SITES) as SiteKey[]).map(key => (
              <button
                key={key}
                type="button"
                onClick={() => handleSiteChange(key)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all border ${
                  site === key
                    ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40'
                    : 'bg-slate-800 text-slate-400 border-slate-700 hover:border-slate-600 hover:text-slate-300'
                }`}
              >
                {SITES[key].label}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Date</label>
            <DatePicker
              value={date}
              onChange={setDate}
              min={new Date().toISOString().slice(0, 10)}
            />
          </div>
          <div>
            <label className={labelClass}>Players</label>
            <select
              value={players}
              onChange={e => setPlayers(Number(e.target.value))}
              className={inputClass}
              style={{ colorScheme: 'dark' }}
            >
              {[1, 2, 3, 4].map(n => (
                <option key={n} value={n}>{n} {n === 1 ? 'player' : 'players'}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Earliest tee time</label>
            <TimePicker value={timeFrom} onChange={setTimeFrom} />
          </div>
          <div>
            <label className={labelClass}>Latest tee time</label>
            <TimePicker value={timeTo} onChange={setTimeTo} />
          </div>
        </div>

        <div>
          <label className={labelClass}>Courses</label>
          <div className="flex gap-2 flex-wrap">
            {siteConfig.courses.map(c => (
              <button
                key={c.id}
                type="button"
                onClick={() => toggleCourse(c.id)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all border ${
                  courses.includes(c.id)
                    ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40'
                    : 'bg-slate-800 text-slate-400 border-slate-700 hover:border-slate-600 hover:text-slate-300'
                }`}
              >
                {c.name}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className={labelClass + ' mb-0'}>Poll interval</label>
            <span className="text-xs font-semibold text-emerald-400 tabular-nums">
              every {interval / 60} {interval / 60 === 1 ? 'min' : 'min'}
            </span>
          </div>
          <input
            type="range"
            min={60}
            max={600}
            step={60}
            value={interval}
            onChange={e => setIntervalSecs(Number(e.target.value))}
            className="w-full"
          />
          <div className="flex justify-between text-xs text-slate-600 mt-1">
            <span>1 min</span><span>10 min</span>
          </div>
        </div>

        {error && (
          <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg text-sm transition-colors"
        >
          {loading ? <><Spinner /> Starting…</> : 'Start scan'}
        </button>
      </form>
    </div>
  )
}
