import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Button } from '@/components/ui/button'
import { FileText, Database, ChatText, TrendUp, ArrowsClockwise, CheckCircle, XCircle } from '@phosphor-icons/react'
import { toast } from 'sonner'
import { useState, useEffect, useCallback } from 'react'
import { getApiBase } from '@/config'
import { ConversationSentimentWidget, ConversationSentimentStats } from './ConversationSentimentWidget'

type IndexStatus = 'active' | 'syncing' | 'error'

type SearchIndex = {
  id: string
  name: string
  description: string
  documentCount: number
  status: IndexStatus
  lastUpdated: string
  vectorDimensions: number
  storageUsed: string
  ai_conversations_count: number
  human_conversations_count: number
}

type DashboardStats = {
  documents_count: number
  total_storage_size: number
  index_name: string
  index_status: string
  last_updated: string
  vector_dimensions: number
  ai_conversations_count: number
  human_conversations_count: number
}

// Default index for fallback
const defaultIndex: SearchIndex = {
  id: 'internal-kb',
  name: 'internal-knowledge-base',
  description: 'Default knowledge base for all uploaded documents',
  documentCount: 0,
  status: 'error',
  lastUpdated: '2024-01-01T00:00:00Z',
  vectorDimensions: 3072,
  storageUsed: '0 MB',
  ai_conversations_count: 0,
  human_conversations_count: 0
}

export function AdminDashboard() {
  const [indexData, setIndexData] = useState(defaultIndex)
  const [loading, setLoading] = useState(false)
  const [sentimentStats, setSentimentStats] = useState<ConversationSentimentStats | null>(null)

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 MB'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const fetchDashboardStats = useCallback(async () => {
    setLoading(true)
    try {
      // Fetch dashboard stats
      const res = await fetch(`${getApiBase()}/api/admin/dashboard`)
      if (!res.ok) throw new Error(`Failed to fetch dashboard stats: ${res.status}`)
      const data: DashboardStats = await res.json()
      
      setIndexData({
        id: 'internal-kb',
        name: data.index_name,
        description: 'Knowledge base for all uploaded documents',
        documentCount: data.documents_count,
        status: data.index_status as IndexStatus,
        lastUpdated: data.last_updated,
        vectorDimensions: data.vector_dimensions,
        storageUsed: formatFileSize(data.total_storage_size),
        ai_conversations_count: data.ai_conversations_count,
        human_conversations_count: data.human_conversations_count
      })

      // Fetch sentiment stats
      try {
        const sentimentRes = await fetch(`${getApiBase()}/api/admin/conversation-sentiment-stats`)
        if (sentimentRes.ok) {
          const sentimentData: ConversationSentimentStats = await sentimentRes.json()
          setSentimentStats(sentimentData)
        }
      } catch (e) {
        console.error('Failed to fetch sentiment stats:', e)
      }
    } catch (e: any) {
      toast.error(e.message || 'Failed to load dashboard stats')
      setIndexData(defaultIndex)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchDashboardStats()
  }, [fetchDashboardStats])
  
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const handleRefreshIndex = async () => {
    setIndexData(prev => ({ ...prev, status: 'syncing' }))
    toast.success('Refreshing dashboard data...')
    
    try {
      await fetchDashboardStats()
      toast.success('Dashboard refreshed successfully')
    } catch (error) {
      toast.error('Failed to refresh dashboard')
      setIndexData(prev => ({ ...prev, status: 'error' }))
    }
  }

  const stats = [
    {
      title: 'Documents',
      value: indexData.documentCount.toString(),
      icon: FileText,
      color: 'bg-blue-500'
    },
    {
      title: 'Search Index',
      value: '1',
      icon: Database,
      color: 'bg-green-500'
    },
    {
      title: 'AI Agent Conversations',
      value: indexData.ai_conversations_count.toLocaleString(),
      icon: ChatText,
      color: 'bg-purple-500'
    },
    {
      title: 'Human Agent Conversations',
      value: indexData.human_conversations_count.toLocaleString(),
      icon: TrendUp,
      color: 'bg-orange-500'
    }
  ]

  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat) => {
          const Icon = stat.icon
          return (
            <Card key={stat.title}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {stat.title}
                </CardTitle>
                <div className={`p-2 rounded-lg ${stat.color}`}>
                  <Icon className="w-4 h-4 text-white" />
                </div>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stat.value}</div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Analytics and Recent Activity */}
      <ConversationSentimentWidget data={sentimentStats} loading={loading} />
    </div>
  )
}