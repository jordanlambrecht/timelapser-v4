"use client"

import * as React from "react"
import { ChevronDownIcon, ChevronUpIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"

/**
 * Enhanced NumberInput Component
 *
 * A comprehensive number input component with the following features:
 * - Built-in increment/decrement buttons
 * - Integer or float support with toggle
 * - Internal or external label support
 * - Min/max validation with visual feedback
 * - Custom step increments
 * - Number formatting options
 * - Accessibility features (ARIA labels, keyboard navigation)
 *
 * @param value - Controlled value (optional)
 * @param defaultValue - Default value for uncontrolled mode (default: 0)
 * @param onChange - Callback when value changes
 * @param min - Minimum allowed value
 * @param max - Maximum allowed value
 * @param step - Increment/decrement step size (default: 1)
 * @param disabled - Disable the input
 * @param className - Additional CSS classes
 * @param label - Label text (shown unless hideLabel is true)
 * @param placeholder - Placeholder text
 * @param formatOptions - Intl.NumberFormat options for display formatting
 * @param id - HTML id attribute
 * @param hideLabel - Hide internal label to allow external labeling (default: false)
 * @param allowFloat - Allow floating point numbers (default: false for integers only)
 *
 * @example
 * // Basic integer input with internal label
 * <NumberInput
 *   label="Count"
 *   value={count}
 *   onChange={setCount}
 *   min={0}
 *   max={100}
 * />
 *
 * @example
 * // Float input with external label
 * <Label htmlFor="latitude">Latitude</Label>
 * <NumberInput
 *   id="latitude"
 *   value={lat}
 *   onChange={setLat}
 *   min={-90}
 *   max={90}
 *   step={0.000001}
 *   hideLabel={true}
 *   allowFloat={true}
 * />
 */
interface NumberInputProps {
  value?: number
  defaultValue?: number
  onChange?: (value: number) => void
  min?: number
  max?: number
  step?: number
  disabled?: boolean
  className?: string
  label?: string
  placeholder?: string
  formatOptions?: Intl.NumberFormatOptions
  id?: string
  // New props for enhanced functionality
  hideLabel?: boolean // Hide the internal label to allow external labels
  allowFloat?: boolean // Allow floating point numbers (default: false for integers only)
}

const NumberInput = React.forwardRef<HTMLInputElement, NumberInputProps>(
  (
    {
      value: controlledValue,
      defaultValue = 0,
      onChange,
      min,
      max,
      step = 1,
      disabled = false,
      className,
      label,
      placeholder,
      formatOptions,
      id,
      hideLabel = false,
      allowFloat = false,
      ...props
    },
    ref
  ) => {
    const [internalValue, setInternalValue] = React.useState(defaultValue)
    const [displayValue, setDisplayValue] = React.useState("")
    const [isFocused, setIsFocused] = React.useState(false)

    const isControlled = controlledValue !== undefined
    const value = isControlled ? controlledValue : internalValue

    const formatNumber = React.useCallback(
      (num: number) => {
        if (formatOptions) {
          return new Intl.NumberFormat(undefined, formatOptions).format(num)
        }
        return num.toString()
      },
      [formatOptions]
    )

    React.useEffect(() => {
      if (!isFocused) {
        setDisplayValue(formatNumber(value))
      }
    }, [value, formatNumber, isFocused])

    const updateValue = React.useCallback(
      (newValue: number) => {
        // Handle integer vs float based on allowFloat prop
        const processedValue = allowFloat ? newValue : Math.round(newValue)
        const clampedValue = Math.min(
          Math.max(processedValue, min ?? -Infinity),
          max ?? Infinity
        )

        if (isControlled) {
          onChange?.(clampedValue)
        } else {
          setInternalValue(clampedValue)
        }
      },
      [min, max, isControlled, onChange, allowFloat]
    )

    const increment = React.useCallback(() => {
      updateValue(value + step)
    }, [value, step, updateValue])

    const decrement = React.useCallback(() => {
      updateValue(value - step)
    }, [value, step, updateValue])

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const inputValue = e.target.value
      setDisplayValue(inputValue)

      // Parse the number, handling formatted values
      const parseMethod = allowFloat ? parseFloat : parseInt
      const numValue = parseMethod(inputValue.replace(/[^\d.-]/g, ""))
      if (!isNaN(numValue)) {
        updateValue(numValue)
      }
    }

    const handleInputFocus = () => {
      setIsFocused(true)
      setDisplayValue(value.toString())
    }

    const handleInputBlur = () => {
      setIsFocused(false)
      setDisplayValue(formatNumber(value))
    }

    const canIncrement = max === undefined || value < max
    const canDecrement = min === undefined || value > min

    return (
      <div className={cn("space-y-2", className)}>
        {label && !hideLabel && (
          <Label htmlFor={id} className='text-sm font-medium'>
            {label}
          </Label>
        )}
        <div className='relative inline-flex h-9 w-full items-center overflow-hidden rounded-md border border-input bg-background text-sm shadow-sm transition-colors focus-within:ring-1 focus-within:ring-ring'>
          <Input
            ref={ref}
            id={id}
            type='text'
            value={displayValue}
            onChange={handleInputChange}
            onFocus={handleInputFocus}
            onBlur={handleInputBlur}
            placeholder={placeholder}
            disabled={disabled}
            className='flex-1 border-0 bg-transparent px-3 py-2 tabular-nums shadow-none focus-visible:ring-0'
            {...props}
          />
          <div className='flex h-full flex-col border-l border-input'>
            <Button
              type='button'
              variant='ghost'
              size='sm'
              onClick={increment}
              disabled={disabled || !canIncrement}
              className='h-1/2 w-6 rounded-none border-0 p-0 hover:bg-accent hover:text-foreground'
            >
              <ChevronUpIcon size={12} aria-hidden='true' />
              <span className='sr-only'>Increment</span>
            </Button>
            <Button
              type='button'
              variant='ghost'
              size='sm'
              onClick={decrement}
              disabled={disabled || !canDecrement}
              className='h-1/2 w-6 rounded-none border-0 border-t border-input p-0 hover:bg-accent hover:text-foreground'
            >
              <ChevronDownIcon size={12} aria-hidden='true' />
              <span className='sr-only'>Decrement</span>
            </Button>
          </div>
        </div>
      </div>
    )
  }
)

NumberInput.displayName = "NumberInput"

export { NumberInput }
