import { useState, useEffect } from 'react'
import axios from 'axios'

const API_BASE = 'http://localhost:8001'

const LAYER_LABELS: Record<string, string> = {
  fundamental: 'F — Fundamentals',
  growth: 'G — Growth Acceleration',
  quality: 'Q — Quality of Management',
  momentum: 'M — Market Microstructure',
  alternative: 'A — Alternative Data',
  technical: 'T — Technical Structure',
  llm: 'L — LLM Intelligence',
}

const LAYER_COLORS: Record<string, string> = {
  fundamental: 'from-blue-600 to-blue-800',
  growth: 'from-green-600 to-green-800',
  quality: 'from-purple-600 to-purple-800',
  momentum: 'from-orange-600 to-orange-800',
  alternative: 'from-cyan-600 to-cyan-800',
  technical: 'from-pink-600 to-pink-800',
  llm: 'from-yellow-600 to-yellow-800',
}

const COMPONENT_LABELS: Record<string, Record<string, string>> = {
  fundamental: {
    roce: 'ROCE',
    debt_equity: 'Debt/Equity',
    cashflow: 'Operating Cash Flow',
    margin_stability: 'Margin Stability',
    asset_turnover: 'Asset Turnover',
  },
  growth: {
    revenue_acceleration: 'Revenue Acceleration',
    pat_acceleration: 'PAT Acceleration',
    margin_expansion: 'Margin Expansion',
    cashflow_improvement: 'Cash Flow Improvement',
  },
  quality: {
    promoter_behavior: 'Promoter Behavior',
    capital_allocation: 'Capital Allocation',
    governance: 'Governance Score',
    cashflow_quality: 'Cash Flow Quality',
    insider_behavior: 'Insider Behavior',
    dilution: 'Dilution Score',
    compensation_quality: 'Compensation Quality',
  },
  momentum: {
    delivery_ratio: 'Delivery Ratio',
    float_absorption: 'Float Absorption',
    volume_anomaly: 'Volume Anomaly',
    vwap_defense: 'VWAP Defense',
    price_compression: 'Price Compression',
    seller_exhaustion: 'Seller Exhaustion',
    bulk_deal: 'Bulk Deal Signal',
  },
  alternative: {
    hiring: 'Hiring Score',
    government_contracts: 'Government Contracts',
    shipment: 'Shipment Score',
    patent: 'Patent Score',
    search_trend: 'Search Trend',
    sector_rotation: 'Sector Rotation',
    news_velocity: 'News Velocity',
  },
  technical: {
    relative_strength: 'Relative Strength',
    trend_strength: 'Trend Strength',
    compression: 'Compression Pattern',
    breakout_probability: 'Breakout Probability',
    volume_confirmation: 'Volume Confirmation',
  },
  llm: {
    annual_report: 'Annual Report Score',
    concall_analysis: 'Concall Analysis',
    sentiment: 'Sentiment Score',
    narrative_shift: 'Narrative Shift',
    risk_extraction: 'Risk Extraction',
    management_confidence: 'Management Confidence',
    governance_language: 'Governance Language',
  },
}

function scoreColor(s: number): string {
  if (s >= 80) return 'text-green-400'
  if (s >= 60) return 'text-yellow-400'
  if (s >= 40) return 'text-orange-400'
  return 'text-red-400'
}

function scoreBg(s: number): string {
  if (s >= 80) return 'bg-green-500'
  if (s >= 60) return 'bg-yellow-500'
  if (s >= 40) return 'bg-orange-500'
  return 'bg-red-500'
}

function formatRaw(raw: any): string {
  if (raw === null || raw === undefined || raw === '') return '-'
  if (typeof raw === 'boolean') return raw ? 'Yes' : 'No'
  if (typeof raw === 'object') return JSON.stringify(raw)
  if (typeof raw === 'number') {
    if (Math.abs(raw) >= 1_00_00_000) return (raw / 1_00_00_000).toFixed(2) + 'Cr'
    if (Math.abs(raw) >= 1_00_000) return (raw / 1_00_000).toFixed(2) + 'L'
    if (Math.abs(raw) >= 1000) return raw.toLocaleString()
    return raw.toFixed(2)
  }
  return String(raw)
}

interface BreakdownData {
  symbol: string
  company_name: string
  total_score: number
  composite: number
  penalty: number
  passed_elimination: boolean
  elimination_stages: string[]
  layers: Record<string, {
    score: number
    weight: number
    weighted: number
    components: Record<string, { raw: any; score: number; weight: number }>
  }>
}

