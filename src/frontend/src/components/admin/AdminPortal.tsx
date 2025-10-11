import { useState } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { DocumentUpload } from './DocumentUpload'
import { FileManagement } from './FileManagement'
import { SyntheticDataGen } from './SyntheticDataGen'
import { AdminDashboard } from './AdminDashboard'

export function AdminPortal() {
  const [activeTab, setActiveTab] = useState('dashboard')

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b border-border bg-card">
        <div className="p-6">
          <h1 className="text-2xl font-bold text-foreground">Admin Portal</h1>
          <p className="text-muted-foreground mt-1">
            Manage documents, knowledge base, and data synthesis
          </p>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 p-6 overflow-auto">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="dashboard">Dashboard</TabsTrigger>
            <TabsTrigger value="upload">Upload</TabsTrigger>
            <TabsTrigger value="files">Files</TabsTrigger>
            <TabsTrigger value="synthetic">Synthetic Data</TabsTrigger>
          </TabsList>

          <div className="mt-6">
            <TabsContent value="dashboard" className="mt-0">
              <AdminDashboard />
            </TabsContent>

            <TabsContent value="upload" className="mt-0">
              <DocumentUpload />
            </TabsContent>

            <TabsContent value="files" className="mt-0">
              <FileManagement />
            </TabsContent>

            <TabsContent value="synthetic" className="mt-0">
              <SyntheticDataGen />
            </TabsContent>
          </div>
        </Tabs>
      </div>
    </div>
  )
}