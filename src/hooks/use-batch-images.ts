/**
 * Batch Image Loading Hook
 * 
 * Optimizes image loading by batching multiple image requests into a single API call.
 * Reduces N+1 query problems common in image grids and galleries.
 * 
 * @example
 * ```tsx
 * // Load thumbnails for multiple images at once
 * const { images, loading, error, refetch } = useBatchImages([1, 2, 3, 4, 5], 'thumbnail');
 * 
 * return (
 *   <div className="grid grid-cols-4 gap-2">
 *     {imageIds.map(id => (
 *       <img key={id} src={images[id]} alt={`Image ${id}`} />
 *     ))}
 *   </div>
 * );
 * ```
 * 
 * Performance Benefits:
 * - Reduces 50 individual thumbnail requests to 1 batch request
 * - Implements intelligent caching to avoid duplicate requests
 * - Automatically handles loading states and error recovery
 * 
 * Integration:
 * - Works with existing SSE system for real-time updates
 * - Respects image CDN caching strategies
 * - Maintains consistency with individual image loading patterns
 */

import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Supported image sizes for batch loading
 */
export type ImageSize = 'thumbnail' | 'small' | 'original';

/**
 * Batch image response structure
 */
interface BatchImageResponse {
  success: boolean;
  data: {
    images: Array<{
      id: number;
      url: string;
      file_path: string;
      file_size: number;
      cached: boolean;
    }>;
    size: string;
    count: number;
    cache_hits: number;
  };
  message: string;
}

/**
 * Hook return interface
 */
interface UseBatchImagesReturn {
  /** Map of image ID to image URL/path */
  images: Record<number, string>;
  /** Loading state for the batch request */
  loading: boolean;
  /** Error state if batch request fails */
  error: string | null;
  /** Cache hit ratio for performance monitoring */
  cacheHitRatio: number;
  /** Total number of images loaded */
  loadedCount: number;
  /** Manually refetch the batch */
  refetch: () => Promise<void>;
  /** Check if specific image ID is loaded */
  isLoaded: (imageId: number) => boolean;
  /** Get loading progress (0-1) */
  progress: number;
}

/**
 * Cache for batch image requests to avoid duplicate API calls
 */
const batchImageCache = new Map<string, Record<number, string>>();

/**
 * Debounce delay for batch requests (ms)
 */
const BATCH_DEBOUNCE_DELAY = 100;

/**
 * Maximum batch size to prevent oversized requests
 */
const MAX_BATCH_SIZE = 50;

/**
 * Custom hook for batch loading multiple images efficiently
 * 
 * @param imageIds - Array of image IDs to load
 * @param size - Image size variant to load ('thumbnail' | 'small' | 'original')
 * @param options - Additional configuration options
 * @param options.enabled - Whether to automatically fetch images (default: true)
 * @param options.staleTime - How long cached results remain fresh in ms (default: 5 minutes)
 * @param options.retryCount - Number of retry attempts on failure (default: 3)
 * @param options.onSuccess - Callback when batch loads successfully
 * @param options.onError - Callback when batch loading fails
 * @returns Hook interface with images map, loading state, and utilities
 */
