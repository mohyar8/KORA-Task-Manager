import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router'
import './app/styles/global.css'
import { Providers } from './app/Providers'
import { router } from './app/router'
import { applyTheme } from './shared/lib/theme'

applyTheme()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Providers>
      <RouterProvider router={router} />
    </Providers>
  </StrictMode>,
)
