import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChatCircle } from '@phosphor-icons/react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { useState, useMemo, useEffect } from 'react'

type ProductSentimentStats = {
  product_name: string
  total_conversations: number
  positive: number
  negative: number
  neutral: number
}

type ConversationData = {
  product: string
  sentiment: string
  agent_id: string
  conversation_date?: string | null
  messages?: Array<{
    sender: string
    message: string
  }> | null
  topic?: string | null
}

export type ConversationSentimentStats = {
  products: ProductSentimentStats[]
  overall_sentiment_distribution: {
    positive: number
    negative: number
    neutral: number
  }
  total_conversations: number
  conversations: ConversationData[]
}

interface ConversationSentimentWidgetProps {
  data: ConversationSentimentStats | null
  loading?: boolean
}

const AGENT_LIST = ['adam', 'betrace', 'curie', 'davinci', 'emil', 'fred']

// Helper function to get ISO week number and year
const getWeekLabel = (date: Date): string => {
  const tempDate = new Date(date.getTime())
  tempDate.setHours(0, 0, 0, 0)
  // Thursday in current week decides the year
  tempDate.setDate(tempDate.getDate() + 3 - (tempDate.getDay() + 6) % 7)
  // January 4 is always in week 1
  const week1 = new Date(tempDate.getFullYear(), 0, 4)
  // Adjust to Thursday in week 1 and count number of weeks from date to week1
  const weekNum = 1 + Math.round(((tempDate.getTime() - week1.getTime()) / 86400000 - 3 + (week1.getDay() + 6) % 7) / 7)
  const year = tempDate.getFullYear()
  return `Week ${weekNum}, ${year}`
}

