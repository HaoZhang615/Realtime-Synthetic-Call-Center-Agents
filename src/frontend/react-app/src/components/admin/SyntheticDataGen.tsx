import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Sparkle, Play, Download, ArrowsClockwise } from '@phosphor-icons/react'
import { toast } from 'sonner'

type GenerationJob = {
  id: string
  type: string
  recordCount: number
  status: 'running' | 'completed' | 'failed'
  progress: number
  startedAt: string
  completedAt?: string
  resultFile?: string
}

export function SyntheticDataGen() {
  const [isGenerating, setIsGenerating] = useState(false)
  const [generationJobs, setGenerationJobs] = useState<GenerationJob[]>([])
  
  // Form state
  const [dataType, setDataType] = useState('customer-calls')
  const [recordCount, setRecordCount] = useState('100')
  const [promptTemplate, setPromptTemplate] = useState(
    'Generate realistic customer service call transcripts with common issues like billing inquiries, technical support, and product questions.'
  )
  const [outputFormat, setOutputFormat] = useState('json')

  const dataTypeOptions = [
    { value: 'customer-calls', label: 'Customer Service Calls' },
    { value: 'support-tickets', label: 'Support Tickets' },
    { value: 'product-reviews', label: 'Product Reviews' },
    { value: 'faq-pairs', label: 'FAQ Q&A Pairs' },
    { value: 'chat-conversations', label: 'Chat Conversations' },
    { value: 'email-exchanges', label: 'Email Exchanges' }
  ]

  const handleGenerate = async () => {
    if (!recordCount || parseInt(recordCount) <= 0) {
      toast.error('Please enter a valid number of records')
      return
    }

    if (!promptTemplate.trim()) {
      toast.error('Please provide a prompt template')
      return
    }

    const newJob: GenerationJob = {
      id: Date.now().toString(),
      type: dataType,
      recordCount: parseInt(recordCount),
      status: 'running',
      progress: 0,
      startedAt: new Date().toISOString()
    }

    setGenerationJobs(prev => [newJob, ...prev])
    setIsGenerating(true)
    toast.success('Synthetic data generation started')

    // Simulate generation progress
    let progress = 0
    const interval = setInterval(() => {
      progress += Math.random() * 15
      if (progress >= 100) {
        progress = 100
        clearInterval(interval)
        
        setGenerationJobs(prev => prev.map(job => 
          job.id === newJob.id 
            ? { 
                ...job, 
                status: Math.random() > 0.1 ? 'completed' : 'failed',
                progress: 100,
                completedAt: new Date().toISOString(),
                resultFile: Math.random() > 0.1 ? `synthetic_${dataType}_${recordCount}_records.${outputFormat}` : undefined
              }
            : job
        ))
        
        setIsGenerating(false)
        toast.success('Synthetic data generation completed')
      } else {
        setGenerationJobs(prev => prev.map(job => 
          job.id === newJob.id ? { ...job, progress } : job
        ))
      }
    }, 300)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getStatusColor = (status: GenerationJob['status']) => {
    switch (status) {
      case 'running': return 'secondary'
      case 'completed': return 'default'
      case 'failed': return 'destructive'
    }
  }

  return (
    <div className="space-y-6">
      {/* Generation Form */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkle className="w-5 h-5 text-primary" />
            Synthetic Data Generation
          </CardTitle>
          <CardDescription>
            Generate realistic synthetic data for testing and training your AI models
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="data-type">Data Type</Label>
              <Select value={dataType} onValueChange={setDataType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {dataTypeOptions.map(option => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            <div>
              <Label htmlFor="record-count">Number of Records</Label>
              <Input
                id="record-count"
                type="number"
                min="1"
                max="10000"
                value={recordCount}
                onChange={(e) => setRecordCount(e.target.value)}
                placeholder="100"
              />
            </div>
          </div>

          <div>
            <Label htmlFor="prompt-template">Prompt Template</Label>
            <Textarea
              id="prompt-template"
              value={promptTemplate}
              onChange={(e) => setPromptTemplate(e.target.value)}
              placeholder="Describe the type of data you want to generate..."
              className="min-h-[100px]"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="output-format">Output Format</Label>
              <Select value={outputFormat} onValueChange={setOutputFormat}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="json">JSON</SelectItem>
                  <SelectItem value="csv">CSV</SelectItem>
                  <SelectItem value="xlsx">Excel (XLSX)</SelectItem>
                  <SelectItem value="txt">Text</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <Button 
            onClick={handleGenerate} 
            disabled={isGenerating}
            className="w-full md:w-auto"
          >
            {isGenerating ? (
              <>
                <ArrowsClockwise className="w-4 h-4 mr-2 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
                Generate Data
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Generation History */}
      {generationJobs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Generation History</CardTitle>
            <CardDescription>
              Track your synthetic data generation jobs
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {generationJobs.map((job) => (
                <div key={job.id} className="border rounded-lg p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <h4 className="font-medium">
                        {dataTypeOptions.find(opt => opt.value === job.type)?.label}
                      </h4>
                      <p className="text-sm text-muted-foreground">
                        {job.recordCount} records • Started {formatDate(job.startedAt)}
                        {job.completedAt && ` • Completed ${formatDate(job.completedAt)}`}
                      </p>
                    </div>
                    <Badge variant={getStatusColor(job.status)}>
                      {job.status}
                    </Badge>
                  </div>

                  {job.status === 'running' && (
                    <div className="mb-3">
                      <div className="flex justify-between text-sm mb-1">
                        <span>Progress</span>
                        <span>{Math.round(job.progress)}%</span>
                      </div>
                      <Progress value={job.progress} className="h-2" />
                    </div>
                  )}

                  {job.status === 'completed' && job.resultFile && (
                    <div className="flex items-center gap-2">
                      <Button size="sm" variant="outline">
                        <Download className="w-4 h-4 mr-2" />
                        Download {job.resultFile}
                      </Button>
                    </div>
                  )}

                  {job.status === 'failed' && (
                    <div className="text-sm text-destructive">
                      Generation failed. Please try again with different parameters.
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tips */}
      <Card>
        <CardHeader>
          <CardTitle>Generation Tips</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li>• Be specific in your prompt template for better quality results</li>
            <li>• Start with smaller record counts to test your prompts</li>
            <li>• Use domain-specific terminology for more realistic data</li>
            <li>• Consider including edge cases and error scenarios</li>
            <li>• JSON format provides the most flexibility for structured data</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}