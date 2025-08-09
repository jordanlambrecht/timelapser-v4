// src/components/ui/multi-toggle-group.tsx
"use client"

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { useId } from "react"

import { cn } from "@/lib/utils"
import { Label } from "@/components/ui/label"

/**
 * Option configuration for MultiToggleGroup
 */
export interface MultiToggleGroupOption {
  /** Display label for the option */
  label: string
  /** Unique value identifier for the option */
  value: string
  /** Optional disabled state for individual option */
  disabled?: boolean
}

/**
 * MultiToggleGroup component props interface
 */
export interface MultiToggleGroupProps {
  /** Array of selectable options */
  options: MultiToggleGroupOption[]
  /** Currently selected option values */
  values: string[]
  /** Callback fired when selection changes */
  onValueChange: (values: string[]) => void
  /** Label text for the toggle group (required) */
  label: string
  /** Color theme variant */
  colorTheme?: "pink" | "yellow" | "cyan"
  /** Size variant for padding and spacing */
  size?: "sm" | "md" | "lg"
  /** Layout orientation */
  orientation?: "horizontal" | "vertical"
  /** Use faded border color (color/25) instead of full color */
  borderFaded?: boolean
  /** Remove border entirely */
  borderNone?: boolean
  /** Disabled state for entire component */
  disabled?: boolean
  /** Additional CSS classes */
  className?: string
  /** HTML id attribute */
  id?: string
}

// Container styling variants (reuse from ToggleGroup)
const multiToggleGroupVariants = cva(
  "relative inline-flex rounded-lg shadow-sm transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] w-full",
  {
    variants: {
      colorTheme: {
        pink: "",
        yellow: "",
        cyan: "",
      },
      orientation: {
        horizontal: "flex-row items-center",
        vertical: "flex-col items-stretch min-w-[8rem]",
      },
      borderFaded: {
        true: "",
        false: "",
      },
      borderNone: {
        true: "border-0",
        false: "border-2",
      },
      disabled: {
        true: "opacity-50 cursor-not-allowed",
        false: "cursor-pointer",
      },
    },
    compoundVariants: [
      // Pink variants
      {
        colorTheme: "pink",
        borderFaded: false,
        borderNone: false,
        class: "border-pink focus-within:border-pink",
      },
      {
        colorTheme: "pink",
        borderFaded: true,
        borderNone: false,
        class: "border-pink/25 focus-within:border-pink/25",
      },
      // Yellow variants
      {
        colorTheme: "yellow",
        borderFaded: false,
        borderNone: false,
        class: "border-yellow focus-within:border-yellow",
      },
      {
        colorTheme: "yellow",
        borderFaded: true,
        borderNone: false,
        class: "border-yellow/25 focus-within:border-yellow/25",
      },
      // Cyan variants
      {
        colorTheme: "cyan",
        borderFaded: false,
        borderNone: false,
        class: "border-cyan focus-within:border-cyan",
      },
      {
        colorTheme: "cyan",
        borderFaded: true,
        borderNone: false,
        class: "border-cyan/25 focus-within:border-cyan/25",
      },
    ],
    defaultVariants: {
      colorTheme: "pink",
      orientation: "horizontal",
      borderFaded: false,
      borderNone: false,
      disabled: false,
    },
  }
)

// Background track styling
const backgroundTrackVariants = cva(
  "absolute inset-1 rounded-md transition-colors duration-300",
  {
    variants: {
      colorTheme: {
        pink: "bg-purple-muted/25",
        yellow: "bg-purple-muted/25",
        cyan: "bg-purple-muted/25",
      },
      borderNone: {
        true: "inset-0 border border-purple-muted/25",
        false: "",
      },
    },
    defaultVariants: {
      colorTheme: "pink",
      borderNone: false,
    },
  }
)

// Sliding indicator styling for multiple selections
const indicatorVariants = cva(
  "absolute rounded-sm shadow-lg transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] border border-primary/20",
  {
    variants: {
      colorTheme: {
        pink: "bg-pink",
        yellow: "bg-yellow",
        cyan: "bg-cyan",
      },
      orientation: {
        horizontal: "top-1 bottom-1",
        vertical: "left-1 right-1",
      },
      borderNone: {
        true: "",
        false: "",
      },
    },
    defaultVariants: {
      colorTheme: "pink",
      orientation: "horizontal",
      borderNone: false,
    },
  }
)