export function ConversationSentimentWidget({ data, loading }: ConversationSentimentWidgetProps) {
  const [selectedAgent, setSelectedAgent] = useState<string>('all')
  const [selectedProduct, setSelectedProduct] = useState<string>('all')
  const [selectedTopic, setSelectedTopic] = useState<string>('all')
  
  // Modal state for showing conversation details
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [selectedWeek, setSelectedWeek] = useState<string>('')
  const [selectedSentiment, setSelectedSentiment] = useState<string>('')
  const [modalConversations, setModalConversations] = useState<ConversationData[]>([])
  const [expandedConvIndex, setExpandedConvIndex] = useState<number | null>(null)

  // Get unique product list from data (filtered by selected agent and topic)
  const productList = useMemo(() => {
    if (!data || !data.conversations) return []
    
    // Filter conversations based on currently selected agent and topic
    let filteredConvs = data.conversations
    
    if (selectedAgent !== 'all') {
      filteredConvs = filteredConvs.filter(conv => conv.agent_id === selectedAgent)
    }
    
    if (selectedTopic !== 'all') {
      filteredConvs = filteredConvs.filter(conv => conv.topic === selectedTopic)
    }
    
    const products = new Set(filteredConvs.map(conv => conv.product))
    return Array.from(products).sort()
  }, [data, selectedAgent, selectedTopic])

  // Get unique topic list from data (filtered by selected agent and product)
  const topicList = useMemo(() => {
    if (!data || !data.conversations) return []
    
    // Filter conversations based on currently selected agent and product
    let filteredConvs = data.conversations
    
    if (selectedAgent !== 'all') {
      filteredConvs = filteredConvs.filter(conv => conv.agent_id === selectedAgent)
    }
    
    if (selectedProduct !== 'all') {
      filteredConvs = filteredConvs.filter(conv => conv.product === selectedProduct)
    }
    
    const topics = new Set(
      filteredConvs
        .map(conv => conv.topic)
        .filter((topic): topic is string => typeof topic === 'string' && topic !== null)
    )
    return Array.from(topics).sort()
  }, [data, selectedAgent, selectedProduct])

  // Get unique agent list from data (filtered by selected topic and product)
  const agentList = useMemo(() => {
    if (!data || !data.conversations) return AGENT_LIST
    
    // Filter conversations based on currently selected topic and product
    let filteredConvs = data.conversations
    
    if (selectedTopic !== 'all') {
      filteredConvs = filteredConvs.filter(conv => conv.topic === selectedTopic)
    }
    
    if (selectedProduct !== 'all') {
      filteredConvs = filteredConvs.filter(conv => conv.product === selectedProduct)
    }
    
    const agents = new Set(filteredConvs.map(conv => conv.agent_id))
    // Return only agents that exist in the filtered data, maintaining the original order
    return AGENT_LIST.filter(agent => agents.has(agent))
  }, [data, selectedTopic, selectedProduct])

  // Auto-reset filters when selected value is no longer available
  useEffect(() => {
    if (selectedProduct !== 'all' && !productList.includes(selectedProduct)) {
      setSelectedProduct('all')
    }
  }, [productList, selectedProduct])
  
  useEffect(() => {
    if (selectedTopic !== 'all' && !topicList.includes(selectedTopic)) {
      setSelectedTopic('all')
    }
  }, [topicList, selectedTopic])
  
  useEffect(() => {
    if (selectedAgent !== 'all' && !agentList.includes(selectedAgent)) {
      setSelectedAgent('all')
    }
  }, [agentList, selectedAgent])

  // Filter and re-aggregate data by calendar week
  const filteredData = useMemo(() => {
    if (!data || !data.conversations) return null
    
    // Filter conversations by agent, product, and topic
    let conversations = data.conversations
    
    // Filter by agent
    if (selectedAgent !== 'all') {
      conversations = conversations.filter(conv => conv.agent_id === selectedAgent)
    }
    
    // Filter by product
    if (selectedProduct !== 'all') {
      conversations = conversations.filter(conv => conv.product === selectedProduct)
    }
    
    // Filter by topic
    if (selectedTopic !== 'all') {
      conversations = conversations.filter(conv => conv.topic === selectedTopic)
    }
    
    // Group by calendar week
    const weeklyStats: Record<string, { positive: number; negative: number; neutral: number; total: number }> = {}
    const overallSentiments = { positive: 0, negative: 0, neutral: 0 }
    
    conversations.forEach(conv => {
      if (!conv.conversation_date) return
      
      try {
        const convDate = new Date(conv.conversation_date)
        const weekLabel = getWeekLabel(convDate)
        const sentiment = conv.sentiment
        
        // Initialize week if not exists
        if (!weeklyStats[weekLabel]) {
          weeklyStats[weekLabel] = { positive: 0, negative: 0, neutral: 0, total: 0 }
        }
        
        // Count sentiments per week
        if (sentiment in weeklyStats[weekLabel]) {
          weeklyStats[weekLabel][sentiment as keyof typeof weeklyStats[typeof weekLabel]]++
        }
        weeklyStats[weekLabel].total++
        
        // Count overall sentiments
        if (sentiment in overallSentiments) {
          overallSentiments[sentiment as keyof typeof overallSentiments]++
        }
      } catch (e) {
        // Skip conversations with invalid dates
      }
    })
    
    // Convert to array and sort by week chronologically
    const weeks = Object.entries(weeklyStats)
      .map(([week, stats]) => ({
        week,
        ...stats
      }))
      .sort((a, b) => {
        // Extract week number and year for proper chronological sorting
        const parseWeek = (weekStr: string) => {
          const match = weekStr.match(/Week (\d+), (\d+)/)
          if (match) {
            const weekNum = parseInt(match[1])
            const year = parseInt(match[2])
            return year * 100 + weekNum
          }
          return 0
        }
        return parseWeek(a.week) - parseWeek(b.week)
      })
    
    return {
      weeks,
      overall_sentiment_distribution: overallSentiments,
      total_conversations: conversations.length
    }
  }, [data, selectedAgent, selectedProduct, selectedTopic])

  // Handle bar click to show conversations for a specific week and sentiment
  const handleBarClick = (weekLabel: string, sentiment: string) => {
    if (!data || !data.conversations) return
    
    // Filter conversations matching the clicked week and sentiment
    const filteredConvs = data.conversations.filter(conv => {
      if (!conv.conversation_date) return false
      
      try {
        const convDate = new Date(conv.conversation_date)
        const convWeek = getWeekLabel(convDate)
        
        // Apply agent filter
        const matchesAgent = selectedAgent === 'all' || conv.agent_id === selectedAgent
        // Apply product filter
        const matchesProduct = selectedProduct === 'all' || conv.product === selectedProduct
        // Apply topic filter
        const matchesTopic = selectedTopic === 'all' || conv.topic === selectedTopic
        
        return convWeek === weekLabel && 
               conv.sentiment === sentiment && 
               matchesAgent && 
               matchesProduct &&
               matchesTopic
      } catch (e) {
        return false
      }
    })
    
    setSelectedWeek(weekLabel)
    setSelectedSentiment(sentiment)
    setModalConversations(filteredConvs)
    setIsModalOpen(true)
    setExpandedConvIndex(null) // Reset expanded state
  }

  // Transform data for recharts - weeks on X-axis with stacked sentiments
  const chartData = filteredData?.weeks.map(week => ({
    name: week.week,
    positive: week.positive,
    neutral: week.neutral,
    negative: week.negative,
    total: week.total
  })) || []

  // Custom tooltip
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const total = payload.reduce((sum: number, entry: any) => sum + entry.value, 0)
      return (
        <div className="bg-popover border border-border rounded-lg shadow-lg p-3">
          <p className="font-semibold mb-2">{label}</p>
          {payload.map((entry: any, index: number) => (
            <div key={index} className="flex items-center gap-2 text-sm">
              <div 
                className="w-3 h-3 rounded-sm" 
                style={{ backgroundColor: entry.color }}
              />
              <span className="capitalize">{entry.name}:</span>
              <span className="font-semibold">{entry.value}</span>
              <span className="text-muted-foreground">
                ({((entry.value / total) * 100).toFixed(1)}%)
              </span>
            </div>
          ))}
          <div className="mt-2 pt-2 border-t border-border text-sm font-semibold">
            Total: {total}
          </div>
        </div>
      )
    }
    return null
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <ChatCircle className="w-5 h-5 text-primary" />
              Human Conversation Sentiment Analytics
            </CardTitle>
            <CardDescription>
              {filteredData ? (
                <>
                  Showing {filteredData.total_conversations} conversation{filteredData.total_conversations !== 1 ? 's' : ''} over time
                  {selectedAgent !== 'all' && <span className="font-semibold"> by {selectedAgent}</span>}
                  {selectedProduct !== 'all' && <span className="font-semibold"> for {selectedProduct}</span>}
                  {selectedTopic !== 'all' && <span className="font-semibold"> about {selectedTopic}</span>}
                </>
              ) : (
                'Sentiment trends over calendar weeks'
              )}
            </CardDescription>
          </div>
          
          {/* Filters: Product and Agent */}
          {data && data.conversations.length > 0 && (
            <div className="flex items-center gap-4">
              {/* Topic Filter */}
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-muted-foreground">Topic:</label>
                <Select value={selectedTopic} onValueChange={setSelectedTopic}>
                  <SelectTrigger className="w-[150px]">
                    <SelectValue placeholder="Select topic" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Topics</SelectItem>
                    {topicList.map(topic => (
                      <SelectItem key={topic} value={topic}>
                        {topic.charAt(0).toUpperCase() + topic.slice(1)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              {/* Product Filter */}
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-muted-foreground">Product:</label>
                <Select value={selectedProduct} onValueChange={setSelectedProduct}>
                  <SelectTrigger className="w-[150px]">
                    <SelectValue placeholder="Select product" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Products</SelectItem>
                    {productList.map(product => (
                      <SelectItem key={product} value={product}>
                        {product}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              {/* Agent Filter */}
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-muted-foreground">Agent:</label>
                <Select value={selectedAgent} onValueChange={setSelectedAgent}>
                  <SelectTrigger className="w-[150px]">
                    <SelectValue placeholder="Select agent" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Agents</SelectItem>
                    {agentList.map(agent => (
                      <SelectItem key={agent} value={agent}>
                        {agent.charAt(0).toUpperCase() + agent.slice(1)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="h-80 flex items-center justify-center text-muted-foreground">
            Loading sentiment data...
          </div>
        ) : !filteredData || chartData.length === 0 ? (
          <div className="h-80 flex items-center justify-center text-muted-foreground">
            No conversation data available yet. Generate synthetic data to see sentiment analytics.
          </div>
        ) : (
          <div className="space-y-4">
            {/* Overall stats */}
            <div className="grid grid-cols-4 gap-4">
              <div className="text-center p-3 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Total Conversations</p>
                <p className="text-2xl font-bold">{filteredData.total_conversations}</p>
              </div>
              <div className="text-center p-3 bg-green-50 dark:bg-green-950 rounded-lg">
                <p className="text-sm text-green-700 dark:text-green-300">Positive</p>
                <p className="text-2xl font-bold text-green-700 dark:text-green-300">
                  {filteredData.overall_sentiment_distribution.positive}
                </p>
              </div>
              <div className="text-center p-3 bg-gray-50 dark:bg-gray-900 rounded-lg">
                <p className="text-sm text-gray-700 dark:text-gray-300">Neutral</p>
                <p className="text-2xl font-bold text-gray-700 dark:text-gray-300">
                  {filteredData.overall_sentiment_distribution.neutral}
                </p>
              </div>
              <div className="text-center p-3 bg-red-50 dark:bg-red-950 rounded-lg">
                <p className="text-sm text-red-700 dark:text-red-300">Negative</p>
                <p className="text-2xl font-bold text-red-700 dark:text-red-300">
                  {filteredData.overall_sentiment_distribution.negative}
                </p>
              </div>
            </div>

            {/* Stacked bar chart - Calendar weeks on X-axis */}
            <ResponsiveContainer width="100%" height={400}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis 
                  dataKey="name" 
                  className="text-sm"
                  angle={-25}
                  textAnchor="end"
                  height={100}
                  interval={0}
                />
                <YAxis 
                  className="text-sm"
                  label={{ value: 'Total Conversations', angle: -90, position: 'insideLeft' }}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend 
                  wrapperStyle={{ paddingTop: '20px' }}
                  iconType="square"
                />
                <Bar 
                  dataKey="positive" 
                  stackId="a" 
                  fill="#10b981" 
                  name="Positive"
                  radius={[0, 0, 0, 0]}
                  onClick={(data) => handleBarClick(data.name, 'positive')}
                  cursor="pointer"
                />
                <Bar 
                  dataKey="neutral" 
                  stackId="a" 
                  fill="#6b7280" 
                  name="Neutral"
                  radius={[0, 0, 0, 0]}
                  onClick={(data) => handleBarClick(data.name, 'neutral')}
                  cursor="pointer"
                />
                <Bar 
                  dataKey="negative" 
                  stackId="a" 
                  fill="#ef4444" 
                  name="Negative"
                  radius={[4, 4, 0, 0]}
                  onClick={(data) => handleBarClick(data.name, 'negative')}
                  cursor="pointer"
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
      
      {/* Conversation Details Modal */}
      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="max-w-4xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Badge variant={selectedSentiment === 'positive' ? 'default' : selectedSentiment === 'negative' ? 'destructive' : 'secondary'}>
                {selectedSentiment.charAt(0).toUpperCase() + selectedSentiment.slice(1)}
              </Badge>
              Conversations - {selectedWeek}
            </DialogTitle>
            <DialogDescription>
              Showing {modalConversations.length} {selectedSentiment} conversation{modalConversations.length !== 1 ? 's' : ''}
              {selectedAgent !== 'all' && <span> by {selectedAgent}</span>}
              {selectedProduct !== 'all' && <span> for {selectedProduct}</span>}
              {selectedTopic !== 'all' && <span> about {selectedTopic}</span>}
            </DialogDescription>
          </DialogHeader>
          
          <ScrollArea className="max-h-[60vh] pr-4">
            {modalConversations.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No conversations found for this selection.
              </div>
            ) : (
              <div className="space-y-4">
                {modalConversations.map((conv, index) => (
                  <div key={index} className="border rounded-lg p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{conv.agent_id}</Badge>
                        <span className="text-sm text-muted-foreground">{conv.product}</span>
                        {conv.topic && (
                          <Badge variant="secondary" className="text-xs">
                            {conv.topic}
                          </Badge>
                        )}
                      </div>
                      {conv.conversation_date && (
                        <span className="text-xs text-muted-foreground">
                          {new Date(conv.conversation_date).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                    
                    {conv.messages && conv.messages.length > 0 && (
                      <div className="space-y-2">
                        <button
                          onClick={() => setExpandedConvIndex(expandedConvIndex === index ? null : index)}
                          className="text-sm text-primary hover:underline font-medium"
                        >
                          {expandedConvIndex === index ? '▼ Hide conversation' : '▶ Show conversation'} ({conv.messages.length} messages)
                        </button>
                        
                        {expandedConvIndex === index && (
                          <div className="space-y-2 mt-2 pl-4 border-l-2 border-muted">
                            {conv.messages.map((msg, msgIndex) => (
                              <div key={msgIndex} className={`p-3 rounded-lg ${
                                msg.sender === 'customer' 
                                  ? 'bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800/50' 
                                  : 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800/50'
                              }`}>
                                <div className="flex items-center gap-2 mb-1">
                                  <span className={`text-xs font-semibold ${
                                    msg.sender === 'customer' 
                                      ? 'text-blue-700 dark:text-blue-400' 
                                      : 'text-green-700 dark:text-green-400'
                                  }`}>
                                    {msg.sender === 'customer' ? '👤 Customer' : '🎧 Agent'}
                                  </span>
                                </div>
                                <p className="text-sm text-foreground">{msg.message}</p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
