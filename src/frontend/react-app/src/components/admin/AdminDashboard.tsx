import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Button } from '@/components/ui/button'
import { FileText, Database, ChatText, TrendUp, ArrowsClockwise, CheckCircle, XCircle } from '@phosphor-icons/react'
import { toast } from 'sonner'
import { useState } from 'react'

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
}

// Default index for the simplified system
const defaultIndex: SearchIndex = {
  id: 'internal-kb',
  name: 'internal-knowledge-base',
  description: 'Default knowledge base for all uploaded documents',
  documentCount: 73,
  status: 'active',
  lastUpdated: '2024-01-15T10:30:00Z',
  vectorDimensions: 1536,
  storageUsed: '4.2 GB'
}

export function AdminDashboard() {
  const [indexData, setIndexData] = useState(defaultIndex)
  
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const handleRefreshIndex = () => {
    setIndexData(prev => ({ ...prev, status: 'syncing' }))
    toast.success('Index refresh started')
    
    // Simulate refresh completion
    setTimeout(() => {
      setIndexData(prev => ({ 
        ...prev, 
        status: 'active',
        lastUpdated: new Date().toISOString()
      }))
      toast.success('Index refresh completed')
    }, 3000)
  }

  const stats = [
    {
      title: 'Documents',
      value: indexData.documentCount.toString(),
      description: 'Total uploaded files',
      icon: FileText,
      trend: '+12%',
      color: 'bg-blue-500'
    },
    {
      title: 'Search Index',
      value: '1',
      description: 'Active knowledge base',
      icon: Database,
      trend: 'Ready',
      color: 'bg-green-500'
    },
    {
      title: 'Conversations',
      value: '1,247',
      description: 'Total chat sessions',
      icon: ChatText,
      trend: '+18%',
      color: 'bg-purple-500'
    },
    {
      title: 'Success Rate',
      value: '94.2%',
      description: 'AI response accuracy',
      icon: TrendUp,
      trend: '+2.1%',
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
                <div className="flex items-center justify-between mt-2">
                  <p className="text-xs text-muted-foreground">
                    {stat.description}
                  </p>
                  <Badge variant="secondary" className="text-xs">
                    {stat.trend}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Knowledge Base Index Info */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Database className="w-5 h-5 text-primary" />
                Internal Knowledge Base
              </CardTitle>
              <CardDescription>
                {indexData.description}
              </CardDescription>
            </div>
            <div className="flex items-center gap-3">
              <Badge variant={
                indexData.status === 'active' ? 'default' :
                indexData.status === 'syncing' ? 'secondary' : 'destructive'
              }>
                {indexData.status === 'active' && <CheckCircle className="w-3 h-3 mr-1" />}
                {indexData.status === 'syncing' && <ArrowsClockwise className="w-3 h-3 mr-1 animate-spin" />}
                {indexData.status === 'error' && <XCircle className="w-3 h-3 mr-1" />}
                {indexData.status}
              </Badge>
              <Button
                size="sm"
                variant="outline"
                onClick={handleRefreshIndex}
                disabled={indexData.status === 'syncing'}
              >
                <ArrowsClockwise className={`w-4 h-4 mr-2 ${indexData.status === 'syncing' ? 'animate-spin' : ''}`} />
                Refresh Index
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Documents</p>
              <p className="text-2xl font-bold">{indexData.documentCount}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Vector Dimensions</p>
              <p className="text-2xl font-bold">{indexData.vectorDimensions}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Storage Used</p>
              <p className="text-2xl font-bold">{indexData.storageUsed}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Last Updated</p>
              <p className="text-lg font-semibold">{formatDate(indexData.lastUpdated)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>System Health</CardTitle>
            <CardDescription>Current system performance metrics</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-sm font-medium">API Response Time</span>
                <span className="text-sm text-muted-foreground">245ms</span>
              </div>
              <Progress value={75} className="h-2" />
            </div>
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-sm font-medium">Search Index Health</span>
                <span className="text-sm text-muted-foreground">98%</span>
              </div>
              <Progress value={98} className="h-2" />
            </div>
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-sm font-medium">Voice Processing</span>
                <span className="text-sm text-muted-foreground">92%</span>
              </div>
              <Progress value={92} className="h-2" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
            <CardDescription>Latest system events and operations</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[
                { action: 'Document uploaded', file: 'customer_guide.pdf', time: '2 minutes ago', status: 'success' },
                { action: 'Knowledge base updated', file: 'internal-knowledge-base', time: '15 minutes ago', status: 'success' },
                { action: 'Chat session started', file: 'User #1247', time: '32 minutes ago', status: 'active' },
                { action: 'Synthetic data generated', file: '500 records', time: '1 hour ago', status: 'success' }
              ].map((activity, index) => (
                <div key={index} className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">{activity.action}</p>
                    <p className="text-xs text-muted-foreground">{activity.file}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-muted-foreground">{activity.time}</p>
                    <Badge 
                      variant={activity.status === 'success' ? 'default' : 'secondary'}
                      className="text-xs"
                    >
                      {activity.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}