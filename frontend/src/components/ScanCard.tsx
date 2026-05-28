import { useEffect, useRef, useState } from 'react'
import type { Scan, ScanStatus } from '../types'

const STATUS: Record<ScanStatus, { label: string; className: string; pulse?: boolean }> = {
  scanning: { label: 'Scanning', className: 'bg-blue-100 text-blue-700', pulse: true },
  found:    { label: 'Found!',   className: 'bg-amber-100 text-amber-700', pulse: true },
  booked:   { label: 'Booked',   className: 'bg-green-100 text-green-700' },
  failed:   { label: 'Failed',   className: 'bg-red-100 text-red-700' },
  cancelled:{ label: 'Cancelled',className: 'bg-gray-100 text-gray-500' },
}

const COURSE: Record<number, string> = { 1: 'Mt Lorette', 2: 'Mt Kidd' }

export default function ScanCard({ scan, onCancel }: { scan: Scan; onCancel: (id: string) => void }) {
  const [expanded, setExpanded] = useState(scan.status === 'scanning' || scan.status === 'found')
  const logRef = useRef<HTMLDivElement>(null)
  const isActive = scan.status === 'scanning' || scan.status === 'found'
  const { label, className, pulse } = STATUS[scan.status]
  const courseLabel = scan.courses.map(c => COURSE[c] ?? c).join(', ')

  useEffect(() => {
    if (expanded && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [scan.log, expanded])

  const visibleLog = expanded ? scan.log : scan.log.slice(-2)

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-semibold text-gray-900">{scan.date}</span>
            <span className="text-gray-500 text-sm">{scan.time_from}–{scan.time_to}</span>
            <span className="text-gray-400 text-sm">{scan.players}p</span>
            <span className="text-gray-400 text-sm">{courseLabel}</span>
          </div>
          <span className={`inline-flex items-center gap-1.5 mt-1.5 text-xs font-medium px-2 py-0.5 rounded-full ${className}`}>
            {pulse && <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />}
            {label}
          </span>
        </div>

        {isActive && (
          <button
            onClick={() => onCancel(scan.id)}
            className="shrink-0 text-xs text-gray-400 hover:text-red-600 border border-gray-200 hover:border-red-300 rounded-md px-2.5 py-1 transition-colors"
          >
            Cancel
          </button>
        )}
      </div>

      {scan.log.length > 0 && (
        <div className="mt-3">
          <button
            onClick={() => setExpanded(e => !e)}
            className="text-xs text-gray-400 hover:text-gray-600 mb-1.5 transition-colors"
          >
            {expanded ? '▾ Hide log' : `▸ Show log (${scan.log.length})`}
          </button>
          <div
            ref={logRef}
            className="bg-gray-50 rounded-lg px-3 py-2 font-mono text-xs text-gray-600 space-y-0.5 max-h-44 overflow-y-auto"
          >
            {!expanded && scan.log.length > 2 && (
              <div className="text-gray-400">… {scan.log.length - 2} earlier</div>
            )}
            {visibleLog.map((line, i) => (
              <div key={i}>{line}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
