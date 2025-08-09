/**
 * Virtual Scrolling Hook & Components
 * 
 * Optimizes rendering of large lists by only rendering visible items.
 * Handles thousands of items without performance degradation.
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';

// Types
interface VirtualItem<T> {
  item: T;
  index: number;
  style: React.CSSProperties;
  isVisible: boolean;
}

interface VirtualListOptions {
  itemHeight?: number;
  estimatedItemHeight?: number;
  overscan?: number;
  enableDynamicHeight?: boolean;
}

interface UseVirtualListReturn<T> {
  containerProps: {
    style: React.CSSProperties;
    onScroll: (e: React.UIEvent<HTMLDivElement>) => void;
  };
  innerProps: {
    style: React.CSSProperties;
  };
  virtualItems: VirtualItem<T>[];
  scrollToIndex: (index: number) => void;
  scrollToTop: () => void;
  scrollToBottom: () => void;
}

interface VirtualListProps<T> {
  items: T[];
  renderItem: (props: VirtualItem<T>) => React.ReactNode;
  height?: number | string;
  className?: string;
  itemHeight?: number;
  estimatedItemHeight?: number;
  overscan?: number;
  enableDynamicHeight?: boolean;
  onItemClick?: (item: T, index: number) => void;
  loading?: boolean;
  error?: string;
  emptyMessage?: string;
}

interface VirtualGridProps<T> extends Omit<VirtualListProps<T>, 'itemHeight'> {
  itemWidth: number;
  itemHeight: number;
  columns: number;
  gap?: number;
}

/**
 * Core virtual scrolling hook
 */
export function useVirtualList<T>(
  items: T[],
  options: VirtualListOptions = {}
): UseVirtualListReturn<T> {
  const {
    itemHeight,
    estimatedItemHeight = 50,
    overscan = 5,
    enableDynamicHeight = !itemHeight,
  } = options;

  const [scrollTop, setScrollTop] = useState(0);
  const [containerHeight, setContainerHeight] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const itemHeights = useRef<number[]>([]);

  // Initialize item heights
  useEffect(() => {
    if (enableDynamicHeight) {
      itemHeights.current = new Array(items.length).fill(estimatedItemHeight);
    }
  }, [items.length, estimatedItemHeight, enableDynamicHeight]);

  // Update container height on resize
  useEffect(() => {
    const updateHeight = () => {
      if (containerRef.current) {
        setContainerHeight(containerRef.current.clientHeight);
      }
    };

    updateHeight();
    window.addEventListener('resize', updateHeight);
    return () => window.removeEventListener('resize', updateHeight);
  }, []);

  // Calculate visible range
  const visibleRange = useMemo(() => {
    if (!containerHeight || items.length === 0) {
      return { start: 0, end: 0 };
    }

    const currentItemHeight = itemHeight || estimatedItemHeight;
    const start = Math.max(0, Math.floor(scrollTop / currentItemHeight) - overscan);
    const visibleCount = Math.ceil(containerHeight / currentItemHeight);
    const end = Math.min(items.length, start + visibleCount + overscan * 2);

    return { start, end };
  }, [scrollTop, containerHeight, items.length, itemHeight, estimatedItemHeight, overscan]);

  // Calculate virtual items
  const virtualItems = useMemo(() => {
    const { start, end } = visibleRange;
    const currentItemHeight = itemHeight || estimatedItemHeight;

    return items.slice(start, end).map((item, index) => {
      const actualIndex = start + index;
      const top = actualIndex * currentItemHeight;

      return {
        item,
        index: actualIndex,
        style: {
          position: 'absolute' as const,
          top,
          left: 0,
          right: 0,
          height: currentItemHeight,
        },
        isVisible: true,
      };
    });
  }, [items, visibleRange, itemHeight, estimatedItemHeight]);

  // Total height calculation
  const totalHeight = useMemo(() => {
    const currentItemHeight = itemHeight || estimatedItemHeight;
    return items.length * currentItemHeight;
  }, [items.length, itemHeight, estimatedItemHeight]);

  // Scroll handlers
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  }, []);

  const scrollToIndex = useCallback((index: number) => {
    if (containerRef.current) {
      const currentItemHeight = itemHeight || estimatedItemHeight;
      containerRef.current.scrollTop = index * currentItemHeight;
    }
  }, [itemHeight, estimatedItemHeight]);

  const scrollToTop = useCallback(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = 0;
    }
  }, []);

  const scrollToBottom = useCallback(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, []);

  return {
    containerProps: {
      style: {
        height: '100%',
        overflow: 'auto',
      },
      onScroll: handleScroll,
    },
    innerProps: {
      style: {
        height: totalHeight,
        position: 'relative',
      },
    },
    virtualItems,
    scrollToIndex,
    scrollToTop,
    scrollToBottom,
  };
}

