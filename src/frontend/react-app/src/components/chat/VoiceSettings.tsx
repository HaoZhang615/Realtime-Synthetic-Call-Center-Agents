import { useState } from 'react'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { Separator } from '@/components/ui/separator'

export function VoiceSettings() {
  const [language, setLanguage] = useState('en-US')
  const [voiceType, setVoiceType] = useState('alloy')
  const [speed, setSpeed] = useState([1])
  const [autoRecord, setAutoRecord] = useState(false)
  const [noiseReduction, setNoiseReduction] = useState(true)

  const languages = [
    { value: 'en-US', label: 'English (US)' },
    { value: 'en-GB', label: 'English (UK)' },
    { value: 'es-ES', label: 'Spanish' },
    { value: 'fr-FR', label: 'French' },
    { value: 'de-DE', label: 'German' },
    { value: 'it-IT', label: 'Italian' },
    { value: 'pt-BR', label: 'Portuguese' },
    { value: 'zh-CN', label: 'Chinese' },
    { value: 'ja-JP', label: 'Japanese' },
    { value: 'ko-KR', label: 'Korean' }
  ]

  const voiceTypes = [
    { value: 'alloy', label: 'Alloy (Neutral)' },
    { value: 'echo', label: 'Echo (Professional)' },
    { value: 'fable', label: 'Fable (Warm)' },
    { value: 'onyx', label: 'Onyx (Deep)' },
    { value: 'nova', label: 'Nova (Friendly)' },
    { value: 'shimmer', label: 'Shimmer (Energetic)' }
  ]

  return (
    <div className="space-y-6">
      {/* Language Selection */}
      <div className="space-y-2">
        <Label htmlFor="language">Language</Label>
        <Select value={language} onValueChange={setLanguage}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {languages.map(lang => (
              <SelectItem key={lang.value} value={lang.value}>
                {lang.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Voice Type */}
      <div className="space-y-2">
        <Label htmlFor="voice-type">Voice Type</Label>
        <Select value={voiceType} onValueChange={setVoiceType}>
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

      {/* Speaking Speed */}
      <div className="space-y-3">
        <div className="flex justify-between">
          <Label htmlFor="speed">Speaking Speed</Label>
          <span className="text-sm text-muted-foreground">{speed[0]}x</span>
        </div>
        <Slider
          value={speed}
          onValueChange={setSpeed}
          min={0.5}
          max={2}
          step={0.1}
          className="w-full"
        />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>Slow</span>
          <span>Normal</span>
          <span>Fast</span>
        </div>
      </div>

      <Separator />

      {/* Advanced Settings */}
      <div className="space-y-4">
        <h4 className="text-sm font-medium">Advanced Settings</h4>
        
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label htmlFor="auto-record">Auto Recording</Label>
            <p className="text-xs text-muted-foreground">
              Automatically start recording when you speak
            </p>
          </div>
          <Switch
            id="auto-record"
            checked={autoRecord}
            onCheckedChange={setAutoRecord}
          />
        </div>

        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label htmlFor="noise-reduction">Noise Reduction</Label>
            <p className="text-xs text-muted-foreground">
              Filter background noise during recording
            </p>
          </div>
          <Switch
            id="noise-reduction"
            checked={noiseReduction}
            onCheckedChange={setNoiseReduction}
          />
        </div>
      </div>
    </div>
  )
}