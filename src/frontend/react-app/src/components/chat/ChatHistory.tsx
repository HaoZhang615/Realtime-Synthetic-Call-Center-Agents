import { useEffect, useRef } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { User, Robot, Download, Copy } from '@phosphor-icons/react'
import { toast } from 'sonner'

type ChatMessage = {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: string
  audioUrl?: string
}

interface ChatHistoryProps {
  messages: ChatMessage[]
  currentTranscript: string
  className?: string
}

export function ChatHistory({ messages, currentTranscript, className = '' }: ChatHistoryProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!scrollRef.current) return
    // Radix ScrollArea viewport
    const viewport = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]') as HTMLDivElement | null
    const el = viewport || scrollRef.current
    el.scrollTop = el.scrollHeight
  }, [messages, currentTranscript])

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const copyToClipboard = (content: string) => {
    navigator.clipboard.writeText(content)
    toast.success('Message copied to clipboard')
  }

  const exportTranscript = () => {
    const transcript = messages
      .map(msg => `[${formatTime(msg.timestamp)}] ${msg.type === 'user' ? 'You' : 'Assistant'}: ${msg.content}`)
      .join('\n')
    
    const blob = new Blob([transcript], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `chat-transcript-${new Date().toISOString().split('T')[0]}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    
    toast.success('Transcript exported')
  }

  return (
    <div className={`flex flex-col h-full min-h-0 ${className}`}>
      {/* Export Button */}
      {messages.length > 0 && (
        <div className="flex justify-end mb-4">
          <Button
            size="sm"
            variant="outline"
            onClick={exportTranscript}
            className="gap-2"
          >
            <Download className="w-4 h-4" />
            Export Transcript
          </Button>
        </div>
      )}

      {/* Messages */}
      <ScrollArea
        className="flex-1 min-h-0 max-h-[500px] overflow-y-auto pr-1"
        ref={scrollRef}
      >
        <div className="space-y-4 pr-4">
          {messages.length === 0 && !currentTranscript && (
            <div className="text-center text-muted-foreground py-12">
              <Robot className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>Start a call to begin your conversation</p>
            </div>
          )}

          {messages
            .filter(m => m.content && m.content.trim().length > 0)
            .map((message) => (
            <div
              key={message.id}
              className={`flex gap-3 ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {message.type === 'assistant' && (
                <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
                  <Robot className="w-4 h-4 text-primary-foreground" />
                </div>
              )}

              <div
                className={`max-w-[70%] rounded-lg p-4 ${
                  message.type === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm leading-relaxed">{message.content}</p>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => copyToClipboard(message.content)}
                    className={`w-6 h-6 p-0 flex-shrink-0 ${
                      message.type === 'user' 
                        ? 'hover:bg-primary-foreground/10' 
                        : 'hover:bg-muted-foreground/10'
                    }`}
                  >
                    <Copy className="w-3 h-3" />
                  </Button>
                </div>
                
                <div className="flex items-center justify-between mt-2">
                  <span className={`text-xs ${
                    message.type === 'user' 
                      ? 'text-primary-foreground/70' 
                      : 'text-muted-foreground/70'
                  }`}>
                    {formatTime(message.timestamp)}
                  </span>
                  
                  {message.audioUrl && (
                    <Button
                      size="sm" 
                      variant="ghost"
                      className="text-xs p-1 h-auto"
                    >
                      Play Audio
                    </Button>
                  )}
                </div>
              </div>

              {message.type === 'user' && (
                <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center flex-shrink-0">
                  <User className="w-4 h-4 text-accent-foreground" />
                </div>
              )}
            </div>
          ))}

          {/* Live Transcript */}
          {currentTranscript && (
            <div className="flex gap-3 justify-end">
              <div className="max-w-[70%] rounded-lg p-4 bg-primary/70 text-primary-foreground">
                <p className="text-sm leading-relaxed">
                  {currentTranscript === '…' ? (
                    <span className="flex items-center gap-2">
                      <span>Listening</span>
                      <span className="flex gap-1">
                        <span className="w-1 h-1 bg-primary-foreground rounded-full animate-pulse" />
                        <span className="w-1 h-1 bg-primary-foreground rounded-full animate-pulse" style={{ animationDelay: '0.2s' }} />
                        <span className="w-1 h-1 bg-primary-foreground rounded-full animate-pulse" style={{ animationDelay: '0.4s' }} />
                      </span>
                    </span>
                  ) : currentTranscript }
                </p>
                <div className="flex items-center gap-2 mt-2">
                  <Badge variant="secondary" className="text-xs">
                    Live
                  </Badge>
                  <div className="flex gap-1">
                    <div className="w-1 h-1 bg-primary-foreground rounded-full animate-pulse"></div>
                    <div className="w-1 h-1 bg-primary-foreground rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></div>
                    <div className="w-1 h-1 bg-primary-foreground rounded-full animate-pulse" style={{ animationDelay: '0.4s' }}></div>
                  </div>
                </div>
              </div>
              
              <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center flex-shrink-0">
                <User className="w-4 h-4 text-accent-foreground" />
              </div>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}