// src/app/settings/page.tsx
"use client"

import { Button } from "@/components/ui/button"
import { Save, RefreshCw } from "lucide-react"
import { useSettings, useSettingsActions } from "@/contexts/settings-context"
import { StickySaveButton } from "@/components/ui/sticky-save-button"
import { DangerZoneCard } from "./components/danger-zone-card"
import { TimezoneSettingsCard } from "./components/timezone-settings-card"
import { LoggingSettingsCard } from "./components/logging-settings-card"
import { ImageSettingsCard } from "./components/image-settings-card"
import { CorruptionSettingsCard } from "./components/corruption-settings-card"
import { WeatherSettingsCard } from "./components/weather-settings-card"
import { CurrentConfigurationCard } from "./components/current-configuration-card"
import { InfoCards } from "./components/info-cards"
import CorruptionTestComponent from "@/components/corruption-test-component"
import { ThumbnailJobSettingsCard } from "./components/thumbnail-job-settings-card"
import { ThumbnailManagementCard } from "./components/thumbnail-management-card"

export default function Settings() {
  // Get all settings from global context
  const settings = useSettings()
  const { saveAllSettings, saving } = useSettingsActions()

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault()
    await saveAllSettings()
  }

  const handleStickySave = async () => {
    await saveAllSettings()
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
        <ImageSettingsCard />

        {/* Thumbnail Job Settings - Full Width */}
        <ThumbnailJobSettingsCard />

        {/* Thumbnail System Management - Full Width */}
        <ThumbnailManagementCard />

        {/* Timezone Settings - Full Width */}
        <TimezoneSettingsCard />

        {/* Weather Settings - Full Width */}
        <WeatherSettingsCard />

        {/* System Maintenance */}
        <LoggingSettingsCard />

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
          timezone: settings.timezone,
          openWeatherApiKey: settings.openWeatherApiKey,
          generateThumbnails: settings.enableThumbnailGeneration,
          imageCaptureType: settings.imageCaptureType,
          logLevel: settings.dbLogLevel,
        }}
      />

      {/* Info Cards */}
      <InfoCards />

      {/* Sticky Save Button */}
      <StickySaveButton
        show={settings.hasUnsavedChanges}
        onSave={handleStickySave}
        saving={saving}
      />
    </div>
  )
}
