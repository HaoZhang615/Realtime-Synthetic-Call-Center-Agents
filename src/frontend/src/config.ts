/**
 * Runtime configuration for the frontend
 * 
 * This allows environment variables to be injected at container startup time
 * rather than at build time, making the same Docker image work across environments.
 */

declare global {
  interface Window {
    ENV?: {
      VITE_API_BASE?: string
      VITE_REALTIME_API_BASE?: string
    }
  }
}

/**
 * Get the API base URL for the backend
 */
export function getApiBase(): string {
  // Runtime config (set by entrypoint.sh in production)
  if (window.ENV?.VITE_API_BASE) {
    return window.ENV.VITE_API_BASE
  }
  
  // Build-time config (for local development)
  if (import.meta.env?.VITE_API_BASE) {
    return import.meta.env.VITE_API_BASE as string
  }
  
  // Default: empty string means same origin (for local dev with proxy)
  return ''
}

/**
 * Get the Realtime API base URL
 */
export function getRealtimeApiBase(): string {
  // Runtime config (set by entrypoint.sh in production)
  if (window.ENV?.VITE_REALTIME_API_BASE) {
    return window.ENV.VITE_REALTIME_API_BASE
  }
  
  // Build-time config (for local development)
  if (import.meta.env?.VITE_REALTIME_API_BASE) {
    return import.meta.env.VITE_REALTIME_API_BASE as string
  }
  
  // Default: fall back to API_BASE
  return getApiBase()
}
