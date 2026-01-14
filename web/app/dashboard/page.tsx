"""Next.js App Router dashboard page (TSX) - minimal example
This file uses Tailwind CSS classes and Framer Motion for a simple loading animation.
"""
import React from 'react'
import { motion } from 'framer-motion'
import Card from '@/components/Card'
import ChatLog from '@/components/ChatLog'
import NetworkStats from '@/components/NetworkStats'
import ChannelsManager from '@/components/ChannelsManager'
import ChannelActivity from '@/components/ChannelActivity'
import MusicPlayer from '@/components/MusicPlayer'
import ResourceMonitor from '@/components/ResourceMonitor'

export default function DashboardPage() {
  return (
    <main className="min-h-screen bg-[linear-gradient(120deg,#0b0b0b_0%,#111_40%)] text-white p-8">
      <div className="max-w-6xl mx-auto grid grid-cols-12 gap-6">
        <aside className="col-span-2 bg-[#0d0d0d] rounded-xl p-4 shadow-lg">
          {/* Sidebar icons (placeholder) */}
          <div className="space-y-4">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-[#ff66aa] to-[#a356ff]" />
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-[#00ffcc] to-[#0099ff]" />
            <div className="w-10 h-10 rounded-lg bg-gray-700" />
          </div>
        </aside>

        <section className="col-span-10">
          <motion.h1 initial={{ y: 20, opacity: 0 }} animate={{ y:0, opacity:1 }} transition={{ duration: 0.5 }} className="text-3xl font-bold mb-4">Dashboard</motion.h1>

          <div className="grid grid-cols-3 gap-4 mb-6">
            <Card title="現在の稼働状況" accent="pink">
              <p>稼働中: 2 bots • レスポンスレイテンシ: 120ms</p>
            </Card>
            <Card title="トークン使用量" accent="purple">
              <div className="h-36 bg-gradient-to-br from-[#111] to-[#111] rounded-md flex items-center justify-center">グラフプレースホルダ</div>
            </Card>
            <Card title="設定中のチャンネル" accent="teal">
              <ul>
                <li>#ai-general</li>
                <li>#dev-chat</li>
              </ul>
            </Card>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-2">
              <NetworkStats />
              <div className="mt-4 grid grid-cols-2 gap-4">
                <Card title="チャンネル管理" accent="pink">
                  <ChannelsManager />
                </Card>
                <Card title="Music Player" accent="pink">
                  <MusicPlayer />
                </Card>
              </div>
              <div className="mt-4">
                <Card title="リソースモニター" accent="purple">
                  <ResourceMonitor />
                </Card>
              </div>
            </div>
            <div className="col-span-1">
              <Card title="会話ログ" accent="purple">
                <ChatLog />
                <div className="mt-4">
                  <ChannelActivity />
                </div>
              </Card>
            </div>
          </div>
        </section>
      </div>
    </main>
  )
}
