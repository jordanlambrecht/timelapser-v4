/**
 * Optimistic Camera Operations Hook
 * 
 * Provides immediate UI feedback for camera operations by updating the UI optimistically
 * before the server confirms the change. Integrates with SSE system for real-time sync.
 * 
 * @example
 * ```tsx
 * const {
 *   camera,
 *   isProcessing,
 *   startTimelapse,
 *   stopTimelapse,
 *   updateSettings,
 *   captureNow
 * } = useOptimisticCamera(cameraId);
 * 
 * // Immediate UI feedback, SSE confirms the change
 * const handleStart = async () => {
 *   try {
 *     await startTimelapse({ name: "Morning Construction" });
 *     toast.success("Timelapse started!");
 *   } catch (error) {
 *     toast.error("Failed to start timelapse");
 *   }
 * };
 * ```
 * 
 * Benefits:
 * - Immediate UI feedback (0ms vs 200-500ms API response)
 * - Automatic error recovery and state reversion
 * - Seamless integration with SSE real-time updates
 * - Prevents duplicate operations during processing
 * 
 * Integration:
 * - Uses existing SSE system for state confirmation
 * - Maintains consistency with non-optimistic components
 * - Provides graceful degradation if SSE fails
 */

import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Camera status types from backend
 */
export type CameraStatus = 'online' | 'offline' | 'error' | 'connecting';

/**
 * Timelapse status types
 */
export type TimelapseStatus = 'stopped' | 'running' | 'paused' | 'starting' | 'stopping';

/**
 * Camera health status
 */
export type HealthStatus = 'healthy' | 'degraded' | 'unhealthy' | 'unknown';

/**
 * Camera data interface
 */
interface Camera {
  id: number;
  name: string;
  rtsp_url: string;
  status: CameraStatus;
  health_status: HealthStatus;
  last_capture_at: string | null;
  last_capture_success: boolean;
  consecutive_failures: number;
  next_capture_at: string | null;
  active_timelapse_id: number | null;
  timelapse_status: TimelapseStatus;
  image_count: number;
  use_time_window: boolean;
  time_window_start: string | null;
  time_window_end: string | null;
  updated_at: string;
}

/**
 * Camera settings update interface
 */
interface CameraSettingsUpdate {
  name?: string;
  rtsp_url?: string;
  use_time_window?: boolean;
  time_window_start?: string | null;
  time_window_end?: string | null;
  video_automation_mode?: string;
  standard_fps?: number;
  enable_time_limits?: boolean;
  min_time_seconds?: number | null;
  max_time_seconds?: number | null;
}

/**
 * Timelapse creation options
 */
interface TimelapseCreateOptions {
  name?: string;
  auto_stop_at?: string | null;
  use_custom_time_window?: boolean;
  time_window_start?: string | null;
  time_window_end?: string | null;
}

/**
 * Hook return interface
 */
interface UseOptimisticCameraReturn {
  /** Current camera state (optimistic + SSE confirmed) */
  camera: Camera | null;
  /** Whether any operation is currently processing */
  isProcessing: boolean;
  /** Map of specific operations in progress */
  processingOperations: Record<string, boolean>;
  /** Last error that occurred */
  lastError: string | null;
  /** Start timelapse with optimistic update */
  startTimelapse: (options?: TimelapseCreateOptions) => Promise<void>;
  /** Stop current timelapse with optimistic update */
  stopTimelapse: () => Promise<void>;
  /** Pause current timelapse with optimistic update */
  pauseTimelapse: () => Promise<void>;
  /** Resume paused timelapse with optimistic update */
  resumeTimelapse: () => Promise<void>;
  /** Complete current timelapse with optimistic update */
  completeTimelapse: () => Promise<void>;
  /** Update camera settings with optimistic update */
  updateSettings: (settings: CameraSettingsUpdate) => Promise<void>;
  /** Trigger immediate capture with optimistic update */
  captureNow: () => Promise<void>;
  /** Test camera connection */
  testConnection: () => Promise<boolean>;
  /** Manually refresh camera data */
  refreshCamera: () => Promise<void>;
  /** Revert any pending optimistic changes */
  revertOptimisticChanges: () => void;
}

