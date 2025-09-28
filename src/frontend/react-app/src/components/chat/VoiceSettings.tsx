import { useState } from 'react'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'

interface VoiceSettingsProps {
  onVoiceChange?: (voice: string) => void
}

export function VoiceSettings({ onVoiceChange }: VoiceSettingsProps) {
  const [voiceType, setVoiceType] = useState('shimmer')

  const voiceTypes = [
    { value: 'alloy', label: 'Alloy' },
    { value: 'ash', label: 'Ash' },
    { value: 'ballad', label: 'Ballad' },
    { value: 'coral', label: 'Coral' },
    { value: 'echo', label: 'Echo' },
    { value: 'sage', label: 'Sage' },
    { value: 'shimmer', label: 'Shimmer' },
    { value: 'verse', label: 'Verse' }
  ]

  return (
    <div className="space-y-6">
      {/* Voice Type */}
      <div className="space-y-2">
        <Label htmlFor="voice-type">Voice Choice</Label>
        <Select 
          value={voiceType} 
          onValueChange={(value) => {
            setVoiceType(value)
            onVoiceChange?.(value)
          }}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {voiceTypes.map(voice => (
              <SelectItem key={voice.value} value={voice.value}>
                {voice.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Separator />
    </div>
  )
}