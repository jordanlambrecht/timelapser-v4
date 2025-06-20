export interface ImageForCamera {
  id: number
  captured_at: string
  file_path: string
  file_size?: number
  day_number: number
  thumbnail_path?: string
  thumbnail_size?: number
  small_path?: string
  small_size?: number
  // Corruption detection fields
  corruption_score: number
  is_flagged: boolean
  corruption_details?: object
}

export interface ImageFormatDialogsProps {
  imageCaptureType: "PNG" | "JPG"
  onImageCaptureTypeChange: (newType: "PNG" | "JPG") => void
}
