import { Heart, Coffee } from "lucide-react"
import { Button } from "./ui/button"
import Link from "next/link"

const Footer = () => {
  return (
    <footer className='mt-16 border-t border-purple-muted/20 bg-black/20 backdrop-blur-sm'>
      <div className='mx-auto max-w-7xl px-6 py-8'>
        <div className='flex flex-col items-center justify-center space-y-6'>
          {/* Main footer content */}
          <div className='text-center space-y-2'>
            <div className='flex items-center justify-center space-x-2'>
              <span className='text-grey-light/80'>
                © {new Date().getFullYear()} – Jordy.
              </span>
              <Button
                asChild
                variant={"link"}
                className='text-cyan hover:text-cyan-dark p-0'
              >
                <Link
                  href={"https://github.com/jordanlambrecht/timelapser-v4"}
                  target='_blank'
                >
                  Fork →
                </Link>
              </Button>
            </div>
            <div className='text-sm text-grey-light/60'>
              Licensed under{" "}
              <Button
                asChild
                variant={"link"}
                className='text- hover:text-purple-light p-0 h-auto'
              >
                <Link
                  href={"https://creativecommons.org/licenses/by-nc/4.0/"}
                  target='_blank'
                >
                  CC BY-NC 4.0
                </Link>
              </Button>{" "}
              – Free for personal use, commercial licensing available
            </div>
          </div>

          {/* Support section */}
          <div className='flex flex-col items-center space-y-3'>
            <div className='flex items-center space-x-2 text-grey-light/70'>
              <Heart className='w-4 h-4 text-pink' />
              <span>Dig this app? You can support me by</span>
            </div>
            <Button asChild className='bg-yellow text-blue font-medium'>
              <Link href='https://buymeacoffee.com/jordyjordy' target='_blank'>
                <Coffee className='w-4 h-4 mr-2' />
                Buying Me A Coffee
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </footer>
  )
}

export default Footer
