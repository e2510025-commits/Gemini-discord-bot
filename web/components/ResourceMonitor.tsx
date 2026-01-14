"use client"

import React, { useEffect, useState } from 'react'

export default function ResourceMonitor() {
  const [data, setData] = useState<any>({})

  useEffect(() => {
    let mounted = true
    async function load() {
      try {
        const res = await fetch('/api/monitor')
        const j = await res.json()
        if (mounted) setData(j)
      } catch (e) {}
    }
    load()
    const t = setInterval(load, 5000)
    return () => { mounted = false; clearInterval(t) }
  }, [])

  return (
    <div className="p-4 rounded-2xl bg-[#0b0b0b] border border-[#1a1a1a]">
      <h4 className="text-sm font-semibold mb-2">リソース制限モニター</h4>
      <div className="text-xs text-gray-400">Gemini tokens used (approx): {Math.round(data.tokens_used || 0)}</div>
      <div className="text-xs text-gray-400">Free quota: {data.quota || 'unset'}</div>
      <div className="mt-2 text-xs text-gray-400">Memory: {data.memory ? (data.memory/1024/1024).toFixed(1) + 'MB' : 'n/a'}</div>
      <div className="mt-2 text-xs text-gray-400">Uptime: {data.uptime || '-'}</div>
    </div>
  )
}
