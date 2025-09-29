import { useState } from 'react'
import { Sidebar } from '@/components/layout/Sidebar'
import { AdminPortal } from '@/components/admin/AdminPortal'
import { VoiceChatInterface } from '@/components/chat/VoiceChatInterface'
import { Toaster } from '@/components/ui/sonner'

type ActiveSection = 'admin' | 'chat'

function App() {
  const [activeSection, setActiveSection] = useState<ActiveSection>('admin')

  return (
    <div className="flex h-screen bg-background">
      <Sidebar 
        activeSection={activeSection} 
        onSectionChange={setActiveSection} 
      />
      
      <main className="flex-1 overflow-hidden">
        {activeSection === 'admin' ? (
          <AdminPortal />
        ) : (
          <VoiceChatInterface />
        )}
      </main>
      
      <Toaster />
    </div>
  )
}

export default App