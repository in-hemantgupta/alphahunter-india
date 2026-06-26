import { useState, useEffect } from 'react'
import axios from 'axios'

const API_BASE = 'http://localhost:8001'

interface Rebalance {
  date: string
  symbol: string
  old_weight: number
  new_weight: number
  reason: string
}

interface PortfolioItem {
  symbol: string
  company_name: string
  weight: number
  score: number
}

export default function Rebalancing() {
  const [rebalances, setRebalances] = useState<Rebalance[]>([])
  const [portfolio, setPortfolio] = useState<PortfolioItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [rebRes, portRes] = await Promise.all([
        axios.get(`${API_BASE}/rebalancing`),
        axios.get(`${API_BASE}/portfolio/current`)
      ])
      setRebalances(rebRes.data.rebalances || [])
      setPortfolio(portRes.data.portfolio || [])
    } catch (error) {
      console.error('Failed to fetch data:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="mb-8">
        <h2 className="text-3xl font-bold mb-2">Portfolio & Rebalancing</h2>
        <p className="text-gray-400">Current allocation and rebalance history</p>
      </div>

      {loading ? (
        <p className="text-gray-400">Loading...</p>
      ) : (
        <>
          <div className="bg-gray-800 rounded-lg p-6 mb-8">
            <h3 className="text-xl font-bold mb-4">Current Portfolio (Top 10)</h3>
            {portfolio.length === 0 ? (
              <p className="text-gray-400">Run a scan to generate portfolio</p>
            ) : (
              <div className="space-y-3">
                {portfolio.map((item) => (
                  <div key={item.symbol} className="flex items-center justify-between p-3 bg-gray-700 rounded-lg">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center text-sm font-bold">
                        {item.weight.toFixed(0)}%
                      </div>
                      <div>
                        <p className="font-semibold">{item.symbol}</p>
                        <p className="text-sm text-gray-400">{item.company_name}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-bold text-green-400">{item.score.toFixed(1)}</p>
                      <p className="text-xs text-gray-400">alpha score</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-gray-800 rounded-lg p-6">
            <h3 className="text-xl font-bold mb-4">Rebalance History</h3>
            {rebalances.length === 0 ? (
              <p className="text-gray-400">No rebalance events yet</p>
            ) : (
              <table className="w-full">
                <thead className="text-gray-400 text-sm">
                  <tr>
                    <th className="text-left p-3">Date</th>
                    <th className="text-left p-3">Symbol</th>
                    <th className="text-left p-3">Old Weight</th>
                    <th className="text-left p-3">New Weight</th>
                    <th className="text-left p-3">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {rebalances.map((r, i) => (
                    <tr key={i} className="border-t border-gray-700">
                      <td className="p-3">{r.date}</td>
                      <td className="p-3 font-semibold">{r.symbol}</td>
                      <td className="p-3">{r.old_weight?.toFixed(2)}%</td>
                      <td className="p-3">{r.new_weight?.toFixed(2)}%</td>
                      <td className="p-3 text-gray-400">{r.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  )
}
