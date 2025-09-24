import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Sparkle, Play, Download, ArrowsClockwise, CaretDown, CaretUp } from '@phosphor-icons/react'
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
  logs?: string[]
}

export function SyntheticDataGen() {
  const [isGenerating, setIsGenerating] = useState(false)
  const [generationJobs, setGenerationJobs] = useState<GenerationJob[]>([])
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [expandedLogs, setExpandedLogs] = useState<{ [key: string]: boolean }>({})  // Form state
  const [companyName, setCompanyName] = useState('Acme Corp')
  const [numCustomers, setNumCustomers] = useState('100')
  const [numProducts, setNumProducts] = useState('10')
  const [numConversations, setNumConversations] = useState('1000')

  const dataTypeOptions = [
    { value: 'customer-calls', label: 'Customer Service Calls' },
    { value: 'support-tickets', label: 'Support Tickets' },
    { value: 'product-reviews', label: 'Product Reviews' },
    { value: 'faq-pairs', label: 'FAQ Q&A Pairs' },
    { value: 'chat-conversations', label: 'Chat Conversations' },
    { value: 'email-exchanges', label: 'Email Exchanges' }
  ]

  // Poll job status from backend
  const pollJobStatus = async (jobId: string) => {
    let completed = false;
    while (!completed) {
      try {
        const res = await fetch(`/api/admin/job-status/${jobId}`);
        if (res.ok) {
          const data = await res.json();
          setGenerationJobs(prev => prev.map(job => job.id === jobId ? {
            ...job,
            progress: data.progress,
            status: data.status === 'completed' ? 'completed' : (data.status === 'failed' ? 'failed' : 'running'),
            logs: data.logs || []
          } : job));
          if (data.status === 'completed' || data.status === 'failed') {
            completed = true;
            setGenerationJobs(prev => prev.map(job => job.id === jobId ? {
              ...job,
              completedAt: new Date().toISOString()
            } : job));
            setActiveJobId(null);
          }
        } else {
          completed = true;
        }
      } catch {
        completed = true;
      }
      await new Promise(r => setTimeout(r, 1000));
    }
  };

  const handleGenerate = async () => {
    if (!companyName.trim()) {
      toast.error('Please enter a company name')
      return
    }
    if (!numCustomers || parseInt(numCustomers) <= 0) {
      toast.error('Please enter a valid number of customers')
      return
    }
    if (!numProducts || parseInt(numProducts) <= 0) {
      toast.error('Please enter a valid number of products')
      return
    }
    if (!numConversations || parseInt(numConversations) <= 0) {
      toast.error('Please enter a valid number of conversations')
      return
    }

    setIsGenerating(true)
    toast.success('Synthetic data generation started')

    // Call backend API
    try {
      const response = await fetch('/api/admin/synthesize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: companyName,
          num_customers: parseInt(numCustomers),
          num_products: parseInt(numProducts),
          num_conversations: parseInt(numConversations)
        })
      })
      const result = await response.json();
      if (result.job_id) {
        const jobId = result.job_id;
        setActiveJobId(jobId);
        setGenerationJobs(prev => [{
          id: jobId,
          type: 'synthesis',
          recordCount: parseInt(numConversations),
          status: 'running',
          progress: 0,
          startedAt: new Date().toISOString(),
          logs: []
        }, ...prev]);
        pollJobStatus(jobId);
      } else {
        toast.error('Failed to start synthesis job');
      }
    } catch (err) {
      toast.error('Failed to start synthesis job');
    }
    setIsGenerating(false);
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
              <Label htmlFor="company-name">Company Name</Label>
              <Input
                id="company-name"
                type="text"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Acme Corp"
              />
            </div>
            <div>
              <Label htmlFor="num-customers">Number of Customers</Label>
              <Input
                id="num-customers"
                type="number"
                min="1"
                max="100000"
                value={numCustomers}
                onChange={(e) => setNumCustomers(e.target.value)}
                placeholder="100"
              />
            </div>
            <div>
              <Label htmlFor="num-products">Number of Products</Label>
              <Input
                id="num-products"
                type="number"
                min="1"
                max="10000"
                value={numProducts}
                onChange={(e) => setNumProducts(e.target.value)}
                placeholder="10"
              />
            </div>
            <div>
              <Label htmlFor="num-conversations">Number of Conversations</Label>
              <Input
                id="num-conversations"
                type="number"
                min="1"
                max="1000000"
                value={numConversations}
                onChange={(e) => setNumConversations(e.target.value)}
                placeholder="1000"
              />
            </div>
          </div>

          {/* Removed prompt template and output format fields, not used by backend */}

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
                      {job.logs && job.logs.length > 0 && (
                        <Collapsible 
                          open={expandedLogs[job.id]} 
                          onOpenChange={(isOpen) => 
                            setExpandedLogs(prev => ({ ...prev, [job.id]: isOpen }))
                          }
                        >
                          <CollapsibleTrigger asChild>
                            <Button 
                              variant="ghost" 
                              size="sm" 
                              className="mt-2 w-full justify-between text-xs"
                            >
                              <span>View Live Logs ({job.logs.length} entries)</span>
                              {expandedLogs[job.id] ? (
                                <CaretUp className="w-3 h-3" />
                              ) : (
                                <CaretDown className="w-3 h-3" />
                              )}
                            </Button>
                          </CollapsibleTrigger>
                          <CollapsibleContent>
                            <div className="mt-2 bg-muted rounded p-3 text-xs max-h-48 overflow-auto font-mono">
                              {job.logs.map((log, idx) => (
                                <div key={idx} className="py-1 border-b border-muted-foreground/10 last:border-0">
                                  <span className="text-muted-foreground mr-2">
                                    [{new Date().toLocaleTimeString()}]
                                  </span>
                                  {log}
                                </div>
                              ))}
                            </div>
                          </CollapsibleContent>
                        </Collapsible>
                      )}
                    </div>
                  )}                  {job.status === 'completed' && job.resultFile && (
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