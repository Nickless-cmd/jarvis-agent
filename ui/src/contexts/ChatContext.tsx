import React, { createContext, useContext, useEffect, useState } from 'react'
import * as api from '../lib/apiClient'
import { t } from '../lib/i18n'

type Message = { id?: string; role: string; content: string; created_at?: string }

type Session = { id: string; name?: string }

type ChatState = {
  profile: any | null
  profileLoading: boolean
  sessions: Session[]
  selectedSessionId?: string
  activeSessionId?: string
  setActiveSessionId: (id: string) => void
  createNewChat: () => Promise<void>
  loadMessages: (id: string) => void
  messages: Message[]
  loading: boolean
  isThinking: boolean
  selectSession: (id: string) => void
  newSession: () => Promise<void>
  sendMessage: (promptOrOpts: string | { sessionId?: string; prompt: string }) => Promise<void>
  logout: () => Promise<void>
}

const ChatContext = createContext<ChatState | null>(null)

export function useChat() { const ctx = useContext(ChatContext); if(!ctx) throw new Error('useChat must be used within ChatProvider'); return ctx }

export const ChatProvider: React.FC<{children:any}> = ({ children }) => {
  const [profile, setProfile] = useState<any | null>(null)
  const [profileLoading, setProfileLoading] = useState<boolean>(true)
  const [sessions, setSessions] = useState<Session[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<string|undefined>(undefined)
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [isThinking, setIsThinking] = useState(false)

  useEffect(() => {
    let mounted = true
    async function init(){
      try{
        const p = await api.getProfile()
        if(!mounted) return
        setProfile(p)
      }catch(e){
        setProfile(null)
        if (mounted) setProfileLoading(false)
        return
      }
      try {
        const s = await api.listSessions()
        if(!mounted) return
        setSessions(s)
        if(s && s.length) {
          // Restore last active session from localStorage
          const savedSessionId = localStorage.getItem('activeSessionId')
          const sessionExists = savedSessionId && s.some(session => session.id === savedSessionId)
          if (sessionExists) {
            selectSession(savedSessionId)
          } else {
            selectSession(s[0].id)
          }
        }
      } finally {
        if (mounted) setProfileLoading(false)
      }
    }
    init()
    return () => { mounted = false }
  }, [])

  async function selectSession(id: string){
    setSelectedSessionId(id)
    // Save to localStorage so it persists across page reloads
    localStorage.setItem('activeSessionId', id)
    setLoading(true)
    try{
      const msgs = await api.getSessionMessages(id)
      setMessages(msgs.map((m:any)=>({role:m.role, content:m.content, created_at:m.created_at})))
    }catch(e){
      setMessages([])
    }finally{ setLoading(false) }
  }

  async function newSession(){
    const id = await api.createSession('Ny chat')
    if(id){
      const updated = await api.listSessions()
      setSessions(updated)
      selectSession(id)
    }
  }

  async function sendMessage(promptOrOpts: string | { sessionId?: string; prompt: string }){
    const opts = typeof promptOrOpts === 'string' ? { sessionId: selectedSessionId, prompt: promptOrOpts } : promptOrOpts
    const sessionId = opts.sessionId || selectedSessionId
    if(!sessionId) return
    const prompt = opts.prompt
    
    setIsThinking(true)
    
    // optimistic user message
    const userMsg: Message = { id: `u-${Date.now()}-${Math.random().toString(36).slice(2,8)}`, role: 'user', content: prompt }
    setMessages(prev => [...prev, userMsg])
    // create assistant placeholder with id so we can update safely
    const assistantId = `a-${Date.now()}-${Math.random().toString(36).slice(2,8)}`
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '' }])

    try{
      const handle = await api.sendChatMessageStream({ sessionId, prompt }, (chunk: string) => {
        setMessages(prev => {
          const copy = prev.slice()
          const idx = copy.findIndex(m => m.id === assistantId)
          if (idx === -1) return copy
          const msg = copy[idx]
          copy[idx] = { ...msg, content: (msg.content || '') + chunk }
          return copy
        })
      })
      // handle.abort() is available if caller needs to cancel
    }catch(err){
      // replace assistant placeholder with error message
      setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content: 'Fejl ved hentning af svar.' } : m))
    }finally{
      setIsThinking(false)
    }
  }

  async function logout() {
    try { await api.logout() } catch {}
    // clear client state
    setProfile(null)
    setSessions([])
    setSelectedSessionId(undefined)
    setMessages([])
    // Clear saved session from localStorage
    localStorage.removeItem('activeSessionId')
    try { window.location.href = '/ui/login' } catch {}
  }

  const value: ChatState = {
    profile,
    profileLoading,
    sessions,
    selectedSessionId,
    activeSessionId: selectedSessionId,
    setActiveSessionId: (id: string) => selectSession(id),
    createNewChat: newSession,
    loadMessages: (id: string) => selectSession(id),
    messages,
    loading,
    isThinking,
    selectSession,
    newSession,
    sendMessage,
    logout,
  }

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}
