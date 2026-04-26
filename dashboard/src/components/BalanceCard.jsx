import React from 'react'
import useSWR from 'swr'
import axios from 'axios'

const fetcher = (url) => axios.get(url).then(res => res.data)

function BalanceCard({ merchantId }) {
  const { data, error, isLoading } = useSWR(
    `http://localhost:8000/api/v1/merchants/${merchantId}/balance/`,
    fetcher,
    {
      refreshInterval: 2000, // Refresh every 2 seconds
      revalidateOnFocus: true,
    }
  )

  if (error) {
    return (
      <div className="bg-white overflow-hidden shadow rounded-lg">
        <div className="p-5">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="w-8 h-8 bg-red-500 rounded-full flex items-center justify-center">
                <span className="text-white text-sm font-medium">!</span>
              </div>
            </div>
            <div className="ml-5 w-0 flex-1">
              <dl>
                <dt className="text-sm font-medium text-gray-500 truncate">
                  Balance Error
                </dt>
                <dd className="text-lg font-medium text-gray-900">
                  Unable to load balance
                </dd>
              </dl>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (isLoading || !data) {
    return (
      <div className="bg-white overflow-hidden shadow rounded-lg">
        <div className="p-5">
          <div className="animate-pulse">
            <div className="flex items-center">
              <div className="w-8 h-8 bg-gray-300 rounded-full"></div>
              <div className="ml-5 w-full">
                <div className="h-4 bg-gray-300 rounded w-3/4 mb-2"></div>
                <div className="h-6 bg-gray-300 rounded w-1/2"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const formatCurrency = (paise) => {
    return `₹${(paise / 100).toFixed(2)}`
  }

  return (
    <div className="bg-white overflow-hidden shadow rounded-lg">
      <div className="p-5">
        <div className="flex items-center">
          <div className="flex-shrink-0">
            <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
              <span className="text-white text-sm font-medium">₹</span>
            </div>
          </div>
          <div className="ml-5 w-0 flex-1">
            <dl>
              <dt className="text-sm font-medium text-gray-500 truncate">
                {data.name}
              </dt>
              <dd className="text-lg font-medium text-gray-900">
                {formatCurrency(data.available_balance)}
              </dd>
            </dl>
          </div>
        </div>
      </div>
      <div className="bg-gray-50 px-5 py-3">
        <div className="text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500">Available:</span>
            <span className="font-medium text-green-600">{formatCurrency(data.available_balance)}</span>
          </div>
          <div className="flex justify-between mt-1">
            <span className="text-gray-500">Held:</span>
            <span className="font-medium text-orange-600">{formatCurrency(data.held_balance)}</span>
          </div>
          <div className="flex justify-between mt-1 pt-1 border-t border-gray-200">
            <span className="text-gray-500">Total:</span>
            <span className="font-medium text-gray-900">{formatCurrency(data.total_balance)}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default BalanceCard