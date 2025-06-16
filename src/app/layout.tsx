// src/app/layout.tsx
import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import { cn } from "@/lib/utils"
import { NavigationLinks } from "@/components/navigation-links"
import { SpirographLogo } from "@/components/spirograph-logo"
import { Toaster } from "sonner"

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
})

export const metadata: Metadata = {
  title: "Timelapser v4",
  description: "Professional timelapse automation platform for RTSP cameras",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang='en'>
      <body
        className={cn(
          "min-h-screen bg-blue text-white font-sans antialiased overflow-x-hidden",
          inter.variable
        )}
      >
        {/* Dynamic animated background */}
        <div className='fixed inset-0 pointer-events-none'>
          {/* Gradient orbs */}
          <div className='absolute rounded-full top-20 left-20 w-96 h-96 bg-pink/10 blur-3xl floating' />
          <div
            className='absolute rounded-full top-40 right-32 w-80 h-80 bg-cyan/15 blur-3xl floating'
            style={{ animationDelay: "2s" }}
          />
          <div
            className='absolute w-64 h-64 rounded-full bottom-32 left-1/3 bg-purple/20 blur-3xl floating'
            style={{ animationDelay: "4s" }}
          />

          {/* Animated grid pattern */}
          <div className='absolute inset-0 opacity-5'>
            <div className='w-full h-full bg-[linear-gradient(var(--color-purple-muted)_1px,transparent_1px),linear-gradient(90deg,var(--color-purple-muted)_1px,transparent_1px)] bg-[size:60px_60px]' />
          </div>
        </div>

        {/* Navigation with active page detection */}
        <nav className='mx-4 mt-4 relative z-20 border-b glass-strong border-purple-muted/20'>
          <div className='px-6 py-4 mx-auto max-w-7xl'>
            <div className='flex items-center justify-between'>
              {/* Logo area with spirograph */}
              <div className='flex items-center space-x-4'>
                <SpirographLogo size={48} />
                <div>
                  <h1 className='text-2xl font-bold gradient-text'>
                    Timelapser
                  </h1>
                  <p className='font-mono text-xs text-grey-light/60'>v4.0</p>
                </div>
              </div>

              {/* Navigation with icons and active states */}
              <NavigationLinks />

              {/* Status indicator */}
              <div className='flex items-center space-x-2'>
                <div className='w-2 h-2 rounded-full bg-success pulse-glow' />
                <span className='text-xs text-grey-light/70'>
                  System Online
                </span>
              </div>
            </div>
          </div>
        </nav>

        {/* Main content */}
        <main className='relative z-10'>
          <div className='px-6 py-8 mx-auto max-w-7xl'>
            {/* Decorative elements */}
            <div className='absolute w-32 h-32 border rounded-full top-8 right-8 border-purple-muted/20 floating opacity-30' />
            <div
              className='absolute w-4 h-4 rounded-full top-32 left-8 bg-cyan/40 floating'
              style={{ animationDelay: "1s" }}
            />
            <div
              className='absolute w-6 h-6 top-64 right-1/4 bg-pink/30 rounded-square floating'
              style={{ animationDelay: "3s" }}
            />

            {children}
          </div>
        </main>

        {/* Floating elements */}
        <div className='fixed pointer-events-none bottom-8 right-8'>
          <div className='w-3 h-3 rounded-full bg-yellow/60 floating' />
        </div>
        <div className='fixed pointer-events-none bottom-32 left-12'>
          <div
            className='w-2 h-8 rounded-full bg-purple/40 floating'
            style={{ animationDelay: "2s" }}
          />
        </div>

        {/* Toast notifications */}
        <Toaster position='bottom-right' richColors closeButton theme='dark' />
      </body>
    </html>
  )
}