// Option button styling
const optionVariants = cva(
  "relative z-10 flex-1 flex items-center justify-center text-sm font-medium transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] outline-none focus:outline-none focus-visible:outline-none rounded-sm whitespace-nowrap overflow-hidden",
  {
    variants: {
      size: {
        sm: "px-3 py-2 min-h-[2rem]",
        md: "px-4 py-2.5 min-h-[2.5rem]",
        lg: "px-5 py-3 min-h-[3rem]",
      },
      selected: {
        true: "text-background font-semibold",
        false: "text-muted-foreground hover:text-foreground",
      },
      disabled: {
        true: "cursor-not-allowed opacity-50",
        false: "cursor-pointer",
      },
    },
    defaultVariants: {
      size: "md",
      selected: false,
      disabled: false,
    },
  }
)

/**
 * MultiToggleGroup - A flexible multi-select toggle component
 *
 * Styled consistently with the ToggleGroup component but supports multiple selections.
 * Shows indicators for all selected options.
 *
 * @example
 * ```tsx
 * const options = [
 *   { label: "Option 1", value: "opt1" },
 *   { label: "Option 2", value: "opt2" },
 *   { label: "Option 3", value: "opt3" }
 * ]
 *
 * <MultiToggleGroup
 *   options={options}
 *   values={selectedValues}
 *   onValueChange={setSelectedValues}
 *   label="Choose options"
 *   colorTheme="cyan"
 *   borderFaded={true}
 * />
 * ```
 */
export const MultiToggleGroup = React.forwardRef<HTMLDivElement, MultiToggleGroupProps>(
  (
    {
      options,
      values,
      onValueChange,
      label,
      colorTheme = "pink",
      size = "md",
      orientation = "horizontal",
      borderFaded = false,
      borderNone = false,
      disabled = false,
      className,
      id: providedId,
    },
    ref
  ) => {
    const generatedId = useId()
    const id = providedId || generatedId
    const groupId = `${id}-group`

    const optionCount = options.length

    // Calculate indicator positions for all selected options
    const getIndicatorStyles = () => {
      return values.map((value) => {
        const selectedIndex = options.findIndex((option) => option.value === value)
        if (selectedIndex < 0) return { display: "none" }
        
        return orientation === "horizontal" ? {
          left: `${(selectedIndex / optionCount) * 100}%`,
          width: `calc(${100 / optionCount}% - 8px)`,
          marginLeft: "4px",
          marginRight: "4px",
        } : {
          top: `${(selectedIndex / optionCount) * 100}%`,
          height: `calc(${100 / optionCount}% - 8px)`,
          marginTop: "4px",
          marginBottom: "4px",
        }
      })
    }

    const handleOptionClick = (
      optionValue: string,
      optionDisabled?: boolean
    ) => {
      if (disabled || optionDisabled) return
      
      const newValues = values.includes(optionValue)
        ? values.filter(v => v !== optionValue)
        : [...values, optionValue]
      
      onValueChange(newValues)
    }

    const handleKeyDown = (
      event: React.KeyboardEvent,
      optionValue: string,
      optionDisabled?: boolean
    ) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault()
        handleOptionClick(optionValue, optionDisabled)
      }
    }

    return (
      <div className='space-y-2'>
        {/* Label */}
        <Label htmlFor={groupId} className='text-sm font-medium'>
          {label}
        </Label>

        {/* Multi Toggle Group Container */}
        <div
          ref={ref}
          id={groupId}
          role='group'
          aria-labelledby={`${id}-label`}
          className={cn(
            multiToggleGroupVariants({
              colorTheme,
              orientation,
              borderFaded,
              borderNone,
              disabled,
            }),
            className
          )}
        >
          {/* Background track */}
          <div
            className={backgroundTrackVariants({ colorTheme, borderNone })}
          />

          {/* Sliding indicators for all selected options */}
          {getIndicatorStyles().map((style, index) => (
            <div
              key={index}
              className={indicatorVariants({ colorTheme, orientation, borderNone })}
              style={style}
              aria-hidden='true'
            />
          ))}

          {/* Options */}
          {options.map((option, index) => {
            const isSelected = values.includes(option.value)
            
            return (
              <button
                key={option.value}
                type='button'
                role='checkbox'
                aria-checked={isSelected}
                aria-disabled={disabled || option.disabled}
                tabIndex={disabled || option.disabled ? -1 : 0}
                className={optionVariants({
                  size,
                  selected: isSelected,
                  disabled: disabled || option.disabled,
                })}
                onClick={() => handleOptionClick(option.value, option.disabled)}
                onKeyDown={(e) => handleKeyDown(e, option.value, option.disabled)}
              >
                <span className='text-ellipsis overflow-hidden px-1'>
                  {option.label}
                </span>
              </button>
            )
          })}
        </div>
      </div>
    )
  }
)

MultiToggleGroup.displayName = "MultiToggleGroup"