import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { TrendingUp, Activity, Database, Zap, RefreshCw, Search } from 'lucide-react'
import axios from 'axios'

const API_BASE = 'http://localhost:8001'

interface Stock {
  symbol: string
  company_name: string
  total_score?: number | null
  returns_1y?: number | null
  returns_6m?: number | null
  volume_ratio?: number | null
  passed_elimination?: boolean | null
  elimination_stages?: string[] | null
}

export default function Dashboard() {
  const [stocks, setStocks] = useState<Stock[]>([])
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState({ stocks: 0, prices: 0, passed: 0, eliminated: 0 })
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null)
  const [search, setSearch] = useState('')

  useEffect(() => {
    fetchStats()
    fetchLatestScan()
  }, [])

  const fetchStats = async () => {
    try {
      const universeRes = await axios.get(`${API_BASE}/stocks/universe`)
      setStats(prev => ({
        ...prev,
        stocks: universeRes.data.total_stocks || 0,
        prices: universeRes.data.total_prices || 0
      }))
    } catch (error) {
      console.error('Failed to fetch stats:', error)
    }
  }

  const fetchLatestScan = async () => {
    try {
      const response = await axios.get(`${API_BASE}/stocks/scored?limit=2394`)
      if (response.data.stocks?.length > 0) {
        setStocks(response.data.stocks)
        const passed = response.data.stocks.filter((s: Stock) => s.passed_elimination).length
        const eliminated = response.data.stocks.length - passed
        setStats(prev => ({ ...prev, passed, eliminated }))
      }
    } catch (error) {
      console.error('Failed to fetch latest scan:', error)
    }
  }

  const runScan = async () => {
    setLoading(true)
    try {
      const response = await axios.get(`${API_BASE}/scan/run`)
      const result = response.data
      if (result.status === 'success') {
        await fetchLatestScan()
        setStats(prev => ({ ...prev, stocks: result.processed || prev.stocks }))
      }
    } catch (error) {
      console.error('Scan failed:', error)
      alert('Scan failed. Check server logs.')
    } finally {
      setLoading(false)
    }
  }

  const filteredStocks = stocks.filter(s =>
    s.symbol.toLowerCase().includes(search.toLowerCase()) ||
    s.company_name?.toLowerCase().includes(search.toLowerCase())
  )
  const topStocks = filteredStocks.slice(0, 10)

  const scoreDistribution = [
    { range: '0-20', count: stocks.filter(s => (s.total_score ?? 0) < 20).length },
    { range: '20-40', count: stocks.filter(s => (s.total_score ?? 0) >= 20 && (s.total_score ?? 0) < 40).length },
    { range: '40-60', count: stocks.filter(s => (s.total_score ?? 0) >= 40 && (s.total_score ?? 0) < 60).length },
    { range: '60-80', count: stocks.filter(s => (s.total_score ?? 0) >= 60 && (s.total_score ?? 0) < 80).length },
    { range: '80-100', count: stocks.filter(s => (s.total_score ?? 0) >= 80).length },
  ]

  const COLORS = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#10b981']

  return (
    <div>
      <div className="mb-8">
        <h2 className="text-3xl font-bold mb-2">Dashboard</h2>
        <p className="text-gray-400">Real-time alpha scoring across Indian equities</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
        <div className="bg-gray-800 rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm">Stocks Analyzed</p>
              <p className="text-3xl font-bold">{stats.stocks}</p>
            </div>
            <Database className="w-8 h-8 text-blue-500" />
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm">Price Records</p>
              <p className="text-3xl font-bold">{stats.prices.toLocaleString()}</p>
            </div>
            <Activity className="w-8 h-8 text-green-500" />
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm">Passed Elimination</p>
              <p className="text-3xl font-bold text-green-400">{stats.passed}</p>
            </div>
            <TrendingUp className="w-8 h-8 text-green-500" />
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm">Eliminated</p>
              <p className="text-3xl font-bold text-red-400">{stats.eliminated}</p>
            </div>
            <Zap className="w-8 h-8 text-red-500" />
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm">Top Score</p>
              <p className="text-3xl font-bold text-yellow-400">{(topStocks[0]?.total_score ?? 0).toFixed(1)}</p>
            </div>
            <TrendingUp className="w-8 h-8 text-yellow-500" />
          </div>
        </div>
      </div>

      <div className="flex gap-4 mb-8">
        <button
          onClick={runScan}
          disabled={loading}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-6 py-3 rounded-lg font-semibold transition-colors"
        >
          <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          {loading ? 'Scanning...' : 'Run New Scan'}
        </button>
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search stocks..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-10 pr-4 py-3 focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 bg-gray-800 rounded-lg p-6">
          <h3 className="text-xl font-bold mb-4">Top 10 Ranked Stocks</h3>
          <div className="space-y-3">
            {topStocks.map((stock, index) => (
              <div
                key={stock.symbol}
                onClick={() => setSelectedStock(stock)}
                className="flex items-center justify-between p-4 bg-gray-700 rounded-lg hover:bg-gray-600 cursor-pointer transition-colors"
              >
                <div className="flex items-center gap-4">
                  <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center font-bold">
                    {index + 1}
                  </div>
                  <div>
                    <p className="font-semibold">{stock.symbol}</p>
                    <p className="text-sm text-gray-400">{stock.company_name}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold text-green-400">{(stock.total_score ?? 0).toFixed(1)}</p>
                  <p className="text-sm text-gray-400">
                    1Y: {stock.returns_1y?.toFixed(1)}% | 6M: {stock.returns_6m?.toFixed(1)}%
                  </p>
                  <p className={`text-xs ${stock.passed_elimination ? 'text-green-500' : 'text-red-500'}`}>
                    {stock.passed_elimination ? '✓ Passed' : '✗ Eliminated'}
                  </p>
                  {!stock.passed_elimination && stock.elimination_stages && (
                    <p className="text-xs text-red-400 mt-1 max-w-[200px] truncate" title={stock.elimination_stages.find(s => s.startsWith('FAILED')) || ''}>
                      {stock.elimination_stages.find(s => s.startsWith('FAILED'))?.replace('FAILED: ', '') || ''}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-xl font-bold mb-4">Score Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={scoreDistribution}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ range, count }) => `${range}: ${count}`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="count"
              >
                {scoreDistribution.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="mt-8 bg-gray-800 rounded-lg p-6">
        <h3 className="text-xl font-bold mb-4">Top 10 Performance Comparison</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={topStocks}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="symbol" stroke="#9ca3af" />
            <YAxis stroke="#9ca3af" />
            <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: 'none' }} />
            <Bar dataKey="total_score" fill="#3b82f6" name="Alpha Score" />
            <Bar dataKey="returns_1y" fill="#10b981" name="1Y Return %" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {selectedStock && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-gray-800 rounded-lg p-8 max-w-2xl w-full">
            <div className="flex justify-between items-start mb-6">
              <div>
                <h3 className="text-3xl font-bold">{selectedStock.symbol}</h3>
                <p className="text-gray-400">{selectedStock.company_name}</p>
              </div>
              <button onClick={() => setSelectedStock(null)} className="text-gray-400 hover:text-white text-2xl">×</button>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-700 rounded-lg p-4">
                <p className="text-gray-400 text-sm">Alpha Score</p>
                <p className="text-3xl font-bold text-green-400">{(selectedStock.total_score ?? 0).toFixed(1)}</p>
              </div>
              <div className="bg-gray-700 rounded-lg p-4">
                <p className="text-gray-400 text-sm">Volume Ratio</p>
                <p className="text-3xl font-bold">{selectedStock.volume_ratio?.toFixed(2)}x</p>
              </div>
              <div className="bg-gray-700 rounded-lg p-4">
                <p className="text-gray-400 text-sm">1 Year Return</p>
                <p className="text-3xl font-bold text-blue-400">{selectedStock.returns_1y?.toFixed(1)}%</p>
              </div>
              <div className="bg-gray-700 rounded-lg p-4">
                <p className="text-gray-400 text-sm">6 Month Return</p>
                <p className="text-3xl font-bold text-purple-400">{selectedStock.returns_6m?.toFixed(1)}%</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
