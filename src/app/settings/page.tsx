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
import { Settings as SettingsIcon, Clock, Save, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"

export default function Settings() {
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [captureInterval, setCaptureInterval] = useState("")

  useEffect(() => {
    fetchSettings()
  }, [])

  const fetchSettings = async () => {
    try {
      const response = await fetch("/api/settings", { cache: "no-store" })
      const data = await response.json()
      setSettings(data)
      setCaptureInterval(data.capture_interval || "300")
    } catch (error) {
      console.error("Failed to fetch settings:", error)
    } finally {
      setLoading(false)
    }
  }

  const saveSettings = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)

    try {
      const response = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          key: "capture_interval",
          value: captureInterval,
        }),
      })

      if (response.ok) {
        // Show success feedback
        const button = e.target as HTMLFormElement
        const submitBtn = button.querySelector('button[type="submit"]')
        if (submitBtn) {
          const originalText = submitBtn.textContent
          submitBtn.textContent = "✅ Saved!"
          setTimeout(() => {
            submitBtn.textContent = originalText
          }, 2000)
        }
        fetchSettings()
      } else {
        alert("Failed to save settings")
      }
    } catch (error) {
      console.error("Failed to save settings:", error)
      alert("Failed to save settings")
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

  if (loading) {
    return (
      <div className='flex items-center justify-center min-h-[400px]'>
        <div className='space-y-4 text-center'>
          <div className='w-8 h-8 mx-auto border-2 rounded-full border-primary border-t-transparent animate-spin' />
          <p className='text-muted-foreground'>Loading settings...</p>
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

      <div className='grid gap-6 lg:grid-cols-2'>
        {/* Capture Settings */}
        <Card className='transition-all duration-300 glass hover:glow'>
          <CardHeader>
            <CardTitle className='flex items-center space-x-2'>
              <Clock className='w-5 h-5 text-primary' />
              <span>Capture Interval</span>
            </CardTitle>
            <CardDescription>
              How often images are captured from your cameras
            </CardDescription>
          </CardHeader>
          <CardContent className='space-y-6'>
            <form onSubmit={saveSettings} className='space-y-4'>
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
                        captureInterval === preset.value ? "default" : "outline"
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

              <div className='flex pt-2 space-x-3'>
                <Button
                  type='submit'
                  disabled={saving}
                  className='flex-1 bg-primary hover:bg-primary/90'
                >
                  {saving ? (
                    <>
                      <RefreshCw className='w-4 h-4 mr-2 animate-spin' />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className='w-4 h-4 mr-2' />
                      Save Settings
                    </>
                  )}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        {/* Current Configuration */}
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
                </div>
                <Badge variant='secondary'>
                  {key === "capture_interval" ? formatInterval(value) : value}
                </Badge>
              </div>
            ))}

            {Object.keys(settings).length === 0 && (
              <div className='py-6 text-center'>
                <p className='text-sm text-muted-foreground'>
                  No settings configured yet
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

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
    </div>
  )
}
