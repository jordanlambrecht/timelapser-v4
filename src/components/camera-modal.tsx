import { useState } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Camera, Clock, Wifi, Settings } from "lucide-react"

interface CameraModalProps {
  isOpen: boolean
  onClose: () => void
  onSave: (camera: any) => void
  camera?: any
  title: string
}

export function CameraModal({ isOpen, onClose, onSave, camera, title }: CameraModalProps) {
  const [formData, setFormData] = useState({
    name: camera?.name || '',
    rtsp_url: camera?.rtsp_url || '',
    use_time_window: camera?.use_time_window || false,
    time_window_start: camera?.time_window_start || '06:00',
    time_window_end: camera?.time_window_end || '18:00',
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSave(formData)
    onClose()
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="glass-strong border-purple-muted/50 max-w-lg">
        <DialogHeader className="relative">
          <div className="absolute -top-2 -right-2 w-16 h-16 bg-gradient-to-bl from-pink/10 to-transparent rounded-full" />
          <DialogTitle className="flex items-center space-x-3 text-xl">
            <div className="p-2 bg-gradient-to-br from-cyan/20 to-purple/20 rounded-xl">
              <Camera className="w-6 h-6 text-white" />
            </div>
            <span className="text-white">{title}</span>
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-8 mt-6">
          <div className="space-y-6">
            {/* Camera Name */}
            <div className="space-y-3">
              <Label htmlFor="name" className="text-white font-medium flex items-center space-x-2">
                <Settings className="w-4 h-4 text-cyan/70" />
                <span>Camera Name</span>
              </Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                placeholder="e.g., Front Door Camera"
                className="bg-black/30 border-purple-muted/30 text-white placeholder:text-grey-light/40 focus:border-pink/50 focus:ring-2 focus:ring-pink/20 rounded-xl h-12"
                required
              />
            </div>

            {/* RTSP URL */}
            <div className="space-y-3">
              <Label htmlFor="rtsp_url" className="text-white font-medium flex items-center space-x-2">
                <Wifi className="w-4 h-4 text-purple-light/70" />
                <span>RTSP Stream URL</span>
              </Label>
              <Input
                id="rtsp_url"
                value={formData.rtsp_url}
                onChange={(e) => setFormData(prev => ({ ...prev, rtsp_url: e.target.value }))}
                placeholder="rtsp://192.168.1.100:554/stream"
                className="bg-black/30 border-purple-muted/30 text-white placeholder:text-grey-light/40 focus:border-cyan/50 focus:ring-2 focus:ring-cyan/20 rounded-xl h-12 font-mono text-sm"
                required
              />
              <p className="text-xs text-grey-light/60 mt-2">
                Secure RTSP streams (rtsps://) are supported
              </p>
            </div>

            {/* Time Window Section */}
            <div className="space-y-6 p-6 bg-black/20 rounded-2xl border border-purple-muted/20">
              <div className="flex items-center justify-between">
                <div className="space-y-2">
                  <Label className="text-white font-medium flex items-center space-x-2">
                    <Clock className="w-4 h-4 text-yellow/70" />
                    <span>Time Window</span>
                  </Label>
                  <p className="text-sm text-grey-light/60">
                    Capture only during specific hours (e.g., daylight only)
                  </p>
                </div>
                <Switch
                  checked={formData.use_time_window}
                  onCheckedChange={(checked) => 
                    setFormData(prev => ({ ...prev, use_time_window: checked }))
                  }
                  className="data-[state=checked]:bg-success data-[state=unchecked]:bg-purple-muted/50"
                />
              </div>

              {formData.use_time_window && (
                <div className="grid grid-cols-2 gap-4 mt-4">
                  <div className="space-y-2">
                    <Label htmlFor="time_start" className="text-grey-light/70 text-sm">
                      Start Time
                    </Label>
                    <Input
                      id="time_start"
                      type="time"
                      value={formData.time_window_start}
                      onChange={(e) => setFormData(prev => ({ ...prev, time_window_start: e.target.value }))}
                      className="bg-black/30 border-purple-muted/30 text-white focus:border-success/50 rounded-xl h-10"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="time_end" className="text-grey-light/70 text-sm">
                      End Time
                    </Label>
                    <Input
                      id="time_end"
                      type="time"
                      value={formData.time_window_end}
                      onChange={(e) => setFormData(prev => ({ ...prev, time_window_end: e.target.value }))}
                      className="bg-black/30 border-purple-muted/30 text-white focus:border-success/50 rounded-xl h-10"
                    />
                  </div>
                </div>
              )}

              {formData.use_time_window && (
                <div className="mt-4 p-3 bg-success/10 border border-success/20 rounded-xl">
                  <p className="text-sm text-success/80">
                    ✓ Camera will capture from <span className="font-mono">{formData.time_window_start}</span> to <span className="font-mono">{formData.time_window_end}</span>
                  </p>
                </div>
              )}
            </div>
          </div>

          <DialogFooter className="gap-3 pt-4">
            <Button 
              type="button" 
              variant="outline" 
              onClick={onClose}
              className="border-purple-muted/40 hover:bg-purple-muted/20 text-grey-light hover:text-white px-6"
            >
              Cancel
            </Button>
            <Button 
              type="submit" 
              className="bg-gradient-to-r from-pink to-cyan hover:from-pink-dark hover:to-cyan text-black font-bold px-8 hover:shadow-lg hover:shadow-pink/20 transition-all duration-300"
            >
              {camera ? 'Update' : 'Add'} Camera
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
