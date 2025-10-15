import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { User, ArrowRight, Database } from '@phosphor-icons/react'
import { toast } from 'sonner'
import { getApiBase } from '@/config'

type Customer = {
  id: string
  name: string  
  first_name: string
  last_name: string
}

interface CustomerSelectionProps {
  onCustomerSelected: (customerId: string, customerName: string) => void
  className?: string
}

export function CustomerSelection({ onCustomerSelected, className }: CustomerSelectionProps) {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedCustomer, setSelectedCustomer] = useState<string | null>(null)

  const API_BASE = getApiBase()

  useEffect(() => {
    fetchCustomers()
  }, [])

  const fetchCustomers = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/customers`)
      const data = await res.json()
      
      if (data.error) {
        throw new Error(data.error)
      }
      
      setCustomers(data.customers || [])
    } catch (error: any) {
      console.error('Failed to load customers:', error)
      toast.error('Failed to load customers: ' + (error.message || 'Unknown error'))
    } finally {
      setLoading(false)
    }
  }

  const handleCustomerSelect = (customer: Customer) => {
    setSelectedCustomer(customer.id)
    onCustomerSelected(customer.id, customer.name)
  }

  if (loading) {
    return (
      <div className={`flex items-center justify-center h-64 ${className}`}>
        <div className="text-center">
          <Database className="w-8 h-8 mx-auto mb-2 animate-spin" />
          <p className="text-muted-foreground">Loading customers...</p>
        </div>
      </div>
    )
  }

  if (customers.length === 0) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="w-5 h-5" />
            Customer Selection
          </CardTitle>
          <CardDescription>
            No customers found. Please synthesize customer data first in the Admin Portal.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <Database className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
            <h3 className="font-semibold mb-2">No Customers Available</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Go to Admin Portal → Synthetic Data tab to generate customer data first.
            </p>
            <Button onClick={fetchCustomers} variant="outline">
              Refresh
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <User className="w-5 h-5" />
          Customer Selection
        </CardTitle>
        <CardDescription>
          Choose a customer profile to start your voice conversation
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3">
          {customers.map((customer) => (
            <div key={customer.id} className="flex items-center justify-between p-4 border rounded-lg hover:bg-muted/50 transition-colors">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                  <User className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <h4 className="font-medium">{customer.name}</h4>
                  <p className="text-sm text-muted-foreground">Customer ID: {customer.id.substring(0, 8)}...</p>
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                {selectedCustomer === customer.id && (
                  <Badge variant="secondary">Selected</Badge>
                )}
                <Button 
                  size="sm" 
                  onClick={() => handleCustomerSelect(customer)}
                  disabled={selectedCustomer === customer.id}
                  className="gap-1"
                >
                  {selectedCustomer === customer.id ? 'Selected' : 'Login'}
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
        
        <div className="mt-4 pt-4 border-t">
          <p className="text-xs text-muted-foreground">
            💡 Tip: Customer profiles are generated from the Synthetic Data in Admin Portal
          </p>
        </div>
      </CardContent>
    </Card>
  )
}