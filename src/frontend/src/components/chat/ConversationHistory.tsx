import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { ChatText, Clock, User, Trash } from '@phosphor-icons/react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { getApiBase } from '@/config'

interface ConversationSummary {
  id: string
  conversation_id: string
  title?: string
  session_start: string | null
  session_end: string | null
  duration_seconds: number
  message_count: number
  first_message_preview: string
}

interface ConversationHistoryProps {
  customerId: string | null
  onConversationSelect?: (conversationId: string) => void
  className?: string
}

export function ConversationHistory({ 
  customerId, 
  onConversationSelect,
  className 
}: ConversationHistoryProps) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  
  const API_BASE = getApiBase()

  useEffect(() => {
    if (customerId) {
      fetchConversations()
    } else {
      setConversations([])
    }
  }, [customerId])

  const fetchConversations = async () => {
    if (!customerId) return

    setLoading(true)
    try {
      const response = await fetch(`${API_BASE}/api/conversations/${customerId}?limit=50`)
      if (!response.ok) {
        throw new Error('Failed to fetch conversation history')
      }
      const data = await response.json()
      setConversations(data)
    } catch (error) {
      console.error('Error fetching conversation history:', error)
      toast.error('Failed to load conversation history')
      setConversations([])
    } finally {
      setLoading(false)
    }
  }

  const handleConversationClick = (conversationId: string, id: string) => {
    setSelectedId(id)
    if (onConversationSelect) {
      onConversationSelect(conversationId)
    }
  }

  const handleDelete = async (e: React.MouseEvent, conversationId: string, documentId: string) => {
    e.stopPropagation() // Prevent triggering the conversation click
    
    if (!customerId) return
    
    if (!confirm('Are you sure you want to delete this conversation? This action cannot be undone.')) {
      return
    }

    setDeletingId(documentId)
    try {
      const response = await fetch(`${API_BASE}/api/conversations/${customerId}/${documentId}`, {
        method: 'DELETE'
      })
      
      if (!response.ok) {
        throw new Error('Failed to delete conversation')
      }
      
      // Remove from local state
      setConversations(prev => prev.filter(conv => conv.id !== documentId))
      
      // Clear selection if deleted conversation was selected
      if (selectedId === documentId) {
        setSelectedId(null)
      }
      
      toast.success('Conversation deleted')
    } catch (error) {
      console.error('Error deleting conversation:', error)
      toast.error('Failed to delete conversation')
    } finally {
      setDeletingId(null)
    }
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Unknown'
    
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    if (mins === 0) return `${secs}s`
    return `${mins}m ${secs}s`
  }

  if (!customerId) {
    return (
      <Card className={cn("h-full", className)}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ChatText className="w-5 h-5" />
            Conversation History
          </CardTitle>
          <CardDescription>
            Select a customer to view their conversation history
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-40 text-muted-foreground text-sm">
            No customer selected
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={cn("h-full flex flex-col", className)}>
      <CardHeader className="flex-shrink-0">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <ChatText className="w-5 h-5" />
            History
          </CardTitle>
          <Button 
            variant="ghost" 
            size="sm"
            onClick={fetchConversations}
            disabled={loading}
          >
            Refresh
          </Button>
        </div>
        <CardDescription>
          Previous conversations with AI
        </CardDescription>
      </CardHeader>
      
      <CardContent className="flex-1 min-h-0 p-0">
        <ScrollArea className="h-full px-6 pb-6">
          {loading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              ))}
            </div>
          ) : conversations.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 text-muted-foreground text-sm">
              <ChatText className="w-12 h-12 mb-2 opacity-20" />
              <p>No conversation history</p>
              <p className="text-xs mt-1">Start a call to create history</p>
            </div>
          ) : (
            <div className="space-y-2">
              {conversations.map((conv) => (
                <div
                  key={conv.id}
                  className="relative group"
                  onMouseEnter={() => setHoveredId(conv.id)}
                  onMouseLeave={() => setHoveredId(null)}
                >
                  <button
                    onClick={() => handleConversationClick(conv.conversation_id, conv.id)}
                    disabled={deletingId === conv.id}
                    className={cn(
                      "w-full text-left p-3 pr-10 rounded-lg border transition-colors",
                      "hover:bg-accent hover:border-primary/50",
                      "disabled:opacity-50 disabled:cursor-not-allowed",
                      selectedId === conv.id 
                        ? "bg-accent border-primary" 
                        : "bg-card border-border"
                    )}
                  >
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <span className="text-sm font-medium text-foreground line-clamp-1">
                        {conv.title || conv.first_message_preview}
                      </span>
                      <Badge variant="secondary" className="flex-shrink-0 text-xs">
                        {conv.message_count}
                      </Badge>
                    </div>
                    
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatDate(conv.session_start)}
                      </span>
                      {conv.duration_seconds > 0 && (
                        <span>
                          {formatDuration(conv.duration_seconds)}
                        </span>
                      )}
                    </div>
                  </button>
                  
                  {/* Delete button - shows on hover */}
                  {hoveredId === conv.id && (
                    <button
                      onClick={(e) => handleDelete(e, conv.conversation_id, conv.id)}
                      disabled={deletingId === conv.id}
                      className={cn(
                        "absolute right-2 top-1/2 -translate-y-1/2",
                        "p-1.5 rounded-md",
                        "bg-destructive/10 hover:bg-destructive/20",
                        "text-destructive hover:text-destructive",
                        "transition-colors",
                        "disabled:opacity-50 disabled:cursor-not-allowed"
                      )}
                      title="Delete conversation"
                    >
                      <Trash className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