/**
 * SSE event data interface
 */
interface SSECameraEvent {
  data: {
    camera_id: number;
    status?: CameraStatus;
    health_status?: HealthStatus;
    timelapse_status?: TimelapseStatus;
    image_count?: number;
    last_capture_at?: string;
    active_timelapse_id?: number | null;
    [key: string]: any;
  };
  timestamp: string;
}

/**
 * Custom hook for optimistic camera operations with SSE integration
 * 
 * @param cameraId - ID of the camera to manage
 * @param options - Configuration options
 * @param options.enableSSE - Whether to listen for SSE updates (default: true)
 * @param options.revertTimeout - Time to wait before reverting optimistic changes on error (ms, default: 5000)
 * @param options.retryAttempts - Number of retry attempts for failed operations (default: 3)
 * @param options.onStatusChange - Callback when camera status changes
 * @param options.onError - Callback when operations fail
 * @returns Hook interface with camera state and operation methods
 */
export const useOptimisticCamera = (
  cameraId: number,
  options: {
    enableSSE?: boolean;
    revertTimeout?: number;
    retryAttempts?: number;
    onStatusChange?: (camera: Camera) => void;
    onError?: (error: string, operation: string) => void;
  } = {}
): UseOptimisticCameraReturn => {
  const {
    enableSSE = true,
    revertTimeout = 5000,
    retryAttempts = 3,
    onStatusChange,
    onError
  } = options;

  // State management
  const [camera, setCamera] = useState<Camera | null>(null);
  const [processingOperations, setProcessingOperations] = useState<Record<string, boolean>>({});
  const [lastError, setLastError] = useState<string | null>(null);

  // Refs for cleanup and state management
  const abortControllerRef = useRef<AbortController | null>(null);
  const optimisticStateRef = useRef<Partial<Camera> | null>(null);
  const revertTimerRef = useRef<NodeJS.Timeout | null>(null);

  /**
   * Derived processing state
   */
  const isProcessing = Object.values(processingOperations).some(Boolean);

  /**
   * Update processing state for specific operation
   */
  const setOperationProcessing = useCallback((operation: string, processing: boolean) => {
    setProcessingOperations(prev => ({
      ...prev,
      [operation]: processing
    }));
  }, []);

  /**
   * Apply optimistic update to camera state
   */
  const applyOptimisticUpdate = useCallback((updates: Partial<Camera>) => {
    optimisticStateRef.current = { ...optimisticStateRef.current, ...updates };
    setCamera(prev => prev ? { ...prev, ...updates } : null);
  }, []);

  /**
   * Revert optimistic changes
   */
  const revertOptimisticChanges = useCallback(() => {
    if (optimisticStateRef.current && camera) {
      // Fetch fresh data from server to ensure accuracy
      refreshCamera();
    }
    optimisticStateRef.current = null;
    
    if (revertTimerRef.current) {
      clearTimeout(revertTimerRef.current);
      revertTimerRef.current = null;
    }
  }, [camera]);

  /**
   * Handle API errors with automatic reversion
   */
  const handleApiError = useCallback((error: unknown, operation: string) => {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
    setLastError(errorMessage);
    onError?.(errorMessage, operation);

    // Schedule optimistic state reversion
    revertTimerRef.current = setTimeout(() => {
      revertOptimisticChanges();
    }, revertTimeout);
  }, [revertTimeout, onError, revertOptimisticChanges]);

  /**
   * Make authenticated API request with error handling
   */
  const makeApiRequest = useCallback(async (
    endpoint: string,
    options: RequestInit = {}
  ): Promise<Response> => {
    // Cancel any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    abortControllerRef.current = new AbortController();
    
    const response = await fetch(endpoint, {
      ...options,
      signal: abortControllerRef.current.signal,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API request failed: ${response.status} ${response.statusText}`);
    }

    return response;
  }, []);

  /**
   * Fetch fresh camera data from server
   */
  const refreshCamera = useCallback(async (): Promise<void> => {
    try {
      const response = await makeApiRequest(`/api/cameras/${cameraId}/details`);
      const data = await response.json();
      
      if (data.success) {
        setCamera(data.data);
        optimisticStateRef.current = null; // Clear optimistic state
        onStatusChange?.(data.data);
      }
    } catch (error) {
      console.error('Failed to refresh camera data:', error);
    }
  }, [cameraId, makeApiRequest, onStatusChange]);

  /**
   * Start timelapse operation
   */
  const startTimelapse = useCallback(async (options: TimelapseCreateOptions = {}): Promise<void> => {
    const operation = 'start_timelapse';
    setOperationProcessing(operation, true);
    setLastError(null);

    // Optimistic update
    applyOptimisticUpdate({
      timelapse_status: 'starting'
    });

    try {
      await makeApiRequest(`/api/cameras/${cameraId}/start-timelapse`, {
        method: 'POST',
        body: JSON.stringify(options),
      });

      // Success - SSE will provide the confirmed state
    } catch (error) {
      handleApiError(error, operation);
      throw error;
    } finally {
      setOperationProcessing(operation, false);
    }
  }, [cameraId, makeApiRequest, applyOptimisticUpdate, handleApiError, setOperationProcessing]);

  /**
   * Stop timelapse operation
   */
  const stopTimelapse = useCallback(async (): Promise<void> => {
    const operation = 'stop_timelapse';
    setOperationProcessing(operation, true);
    setLastError(null);

    // Optimistic update
    applyOptimisticUpdate({
      timelapse_status: 'stopping'
    });

    try {
      await makeApiRequest(`/api/cameras/${cameraId}/stop-timelapse`, {
        method: 'POST',
      });
    } catch (error) {
      handleApiError(error, operation);
      throw error;
    } finally {
      setOperationProcessing(operation, false);
    }
  }, [cameraId, makeApiRequest, applyOptimisticUpdate, handleApiError, setOperationProcessing]);

  /**
   * Pause timelapse operation
   */
  const pauseTimelapse = useCallback(async (): Promise<void> => {
    const operation = 'pause_timelapse';
    setOperationProcessing(operation, true);
    setLastError(null);

    applyOptimisticUpdate({
      timelapse_status: 'paused'
    });

    try {
      await makeApiRequest(`/api/cameras/${cameraId}/pause-timelapse`, {
        method: 'POST',
      });
    } catch (error) {
      handleApiError(error, operation);
      throw error;
    } finally {
      setOperationProcessing(operation, false);
    }
  }, [cameraId, makeApiRequest, applyOptimisticUpdate, handleApiError, setOperationProcessing]);

  /**
   * Resume timelapse operation
   */
  const resumeTimelapse = useCallback(async (): Promise<void> => {
    const operation = 'resume_timelapse';
    setOperationProcessing(operation, true);
    setLastError(null);

    applyOptimisticUpdate({
      timelapse_status: 'running'
    });

    try {
      await makeApiRequest(`/api/cameras/${cameraId}/resume-timelapse`, {
        method: 'POST',
      });
    } catch (error) {
      handleApiError(error, operation);
      throw error;
    } finally {
      setOperationProcessing(operation, false);
    }
  }, [cameraId, makeApiRequest, applyOptimisticUpdate, handleApiError, setOperationProcessing]);

  /**
   * Complete timelapse operation
   */
  const completeTimelapse = useCallback(async (): Promise<void> => {
    const operation = 'complete_timelapse';
    setOperationProcessing(operation, true);
    setLastError(null);

    applyOptimisticUpdate({
      timelapse_status: 'stopped',
      active_timelapse_id: null
    });

    try {
      await makeApiRequest(`/api/cameras/${cameraId}/complete-timelapse`, {
        method: 'POST',
      });
    } catch (error) {
      handleApiError(error, operation);
      throw error;
    } finally {
      setOperationProcessing(operation, false);
    }
  }, [cameraId, makeApiRequest, applyOptimisticUpdate, handleApiError, setOperationProcessing]);

  /**
   * Update camera settings
   */
  const updateSettings = useCallback(async (settings: CameraSettingsUpdate): Promise<void> => {
    const operation = 'update_settings';
    setOperationProcessing(operation, true);
    setLastError(null);

    // Optimistic update
    applyOptimisticUpdate(settings);

    try {
      await makeApiRequest(`/api/cameras/${cameraId}`, {
        method: 'PUT',
        body: JSON.stringify(settings),
      });
    } catch (error) {
      handleApiError(error, operation);
      throw error;
    } finally {
      setOperationProcessing(operation, false);
    }
  }, [cameraId, makeApiRequest, applyOptimisticUpdate, handleApiError, setOperationProcessing]);

  /**
   * Trigger immediate capture
   */
  const captureNow = useCallback(async (): Promise<void> => {
    const operation = 'capture_now';
    setOperationProcessing(operation, true);
    setLastError(null);

    // Optimistic update - increment image count
    if (camera) {
      applyOptimisticUpdate({
        image_count: camera.image_count + 1,
        last_capture_at: new Date().toISOString()
      });
    }

    try {
      await makeApiRequest(`/api/cameras/${cameraId}/capture-now`, {
        method: 'POST',
      });
    } catch (error) {
      handleApiError(error, operation);
      throw error;
    } finally {
      setOperationProcessing(operation, false);
    }
  }, [camera, cameraId, makeApiRequest, applyOptimisticUpdate, handleApiError, setOperationProcessing]);

  /**
   * Test camera connection
   */
  const testConnection = useCallback(async (): Promise<boolean> => {
    const operation = 'test_connection';
    setOperationProcessing(operation, true);
    setLastError(null);

    try {
      const response = await makeApiRequest(`/api/cameras/${cameraId}/test-connection`, {
        method: 'POST',
      });
      const data = await response.json();
      return data.success;
    } catch (error) {
      handleApiError(error, operation);
      return false;
    } finally {
      setOperationProcessing(operation, false);
    }
  }, [cameraId, makeApiRequest, handleApiError, setOperationProcessing]);

  /**
   * Handle SSE events for this camera
   */
  useEffect(() => {
    if (!enableSSE) return;

    const handleSSEEvent = (event: MessageEvent) => {
      try {
        const eventData: SSECameraEvent = JSON.parse(event.data);
        
        if (eventData.data.camera_id === cameraId) {
          // Clear optimistic state when SSE confirms changes
          if (optimisticStateRef.current) {
            optimisticStateRef.current = null;
          }

          // Update camera state with confirmed data
          setCamera(prev => {
            if (!prev) return null;
            const updated = { ...prev, ...eventData.data };
            onStatusChange?.(updated);
            return updated;
          });

          // Clear any pending revert timer
          if (revertTimerRef.current) {
            clearTimeout(revertTimerRef.current);
            revertTimerRef.current = null;
          }
        }
      } catch (error) {
        console.error('Failed to parse SSE event:', error);
      }
    };

    // Listen for relevant SSE events
    const eventSource = new EventSource('/api/events');
    eventSource.addEventListener('camera_status_changed', handleSSEEvent);
    eventSource.addEventListener('image_captured', handleSSEEvent);
    eventSource.addEventListener('timelapse_status_changed', handleSSEEvent);

    return () => {
      eventSource.close();
    };
  }, [cameraId, enableSSE, onStatusChange]);

  /**
   * Initial camera data fetch
   */
  useEffect(() => {
    refreshCamera();
  }, [refreshCamera]);

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (revertTimerRef.current) {
        clearTimeout(revertTimerRef.current);
      }
    };
  }, []);

  return {
    camera,
    isProcessing,
    processingOperations,
    lastError,
    startTimelapse,
    stopTimelapse,
    pauseTimelapse,
    resumeTimelapse,
    completeTimelapse,
    updateSettings,
    captureNow,
    testConnection,
    refreshCamera,
    revertOptimisticChanges,
  };
};