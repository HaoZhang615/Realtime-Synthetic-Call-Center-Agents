// Phase 2: TODO - Wire RealtimeClient into VoiceChatInterface and supply a backend token provider

/**
 * Realtime Voice Client for TypeScript/React
 * Connects to FastAPI backend which bridges to Azure OpenAI Realtime API
 * 
 * Updated for Phase 2: Uses FastAPI WebSocket proxy instead of direct Azure connection
 * Based on openai-realtime-voice-template patterns and Python realtime2.py implementation
 */

// Event types for the realtime API
export type RealtimeEvent = 
  | 'session.created'
  | 'session.updated'  
  | 'session.deleted'
  | 'conversation.created'
  | 'conversation.item.created'
  | 'conversation.item.truncated'
  | 'conversation.item.deleted'
  | 'conversation.item.input_audio_transcription.completed'
  | 'conversation.item.input_audio_transcription.failed'
  | 'input_audio_buffer.committed' 
  | 'input_audio_buffer.cleared'
  | 'input_audio_buffer.speech_started'
  | 'input_audio_buffer.speech_stopped'
  | 'response.created'
  | 'response.done'
  | 'response.output_item.added'
  | 'response.output_item.done'
  | 'response.content_part.added'
  | 'response.content_part.done'
  | 'response.text.delta'
  | 'response.text.done'
  | 'response.audio_transcript.delta'
  | 'response.audio_transcript.done'
  | 'response.audio.delta'
  | 'response.audio.done'
  | 'response.function_call_arguments.delta'
  | 'response.function_call_arguments.done'
  | 'rate_limits.updated'
  | 'error'
  | 'connected'
  | 'disconnected'
  | 'connecting'

export interface RealtimeEventData {
  event_id?: string
  type: RealtimeEvent
  [key: string]: any
}

/**
 * Base64 utilities for audio data encoding
 */
class Base64Utils {
  /**
   * Encode ArrayBuffer to base64 string
   */
  static encode(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer)
    let binary = ''
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i])
    }
    return btoa(binary)
  }

  /**
   * Decode base64 string to ArrayBuffer
   */
  static decode(base64: string): ArrayBuffer {
    const binaryString = atob(base64)
    const bytes = new Uint8Array(binaryString.length)
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i)
    }
    return bytes.buffer
  }
}

/**
 * WebSocket connection manager for FastAPI Realtime Proxy
 * Connects to our FastAPI backend which handles Azure OpenAI communication
 */
export class RealtimeAPI {
  private ws: WebSocket | null = null
  private backendUrl: string = 'http://localhost:8000'
  private eventListeners = new Map<RealtimeEvent, Set<(data: any) => void>>()

  constructor(backendUrl?: string) {
    if (backendUrl) {
      this.backendUrl = backendUrl.replace(/\/$/, '') // Remove trailing slash
    }
  }

