import React from 'react'

type ErrorFallbackProps = {
  error: Error
  resetErrorBoundary: () => void
}

// Simple error boundary fallback used by `react-error-boundary`.
export function ErrorFallback({ error, resetErrorBoundary }: ErrorFallbackProps) {
  return (
    <div role="alert" style={{ padding: 20, fontFamily: 'Inter, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial' }}>
      <h2 style={{ marginTop: 0 }}>Something went wrong</h2>
      <pre style={{ whiteSpace: 'pre-wrap', color: '#721c24', background: '#f8d7da', padding: '10px', borderRadius: 6 }}>{error?.message ?? String(error)}</pre>
      <div style={{ marginTop: 12 }}>
        <button onClick={resetErrorBoundary} style={{ cursor: 'pointer', padding: '8px 12px', borderRadius: 6 }}>
          Try again
        </button>
      </div>
    </div>
  )
}
