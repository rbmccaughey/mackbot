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
  valley_ridge: {
    label: 'Valley Ridge',
    courses: [
      { id: 1, name: 'Valley Ridge' },
    ],
  },
}

type SiteKey = keyof typeof SITES

function tomorrow(): string {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toISOString().slice(0, 10)
}

const INTERVAL_PRESETS = [
  { label: '1m', value: 60 },
  { label: '2m', value: 120 },
  { label: '5m', value: 300 },
  { label: '10m', value: 600 },
]

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
  const [collapsed, setCollapsed] = useState(false)

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
      setCollapsed(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }

  const expand = () => {
    setCollapsed(false)
    setError('')
  }

  const siteConfig = SITES[site]

  if (collapsed) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl px-5 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            <span className="text-sm font-medium text-slate-300">Scan started</span>
          </div>
          <button
            onClick={expand}
            className="flex items-center gap-1.5 text-xs font-medium text-emerald-400 hover:text-emerald-300 border border-emerald-500/30 hover:border-emerald-500/50 bg-emerald-500/10 hover:bg-emerald-500/15 rounded-lg px-3 py-1.5 transition-all"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            New scan
          </button>
        </div>
      </div>
    )
  }

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
            <div className="flex gap-2">
              {[1, 2, 3, 4].map(n => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setPlayers(n)}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all border ${
                    players === n
                      ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40'
                      : 'bg-slate-800 text-slate-400 border-slate-700 hover:border-slate-600 hover:text-slate-300'
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
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
          <div className="flex items-center justify-between mb-1.5">
            <label className={labelClass + ' mb-0'}>Poll interval</label>
          </div>
          <div className="flex gap-2">
            {INTERVAL_PRESETS.map(p => (
              <button
                key={p.value}
                type="button"
                onClick={() => setIntervalSecs(p.value)}
                className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all border ${
                  interval === p.value
                    ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40'
                    : 'bg-slate-800 text-slate-400 border-slate-700 hover:border-slate-600 hover:text-slate-300'
                }`}
              >
                {p.label}
              </button>
            ))}
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
