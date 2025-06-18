// src/components/ui/animated-gradient-button.tsx
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { type ComponentProps } from "react"

type AnimatedGradientButtonProps = ComponentProps<typeof Button>

export const AnimatedGradientButton = ({
  ...props
}: AnimatedGradientButtonProps) => {
  return (
    <div className='relative group rounded-xl inline-block p-[1.3px] overflow-hidden'>
      <span className='absolute inset-[-1000%] animate-[spin_3s_linear_infinite] bg-[conic-gradient(from_90deg_at_50%_50%,#8B5CF6_0%,#06B6D4_25%,#EC4899_50%,#8B5CF6_75%,#06B6D4_100%)] group-hover:animate-none' />
      <Button
        {...props}
        className={cn(
          "backdrop-blur-2xl rounded-xl bg-black/90 text-white font-medium group-hover:scale-100 relative",
          props.className
        )}
      />
    </div>
  )
}
