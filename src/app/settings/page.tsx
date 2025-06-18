// src/app/settings/page.tsx
"use client"

import { useState, useEffect } from "react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import {
  Settings as SettingsIcon,
  Clock,
  Save,
  RefreshCw,
  Globe,
  Image as ImageIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { TimezoneSelector } from "@/components/timezone-selector-combobox"
import { ThumbnailRegenerationModal } from "@/components/thumbnail-regeneration-modal"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { toast } from "@/lib/toast"

export default function Settings() {
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [captureInterval, setCaptureInterval] = useState("")
  const [timezone, setTimezone] = useState("America/Chicago")
  const [generateThumbnails, setGenerateThumbnails] = useState(true)
  const [thumbnailModalOpen, setThumbnailModalOpen] = useState(false)
  const [thumbnailConfirmOpen, setThumbnailConfirmOpen] = useState(false)

  // Debug timezone changes
  const handleTimezoneChange = (newTimezone: string) => {
    console.log(
      "🎯 Settings page: timezone changing from",
      timezone,
      "to",
      newTimezone
    )
    setTimezone(newTimezone)
  }

  useEffect(() => {
    fetchSettings()
  }, [])

  const fetchSettings = async () => {
    console.log("🔄 Fetching settings from API...")
    try {
      const response = await fetch("/api/settings", { cache: "no-store" })
      const data = await response.json()
      console.log("📥 Received settings:", data)

      setSettings(data)
      setCaptureInterval(data.capture_interval || "300")
      setTimezone(data.timezone || "America/Chicago")
      setGenerateThumbnails(data.generate_thumbnails !== "false") // Default true unless explicitly false

      console.log("✅ Settings state updated:", {
        captureInterval: data.capture_interval || "300",
        timezone: data.timezone || "America/Chicago",
        generateThumbnails: data.generate_thumbnails !== "false",
      })
    } catch (error) {
      console.error("❌ Failed to fetch settings:", error)
    } finally {
      setLoading(false)
    }
  }

  const saveSettings = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)

    console.log("💾 Saving settings:", {
      captureInterval,
      timezone,
      generateThumbnails,
    })

    try {
      // Save capture interval, timezone, and thumbnail setting
      const updates = [
        { key: "capture_interval", value: captureInterval },
        { key: "timezone", value: timezone },
        { key: "generate_thumbnails", value: generateThumbnails.toString() },
      ]

      console.log("🔄 Updates to save:", updates)

      for (const update of updates) {
        console.log(`📤 Saving ${update.key}:`, update.value)

        // Add more detailed logging for debugging
        const requestUrl = "/api/settings"
        const requestOptions = {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(update),
        }

        console.log(`🔍 Request details for ${update.key}:`, {
          url: requestUrl,
          method: requestOptions.method,
          headers: requestOptions.headers,
          body: update,
        })

        const response = await fetch(requestUrl, requestOptions)

        console.log(
          `📥 Response for ${update.key}:`,
          response.status,
          response.statusText,
          response.ok
        )

        if (!response.ok) {
          const errorText = await response.text()
          console.error(`❌ Failed to save ${update.key}:`, {
            status: response.status,
            statusText: response.statusText,
            errorText,
            headers: Object.fromEntries(response.headers.entries()),
          })
          throw new Error(
            `Failed to save ${update.key}: ${response.status} ${response.statusText} - ${errorText}`
          )
        }

        const result = await response.json()
        console.log(`✅ Saved ${update.key} successfully:`, result)
      }

      // Show success toast
      toast.success("Settings saved successfully!", {
        description:
          "Your capture interval, timezone, and thumbnail settings have been updated",
        duration: 4000,
      })

      console.log("🔄 Fetching updated settings...")
      await fetchSettings()
    } catch (error: unknown) {
      console.error("❌ Failed to save settings:", error)
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error occurred"

      // Show error toast
      toast.error("Failed to save settings", {
        description: errorMessage,
        duration: 6000,
      })
    } finally {
      setSaving(false)
    }
  }

  const formatInterval = (seconds: string) => {
    const sec = parseInt(seconds)
    if (sec < 60) return `${sec} seconds`
    if (sec < 3600) return `${Math.floor(sec / 60)} minutes`
    return `${Math.floor(sec / 3600)} hours`
  }

  const getIntervalPreset = (seconds: string) => {
    const sec = parseInt(seconds)
    const presets = [
      { label: "Every 30 seconds", value: 30 },
      { label: "Every minute", value: 60 },
      { label: "Every 5 minutes", value: 300 },
      { label: "Every 15 minutes", value: 900 },
      { label: "Every hour", value: 3600 },
    ]

    return presets.find((p) => p.value === sec)?.label || "Custom interval"
  }

  // TODO: This needs to be moved to a layout file
  if (loading) {
    return (
      <div className='flex items-center justify-center min-h-[60vh]'>
        <div className='space-y-6 text-center'>
          <div className='relative'>
            <div className='w-16 h-16 mx-auto border-4 rounded-full border-cyan/20 border-t-cyan animate-spin' />
            <div
              className='absolute inset-0 w-16 h-16 mx-auto border-4 rounded-full border-purple/20 border-b-purple-light animate-spin'
              style={{
                animationDirection: "reverse",
                animationDuration: "1.5s",
              }}
            />
            <div
              className='absolute w-12 h-12 mx-auto border-2 rounded-full inset-2 border-pink/30 border-l-pink animate-spin'
              style={{ animationDuration: "2s" }}
            />
          </div>
          <div>
            <p className='font-medium text-white'>Loading settings...</p>
            <p className='mt-1 text-sm text-grey-light/60'>
              Configuring system preferences
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className='max-w-4xl mx-auto space-y-8'>
      {/* Header */}
      <div className='space-y-4'>
        <div>
          <h1 className='text-4xl font-bold gradient-text'>Settings</h1>
          <p className='mt-2 text-muted-foreground'>
            Configure capture intervals and system preferences
          </p>
        </div>
      </div>

      {/* Unified Settings Form */}
      <form onSubmit={saveSettings} className='space-y-6'>
        <div className='grid gap-6 lg:grid-cols-2'>
          {/* Capture Settings */}
          <Card className='transition-all duration-300 glass hover:glow'>
            <CardHeader>
              <CardTitle className='flex items-center space-x-2'>
                <Clock className='w-5 h-5 text-primary' />
                <span>Capture Settings</span>
              </CardTitle>
              <CardDescription>
                Configure image capture intervals and thumbnail generation
              </CardDescription>
            </CardHeader>
            <CardContent className='space-y-6'>
              <div className='space-y-4'>
                <div className='space-y-3'>
                  <Label htmlFor='interval' className='text-sm font-medium'>
                    Interval (seconds)
                  </Label>
                  <div className='flex space-x-3'>
                    <Input
                      id='interval'
                      type='number'
                      value={captureInterval}
                      onChange={(e) => setCaptureInterval(e.target.value)}
                      min='1'
                      max='86400'
                      className='bg-background/50 border-borderColor/50 focus:border-primary/50'
                      required
                    />
                    <Badge className='px-3 py-2 whitespace-nowrap'>
                      {formatInterval(captureInterval)}
                    </Badge>
                  </div>
                  <p className='text-xs text-muted-foreground'>
                    Range: 1 second to 24 hours (86,400 seconds)
                  </p>
                </div>

                {/* Thumbnail Generation Toggle */}
                <div className='space-y-3'>
                  <div className='flex items-center justify-between'>
                    <div className='space-y-1'>
                      <Label
                        htmlFor='thumbnails'
                        className='text-sm font-medium flex items-center space-x-2'
                      >
                        <ImageIcon className='w-4 h-4 text-purple-light' />
                        <span>Generate Thumbnails</span>
                      </Label>
                      <p className='text-xs text-muted-foreground'>
                        Create small preview images for faster dashboard loading
                      </p>
                    </div>
                    <Switch
                      id='thumbnails'
                      checked={generateThumbnails}
                      onCheckedChange={setGenerateThumbnails}
                    />
                  </div>
                  <div className='p-3 rounded-lg bg-background/30 border border-borderColor/30'>
                    <div className='flex items-center space-x-2 text-xs text-muted-foreground'>
                      <div
                        className={cn(
                          "w-2 h-2 rounded-full",
                          generateThumbnails ? "bg-green-500" : "bg-gray-500"
                        )}
                      />
                      <span>
                        {generateThumbnails
                          ? "Thumbnails will be generated for faster dashboard performance"
                          : "Only full-size images will be saved (slower dashboard loading)"}
                      </span>
                    </div>
                    {generateThumbnails && (
                      <div className='mt-2 text-xs text-purple-light/70'>
                        Creates: 200×150 thumbnails + 800×600 small images
                        alongside full captures
                      </div>
                    )}
                    {generateThumbnails && (
                      <div className='mt-3 pt-3 border-t border-borderColor/20'>
                        <Button
                          type='button'
                          variant='outline'
                          size='sm'
                          onClick={() => setThumbnailConfirmOpen(true)}
                          className='text-xs border-cyan/30 text-cyan hover:bg-cyan/10'
                        >
                          <ImageIcon className='w-3 h-3 mr-2' />
                          Regenerate All Now
                        </Button>
                        <p className='mt-2 text-xs text-gray-500'>
                          Generate thumbnails for existing images that don't
                          have them
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Quick Presets */}
                <div className='space-y-3'>
                  <Label className='text-sm font-medium'>Quick Presets</Label>
                  <div className='grid grid-cols-2 gap-2'>
                    {[
                      { label: "30s", value: "30" },
                      { label: "1m", value: "60" },
                      { label: "5m", value: "300" },
                      { label: "15m", value: "900" },
                      { label: "1h", value: "3600" },
                      { label: "6h", value: "21600" },
                    ].map((preset) => (
                      <Button
                        key={preset.value}
                        type='button'
                        variant={
                          captureInterval === preset.value
                            ? "default"
                            : "outline"
                        }
                        size='sm'
                        onClick={() => setCaptureInterval(preset.value)}
                        className={cn(
                          "text-xs",
                          captureInterval === preset.value &&
                            "bg-primary text-primary-foreground"
                        )}
                      >
                        {preset.label}
                      </Button>
                    ))}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Timezone Settings */}
          <Card className='transition-all duration-300 glass hover:glow'>
            <CardHeader className='mb-2 pb-0'>
              <CardTitle className='flex items-center space-x-2'>
                <Globe className='w-5 h-5 text-pink' />
                <span className='text-white'>Timezone Configuration</span>
              </CardTitle>
              <CardDescription>
                Set the timezone for accurate time calculations and display
              </CardDescription>
            </CardHeader>
            <CardContent>
              <TimezoneSelector
                value={timezone}
                onChange={handleTimezoneChange}
                disabled={saving}
              />
            </CardContent>
          </Card>
        </div>

        {/*  Save Button */}
        <div className='flex justify-center pt-4'>
          <Button
            type='submit'
            disabled={saving}
            className='transition-colors duration-300 ease-in text-purple-dark min-w-[200px] bg-primary hover:bg-primary/50'
          >
            {saving ? (
              <>
                <RefreshCw className='w-4 h-4 mr-2 animate-spin' />
                Saving Settings...
              </>
            ) : (
              <>
                <Save className='w-4 h-4 mr-2' />
                Save All Settings
              </>
            )}
          </Button>
        </div>
      </form>

      {/* Current Configuration - Full Width */}
      <Card className='transition-all duration-300 glass hover:glow'>
        <CardHeader>
          <CardTitle className='flex items-center space-x-2'>
            <SettingsIcon className='w-5 h-5 text-primary' />
            <span>Current Configuration</span>
          </CardTitle>
          <CardDescription>
            Active system settings and their values
          </CardDescription>
        </CardHeader>
        <CardContent className='space-y-4'>
          <div className='grid gap-4 md:grid-cols-2 lg:grid-cols-3'>
            {Object.entries(settings).map(([key, value]) => (
              <div
                key={key}
                className='flex items-center justify-between p-3 border rounded-lg bg-background/50 border-borderColor/50'
              >
                <div className='space-y-1'>
                  <p className='text-sm font-medium capitalize'>
                    {key.replace(/_/g, " ")}
                  </p>
                  {key === "capture_interval" && (
                    <p className='text-xs text-muted-foreground'>
                      {getIntervalPreset(value)}
                    </p>
                  )}
                  {key === "timezone" && (
                    <p className='text-xs text-muted-foreground'>
                      {new Date().toLocaleString("en-US", {
                        timeZone: value,
                        hour: "2-digit",
                        minute: "2-digit",
                        hour12: true,
                      })}
                    </p>
                  )}
                </div>
                <Badge variant='secondary'>
                  {key === "capture_interval"
                    ? formatInterval(value)
                    : key === "timezone"
                    ? value.split("/").pop()
                    : value}
                </Badge>
              </div>
            ))}
          </div>

          {Object.keys(settings).length === 0 && (
            <div className='py-6 text-center'>
              <p className='text-sm text-muted-foreground'>
                No settings configured yet
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Info Cards */}
      <div className='grid gap-6 md:grid-cols-2'>
        <Card className='glass border-borderColor/50'>
          <CardHeader>
            <CardTitle className='text-lg'>💡 Capture Guidelines</CardTitle>
          </CardHeader>
          <CardContent className='space-y-3 text-sm text-muted-foreground'>
            <div className='space-y-2'>
              <p>
                <strong className='text-foreground'>
                  Fast intervals (1-30s):
                </strong>{" "}
                High-detail timelapses, short events
              </p>
              <p>
                <strong className='text-foreground'>
                  Medium intervals (1-15m):
                </strong>{" "}
                Construction, daily activities
              </p>
              <p>
                <strong className='text-foreground'>
                  Slow intervals (1-6h):
                </strong>{" "}
                Long-term projects, seasonal changes
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className='glass border-borderColor/50'>
          <CardHeader>
            <CardTitle className='text-lg'>⚙️ System Info</CardTitle>
          </CardHeader>
          <CardContent className='space-y-3 text-sm text-muted-foreground'>
            <div className='space-y-2'>
              <p>
                <strong className='text-foreground'>Time Windows:</strong>{" "}
                Configure per-camera to capture only during specific hours
              </p>
              <p>
                <strong className='text-foreground'>Health Monitoring:</strong>{" "}
                Cameras automatically marked offline after failures
              </p>
              <p>
                <strong className='text-foreground'>Auto-Cleanup:</strong> Old
                images and logs are automatically managed
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Thumbnail Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={thumbnailConfirmOpen}
        onClose={() => setThumbnailConfirmOpen(false)}
        onConfirm={() => {
          setThumbnailConfirmOpen(false)
          setThumbnailModalOpen(true)
        }}
        title='Regenerate All Thumbnails'
        description='Are you sure? This might take a while to process all existing images and generate thumbnails.'
        confirmLabel='Yes, Start Regeneration'
        cancelLabel='Cancel'
        variant='warning'
        icon={<ImageIcon className='w-6 h-6' />}
      />

      {/* Thumbnail Regeneration Modal */}
      <ThumbnailRegenerationModal
        isOpen={thumbnailModalOpen}
        onClose={() => setThumbnailModalOpen(false)}
      />
    </div>
  )
}
