import { useEffect, useState } from 'react'

interface AudioVisualizerProps {
  isActive: boolean
  audioLevel: number
}

export function AudioVisualizer({ isActive, audioLevel }: AudioVisualizerProps) {
  const [bars, setBars] = useState<number[]>(Array(20).fill(0))

  useEffect(() => {
    if (!isActive) {
      setBars(Array(20).fill(0))
      return
    }

    const interval = setInterval(() => {
      setBars(prev => prev.map(() => Math.random() * 100))
    }, 100)

    return () => clearInterval(interval)
  }, [isActive])

  return (
    <div className="space-y-4">
      {/* Waveform Visualizer */}
      <div className="flex items-end justify-center gap-1 h-24">
        {bars.map((height, index) => (
          <div
            key={index}
            className={`w-2 rounded-full transition-all duration-100 ${
              isActive 
                ? 'bg-primary' 
                : 'bg-muted-foreground/20'
            }`}
            style={{
              height: isActive ? `${Math.max(height, 10)}%` : '10%'
            }}
          />
        ))}
      </div>

      {/* Status Indicator */}
      <div className="text-center">
        <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs ${
          isActive 
            ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' 
            : 'bg-muted text-muted-foreground'
        }`}>
          <div className={`w-2 h-2 rounded-full ${
            isActive ? 'bg-green-500 animate-pulse' : 'bg-muted-foreground'
          }`} />
          {isActive ? 'Recording' : 'Inactive'}
        </div>
      </div>

      {/* Audio Level Meter */}
      <div className="space-y-2">
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>Audio Level</span>
          <span>{Math.round(audioLevel)}%</span>
        </div>
        <div className="w-full bg-muted rounded-full h-2">
          <div
            className={`h-full rounded-full transition-all duration-300 ${
              audioLevel > 80 ? 'bg-red-500' :
              audioLevel > 50 ? 'bg-yellow-500' :
              'bg-green-500'
            }`}
            style={{ width: `${audioLevel}%` }}
          />
        </div>
      </div>
    </div>
  )
}