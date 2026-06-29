import { useState, useEffect } from 'react'
import { Search } from 'lucide-react'
import axios from 'axios'

const API_BASE = 'http://localhost:8001'

interface Stock {
  symbol: string
  company_name: string
  sector?: string
  exchange?: string
  total_score?: number | null
  returns_1y?: number | null
  returns_6m?: number | null
  volume_ratio?: number | null
  current_price?: number
  passed_elimination?: boolean | null
  elimination_stages?: string[] | null
}

export default function Universe() {
  const [stocks, setStocks] = useState<Stock[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [sortKey, setSortKey] = useState<keyof Stock>('total_score')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  useEffect(() => {
    fetchUniverse()
  }, [])

  const fetchUniverse = async () => {
    try {
      const [universeRes, scoredRes] = await Promise.all([
        axios.get(`${API_BASE}/stocks/universe`),
        axios.get(`${API_BASE}/stocks/scored?limit=2394`)
      ])
      const allStocks = universeRes.data.universe || []
      const scoredStocks = scoredRes.data.stocks || []
      
      // Create a map of scored stocks for quick lookup
      const scoredMap = new Map(scoredStocks.map(s => [s.symbol, s]))
      
      // Merge: all stocks with scores where available
      const merged = allStocks.map((s: any) => {
        const scored = scoredMap.get(s.symbol)
        return {
          ...s,
          total_score: scored?.total_score ?? null,
          returns_1y: scored?.returns_1y ?? null,
          returns_6m: scored?.returns_6m ?? null,
          volume_ratio: scored?.volume_ratio ?? null,
          current_price: scored?.current_price ?? null,
          passed_elimination: scored?.passed_elimination ?? null,
          elimination_stages: scored?.elimination_stages ?? null
        }
      })
      
      setStocks(merged)
    } catch (error) {
      console.error('Failed to fetch universe:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSort = (key: keyof Stock) => {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const filtered = stocks
    .filter(s =>
      s.symbol.toLowerCase().includes(search.toLowerCase()) ||
      s.company_name?.toLowerCase().includes(search.toLowerCase())
    )
    .sort((a, b) => {
      const aVal = a[sortKey] ?? 0
      const bVal = b[sortKey] ?? 0
      const cmp = typeof aVal === 'string' ? aVal.localeCompare(bVal as string) : (aVal as number) - (bVal as number)
      return sortDir === 'asc' ? cmp : -cmp
    })

  const SortHeader = ({ label, field }: { label: string; field: keyof Stock }) => (
    <th
      className="text-left p-3 cursor-pointer hover:text-white transition-colors"
      onClick={() => handleSort(field)}
    >
      {label} {sortKey === field && (sortDir === 'asc' ? '↑' : '↓')}
    </th>
  )

  return (
    <div>
      <div className="mb-8">
        <h2 className="text-3xl font-bold mb-2">Stock Universe</h2>
        <p className="text-gray-400">{stocks.length} stocks in database</p>
      </div>

      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
        <input
          type="text"
          placeholder="Filter by symbol or company name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-10 pr-4 py-3 focus:outline-none focus:border-blue-500"
        />
      </div>

      {loading ? (
        <p className="text-gray-400">Loading...</p>
      ) : (
        <div className="bg-gray-800 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-700 text-gray-400 text-sm">
              <tr>
                <SortHeader label="Symbol" field="symbol" />
                <SortHeader label="Company" field="company_name" />
                <SortHeader label="Score" field="total_score" />
                <SortHeader label="Status" field="passed_elimination" />
                <SortHeader label="Price" field="current_price" />
                <SortHeader label="1Y Return" field="returns_1y" />
                <SortHeader label="6M Return" field="returns_6m" />
                <SortHeader label="Vol Ratio" field="volume_ratio" />
                <th className="text-left p-3 text-gray-400">Elimination Reason</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((stock, i) => (
                <tr key={stock.symbol} className={`border-t border-gray-700 ${i % 2 === 0 ? 'bg-gray-800' : 'bg-gray-700/50'} hover:bg-gray-600 transition-colors`}>
                  <td className="p-3 font-semibold">{stock.symbol}</td>
                  <td className="p-3 text-gray-400">{stock.company_name}</td>
                  <td className="p-3">
                    <span className={`font-bold ${(stock.total_score ?? 0) >= 60 ? 'text-green-400' : (stock.total_score ?? 0) >= 40 ? 'text-yellow-400' : 'text-red-400'}`}>
                      {(stock.total_score ?? 0).toFixed(1)}
                    </span>
                  </td>
                  <td className="p-3">
                    <span className={`text-sm font-medium ${stock.passed_elimination ? 'text-green-400' : 'text-red-400'}`}>
                      {stock.passed_elimination ? '✓ Passed' : '✗ Eliminated'}
                    </span>
                  </td>
                  <td className="p-3">{stock.current_price?.toFixed(2) || '-'}</td>
                  <td className={`p-3 ${(stock.returns_1y ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {(stock.returns_1y ?? 0).toFixed(1)}%
                  </td>
                  <td className={`p-3 ${(stock.returns_6m ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {(stock.returns_6m ?? 0).toFixed(1)}%
                  </td>
                  <td className="p-3">{(stock.volume_ratio ?? 0).toFixed(2)}x</td>
                  <td className="p-3 text-xs text-red-400 max-w-[200px] truncate" title={(!stock.passed_elimination && stock.elimination_stages?.find(s => s.startsWith('FAILED'))?.replace('FAILED: ', '')) || ''}>
                    {!stock.passed_elimination && stock.elimination_stages?.find(s => s.startsWith('FAILED'))?.replace('FAILED: ', '') || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <p className="text-center text-gray-400 py-8">No stocks match your filter</p>
          )}
        </div>
      )}
    </div>
  )
}
