"use client"

import React, { useEffect, useState } from 'react'

type ChatItem = {
  id: number
  user_name: string | null
  user_avatar?: string | null
  user_message: string
  bot_response: string
  tokens: number
  latency_ms: number
  created_at: string
}

export default function ChatLog() {
  const [items, setItems] = useState<ChatItem[]>([])

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch('/api/chatlogs?limit=100')
        const data = await res.json()
        setItems(data.items || [])
      } catch (e) {
        console.error(e)
      }
    }
    load()

    const es = new EventSource('/api/stream')
    es.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data)
        if (d.type === 'chat') {
          setItems(prev => [d.payload, ...prev].slice(0, 100))
        }
      } catch (e) {
        // ignore
      }
    }
    return () => es.close()
  }, [])

  return (
    <div className="space-y-3">
      {items.map(item => (
        <div key={item.id} className="group relative overflow-hidden rounded-2xl bg-[#0b0b0b] border border-[#1a1a1a] p-4 hover:scale-[1.01] transition-transform">
          {item.user_avatar && (
            <div
              className="absolute inset-0 opacity-6"
              style={{
                backgroundImage: `url(${item.user_avatar})`,
                backgroundSize: 'cover',
                filter: 'blur(6px)'
              }}
            />
          )}
          <div className="relative flex items-start gap-4">
            <div className="flex-shrink-0 w-12 h-12 rounded-md bg-gradient-to-br from-[#ff66aa] to-[#a356ff] flex items-center justify-center text-sm font-semibold">{item.user_name?.slice(0,1).toUpperCase()}</div>
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold">{item.user_name}</div>
                <div className="text-xs text-gray-400">{new Date(item.created_at).toLocaleString()}</div>
              </div>
              <div className="mt-2 text-sm text-gray-200">{item.user_message}</div>
              <div className="mt-2 text-sm text-teal-300">AI: {item.bot_response}</div>
              <div className="mt-3 flex items-center gap-3 text-xs text-gray-400">
                <div>Tokens: <strong className="text-white">{Math.round(item.tokens)}</strong></div>
                <div>Latency: <strong className="text-white">{Math.round(item.latency_ms)}ms</strong></div>
              </div>
            </div>
          </div>
          <div className="pointer-events-none absolute inset-0 rounded-2xl transition-opacity group-hover:shadow-[0_0_30px_rgba(255,102,170,0.12)]" aria-hidden />
        </div>
      ))}
    </div>
  )
}
