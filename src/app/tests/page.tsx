'use client';

import { useState, useEffect } from 'react';

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

interface TestResponse {
  success: boolean;
  summary?: TestSummary;
  rawOutput?: string;
  error?: string;
  details?: string;
}

const StatusIcon = ({ status }: { status: string }) => {
  switch (status) {
    case 'passed':
      return <span className="text-green-500 text-lg">✅</span>;
    case 'failed':
      return <span className="text-red-500 text-lg">❌</span>;
    case 'error':
      return <span className="text-yellow-500 text-lg">⚠️</span>;
    default:
      return <span className="text-gray-500 text-lg">⚪</span>;
  }
};

const StatusBadge = ({ status, count }: { status: string; count: number }) => {
  const colors = {
    passed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    error: 'bg-yellow-100 text-yellow-800',
    total: 'bg-blue-100 text-blue-800'
  };

  return (
    <span className={`px-3 py-1 rounded-full text-sm font-medium ${colors[status as keyof typeof colors] || colors.total}`}>
      {count} {status}
    </span>
  );
};

export default function TestsPage() {
  const [testData, setTestData] = useState<TestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [testType, setTestType] = useState('quick');
  const [showRawOutput, setShowRawOutput] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const runTests = async (type: string = testType) => {
    setLoading(true);
    try {
      const response = await fetch(`/api/tests?type=${type}`);
      const data = await response.json();
      setTestData(data);
    } catch (error) {
      console.error('Failed to run tests:', error);
      setTestData({
        success: false,
        error: 'Failed to run tests',
        details: error instanceof Error ? error.message : 'Unknown error'
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runTests();
  }, []);

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => runTests(), 30000); // Refresh every 30 seconds
      return () => clearInterval(interval);
    }
  }, [autoRefresh, testType]);

  const groupedResults = testData?.summary?.results.reduce((acc, result) => {
    if (!acc[result.category]) {
      acc[result.category] = [];
    }
    acc[result.category].push(result);
    return acc;
  }, {} as Record<string, TestResult[]>) || {};

  const getSuccessRate = (summary: TestSummary) => {
    if (summary.total === 0) return 0;
    return Math.round((summary.passed / summary.total) * 100);
  };

  const getCategoryStats = (tests: TestResult[]) => {
    return {
      passed: tests.filter(t => t.status === 'passed').length,
      failed: tests.filter(t => t.status === 'failed').length,
      error: tests.filter(t => t.status === 'error').length,
      total: tests.length
    };
  };

  return (
    <div className="container mx-auto p-6">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Test Results</h1>
          <p className="text-gray-600 mt-2">Python Worker Test Suite Status</p>
        </div>
        
        <div className="flex gap-4 items-center">
          <select
            value={testType}
            onChange={(e) => setTestType(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="quick">Quick Tests</option>
            <option value="standard">Standard Tests</option>
            <option value="coverage">Coverage Tests</option>
            <option value="verbose">Verbose Tests</option>
          </select>
          
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            <span className="text-sm text-gray-600">Auto-refresh</span>
          </label>
          
          <button
            onClick={() => runTests()}
            disabled={loading}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Running...' : 'Run Tests'}
          </button>
        </div>
      </div>

      {/* Test Summary */}
      {testData?.summary && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex justify-between items-start mb-4">
            <h2 className="text-xl font-semibold text-gray-900">Test Summary</h2>
            <div className="text-sm text-gray-500">
              Last run: {new Date(testData.summary.timestamp).toLocaleString()}
            </div>
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">{testData.summary.total}</div>
              <div className="text-sm text-gray-600">Total Tests</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{testData.summary.passed}</div>
              <div className="text-sm text-gray-600">Passed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">{testData.summary.failed}</div>
              <div className="text-sm text-gray-600">Failed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-600">{testData.summary.duration.toFixed(1)}s</div>
              <div className="text-sm text-gray-600">Duration</div>
            </div>
          </div>
          
          <div className="flex justify-between items-center">
            <div className="flex gap-2">
              <StatusBadge status="passed" count={testData.summary.passed} />
              <StatusBadge status="failed" count={testData.summary.failed} />
              {testData.summary.errors > 0 && (
                <StatusBadge status="error" count={testData.summary.errors} />
              )}
            </div>
            
            <div className="text-right">
              <div className="text-lg font-semibold">
                Success Rate: {getSuccessRate(testData.summary)}%
              </div>
              <div className="w-32 bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${
                    getSuccessRate(testData.summary) >= 80 ? 'bg-green-500' :
                    getSuccessRate(testData.summary) >= 60 ? 'bg-yellow-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${getSuccessRate(testData.summary)}%` }}
                ></div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Test Categories */}
      {Object.entries(groupedResults).map(([category, tests]) => {
        const stats = getCategoryStats(tests);
        const successRate = stats.total > 0 ? Math.round((stats.passed / stats.total) * 100) : 0;
        
        return (
          <div key={category} className="bg-white rounded-lg shadow mb-6">
            <div className="p-4 border-b border-gray-200">
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-semibold text-gray-900">{category}</h3>
                <div className="flex items-center gap-4">
                  <div className="flex gap-2">
                    <StatusBadge status="passed" count={stats.passed} />
                    {stats.failed > 0 && <StatusBadge status="failed" count={stats.failed} />}
                    {stats.error > 0 && <StatusBadge status="error" count={stats.error} />}
                  </div>
                  <div className="text-sm text-gray-600">
                    {successRate}% success
                  </div>
                </div>
              </div>
            </div>
            
            <div className="p-4">
              <div className="grid gap-2">
                {tests.map((test, index) => (
                  <div key={index} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-b-0">
                    <div className="flex items-center gap-3">
                      <StatusIcon status={test.status} />
                      <span className="font-medium text-gray-900">{test.name}</span>
                    </div>
                    <div className="text-sm text-gray-500">
                      {test.duration && `${test.duration}s`}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        );
      })}

      {/* Error Display */}
      {!testData?.success && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-red-800 mb-2">Test Execution Error</h3>
          <p className="text-red-700 mb-4">{testData?.error}</p>
          {testData?.details && (
            <details className="text-sm">
              <summary className="cursor-pointer text-red-600 hover:text-red-800">Show Details</summary>
              <pre className="mt-2 p-3 bg-red-100 rounded text-red-800 overflow-x-auto">
                {testData.details}
              </pre>
            </details>
          )}
        </div>
      )}

      {/* Raw Output Toggle */}
      {testData?.rawOutput && (
        <div className="mt-6">
          <button
            onClick={() => setShowRawOutput(!showRawOutput)}
            className="text-blue-600 hover:text-blue-800 text-sm font-medium"
          >
            {showRawOutput ? 'Hide' : 'Show'} Raw Output
          </button>
          
          {showRawOutput && (
            <div className="mt-4 bg-gray-900 text-green-400 p-4 rounded-lg">
              <pre className="text-xs overflow-x-auto whitespace-pre-wrap">
                {testData.rawOutput}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 flex items-center gap-4">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
            <span>Running {testType} tests...</span>
          </div>
        </div>
      )}
    </div>
  );
}