export default function StockBreakdownModal({
  symbol,
  onClose,
}: {
  symbol: string
  onClose: () => void
}) {
  const [data, setData] = useState<BreakdownData | null>(null)
  const [loading, setLoading] = useState(true)
  const [expandedLayer, setExpandedLayer] = useState<string | null>(null)

  useEffect(() => {
    axios.get(`${API_BASE}/stock/${symbol}/breakdown`)
      .then(res => setData(res.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [symbol])

  return (
    <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center p-4 z-50" onClick={onClose}>
      <div
        className="bg-gray-900 rounded-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        {loading ? (
          <div className="p-8 text-center text-gray-400">Loading breakdown...</div>
        ) : !data ? (
          <div className="p-8 text-center text-red-400">Failed to load breakdown for {symbol}</div>
        ) : (
          <>
            {/* Header */}
            <div className="sticky top-0 bg-gray-900 border-b border-gray-700 p-6 flex items-start justify-between">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-2xl font-bold">{data.symbol}</h2>
                  <span className="text-gray-400">{data.company_name}</span>
                </div>
                <div className="flex items-center gap-4 mt-2">
                  <span className={`text-4xl font-bold ${scoreColor(data.total_score)}`}>
                    {data.total_score.toFixed(1)}
                  </span>
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${data.passed_elimination ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}`}>
                    {data.passed_elimination ? '✓ Passed' : '✗ Eliminated'}
                  </span>
                  {data.penalty > 0 && (
                    <span className="text-sm text-red-400">Penalty: -{data.penalty}</span>
                  )}
                </div>
              </div>
              <button onClick={onClose} className="text-gray-400 hover:text-white text-3xl leading-none">&times;</button>
            </div>

            {/* Layer Scores */}
            <div className="p-6 space-y-4">
              {Object.entries(data.layers).map(([key, layer]) => (
                <div key={key} className="bg-gray-800 rounded-lg overflow-hidden">
                  {/* Layer header - always visible */}
                  <button
                    className={`w-full flex items-center justify-between p-4 bg-gradient-to-r ${LAYER_COLORS[key]} transition-colors`}
                    onClick={() => setExpandedLayer(expandedLayer === key ? null : key)}
                  >
                    <div className="flex items-center gap-4">
                      <span className="font-semibold">{LAYER_LABELS[key] || key}</span>
                      <div className="flex items-center gap-2 text-sm">
                        <span>score</span>
                        <span className={`font-bold text-lg ${scoreColor(layer.score)}`}>
                          {layer.score.toFixed(1)}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-sm text-gray-300">
                        × {layer.weight} = <span className="font-bold text-white">{layer.weighted.toFixed(2)}</span>
                      </span>
                      <span className={`transform transition-transform ${expandedLayer === key ? 'rotate-180' : ''}`}>
                        &#9660;
                      </span>
                    </div>
                  </button>

                  {/* Expanded components */}
                  {expandedLayer === key && (
                    <div className="p-4 space-y-2">
                      <div className="grid grid-cols-4 gap-2 text-xs text-gray-500 font-medium px-2 pb-1 border-b border-gray-700">
                        <span>Component</span>
                        <span className="text-right">Raw Value</span>
                        <span className="text-right">Score</span>
                        <span className="text-right">Weight × Score</span>
                      </div>
                      {Object.entries(layer.components).map(([cname, comp]) => {
                        const label = COMPONENT_LABELS[key]?.[cname] || cname
                        const contrib = (comp.score * comp.weight)
                        return (
                          <div key={cname} className="grid grid-cols-4 gap-2 text-sm px-2 py-1.5 rounded hover:bg-gray-700">
                            <span className="text-gray-300 font-medium truncate" title={label}>{label}</span>
                            <span className="text-right text-gray-400 font-mono">{formatRaw(comp.raw)}</span>
                            <span className={`text-right font-mono font-medium ${scoreColor(comp.score)}`}>
                              {comp.score}
                            </span>
                            <span className="text-right text-gray-300 font-mono">
                              {comp.weight} × {comp.score} = <span className="font-bold">{contrib.toFixed(1)}</span>
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Score bar */}
            <div className="px-6 pb-6">
              <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
                <div
                  className={`h-full rounded-full ${scoreBg(data.total_score)} transition-all duration-500`}
                  style={{ width: `${data.total_score}%` }}
                />
              </div>
              <div className="flex justify-between mt-1 text-xs text-gray-500">
                <span>0</span>
                <span>25</span>
                <span>50</span>
                <span>75</span>
                <span>100</span>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}