import { useEffect, useState } from 'react'
import type { Scan, CreateScanPayload } from './types'
import CreateScanForm from './components/CreateScanForm'
import ScanCard from './components/ScanCard'

export default function App() {
  const [scans, setScans] = useState<Scan[]>([])
  const [serverError, setServerError] = useState(false)

  useEffect(() => {
    const poll = () => {
      fetch('/scans')
        .then(r => r.json())
        .then((data: Scan[]) => {
          setScans(data)
          setServerError(false)
        })
        .catch(() => setServerError(true))
    }
    poll()
    const id = setInterval(poll, 3000)
    return () => clearInterval(id)
  }, [])

  const createScan = async (payload: CreateScanPayload) => {
    const resp = await fetch('/scans', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!resp.ok) {
      const err = await resp.json()
      throw new Error(err.detail ?? 'Failed to create scan')
    }
    const scan: Scan = await resp.json()
    setScans(prev => [scan, ...prev])
  }

  const cancelScan = async (id: string) => {
    await fetch(`/scans/${id}`, { method: 'DELETE' })
  }

  const activeScans = scans.filter(s => s.status === 'scanning' || s.status === 'found')
  const doneScans = scans.filter(s => s.status === 'booked' || s.status === 'cancelled' || s.status === 'failed')

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="relative bg-gradient-to-b from-slate-800 to-slate-900 shadow-2xl shadow-black/40">
        <div className="max-w-2xl mx-auto px-6 py-0 flex items-center justify-between">
          <div className="flex items-center gap-5">
            <img
              src="/mackbot.png"
              alt="mackbot"
              className="w-36 h-36 object-contain drop-shadow-[0_0_16px_rgba(16,185,129,0.35)]"
            />
            <div>
              <h1 className="text-2xl text-white tracking-wide" style={{ fontFamily: "'Bitcount Grid Single', monospace", fontWeight: 700 }}>MackBot</h1>
              <p className="text-xs text-slate-400 mt-1" style={{ fontFamily: "'Space Mono', monospace" }}>snagging tee times so you don't have to</p>
            </div>
          </div>
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold border ${
            serverError
              ? 'bg-red-500/10 border-red-500/25 text-red-400'
              : 'bg-emerald-500/10 border-emerald-500/25 text-emerald-400'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${serverError ? 'bg-red-400' : 'bg-emerald-400 animate-pulse'}`} />
            {serverError ? 'Disconnected' : 'Live'}
          </div>
        </div>
        <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-500/40 to-transparent" />
      </header>

      <main className="max-w-2xl mx-auto px-4 py-8 space-y-8">
        {serverError && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 text-sm rounded-xl px-4 py-3 flex items-start gap-2.5">
            <span className="mt-0.5 shrink-0">⚠</span>
            <span>
              Cannot reach the server — make sure{' '}
              <code className="font-mono text-xs bg-red-500/15 px-1.5 py-0.5 rounded">uvicorn server:app --reload</code>{' '}
              is running.
            </span>
          </div>
        )}

        <CreateScanForm onSubmit={createScan} />

        {activeScans.length > 0 && (
          <section className="space-y-3">
            <div className="flex items-center gap-3">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-widest">Active</span>
              <span className="flex-1 h-px bg-slate-800" />
              <span className="text-xs text-slate-500">{activeScans.length}</span>
            </div>
            {activeScans.map(s => <ScanCard key={s.id} scan={s} onCancel={cancelScan} />)}
          </section>
        )}

        {doneScans.length > 0 && (
          <section className="space-y-3">
            <div className="flex items-center gap-3">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-widest">Completed</span>
              <span className="flex-1 h-px bg-slate-800" />
              <span className="text-xs text-slate-500">{doneScans.length}</span>
            </div>
            {doneScans.map(s => <ScanCard key={s.id} scan={s} onCancel={cancelScan} />)}
          </section>
        )}

        {!serverError && scans.length === 0 && (
          <div className="text-center py-16">
            <div className="text-4xl mb-3 select-none">🏌️</div>
            <p className="text-slate-500 text-sm">No scans yet. Create one above.</p>
          </div>
        )}
      </main>
    </div>
  )
}
