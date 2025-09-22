import { useState, useEffect, useRef } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { VoiceControls } from './VoiceControls'
import { ChatHistory } from './ChatHistory'
import { AudioVisualizer } from './AudioVisualizer'
import { VoiceSettings } from './VoiceSettings'
import { ChatText, Microphone, MicrophoneSlash, Phone, PhoneDisconnect } from '@phosphor-icons/react'
import { toast } from 'sonner'

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
  
  const wsRef = useRef<WebSocket | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)

  useEffect(() => {
    // Simulate connection status changes
    const timer = setTimeout(() => {
      setConnectionStatus('connected')
    }, 1000)

    return () => clearTimeout(timer)
  }, [])

  const connectWebSocket = () => {
    if (connectionStatus === 'connected') return

    setConnectionStatus('connecting')
    
    // Simulate WebSocket connection
    setTimeout(() => {
      setConnectionStatus('connected')
      toast.success('Connected to AI voice service')
    }, 2000)
  }

  const disconnectWebSocket = () => {
    setConnectionStatus('disconnected')
    setCallStatus('idle')
    setIsRecording(false)
    toast.info('Disconnected from voice service')
  }

  const startCall = async () => {
    if (connectionStatus !== 'connected') {
      connectWebSocket()
      return
    }

    try {
      // Request microphone permission
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      
      setCallStatus('calling')
      setTimeout(() => {
        setCallStatus('active')
        toast.success('Call started')
        
        // Add welcome message
        const welcomeMessage: ChatMessage = {
          id: Date.now().toString(),
          type: 'assistant',
          content: 'Hello! I\'m your AI assistant. How can I help you today?',
          timestamp: new Date().toISOString()
        }
        setMessages([welcomeMessage])
      }, 1500)
      
      stream.getTracks().forEach(track => track.stop())
    } catch (error) {
      toast.error('Microphone access denied')
      setCallStatus('idle')
    }
  }

  const endCall = () => {
    setCallStatus('ended')
    setIsRecording(false)
    setCurrentTranscript('')
    
    setTimeout(() => {
      setCallStatus('idle')
      toast.info('Call ended')
    }, 1000)
  }

  const toggleRecording = () => {
    if (callStatus !== 'active') return

    if (isRecording) {
      setIsRecording(false)
      setCurrentTranscript('')
      toast.info('Recording stopped')
    } else {
      setIsRecording(true)
      simulateRecording()
      toast.info('Recording started')
    }
  }

  const simulateRecording = () => {
    // Simulate live transcription
    const phrases = [
      'Hello, I need help with...',
      'Can you tell me about your services?',
      'I have a billing question',
      'What are your business hours?'
    ]
    
    let currentPhrase = phrases[Math.floor(Math.random() * phrases.length)]
    let currentIndex = 0
    
    const interval = setInterval(() => {
      if (!isRecording) {
        clearInterval(interval)
        return
      }
      
      if (currentIndex < currentPhrase.length) {
        setCurrentTranscript(currentPhrase.substring(0, currentIndex + 1))
        currentIndex++
      } else {
        clearInterval(interval)
        
        // Add user message
        const userMessage: ChatMessage = {
          id: Date.now().toString(),
          type: 'user',
          content: currentPhrase,
          timestamp: new Date().toISOString()
        }
        
        setMessages(prev => [...prev, userMessage])
        setCurrentTranscript('')
        setIsRecording(false)
        
        // Simulate AI response after delay
        setTimeout(() => {
          const responses = [
            'I\'d be happy to help you with that. Let me look into your account details.',
            'Our services include 24/7 customer support, technical assistance, and billing inquiries.',
            'I can help you with billing questions. What specific issue are you experiencing?',
            'Our business hours are Monday through Friday, 9 AM to 6 PM EST.'
          ]
          
          const response = responses[Math.floor(Math.random() * responses.length)]
          
          const assistantMessage: ChatMessage = {
            id: (Date.now() + 1).toString(),
            type: 'assistant',
            content: response,
            timestamp: new Date().toISOString()
          }
          
          setMessages(prev => [...prev, assistantMessage])
        }, 2000)
      }
    }, 100)
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