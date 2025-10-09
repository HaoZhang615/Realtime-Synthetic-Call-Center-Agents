import { useState, useEffect, useRef } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { VoiceControls } from './VoiceControls'
import { ChatHistory } from './ChatHistory'
import { VoiceSettings } from './VoiceSettings'
import { CustomerSelection } from './CustomerSelection'
import { ChatText } from '@phosphor-icons/react'
import { toast } from 'sonner'
import { RealtimeClient } from '@/utils/realtimeClient'
import { getRealtimeApiBase } from '@/config'

type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error'
type CallStatus = 'idle' | 'calling' | 'active' | 'ended'

type ChatMessage = {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: string
  audioUrl?: string
  streaming?: boolean
}

export function VoiceChatInterface() {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected')
  const [callStatus, setCallStatus] = useState<CallStatus>('idle')
  const [isRecording, setIsRecording] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const isMutedRef = useRef(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [currentTranscript, setCurrentTranscript] = useState('')
  const [textInput, setTextInput] = useState('')
  
  // Customer selection state
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null)
  const [selectedCustomerName, setSelectedCustomerName] = useState<string>('')
  const [showCustomerSelection, setShowCustomerSelection] = useState(true)
  
  const realtimeClientRef = useRef<RealtimeClient | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const scriptProcessorRef = useRef<ScriptProcessorNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioSourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const assistantStreamingIdRef = useRef<string | null>(null)
  const assistantTranscriptRef = useRef<string>('')
  const userStreamingIdRef = useRef<string | null>(null)
  const userTranscriptRef = useRef<string>('')
  const userSpeechStartRef = useRef<string | null>(null)
  const pendingCustomerIdRef = useRef<string | null>(null)
  const connectedCustomerIdRef = useRef<string | null>(null)
  const hasPlayedGreetingRef = useRef<boolean>(false)

  useEffect(() => {
    // Initialize RealtimeClient
    realtimeClientRef.current = new RealtimeClient({
      voice: 'shimmer',
      instructions: 'You are a helpful customer service AI assistant. Be friendly, professional, and assist with customer inquiries.'
    }, getRealtimeApiBase())

    // Set up event listeners
    const client = realtimeClientRef.current
    
    client.on('connected', () => {
      setConnectionStatus('connected')
      connectedCustomerIdRef.current = pendingCustomerIdRef.current
      pendingCustomerIdRef.current = null
      toast.success('Connected to AI voice service')
    })

    client.on('disconnected', () => {
      setConnectionStatus('disconnected')
      setCallStatus('idle')
      setIsRecording(false)
      pendingCustomerIdRef.current = null
      connectedCustomerIdRef.current = null
      hasPlayedGreetingRef.current = false
      toast.info('Disconnected from voice service')
    })

    client.on('error', (error) => {
      setConnectionStatus('error')
      toast.error(`Connection error: ${error.message}`)
    })

    // Handle assistant audio responses
    client.on('response.audio.delta', (data) => {
      if (data.delta && realtimeClientRef.current) {
        // Play audio chunk
        realtimeClientRef.current.playAudioChunk(data.delta)
      }
    })

    // Handle response completion (reset audio state)
    client.on('response.done', () => {
      console.log('Response completed')
    })

  // ===== Assistant transcript (streaming) handling =====
    client.on('response.audio_transcript.delta', (data) => {
      const delta: string | undefined = data?.delta
      if (!delta) return
      assistantTranscriptRef.current += delta

      // Avoid creating an empty bubble; only after non-whitespace content exists
      if (!assistantStreamingIdRef.current && assistantTranscriptRef.current.trim().length === 0) {
        return
      }

      setMessages(prev => {
        if (!assistantStreamingIdRef.current) {
          const id = `asst_${Date.now()}`
          assistantStreamingIdRef.current = id
          return [
            ...prev,
            {
              id,
              type: 'assistant',
              content: assistantTranscriptRef.current,
              timestamp: new Date().toISOString(),
              streaming: true
            }
          ]
        }
        return prev.map(m => m.id === assistantStreamingIdRef.current ? { ...m, content: assistantTranscriptRef.current } : m)
      })
    })

    client.on('response.audio_transcript.done', () => {
      if (!assistantStreamingIdRef.current) return
      // Finalize the assistant message
      setMessages(prev => prev.map(m => m.id === assistantStreamingIdRef.current ? { ...m, streaming: false } : m))
      assistantStreamingIdRef.current = null
      assistantTranscriptRef.current = ''
    })

    // Handle response creation (assistant is thinking)
    client.on('response.created', () => {
      console.log('Assistant is generating response...')
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
          if (message.type === 'assistant' && assistantStreamingIdRef.current && prev.some(m => m.id === assistantStreamingIdRef.current)) {
            const tempId = assistantStreamingIdRef.current
            assistantStreamingIdRef.current = item.id
            return prev.map(m => m.id === tempId ? { ...m, id: item.id, content: message.content || m.content, timestamp: message.timestamp } : m)
          }

          if (message.type === 'user' && userStreamingIdRef.current && prev.some(m => m.id === userStreamingIdRef.current)) {
            const tempId = userStreamingIdRef.current
            userStreamingIdRef.current = item.id
            return prev.map(m => m.id === tempId ? { ...m, id: item.id, content: message.content || m.content, timestamp: message.timestamp, streaming: false } : m)
          }

          // Avoid duplicate optimistic messages
          const last = prev[prev.length - 1]
          if (last && last.type === message.type && last.content === message.content) {
            return prev
          }

          const existing = prev.find(m => m.id === item.id)
          if (existing) {
            return prev.map(m => m.id === item.id ? message : m)
          }

          return [...prev, message]
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

    // ===== User transcription handling =====
    // Clear live transcript at start of speech (server VAD)
    client.on('input_audio_buffer.speech_started', () => {
      userTranscriptRef.current = ''
      userSpeechStartRef.current = new Date().toISOString()
      const messageId = `user_${Date.now()}`
      userStreamingIdRef.current = messageId
      setMessages(prev => [
        ...prev,
        {
          id: messageId,
          type: 'user',
          content: '',
          timestamp: userSpeechStartRef.current || new Date().toISOString(),
          streaming: true
        }
      ])
      // Show placeholder bubble immediately for each new user turn
      setCurrentTranscript('…')
      // Show visual feedback that user is interrupting
      toast.info('Listening...', { duration: 1000 })
    })

    // Live delta (if backend forwards) - update ephemeral transcript state
    client.on('conversation.item.input_audio_transcription.delta', ({ delta }) => {
      if (delta) {
        userTranscriptRef.current += delta
        setCurrentTranscript(userTranscriptRef.current)
        if (userStreamingIdRef.current) {
          const id = userStreamingIdRef.current
          setMessages(prev => prev.map(m => m.id === id ? { ...m, content: userTranscriptRef.current } : m))
        }
      }
    })

    // Completed transcription: commit to messages and clear live transcript
    client.on('conversation.item.input_audio_transcription.completed', ({ transcript }) => {
      const finalText = transcript || userTranscriptRef.current
      if (finalText && userStreamingIdRef.current) {
        const id = userStreamingIdRef.current
        setMessages(prev => prev.map(m => m.id === id ? { ...m, content: finalText, streaming: false } : m))
      } else if (finalText) {
        const message: ChatMessage = {
          id: `user_${Date.now()}`,
          type: 'user',
          content: finalText,
          timestamp: userSpeechStartRef.current || new Date().toISOString()
        }
        setMessages(prev => [...prev, message])
      }
      if (userStreamingIdRef.current) {
        // Ensure timestamp reflects start time
        const start = userSpeechStartRef.current
        if (start) {
          setMessages(prev => prev.map(m => m.id === userStreamingIdRef.current ? { ...m, timestamp: start } : m))
        }
      }
      userTranscriptRef.current = ''
      setCurrentTranscript('')
      userStreamingIdRef.current = null
      userSpeechStartRef.current = null
    })

    client.on('conversation.item.input_audio_transcription.failed', () => {
      userTranscriptRef.current = ''
      setCurrentTranscript('')
      if (userStreamingIdRef.current) {
        const id = userStreamingIdRef.current
        setMessages(prev => prev.filter(m => m.id !== id))
        userStreamingIdRef.current = null
      }
    })

    return () => {
      if (realtimeClientRef.current) {
        realtimeClientRef.current.disconnect()
      }
    }
  }, [])

  const handleCustomerSelected = async (customerId: string, customerName: string) => {
    setSelectedCustomerId(customerId)
    setSelectedCustomerName(customerName)
    setShowCustomerSelection(false)

    // Reset conversation state when switching customers
    stopRecording({ silent: true })
    disconnectWebSocket()
    hasPlayedGreetingRef.current = false
    assistantStreamingIdRef.current = null
    assistantTranscriptRef.current = ''
    userStreamingIdRef.current = null
    userTranscriptRef.current = ''
    userSpeechStartRef.current = null
    setMessages([])
    setCurrentTranscript('')
    setTextInput('')
    setCallStatus('idle')
    setIsMuted(false)

    toast.success(`Selected customer: ${customerName}`)

    try {
      await connectWebSocket(customerId)
    } catch (error) {
      console.error('Failed to auto-connect after customer selection:', error)
    }
  }

  const connectWebSocket = async (customerIdOverride?: string) => {
    const client = realtimeClientRef.current
    if (!client) return

    const targetCustomerId = customerIdOverride ?? selectedCustomerId
    if (!targetCustomerId) {
      toast.error('Please select a customer first')
      return
    }

    if (client.isConnected) {
      if (connectedCustomerIdRef.current === targetCustomerId) {
        setConnectionStatus('connected')
        return
      }
      client.disconnect()
      connectedCustomerIdRef.current = null
    }

    if (connectionStatus === 'connecting') {
      return
    }

    pendingCustomerIdRef.current = targetCustomerId
    setConnectionStatus('connecting')
    
    try {
      await client.connect(targetCustomerId)
    } catch (error) {
      pendingCustomerIdRef.current = null
      setConnectionStatus('error')
      toast.error(`Connection failed: ${error}`)
    }
  }

  const disconnectWebSocket = () => {
    const client = realtimeClientRef.current
    if (client) {
      pendingCustomerIdRef.current = null
      connectedCustomerIdRef.current = null
      client.disconnect()
    }
  }

  const startRecording = async (options: { playGreeting?: boolean } = {}) => {
    if (isRecording || !realtimeClientRef.current) return

    try {
      // Get microphone access with specific constraints for 24kHz
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 24000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true
        }
      })

      streamRef.current = stream

      // Create audio context with 24kHz sample rate
      const audioContext = new AudioContext({ sampleRate: 24000 })
      audioContextRef.current = audioContext

  const source = audioContext.createMediaStreamSource(stream)
  audioSourceRef.current = source
      const processor = audioContext.createScriptProcessor(4096, 1, 1)
      scriptProcessorRef.current = processor

      processor.onaudioprocess = (event) => {
        const inputBuffer = event.inputBuffer
        const inputData = inputBuffer.getChannelData(0)

        if (isMutedRef.current) {
          return
        }

        // Convert to PCM16 and send to realtime client
        const pcmData = convertToPCM16(inputData)
        if (realtimeClientRef.current) {
          realtimeClientRef.current.sendAudioData(pcmData)
        }
      }

      source.connect(processor)
      processor.connect(audioContext.destination)

      setIsRecording(true)
      toast.info('Recording started')

      updateMuteState()

      if (options.playGreeting && !hasPlayedGreetingRef.current && realtimeClientRef.current?.isConnected) {
        const customerName = selectedCustomerName || 'there'
        realtimeClientRef.current.requestResponse({
          instructions: `Please greet ${customerName} warmly to start the conversation. Respond in English only.`
        })
        hasPlayedGreetingRef.current = true
      }
    } catch (error) {
      console.error('Failed to start recording:', error)
      toast.error('Failed to start recording')
      throw error
    }
  }

  const stopRecording = (options: { silent?: boolean } = {}) => {
    const hasAudioResources = scriptProcessorRef.current || audioContextRef.current || streamRef.current
    if (!hasAudioResources && !isRecording) {
      return
    }

    if (scriptProcessorRef.current) {
      scriptProcessorRef.current.disconnect()
      scriptProcessorRef.current = null
    }
    if (audioSourceRef.current) {
      audioSourceRef.current.disconnect()
      audioSourceRef.current = null
    }
    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop())
      streamRef.current = null
    }

    setIsRecording(false)
    if (isMuted) {
      setIsMuted(false)
    }
    if (!options.silent) {
      toast.info('Recording stopped')
    }
  }
  const updateMuteState = () => {
    const stream = streamRef.current
    if (!stream) return

    stream.getAudioTracks().forEach(track => {
      track.enabled = !isMuted
    })
  }

  useEffect(() => {
    isMutedRef.current = isMuted
    updateMuteState()
  }, [isMuted])


  const startCall = async () => {
    if (!selectedCustomerId) {
      setShowCustomerSelection(true)
      toast.error('Please select a customer first')
      return
    }

    const client = realtimeClientRef.current
    if (!client) return

    try {
      setCallStatus('calling')
      setMessages([])
      setCurrentTranscript('')

      if (!client.isConnected) {
        await connectWebSocket(selectedCustomerId)
      }

      if (!client.isConnected) {
        throw new Error('Voice service not connected')
      }

      await startRecording({ playGreeting: true })

      setCallStatus('active')
      toast.success(`Call started for ${selectedCustomerName}`)
    } catch (error) {
      console.error('Failed to start call:', error)
      toast.error('Unable to start the call')
      setCallStatus('idle')
      stopRecording({ silent: true })
    }
  }

  const endCall = () => {
    stopRecording({ silent: true })
    hasPlayedGreetingRef.current = false
    setCallStatus('ended')
    setCurrentTranscript('')
    setIsMuted(false)

    disconnectWebSocket()

    setTimeout(() => {
      setCallStatus('idle')
      toast.info('Call ended')
    }, 1000)
  }

  const sendTextInput = () => {
    const trimmed = textInput.trim()
    if (!trimmed || !realtimeClientRef.current) return
    // Optimistic user message
    const optimistic: ChatMessage = {
      id: `user_temp_${Date.now()}`,
      type: 'user',
      content: trimmed,
      timestamp: new Date().toISOString()
    }
    setMessages(prev => [...prev, optimistic])
    realtimeClientRef.current.sendTextMessage(trimmed)
    setTextInput('')
  }

  const handleTextInputKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendTextInput()
    }
  }

  // Helper function to convert Float32Array to PCM16
  const convertToPCM16 = (float32Array: Float32Array): ArrayBuffer => {
    const arrayBuffer = new ArrayBuffer(float32Array.length * 2)
    const view = new DataView(arrayBuffer)
    for (let i = 0; i < float32Array.length; i++) {
      const sample = Math.max(-1, Math.min(1, float32Array[i]))
      view.setInt16(i * 2, sample * 0x7FFF, true) // little-endian
    }
    return arrayBuffer
  }

  const toggleMute = () => {
    setIsMuted(prev => !prev)
  }

  const getConnectionStatusColor = () => {
    switch (connectionStatus) {
      case 'connected': return 'bg-green-500'
      case 'connecting': return 'bg-yellow-500'
      case 'error': return 'bg-red-500'
      default: return 'bg-gray-500'
    }
  }

  const handleVoiceChange = (voice: string) => {
    if (realtimeClientRef.current) {
      realtimeClientRef.current.updateSession({ voice: voice as any })
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

  // Show customer selection if no customer is selected
  if (showCustomerSelection || !selectedCustomerId) {
    return (
      <div className="flex flex-col h-full">
        <div className="border-b border-border bg-card">
          <div className="p-6">
            <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
              <ChatText className="w-6 h-6 text-primary" />
              Voice Chat Interface
            </h1>
            <p className="text-muted-foreground mt-1">
              Select a customer to start your voice conversation
            </p>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="w-full max-w-2xl">
            <CustomerSelection onCustomerSelected={handleCustomerSelected} />
          </div>
        </div>
      </div>
    )
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
                Conversation with {selectedCustomerName}
              </p>
            </div>
            
            <div className="flex items-center gap-4">
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => setShowCustomerSelection(true)}
              >
                Change Customer
              </Button>
              
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
              <div className="flex-1 min-h-0 flex flex-col">
                <ChatHistory
                  className="flex-1 min-h-0"
                  messages={messages}
                  currentTranscript={currentTranscript}
                />
                <div className="pt-3 mt-3 border-t border-border flex items-center gap-2">
                  <input
                    type="text"
                    value={textInput}
                    onChange={e => setTextInput(e.target.value)}
                    onKeyDown={handleTextInputKey}
                    placeholder={connectionStatus === 'connected' ? 'Type a message...' : 'Connect to start chatting'}
                    disabled={connectionStatus !== 'connected'}
                    className="flex-1 rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
                  />
                  <Button size="sm" onClick={sendTextInput} disabled={!textInput.trim() || connectionStatus !== 'connected'}>
                    Send
                  </Button>
                </div>
              </div>
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
                isMuted={isMuted}
                onStartCall={startCall}
                onEndCall={endCall}
                onToggleMute={toggleMute}
              />
            </CardContent>
          </Card>

          {/* Voice Settings */}
          <Card>
            <CardHeader>
              <CardTitle>Settings</CardTitle>
            </CardHeader>
            <CardContent>
              <VoiceSettings onVoiceChange={handleVoiceChange} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}