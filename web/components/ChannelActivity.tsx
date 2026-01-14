"use client"

import React, { useEffect, useState } from 'react'

type Activity = { channel_id: number; name?: string; score: number }

export default function ChannelActivity() {
  const [activities, setActivities] = useState<Activity[]>([])

  useEffect(() => {
    const es = new EventSource('/api/stream')
    es.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data)
        if (d.type === 'chat' && d.payload.channel_id) {
          const id = d.payload.channel_id
          setActivities(prev => {
            const found = prev.find(p => p.channel_id === id)
            if (found) {
              return prev.map(p => p.channel_id === id ? { ...p, score: Math.min(p.score + 1, 100) } : { ...p, score: Math.max(p.score - 0.02, 0) })
            }
            return [{ channel_id: id, name: d.payload.channel_name || `#${id}`, score: 1 }, ...prev].slice(0, 20)
          })
        }
      } catch (e) {}
    }
    return () => es.close()
  }, [])

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-semibold">チャネルアクティビティ</h4>
      <div className="space-y-1">
        {activities.map(a => (
          <div key={a.channel_id} className="flex items-center gap-3">
            <div className="flex-1">
              <div className="text-xs text-gray-300">#{a.channel_id}</div>
              <div className="h-2 bg-white/6 rounded-full mt-1">
                <div className="h-2 bg-gradient-to-r from-[#ff66aa] to-[#00ffcc] rounded-full" style={{ width: `${Math.min(100, a.score)}%` }} />
              </div>
            </div>
            <div className="w-10 text-right text-xs">{Math.round(a.score)}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
