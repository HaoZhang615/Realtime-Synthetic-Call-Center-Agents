import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChatCircle } from '@phosphor-icons/react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

type ProductSentimentStats = {
  product_name: string
  total_conversations: number
  positive: number
  negative: number
  neutral: number
}

export type ConversationSentimentStats = {
  products: ProductSentimentStats[]
  overall_sentiment_distribution: {
    positive: number
    negative: number
    neutral: number
  }
  total_conversations: number
}

interface ConversationSentimentWidgetProps {
  data: ConversationSentimentStats | null
  loading?: boolean
}

export function ConversationSentimentWidget({ data, loading }: ConversationSentimentWidgetProps) {
  // Transform data for recharts
  const chartData = data?.products.map(product => ({
    name: product.product_name,
    positive: product.positive,
    neutral: product.neutral,
    negative: product.negative,
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
        <CardTitle className="flex items-center gap-2">
          <ChatCircle className="w-5 h-5 text-primary" />
          Human Conversation Sentiment Analytics
        </CardTitle>
        <CardDescription>
          Customer sentiment distribution by product
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="h-80 flex items-center justify-center text-muted-foreground">
            Loading sentiment data...
          </div>
        ) : !data || chartData.length === 0 ? (
          <div className="h-80 flex items-center justify-center text-muted-foreground">
            No conversation data available yet. Generate synthetic data to see sentiment analytics.
          </div>
        ) : (
          <div className="space-y-4">
            {/* Overall stats */}
            <div className="grid grid-cols-4 gap-4">
              <div className="text-center p-3 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Total Conversations</p>
                <p className="text-2xl font-bold">{data.total_conversations}</p>
              </div>
              <div className="text-center p-3 bg-green-50 dark:bg-green-950 rounded-lg">
                <p className="text-sm text-green-700 dark:text-green-300">Positive</p>
                <p className="text-2xl font-bold text-green-700 dark:text-green-300">
                  {data.overall_sentiment_distribution.positive}
                </p>
              </div>
              <div className="text-center p-3 bg-gray-50 dark:bg-gray-900 rounded-lg">
                <p className="text-sm text-gray-700 dark:text-gray-300">Neutral</p>
                <p className="text-2xl font-bold text-gray-700 dark:text-gray-300">
                  {data.overall_sentiment_distribution.neutral}
                </p>
              </div>
              <div className="text-center p-3 bg-red-50 dark:bg-red-950 rounded-lg">
                <p className="text-sm text-red-700 dark:text-red-300">Negative</p>
                <p className="text-2xl font-bold text-red-700 dark:text-red-300">
                  {data.overall_sentiment_distribution.negative}
                </p>
              </div>
            </div>

            {/* Stacked bar chart */}
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis 
                  dataKey="name" 
                  className="text-sm"
                  angle={-15}
                  textAnchor="end"
                  height={80}
                />
                <YAxis className="text-sm" />
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
                />
                <Bar 
                  dataKey="neutral" 
                  stackId="a" 
                  fill="#6b7280" 
                  name="Neutral"
                  radius={[0, 0, 0, 0]}
                />
                <Bar 
                  dataKey="negative" 
                  stackId="a" 
                  fill="#ef4444" 
                  name="Negative"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
