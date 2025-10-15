import React, { createContext, useContext, useState, ReactNode } from 'react'
import { RealtimeClient } from '@/utils/realtimeClient'

export interface VoiceSettingsState {
  voiceType: 'alloy' | 'ash' | 'ballad' | 'coral' | 'echo' | 'sage' | 'shimmer' | 'verse'
}

export interface VoiceSettingsContextType {
  settings: VoiceSettingsState
  updateSettings: (newSettings: Partial<VoiceSettingsState>) => void
  applyToClient: (client: RealtimeClient) => void
}

const VoiceSettingsContext = createContext<VoiceSettingsContextType | undefined>(undefined)

const defaultSettings: VoiceSettingsState = {
  voiceType: 'shimmer'
}

export function VoiceSettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<VoiceSettingsState>(defaultSettings)

  const updateSettings = (newSettings: Partial<VoiceSettingsState>) => {
    setSettings(prev => ({ ...prev, ...newSettings }))
  }

  const applyToClient = (client: RealtimeClient) => {
    // Update the RealtimeClient with current settings
    client.updateSession({
      voice: settings.voiceType
    })
  }

  const value: VoiceSettingsContextType = {
    settings,
    updateSettings,
    applyToClient
  }

  return (
    <VoiceSettingsContext.Provider value={value}>
      {children}
    </VoiceSettingsContext.Provider>
  )
}

export function useVoiceSettings() {
  const context = useContext(VoiceSettingsContext)
  if (context === undefined) {
    throw new Error('useVoiceSettings must be used within a VoiceSettingsProvider')
  }
  return context
}

// With language auto-detection handled by the model, no additional
// instruction synthesis is required here.
