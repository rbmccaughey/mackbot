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
    <div className="min-h-screen bg-gray-50">
      <header className="bg-green-800 text-white px-6 py-5">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-2xl font-bold tracking-tight">mackbot</h1>
          <p className="text-green-300 text-sm mt-0.5">Kananaskis tee time scanner</p>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-6 space-y-6">
        {serverError && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
            Cannot reach the server — make sure <code className="font-mono text-xs bg-red-100 px-1 rounded">uvicorn server:app --reload</code> is running.
          </div>
        )}

        <CreateScanForm onSubmit={createScan} />

        {activeScans.length > 0 && (
          <section>
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Active</h2>
            <div className="space-y-3">
              {activeScans.map(s => <ScanCard key={s.id} scan={s} onCancel={cancelScan} />)}
            </div>
          </section>
        )}

        {doneScans.length > 0 && (
          <section>
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Completed</h2>
            <div className="space-y-3">
              {doneScans.map(s => <ScanCard key={s.id} scan={s} onCancel={cancelScan} />)}
            </div>
          </section>
        )}

        {!serverError && scans.length === 0 && (
          <p className="text-center text-gray-400 py-12 text-sm">No scans yet.</p>
        )}
      </main>
    </div>
  )
}
