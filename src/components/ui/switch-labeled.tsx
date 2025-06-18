"use client"

import { useId } from "react"

import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"

import { cn } from "@/lib/utils"

interface SwitchLabeledProps {
  trueLabel?: string
  falseLabel?: string
  className?: string
  id?: string
  checked: boolean
  onCheckedChange: (checked: boolean) => void
}

const SwitchLabeled = ({
  trueLabel = "on",
  falseLabel = "off",
  checked,
  onCheckedChange,
  className,
  id: providedId,
  ...props
}: SwitchLabeledProps) => {
  const generatedId = useId()
  const id = providedId || generatedId

  return (
    <div>
      <div
        className={cn(
          "relative inline-grid h-9 grid-cols-[1fr_1fr] items-center text-sm font-medium",
          className
        )}
      >
        <Switch
          id={id}
          checked={checked}
          onCheckedChange={onCheckedChange}
          {...props}
          className='peer bg-input data-[state=unchecked]:bg-purple-muted/25 absolute inset-0 h-[inherit] w-auto rounded-md [&_span]:z-10 [&_span]:h-full [&_span]:w-1/2 [&_span]:rounded-sm [&_span]:transition-transform [&_span]:duration-300 [&_span]:ease-[cubic-bezier(0.16,1,0.3,1)] [&_span]:data-[state=checked]:translate-x-full [&_span]:data-[state=checked]:rtl:-translate-x-full border-pink data-[state=unchecked]:border-purple-muted/25'
        />
        <span className='pointer-events-none relative ms-0.5 flex items-center justify-center px-2 text-center transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] peer-data-[state=checked]:invisible peer-data-[state=unchecked]:translate-x-full peer-data-[state=unchecked]:rtl:-translate-x-full'>
          <span className='text-[10px] font-medium uppercase'>
            {falseLabel}
          </span>
        </span>
        <span className='peer-data-[state=checked]:text-background pointer-events-none relative me-0.5 flex items-center justify-center px-2 text-center transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] peer-data-[state=checked]:-translate-x-full peer-data-[state=unchecked]:invisible peer-data-[state=checked]:rtl:translate-x-full'>
          <span className='text-[10px] font-medium uppercase'>{trueLabel}</span>
        </span>
      </div>
      <Label htmlFor={id} className='sr-only'>
        Labeled switch
      </Label>
    </div>
  )
}
export default SwitchLabeled
