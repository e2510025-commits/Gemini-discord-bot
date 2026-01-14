import React from 'react'
import { motion } from 'framer-motion'

type Props = {
  title: string
  accent?: 'pink' | 'purple' | 'teal'
  children?: React.ReactNode
}

const accentMap = {
  pink: 'bg-gradient-to-br from-[#ff66aa] to-[#a356ff] shadow-pink-500/20',
  purple: 'bg-gradient-to-br from-[#a356ff] to-[#6a5cff] shadow-purple-500/20',
  teal: 'bg-gradient-to-br from-[#00ffcc] to-[#00b3ff] shadow-teal-500/20',
}

export default function Card({ title, accent = 'purple', children }: Props) {
  return (
    <motion.div
      initial={{ y: 8, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.45 }}
      className={`p-4 rounded-2xl bg-[#0c0c0c] border border-[#1a1a1a] ${accentMap[accent]} min-h-[120px]`}
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-lg font-semibold">{title}</h3>
        <div className="w-10 h-4 rounded-full bg-white/6" />
      </div>
      <div className="text-sm text-gray-300">{children}</div>
    </motion.div>
  )
}
