import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { MagnifyingGlass, Download, Trash, FileText, Calendar, Eye } from '@phosphor-icons/react'
import { toast } from 'sonner'

type FileItem = {
  id: string
  name: string
  type: string
  size: number
  uploadDate: string
  status: 'processed' | 'processing' | 'error'
  indexedIn: string[]
}

const mockFiles: FileItem[] = [
  {
    id: '1',
    name: 'customer_service_guide.pdf',
    type: 'PDF',
    size: 2.4 * 1024 * 1024,
    uploadDate: '2024-01-15T10:30:00Z',
    status: 'processed',
    indexedIn: ['customer-support', 'general-knowledge']
  },
  {
    id: '2', 
    name: 'product_specifications.docx',
    type: 'DOCX',
    size: 1.8 * 1024 * 1024,
    uploadDate: '2024-01-14T15:45:00Z',
    status: 'processed',
    indexedIn: ['product-info']
  },
  {
    id: '3',
    name: 'training_manual.pdf',
    type: 'PDF', 
    size: 5.2 * 1024 * 1024,
    uploadDate: '2024-01-14T09:20:00Z',
    status: 'processing',
    indexedIn: []
  },
  {
    id: '4',
    name: 'company_policies.txt',
    type: 'TXT',
    size: 0.3 * 1024 * 1024,
    uploadDate: '2024-01-13T14:10:00Z',
    status: 'error',
    indexedIn: []
  }
]

export function FileManagement() {
  const [files, setFiles] = useState<FileItem[]>(mockFiles)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedFiles, setSelectedFiles] = useState<string[]>([])

  const filteredFiles = files.filter(file =>
    file.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    file.type.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
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

  const handleDelete = (fileId: string) => {
    setFiles(prev => prev.filter(f => f.id !== fileId))
    toast.success('File deleted successfully')
  }

  const handleBulkDelete = () => {
    setFiles(prev => prev.filter(f => !selectedFiles.includes(f.id)))
    setSelectedFiles([])
    toast.success(`${selectedFiles.length} files deleted`)
  }

  const toggleFileSelection = (fileId: string) => {
    setSelectedFiles(prev => 
      prev.includes(fileId) 
        ? prev.filter(id => id !== fileId)
        : [...prev, fileId]
    )
  }

  const selectAllFiles = () => {
    setSelectedFiles(filteredFiles.map(f => f.id))
  }

  const clearSelection = () => {
    setSelectedFiles([])
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card>
        <CardHeader>
          <CardTitle>File Management</CardTitle>
          <CardDescription>
            Manage uploaded documents and their processing status
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between gap-4">
            <div className="relative flex-1 max-w-sm">
              <MagnifyingGlass className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search files..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            
            <div className="flex items-center gap-2">
              {selectedFiles.length > 0 && (
                <>
                  <span className="text-sm text-muted-foreground">
                    {selectedFiles.length} selected
                  </span>
                  <Button variant="outline" size="sm" onClick={clearSelection}>
                    Clear
                  </Button>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="destructive" size="sm">
                        <Trash className="w-4 h-4 mr-2" />
                        Delete Selected
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Delete Files</AlertDialogTitle>
                        <AlertDialogDescription>
                          Are you sure you want to delete {selectedFiles.length} selected files? 
                          This action cannot be undone.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={handleBulkDelete}>
                          Delete
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Files Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">
                  <input
                    type="checkbox"
                    checked={selectedFiles.length === filteredFiles.length && filteredFiles.length > 0}
                    onChange={selectedFiles.length === filteredFiles.length ? clearSelection : selectAllFiles}
                    className="rounded"
                  />
                </TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Size</TableHead>
                <TableHead>Upload Date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Indexed In</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredFiles.map((file) => (
                <TableRow key={file.id}>
                  <TableCell>
                    <input
                      type="checkbox"
                      checked={selectedFiles.includes(file.id)}
                      onChange={() => toggleFileSelection(file.id)}
                      className="rounded"
                    />
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-muted-foreground" />
                      <span className="font-medium">{file.name}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{file.type}</Badge>
                  </TableCell>
                  <TableCell>{formatFileSize(file.size)}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Calendar className="w-4 h-4" />
                      {formatDate(file.uploadDate)}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={
                      file.status === 'processed' ? 'default' :
                      file.status === 'processing' ? 'secondary' : 'destructive'
                    }>
                      {file.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {file.indexedIn.map(index => (
                        <Badge key={index} variant="outline" className="text-xs">
                          {index}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Button size="sm" variant="ghost">
                        <Eye className="w-4 h-4" />
                      </Button>
                      <Button size="sm" variant="ghost">
                        <Download className="w-4 h-4" />
                      </Button>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button size="sm" variant="ghost">
                            <Trash className="w-4 h-4 text-destructive" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Delete File</AlertDialogTitle>
                            <AlertDialogDescription>
                              Are you sure you want to delete "{file.name}"? 
                              This action cannot be undone.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction onClick={() => handleDelete(file.id)}>
                              Delete
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          
          {filteredFiles.length === 0 && (
            <div className="p-8 text-center text-muted-foreground">
              {searchTerm ? 'No files match your search.' : 'No files uploaded yet.'}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}