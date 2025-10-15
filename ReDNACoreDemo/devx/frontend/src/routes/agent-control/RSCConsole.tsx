import { useCallback, useEffect, useState } from 'react'
import { toast } from 'react-toastify'
import {
  type RSCMessage,
  getInbox,
  getSent,
  sendRSCMessage,
  actOnMessage,
  formatTimestamp,
  getExpiry,
  isExpired,
  getMessageTypeLabel,
  getMessageTypeColor,
} from '@/lib/rscApi'

interface RSCConsoleProps {
  userId: string
}

type TabType = 'inbox' | 'sent'
type FilterType = 'all' | 'invites' | 'briefs' | 'open' | 'closed'

export default function RSCConsole({ userId }: RSCConsoleProps) {
  const [activeTab, setActiveTab] = useState<TabType>('inbox')
  const [filter, setFilter] = useState<FilterType>('all')
  const [inbox, setInbox] = useState<RSCMessage[]>([])
  const [sent, setSent] = useState<RSCMessage[]>([])
  const [selectedMessage, setSelectedMessage] = useState<RSCMessage | null>(null)
  const [loading, setLoading] = useState(true)
  const [showCompose, setShowCompose] = useState(false)
  const [composing, setComposing] = useState(false)

  // Compose form state
  const [toUser, setToUser] = useState('')
  const [topic, setTopic] = useState('')
  const [namespaces, setNamespaces] = useState<string[]>(['SkillDNA'])

  const loadMessages = useCallback(async () => {
    setLoading(true)
    try {
      const [inboxRes, sentRes] = await Promise.all([
        getInbox(userId, { limit: 50 }),
        getSent(userId, { limit: 50 }),
      ])
      setInbox(inboxRes.inbox)
      setSent(sentRes.sent)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load messages'
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }, [userId])

  useEffect(() => {
    loadMessages()
  }, [loadMessages])

  const handleAct = useCallback(
    async (messageId: string, action: 'accept' | 'decline' | 'close') => {
      try {
        await actOnMessage(userId, { message_id: messageId, action })
        toast.success(`Message ${action}ed successfully`)
        loadMessages()
        setSelectedMessage(null)
      } catch (err) {
        const message = err instanceof Error ? err.message : `Failed to ${action} message`
        toast.error(message)
      }
    },
    [userId, loadMessages]
  )

  const handleCompose = useCallback(async () => {
    if (!toUser || !topic) {
      toast.error('Partner and topic are required')
      return
    }

    setComposing(true)
    try {
      await sendRSCMessage({
        from_user: userId,
        to_user: toUser,
        type: 'rsc_invite',
        topic,
        constraints: { namespaces },
        policy: { allow_reply: true },
      })
      toast.success('Invite sent successfully')
      setShowCompose(false)
      setToUser('')
      setTopic('')
      setNamespaces(['SkillDNA'])
      loadMessages()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to send invite'
      toast.error(message)
    } finally {
      setComposing(false)
    }
  }, [userId, toUser, topic, namespaces, loadMessages])

  const messages = activeTab === 'inbox' ? inbox : sent

  const filteredMessages = messages.filter(msg => {
    if (filter === 'all') return true
    if (filter === 'invites') return msg.type === 'rsc_invite'
    if (filter === 'briefs') return msg.type === 'rsc_brief'
    if (filter === 'open') return msg.type === 'rsc_invite' && !isExpired(msg)
    if (filter === 'closed') return msg.type === 'rsc_close' || isExpired(msg)
    return true
  })

  if (loading) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6 text-center text-sm text-gray-500">
        Loading RSC messages…
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Tabs */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <button
            className={`rounded-md px-4 py-2 text-sm font-medium ${
              activeTab === 'inbox'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
            onClick={() => setActiveTab('inbox')}
          >
            Inbox ({inbox.length})
          </button>
          <button
            className={`rounded-md px-4 py-2 text-sm font-medium ${
              activeTab === 'sent'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
            onClick={() => setSent(sent)}
          >
            Sent ({sent.length})
          </button>
        </div>
        <button
          className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
          onClick={() => setShowCompose(true)}
        >
          Compose Invite
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        {(['all', 'invites', 'briefs', 'open', 'closed'] as FilterType[]).map(f => (
          <button
            key={f}
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              filter === f
                ? 'bg-blue-100 text-blue-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
            onClick={() => setFilter(f)}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Message List */}
      <div className="space-y-2">
        {filteredMessages.length === 0 ? (
          <div className="rounded-lg border border-dashed border-gray-300 bg-white p-6 text-center text-sm text-gray-500">
            No messages in {activeTab}
          </div>
        ) : (
          filteredMessages.map(msg => {
            const expired = isExpired(msg)
            const expiry = getExpiry(msg)

            return (
              <div
                key={msg.id}
                className={`cursor-pointer rounded-lg border bg-white p-4 hover:bg-gray-50 ${
                  selectedMessage?.id === msg.id ? 'border-blue-500' : 'border-gray-200'
                }`}
                onClick={() => setSelectedMessage(msg)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${getMessageTypeColor(
                          msg.type
                        )}`}
                      >
                        {getMessageTypeLabel(msg.type)}
                      </span>
                      {expired && (
                        <span className="inline-flex rounded-full bg-red-100 px-2 py-1 text-xs font-medium text-red-700">
                          Expired
                        </span>
                      )}
                    </div>
                    <div className="text-sm font-semibold text-gray-900">
                      {msg.topic || 'No topic'}
                    </div>
                    <div className="text-xs text-gray-600">
                      {activeTab === 'inbox' ? `From: ${msg.from}` : `To: ${msg.to}`}
                    </div>
                    <div className="text-xs text-gray-500">
                      {formatTimestamp(msg.timestamp)}
                      {expiry && ` • Expires: ${formatTimestamp(expiry.toISOString())}`}
                    </div>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Message Detail */}
      {selectedMessage && (
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-gray-200 pb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">
                  {selectedMessage.topic || 'No topic'}
                </h3>
                <div className="mt-1 text-sm text-gray-600">
                  Thread: {selectedMessage.thread_id || 'N/A'}
                </div>
              </div>
              <button
                className="text-sm text-gray-500 hover:text-gray-700"
                onClick={() => setSelectedMessage(null)}
              >
                Close
              </button>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <div className="text-xs font-semibold uppercase text-gray-500">From</div>
                <div className="text-sm text-gray-900">{selectedMessage.from}</div>
              </div>
              <div>
                <div className="text-xs font-semibold uppercase text-gray-500">To</div>
                <div className="text-sm text-gray-900">{selectedMessage.to}</div>
              </div>
            </div>

            {selectedMessage.constraints && Object.keys(selectedMessage.constraints).length > 0 && (
              <div>
                <div className="text-xs font-semibold uppercase text-gray-500">Constraints</div>
                <pre className="mt-1 rounded bg-gray-50 p-2 text-xs text-gray-800">
                  {JSON.stringify(selectedMessage.constraints, null, 2)}
                </pre>
              </div>
            )}

            {selectedMessage.payload && Object.keys(selectedMessage.payload).length > 0 && (
              <div>
                <div className="text-xs font-semibold uppercase text-gray-500">Payload</div>
                <pre className="mt-1 rounded bg-gray-50 p-2 text-xs text-gray-800">
                  {JSON.stringify(selectedMessage.payload, null, 2)}
                </pre>
              </div>
            )}

            {/* Actions */}
            {activeTab === 'inbox' && selectedMessage.type === 'rsc_invite' && !isExpired(selectedMessage) && (
              <div className="flex gap-3 border-t border-gray-200 pt-4">
                <button
                  className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
                  onClick={() => handleAct(selectedMessage.id, 'accept')}
                >
                  Accept
                </button>
                <button
                  className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
                  onClick={() => handleAct(selectedMessage.id, 'decline')}
                >
                  Decline
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Compose Modal */}
      {showCompose && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/50 p-4">
          <div className="w-full max-w-lg rounded-lg border border-gray-200 bg-white shadow-xl">
            <div className="border-b border-gray-200 px-6 py-4">
              <h3 className="text-lg font-semibold text-gray-900">Compose RSC Invite</h3>
            </div>
            <div className="space-y-4 px-6 py-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Partner User ID</label>
                <input
                  type="text"
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  placeholder="USER2"
                  value={toUser}
                  onChange={e => setToUser(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Topic</label>
                <input
                  type="text"
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  placeholder="career_brief"
                  value={topic}
                  onChange={e => setTopic(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Namespaces</label>
                <select
                  multiple
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  value={namespaces}
                  onChange={e => setNamespaces(Array.from(e.target.selectedOptions, opt => opt.value))}
                >
                  <option value="SkillDNA">SkillDNA</option>
                  <option value="Career">Career</option>
                  <option value="Core">Core</option>
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-3 border-t border-gray-200 px-6 py-4">
              <button
                className="rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                onClick={() => setShowCompose(false)}
                disabled={composing}
              >
                Cancel
              </button>
              <button
                className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-60"
                onClick={handleCompose}
                disabled={composing}
              >
                {composing ? 'Sending...' : 'Send Invite'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
