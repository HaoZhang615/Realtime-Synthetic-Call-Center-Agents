import { useState, useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Upload, File, CheckCircle, XCircle, Trash } from '@phosphor-icons/react'
import { toast } from 'sonner'

type UploadFile = {
  id: string
  file: File
  progress: number
  status: 'pending' | 'uploading' | 'success' | 'error'
  error?: string
}

export function DocumentUpload() {
  const [uploadFiles, setUploadFiles] = useState<UploadFile[]>([])
  const [isDragActive, setIsDragActive] = useState(false)
  const [isProcessingQueue, setIsProcessingQueue] = useState(false)

  const onDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragActive(true)
  }, [])

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragActive(false)
  }, [])

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragActive(false)

    const files = Array.from(e.dataTransfer.files)
    handleFiles(files)
  }, [])

  const onFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    handleFiles(files)
  }

  const API_BASE = (import.meta as any).env?.VITE_API_BASE || '' // e.g. http://127.0.0.1:8000 when running vite dev

  // Sequential upload processing to avoid backend concurrency issues
  const processUploadQueue = async (filesToUpload: UploadFile[]) => {
    if (isProcessingQueue) return // Prevent multiple queue processors
    setIsProcessingQueue(true)
    
    for (const file of filesToUpload) {
      await startUpload(file)
      // Small delay between uploads to ensure backend processing completes
      await new Promise(resolve => setTimeout(resolve, 500))
    }
    
    setIsProcessingQueue(false)
  }

  const handleFiles = (files: File[]) => {
    const validFiles = files.filter(file => {
      const validTypes = ['application/pdf', 'text/plain', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
      const maxSize = 10 * 1024 * 1024 // 10MB
      
      if (!validTypes.includes(file.type)) {
        toast.error(`${file.name}: Unsupported file type`)
        return false
      }
      
      if (file.size > maxSize) {
        toast.error(`${file.name}: File too large (max 10MB)`)
        return false
      }
      
      return true
    })

    const newFiles: UploadFile[] = validFiles.map(file => ({
      id: `${Date.now()}-${Math.random()}`,
      file,
      progress: 0,
      status: 'pending'
    }))

    setUploadFiles(prev => [...prev, ...newFiles])
    
    // Batch process uploads sequentially to avoid backend concurrency issues
    processUploadQueue(newFiles)
  }

  const startUpload = async (uploadFile: UploadFile): Promise<void> => {
    const fileId = uploadFile.id
    const fileObj = uploadFile.file

    // Update to uploading
    setUploadFiles(prev => prev.map(f => f.id === fileId ? { ...f, status: 'uploading', progress: 0, error: undefined } : f))

    return new Promise((resolve, reject) => {
      const formData = new FormData()
      // Backend expects field name 'files' (list). We send single file per request to simplify progress tracking.
      formData.append('files', fileObj, fileObj.name)

      const xhr = new XMLHttpRequest()
      xhr.open('POST', API_BASE + '/api/admin/upload')

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100)
          setUploadFiles(prev => prev.map(f => f.id === fileId ? { ...f, progress: pct } : f))
        }
      }

      xhr.onreadystatechange = () => {
        if (xhr.readyState === 4) {
          const success = xhr.status >= 200 && xhr.status < 300
          if (success) {
            setUploadFiles(prev => prev.map(f => f.id === fileId ? { ...f, status: 'success', progress: 100 } : f))
            toast.success(`${fileObj.name} uploaded`)
            resolve()
          } else {
            let errMsg = `Upload failed (status ${xhr.status || 'network'})`
            try {
              const resp = JSON.parse(xhr.responseText || '{}')
              if (resp.detail) errMsg = resp.detail
            } catch {}
            setUploadFiles(prev => prev.map(f => f.id === fileId ? { ...f, status: 'error', error: errMsg } : f))
            toast.error(errMsg)
            reject(new Error(errMsg))
          }
        }
      }

      xhr.onerror = () => {
        const errMsg = 'Network error'
        setUploadFiles(prev => prev.map(f => f.id === fileId ? { ...f, status: 'error', error: errMsg } : f))
        toast.error(errMsg)
        reject(new Error(errMsg))
      }

      xhr.send(formData)
    })
  }

  const removeFile = (fileId: string) => {
    setUploadFiles(prev => prev.filter(f => f.id !== fileId))
  }

  const retryUpload = async (fileId: string) => {
    const fileObj = uploadFiles.find(f => f.id === fileId)
    if (!fileObj) return
    setUploadFiles(prev => prev.map(f => f.id === fileId ? { ...f, status: 'pending', progress: 0, error: undefined } : f))
    // Process single file retry
    try {
      await startUpload({ ...fileObj, status: 'pending', progress: 0, error: undefined })
    } catch (error) {
      // Error already handled in startUpload
    }
  }

  return (
    <div className="space-y-6">
      {/* Upload Zone */}
      <Card>
        <CardHeader>
          <CardTitle>Document Upload</CardTitle>
          <CardDescription>
            Upload documents to add to your knowledge base. Supported formats: PDF, DOC, DOCX, TXT
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div
            className={`
              border-2 border-dashed rounded-lg p-8 text-center transition-colors
              ${isDragActive 
                ? 'border-primary bg-primary/5' 
                : 'border-muted-foreground/25 hover:border-muted-foreground/50'
              }
            `}
            onDragEnter={onDragEnter}
            onDragLeave={onDragLeave}
            onDragOver={onDragOver}
            onDrop={onDrop}
          >
            <Upload className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
            <h3 className="text-lg font-semibold mb-2">
              {isDragActive ? 'Drop files here' : 'Drag & drop files here'}
            </h3>
            <p className="text-muted-foreground mb-4">
              or click to browse files
            </p>
            <input
              type="file"
              multiple
              accept=".pdf,.doc,.docx,.txt"
              onChange={onFileSelect}
              className="hidden"
              id="file-upload"
            />
            <Button asChild>
              <label htmlFor="file-upload" className="cursor-pointer">
                Select Files
              </label>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Upload Queue */}
      {uploadFiles.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Upload Queue</CardTitle>
            <CardDescription>
              {uploadFiles.length} file(s) in queue
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {uploadFiles.map(uploadFile => (
                <div key={uploadFile.id} className="flex items-center gap-4 p-4 border rounded-lg">
                  <File className="w-8 h-8 text-muted-foreground flex-shrink-0" />
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <p className="font-medium truncate">
                        {uploadFile.file.name}
                      </p>
                      <Badge variant={
                        uploadFile.status === 'success' ? 'default' :
                        uploadFile.status === 'error' ? 'destructive' :
                        uploadFile.status === 'uploading' ? 'secondary' : 'outline'
                      }>
                        {uploadFile.status}
                      </Badge>
                    </div>
                    
                    <p className="text-sm text-muted-foreground mb-2">
                      {(uploadFile.file.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                    
                    {uploadFile.status === 'uploading' && (
                      <Progress value={uploadFile.progress} className="h-2" />
                    )}
                    
                    {uploadFile.error && (
                      <p className="text-sm text-destructive">{uploadFile.error}</p>
                    )}
                  </div>
                  
                  <div className="flex items-center gap-2">
                    {uploadFile.status === 'success' && (
                      <CheckCircle className="w-5 h-5 text-green-500" />
                    )}
                    {uploadFile.status === 'error' && (
                      <>
                        <XCircle className="w-5 h-5 text-destructive" />
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => retryUpload(uploadFile.id)}
                        >
                          Retry
                        </Button>
                      </>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => removeFile(uploadFile.id)}
                    >
                      <Trash className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}