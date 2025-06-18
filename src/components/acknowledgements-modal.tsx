// src/components/acknowledgements-modal.tsx
"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import {
  ExternalLink,
  Heart,
  Code,
  Package,
  Layers3,
  Palette,
  Zap,
  Database,
  Globe,
  Camera,
  Video,
} from "lucide-react"

interface Acknowledgement {
  name: string
  version?: string
  description: string
  license: string
  url: string
  category: "frontend" | "backend" | "ui" | "development" | "infrastructure"
  icon?: React.ReactNode
}

const acknowledgements: Acknowledgement[] = [
  // Frontend Framework
  {
    name: "Next.js",
    version: "15.1.6",
    description: "React framework for production-grade applications",
    license: "MIT",
    url: "https://nextjs.org",
    category: "frontend",
    icon: <Layers3 className='w-4 h-4' />,
  },
  {
    name: "React",
    version: "19.0.0",
    description: "JavaScript library for building user interfaces",
    license: "MIT",
    url: "https://react.dev",
    category: "frontend",
    icon: <Code className='w-4 h-4' />,
  },
  {
    name: "TypeScript",
    description: "Typed JavaScript at any scale",
    license: "Apache-2.0",
    url: "https://www.typescriptlang.org",
    category: "development",
    icon: <Code className='w-4 h-4' />,
  },

  // UI Components
  {
    name: "Tailwind CSS",
    description: "Utility-first CSS framework",
    license: "MIT",
    url: "https://tailwindcss.com",
    category: "ui",
    icon: <Palette className='w-4 h-4' />,
  },
  {
    name: "Radix UI",
    description: "Low-level UI primitives with accessibility",
    license: "MIT",
    url: "https://www.radix-ui.com",
    category: "ui",
    icon: <Layers3 className='w-4 h-4' />,
  },
  {
    name: "Lucide React",
    description: "Beautiful & consistent icons",
    license: "ISC",
    url: "https://lucide.dev",
    category: "ui",
    icon: <Palette className='w-4 h-4' />,
  },
  {
    name: "Sonner",
    description: "Opinionated toast component for React",
    license: "MIT",
    url: "https://sonner.emilkowal.ski",
    category: "ui",
    icon: <Zap className='w-4 h-4' />,
  },

  // Backend & Infrastructure
  {
    name: "FastAPI",
    description: "Modern, fast web framework for Python APIs",
    license: "MIT",
    url: "https://fastapi.tiangolo.com",
    category: "backend",
    icon: <Zap className='w-4 h-4' />,
  },
  {
    name: "SQLAlchemy",
    description: "Python SQL toolkit and Object Relational Mapping",
    license: "MIT",
    url: "https://www.sqlalchemy.org",
    category: "backend",
    icon: <Database className='w-4 h-4' />,
  },
  {
    name: "PostgreSQL",
    description: "Advanced open source relational database",
    license: "PostgreSQL License",
    url: "https://www.postgresql.org",
    category: "infrastructure",
    icon: <Database className='w-4 h-4' />,
  },
  {
    name: "Alembic",
    description: "Database migration tool for SQLAlchemy",
    license: "MIT",
    url: "https://alembic.sqlalchemy.org",
    category: "backend",
    icon: <Database className='w-4 h-4' />,
  },

  // Specialized Libraries
  {
    name: "OpenCV",
    description: "Open source computer vision library",
    license: "Apache-2.0",
    url: "https://opencv.org",
    category: "backend",
    icon: <Camera className='w-4 h-4' />,
  },
  {
    name: "FFmpeg",
    description:
      "Complete solution to record, convert and stream audio and video",
    license: "LGPL/GPL",
    url: "https://ffmpeg.org",
    category: "infrastructure",
    icon: <Video className='w-4 h-4' />,
  },
  {
    name: "React Timezone Select",
    description: "Timezone selection component for React",
    license: "MIT",
    url: "https://github.com/ndom91/react-timezone-select",
    category: "ui",
    icon: <Globe className='w-4 h-4' />,
  },
]

const categoryColors = {
  frontend: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  backend: "bg-green-500/20 text-green-400 border-green-500/30",
  ui: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  development: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  infrastructure: "bg-red-500/20 text-red-400 border-red-500/30",
}

export function AcknowledgementsModal() {
  const [isOpen, setIsOpen] = useState(false)

  const groupedAcknowledgements = acknowledgements.reduce((acc, item) => {
    if (!acc[item.category]) {
      acc[item.category] = []
    }
    acc[item.category].push(item)
    return acc
  }, {} as Record<string, Acknowledgement[]>)

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button
          variant='link'
          size='sm'
          className='text-grey-light/60 hover:text-purple-light p-0 h-auto text-xs'
        >
          <Package className='w-3 h-3 mr-1' />
          Open Source Acknowledgements
        </Button>
      </DialogTrigger>
      <DialogContent className='max-w-4xl max-h-[80vh] glass'>
        <DialogHeader>
          <DialogTitle className='flex items-center gap-2 text-xl'>
            <Heart className='w-5 h-5 text-pink' />
            Open Source Acknowledgements
          </DialogTitle>
          <DialogDescription>
            This project stands on the shoulders of giants. Here are the amazing
            open source projects that make Timelapser v4 possible.
          </DialogDescription>
        </DialogHeader>

        <div className='h-[60vh] w-full overflow-y-auto pr-4'>
          <div className='space-y-6'>
            {Object.entries(groupedAcknowledgements).map(
              ([category, items]) => (
                <div key={category} className='space-y-3'>
                  <div className='flex items-center gap-2'>
                    <Badge
                      variant='outline'
                      className={`capitalize ${
                        categoryColors[category as keyof typeof categoryColors]
                      }`}
                    >
                      {category}
                    </Badge>
                    <div className='h-px bg-border flex-1' />
                  </div>

                  <div className='grid gap-3 md:grid-cols-2'>
                    {items.map((item) => (
                      <div
                        key={item.name}
                        className='p-4 rounded-lg border border-borderColor/50 bg-background/30 hover:bg-background/50 transition-colors'
                      >
                        <div className='flex items-start justify-between gap-3'>
                          <div className='space-y-2 flex-1'>
                            <div className='flex items-center gap-2'>
                              {item.icon}
                              <h3 className='font-semibold text-foreground'>
                                {item.name}
                              </h3>
                              {item.version && (
                                <Badge variant='secondary' className='text-xs'>
                                  v{item.version}
                                </Badge>
                              )}
                            </div>
                            <p className='text-sm text-muted-foreground leading-relaxed'>
                              {item.description}
                            </p>
                            <div className='flex items-center gap-2 text-xs text-muted-foreground'>
                              <Badge variant='outline' className='text-xs'>
                                {item.license}
                              </Badge>
                            </div>
                          </div>
                          <Button
                            asChild
                            variant='ghost'
                            size='sm'
                            className='shrink-0'
                          >
                            <a
                              href={item.url}
                              target='_blank'
                              rel='noopener noreferrer'
                              className='text-muted-foreground hover:text-foreground'
                            >
                              <ExternalLink className='w-4 h-4' />
                            </a>
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )
            )}
          </div>

          <div className='mt-8 p-4 rounded-lg bg-muted/30 border border-borderColor/30'>
            <div className='flex items-center gap-2 mb-2'>
              <Heart className='w-4 h-4 text-pink' />
              <p className='text-sm font-medium'>Thank You</p>
            </div>
            <p className='text-xs text-muted-foreground leading-relaxed'>
              Special thanks to all the maintainers, contributors, and
              communities behind these projects. Your dedication to open source
              enables projects like this to exist and thrive.
            </p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
