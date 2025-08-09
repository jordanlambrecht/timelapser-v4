// src/app/settings/page.tsx
"use client"

import { useState, useEffect } from "react"
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
import { SettingsSidebar } from "./components/settings-sidebar"

export default function Settings() {
  // Get all settings from global context
  const settings = useSettings()
  const { saveAllSettings, saving } = useSettingsActions()
  
  // State for active section navigation
  const [activeSection, setActiveSection] = useState("capture")

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault()
    await saveAllSettings()
  }

  const handleStickySave = async () => {
    await saveAllSettings()
  }

  const scrollToSection = (sectionId: string) => {
    const element = document.getElementById(sectionId)
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "start" })
    }
  }

  const handleSectionChange = (sectionId: string) => {
    setActiveSection(sectionId)
    scrollToSection(sectionId)
  }

  // Intersection Observer to track active section
  useEffect(() => {
    const sectionIds = ["capture", "thumbnails", "timezone", "weather", "logging", "corruption", "system", "info"]
    
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && entry.intersectionRatio > 0.5) {
            setActiveSection(entry.target.id)
          }
        })
      },
      {
        threshold: [0.5],
        rootMargin: "-100px 0px -50% 0px"
      }
    )

    sectionIds.forEach((id) => {
      const element = document.getElementById(id)
      if (element) {
        observer.observe(element)
      }
    })

    return () => {
      observer.disconnect()
    }
  }, [])

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <div className="flex gap-8">
        {/* Sidebar Navigation */}
        <div className="sticky top-8 h-fit">
          <SettingsSidebar
            activeSection={activeSection}
            onSectionChange={handleSectionChange}
          />
        </div>
        
        {/* Main Content Area */}
        <div className="flex-1 space-y-8">
          {/* Header */}
          <div className="space-y-4">
            <div>
              <h1 className="text-4xl font-bold gradient-text">Settings</h1>
              <p className="mt-2 text-muted-foreground">
                Configure capture intervals and system preferences
              </p>
            </div>
          </div>

          {/* Unified Settings Form */}
          <form onSubmit={handleSaveSettings} className="space-y-8">
            {/* Capture Settings Section */}
            <section id="capture" className="space-y-6">
              <h2 className="text-2xl font-semibold border-b pb-2">Capture Settings</h2>
              <ImageSettingsCard />
            </section>

            {/* Thumbnail Settings Section */}
            <section id="thumbnails" className="space-y-6">
              <h2 className="text-2xl font-semibold border-b pb-2">Thumbnail Settings</h2>
              <ThumbnailJobSettingsCard />
              <ThumbnailManagementCard />
            </section>

            {/* Timezone Settings Section */}
            <section id="timezone" className="space-y-6">
              <h2 className="text-2xl font-semibold border-b pb-2">Timezone Settings</h2>
              <TimezoneSettingsCard />
            </section>

            {/* Weather Settings Section */}
            <section id="weather" className="space-y-6">
              <h2 className="text-2xl font-semibold border-b pb-2">Weather Settings</h2>
              <WeatherSettingsCard />
            </section>

            {/* Logging Settings Section */}
            <section id="logging" className="space-y-6">
              <h2 className="text-2xl font-semibold border-b pb-2">Logging Settings</h2>
              <LoggingSettingsCard />
            </section>

            {/* Corruption Detection Section */}
            <section id="corruption" className="space-y-6">
              <h2 className="text-2xl font-semibold border-b pb-2">Corruption Detection</h2>
              <CorruptionSettingsCard />
              <CorruptionTestComponent />
            </section>

            {/* System Maintenance Section */}
            <section id="system" className="space-y-6">
              <h2 className="text-2xl font-semibold border-b pb-2">System Maintenance</h2>
              <DangerZoneCard />
            </section>

            {/* Save Button */}
            <div className="flex justify-center pt-4 pb-2">
              <Button
                type="submit"
                disabled={saving}
                className="transition-colors duration-300 ease-in text-black min-w-[200px] bg-primary hover:bg-primary/80 font-medium"
              >
                {saving ? (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    Saving Settings...
                  </>
                ) : (
                  <>
                    <Save className="w-4 h-4 mr-2" />
                    Save All Settings
                  </>
                )}
              </Button>
            </div>
          </form>

          {/* Configuration Info Section */}
          <section id="info" className="space-y-6">
            <h2 className="text-2xl font-semibold border-b pb-2">Configuration Info</h2>
            <CurrentConfigurationCard
              settings={{
                timezone: settings.timezone,
                openWeatherApiKey: settings.openWeatherApiKey,
                generateThumbnails: settings.enableThumbnailGeneration,
                imageCaptureType: settings.imageCaptureType,
                logLevel: settings.dbLogLevel,
              }}
            />
            <InfoCards />
          </section>

          {/* Sticky Save Button */}
          <StickySaveButton
            show={settings.hasUnsavedChanges}
            onSave={handleStickySave}
            saving={saving}
          />
        </div>
      </div>
    </div>
  )
}
