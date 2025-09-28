import { useState, useCallback, useEffect, useRef } from 'react'

interface TokenResponse {
  websocket_url: string
  api_version: string
  deployment: string
  token: string
  expires_at: string
  ttl_seconds: number
}

export interface RealtimeConfig {
  token: string
  websocketUrl: string
  deployment: string
  apiVersion: string
  expiresAt: Date
  ttlSeconds: number
}

const DEFAULT_API_BASE = (import.meta as any).env?.VITE_API_BASE || ''
const REALTIME_API_BASE =
  (import.meta as any).env?.VITE_REALTIME_API_BASE || DEFAULT_API_BASE
const TOKEN_ENDPOINT = `${REALTIME_API_BASE}/api/realtime/token`
const REFRESH_MARGIN_SECONDS = 5

export interface UseRealtimeTokenResult {
  config: RealtimeConfig | null
  loading: boolean
  error: string | null
  refresh: () => Promise<RealtimeConfig | null>
  clear: () => void
}

export function useRealtimeToken(autoRefresh = false): UseRealtimeTokenResult {
  const [config, setConfig] = useState<RealtimeConfig | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const refreshTimer = useRef<number | null>(null)
  const refreshRef = useRef<(() => Promise<RealtimeConfig | null>) | null>(null)

  const clearRefreshTimer = useCallback(() => {
    if (refreshTimer.current !== null) {
      window.clearTimeout(refreshTimer.current)
      refreshTimer.current = null
    }
  }, [])

  const scheduleRefresh = useCallback((ttlSeconds: number) => {
    clearRefreshTimer()

    if (!ttlSeconds || Number.isNaN(ttlSeconds)) {
      return
    }

    const refreshDelay = Math.max(ttlSeconds - REFRESH_MARGIN_SECONDS, 5) * 1000
    refreshTimer.current = window.setTimeout(() => {
      void refreshRef.current?.()
    }, refreshDelay)
  }, [clearRefreshTimer])

  const refresh = useCallback(async (): Promise<RealtimeConfig | null> => {
    try {
      setLoading(true)
      setError(null)

      const response = await fetch(TOKEN_ENDPOINT, { method: 'POST' })

      if (!response.ok) {
        throw new Error(`Token request failed: ${response.status} ${response.statusText}`)
      }

      const data: TokenResponse = await response.json()
      const expiresAt = new Date(data.expires_at)

      const nextConfig: RealtimeConfig = {
        token: data.token,
        websocketUrl: data.websocket_url,
        deployment: data.deployment,
        apiVersion: data.api_version,
        expiresAt,
        ttlSeconds: data.ttl_seconds
      }

      setConfig(nextConfig)
      scheduleRefresh(data.ttl_seconds)
      return nextConfig
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch realtime token'
      setError(errorMessage)
      console.error('Realtime token fetch error:', err)
      return null
    } finally {
      setLoading(false)
    }
  }, [scheduleRefresh])

  useEffect(() => {
    refreshRef.current = refresh
  }, [refresh])

  const clear = useCallback(() => {
    clearRefreshTimer()
    setConfig(null)
    setError(null)
  }, [clearRefreshTimer])

  useEffect(() => {
    if (autoRefresh && !config && !loading) {
      void refresh()
    }
  }, [autoRefresh, config, loading, refresh])

  useEffect(() => () => clearRefreshTimer(), [clearRefreshTimer])

  return {
    config,
    loading,
    error,
    refresh,
    clear
  }
}