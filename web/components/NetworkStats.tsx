"use client"

import React, { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

type NetPoint = { t: string; rx: number; tx: number }

export default function NetworkStats() {
  const [data, setData] = useState<NetPoint[]>([])

  useEffect(() => {
    const es = new EventSource('/api/stream')
    es.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data)
        if (d.type === 'network') {
          const ts = new Date(d.payload.timestamp)
          const label = ts.toLocaleTimeString()
          setData(prev => {
            const next = [...prev, { t: label, rx: d.payload.rx, tx: d.payload.tx }]
            return next.slice(-40)
          })
        }
      } catch (e) {
        // ignore
      }
    }
    return () => es.close()
  }, [])

  return (
    <div className="p-4 rounded-2xl bg-[#0b0b0b] border border-[#1a1a1a]">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-semibold">Network (RX/TX)</h4>
        <div className="text-xs text-gray-400">Realtime</div>
      </div>
      <div style={{ width: '100%', height: 180 }}>
        <ResponsiveContainer>
          <LineChart data={data}>
            <XAxis dataKey="t" tick={{ fill: '#aaa' }} />
            <YAxis tick={{ fill: '#aaa' }} />
            <Tooltip />
            <Line type="monotone" dataKey="rx" stroke="#ff66aa" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="tx" stroke="#00ffcc" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
