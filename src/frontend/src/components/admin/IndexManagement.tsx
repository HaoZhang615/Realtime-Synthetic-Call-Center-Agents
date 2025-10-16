import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Database, Plus, Trash, ArrowsClockwise, CheckCircle, XCircle } from '@phosphor-icons/react'
import { toast } from 'sonner'

type SearchIndex = {
  id: string
  name: string
  description: string
  documentCount: number
  status: 'active' | 'syncing' | 'error'
  lastUpdated: string
  vectorDimensions: number
  storageUsed: string
}

export function IndexManagement() {
  const [indices, setIndices] = useState<SearchIndex[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [newIndexName, setNewIndexName] = useState('')
  const [newIndexDescription, setNewIndexDescription] = useState('')
  const [newIndexDimensions, setNewIndexDimensions] = useState('1536')

  // TODO: Replace with real API call to fetch indices from Azure AI Search
  useEffect(() => {
    const fetchIndices = async () => {
      try {
        setIsLoading(true)
        // Fetch from /api/admin/stats for now (contains basic index info)
        const response = await fetch('/api/admin/stats')
        if (response.ok) {
          const data = await response.json()
          // Convert the stats response to index format
          const index: SearchIndex = {
            id: '1',
            name: data.index_name || 'documents',
            description: 'Primary search index for documents',
            documentCount: data.document_count || 0,
            status: data.index_status || 'active',
            lastUpdated: new Date().toISOString(),
            vectorDimensions: 3072, // text-embedding-3-large default
            storageUsed: 'N/A'
          }
          setIndices([index])
        }
      } catch (error) {
        console.error('Failed to fetch index info:', error)
        toast.error('Failed to load index information')
      } finally {
        setIsLoading(false)
      }
    }
    
    fetchIndices()
  }, [])

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const handleCreateIndex = async () => {
    if (!newIndexName.trim()) {
      toast.error('Index name is required')
      return
    }

    const newIndex: SearchIndex = {
      id: Date.now().toString(),
      name: newIndexName.toLowerCase().replace(/\s+/g, '-'),
      description: newIndexDescription,
      documentCount: 0,
      status: 'active',
      lastUpdated: new Date().toISOString(),
      vectorDimensions: parseInt(newIndexDimensions),
      storageUsed: '0 MB'
    }

    setIndices(prev => [...prev, newIndex])
    setIsCreateDialogOpen(false)
    setNewIndexName('')
    setNewIndexDescription('')
    setNewIndexDimensions('1536')
    toast.success('Search index created successfully')
  }

  const handleDeleteIndex = (indexId: string) => {
    setIndices(prev => prev.filter(i => i.id !== indexId))
    toast.success('Index deleted successfully')
  }

  const handleRefreshIndex = (indexId: string) => {
    setIndices(prev => prev.map(index => 
      index.id === indexId 
        ? { ...index, status: 'syncing' as const, lastUpdated: new Date().toISOString() }
        : index
    ))
    
    toast.success('Index refresh started')
    
    // Simulate refresh completion
    setTimeout(() => {
      setIndices(prev => prev.map(index => 
        index.id === indexId 
          ? { ...index, status: 'active' as const }
          : index
      ))
      toast.success('Index refresh completed')
    }, 3000)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Search Index Management</CardTitle>
              <CardDescription>
                Create and manage Azure AI Search indices for your documents
              </CardDescription>
            </div>
            <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="w-4 h-4 mr-2" />
                  Create Index
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create New Search Index</DialogTitle>
                  <DialogDescription>
                    Create a new search index to organize your documents
                  </DialogDescription>
                </DialogHeader>
                
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="index-name">Index Name</Label>
                    <Input
                      id="index-name"
                      placeholder="e.g., customer-support"
                      value={newIndexName}
                      onChange={(e) => setNewIndexName(e.target.value)}
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="index-description">Description</Label>
                    <Input
                      id="index-description"
                      placeholder="Brief description of this index"
                      value={newIndexDescription}
                      onChange={(e) => setNewIndexDescription(e.target.value)}
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="vector-dimensions">Vector Dimensions</Label>
                    <Select value={newIndexDimensions} onValueChange={setNewIndexDimensions}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="384">384 (Small)</SelectItem>
                        <SelectItem value="768">768 (Medium)</SelectItem>
                        <SelectItem value="1536">1536 (Large)</SelectItem>
                        <SelectItem value="3072">3072 (Extra Large)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                
                <DialogFooter>
                  <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleCreateIndex}>
                    Create Index
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </CardHeader>
      </Card>

      {/* Indices Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {indices.map((index) => (
          <Card key={index.id}>
            <CardHeader>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <Database className="w-5 h-5 text-primary" />
                  <CardTitle className="text-lg">{index.name}</CardTitle>
                </div>
                <Badge variant={
                  index.status === 'active' ? 'default' :
                  index.status === 'syncing' ? 'secondary' : 'destructive'
                }>
                  {index.status === 'active' && <CheckCircle className="w-3 h-3 mr-1" />}
                  {index.status === 'syncing' && <ArrowsClockwise className="w-3 h-3 mr-1 animate-spin" />}
                  {index.status === 'error' && <XCircle className="w-3 h-3 mr-1" />}
                  {index.status}
                </Badge>
              </div>
              <CardDescription>{index.description}</CardDescription>
            </CardHeader>
            
            <CardContent>
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Documents:</span>
                  <span className="font-medium">{index.documentCount}</span>
                </div>
                
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Dimensions:</span>
                  <span className="font-medium">{index.vectorDimensions}</span>
                </div>
                
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Storage:</span>
                  <span className="font-medium">{index.storageUsed}</span>
                </div>
                
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Last Updated:</span>
                  <span className="font-medium">{formatDate(index.lastUpdated)}</span>
                </div>
                
                <div className="flex gap-2 pt-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleRefreshIndex(index.id)}
                    disabled={index.status === 'syncing'}
                  >
                    <ArrowsClockwise className={`w-4 h-4 mr-2 ${index.status === 'syncing' ? 'animate-spin' : ''}`} />
                    Refresh
                  </Button>
                  
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button size="sm" variant="destructive">
                        <Trash className="w-4 h-4 mr-2" />
                        Delete
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Delete Index</AlertDialogTitle>
                        <AlertDialogDescription>
                          Are you sure you want to delete the "{index.name}" index? 
                          This will permanently remove all indexed documents and cannot be undone.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={() => handleDeleteIndex(index.id)}>
                          Delete
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {indices.length === 0 && (
        <Card>
          <CardContent className="p-8 text-center">
            <Database className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
            <h3 className="text-lg font-semibold mb-2">No Search Indices</h3>
            <p className="text-muted-foreground mb-4">
              Create your first search index to start organizing your documents
            </p>
            <Button onClick={() => setIsCreateDialogOpen(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Create Your First Index
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}