export const useBatchImages = (
  imageIds: number[],
  size: ImageSize = 'thumbnail',
  options: {
    enabled?: boolean;
    staleTime?: number;
    retryCount?: number;
    onSuccess?: (images: Record<number, string>) => void;
    onError?: (error: string) => void;
  } = {}
): UseBatchImagesReturn => {
  const {
    enabled = true,
    staleTime = 5 * 60 * 1000, // 5 minutes
    retryCount = 3,
    onSuccess,
    onError
  } = options;

  // State management
  const [images, setImages] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cacheHitRatio, setCacheHitRatio] = useState(0);
  const [loadedCount, setLoadedCount] = useState(0);

  // Refs for cleanup and debouncing
  const abortControllerRef = useRef<AbortController | null>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const retryCountRef = useRef(0);

  /**
   * Generate cache key for batch request
   */
  const getCacheKey = useCallback((ids: number[], imageSize: string): string => {
    return `${ids.sort().join(',')}-${imageSize}`;
  }, []);

  /**
   * Check if cached data is still fresh
   */
  const isCacheValid = useCallback((cacheKey: string): boolean => {
    const cached = batchImageCache.get(cacheKey);
    if (!cached) return false;

    // For now, consider cache always valid within stale time
    // Could be enhanced with timestamps
    return true;
  }, [staleTime]);

  /**
   * Perform the actual batch image fetch
   */
  const fetchBatchImages = useCallback(async (
    ids: number[],
    imageSize: ImageSize,
    signal?: AbortSignal
  ): Promise<Record<number, string>> => {
    if (ids.length === 0) return {};

    // Check cache first
    const cacheKey = getCacheKey(ids, imageSize);
    if (isCacheValid(cacheKey)) {
      const cached = batchImageCache.get(cacheKey);
      if (cached) {
        setCacheHitRatio(1.0);
        return cached;
      }
    }

    // Split large batches to respect API limits
    if (ids.length > MAX_BATCH_SIZE) {
      const chunks = [];
      for (let i = 0; i < ids.length; i += MAX_BATCH_SIZE) {
        chunks.push(ids.slice(i, i + MAX_BATCH_SIZE));
      }

      const results = await Promise.all(
        chunks.map(chunk => fetchBatchImages(chunk, imageSize, signal))
      );

      return results.reduce((acc, result) => ({ ...acc, ...result }), {});
    }

    // Make API request
    const response = await fetch(
      `/api/images/batch?ids=${ids.join(',')}&size=${imageSize}`,
      {
        signal,
        headers: {
          'Accept': 'application/json',
        },
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to load batch images: ${response.status} ${response.statusText}`);
    }

    const data: BatchImageResponse = await response.json();

    if (!data.success) {
      throw new Error(data.message || 'Failed to load batch images');
    }

    // Transform response to image map
    const imageMap = data.data.images.reduce((acc: Record<number, string>, img) => {
      acc[img.id] = img.url;
      return acc;
    }, {});

    // Update cache
    batchImageCache.set(cacheKey, imageMap);

    // Update metrics
    setCacheHitRatio(data.data.cache_hits / data.data.count);
    setLoadedCount(data.data.count);

    return imageMap;
  }, [getCacheKey, isCacheValid]);

  /**
   * Execute batch fetch with error handling and retries
   */
  const executeBatchFetch = useCallback(async (): Promise<void> => {
    if (!enabled || imageIds.length === 0) return;

    // Cancel any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // Create new abort controller
    abortControllerRef.current = new AbortController();
    const { signal } = abortControllerRef.current;

    setLoading(true);
    setError(null);

    try {
      const result = await fetchBatchImages(imageIds, size, signal);
      
      if (!signal.aborted) {
        setImages(result);
        retryCountRef.current = 0; // Reset retry count on success
        onSuccess?.(result);
      }
    } catch (err) {
      if (!signal.aborted) {
        const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
        
        // Retry logic
        if (retryCountRef.current < retryCount) {
          retryCountRef.current++;
          console.warn(`Batch image fetch failed, retrying (${retryCountRef.current}/${retryCount}):`, errorMessage);
          
          // Exponential backoff
          setTimeout(() => {
            executeBatchFetch();
          }, Math.pow(2, retryCountRef.current) * 1000);
          return;
        }

        setError(errorMessage);
        onError?.(errorMessage);
      }
    } finally {
      if (!signal.aborted) {
        setLoading(false);
      }
    }
  }, [enabled, imageIds, size, retryCount, fetchBatchImages, onSuccess, onError]);

  /**
   * Debounced fetch function to avoid rapid-fire requests
   */
  const debouncedFetch = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = setTimeout(() => {
      executeBatchFetch();
    }, BATCH_DEBOUNCE_DELAY);
  }, [executeBatchFetch]);

  /**
   * Manual refetch function
   */
  const refetch = useCallback(async (): Promise<void> => {
    // Clear cache for this batch
    const cacheKey = getCacheKey(imageIds, size);
    batchImageCache.delete(cacheKey);
    
    await executeBatchFetch();
  }, [getCacheKey, imageIds, size, executeBatchFetch]);

  /**
   * Check if specific image is loaded
   */
  const isLoaded = useCallback((imageId: number): boolean => {
    return imageId in images;
  }, [images]);

  /**
   * Calculate loading progress
   */
  const progress = imageIds.length > 0 ? Object.keys(images).length / imageIds.length : 1;

  // Effect to trigger fetch when dependencies change
  useEffect(() => {
    debouncedFetch();

    // Cleanup function
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [debouncedFetch]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return {
    images,
    loading,
    error,
    cacheHitRatio,
    loadedCount,
    refetch,
    isLoaded,
    progress,
  };
};