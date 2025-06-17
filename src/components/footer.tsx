import { Heart, Coffee } from "lucide-react"
import { Button } from "./ui/button"
import Link from "next/link"
import { link } from "fs"
const Footer = () => {
  return (
    <footer className='h-32'>
      <div className='mx-4 mt-4 px-8 py-10 flex flex-col justify-center align-middle items-center'>
        <div className='text-center'>
          <div>
            © {new Date().getFullYear()} – Jordy.{" "}
            <Button asChild variant={"link"}>
              <Link
                href={"https://github.com/jordanlambrecht/timelapser-v4"}
                target='_blank'
              >
                Fork →
              </Link>
            </Button>
          </div>
          <div className='text-sm text-muted-foreground mt-1'>
            Licensed under{" "}
            <Button asChild variant={"link"} className='p-0 h-auto'>
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
        <div className='flex flex-col'>
          <span>
            <Heart />
            Dig this app? You can support me by
          </span>
          <Button asChild>
            <Link href='https://buymeacoffee.com/jordyjordy' target='_blank'>
              <Coffee /> Buying Me A Coffee
            </Link>
          </Button>
        </div>
      </div>
    </footer>
  )
}

export default Footer
