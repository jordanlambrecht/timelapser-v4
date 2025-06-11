import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Timelapser v4',
  description: 'RTSP Camera Timelapse Automation Platform',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <nav className="bg-slate-800 text-white p-4">
          <div className="container mx-auto flex justify-between items-center">
            <h1 className="text-xl font-bold">Timelapser v4</h1>
            <div className="space-x-4">
              <a href="/" className="hover:text-slate-300">Dashboard</a>
              <a href="/settings" className="hover:text-slate-300">Settings</a>
              <a href="/tests" className="hover:text-slate-300">Tests</a>
            </div>
          </div>
        </nav>
        <main className="container mx-auto p-4">
          {children}
        </main>
      </body>
    </html>
  )
}
