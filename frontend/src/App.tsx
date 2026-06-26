import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Universe from './pages/Universe'
import ScanHistory from './pages/ScanHistory'
import Rebalancing from './pages/Rebalancing'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/universe" element={<Universe />} />
          <Route path="/scan-history" element={<ScanHistory />} />
          <Route path="/rebalancing" element={<Rebalancing />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
