"use client"

import { useState, useEffect } from "react"
import { AlertCircle, ImageUp, X, Shield, Clock, CheckCircle, AlertTriangle, Loader2 } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { useFileUpload } from "@/hooks/use-file-upload"
import { toast } from "sonner"

interface CorruptionTestResult {
  corruption_score: number
  fast_score: number
  heavy_score: number | null
  processing_time_ms: number
  action_taken: string
  detection_details: {
    fast_detection: {
      file_size_check: { passed: boolean; reason?: string }
      pixel_statistics: { passed: boolean; reason?: string }
      uniformity_check: { passed: boolean; reason?: string }
      basic_validity: { passed: boolean; reason?: string }
    }
    heavy_detection?: {
      blur_detection: { passed: boolean; reason?: string }
      edge_analysis: { passed: boolean; reason?: string }
      noise_detection: { passed: boolean; reason?: string }
      histogram_analysis: { passed: boolean; reason?: string }
      pattern_detection: { passed: boolean; reason?: string }
    }
  }
  failed_checks: string[]
}

export default function CorruptionTestComponent() {
  const [testResult, setTestResult] = useState<CorruptionTestResult | null>(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  
  const maxSizeMB = 10
  const maxSize = maxSizeMB * 1024 * 1024
  
  const [
    { files, isDragging, errors },
    {
      handleDragEnter,
      handleDragLeave,
      handleDragOver,
      handleDrop,
      openFileDialog,
      removeFile,
      getInputProps,
    },
  ] = useFileUpload({
    accept: "image/*",
    maxSize,
  })
  
  const previewUrl = files[0]?.preview || null

  const analyzeImage = async (file: File) => {
    setIsAnalyzing(true)
    setTestResult(null)
    
    try {
      const formData = new FormData()
      formData.append('image', file)
      
      const response = await fetch('/api/corruption/test-image', {
        method: 'POST',
        body: formData,
      })
      
      if (!response.ok) {
        throw new Error('Failed to analyze image')
      }
      
      const result = await response.json()
      setTestResult(result)
    } catch (error) {
      console.error('Error analyzing image:', error)
      toast.error('Failed to analyze image')
    } finally {
      setIsAnalyzing(false)
    }
  }

  // Watch for file changes
  useEffect(() => {
    if (files.length > 0 && files[0]?.file && !isAnalyzing) {
      analyzeImage(files[0].file)
    }
  }, [files])

  const getScoreColor = (score: number) => {
    if (score >= 90) return "text-green-600"
    if (score >= 70) return "text-blue-600"
    if (score >= 50) return "text-yellow-600"
    if (score >= 30) return "text-orange-600"
    return "text-red-600"
  }

  const getScoreBadgeVariant = (score: number) => {
    if (score >= 70) return "default"
    if (score >= 50) return "secondary"
    return "destructive"
  }

  const clearTest = () => {
    setTestResult(null)
    if (files[0]?.id) {
      removeFile(files[0].id)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center space-x-2">
          <Shield className="h-5 w-5" />
          <CardTitle>Test Corruption Detection</CardTitle>
        </div>
        <p className="text-sm text-muted-foreground">
          Upload test images to see how the corruption detection system analyzes them
        </p>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Upload Area */}
          <div className="space-y-4">
            <div className="relative">
              <div
                role="button"
                onClick={openFileDialog}
                onDragEnter={handleDragEnter}
                onDragLeave={handleDragLeave}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                data-dragging={isDragging || undefined}
                className="border-input hover:bg-accent/50 data-[dragging=true]:bg-accent/50 has-[input:focus]:border-ring has-[input:focus]:ring-ring/50 relative flex min-h-64 flex-col items-center justify-center overflow-hidden rounded-xl border border-dashed p-4 transition-colors has-disabled:pointer-events-none has-disabled:opacity-50 has-[img]:border-none has-[input:focus]:ring-[3px]"
              >
                <input
                  {...getInputProps()}
                  className="sr-only"
                  aria-label="Upload test image"
                />
                {previewUrl ? (
                  <div className="absolute inset-0">
                    <img
                      src={previewUrl}
                      alt={files[0]?.file?.name || "Test image"}
                      className="size-full object-cover"
                    />
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center px-4 py-3 text-center">
                    <div
                      className="bg-background mb-2 flex size-11 shrink-0 items-center justify-center rounded-full border"
                      aria-hidden="true"
                    >
                      <ImageUp className="size-4 opacity-60" />
                    </div>
                    <p className="mb-1.5 text-sm font-medium">
                      Drop your test image here or click to browse
                    </p>
                    <p className="text-muted-foreground text-xs">
                      Max size: {maxSizeMB}MB • Images are analyzed and discarded
                    </p>
                  </div>
                )}
              </div>
              {previewUrl && (
                <div className="absolute top-4 right-4">
                  <button
                    type="button"
                    className="focus-visible:border-ring focus-visible:ring-ring/50 z-50 flex size-8 cursor-pointer items-center justify-center rounded-full bg-black/60 text-white transition-[color,box-shadow] outline-none hover:bg-black/80 focus-visible:ring-[3px]"
                    onClick={clearTest}
                    aria-label="Remove image"
                  >
                    <X className="size-4" aria-hidden="true" />
                  </button>
                </div>
              )}
            </div>
            
            {errors.length > 0 && (
              <div
                className="text-destructive flex items-center gap-1 text-xs"
                role="alert"
              >
                <AlertCircle className="size-3 shrink-0" />
                <span>{errors[0]}</span>
              </div>
            )}
          </div>

          {/* Results Area */}
          <div className="space-y-4">
            {isAnalyzing && (
              <div className="flex items-center justify-center min-h-64 border rounded-lg bg-muted/50">
                <div className="text-center space-y-2">
                  <Loader2 className="h-8 w-8 animate-spin mx-auto text-blue-600" />
                  <p className="text-sm text-muted-foreground">Analyzing image...</p>
                </div>
              </div>
            )}
            
            {testResult && !isAnalyzing && (
              <div className="space-y-4">
                {/* Overall Score */}
                <div className="text-center p-4 border rounded-lg">
                  <div className="space-y-2">
                    <h3 className="font-medium">Corruption Score</h3>
                    <div className={`text-4xl font-bold ${getScoreColor(testResult.corruption_score)}`}>
                      {testResult.corruption_score}/100
                    </div>
                    <div className="flex items-center justify-center space-x-2">
                      <Badge variant={getScoreBadgeVariant(testResult.corruption_score)}>
                        {testResult.action_taken}
                      </Badge>
                      <div className="flex items-center text-xs text-muted-foreground">
                        <Clock className="h-3 w-3 mr-1" />
                        {testResult.processing_time_ms}ms
                      </div>
                    </div>
                  </div>
                </div>

                {/* Detection Breakdown */}
                <div className="space-y-3">
                  <h4 className="font-medium">Detection Breakdown</h4>
                  
                  {/* Fast Detection */}
                  <div className="border rounded-lg p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">Fast Detection</span>
                      <Badge variant="outline">{testResult.fast_score}/100</Badge>
                    </div>
                    <div className="space-y-1">
                      {Object.entries(testResult.detection_details.fast_detection).map(([key, result]) => (
                        <div key={key} className="flex items-center justify-between text-xs">
                          <span className="capitalize">{key.replace('_', ' ')}</span>
                          <div className="flex items-center space-x-1">
                            {result.passed ? (
                              <CheckCircle className="h-3 w-3 text-green-600" />
                            ) : (
                              <AlertTriangle className="h-3 w-3 text-red-600" />
                            )}
                            <span className={result.passed ? "text-green-600" : "text-red-600"}>
                              {result.passed ? "Pass" : "Fail"}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Heavy Detection */}
                  {testResult.detection_details.heavy_detection && (
                    <div className="border rounded-lg p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Heavy Detection</span>
                        <Badge variant="outline">{testResult.heavy_score}/100</Badge>
                      </div>
                      <div className="space-y-1">
                        {Object.entries(testResult.detection_details.heavy_detection).map(([key, result]) => (
                          <div key={key} className="flex items-center justify-between text-xs">
                            <span className="capitalize">{key.replace('_', ' ')}</span>
                            <div className="flex items-center space-x-1">
                              {result.passed ? (
                                <CheckCircle className="h-3 w-3 text-green-600" />
                              ) : (
                                <AlertTriangle className="h-3 w-3 text-red-600" />
                              )}
                              <span className={result.passed ? "text-green-600" : "text-red-600"}>
                                {result.passed ? "Pass" : "Fail"}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Failed Checks */}
                  {testResult.failed_checks.length > 0 && (
                    <div className="border rounded-lg p-3 bg-red-50 border-red-200">
                      <h5 className="text-sm font-medium text-red-800 mb-2">Failed Checks</h5>
                      <div className="space-y-1">
                        {testResult.failed_checks.map((check, index) => (
                          <div key={index} className="flex items-center space-x-2 text-xs text-red-700">
                            <AlertTriangle className="h-3 w-3" />
                            <span>{check}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
            
            {!testResult && !isAnalyzing && (
              <div className="flex items-center justify-center min-h-64 border rounded-lg bg-muted/50">
                <p className="text-muted-foreground">Upload an image to see analysis results</p>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}