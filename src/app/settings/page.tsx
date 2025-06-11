"use client"

import { useState, useEffect } from "react"

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
        alert("Settings saved successfully!")
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

  if (loading) {
    return <div className='py-8 text-center'>Loading settings...</div>
  }

  return (
    <div className='max-w-2xl mx-auto space-y-6'>
      <h1 className='text-3xl font-bold'>Settings</h1>

      <div className='p-6 bg-white rounded-lg shadow'>
        <h2 className='mb-4 text-xl font-semibold'>Capture Settings</h2>

        <form onSubmit={saveSettings} className='space-y-4'>
          <div>
            <label className='block mb-2 text-sm font-medium text-gray-700'>
              Image Capture Interval
            </label>
            <div className='flex items-center space-x-4'>
              <input
                type='number'
                value={captureInterval}
                onChange={(e) => setCaptureInterval(e.target.value)}
                min='1'
                max='86400'
                className='w-32 p-2 border border-gray-300 rounded'
                required
              />
              <span className='text-sm text-gray-600'>seconds</span>
            </div>
            <p className='mt-1 text-sm text-gray-500'>
              Current interval: {formatInterval(captureInterval)}
            </p>
            <p className='mt-1 text-xs text-gray-400'>
              How often to capture images from cameras (1 second to 24 hours)
            </p>
          </div>

          <div className='pt-4'>
            <button
              type='submit'
              disabled={saving}
              className='px-6 py-2 text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50'
            >
              {saving ? "Saving..." : "Save Settings"}
            </button>
          </div>
        </form>
      </div>

      <div className='p-6 rounded-lg bg-gray-50'>
        <h3 className='mb-3 text-lg font-medium'>Current Settings</h3>
        <div className='space-y-2'>
          {Object.entries(settings).map(([key, value]) => (
            <div key={key} className='flex justify-between'>
              <span className='font-medium capitalize'>
                {key.replace("_", " ")}:
              </span>
              <span className='text-gray-600'>
                {key === "capture_interval" ? formatInterval(value) : value}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
