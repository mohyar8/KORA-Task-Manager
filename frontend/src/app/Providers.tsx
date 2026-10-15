import { useState, type ReactNode } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { createQueryClient } from '@/shared/api/queryClient'
import { SessionProvider } from '@/features/auth/SessionProvider'
import { I18nProvider } from '@/shared/i18n/i18n'
import { ToastProvider } from '@/shared/ui/Feedback'

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createQueryClient)
  return (
    <I18nProvider>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <SessionProvider>{children}</SessionProvider>
        </ToastProvider>
      </QueryClientProvider>
    </I18nProvider>
  )
}
