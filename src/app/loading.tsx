"use client"

const LoadingSpinner = ({}) => {
  // TODO: PASS LOADING MESSAGE DYNAMICLY
  return (
    <div className='flex items-center justify-center min-h-[60vh]'>
      <div className='space-y-6 text-center'>
        <div className='relative'>
          <div className='w-16 h-16 mx-auto border-4 rounded-full border-pink/20 border-t-pink animate-spin' />
          <div
            className='absolute inset-0 w-16 h-16 mx-auto border-4 rounded-full border-cyan/20 border-b-cyan animate-spin'
            style={{
              animationDirection: "reverse",
              animationDuration: "1.5s",
            }}
          />
        </div>
        <div>
          <p className='font-medium text-white'>Loading dashboard...</p>
          <p className='mt-1 text-sm text-grey-light/60'>
            Fetching camera data
          </p>
        </div>
      </div>
      )
    </div>
  )
}
export default LoadingSpinner
