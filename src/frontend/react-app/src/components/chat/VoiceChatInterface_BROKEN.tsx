import { useState, useEffect, useRef } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { VoiceControls } from './VoiceControls'
import { ChatHistory } from './ChatHistory'
import { AudioVisualizer } from './AudioVisualizer'
import { VoiceSettings } from './VoiceSettings'
import { CustomerSelection } from './CustomerSelection'
import { ChatText, Microphone, MicrophoneSlash, Phone, PhoneDisconnect } from '@phosphor-icons/react'
import { toast } from 'sonner'
import { RealtimeClient } from '@/utils/realtimeClient'

type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error'
type CallStatus = 'idle' | 'calling' | 'active' | 'ended'

type ChatMessage = {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: string
  audioUrl?: string
}

export function VoiceChatInterface() {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected')
  const [callStatus, setCallStatus] = useState<CallStatus>('idle')
  const [isRecording, setIsRecording] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [currentTranscript, setCurrentTranscript] = useState('')
  const [audioLevel, setAudioLevel] = useState(0)
  
  // Customer selection state
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null)
  const [selectedCustomerName, setSelectedCustomerName] = useState<string>('')
  
  const realtimeClientRef = useRef<RealtimeClient | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)

  useEffect(() => {
    // Initialize RealtimeClient
    realtimeClientRef.current = new RealtimeClient({
      voice: 'shimmer',
      instructions: 'You are a helpful customer service AI assistant. Be friendly, professional, and assist with customer inquiries.'
    }, 'http://localhost:8000')

    // Set up event listeners
    const client = realtimeClientRef.current
    
    client.on('connected', () => {
      setConnectionStatus('connected')
      toast.success('Connected to AI voice service')
    })

    client.on('disconnected', () => {
      setConnectionStatus('disconnected')
      setCallStatus('idle')
      setIsRecording(false)
      toast.info('Disconnected from voice service')
    })

    client.on('error', (error) => {
      setConnectionStatus('error')
      toast.error(`Connection error: ${error.message}`)
    })

    client.on('conversation.item.created', ({ item }) => {
      if (item.type === 'message') {
        const message: ChatMessage = {
          id: item.id,
          type: item.role === 'user' ? 'user' : 'assistant',
          content: item.content?.[0]?.text || '',
          timestamp: new Date().toISOString()
        }
        
        setMessages(prev => {
          const existing = prev.find(m => m.id === item.id)
          if (existing) {
            return prev.map(m => m.id === item.id ? message : m)
          } else {
            return [...prev, message]
          }
        })
      }
    })

    client.on('response.text.delta', ({ delta, item_id }) => {
      if (delta) {
        setMessages(prev => prev.map(msg => {
          if (msg.id === item_id) {
            return { ...msg, content: msg.content + delta }
          }
          return msg
        }))
      }
    })

    client.on('conversation.item.input_audio_transcription.completed', ({ transcript }) => {
      setCurrentTranscript(transcript || '')
    })

    return () => {
      if (realtimeClientRef.current) {
        realtimeClientRef.current.disconnect()
      }
    }
  }, [])

  const connectWebSocket = async () => {
    if (connectionStatus === 'connected' || !realtimeClientRef.current) return
    if (!selectedCustomerId) {
      toast.error('Please select a customer first')
      return
    }

    setConnectionStatus('connecting')
    
    try {
      await realtimeClientRef.current.connect(selectedCustomerId)
    } catch (error) {
      setConnectionStatus('error')
      toast.error(`Connection failed: ${error}`)
    }
  }
      toast.error('Failed to connect to voice service')
    }
  }

  const disconnectWebSocket = () => {
    if (realtimeClientRef.current) {
      realtimeClientRef.current.disconnect()
    }
  }

  const startCall = async () => {
    if (connectionStatus !== 'connected') {
      await connectWebSocket()
      return
    }

    try {
      setCallStatus('calling')
      
      // Start audio recording and send to RealtimeClient
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      
      setCallStatus('active')
      toast.success('Call started')
      
      // TODO: Implement audio streaming to RealtimeClient
      // This would involve setting up MediaRecorder and sending chunks
      
    } catch (error) {
      toast.error('Microphone access denied')
      setCallStatus('idle')
    }
  }

  const endCall = () => {
    setCallStatus('ended')
    setIsRecording(false)
    setCurrentTranscript('')
    
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop()
    }
    
    setTimeout(() => {
      setCallStatus('idle')
      toast.info('Call ended')
    }, 1000)
  }

  const toggleRecording = async () => {
    if (callStatus !== 'active' || !realtimeClientRef.current) return

    if (isRecording) {
      setIsRecording(false)
      // Stop recording
      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.stop()
      }
      toast.info('Recording stopped')
    } else {
      try {
        // Start recording and streaming to RealtimeClient
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        
        const mediaRecorder = new MediaRecorder(stream)
        mediaRecorderRef.current = mediaRecorder
        
        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0 && realtimeClientRef.current) {
            // Convert blob to ArrayBuffer and send
            event.data.arrayBuffer().then((arrayBuffer) => {
              realtimeClientRef.current!.sendAudioData(arrayBuffer)
            })
          }
        }
        
        mediaRecorder.start(100) // Record in 100ms chunks
        setIsRecording(true)
        toast.info('Recording started')
        
      } catch (error) {
        toast.error('Failed to start recording')
      }
    }
  }

  const getConnectionStatusColor = () => {
    switch (connectionStatus) {
      case 'connected': return 'bg-green-500'
      case 'connecting': return 'bg-yellow-500'
      case 'error': return 'bg-red-500'
      default: return 'bg-gray-500'
    }
  }

  const getCallStatusText = () => {
    switch (callStatus) {
      case 'calling': return 'Connecting...'
      case 'active': return 'Call Active'
      case 'ended': return 'Call Ended'
      default: return 'Ready to Call'
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b border-border bg-card">
        <div className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
                <ChatText className="w-6 h-6 text-primary" />
                Voice Chat Interface
              </h1>
              <p className="text-muted-foreground mt-1">
                Real-time AI-powered voice conversations
              </p>
            </div>
            
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${getConnectionStatusColor()}`}></div>
                <span className="text-sm text-muted-foreground">
                  {connectionStatus === 'connected' ? 'Connected' : 'Disconnected'}
                </span>
              </div>
              
              <Badge variant={callStatus === 'active' ? 'default' : 'secondary'}>
                {getCallStatusText()}
              </Badge>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex gap-6 p-6 min-h-0">
        {/* Left Panel - Chat History */}
        <div className="flex-1 flex flex-col min-w-0">
          <Card className="flex-1 flex flex-col">
            <CardHeader>
              <CardTitle>Conversation</CardTitle>
              <CardDescription>
                Live transcript of your voice conversation
              </CardDescription>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col min-h-0">
              <ChatHistory messages={messages} currentTranscript={currentTranscript} />
            </CardContent>
          </Card>
        </div>

        {/* Right Panel - Controls */}
        <div className="w-80 flex flex-col gap-6">
          {/* Voice Controls */}
          <Card>
            <CardHeader>
              <CardTitle>Voice Controls</CardTitle>
            </CardHeader>
            <CardContent>
              <VoiceControls
                callStatus={callStatus}
                isRecording={isRecording}
                isMuted={isMuted}
                onStartCall={startCall}
                onEndCall={endCall}
                onToggleRecording={toggleRecording}
                onToggleMute={() => setIsMuted(!isMuted)}
              />
            </CardContent>
          </Card>

          {/* Audio Visualizer */}
          <Card>
            <CardHeader>
              <CardTitle>Audio Activity</CardTitle>
            </CardHeader>
            <CardContent>
              <AudioVisualizer 
                isActive={isRecording} 
                audioLevel={audioLevel}
              />
            </CardContent>
          </Card>

          {/* Voice Settings */}
          <Card>
            <CardHeader>
              <CardTitle>Settings</CardTitle>
            </CardHeader>
            <CardContent>
              <VoiceSettings />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}