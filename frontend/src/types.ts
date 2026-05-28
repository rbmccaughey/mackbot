export type ScanStatus = 'scanning' | 'found' | 'booked' | 'failed' | 'cancelled'

export interface Scan {
  id: string
  date: string
  time_from: string
  time_to: string
  players: number
  courses: number[]
  interval: number
  status: ScanStatus
  log: string[]
  created_at: string
}

export interface CreateScanPayload {
  date: string
  time_from: string
  time_to: string
  players: number
  courses: number[]
  interval: number
}
