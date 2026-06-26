import { useState, useEffect } from 'react'
import { RefreshCw } from 'lucide-react'
import axios from 'axios'

const API_BASE = 'http://localhost:8001'

interface ScanRecord {
  date: string
  symbol: string
  allocation: number
  score: number
}

export default function ScanHistory() {
  const [history, setHistory] = useState<ScanRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [lastScan, setLastScan] = useState<{ processed: number; ranked: number } | null>(null)

  useEffect(() => {
    fetchHistory()
  }, [])

  const fetchHistory = async () => {
    try {
      const response = await axios.get(`${API_BASE}/scan/history`)
      setHistory(response.data.history || [])
    } catch (error) {
      console.error('Failed to fetch history:', error)
    } finally {
      setLoading(false)
    }
  }

  const runScan = async () => {
    setScanning(true)
    try {
      const response = await axios.get(`${API_BASE}/scan/run`)
      const result = response.data
      setLastScan({
        processed: result.processed || 0,
        ranked: result.ranked?.length || 0
      })
      fetchHistory()
    } catch (error) {
      console.error('Scan failed:', error)
      alert('Scan failed')
    } finally {
      setScanning(false)
    }
  }

  const groupedByDate = history.reduce((acc, r) => {
    if (!acc[r.date]) acc[r.date] = []
    acc[r.date].push(r)
    return acc
  }, {} as Record<string, ScanRecord[]>)

  return (
    <div>
      <div className="flex justify-between items-start mb-8">
        <div>
          <h2 className="text-3xl font-bold mb-2">Scan History</h2>
          <p className="text-gray-400">{history.length} historical records</p>
        </div>
        <button
          onClick={runScan}
          disabled={scanning}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-6 py-3 rounded-lg font-semibold transition-colors"
        >
          <RefreshCw className={`w-5 h-5 ${scanning ? 'animate-spin' : ''}`} />
          {scanning ? 'Scanning...' : 'Run Scan'}
        </button>
      </div>

      {lastScan && (
        <div className="bg-green-900 bg-opacity-30 border border-green-700 rounded-lg p-4 mb-6">
          <p className="text-green-400 font-semibold">
            Last scan: {lastScan.processed} stocks processed, {lastScan.ranked} ranked
          </p>
        </div>
      )}

      {loading ? (
        <p className="text-gray-400">Loading...</p>
      ) : history.length === 0 ? (
        <div className="bg-gray-800 rounded-lg p-12 text-center">
          <p className="text-gray-400 mb-4">No scan history yet</p>
          <p className="text-gray-500 text-sm">Run a scan to populate history</p>
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(groupedByDate).map(([date, records]) => (
            <div key={date} className="bg-gray-800 rounded-lg p-6">
              <h3 className="text-lg font-bold mb-4">{date}</h3>
              <table className="w-full">
                <thead className="text-gray-400 text-sm">
                  <tr>
                    <th className="text-left p-2">Symbol</th>
                    <th className="text-left p-2">Score</th>
                    <th className="text-left p-2">Allocation</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((r) => (
                    <tr key={r.symbol} className="border-t border-gray-700">
                      <td className="p-2 font-semibold">{r.symbol}</td>
                      <td className="p-2 text-green-400">{r.score?.toFixed(1)}</td>
                      <td className="p-2">{r.allocation?.toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
