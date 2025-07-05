"use client"

import { forwardRef, useState } from "react"
import { EyeIcon, EyeOffIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input, type InputProps } from "@/components/ui/input"
import { cn } from "@/lib/utils"

export interface PasswordInputProps extends InputProps {
  showPassword?: boolean
  onTogglePassword?: () => void
}

const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(
  ({ className, showPassword: externalShowPassword, onTogglePassword, ...props }, ref) => {
    const [internalShowPassword, setInternalShowPassword] = useState(false)
    
    // Use external control if provided, otherwise use internal state
    const showPassword = externalShowPassword !== undefined ? externalShowPassword : internalShowPassword
    const togglePassword = onTogglePassword || (() => setInternalShowPassword((prev) => !prev))
    
    // Only disable the toggle button if the component itself is disabled, not if empty
    const disabled = props.disabled

    return (
      <div className='relative'>
        <Input
          type={showPassword ? "text" : "password"}
          className={cn("hide-password-toggle pr-10", className)}
          ref={ref}
          {...props}
        />
        <Button
          type='button'
          variant='ghost'
          size='sm'
          className='absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent z-10'
          onClick={togglePassword}
          disabled={disabled}
          aria-label={showPassword ? "Hide password" : "Show password"}
        >
          {showPassword ? (
            <EyeOffIcon className='h-4 w-4' aria-hidden='true' />
          ) : (
            <EyeIcon className='h-4 w-4' aria-hidden='true' />
          )}
          <span className='sr-only'>
            {showPassword ? "Hide password" : "Show password"}
          </span>
        </Button>

        {/* hides browsers password toggles */}
        <style>{`
					.hide-password-toggle::-ms-reveal,
					.hide-password-toggle::-ms-clear {
						visibility: hidden;
						pointer-events: none;
						display: none;
					}
				`}</style>
      </div>
    )
  }
)
PasswordInput.displayName = "PasswordInput"

export { PasswordInput }
