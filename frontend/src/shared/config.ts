/**
 * The mock layer (`src/mock/*`: browser-only structure, chat, requests, files) is kept for trying the UI
 * without a server. By default the app talks to the real backend; `npm run dev:mock` (VITE_MOCK=true)
 * switches the affected features back to the mock data. A function so tests can stub the variable.
 */
export const isMock = (): boolean => import.meta.env.VITE_MOCK === 'true'
