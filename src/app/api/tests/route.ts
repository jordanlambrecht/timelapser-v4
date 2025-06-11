import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execAsync = promisify(exec);

interface TestResult {
  name: string;
  status: 'passed' | 'failed' | 'error';
  category: string;
  duration?: number;
  error?: string;
}

interface TestSummary {
  total: number;
  passed: number;
  failed: number;
  errors: number;
  duration: number;
  timestamp: string;
  results: TestResult[];
}

function parseTestCategory(testName: string): string {
  if (testName.includes('test_database')) return 'Database Operations';
  if (testName.includes('test_rtsp_capture')) return 'RTSP Capture';
  if (testName.includes('test_time_windows')) return 'Time Windows';
  if (testName.includes('test_video_generation')) return 'Video Generation';
  return 'Other';
}

function parseTestOutput(output: string): TestSummary {
  const lines = output.split('\n');
  const results: TestResult[] = [];
  let total = 0;
  let passed = 0;
  let failed = 0;
  let errors = 0;
  let duration = 0;

  // Parse individual test results
  for (const line of lines) {
    // Match test result lines like "tests/test_database.py::TestDatabase::test_get_active_cameras PASSED"
    const testMatch = line.match(/^(tests\/[^:]+::[^:]+::[^\s]+)\s+(PASSED|FAILED|ERROR)(?:\s+\[.*?\])?$/);
    if (testMatch) {
      const [, testName, status] = testMatch;
      const cleanName = testName.replace(/tests\/|\.py::|Test\w+::/g, '').replace(/_/g, ' ');
      
      results.push({
        name: cleanName,
        status: status.toLowerCase() as 'passed' | 'failed' | 'error',
        category: parseTestCategory(testName)
      });
      
      total++;
      if (status === 'PASSED') passed++;
      else if (status === 'FAILED') failed++;
      else if (status === 'ERROR') errors++;
    }
  }

  // Parse summary line like "23 failed, 24 passed in 4.57s"
  const summaryMatch = output.match(/(\d+)\s+failed,\s+(\d+)\s+passed.*?in\s+([\d.]+)s/);
  if (summaryMatch) {
    failed = parseInt(summaryMatch[1]);
    passed = parseInt(summaryMatch[2]);
    duration = parseFloat(summaryMatch[3]);
    total = passed + failed;
  } else {
    // Try alternative summary format "40 passed in 4.57s"
    const altSummaryMatch = output.match(/(\d+)\s+passed.*?in\s+([\d.]+)s/);
    if (altSummaryMatch) {
      passed = parseInt(altSummaryMatch[1]);
      duration = parseFloat(altSummaryMatch[2]);
      total = passed;
      failed = 0;
    }
  }

  return {
    total,
    passed,
    failed,
    errors,
    duration,
    timestamp: new Date().toISOString(),
    results
  };
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const testType = searchParams.get('type') || 'quick';
    
    // Path to python-worker directory
    const pythonWorkerDir = path.join(process.cwd(), 'python-worker');
    
    console.log('Running pytest in:', pythonWorkerDir);
    
    // Run pytest command
    const command = `cd "${pythonWorkerDir}" && ./run-tests.sh ${testType}`;
    
    try {
      const { stdout, stderr } = await execAsync(command, {
        timeout: 60000, // 60 second timeout
        maxBuffer: 1024 * 1024 // 1MB buffer
      });
      
      const output = stdout + stderr;
      const summary = parseTestOutput(output);
      
      return NextResponse.json({
        success: true,
        summary,
        rawOutput: output
      });
      
    } catch (execError: any) {
      // pytest returns non-zero exit code when tests fail, but that's not an error for us
      const output = (execError.stdout || '') + (execError.stderr || '');
      
      if (output.includes('collected') && output.includes('failed')) {
        // Tests ran but some failed - this is normal
        const summary = parseTestOutput(output);
        return NextResponse.json({
          success: true,
          summary,
          rawOutput: output
        });
      } else {
        // Actual execution error
        throw execError;
      }
    }
    
  } catch (error: any) {
    console.error('Test execution error:', error);
    
    return NextResponse.json({
      success: false,
      error: error.message,
      details: error.stderr || error.stdout || 'Unknown error occurred'
    }, { status: 500 });
  }
}

export async function POST(request: Request) {
  const { testType = 'quick' } = await request.json();
  
  // Redirect to GET with query parameter
  const url = new URL('/api/tests', request.url);
  url.searchParams.set('type', testType);
  
  return GET(new Request(url.toString()));
}