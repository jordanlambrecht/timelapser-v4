// src/app/settings/components/weather-settings-card.tsx
"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { NumberInput } from "@/components/ui/number-input"
import { Badge } from "@/components/ui/badge"
import { Switch, SuperSwitch } from "@/components/ui/switch"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { PasswordInput } from "@/components/ui/password-input"
import { Separator } from "@/components/ui/separator"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Cloud,
  MapPin,
  Check,
  ExternalLink,
  Loader2,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
} from "lucide-react"
import { useSettings } from "@/contexts/settings-context"
import {
  validateApiKeyAndFetchWeather,
  getWeatherIcon,
  formatTemperature,
  capitalizeWords,
  type ApiKeyValidationResult,
} from "@/lib/weather-api"

export function WeatherSettingsCard() {
  const {
    weatherIntegrationEnabled,
    setWeatherIntegrationEnabled,
    weatherRecordData,
    setWeatherRecordData,
    sunriseSunsetEnabled,
    setSunriseSunsetEnabled,
    temperatureUnit,
    setTemperatureUnit,
    latitude,
    setLatitude,
    longitude,
    setLongitude,
    openWeatherApiKey,
    setOpenWeatherApiKey,
    apiKeyModified,
    setApiKeyModified,
    originalApiKeyHash,
    loading,
    weatherDateFetched,
    currentTemp,
    currentWeatherIcon,
    currentWeatherDescription,
    sunriseTimestamp,
    sunsetTimestamp,
    refetch: refetchSettings,
  } = useSettings()

  // Local state for validation errors
  const [latError, setLatError] = useState<string | null>(null)
  const [lngError, setLngError] = useState<string | null>(null)

  // API key validation state
  const [isValidatingApiKey, setIsValidatingApiKey] = useState(false)
  const [apiKeyValidationResult, setApiKeyValidationResult] =
    useState<ApiKeyValidationResult | null>(null)
  const [showWeatherConfirmation, setShowWeatherConfirmation] = useState(false)

  // Debounced validation and cleanup
  const [validationTimeout, setValidationTimeout] =
    useState<NodeJS.Timeout | null>(null)
  const [confirmationTimeout, setConfirmationTimeout] =
    useState<NodeJS.Timeout | null>(null)

  // Password field state and ref
  const [showApiKey, setShowApiKey] = useState(false)
  const apiKeyInputRef = useRef<HTMLInputElement>(null)
  const hasValidatedOnLoadRef = useRef(false)

  // Weather refresh state
  const [isRefreshingWeather, setIsRefreshingWeather] = useState(false)
  const [refreshError, setRefreshError] = useState<string | null>(null)

  // API key handlers (moved from ApiKeySettingsCard)
  const handleApiKeyChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setOpenWeatherApiKey(value)
    setApiKeyModified(true)

    // Clear previous validation results when user starts typing
    setApiKeyValidationResult(null)
    setShowWeatherConfirmation(false)

    // Clear previous timeout
    if (validationTimeout) {
      clearTimeout(validationTimeout)
    }

    // Validate after a short delay (debounced)
    if (value.trim()) {
      const timeoutId = setTimeout(() => {
        validateApiKey(value)
      }, 1500)

      setValidationTimeout(timeoutId)
    }
  }

  const getApiKeyDisplayValue = () => {
    // Always return the current key value for proper display
    return openWeatherApiKey
  }

  const getApiKeyPlaceholder = () => {
    if (!openWeatherApiKey && !originalApiKeyHash) {
      return "Enter your OpenWeather API key"
    }
    return ""
  }

  // Handle focus behavior based on eye icon state
  const handleApiKeyFocus = (e: React.FocusEvent<HTMLInputElement>) => {
    if (!showApiKey && openWeatherApiKey) {
      // If eye is off and there's a stored key, select all text
      e.target.select()
    }
    // If eye is on, allow normal cursor placement (default behavior)
  }

  // API key validation function
  const validateApiKey = useCallback(
    async (keyToValidate?: string) => {
      const apiKey = keyToValidate || openWeatherApiKey

      console.log(
        `🔍 validateApiKey called with: "${apiKey}", lat: ${latitude}, lng: ${longitude}`
      )

      if (!apiKey || !apiKey.trim()) {
        console.log("🚫 Validation skipped - no API key")
        setApiKeyValidationResult(null)
        setShowWeatherConfirmation(false)
        return
      }

      setIsValidatingApiKey(true)
      setShowWeatherConfirmation(false)

      try {
        // If we have coordinates, get full weather data
        if (latitude !== null && longitude !== null) {
          const result = await validateApiKeyAndFetchWeather(
            apiKey,
            latitude,
            longitude
          )
          setApiKeyValidationResult(result)

          if (result.isValid && result.weatherData) {
            setShowWeatherConfirmation(true)
            // Auto-hide confirmation after 8 seconds
            setTimeout(() => {
              setShowWeatherConfirmation(false)
            }, 8000)
          }
        } else {
          // No coordinates - just validate API key with a simple call
          const result = await validateApiKeyAndFetchWeather(
            apiKey,
            40.7128, // Default to NYC for validation
            -74.006
          )

          if (result.isValid) {
            setApiKeyValidationResult({
              isValid: true,
              message: "OpenWeather API key working",
            })
          } else {
            setApiKeyValidationResult(result)
          }
        }
      } catch (error) {
        setApiKeyValidationResult({
          isValid: false,
          error: "Validation failed",
        })
      } finally {
        setIsValidatingApiKey(false)
      }
    },
    [openWeatherApiKey, latitude, longitude]
  )

  // Validate API key when component loads with existing key
  useEffect(() => {
    if (openWeatherApiKey && !loading && !hasValidatedOnLoadRef.current) {
      hasValidatedOnLoadRef.current = true
      validateApiKey()
    }
  }, [openWeatherApiKey, loading, validateApiKey]) // Include validateApiKey but use ref to prevent loops

  // Cleanup timeouts on unmount
  useEffect(() => {
    return () => {
      if (validationTimeout) {
        clearTimeout(validationTimeout)
      }
      if (confirmationTimeout) {
        clearTimeout(confirmationTimeout)
      }
    }
  }, [validationTimeout, confirmationTimeout])

  // Check if we have an API key (either stored or currently entered)
  const hasApiKey =
    (originalApiKeyHash && originalApiKeyHash.trim()) ||
    (apiKeyModified && openWeatherApiKey.trim())
  const canUseWeather =
    weatherIntegrationEnabled &&
    hasApiKey &&
    latitude !== null &&
    longitude !== null
  const locationComplete = latitude !== null && longitude !== null

  // Update validation status when location becomes available/unavailable
  const canValidateApiKey = hasApiKey && locationComplete

  // Manual weather refresh function
  const handleRefreshWeather = async () => {
    setIsRefreshingWeather(true)
    setRefreshError(null)

    try {
      const response = await fetch("/api/weather/refresh", {
        method: "POST",
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error || "Failed to refresh weather")
      }

      const result = await response.json()

      // Show success feedback
      if (result.data) {
        setShowWeatherConfirmation(true)
        setApiKeyValidationResult({
          isValid: true,
          message: "Weather data refreshed",
          weatherData: {
            temperature: result.data.temperature,
            condition: result.data.description || "Unknown",
            description: result.data.description,
            icon: result.data.icon,
            cityName: result.data.city || "",
            countryCode: "",
          },
        })

        // Auto-hide after 5 seconds
        setTimeout(() => {
          setShowWeatherConfirmation(false)
        }, 5000)
      }

      // Refetch settings to update the UI with new weather data
      if (refetchSettings) {
        await refetchSettings()
      }
    } catch (error: any) {
      console.error("Weather refresh error:", error)
      setRefreshError(error.message || "Failed to refresh weather data")
    } finally {
      setIsRefreshingWeather(false)
    }
  }

  return (
    <Card className='transition-all duration-300 glass hover:glow'>
      <CardHeader>
        <CardTitle className='flex items-center space-x-2'>
          <Cloud className='w-5 h-5 text-blue-400' />
          <span>Weather Integration</span>
          {weatherIntegrationEnabled && canUseWeather && (
            <Badge
              variant='secondary'
              className='ml-2 text-xs bg-green-500/20 text-green-300 border-green-500/30'
            >
              Active
            </Badge>
          )}
        </CardTitle>
        <CardDescription>
          Configure OpenWeather integration for weather data collection and
          sunrise/sunset features
        </CardDescription>
      </CardHeader>

      <CardContent className='space-y-6'>
        {/* Main Weather Integration Toggle */}
        <div className='space-y-3'>
          {loading ? (
            <div className='h-6 bg-gray-200 rounded animate-pulse'></div>
          ) : (
            <SuperSwitch
              variant='labeled'
              id='weather-integration'
              falseLabel='disabled'
              trueLabel='enabled'
              checked={weatherIntegrationEnabled}
              onCheckedChange={setWeatherIntegrationEnabled}
            />
          )}
          <div className='space-y-1'>
            <Label className='text-sm font-medium'>Weather Integration</Label>
            <p className='text-xs text-muted-foreground'>
              Enable weather features including data collection and
              sunrise/sunset time windows
            </p>
          </div>
        </div>

        {weatherIntegrationEnabled && (
          <>
            <Separator />

            {/* OpenWeather API Key */}
            <div className='space-y-3'>
              <Label htmlFor='openweather-key' className='text-sm font-medium'>
                OpenWeather API Key
              </Label>
              <div className='relative'>
                <PasswordInput
                  ref={apiKeyInputRef}
                  id='openweather-key'
                  value={getApiKeyDisplayValue()}
                  onChange={handleApiKeyChange}
                  onFocus={handleApiKeyFocus}
                  placeholder={getApiKeyPlaceholder()}
                  className='bg-background/50 border-borderColor/50 focus:border-primary/50'
                  showPassword={showApiKey}
                  onTogglePassword={() => setShowApiKey(!showApiKey)}
                />
              </div>

              {/* API Key Validation Indicator */}
              {(isValidatingApiKey || apiKeyValidationResult) && (
                <div className='flex items-center space-x-2 text-xs'>
                  {isValidatingApiKey ? (
                    <>
                      <Loader2 className='w-4 h-4 animate-spin text-muted-foreground' />
                      <span className='text-muted-foreground'>
                        Validating API key...
                      </span>
                    </>
                  ) : apiKeyValidationResult?.isValid ? (
                    <>
                      <CheckCircle2 className='w-4 h-4 text-green-500' />
                      <span className='text-green-400'>
                        {apiKeyValidationResult.message ||
                          "API key validated successfully"}
                      </span>
                    </>
                  ) : (
                    <>
                      <AlertCircle className='w-4 h-4 text-red-500' />
                      <span className='text-red-400'>
                        {apiKeyValidationResult?.error ||
                          "API key validation failed"}
                      </span>
                    </>
                  )}
                </div>
              )}

              {/* Weather Confirmation */}
              {showWeatherConfirmation &&
                apiKeyValidationResult?.isValid &&
                apiKeyValidationResult.weatherData && (
                  <Alert className='border-green-500/30 bg-green-500/10'>
                    <div className='flex items-center space-x-2'>
                      <span className='text-lg'>
                        {getWeatherIcon(
                          apiKeyValidationResult.weatherData.icon
                        )}
                      </span>
                      <AlertDescription className='text-sm text-green-300'>
                        Currently{" "}
                        {formatTemperature(
                          apiKeyValidationResult.weatherData.temperature,
                          temperatureUnit
                        )}{" "}
                        and{" "}
                        {capitalizeWords(
                          apiKeyValidationResult.weatherData.description
                        )}{" "}
                        in {apiKeyValidationResult.weatherData.cityName}
                        {apiKeyValidationResult.weatherData.countryCode &&
                          `, ${apiKeyValidationResult.weatherData.countryCode}`}
                        . Wow.
                      </AlertDescription>
                    </div>
                  </Alert>
                )}

              <p className='text-xs text-muted-foreground'>
                Get your free API key from{" "}
                <a
                  href='https://openweathermap.org/api'
                  target='_blank'
                  rel='noopener noreferrer'
                  className='text-primary hover:text-primary/80 inline-flex items-center'
                >
                  OpenWeatherMap <ExternalLink className='w-3 h-3 ml-1' />
                </a>
              </p>
            </div>

            <Separator />

            {/* Location Configuration */}
            <div className='space-y-4'>
              <div className='flex items-center space-x-2'>
                <MapPin className='w-4 h-4 text-blue-400' />
                <Label className='text-sm font-medium'>
                  Location Coordinates
                </Label>
              </div>

              <div className='grid grid-cols-2 gap-4'>
                <div className='space-y-2'>
                  <NumberInput
                    id='latitude'
                    label='Latitude (-90 to 90)'
                    step={0.000001}
                    min={-90}
                    max={90}
                    value={latitude || 0}
                    onChange={(value) => {
                      if (value >= -90 && value <= 90) {
                        setLatitude(value)
                        setLatError(null)
                      } else {
                        setLatError("Latitude must be between -90 and 90")
                      }
                    }}
                    placeholder='e.g., 40.7128'
                    className='bg-background/50 border-borderColor/50 focus:border-primary/50'
                    allowFloat={true}
                  />
                  {latError && (
                    <p className='text-xs text-red-400 mt-1'>{latError}</p>
                  )}
                </div>

                <div className='space-y-2'>
                  <NumberInput
                    id='longitude'
                    label='Longitude (-180 to 180)'
                    step={0.000001}
                    min={-180}
                    max={180}
                    value={longitude || 0}
                    onChange={(value) => {
                      if (value >= -180 && value <= 180) {
                        setLongitude(value)
                        setLngError(null)
                      } else {
                        setLngError("Longitude must be between -180 and 180")
                      }
                    }}
                    placeholder='e.g., -74.0060'
                    className='bg-background/50 border-borderColor/50 focus:border-primary/50'
                    allowFloat={true}
                  />
                  {lngError && (
                    <p className='text-xs text-red-400 mt-1'>{lngError}</p>
                  )}
                </div>
              </div>

              <div className='flex items-center justify-between'>
                <p className='text-xs text-muted-foreground'>
                  Use a service like{" "}
                  <a
                    href='https://www.latlong.net/'
                    target='_blank'
                    rel='noopener noreferrer'
                    className='text-primary hover:text-primary/80 inline-flex items-center'
                  >
                    latlong.net <ExternalLink className='w-3 h-3 ml-1' />
                  </a>{" "}
                  to find your coordinates
                </p>
                {locationComplete && (
                  <Badge
                    variant='outline'
                    className='text-xs text-green-300 border-green-500/30'
                  >
                    <Check className='w-3 h-3 mr-1' />
                    Location Set
                  </Badge>
                )}
              </div>
            </div>

            <Separator />

            {/* Weather Data Collection */}
            <div className='space-y-4'>
              <div className='flex items-center justify-between'>
                <div className='space-y-1'>
                  <Label className='text-sm font-medium'>
                    Weather Data Recording
                  </Label>
                  <p className='text-xs text-muted-foreground'>
                    Fetch weather data hourly and cache it in the database. When
                    enabled, timelapses will include the current hour's weather
                    conditions with each captured image.
                  </p>
                </div>
                <div className='flex items-center space-x-2'>
                  <Switch
                    checked={weatherRecordData}
                    onCheckedChange={setWeatherRecordData}
                    disabled={!hasApiKey || !locationComplete}
                  />
                  {weatherRecordData && hasApiKey && locationComplete && (
                    <Button
                      size='sm'
                      variant='outline'
                      onClick={handleRefreshWeather}
                      disabled={isRefreshingWeather}
                      className='ml-2'
                    >
                      {isRefreshingWeather ? (
                        <>
                          <Loader2 className='w-4 h-4 mr-2 animate-spin' />
                          Refreshing...
                        </>
                      ) : (
                        <>
                          <RefreshCw className='w-4 h-4 mr-2' />
                          Set Now
                        </>
                      )}
                    </Button>
                  )}
                </div>
              </div>

              {weatherRecordData && (!hasApiKey || !locationComplete) && (
                <Alert>
                  <AlertDescription className='text-xs'>
                    Weather data recording requires a valid API key and location
                    coordinates.
                  </AlertDescription>
                </Alert>
              )}

              {refreshError && (
                <Alert className='border-red-500/30 bg-red-500/10'>
                  <AlertCircle className='w-4 h-4 text-red-500' />
                  <AlertDescription className='text-xs text-red-400'>
                    {refreshError}
                  </AlertDescription>
                </Alert>
              )}

              {/* Cached Weather Data Display */}
              {weatherDateFetched && (
                <div className='mt-3 p-3 rounded-md bg-muted/30 border border-muted/50'>
                  <div className='flex items-center justify-between mb-2'>
                    <span className='text-xs text-muted-foreground'>
                      Last Updated:{" "}
                      {new Date(weatherDateFetched).toLocaleString()}
                    </span>
                    {currentWeatherIcon && (
                      <span className='text-lg'>
                        {getWeatherIcon(currentWeatherIcon)}
                      </span>
                    )}
                  </div>
                  {currentTemp !== null && currentWeatherDescription && (
                    <div className='text-sm'>
                      <span className='font-medium'>
                        {formatTemperature(currentTemp, temperatureUnit)}
                      </span>
                      <span className='text-muted-foreground ml-2'>
                        {capitalizeWords(currentWeatherDescription)}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>

            <Separator />

            {/* Temperature Unit */}
            <div className='space-y-4'>
              <div className='space-y-3'>
                <Label className='text-sm font-medium'>Temperature Unit</Label>
                <p className='text-xs text-muted-foreground'>
                  Choose how temperatures are displayed throughout the
                  application
                </p>
                <RadioGroup
                  value={temperatureUnit}
                  onValueChange={(value) =>
                    setTemperatureUnit(value as "celsius" | "fahrenheit")
                  }
                  className='flex space-x-6'
                >
                  <div className='flex items-center space-x-2'>
                    <RadioGroupItem value='celsius' id='celsius' />
                    <Label htmlFor='celsius' className='text-sm cursor-pointer'>
                      Celsius (°C)
                    </Label>
                  </div>
                  <div className='flex items-center space-x-2'>
                    <RadioGroupItem value='fahrenheit' id='fahrenheit' />
                    <Label
                      htmlFor='fahrenheit'
                      className='text-sm cursor-pointer'
                    >
                      Fahrenheit (°F)
                    </Label>
                  </div>
                </RadioGroup>
              </div>
            </div>

            <Separator />

            {/* Sunrise/Sunset Time Windows */}
            <div className='space-y-4'>
              <div className='flex items-center justify-between'>
                <div className='space-y-1'>
                  <Label className='text-sm font-medium'>
                    Sunrise/Sunset Time Windows
                  </Label>
                  <p className='text-xs text-muted-foreground'>
                    Fetch sunrise and sunset times hourly for use in timelapse
                    time windows. Times are calculated based on your location
                    and updated daily.
                  </p>
                </div>
                <Switch
                  checked={sunriseSunsetEnabled}
                  onCheckedChange={setSunriseSunsetEnabled}
                  disabled={!hasApiKey || !locationComplete}
                />
              </div>

              {sunriseSunsetEnabled && (!hasApiKey || !locationComplete) && (
                <Alert>
                  <AlertDescription className='text-xs'>
                    Sunrise/sunset time windows require a valid API key and
                    location coordinates.
                  </AlertDescription>
                </Alert>
              )}

              {/* Cached Sunrise/Sunset Times Display */}
              {sunriseSunsetEnabled &&
                (sunriseTimestamp || sunsetTimestamp) && (
                  <div className='mt-3 p-3 rounded-md bg-muted/30 border border-muted/50'>
                    <div className='grid grid-cols-2 gap-4 text-sm'>
                      {sunriseTimestamp && (
                        <div>
                          <span className='text-xs text-muted-foreground block mb-1'>
                            Sunrise
                          </span>
                          <span className='font-medium'>
                            {new Date(sunriseTimestamp).toLocaleTimeString([], {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </div>
                      )}
                      {sunsetTimestamp && (
                        <div>
                          <span className='text-xs text-muted-foreground block mb-1'>
                            Sunset
                          </span>
                          <span className='font-medium'>
                            {new Date(sunsetTimestamp).toLocaleTimeString([], {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
