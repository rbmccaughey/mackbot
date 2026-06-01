import { useEffect, useRef, useState } from 'react'
import type { Scan, ScanStatus } from '../types'

const STATUS: Record<ScanStatus, { label: string; dot: string; text: string; bg: string; border: string; pulse?: boolean }> = {
  scanning: {
    label: 'Scanning',
    dot: 'bg-blue-400',
    text: 'text-blue-400',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/20',
    pulse: true,
  },
  found: {
    label: 'Found!',
    dot: 'bg-amber-400',
    text: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/20',
    pulse: true,
  },
  booked: {
    label: 'Booked',
    dot: 'bg-emerald-400',
    text: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/20',
  },
  failed: {
    label: 'Failed',
    dot: 'bg-red-400',
    text: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/20',
  },
  cancelled: {
    label: 'Cancelled',
    dot: 'bg-slate-500',
    text: 'text-slate-500',
    bg: 'bg-slate-700/30',
    border: 'border-slate-700',
  },
}

const COURSE: Record<number, string> = { 1: 'Mt Lorette', 2: 'Mt Kidd' }

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T12:00:00')
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
}

export default function ScanCard({ scan, onCancel }: { scan: Scan; onCancel: (id: string) => void }) {
  const [expanded, setExpanded] = useState(scan.status === 'scanning' || scan.status === 'found')
  const logRef = useRef<HTMLDivElement>(null)
  const isActive = scan.status === 'scanning' || scan.status === 'found'
  const s = STATUS[scan.status]
  const courseLabel = scan.courses.map(c => COURSE[c] ?? c).join(' · ')

  useEffect(() => {
    if (expanded && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [scan.log, expanded])

  const visibleLog = expanded ? scan.log : scan.log.slice(-2)

  return (
    <div className={`bg-slate-900 rounded-xl border overflow-hidden transition-colors ${isActive ? 'border-slate-700' : 'border-slate-800'}`}>
      {isActive && (
        <div className="h-px bg-gradient-to-r from-emerald-500/60 via-emerald-500/20 to-transparent" />
      )}

      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <span className="font-semibold text-white text-sm">{formatDate(scan.date)}</span>
              <span className="text-slate-400 text-xs tabular-nums">{scan.time_from}–{scan.time_to}</span>
              <span className="text-slate-500 text-xs">{scan.players}p</span>
              <span className="text-slate-600 text-xs">·</span>
              <span className="text-slate-500 text-xs">{courseLabel}</span>
            </div>

            <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full border ${s.text} ${s.bg} ${s.border}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${s.dot} ${s.pulse ? 'animate-pulse' : ''}`} />
              {s.label}
            </span>
          </div>

          {isActive && (
            <button
              onClick={() => onCancel(scan.id)}
              className="shrink-0 text-xs text-slate-500 hover:text-red-400 border border-slate-700 hover:border-red-500/40 rounded-lg px-2.5 py-1.5 transition-colors bg-slate-800/50 hover:bg-red-500/10"
            >
              Cancel
            </button>
          )}
        </div>

        {scan.log.length > 0 && (
          <div className="mt-3">
            <button
              onClick={() => setExpanded(e => !e)}
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 mb-2 transition-colors"
            >
              <svg
                className={`w-3 h-3 transition-transform ${expanded ? 'rotate-90' : ''}`}
                viewBox="0 0 12 12"
                fill="currentColor"
              >
                <path d="M4.5 3L7.5 6L4.5 9" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {expanded ? 'Hide log' : `Show log (${scan.log.length} lines)`}
            </button>

            <div
              ref={logRef}
              className="log-scroll bg-[#0d1117] border border-slate-800 rounded-lg px-3 py-2.5 font-mono text-xs text-slate-400 space-y-1 max-h-44 overflow-y-auto"
            >
              {!expanded && scan.log.length > 2 && (
                <div className="text-slate-600 select-none">↑ {scan.log.length - 2} earlier lines</div>
              )}
              {visibleLog.map((line, i) => (
                <div key={i} className="leading-relaxed">
                  <span className="text-emerald-600 select-none mr-2">›</span>
                  {line}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