  /**
   * Check if WebSocket is connected
   */
  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  /**
   * Add event listener
   */
  on(event: RealtimeEvent, callback: (data: any) => void) {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, new Set())
    }
    this.eventListeners.get(event)!.add(callback)
  }

  /**
   * Remove event listener
   */
  off(event: RealtimeEvent, callback: (data: any) => void) {
    this.eventListeners.get(event)?.delete(callback)
  }

  /**
   * Emit event to listeners
   */
  private emit(event: RealtimeEvent, data?: any) {
    const listeners = this.eventListeners.get(event)
    if (listeners) {
      listeners.forEach(callback => callback(data))
    }
  }

  /**
   * Connect to the FastAPI WebSocket endpoint
   */
  async connect(customerId?: string): Promise<void> {
    return new Promise((resolve, reject) => {
      this.emit('connecting')
      
      // Build WebSocket URL for our FastAPI backend
      let wsUrl = this.backendUrl.replace('http://', 'ws://').replace('https://', 'wss://')
      wsUrl += '/api/realtime'
      
      if (customerId) {
        wsUrl += `?customer_id=${encodeURIComponent(customerId)}`
      }
      
      console.log('Connecting to FastAPI WebSocket proxy:', wsUrl)
      
      // Create WebSocket connection
      this.ws = new WebSocket(wsUrl)

      this.ws.addEventListener('open', (event) => {
        console.log('WebSocket connected to FastAPI backend')
        this.emit('connected')
        resolve()
      })

      this.ws.addEventListener('close', (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason)
        this.emit('disconnected', { code: event.code, reason: event.reason })
      })

      this.ws.addEventListener('error', (event) => {
        console.error('WebSocket error:', event)
        console.error('WebSocket URL was:', wsUrl)
        const error = new Error(`WebSocket connection failed. URL: ${wsUrl}. Check console for details.`)
        this.emit('error', error)
        reject(error)
      })

      this.ws.addEventListener('message', (event) => {
        try {
          const data: RealtimeEventData = JSON.parse(event.data)
          console.log('Received event:', data.type, data)
          this.emit(data.type, data)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error, 'Raw data:', event.data)
          this.emit('error', error)
        }
      })
    })
  }

  /**
   * Disconnect from the WebSocket
   */
  disconnect() {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  /**
   * Send event to the server
   */
  sendEvent(event: Omit<RealtimeEventData, 'event_id'>) {
    if (!this.isConnected) {
      throw new Error('WebSocket is not connected')
    }

    const eventWithId = {
      event_id: this.generateEventId(),
      ...event
    } as RealtimeEventData

    console.log('Sending event:', eventWithId.type, eventWithId)
    this.ws!.send(JSON.stringify(eventWithId))
  }

  /**
   * Generate unique event ID
   */
  private generateEventId(): string {
    return `evt_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }
}

/**
 * Conversation state management
 */
export class RealtimeConversation {
  private items: any[] = []
  private responses: any[] = []
  private queuedSpeechItems: any[] = []
  private queuedTranscriptItems: any[] = []
  private queuedInputAudio: ArrayBuffer | null = null

  /**
   * Get all conversation items
   */
  getItems(): any[] {
    return [...this.items]
  }

  /**
   * Add item to conversation
   */
  addItem(item: any): any {
    const newItem = {
      id: item.id || this.generateItemId(),
      ...item
    }
    this.items.push(newItem)
    return newItem
  }

  /**
   * Update item in conversation
   */
  updateItem(id: string, updates: any): any | null {
    const index = this.items.findIndex(item => item.id === id)
    if (index !== -1) {
      this.items[index] = { ...this.items[index], ...updates }
      return this.items[index]
    }
    return null
  }

  /**
   * Delete item from conversation
   */
  deleteItem(id: string): any | null {
    const index = this.items.findIndex(item => item.id === id)
    if (index !== -1) {
      return this.items.splice(index, 1)[0]
    }
    return null
  }

  /**
   * Truncate conversation from a specific item
   */
  truncate(itemId: string): any[] {
    const index = this.items.findIndex(item => item.id === itemId)
    if (index !== -1) {
      return this.items.splice(index)
    }
    return []
  }

  /**
   * Add queued speech item
   */
  queueSpeechItem(item: any) {
    this.queuedSpeechItems.push(item)
  }

  /**
   * Add queued transcript item
   */
  queueTranscriptItem(item: any) {
    this.queuedTranscriptItems.push(item)
  }

  /**
   * Queue input audio
   */
  queueInputAudio(audioData: ArrayBuffer) {
    if (this.queuedInputAudio) {
      // Concatenate with existing audio
      const combined = new Uint8Array(this.queuedInputAudio.byteLength + audioData.byteLength)
      combined.set(new Uint8Array(this.queuedInputAudio), 0)
      combined.set(new Uint8Array(audioData), this.queuedInputAudio.byteLength)
      this.queuedInputAudio = combined.buffer
    } else {
      this.queuedInputAudio = audioData
    }
  }

  /**
   * Get and clear queued input audio
   */
  getQueuedInputAudio(): ArrayBuffer | null {
    const audio = this.queuedInputAudio
    this.queuedInputAudio = null
    return audio
  }

  /**
   * Generate unique item ID
   */
  private generateItemId(): string {
    return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }
}

/**
 * Configuration interface for RealtimeClient
 */
export interface RealtimeClientConfig {
  model?: string
  voice?: 'alloy' | 'shimmer' | 'echo' | 'onyx' | 'nova' | 'coral' | 'fable'
  temperature?: number
  maxResponseTokens?: number
  instructions?: string
  modalities?: ('text' | 'audio')[]
  inputAudioFormat?: 'pcm16' | 'g711_ulaw' | 'g711_alaw'
  outputAudioFormat?: 'pcm16' | 'g711_ulaw' | 'g711_alaw'
  inputAudioTranscription?: {
    model?: 'whisper-1'
  }
  turnDetection?: {
    type?: 'server_vad'
    threshold?: number
    prefix_padding_ms?: number
    silence_duration_ms?: number
  }
  tools?: any[]
}

/**
 * Main RealtimeClient class
 * High-level interface for FastAPI Realtime Proxy
 */
export class RealtimeClient {
  private api: RealtimeAPI
  private conversation: RealtimeConversation
  private sessionConfig: RealtimeClientConfig
  private eventHandlers = new Map<RealtimeEvent, ((data: any) => void)[]>()
  private audioContext: AudioContext | null = null
  private nextPlayTime: number = 0

  constructor(
    config: RealtimeClientConfig = {},
    backendUrl?: string
  ) {
    // Default configuration
    this.sessionConfig = {
      model: config.model ?? 'gpt-realtime',
      voice: config.voice ?? 'shimmer', // Changed default to match backend
      temperature: config.temperature ?? 0.8,
      maxResponseTokens: config.maxResponseTokens ?? 4096,
      modalities: config.modalities ?? ['text', 'audio'],
      inputAudioFormat: config.inputAudioFormat ?? 'pcm16',
      outputAudioFormat: config.outputAudioFormat ?? 'pcm16',
      inputAudioTranscription: config.inputAudioTranscription ?? { model: 'whisper-1' },
      turnDetection: config.turnDetection ?? {
        type: 'server_vad',
        threshold: 0.5,
        prefix_padding_ms: 300,
        silence_duration_ms: 200
      },
      instructions: config.instructions ?? 'You are a helpful AI assistant.',
      tools: config.tools
    }

    this.api = new RealtimeAPI(backendUrl)
    this.conversation = new RealtimeConversation()

    // Set up default event handlers
    this.setupDefaultHandlers()
  }

  private buildSessionPayload(overrides: Partial<RealtimeClientConfig> = {}) {
    const config: RealtimeClientConfig = { ...this.sessionConfig, ...overrides }
    const session: Record<string, unknown> = {}

    if (config.model) session.model = config.model
    if (config.voice) session.voice = config.voice
    // Note: Temperature and max tokens are handled by the backend
    if (config.instructions) session.instructions = config.instructions
    if (config.modalities) session.modalities = config.modalities
    if (config.inputAudioFormat) {
      session.input_audio_format = config.inputAudioFormat
    }
    if (config.outputAudioFormat) {
      session.output_audio_format = config.outputAudioFormat
    }
    if (config.inputAudioTranscription) {
      session.input_audio_transcription = {
        ...config.inputAudioTranscription
      }
    }
    if (config.turnDetection) {
      session.turn_detection = {
        ...config.turnDetection
      }
    }
    if (config.tools) {
      session.tools = config.tools
    }

    return session
  }

  /**
   * Set up default event handlers
   */
  private setupDefaultHandlers() {
    // Session events
    this.api.on('session.created', (event) => {
      console.log('Session created:', event.session)
    })

    // Conversation events
    this.api.on('conversation.item.created', (event) => {
      const item = event.item
      this.conversation.addItem(item)
      this.emit('conversation.item.created', { item })
    })

    this.api.on('conversation.item.truncated', (event) => {
      const truncatedItems = this.conversation.truncate(event.item_id)
      this.emit('conversation.item.truncated', { items: truncatedItems })
    })

    this.api.on('conversation.item.deleted', (event) => {
      const deletedItem = this.conversation.deleteItem(event.item_id)
      this.emit('conversation.item.deleted', { item: deletedItem })
    })

    // Audio buffer events
    this.api.on('input_audio_buffer.speech_started', (event) => {
      console.log('Speech started')
      this.emit('input_audio_buffer.speech_started', event)
    })

    this.api.on('input_audio_buffer.speech_stopped', (event) => {
      console.log('Speech stopped')
      this.emit('input_audio_buffer.speech_stopped', event)
    })

    // Response events
    this.api.on('response.created', (event) => {
      console.log('Response created:', event.response.id)
    })

    this.api.on('response.audio.delta', (event) => {
      this.emit('response.audio.delta', event)
    })

    this.api.on('response.text.delta', (event) => {
      this.emit('response.text.delta', event)
    })

    // Forward connection events
    this.api.on('connected', () => this.emit('connected'))
    this.api.on('disconnected', (data) => this.emit('disconnected', data))
    this.api.on('error', (error) => this.emit('error', error))
  }

  /**
   * Add event listener
   */
  on(event: RealtimeEvent, callback: (data: any) => void) {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, [])
    }
    this.eventHandlers.get(event)!.push(callback)
  }

  /**
   * Remove event listener
   */
  off(event: RealtimeEvent, callback: (data: any) => void) {
    const handlers = this.eventHandlers.get(event)
    if (handlers) {
      const index = handlers.indexOf(callback)
      if (index !== -1) {
        handlers.splice(index, 1)
      }
    }
  }

  /**
   * Emit event to listeners
   */
  private emit(event: RealtimeEvent, data?: any) {
    const handlers = this.eventHandlers.get(event)
    if (handlers) {
      handlers.forEach(callback => callback(data))
    }
  }

  /**
   * Connect to FastAPI backend
   */
  async connect(customerId?: string, backendUrl?: string): Promise<void> {
    // Update backend URL if provided
    if (backendUrl) {
      this.api = new RealtimeAPI(backendUrl)
      this.setupDefaultHandlers() // Re-setup handlers with new API instance
    }
    
    // Connect to the FastAPI WebSocket endpoint
    await this.api.connect(customerId)
    
    // Get session configuration from backend and send session update
    try {
      const backendBaseUrl = backendUrl || 'http://localhost:8000'
      const configResponse = await fetch(`${backendBaseUrl}/api/session/config`)
      if (configResponse.ok) {
        const backendConfig = await configResponse.json()
        console.log('Loaded session config from backend:', backendConfig)
        
        // Merge backend config with local overrides
        const sessionPayload = this.buildSessionPayload(backendConfig)
        console.log('Sending session update with payload:', sessionPayload)
        
        this.api.sendEvent({
          type: 'session.update',
          session: sessionPayload
        })
      } else {
        console.warn('Failed to load session config from backend, using defaults')
        // Fall back to local configuration
        const sessionPayload = this.buildSessionPayload()
        this.api.sendEvent({
          type: 'session.update',
          session: sessionPayload
        })
      }
    } catch (error) {
      console.warn('Error loading session config from backend:', error)
      // Fall back to local configuration
      const sessionPayload = this.buildSessionPayload()
      this.api.sendEvent({
        type: 'session.update',
        session: sessionPayload
      })
    }
  }

  /**
   * Disconnect from the API
   */
  disconnect() {
    this.api.disconnect()
  }

  /**
   * Check connection status
   */
  get isConnected(): boolean {
    return this.api.isConnected
  }

  /**
   * Send audio data to the server
   */
  sendAudioData(audioData: ArrayBuffer) {
    if (!this.isConnected) {
      console.warn('Not connected, queueing audio data')
      this.conversation.queueInputAudio(audioData)
      return
    }

    const base64Audio = Base64Utils.encode(audioData)
    
    this.api.sendEvent({
      type: 'input_audio_buffer.append',
      audio: base64Audio
    })
  }

  /**
   * Commit audio buffer (trigger processing)
   */
  commitAudioBuffer() {
    if (!this.isConnected) return

    this.api.sendEvent({
      type: 'input_audio_buffer.commit'
    })
  }

  /**
   * Clear audio buffer
   */
  clearAudioBuffer() {
    if (!this.isConnected) return

    this.api.sendEvent({
      type: 'input_audio_buffer.clear'
    })
  }

  /**
   * Send text message
   */
  sendTextMessage(text: string) {
    if (!this.isConnected) return

    const item = {
      type: 'message',
      role: 'user',
      content: [
        {
          type: 'input_text',
          text: text
        }
      ]
    }

    this.api.sendEvent({
      type: 'conversation.item.create',
      item: item
    })

    this.api.sendEvent({
      type: 'response.create'
    })
  }

  /**
   * Cancel current response generation
   */
  cancelResponse() {
    if (!this.isConnected) return

    this.api.sendEvent({
      type: 'response.cancel'
    })
  }

  /**
   * Update session configuration
   */
  updateSession(config: Partial<RealtimeClientConfig>) {
    this.sessionConfig = { ...this.sessionConfig, ...config }
    
    if (this.isConnected) {
      const sessionPayload = this.buildSessionPayload(config)
      this.api.sendEvent({
        type: 'session.update',
        session: sessionPayload
      })
    }
  }

  /**
   * Get current conversation items
   */
  getConversationItems() {
    return this.conversation.getItems()
  }

  /**
   * Initialize audio context for playback
   */
  private initializeAudioContext() {
    if (!this.audioContext || this.audioContext.state === 'closed') {
      this.audioContext = new AudioContext({ sampleRate: 24000 })
      this.nextPlayTime = 0
    }
    return this.audioContext
  }

  /**
   * Resume audio context if suspended
   */
  private async resumeAudioContext() {
    if (this.audioContext && this.audioContext.state === 'suspended') {
      await this.audioContext.resume()
    }
  }

  /**
   * Convert base64 audio to PCM16 and play
   */
  async playAudioChunk(base64Audio: string) {
    try {
      const audioContext = this.initializeAudioContext()
      await this.resumeAudioContext()

      // Convert base64 to binary
      const audioData = atob(base64Audio)
      const audioBytes = new Uint8Array(audioData.length)
      for (let i = 0; i < audioData.length; i++) {
        audioBytes[i] = audioData.charCodeAt(i)
      }

      // Convert to Int16Array (PCM16)
      const pcm16Data = new Int16Array(audioBytes.buffer)
      
      if (pcm16Data.length === 0) return

      // Create WAV buffer for decoding
      const wavBuffer = this.createWavBuffer(pcm16Data)
      const audioBuffer = await audioContext.decodeAudioData(wavBuffer)

      // Create and play audio source
      const source = audioContext.createBufferSource()
      source.buffer = audioBuffer
      source.connect(audioContext.destination)

      const currentTime = audioContext.currentTime
      const startTime = Math.max(currentTime, this.nextPlayTime)
      
      if (this.nextPlayTime === 0) {
        this.nextPlayTime = currentTime
      }

      source.start(startTime)
      this.nextPlayTime = startTime + audioBuffer.duration

    } catch (error) {
      console.error('Failed to play audio chunk:', error)
    }
  }

  /**
   * Create WAV buffer from PCM16 data for AudioContext decoding
   */
  private createWavBuffer(pcm16Data: Int16Array): ArrayBuffer {
    const length = pcm16Data.length
    const buffer = new ArrayBuffer(44 + length * 2)
    const view = new DataView(buffer)
    
    const writeString = (offset: number, string: string) => {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i))
      }
    }

    writeString(0, 'RIFF')
    view.setUint32(4, 36 + length * 2, true)
    writeString(8, 'WAVE')
    writeString(12, 'fmt ')
    view.setUint32(16, 16, true)
    view.setUint16(20, 1, true)
    view.setUint16(22, 1, true)
    view.setUint32(24, 24000, true) // 24kHz sample rate
    view.setUint32(28, 24000 * 2, true)
    view.setUint16(32, 2, true)
    view.setUint16(34, 16, true)
    writeString(36, 'data')
    view.setUint32(40, length * 2, true)

    // Copy PCM data
    let offset = 44
    for (let i = 0; i < length; i++) {
      view.setInt16(offset, pcm16Data[i], true)
      offset += 2
    }

    return buffer
  }
}