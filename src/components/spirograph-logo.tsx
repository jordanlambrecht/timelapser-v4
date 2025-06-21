// src/components/spirograph-logo.tsx

import { cn } from "@/lib/utils"

interface SpirographLogoProps {
  className?: string
  size?: number
}

export function SpirographLogo({ className, size = 48 }: SpirographLogoProps) {
  // Generate spirograph path using mathematical equations
  const generateSpirographPath = (
    R: number,
    r: number,
    d: number,
    steps: number = 500
  ) => {
    const path: string[] = []
    const centerX = 50
    const centerY = 50

    for (let i = 0; i <= steps; i++) {
      const t = (i / steps) * 2 * Math.PI * 10 // Multiple rotations for complete pattern
      const x =
        centerX +
        ((R - r) * Math.cos(t) + d * Math.cos(((R - r) / r) * t)) * 0.8
      const y =
        centerY +
        ((R - r) * Math.sin(t) - d * Math.sin(((R - r) / r) * t)) * 0.8

      if (i === 0) {
        path.push(`M ${x} ${y}`)
      } else {
        path.push(`L ${x} ${y}`)
      }
    }

    return path.join(" ")
  }

  // Different spirograph parameters for layered effect
  const spirographs = [
    {
      R: 30,
      r: 7,
      d: 15,
      color: "var(--color-pink)",
      opacity: 0.8,
      duration: "20s",
    },
    {
      R: 25,
      r: 5,
      d: 12,
      color: "var(--color-cyan)",
      opacity: 0.7,
      duration: "15s",
    },
    {
      R: 20,
      r: 8,
      d: 10,
      color: "var(--color-purple)",
      opacity: 0.6,
      duration: "25s",
    },
    {
      R: 35,
      r: 12,
      d: 8,
      color: "var(--color-purple-light)",
      opacity: 0.5,
      duration: "30s",
    },
  ]

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
          {/* Main spirograph layers */}
          {spirographs.map((config, index) => (
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
                stroke={
                  index < 2
                    ? `url(#spirograph-gradient-${index + 1})`
                    : config.color
                }
                strokeWidth='0.5'
                opacity={config.opacity}
                strokeLinecap='round'
                strokeLinejoin='round'
              />
            </g>
          ))}

          {/* Additional detailed inner pattern */}
          <g
            className='animate-spin'
            style={{
              animationDuration: "8s",
              animationDirection: "reverse",
              transformOrigin: "50px 50px",
            }}
          >
            <path
              d={generateSpirographPath(15, 3, 8)}
              fill='none'
              stroke='var(--color-yellow)'
              strokeWidth='0.3'
              opacity='0.9'
              strokeLinecap='round'
            />
          </g>
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
