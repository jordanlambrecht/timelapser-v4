"use client"

import {
  ComponentPropsWithoutRef,
  ComponentRef,
  forwardRef,
  useId,
} from "react"
import * as SwitchPrimitives from "@radix-ui/react-switch"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"
import { Label } from "@/components/ui/label"

const switchVariants = cva(
  "peer shrink-0 cursor-pointer border-2 shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
  {
    variants: {
      variant: {
        basic: "inline-flex h-6 w-10 items-center rounded-lg",
        labeled:
          "absolute inset-0 h-[inherit] w-auto rounded-md [&_span]:z-10 [&_span]:h-full [&_span]:w-1/2 [&_span]:rounded-sm [&_span]:transition-transform [&_span]:duration-300 [&_span]:ease-[cubic-bezier(0.16,1,0.3,1)] [&_span]:data-[state=checked]:translate-x-full [&_span]:data-[state=checked]:rtl:-translate-x-full",
      },
      colorTheme: {
        pink: "border-pink data-[state=checked]:bg-pink data-[state=unchecked]:bg-input data-[state=unchecked]:bg-purple-muted/25 data-[state=unchecked]:border-purple-muted/25",
        yellow:
          "border-yellow data-[state=checked]:bg-yellow data-[state=unchecked]:bg-input data-[state=unchecked]:bg-purple-muted/25 data-[state=unchecked]:border-purple-muted/25",
        cyan: "border-cyan data-[state=checked]:bg-cyan data-[state=unchecked]:bg-input data-[state=unchecked]:bg-purple-muted/25 data-[state=unchecked]:border-purple-muted/25",
      },
    },
    defaultVariants: {
      variant: "basic",
      colorTheme: "pink",
    },
  }
)

const wrapperVariants = cva("", {
  variants: {
    variant: {
      basic: "",
      labeled:
        "relative inline-grid h-9 grid-cols-[1fr_1fr] items-center text-sm font-medium",
    },
  },
})

const thumbVariants = cva(
  "pointer-events-none block bg-background shadow-lg ring-0 transition-transform border-0 duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
  {
    variants: {
      variant: {
        basic:
          "h-5 w-5 rounded-md data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0",
        labeled:
          "h-full w-1/2 rounded-sm data-[state=checked]:translate-x-full data-[state=unchecked]:translate-x-0",
      },
    },
  }
)

interface BaseSwitchProps {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  className?: string
  id?: string
  disabled?: boolean
  colorTheme?: "pink" | "yellow" | "cyan"
}

type BasicSwitchProps = BaseSwitchProps & {
  variant?: "basic"
  trueLabel?: never
  falseLabel?: never
}

type LabeledSwitchProps = BaseSwitchProps & {
  variant: "labeled"
  trueLabel?: string
  falseLabel?: string
}

type SuperSwitchProps = (BasicSwitchProps | LabeledSwitchProps) &
  Omit<
    ComponentPropsWithoutRef<typeof SwitchPrimitives.Root>,
    "checked" | "onCheckedChange"
  >

const SuperSwitch = forwardRef<
  ComponentRef<typeof SwitchPrimitives.Root>,
  SuperSwitchProps
>(
  (
    {
      variant = "basic",
      colorTheme = "pink",
      className,
      id: providedId,
      trueLabel,
      falseLabel,
      ...props
    },
    ref
  ) => {
    const generatedId = useId()
    const id = providedId || generatedId

    const renderSwitch = () => (
      <SwitchPrimitives.Root
        ref={ref}
        id={id}
        className={cn(switchVariants({ variant, colorTheme }), className)}
        {...props}
      >
        <SwitchPrimitives.Thumb className={thumbVariants({ variant })} />
      </SwitchPrimitives.Root>
    )

    if (variant === "labeled") {
      const labelTrue = trueLabel || "on"
      const labelFalse = falseLabel || "off"

      return (
        <div>
          <div className={wrapperVariants({ variant })}>
            {renderSwitch()}
            <span className='pointer-events-none relative ms-0.5 flex items-center justify-center px-2 text-center transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] peer-data-[state=checked]:invisible peer-data-[state=unchecked]:translate-x-full peer-data-[state=unchecked]:rtl:-translate-x-full'>
              <span className='text-[10px] font-medium uppercase'>
                {labelFalse}
              </span>
            </span>
            <span className='peer-data-[state=checked]:text-background pointer-events-none relative me-0.5 flex items-center justify-center px-2 text-center transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] peer-data-[state=checked]:-translate-x-full peer-data-[state=unchecked]:invisible peer-data-[state=checked]:rtl:translate-x-full'>
              <span className='text-[10px] font-medium uppercase'>
                {labelTrue}
              </span>
            </span>
          </div>
          <Label htmlFor={id} className='sr-only'>
            Switch
          </Label>
        </div>
      )
    }

    return renderSwitch()
  }
)

SuperSwitch.displayName = "SuperSwitch"

// Legacy Switch export for backward compatibility
const Switch = forwardRef<
  ComponentRef<typeof SwitchPrimitives.Root>,
  Omit<BaseSwitchProps, "variant"> &
    ComponentPropsWithoutRef<typeof SwitchPrimitives.Root>
>(
  (
    { className, checked, onCheckedChange, id, disabled, colorTheme, ...props },
    ref
  ) => (
    <SuperSwitch
      variant='basic'
      checked={checked}
      onCheckedChange={onCheckedChange}
      className={className}
      id={id}
      disabled={disabled}
      colorTheme={colorTheme}
      ref={ref}
      {...props}
    />
  )
)

Switch.displayName = SwitchPrimitives.Root.displayName

export { SuperSwitch, Switch, type SuperSwitchProps }
