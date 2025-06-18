"use client"

import * as React from "react"
import { ChevronDownIcon, ChevronUpIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"

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
}

const NumberInput = React.forwardRef<HTMLInputElement, NumberInputProps>(
  ({
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
    ...props
  }, ref) => {
    const [internalValue, setInternalValue] = React.useState(defaultValue)
    const [displayValue, setDisplayValue] = React.useState("")
    const [isFocused, setIsFocused] = React.useState(false)
    
    const isControlled = controlledValue !== undefined
    const value = isControlled ? controlledValue : internalValue
    
    const formatNumber = React.useCallback((num: number) => {
      if (formatOptions) {
        return new Intl.NumberFormat(undefined, formatOptions).format(num)
      }
      return num.toString()
    }, [formatOptions])
    
    React.useEffect(() => {
      if (!isFocused) {
        setDisplayValue(formatNumber(value))
      }
    }, [value, formatNumber, isFocused])
    
    const updateValue = React.useCallback((newValue: number) => {
      const clampedValue = Math.min(Math.max(newValue, min ?? -Infinity), max ?? Infinity)
      
      if (isControlled) {
        onChange?.(clampedValue)
      } else {
        setInternalValue(clampedValue)
      }
    }, [min, max, isControlled, onChange])
    
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
      const numValue = parseFloat(inputValue.replace(/[^\d.-]/g, ''))
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
        {label && (
          <Label htmlFor={id} className="text-sm font-medium">
            {label}
          </Label>
        )}
        <div className="relative inline-flex h-9 w-full items-center overflow-hidden rounded-md border border-input bg-background text-sm shadow-sm transition-colors focus-within:ring-1 focus-within:ring-ring">
          <Input
            ref={ref}
            id={id}
            type="text"
            value={displayValue}
            onChange={handleInputChange}
            onFocus={handleInputFocus}
            onBlur={handleInputBlur}
            placeholder={placeholder}
            disabled={disabled}
            className="flex-1 border-0 bg-transparent px-3 py-2 tabular-nums shadow-none focus-visible:ring-0"
            {...props}
          />
          <div className="flex h-full flex-col border-l border-input">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={increment}
              disabled={disabled || !canIncrement}
              className="h-1/2 w-6 rounded-none border-0 p-0 hover:bg-accent hover:text-foreground"
            >
              <ChevronUpIcon size={12} aria-hidden="true" />
              <span className="sr-only">Increment</span>
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={decrement}
              disabled={disabled || !canDecrement}
              className="h-1/2 w-6 rounded-none border-0 border-t border-input p-0 hover:bg-accent hover:text-foreground"
            >
              <ChevronDownIcon size={12} aria-hidden="true" />
              <span className="sr-only">Decrement</span>
            </Button>
          </div>
        </div>
      </div>
    )
  }
)

NumberInput.displayName = "NumberInput"

export { NumberInput }
