import { Button } from '@/components/ui/button'
import { Microphone, MicrophoneSlash, Phone, PhoneDisconnect } from '@phosphor-icons/react'

type CallStatus = 'idle' | 'calling' | 'active' | 'ended'

interface VoiceControlsProps {
  callStatus: CallStatus
  isMuted: boolean
  onStartCall: () => void
  onEndCall: () => void
  onToggleMute: () => void
}

export function VoiceControls({
  callStatus,
  isMuted,
  onStartCall,
  onEndCall,
  onToggleMute
}: VoiceControlsProps) {
  return (
    <div className="space-y-4">
      {/* Call Controls */}
      <div className="flex justify-center">
        {callStatus === 'idle' || callStatus === 'ended' ? (
          <Button
            size="lg"
            onClick={onStartCall}
            className="w-16 h-16 rounded-full bg-green-500 hover:bg-green-600 text-white"
          >
            <Phone className="w-6 h-6" />
          </Button>
        ) : (
          <Button
            size="lg"
            onClick={onEndCall}
            className="w-16 h-16 rounded-full bg-red-500 hover:bg-red-600 text-white"
            disabled={callStatus === 'calling'}
          >
            <PhoneDisconnect className="w-6 h-6" />
          </Button>
        )}
      </div>
      {/* Mute Control */}
      {callStatus === 'active' && (
        <div className="flex justify-center">
          <Button
            size="lg"
            variant={isMuted ? 'destructive' : 'outline'}
            onClick={onToggleMute}
            className="w-14 h-14 rounded-full"
          >
            {isMuted ? (
              <MicrophoneSlash className="w-5 h-5" />
            ) : (
              <Microphone className="w-5 h-5" />
            )}
          </Button>
        </div>
      )}

      {/* Status Text */}
      <div className="text-center text-sm text-muted-foreground">
        {callStatus === 'idle' && 'Click to start a voice call'}
        {callStatus === 'calling' && 'Connecting to AI assistant...'}
        {callStatus === 'active' && !isMuted && 'Microphone is live'}
        {callStatus === 'active' && isMuted && 'Microphone muted'}
        {callStatus === 'ended' && 'Call ended'}
      </div>
    </div>
  )
}