/**
 * Virtual List Component
 */
export function VirtualList<T>({
  items,
  renderItem,
  height = 400,
  className = '',
  itemHeight,
  estimatedItemHeight = 50,
  overscan = 5,
  enableDynamicHeight,
  onItemClick,
  loading = false,
  error,
  emptyMessage = 'No items to display',
}: VirtualListProps<T>) {
  const options = useMemo(() => ({
    itemHeight,
    estimatedItemHeight,
    overscan,
    enableDynamicHeight,
  }), [itemHeight, estimatedItemHeight, overscan, enableDynamicHeight]);

  const {
    containerProps,
    innerProps,
    virtualItems,
  } = useVirtualList(items, options);

  // Handle loading state
  if (loading) {
    return (
      <div 
        className={`flex items-center justify-center ${className}`}
        style={{ height }}
      >
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  // Handle error state
  if (error) {
    return (
      <div 
        className={`flex items-center justify-center ${className}`}
        style={{ height }}
      >
        <div className="text-red-500">Error: {error}</div>
      </div>
    );
  }

  // Handle empty state
  if (items.length === 0) {
    return (
      <div 
        className={`flex items-center justify-center ${className}`}
        style={{ height }}
      >
        <div className="text-gray-500">{emptyMessage}</div>
      </div>
    );
  }

  return (
    <div 
      {...containerProps}
      className={className}
      style={{ ...containerProps.style, height }}
    >
      <div {...innerProps}>
        {virtualItems.map(({ item, index, style, isVisible }) => (
          <div
            key={index}
            style={style}
            data-virtual-item
            data-virtual-index={index}
            onClick={() => onItemClick?.(item, index)}
          >
            {renderItem({ item, index, style, isVisible })}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Virtual Grid Component
 */
export function VirtualGrid<T>({
  items,
  renderItem,
  height = 400,
  className = '',
  itemWidth,
  itemHeight,
  columns,
  gap = 0,
  onItemClick,
  loading = false,
  error,
  emptyMessage = 'No items to display',
}: VirtualGridProps<T>) {
  // Convert grid to list format
  const gridItems = useMemo(() => {
    const rows: (T | null)[][] = [];
    for (let i = 0; i < items.length; i += columns) {
      const row: (T | null)[] = [];
      for (let j = 0; j < columns; j++) {
        row.push(items[i + j] || null);
      }
      rows.push(row);
    }
    return rows;
  }, [items, columns]);

  const rowHeight = itemHeight + gap;

  const renderRow = useCallback(({ item: row, index: rowIndex, style, isVisible }: VirtualItem<(T | null)[]>) => (
    <div style={style} className="flex" data-row={rowIndex}>
      {row.map((item, colIndex) => {
        if (!item) return <div key={colIndex} style={{ width: itemWidth, height: itemHeight }} />;
        
        const itemIndex = rowIndex * columns + colIndex;
        return (
          <div
            key={colIndex}
            style={{ 
              width: itemWidth, 
              height: itemHeight,
              marginRight: colIndex < columns - 1 ? gap : 0
            }}
            onClick={() => onItemClick?.(item, itemIndex)}
          >
            {renderItem({ 
              item, 
              index: itemIndex, 
              style: { width: itemWidth, height: itemHeight }, 
              isVisible 
            })}
          </div>
        );
      })}
    </div>
  ), [columns, itemWidth, itemHeight, gap, onItemClick, renderItem]);

  return (
    <VirtualList
      items={gridItems}
      renderItem={renderRow}
      height={height}
      className={className}
      itemHeight={rowHeight}
      loading={loading}
      error={error}
      emptyMessage={emptyMessage}
    />
  );
}

// Export types
export type { VirtualItem, VirtualListOptions, UseVirtualListReturn, VirtualListProps, VirtualGridProps };