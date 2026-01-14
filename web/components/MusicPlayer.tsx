"use client"

import React, { useEffect, useRef, useState } from 'react'
import { io } from 'socket.io-client'
import Visualizer from './Visualizer'

type Track = { id: number; title: string; thumbnail?: string; duration?: number }

export default function MusicPlayer() {
  const [current, setCurrent] = useState<Track | null>(null)
  const [queue, setQueue] = useState<Track[]>([])
  const [playing, setPlaying] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const socketRef = useRef<any>(null)

  useEffect(() => {
    const socket = io('/ws')
    socketRef.current = socket
    socket.on('connect', () => {})
    socket.on('music:play', (payload: any) => {
      setCurrent(payload.track)
      setPlaying(true)
      // set audio src and sync
      if (audioRef.current && payload.track && payload.track.id) {
        audioRef.current.src = `/api/music/stream?track_id=${payload.track.id}`
        // compute offset from started_at
        if (payload.started_at) {
          const startedAt = new Date(payload.started_at).getTime()
          const now = Date.now()
          const offsetSec = Math.max(0, (now - startedAt) / 1000)
          audioRef.current.currentTime = offsetSec
        }
        audioRef.current.play().catch(() => {})
      }
    })
    socket.on('music:queue_update', (payload: any) => {
      setQueue(payload.queue || [])
    })
    socket.on('music_control', (data: any) => {
      if (data.action === 'stop') {
        setPlaying(false)
        if (audioRef.current) audioRef.current.pause()
      }
    })
    return () => { socket.disconnect(); }
  }, [])

  async function playNow(query: string) {
    // send to server via socket
    if (socketRef.current) {
      socketRef.current.emit('music_control', { action: 'play', query, guild_id: 0 })
    } else {
      await fetch('/api/music/play', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ guild_id: 0, query }) })
    }
  }

  async function skip() {
    if (socketRef.current) socketRef.current.emit('music_control', { action: 'skip', guild_id: 0 })
    else await fetch('/api/music/skip', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ guild_id: 0 }) })
  }

  return (
    <div className="p-4 rounded-2xl bg-[#0b0b0b] border border-[#1a1a1a]">
      <div className="flex items-center gap-4">
        <div className="w-24 h-24 rounded-lg bg-gray-800 overflow-hidden">
          {current?.thumbnail ? <img src={current.thumbnail} className="w-full h-full object-cover" /> : <div className="w-full h-full flex items-center justify-center">No Art</div>}
        </div>
        <div className="flex-1">
          <div className="text-lg font-semibold">{current?.title || 'Not playing'}</div>
          <div className="text-sm text-gray-400">{playing ? 'Playing' : 'Stopped'}</div>
          <div className="mt-3 flex items-center gap-3">
            <button className="w-12 h-12 rounded-full bg-pink-500 text-white flex items-center justify-center" onClick={() => audioRef.current?.play()}>▶</button>
            <button className="w-12 h-12 rounded-full bg-white/6 text-white flex items-center justify-center" onClick={skip}>⏭</button>
            <button className="w-12 h-12 rounded-full bg-white/6 text-white flex items-center justify-center" onClick={() => { if (audioRef.current) { if (audioRef.current.paused) audioRef.current.play(); else audioRef.current.pause(); } }}>⏯</button>
          </div>
        </div>
      </div>

      <div className="mt-4">
        <div className="text-sm font-semibold mb-2">Up Next</div>
        <div className="space-y-2">
          {queue.map(q => (
            <div key={q.id} className="text-sm">{q.title}</div>
          ))}
        </div>
      </div>

      <div className="mt-3">
        <audio ref={audioRef} />
        <Visualizer audio={audioRef.current} />
      </div>

      <div className="mt-3 flex items-center gap-2">
        <input className="flex-1 p-2 rounded bg-[#070707]" placeholder="Search and play" id="qinput" />
        <button className="px-3 py-2 rounded bg-pink-500 text-white" onClick={() => { const v = (document.getElementById('qinput') as HTMLInputElement).value; playNow(v) }}>Play</button>
      </div>
    </div>
  )
}
