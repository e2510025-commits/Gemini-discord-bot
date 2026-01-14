"use client"

import React, { useEffect, useState } from 'react'

type Channel = {
  id: number
  guild_id: number
  channel_id: number
  name: string
  type: string
  owner_id?: number | null
  owner_name?: string | null
  owner_avatar?: string | null
}

export default function ChannelsManager() {
  const [publicChannels, setPublicChannels] = useState<Channel[]>([])
  const [privateChannels, setPrivateChannels] = useState<Channel[]>([])

  useEffect(() => {
    async function load() {
      const res = await fetch('/api/channels')
      const data = await res.json()
      setPublicChannels(data.public || [])
      setPrivateChannels(data.private || [])
    }
    load()

    const es = new EventSource('/api/stream')
    es.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data)
        if (d.type === 'channel:created') {
          const p = d.payload
          if (p.type === 'public') setPublicChannels(prev => [p, ...prev])
          else setPrivateChannels(prev => [p, ...prev])
        }
        if (d.type === 'channel:deleted') {
          setPublicChannels(prev => prev.filter(c => c.channel_id !== d.payload.channel_id))
          setPrivateChannels(prev => prev.filter(c => c.channel_id !== d.payload.channel_id))
        }
      } catch (e) {}
    }
    return () => es.close()
  }, [])

  async function archiveChannel(channel_id: number) {
    if (!confirm('チャネルをアーカイブしますか？')) return
    const res = await fetch(`/api/channels/${channel_id}`, { method: 'DELETE' })
    if (res.ok) {
      setPublicChannels(prev => prev.filter(c => c.channel_id !== channel_id))
      setPrivateChannels(prev => prev.filter(c => c.channel_id !== channel_id))
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-sm font-semibold mb-2">公開チャンネル</h4>
        <div className="space-y-2">
          {publicChannels.map(ch => (
            <div key={ch.channel_id} className="flex items-center justify-between p-3 rounded-lg bg-[#0c0c0c] border border-[#1a1a1a]">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded bg-gradient-to-br from-[#ff66aa] to-[#a356ff] flex items-center justify-center text-sm">#</div>
                <div>
                  <div className="text-sm font-medium">{ch.name}</div>
                  <div className="text-xs text-gray-400">Guild: {ch.guild_id}</div>
                </div>
              </div>
              <div>
                <button className="text-xs px-3 py-1 rounded bg-white/6" onClick={() => archiveChannel(ch.channel_id)}>Archive</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h4 className="text-sm font-semibold mb-2">個人チャンネル</h4>
        <div className="space-y-2">
          {privateChannels.map(ch => (
            <div key={ch.channel_id} className="flex items-center justify-between p-3 rounded-lg bg-[#0c0c0c] border border-[#1a1a1a]">
              <div className="flex items-center gap-3">
                <img src={ch.owner_avatar || '/avatar-placeholder.png'} className="w-8 h-8 rounded" alt="avatar" />
                <div>
                  <div className="text-sm font-medium">{ch.name}</div>
                  <div className="text-xs text-gray-400">Owner: {ch.owner_name}</div>
                </div>
              </div>
              <div>
                <button className="text-xs px-3 py-1 rounded bg-white/6" onClick={() => archiveChannel(ch.channel_id)}>Archive</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
