// src/components/camera-modal.tsx
import { useState, useEffect } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  Camera,
  Clock,
  Wifi,
  Settings,
  Shield,
  CheckCircle,
  Circle,
} from "lucide-react"
import { toast } from "@/lib/toast"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import type { CameraModalProps } from "@/types"

export function CameraModal({
  isOpen,
  onClose,
  onSave,
  camera,
  title,
}: CameraModalProps) {
  const [formData, setFormData] = useState({
    name: "",
    rtsp_url: "",
    use_time_window: false,
    time_window_start: "06:00",
    time_window_end: "18:00",
    corruption_detection_heavy: false,
  })
  const [saving, setSaving] = useState(false)

  // Update form data when camera prop changes or modal opens
  useEffect(() => {
    if (isOpen) {
      setFormData({
        name: camera?.name || "",
        rtsp_url: camera?.rtsp_url || "",
        use_time_window: camera?.use_time_window || false,
        time_window_start: camera?.time_window_start || "06:00",
        time_window_end: camera?.time_window_end || "18:00",
        corruption_detection_heavy: camera?.corruption_detection_heavy || false,
      })
      setSaving(false) // Reset saving state when modal opens
    }
  }, [isOpen, camera])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await onSave(formData)
      toast.success("Camera settings saved successfully!")
    } catch (error) {
      toast.error("Failed to save camera settings. Please try again.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className='max-w-lg glass-strong border-purple-muted/50'>
        <DialogHeader className='relative'>
          <div className='absolute w-16 h-16 rounded-full -top-2 -right-2 bg-gradient-to-bl from-pink/10 to-transparent' />
          <DialogTitle className='flex items-center space-x-3 text-xl'>
            <div className='p-2 bg-gradient-to-br from-cyan/20 to-purple/20 rounded-xl'>
              <Camera className='w-6 h-6 text-white' />
            </div>
            <span className='text-white'>{title}</span>
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className='mt-6 space-y-8'>
          <div className='space-y-6'>
            {/* Camera Name */}
            <div className='space-y-3'>
              <Label
                htmlFor='name'
                className='flex items-center space-x-2 font-medium text-white'
              >
                <Settings className='w-4 h-4 text-cyan/70' />
                <span>Camera Name</span>
              </Label>
              <Input
                id='name'
                data-1p-ignore
                value={formData.name}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, name: e.target.value }))
                }
                placeholder='e.g., Front Door Camera'
                className='h-12 text-white bg-black/30 border-purple-muted/30 placeholder:text-grey-light/40 focus:border-pink/50 focus:ring-2 focus:ring-pink/20 rounded-xl'
                required
              />
            </div>

            {/* RTSP URL */}
            <div className='space-y-3'>
              <Label
                htmlFor='rtsp_url'
                className='flex items-center space-x-2 font-medium text-white'
              >
                <Wifi className='w-4 h-4 text-purple-light/70' />
                <span>RTSP Stream URL</span>
              </Label>
              <Input
                id='rtsp_url'
                value={formData.rtsp_url}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, rtsp_url: e.target.value }))
                }
                placeholder='rtsp://192.168.1.100:554/stream'
                className='h-12 font-mono text-sm text-white bg-black/30 border-purple-muted/30 placeholder:text-grey-light/40 focus:border-cyan/50 focus:ring-2 focus:ring-cyan/20 rounded-xl'
                required
              />
              <p className='mt-2 text-xs text-grey-light/60'>
                Secure RTSP streams (rtsps://) are supported
              </p>
            </div>

            {/* Time Window Section */}
            <div className='p-6 space-y-6 border bg-black/20 rounded-2xl border-purple-muted/20'>
              <div className='flex items-center justify-between'>
                <div className='space-y-2'>
                  <Label className='flex items-center space-x-2 font-medium text-white'>
                    <Clock className='w-4 h-4 text-yellow/70' />
                    <span>Time Window</span>
                  </Label>
                  <p className='text-sm text-grey-light/60'>
                    Capture only during specific hours (e.g., daylight only)
                  </p>
                </div>
                <Switch
                  checked={formData.use_time_window}
                  onCheckedChange={(checked) =>
                    setFormData((prev) => ({
                      ...prev,
                      use_time_window: checked,
                    }))
                  }
                  className='data-[state=checked]:bg-success data-[state=unchecked]:bg-purple-muted/50'
                />
              </div>

              {formData.use_time_window && (
                <div className='grid grid-cols-2 gap-4 mt-4'>
                  <div className='space-y-2'>
                    <Label
                      htmlFor='time_start'
                      className='text-sm text-grey-light/70'
                    >
                      Start Time
                    </Label>
                    <Input
                      id='time_start'
                      type='time'
                      value={formData.time_window_start}
                      onChange={(e) =>
                        setFormData((prev) => ({
                          ...prev,
                          time_window_start: e.target.value,
                        }))
                      }
                      className='h-10 text-white bg-black/30 border-purple-muted/30 focus:border-success/50 rounded-xl'
                    />
                  </div>
                  <div className='space-y-2'>
                    <Label
                      htmlFor='time_end'
                      className='text-sm text-grey-light/70'
                    >
                      End Time
                    </Label>
                    <Input
                      id='time_end'
                      type='time'
                      value={formData.time_window_end}
                      onChange={(e) =>
                        setFormData((prev) => ({
                          ...prev,
                          time_window_end: e.target.value,
                        }))
                      }
                      className='h-10 text-white bg-black/30 border-purple-muted/30 focus:border-success/50 rounded-xl'
                    />
                  </div>
                </div>
              )}

              {formData.use_time_window && (
                <div className='p-3 mt-4 border bg-success/10 border-success/20 rounded-xl'>
                  <p className='text-sm text-success/80'>
                    ✓ Camera will capture from{" "}
                    <span className='font-mono'>
                      {formData.time_window_start}
                    </span>{" "}
                    to{" "}
                    <span className='font-mono'>
                      {formData.time_window_end}
                    </span>
                  </p>
                </div>
              )}
            </div>

            {/* Image Quality Detection Section */}
            <div className='p-6 space-y-6 border bg-black/20 rounded-2xl border-purple-muted/20'>
              <div className='flex items-center justify-between'>
                <div className='space-y-2'>
                  <Label className='flex items-center space-x-2 font-medium text-white'>
                    <Shield className='w-4 h-4 text-cyan/70' />
                    <span>Image Quality Detection</span>
                  </Label>
                  <p className='text-sm text-grey-light/60'>
                    Automatically detect and handle corrupted images from this
                    camera
                  </p>
                </div>
                <div className='flex items-center space-x-2'>
                  <span className='text-xs font-medium text-grey-light/60'>
                    {formData.corruption_detection_heavy ? "Advanced" : "Basic"}
                  </span>
                  <Switch
                    checked={formData.corruption_detection_heavy}
                    onCheckedChange={(checked) =>
                      setFormData((prev) => ({
                        ...prev,
                        corruption_detection_heavy: checked,
                      }))
                    }
                    className='data-[state=checked]:bg-cyan data-[state=unchecked]:bg-purple-muted/50'
                  />
                </div>
              </div>

              {/* Detection Methods Explanation */}
              <div className='p-4 border bg-grey-dark/30 border-purple-muted/20 rounded-xl'>
                <div className='text-sm font-medium text-white mb-3'>
                  Detection Methods:
                </div>
                <div className='space-y-2 text-xs'>
                  <div className='flex items-center space-x-2'>
                    <CheckCircle className='h-3 w-3 text-success' />
                    <span className='text-grey-light/80'>
                      Fast heuristics (file size, pixel statistics)
                    </span>
                  </div>
                  <div className='flex items-center space-x-2'>
                    {formData.corruption_detection_heavy ? (
                      <CheckCircle className='h-3 w-3 text-success' />
                    ) : (
                      <Circle className='h-3 w-3 text-grey-light/40' />
                    )}
                    <span
                      className={
                        formData.corruption_detection_heavy
                          ? "text-grey-light/80"
                          : "text-grey-light/40"
                      }
                    >
                      Computer vision (blur, noise, pattern analysis)
                    </span>
                  </div>
                </div>
              </div>

              {/* Performance Impact Indicator */}
              <div className='flex items-center justify-between p-3 bg-purple-muted/10 border border-purple-muted/20 rounded-xl'>
                <div className='flex items-center space-x-2 text-xs text-grey-light/60'>
                  <Clock className='h-3 w-3' />
                  <span>Processing time per capture:</span>
                </div>
                <div className='flex items-center space-x-2'>
                  <span className='text-xs font-medium text-white'>
                    ~{formData.corruption_detection_heavy ? "55" : "5"}ms
                  </span>
                  <div
                    className={`px-2 py-1 rounded text-xs font-medium ${
                      formData.corruption_detection_heavy
                        ? "bg-yellow/20 text-yellow border border-yellow/30"
                        : "bg-success/20 text-success border border-success/30"
                    }`}
                  >
                    {formData.corruption_detection_heavy ? "+50ms" : "+2ms"}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <DialogFooter className='gap-3 pt-4'>
            <Button
              type='button'
              variant='outline'
              onClick={onClose}
              className='px-6 border-purple-muted/40 hover:bg-purple-muted/20 text-grey-light hover:text-white'
            >
              Cancel
            </Button>
            <Button
              type='submit'
              disabled={saving}
              className='px-8 font-bold text-black transition-all duration-300 bg-gradient-to-r from-pink to-cyan hover:from-pink-dark hover:to-cyan hover:shadow-lg hover:shadow-pink/20 disabled:opacity-50 disabled:cursor-not-allowed'
            >
              {saving ? (
                <>
                  <LoadingSpinner
                    size='sm'
                    variant='icon'
                    className='text-black mr-2'
                  />
                  {camera ? "Updating..." : "Adding..."}
                </>
              ) : (
                <>{camera ? "Update" : "Add"} Camera</>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
