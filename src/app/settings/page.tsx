// src/app/settings/page.tsx
"use client"

import { Button } from "@/components/ui/button"
import { Save, RefreshCw } from "lucide-react"
import { useSettings, useSettingsActions } from "@/contexts/settings-context"
import { DangerZoneCard } from "./components/danger-zone-card"
import { TimezoneSettingsCard } from "./components/timezone-settings-card"
import { LoggingSettingsCard } from "./components/logging-settings-card"
import { ApiKeySettingsCard } from "./components/api-key-settings-card"
import { CaptureSettingsCard } from "./components/capture-settings-card"
import { CorruptionSettingsCard } from "./components/corruption-settings-card"
import { WeatherSettingsCard } from "./components/weather-settings-card"
import { CurrentConfigurationCard } from "./components/current-configuration-card"
import { InfoCards } from "./components/info-cards"
import { Separator } from "@/components/ui/separator"
import { Badge } from "@/components/ui/badge"
import { toast } from "@/lib/toast"
import CorruptionTestComponent from "@/components/corruption-test-component"

export default function Settings() {
  // Get all settings from global context
  const settings = useSettings()
  const { saveAllSettings, saving } = useSettingsActions()

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault()
    await saveAllSettings()
  }

  // TODO: This needs to be moved to a layout file
  if (settings.loading) {
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
      <form onSubmit={handleSaveSettings} className='space-y-6'>
        {/* Capture Settings*/}
        <CaptureSettingsCard />

        {/* Timezone Settings - Full Width */}
        <TimezoneSettingsCard />

        {/* Weather Settings - Full Width */}
        <WeatherSettingsCard />

        {/* Additional Settings Grid */}
        <div className='grid gap-6 lg:grid-cols-2'>
          {/* External Services */}
          <ApiKeySettingsCard />

          {/* System Maintenance */}
          <LoggingSettingsCard />
        </div>

        {/* Corruption Detection Settings - Full Width */}
        <CorruptionSettingsCard />
        <CorruptionTestComponent />
        {/*  Save Button */}
        <div className='flex justify-center pt-4 pb-2'>
          <Button
            type='submit'
            disabled={saving}
            className='transition-colors duration-300 ease-in text-black min-w-[200px] bg-primary hover:bg-primary/80 font-medium'
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

        {/* Danger Zone - Full Width */}
        <DangerZoneCard />
      </form>

      {/* Current Configuration - Full Width */}
      <CurrentConfigurationCard
        settings={{
          captureInterval: settings.captureInterval,
          timezone: settings.timezone,
          openWeatherApiKey: settings.openWeatherApiKey,
          generateThumbnails: settings.generateThumbnails,
          imageCaptureType: settings.imageCaptureType,
          logLevel: settings.logLevel,
        }}
      />

      {/* Info Cards */}
      <InfoCards />
    </div>
  )
}
