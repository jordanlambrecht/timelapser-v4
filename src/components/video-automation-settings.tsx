// src/components/video-automation-settings.tsx
'use client';

import { useState, useEffect } from 'react';
import { 
  VideoAutomationMode, 
  CameraAutomationSettings, 
  AutomationScheduleConfig, 
  MilestoneConfig 
} from '@/types/video-automation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Button } from '@/components/ui/button';
import { 
  Clock, 
  Camera, 
  Calendar, 
  Target, 
  Play, 
  Settings, 
  AlertCircle,
  Info,
  Zap
} from 'lucide-react';
import { toast } from '@/lib/toast';

interface VideoAutomationSettingsProps {
  cameraId?: number;
  initialSettings?: CameraAutomationSettings;
  onSettingsChange?: (settings: CameraAutomationSettings) => void;
  disabled?: boolean;
  showTitle?: boolean;
}

const DAYS_OF_WEEK = [
  'monday', 'tuesday', 'wednesday', 'thursday', 
  'friday', 'saturday', 'sunday'
];

const DEFAULT_MILESTONES = [100, 500, 1000, 2500, 5000];

export function VideoAutomationSettings({
  cameraId,
  initialSettings,
  onSettingsChange,
  disabled = false,
  showTitle = true
}: VideoAutomationSettingsProps) {
  const [settings, setSettings] = useState<CameraAutomationSettings>({
    video_automation_mode: VideoAutomationMode.MANUAL,
    automation_schedule: undefined,
    milestone_config: {
      enabled: false,
      thresholds: DEFAULT_MILESTONES,
      reset_on_complete: false
    }
  });

  // Initialize settings from props
  useEffect(() => {
    if (initialSettings) {
      setSettings(initialSettings);
    }
  }, [initialSettings]);

  // Notify parent of changes
  useEffect(() => {
    if (onSettingsChange) {
      onSettingsChange(settings);
    }
  }, [settings, onSettingsChange]);

  const handleModeChange = (mode: VideoAutomationMode) => {
    setSettings(prev => ({
      ...prev,
      video_automation_mode: mode,
      // Clear mode-specific settings when switching modes
      automation_schedule: mode === VideoAutomationMode.SCHEDULED ? prev.automation_schedule : undefined,
      milestone_config: mode === VideoAutomationMode.MILESTONE ? prev.milestone_config : {
        enabled: false,
        thresholds: DEFAULT_MILESTONES,
        reset_on_complete: false
      }
    }));
  };

  const handleScheduleChange = (field: keyof AutomationScheduleConfig, value: string) => {
    setSettings(prev => ({
      ...prev,
      automation_schedule: {
        ...prev.automation_schedule,
        type: prev.automation_schedule?.type || 'daily',
        time: prev.automation_schedule?.time || '18:00',
        [field]: value
      } as AutomationScheduleConfig
    }));
  };

  const handleMilestoneChange = (field: keyof MilestoneConfig, value: any) => {
    setSettings(prev => ({
      ...prev,
      milestone_config: {
        ...prev.milestone_config,
        [field]: value
      } as MilestoneConfig
    }));
  };

  const addMilestone = () => {
    const newThreshold = Math.max(...(settings.milestone_config?.thresholds || [0])) + 500;
    handleMilestoneChange('thresholds', [
      ...(settings.milestone_config?.thresholds || []),
      newThreshold
    ]);
  };

  const removeMilestone = (index: number) => {
    const newThresholds = [...(settings.milestone_config?.thresholds || [])];
    newThresholds.splice(index, 1);
    handleMilestoneChange('thresholds', newThresholds);
  };

  const updateMilestone = (index: number, value: number) => {
    const newThresholds = [...(settings.milestone_config?.thresholds || [])];
    newThresholds[index] = value;
    handleMilestoneChange('thresholds', newThresholds.sort((a, b) => a - b));
  };

  const getModeDescription = (mode: VideoAutomationMode) => {
    switch (mode) {
      case VideoAutomationMode.MANUAL:
        return 'Videos generated only when manually triggered';
      case VideoAutomationMode.PER_CAPTURE:
        return 'Generate video after each image capture (throttled to prevent overload)';
      case VideoAutomationMode.SCHEDULED:
        return 'Generate videos on a time-based schedule (daily/weekly)';
      case VideoAutomationMode.MILESTONE:
        return 'Generate videos when reaching specific image count milestones';
      default:
        return '';
    }
  };

  const getModeIcon = (mode: VideoAutomationMode) => {
    switch (mode) {
      case VideoAutomationMode.MANUAL:
        return <Play className="h-4 w-4" />;
      case VideoAutomationMode.PER_CAPTURE:
        return <Zap className="h-4 w-4" />;
      case VideoAutomationMode.SCHEDULED:
        return <Clock className="h-4 w-4" />;
      case VideoAutomationMode.MILESTONE:
        return <Target className="h-4 w-4" />;
      default:
        return <Settings className="h-4 w-4" />;
    }
  };

  return (
    <Card className={disabled ? 'opacity-50' : ''}>
      {showTitle && (
        <CardHeader>
          <div className="flex items-center space-x-2">
            <Camera className="h-5 w-5" />
            <div>
              <CardTitle>Video Automation</CardTitle>
              <CardDescription>
                Configure automatic video generation for this camera
              </CardDescription>
            </div>
          </div>
        </CardHeader>
      )}
      
      <CardContent className="space-y-6">
        {/* Automation Mode Selection */}
        <div className="space-y-3">
          <Label className="text-sm font-medium">Automation Mode</Label>
          <Select 
            value={settings.video_automation_mode} 
            onValueChange={handleModeChange}
            disabled={disabled}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.values(VideoAutomationMode).map((mode) => (
                <SelectItem key={mode} value={mode}>
                  <div className="flex items-center space-x-2">
                    {getModeIcon(mode)}
                    <span className="capitalize">{mode.replace('_', ' ')}</span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          
          <p className="text-xs text-muted-foreground">
            {getModeDescription(settings.video_automation_mode)}
          </p>
        </div>

        {/* Per-Capture Mode Info */}
        {settings.video_automation_mode === VideoAutomationMode.PER_CAPTURE && (
          <div className="p-3 bg-blue-50 dark:bg-blue-950/20 rounded-lg border border-blue-200 dark:border-blue-800">
            <div className="flex items-start space-x-2">
              <Info className="h-4 w-4 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-medium text-blue-800 dark:text-blue-200">Throttling Active</p>
                <p className="text-blue-700 dark:text-blue-300">
                  Videos will be generated with a minimum 5-minute interval to prevent system overload.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Scheduled Mode Configuration */}
        {settings.video_automation_mode === VideoAutomationMode.SCHEDULED && (
          <div className="space-y-4">
            <Separator />
            <div className="space-y-4">
              <div className="flex items-center space-x-2">
                <Calendar className="h-4 w-4" />
                <Label className="text-sm font-medium">Schedule Configuration</Label>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="schedule-type">Frequency</Label>
                  <Select 
                    value={settings.automation_schedule?.type || 'daily'}
                    onValueChange={(value) => handleScheduleChange('type', value)}
                    disabled={disabled}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="daily">Daily</SelectItem>
                      <SelectItem value="weekly">Weekly</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="schedule-time">Time</Label>
                  <Input
                    id="schedule-time"
                    type="time"
                    value={settings.automation_schedule?.time || '18:00'}
                    onChange={(e) => handleScheduleChange('time', e.target.value)}
                    disabled={disabled}
                  />
                </div>
              </div>

              {settings.automation_schedule?.type === 'weekly' && (
                <div className="space-y-2">
                  <Label htmlFor="schedule-day">Day of Week</Label>
                  <Select 
                    value={settings.automation_schedule?.day || 'sunday'}
                    onValueChange={(value) => handleScheduleChange('day', value)}
                    disabled={disabled}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {DAYS_OF_WEEK.map((day) => (
                        <SelectItem key={day} value={day}>
                          <span className="capitalize">{day}</span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Milestone Mode Configuration */}
        {settings.video_automation_mode === VideoAutomationMode.MILESTONE && (
          <div className="space-y-4">
            <Separator />
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Target className="h-4 w-4" />
                  <Label className="text-sm font-medium">Milestone Configuration</Label>
                </div>
                <Switch
                  checked={settings.milestone_config?.enabled || false}
                  onCheckedChange={(checked) => handleMilestoneChange('enabled', checked)}
                  disabled={disabled}
                />
              </div>

              {settings.milestone_config?.enabled && (
                <>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Label className="text-sm">Image Count Thresholds</Label>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={addMilestone}
                        disabled={disabled}
                      >
                        Add Milestone
                      </Button>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-2">
                      {(settings.milestone_config?.thresholds || []).map((threshold, index) => (
                        <div key={index} className="flex items-center space-x-2">
                          <Input
                            type="number"
                            value={threshold}
                            onChange={(e) => updateMilestone(index, parseInt(e.target.value) || 0)}
                            disabled={disabled}
                            min={1}
                            className="flex-1"
                          />
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => removeMilestone(index)}
                            disabled={disabled || (settings.milestone_config?.thresholds?.length || 0) <= 1}
                          >
                            ×
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Switch
                      checked={settings.milestone_config?.reset_on_complete || false}
                      onCheckedChange={(checked) => handleMilestoneChange('reset_on_complete', checked)}
                      disabled={disabled}
                    />
                    <Label className="text-sm">Reset count after timelapse completion</Label>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* Current Status */}
        <div className="pt-2">
          <div className="flex items-center space-x-2">
            <Badge variant={settings.video_automation_mode === VideoAutomationMode.MANUAL ? 'secondary' : 'default'}>
              {getModeIcon(settings.video_automation_mode)}
              <span className="ml-1 capitalize">
                {settings.video_automation_mode.replace('_', ' ')}
              </span>
            </Badge>
            
            {settings.video_automation_mode !== VideoAutomationMode.MANUAL && (
              <Badge variant="outline">
                Automated
              </Badge>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
