// src/components/spirograph-logo.tsx
"use client"
import React, { useEffect, useState } from "react"
import { cn } from "@/lib/utils"

interface SpirographLogoProps {
  className?: string
  size?: number
}

// Helper function for GCD calculation
function gcd(a: number, b: number): number {
  return b === 0 ? a : gcd(b, a % b)
}

// Generate a spirograph path
function generateSpirographPath(
  R: number,
  r: number,
  d: number,
  precision = 100
): string {
  const path = []
  const iterations = Math.ceil((r * precision) / gcd(R, r))

  for (let i = 0; i <= iterations; i++) {
    const t = (i / precision) * 2 * Math.PI
    const x = (R - r) * Math.cos(t) + d * Math.cos(((R - r) / r) * t)
    const y = (R - r) * Math.sin(t) - d * Math.sin(((R - r) / r) * t)

    // Scale and center - larger scale for bigger spirograph
    const scaledX = x * 0.8 + 50
    const scaledY = y * 0.8 + 50

    if (i === 0) {
      path.push(`M ${scaledX.toFixed(2)} ${scaledY.toFixed(2)}`)
    } else {
      path.push(`L ${scaledX.toFixed(2)} ${scaledY.toFixed(2)}`)
    }
  }

  return path.join(" ")
}

export function SpirographLogo({ className, size = 48 }: SpirographLogoProps) {
  const [isClient, setIsClient] = useState(false)

  // Only render the dynamic content on the client to avoid hydration issues
  useEffect(() => {
    setIsClient(true)
  }, [])

  // Simplified spirograph configurations - larger and less complex
  const spirographConfigs = [
    {
      R: 40,
      r: 12,
      d: 8,
      color: "url(#spirograph-gradient-1)",
      opacity: 0.9,
      duration: "15s",
    },
    {
      R: 35,
      r: 10,
      d: 6,
      color: "var(--color-purple)",
      opacity: 0.7,
      duration: "20s",
    },
  ]

  const innerPatternConfig = { R: 30, r: 8, d: 5 }

  return (
    <div
      className={cn("relative", className)}
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        viewBox='0 0 100 100'
        className='absolute inset-0'
      >
        <defs>
          {/* Animated gradient for dynamic colors */}
          <linearGradient
            id='spirograph-gradient-1'
            x1='0%'
            y1='0%'
            x2='100%'
            y2='100%'
          >
            <stop offset='0%' stopColor='var(--color-pink)'>
              <animate
                attributeName='stop-color'
                values='var(--color-pink);var(--color-cyan);var(--color-purple);var(--color-pink)'
                dur='10s'
                repeatCount='indefinite'
              />
            </stop>
            <stop offset='100%' stopColor='var(--color-cyan)'>
              <animate
                attributeName='stop-color'
                values='var(--color-cyan);var(--color-purple);var(--color-pink);var(--color-cyan)'
                dur='10s'
                repeatCount='indefinite'
              />
            </stop>
          </linearGradient>

          <linearGradient
            id='spirograph-gradient-2'
            x1='0%'
            y1='0%'
            x2='100%'
            y2='100%'
          >
            <stop offset='0%' stopColor='var(--color-purple)'>
              <animate
                attributeName='stop-color'
                values='var(--color-purple);var(--color-pink);var(--color-cyan);var(--color-purple)'
                dur='12s'
                repeatCount='indefinite'
              />
            </stop>
            <stop offset='100%' stopColor='var(--color-purple-light)'>
              <animate
                attributeName='stop-color'
                values='var(--color-purple-light);var(--color-cyan);var(--color-pink);var(--color-purple-light)'
                dur='12s'
                repeatCount='indefinite'
              />
            </stop>
          </linearGradient>
        </defs>

        {/* Rotating container for the entire spirograph */}
        <g
          className='animate-spin'
          style={{ animationDuration: "60s", transformOrigin: "50px 50px" }}
        >
          {/* Main spirograph layers - only render on client */}
          {isClient &&
            spirographConfigs.map((config, index) => (
              <g
                key={index}
                className='animate-spin'
                style={{
                  animationDuration: config.duration,
                  animationDirection: index % 2 === 0 ? "normal" : "reverse",
                  transformOrigin: "50px 50px",
                }}
              >
                <path
                  d={generateSpirographPath(config.R, config.r, config.d)}
                  fill='none'
                  stroke={config.color}
                  strokeWidth='1.5'
                  opacity={config.opacity}
                  strokeLinecap='round'
                  strokeLinejoin='round'
                />
              </g>
            ))}

          {/* Additional detailed inner pattern - only render on client */}
          {isClient && (
            <g
              className='animate-spin'
              style={{
                animationDuration: "8s",
                animationDirection: "reverse",
                transformOrigin: "50px 50px",
              }}
            >
              <path
                d={generateSpirographPath(
                  innerPatternConfig.R,
                  innerPatternConfig.r,
                  innerPatternConfig.d
                )}
                fill='none'
                stroke='var(--color-yellow)'
                strokeWidth='1'
                opacity='0.8'
                strokeLinecap='round'
              />
            </g>
          )}

          {/* Fallback static content for SSR */}
          {!isClient && (
            <circle
              cx='50'
              cy='50'
              r='30'
              fill='none'
              stroke='var(--color-purple)'
              strokeWidth='1.5'
              opacity='0.7'
            />
          )}
        </g>

        {/* Center dot */}
        <circle
          cx='50'
          cy='50'
          r='1'
          fill='url(#spirograph-gradient-1)'
          opacity='0.8'
        />

        {/* Subtle outer glow ring */}
        <circle
          cx='50'
          cy='50'
          r='45'
          fill='none'
          stroke='var(--color-pink)'
          strokeWidth='0.2'
          opacity='0.1'
          className='animate-pulse'
        />
      </svg>

      {/* Glow effect overlay */}
      <div
        className='absolute inset-0 rounded-full opacity-20 animate-pulse'
        style={{
          background:
            "radial-gradient(circle, var(--color-pink) 0%, transparent 70%)",
          filter: "blur(6px)",
          animationDuration: "4s",
        }}
      />
    </div>
  )
}
