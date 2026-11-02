import { useSyncExternalStore } from 'react'

/**
 * MOCK: task attachments live in this browser only (file bytes in IndexedDB, details in localStorage) until the
 * backend has object storage. `brief` files are attached by whoever creates the task; `delivery` files are handed
 * in by the people doing it.
 */
export type FileKind = 'brief' | 'delivery'

export interface TaskFile {
  id: string
  taskId: string
  kind: FileKind
  name: string
  size: number
  type: string
  authorId: string
  authorName: string
  at: string
}

export const MAX_FILE_BYTES = 10 * 1024 * 1024
export const MAX_FILES_PER_KIND = 10
const BLOCKED = new Set(['exe', 'bat', 'cmd', 'com', 'scr', 'msi', 'vbs', 'ps1', 'sh', 'js', 'jar', 'dll'])

const KEY = 'kora.mock.files'
const DB = 'kora-mock-files'

export type FileProblem = 'tooBig' | 'blocked' | 'tooMany'

/** Why a file cannot be attached, or null when it is fine. */
export function checkFile(file: File, existingOfKind: number): FileProblem | null {
  const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
  if (BLOCKED.has(ext)) return 'blocked'
  if (file.size > MAX_FILE_BYTES) return 'tooBig'
  if (existingOfKind >= MAX_FILES_PER_KIND) return 'tooMany'
  return null
}

function load(): TaskFile[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '[]') as TaskFile[]
  } catch {
    return []
  }
}

let files = load()
const listeners = new Set<() => void>()

function commit(next: TaskFile[]) {
  files = next
  try {
    localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    // keep working in memory
  }
  listeners.forEach((l) => l())
}

function db(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1)
    req.onupgradeneeded = () => req.result.createObjectStore('blobs')
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function blobOp<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const database = await db()
  return new Promise((resolve, reject) => {
    const req = run(database.transaction('blobs', mode).objectStore('blobs'))
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export const fileActions = {
  async add(taskId: string, kind: FileKind, file: File, author: { id: string; name: string }) {
    const id = crypto.randomUUID()
    await blobOp('readwrite', (s) => s.put(file, id))
    commit([...files, { id, taskId, kind, name: file.name, size: file.size, type: file.type, authorId: author.id, authorName: author.name, at: new Date().toISOString() }])
  },
  async remove(id: string) {
    commit(files.filter((f) => f.id !== id))
    await blobOp('readwrite', (s) => s.delete(id))
  },
  /** Saves the file through the browser's normal download. */
  async download(file: TaskFile) {
    const blob = await blobOp<Blob | undefined>('readonly', (s) => s.get(file.id))
    if (!blob) return
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = file.name
    a.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 10_000)
  },
}

export const useTaskFiles = () => useSyncExternalStore((l) => { listeners.add(l); return () => listeners.delete(l) }, () => files)
