import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Gear, ChatCircle, FileText, Activity } from '@phosphor-icons/react'

interface SidebarProps {
  activeSection: 'admin' | 'chat'
  onSectionChange: (section: 'admin' | 'chat') => void
}

export function Sidebar({ activeSection, onSectionChange }: SidebarProps) {
  const navItems = [
    {
      id: 'admin' as const,
      label: 'Admin Portal',
      icon: Gear,
      // description: 'Documents Management and Data Synthesis'
    },
    {
      id: 'chat' as const,
      label: 'Voice Chat',
      icon: ChatCircle,
      description: 'Real-time AI conversations'
    }
  ]

  return (
    <div className="w-74 bg-card border-r border-border flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
            <Activity className="w-5 h-5 text-primary-foreground" />
          </div>
          <div>
            <h1 className="font-semibold text-lg text-foreground">AI Powered Call Center</h1>
            <p className="text-sm text-muted-foreground">With Data Synthesis</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4">
        <div className="space-y-2">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = activeSection === item.id
            
            return (
              <Button
                key={item.id}
                variant={isActive ? "default" : "ghost"}
                className={cn(
                  "w-full justify-start h-auto p-4 text-left overflow-hidden",
                  isActive && "bg-primary text-primary-foreground shadow-sm"
                )}
                onClick={() => onSectionChange(item.id)}
              >
                <div className="flex items-start gap-3 w-full min-w-0">
                  <Icon 
                    className={cn(
                      "w-5 h-5 mt-0.5 flex-shrink-0",
                      isActive ? "text-primary-foreground" : "text-muted-foreground"
                    )} 
                  />
                  <div className="flex-1 min-w-0 overflow-hidden">
                    <div className={cn(
                      "font-medium truncate",
                      isActive ? "text-primary-foreground" : "text-foreground"
                    )}>
                      {item.label}
                    </div>
                    <div className={cn(
                      "text-sm mt-1 leading-tight",
                      isActive ? "text-primary-foreground/80" : "text-muted-foreground"
                    )}>
                      {item.description}
                    </div>
                  </div>
                </div>
              </Button>
            )
          })}
        </div>
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-border">
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>System Status</span>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span>Online</span>
          </div>
        </div>
      </div>
    </div>
  )
}