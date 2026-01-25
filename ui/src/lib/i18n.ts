const translations: Record<string, Record<string, string>> = {
  en: {
    thinking: 'Thinking…',
    noChats: 'No chats yet.',
    emptySession: 'No messages yet',
    startChat: 'Start a new chat or select one from the left.',
    welcome: 'Welcome to Jarvis',
    typeMessage: 'Type your message…',
    send: 'Send',
  },
  da: {
    thinking: 'Tænker…',
    noChats: 'Ingen chats endnu.',
    emptySession: 'Ingen beskeder endnu',
    startChat: 'Start en ny chat eller vælg en i venstre side.',
    welcome: 'Velkommen til Jarvis',
    typeMessage: 'Skriv din besked…',
    send: 'Send',
  },
}

export function getLang(): 'en' | 'da' {
  if (typeof localStorage === 'undefined') return 'en'
  const stored = localStorage.getItem('jarvisLang')
  if (stored === 'en' || stored === 'da') return stored
  const browserLang = navigator.language?.slice(0, 2)
  if (browserLang === 'da') return 'da'
  return 'en'
}

export function setLang(lang: 'en' | 'da') {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('jarvisLang', lang)
  }
}

export function t(key: string): string {
  const lang = getLang()
  return translations[lang]?.[key] || translations.en[key] || key
}
