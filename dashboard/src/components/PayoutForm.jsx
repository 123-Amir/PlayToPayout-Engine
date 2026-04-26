import React, { useState } from 'react'
import axios from 'axios'
import { v4 as uuidv4 } from 'uuid'

function PayoutForm({ merchantId }) {
  const [formData, setFormData] = useState({
    amount_paise: '',
    bank_account_id: ''
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [message, setMessage] = useState('')

  const handleInputChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: value
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setIsSubmitting(true)
    setMessage('')

    try {
      const idempotencyKey = uuidv4()

      const payload = {
        merchant: merchantId,
        amount_paise: parseInt(formData.amount_paise),
        bank_account_id: formData.bank_account_id
      }

      const response = await axios.post(
        'http://localhost:8000/api/v1/payouts/',
        payload,
        {
          headers: {
            'Content-Type': 'application/json',
            'Idempotency-Key': idempotencyKey
          }
        }
      )

      setMessage(`✅ Payout created successfully! ID: ${response.data.payout_id}`)
      setFormData({ amount_paise: '', bank_account_id: '' })

    } catch (error) {
      console.error('Payout creation error:', error)
      if (error.response) {
        setMessage(`❌ Error: ${error.response.data.detail || 'Failed to create payout'}`)
      } else {
        setMessage('❌ Error: Unable to connect to server')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const formatCurrency = (paise) => {
    if (!paise) return '₹0.00'
    return `₹${(parseInt(paise) / 100).toFixed(2)}`
  }

  return (
    <div className="bg-white shadow rounded-lg">
      <div className="px-4 py-5 sm:p-6">
        <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
          Create New Payout
        </h3>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="amount_paise" className="block text-sm font-medium text-gray-700">
              Amount (in paise)
            </label>
            <div className="mt-1 relative rounded-md shadow-sm">
              <input
                type="number"
                name="amount_paise"
                id="amount_paise"
                required
                min="1"
                value={formData.amount_paise}
                onChange={handleInputChange}
                className="focus:ring-indigo-500 focus:border-indigo-500 block w-full pl-3 pr-12 sm:text-sm border-gray-300 rounded-md"
                placeholder="50000"
              />
              <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                <span className="text-gray-500 sm:text-sm">
                  {formatCurrency(formData.amount_paise)}
                </span>
              </div>
            </div>
            <p className="mt-1 text-sm text-gray-500">
              100 paise = ₹1.00
            </p>
          </div>

          <div>
            <label htmlFor="bank_account_id" className="block text-sm font-medium text-gray-700">
              Bank Account ID
            </label>
            <input
              type="text"
              name="bank_account_id"
              id="bank_account_id"
              required
              value={formData.bank_account_id}
              onChange={handleInputChange}
              className="mt-1 focus:ring-indigo-500 focus:border-indigo-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
              placeholder="ACC0012345678901"
            />
          </div>

          <div className="pt-4">
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? 'Creating Payout...' : 'Create Payout'}
            </button>
          </div>
        </form>

        {message && (
          <div className={`mt-4 p-4 rounded-md ${
            message.startsWith('✅')
              ? 'bg-green-50 text-green-800'
              : 'bg-red-50 text-red-800'
          }`}>
            <p className="text-sm">{message}</p>
          </div>
        )}

        <div className="mt-4 p-3 bg-gray-50 rounded-md">
          <p className="text-xs text-gray-500">
            <strong>Idempotency Key:</strong> Auto-generated UUID ensures safe retries
          </p>
        </div>
      </div>
    </div>
  )
}

export default PayoutForm