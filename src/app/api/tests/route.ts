import { NextResponse } from "next/server"
import path from "path"

// Remove dangerous exec import and functionality
// Tests should be run manually or through secure CI/CD pipelines

interface TestResult {
  name: string
  status: "passed" | "failed" | "error"
  category: string
  duration?: number
  error?: string
}

interface TestSummary {
  total: number
  passed: number
  failed: number
  errors: number
  duration: number
  timestamp: string
  results: TestResult[]
}

function parseTestCategory(testName: string): string {
  if (testName.includes("test_database")) return "Database Operations"
  if (testName.includes("test_rtsp_capture")) return "RTSP Capture"
  if (testName.includes("test_time_windows")) return "Time Windows"
  if (testName.includes("test_video_generation")) return "Video Generation"
  return "Other"
}

function parseTestOutput(output: string): TestSummary {
  const lines = output.split("\n")
  const results: TestResult[] = []
  let total = 0
  let passed = 0
  let failed = 0
  let errors = 0
  let duration = 0

  // Parse individual test results
  for (const line of lines) {
    // Match test result lines like "tests/test_database.py::TestDatabase::test_get_active_cameras PASSED"
    const testMatch = line.match(
      /^(tests\/[^:]+::[^:]+::[^\s]+)\s+(PASSED|FAILED|ERROR)(?:\s+\[.*?\])?$/
    )
    if (testMatch) {
      const [, testName, status] = testMatch
      const cleanName = testName
        .replace(/tests\/|\.py::|Test\w+::/g, "")
        .replace(/_/g, " ")

      results.push({
        name: cleanName,
        status: status.toLowerCase() as "passed" | "failed" | "error",
        category: parseTestCategory(testName),
      })

      total++
      if (status === "PASSED") passed++
      else if (status === "FAILED") failed++
      else if (status === "ERROR") errors++
    }
  }

  // Parse summary line like "23 failed, 24 passed in 4.57s"
  const summaryMatch = output.match(
    /(\d+)\s+failed,\s+(\d+)\s+passed.*?in\s+([\d.]+)s/
  )
  if (summaryMatch) {
    failed = parseInt(summaryMatch[1])
    passed = parseInt(summaryMatch[2])
    duration = parseFloat(summaryMatch[3])
    total = passed + failed
  } else {
    // Try alternative summary format "40 passed in 4.57s"
    const altSummaryMatch = output.match(/(\d+)\s+passed.*?in\s+([\d.]+)s/)
    if (altSummaryMatch) {
      passed = parseInt(altSummaryMatch[1])
      duration = parseFloat(altSummaryMatch[2])
      total = passed
      failed = 0
    }
  }

  return {
    total,
    passed,
    failed,
    errors,
    duration,
    timestamp: new Date().toISOString(),
    results,
  }
}

export async function GET(request: Request) {
  // SECURITY: Tests should not be run via web API due to shell injection risks
  // Run tests manually: cd python-worker && ./run-tests.sh

  return NextResponse.json(
    {
      success: false,
      error: "Test execution disabled for security reasons",
      message: "Run tests manually: cd python-worker && ./run-tests.sh",
    },
    { status: 403 }
  )
}

export async function POST(request: Request) {
  // SECURITY: Tests should not be run via web API due to shell injection risks

  return NextResponse.json(
    {
      success: false,
      error: "Test execution disabled for security reasons",
      message: "Run tests manually: cd python-worker && ./run-tests.sh",
    },
    { status: 403 }
  )
}
