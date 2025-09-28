// Phase 2: TODO - Wire RealtimeClient into VoiceChatInterface and supply a backend token provider

/**
 * Azure OpenAI Realtime API Client for TypeScript/React
 * Provides real-time voice communication with Azure OpenAI's realtime service
 * 
 * Based on Python realtime2.py implementation
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
 * WebSocket connection manager for Azure OpenAI Realtime API
 */
export class RealtimeAPI {
  private ws: WebSocket | null = null
  private url: string = ''
  private apiKey: string = ''
  private eventListeners = new Map<RealtimeEvent, Set<(data: any) => void>>()

  constructor(url?: string, apiKey?: string) {
    if (url && apiKey) {
      this.url = url
      this.apiKey = apiKey
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
   * Connect to the Azure OpenAI Realtime API
   */
  async connect(websocketUrl?: string, apiKey?: string, deployment?: string, apiVersion?: string): Promise<void> {
    if (websocketUrl) this.url = websocketUrl
    if (apiKey) this.apiKey = apiKey

    if (!this.url || !this.apiKey) {
      throw new Error('WebSocket URL and API key are required')
    }

    return new Promise((resolve, reject) => {
      this.emit('connecting')
      
      // Check if this is a local proxy URL vs direct Azure URL
      const isLocalProxy = this.url.includes('localhost') || this.url.includes('127.0.0.1')
      
      let wsUrl: string
      if (isLocalProxy) {
        // Local proxy - use the URL as-is, proxy will handle Azure authentication
        wsUrl = this.url
        console.log('Connecting to local WebSocket proxy:', wsUrl)
      } else {
        // Direct Azure connection - construct full URL with parameters
        const version = apiVersion || '2024-10-01-preview'
        wsUrl = `${this.url}/openai/realtime?api-version=${version}`
        if (deployment) wsUrl += `&deployment=${deployment}`
        console.log('Connecting directly to Azure OpenAI:', wsUrl)
      }
      
      console.log('Using deployment:', deployment)
      console.log('Using token:', this.apiKey.substring(0, 20) + '...')
      
      // Create WebSocket connection
      this.ws = new WebSocket(wsUrl)

      this.ws.addEventListener('open', (event) => {
        console.log('WebSocket connected successfully')
        
        if (!isLocalProxy) {
          // For direct Azure connections, send authentication via session update
          try {
            const sessionUpdate = {
              type: 'session.update',
              session: {
                modalities: ['text', 'audio'],
                instructions: 'You are a helpful AI assistant.',
                voice: 'alloy',
                input_audio_format: 'pcm16',
                output_audio_format: 'pcm16',
                input_audio_transcription: {
                  model: 'whisper-1'
                }
              }
            }
            
            this.ws!.send(JSON.stringify(sessionUpdate))
            console.log('Sent session update with auth context')
          } catch (error) {
            console.error('Session update failed:', error)
          }
        }
        
        console.log('WebSocket connection established')
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
        console.error('Connection failed with error:', event)
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
 * High-level interface for Azure OpenAI Realtime API
 */
export class RealtimeClient {
  private api: RealtimeAPI
  private conversation: RealtimeConversation
  private sessionConfig: RealtimeClientConfig
  private eventHandlers = new Map<RealtimeEvent, ((data: any) => void)[]>()
  private connectionConfig: {
    websocketUrl?: string
    deployment?: string
    apiVersion?: string
  } = {}

  constructor(
    apiKey: string,
    config: RealtimeClientConfig = {}
  ) {
    // Default configuration
    this.sessionConfig = {
      model: config.model ?? 'gpt-realtime',
      voice: config.voice ?? 'alloy',
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

  this.api = new RealtimeAPI()
  this.conversation = new RealtimeConversation()

  // Set up default event handlers
  this.setupDefaultHandlers()
  }

  private buildSessionPayload(overrides: Partial<RealtimeClientConfig> = {}) {
    const config: RealtimeClientConfig = { ...this.sessionConfig, ...overrides }
    const session: Record<string, unknown> = {}

    if (config.model) session.model = config.model
    if (config.voice) session.voice = config.voice
    // Azure Realtime API currently ignores temperature/max tokens at the session level
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
   * Get WebSocket URL for Azure OpenAI Realtime API from environment
   */
  private getWebSocketUrl(): string {
    // Get from backend via an API call since we can't access env vars directly in browser
    // This will be set when we get the token from backend
    return '' // Will be populated from backend response
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
   * Connect to Azure OpenAI Realtime API
   */
  async connect(websocketUrl?: string, apiKey?: string, deployment?: string, apiVersion?: string): Promise<void> {
    // Store connection configuration
    if (websocketUrl) this.connectionConfig.websocketUrl = websocketUrl
    if (deployment) this.connectionConfig.deployment = deployment
    if (apiVersion) this.connectionConfig.apiVersion = apiVersion
    
    // Connect to the WebSocket API
    await this.api.connect(
      this.connectionConfig.websocketUrl,
      apiKey,
      this.connectionConfig.deployment,
      this.connectionConfig.apiVersion
    )
    
    // Send session configuration immediately after connection
    const sessionPayload = this.buildSessionPayload()
    console.log('Sending session update with payload:', sessionPayload)
    this.api.sendEvent({
      type: 'session.update',
      session: sessionPayload
    })
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
}