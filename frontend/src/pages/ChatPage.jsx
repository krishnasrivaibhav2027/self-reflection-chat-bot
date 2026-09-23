import { useCallback, useState } from 'react'
import ChatArea from '../components/ChatArea'
import Sidebar from '../components/Sidebar'

const ChatPage = () => {
  const [activeThreadId, setActiveThreadId] = useState(null)
  const [chatSessionKey, setChatSessionKey] = useState(0) // stable key for entire chat session
  // Incrementing this signal causes Sidebar to re-fetch threads
  const [sidebarRefresh, setSidebarRefresh] = useState(0)

  const handleNewChat = useCallback(() => {
    setActiveThreadId(null)
    setChatSessionKey((k) => k + 1) // new session = new key = fresh remount
  }, [])

  const handleSelectThread = useCallback((threadId) => {
    setActiveThreadId(threadId)
    setChatSessionKey((k) => k + 1) // switching threads = new session = fresh remount
  }, [])

  // Called by ChatArea when a new thread_id arrives from the backend
  const handleThreadCreated = useCallback((threadId) => {
    // Update threadId without remounting — just update the prop
    setActiveThreadId(threadId)
    setSidebarRefresh((n) => n + 1)
  }, [])

  return (
    <div className="chat-page">
      <Sidebar
        activeThreadId={activeThreadId}
        onSelectThread={handleSelectThread}
        onNewChat={handleNewChat}
        refreshSignal={sidebarRefresh}
      />
      <ChatArea
        key={chatSessionKey}
        threadId={activeThreadId}
        onThreadCreated={handleThreadCreated}
      />
    </div>
  )
}

export default ChatPage
