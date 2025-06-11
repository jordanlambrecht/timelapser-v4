#!/bin/bash

# Quick test script to verify the tests API endpoint works

echo "🧪 Testing the Tests API Endpoint"
echo "================================="

# Check if Next.js dev server is running
if ! curl -s http://localhost:3000 > /dev/null; then
    echo "❌ Next.js dev server not running on localhost:3000"
    echo "Please start it with: npm run dev"
    exit 1
fi

echo "✅ Next.js dev server is running"

# Test the API endpoint
echo "📡 Testing /api/tests endpoint..."

# Make request to tests API
response=$(curl -s -w "HTTPSTATUS:%{http_code}" http://localhost:3000/api/tests?type=quick)

# Extract HTTP status code
http_code=$(echo $response | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')

# Extract response body
response_body=$(echo $response | sed -e 's/HTTPSTATUS:.*//g')

echo "HTTP Status: $http_code"

if [ "$http_code" -eq 200 ]; then
    echo "✅ API endpoint is working"
    
    # Try to parse some basic info from response
    if echo "$response_body" | grep -q '"success":true'; then
        echo "✅ Tests executed successfully"
        
        # Extract test counts if available
        total=$(echo "$response_body" | grep -o '"total":[0-9]*' | grep -o '[0-9]*')
        passed=$(echo "$response_body" | grep -o '"passed":[0-9]*' | grep -o '[0-9]*')
        failed=$(echo "$response_body" | grep -o '"failed":[0-9]*' | grep -o '[0-9]*')
        
        if [ ! -z "$total" ]; then
            echo "📊 Test Results: $passed passed, $failed failed, $total total"
        fi
    else
        echo "⚠️  Tests may have encountered issues"
        echo "Response: $response_body" | head -c 200
    fi
else
    echo "❌ API endpoint returned HTTP $http_code"
    echo "Response: $response_body" | head -c 200
fi

echo ""
echo "🌐 Visit http://localhost:3000/tests to see the full test dashboard"
