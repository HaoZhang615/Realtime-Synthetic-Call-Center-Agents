import { useState, useCallback } from 'react'
import { getApiBase, getRealtimeApiBase } from '@/config'

interface TokenResponse {
  access_token: string
  expires_on: number
  websocket_url: string
  deployment: string
  api_version: string
}

export interface RealtimeConfig {
  token: string
  websocketUrl: string
  deployment: string
  apiVersion: string
}

export function useRealtimeToken() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchRealtimeConfig = useCallback(async (): Promise<RealtimeConfig | undefined> => {
    try {
      setLoading(true)
      setError(null)
      
      const REALTIME_API_BASE = getRealtimeApiBase()
      const TOKEN_ENDPOINT = `${REALTIME_API_BASE}/api/realtime/token`

      const res = await fetch(TOKEN_ENDPOINT, { method: 'POST' })

      if (!res.ok) {
        throw new Error(`Token request failed: ${res.status} ${res.statusText}`)
      }

      const data: TokenResponse = await res.json()
      return {
        token: data.access_token,
        websocketUrl: data.websocket_url,
        deployment: data.deployment,
        apiVersion: data.api_version
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch realtime config'
      setError(errorMessage)
      console.error('Realtime config fetch error:', err)
      return undefined
    } finally {
      setLoading(false)
    }
  }, [])

  return { fetchRealtimeConfig, loading, error }
}