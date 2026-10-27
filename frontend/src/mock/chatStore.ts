import { useSyncExternalStore } from 'react'

/**
 * MOCK: chat lives in this browser only (localStorage) until the messaging backend exists.
 * The shape (channels by kind, messages, read marks) is the contract the backend will implement.
 */
export type ChannelKind = 'direct' | 'team' | 'administration' | 'organization'

export interface ChatMessage {
  id: string
  channelId: string
  authorId: string
  text: string
  at: string
}

interface State {
  messages: ChatMessage[]
  /** channelId → ISO time of the last message the person has seen. */
  read: Record<string, string>
  /** Direct conversations the person opened (peer member ids). */
  dms: string[]
}

const KEY = 'kora.mock.chat'

function load(): State {
  try {
    const raw = localStorage.getItem(KEY)
    if (raw) return { messages: [], read: {}, dms: [], ...(JSON.parse(raw) as Partial<State>) }
  } catch {
    // storage unavailable: start empty
  }
  return { messages: [], read: {}, dms: [] }
}

let state: State = load()
const listeners = new Set<() => void>()

function commit(next: State) {
  state = next
  try {
    localStorage.setItem(KEY, JSON.stringify(state))
  } catch {
    // keep working in memory
  }
  listeners.forEach((l) => l())
}

const subscribe = (l: () => void) => {
  listeners.add(l)
  return () => listeners.delete(l)
}

export const orgChannelId = 'org'
export const unitChannelId = (unitId: string) => `unit:${unitId}`
export const dmChannelId = (peerId: string) => `dm:${peerId}`

export const chatActions = {
  send(channelId: string, authorId: string, text: string) {
    const clean = text.trim()
    if (!clean) return
    const message: ChatMessage = { id: crypto.randomUUID(), channelId, authorId, text: clean, at: new Date().toISOString() }
    const peer = channelId.startsWith('dm:') ? channelId.slice(3) : null
    commit({ ...state, messages: [...state.messages, message], read: { ...state.read, [channelId]: message.at }, dms: peer && !state.dms.includes(peer) ? [...state.dms, peer] : state.dms })
  },
  markRead(channelId: string) {
    const last = state.messages.filter((m) => m.channelId === channelId).at(-1)?.at
    if (last && state.read[channelId] !== last) commit({ ...state, read: { ...state.read, [channelId]: last } })
  },
  openDm(peerId: string) {
    if (!state.dms.includes(peerId)) commit({ ...state, dms: [...state.dms, peerId] })
  },
  /** First visit to a channel: a couple of sample messages so the screen can be judged. */
  seed(channelId: string, authors: string[], lines: string[]) {
    if (state.messages.some((m) => m.channelId === channelId) || authors.length === 0) return
    const now = Date.now()
    const messages = lines.map((text, i) => ({ id: crypto.randomUUID(), channelId, authorId: authors[i % authors.length], text, at: new Date(now - (lines.length - i) * 3_600_000).toISOString() }))
    commit({ ...state, messages: [...state.messages, ...messages], read: { ...state.read, [channelId]: messages.at(-1)?.at ?? '' } })
  },
}

export const useChatState = () => useSyncExternalStore(subscribe, () => state)
