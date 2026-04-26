import React, { useState } from 'react'
import BalanceCard from './components/BalanceCard'
import PayoutForm from './components/PayoutForm'
import PayoutHistoryTable from './components/PayoutHistoryTable'

function App() {
  const [selectedMerchant, setSelectedMerchant] = useState(1) // Default to first merchant

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <h1 className="text-3xl font-bold text-gray-900">PlayToPayout Dashboard</h1>
            <div className="flex items-center space-x-4">
              <select
                value={selectedMerchant}
                onChange={(e) => setSelectedMerchant(parseInt(e.target.value))}
                className="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
              >
                <option value={1}>TechCorp Solutions</option>
                <option value={2}>DigitalMart E-commerce</option>
                <option value={3}>ServiceHub Providers</option>
              </select>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Balance Card */}
          <div className="lg:col-span-1">
            <BalanceCard merchantId={selectedMerchant} />
          </div>

          {/* Payout Form */}
          <div className="lg:col-span-1">
            <PayoutForm merchantId={selectedMerchant} />
          </div>

          {/* Payout History */}
          <div className="lg:col-span-3">
            <PayoutHistoryTable merchantId={selectedMerchant} />
          </div>
        </div>
      </main>
    </div>
  )
}

export default App