#!/usr/bin/env python3
"""
Load Testing Script for Multi-Vendor Data Fetch Service
Uses k6 to simulate 200 concurrent users for 60 seconds
"""

import subprocess
import json
import time
import requests
from typing import List, Dict, Any


def create_k6_script() -> str:
    """Create the k6 test script"""
    return """
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('errors');

export const options = {
  stages: [
    { duration: '10s', target: 50 },   // Ramp up to 50 users
    { duration: '10s', target: 100 },  // Ramp up to 100 users
    { duration: '10s', target: 200 },  // Ramp up to 200 users
    { duration: '30s', target: 200 },  // Stay at 200 users
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'], // 95% of requests should be below 2s
    http_req_failed: ['rate<0.1'],     // Error rate should be below 10%
    errors: ['rate<0.1'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  const payload = {
    data: {
      user_id: Math.floor(Math.random() * 10000),
      query: `test_query_${Math.floor(Math.random() * 1000)}`,
      timestamp: new Date().toISOString(),
      metadata: {
        source: 'load_test',
        iteration: Math.floor(Math.random() * 1000)
      }
    }
  };

  // POST /jobs - Create a new job
  const createResponse = http.post(`${BASE_URL}/jobs`, JSON.stringify(payload), {
    headers: { 'Content-Type': 'application/json' },
  });

  check(createResponse, {
    'create job status is 200': (r) => r.status === 200,
    'create job has request_id': (r) => r.json('request_id') !== undefined,
  });

  if (createResponse.status !== 200) {
    errorRate.add(1);
  }

  // If job creation was successful, get the request_id
  if (createResponse.status === 200) {
    const requestId = createResponse.json('request_id');
    
    // GET /jobs/{request_id} - Check job status
    const statusResponse = http.get(`${BASE_URL}/jobs/${requestId}`);
    
    check(statusResponse, {
      'get job status is 200': (r) => r.status === 200,
      'job status is valid': (r) => ['pending', 'processing', 'complete', 'failed'].includes(r.json('status')),
    });

    if (statusResponse.status !== 200) {
      errorRate.add(1);
    }
  }

  // Random sleep between requests (0.5 to 2 seconds)
  sleep(Math.random() * 1.5 + 0.5);
}
"""


def run_k6_test(script_content: str, duration: int = 60) -> Dict[str, Any]:
    """Run k6 load test and return results"""
    # Write script to temporary file
    script_file = "k6_load_test.js"
    with open(script_file, "w") as f:
        f.write(script_content)
    
    try:
        # Run k6 test
        print("Starting k6 load test...")
        print(f"Duration: {duration} seconds")
        print("Target: 200 concurrent users")
        print("-" * 50)
        
        result = subprocess.run([
            "k6", "run", 
            "--out", "json=load_test_results.json",
            "--out", "influxdb=http://localhost:8086/k6",  # Optional: for detailed metrics
            script_file
        ], capture_output=True, text=True, timeout=duration + 30)
        
        # Parse results
        results = {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
            "success": result.returncode == 0
        }
        
        # Try to read detailed results if available
        try:
            with open("load_test_results.json", "r") as f:
                results["detailed"] = json.load(f)
        except FileNotFoundError:
            results["detailed"] = None
        
        return results
    
    finally:
        # Clean up
        import os
        if os.path.exists(script_file):
            os.remove(script_file)


def analyze_results(results: Dict[str, Any]) -> str:
    """Analyze load test results and provide insights"""
    analysis = []
    analysis.append("=" * 60)
    analysis.append("LOAD TEST ANALYSIS")
    analysis.append("=" * 60)
    
    if not results["success"]:
        analysis.append("❌ Load test failed!")
        analysis.append(f"Error: {results['stderr']}")
        return "\n".join(analysis)
    
    analysis.append("✅ Load test completed successfully!")
    analysis.append("")
    
    # Parse stdout for key metrics
    stdout = results["stdout"]
    
    # Extract key metrics using simple parsing
    lines = stdout.split('\n')
    for line in lines:
        if 'http_req_duration' in line and 'avg=' in line:
            analysis.append(f"📊 Average Response Time: {line.strip()}")
        elif 'http_req_rate' in line and 'avg=' in line:
            analysis.append(f"📈 Request Rate: {line.strip()}")
        elif 'http_req_failed' in line and 'avg=' in line:
            analysis.append(f"❌ Error Rate: {line.strip()}")
        elif 'iterations' in line and 'count=' in line:
            analysis.append(f"🔄 Total Iterations: {line.strip()}")
    
    analysis.append("")
    analysis.append("KEY INSIGHTS:")
    analysis.append("-" * 30)
    
    # Add insights based on results
    if "http_req_failed" in stdout and "avg=0.00" in stdout:
        analysis.append("✅ Excellent error rate - 0% failures")
    elif "http_req_failed" in stdout and "avg=0.0" in stdout:
        analysis.append("✅ Good error rate - very low failures")
    else:
        analysis.append("⚠️  Some errors detected - check system stability")
    
    if "http_req_duration" in stdout and "avg<1000" in stdout:
        analysis.append("✅ Fast response times - under 1 second average")
    elif "http_req_duration" in stdout and "avg<2000" in stdout:
        analysis.append("✅ Acceptable response times - under 2 seconds average")
    else:
        analysis.append("⚠️  Response times could be improved")
    
    analysis.append("")
    analysis.append("RECOMMENDATIONS:")
    analysis.append("-" * 30)
    analysis.append("1. Monitor MongoDB connection pool size")
    analysis.append("2. Consider Redis connection pooling")
    analysis.append("3. Scale worker instances if needed")
    analysis.append("4. Monitor vendor rate limits")
    analysis.append("5. Add circuit breakers for vendor calls")
    
    return "\n".join(analysis)


def test_individual_endpoints() -> str:
    """Test individual endpoints to ensure they work"""
    base_url = "http://localhost:8000"
    results = []
    
    results.append("Testing individual endpoints...")
    results.append("-" * 40)
    
    try:
        # Test health endpoint
        response = requests.get(f"{base_url}/health", timeout=5)
        results.append(f"Health check: {'✅' if response.status_code == 200 else '❌'} ({response.status_code})")
        
        # Test job creation
        payload = {"data": {"test": "value"}}
        response = requests.post(f"{base_url}/jobs", json=payload, timeout=5)
        if response.status_code == 200:
            request_id = response.json().get("request_id")
            results.append(f"Job creation: ✅ ({response.status_code}) - ID: {request_id}")
            
            # Test job status
            response = requests.get(f"{base_url}/jobs/{request_id}", timeout=5)
            results.append(f"Job status: {'✅' if response.status_code == 200 else '❌'} ({response.status_code})")
        else:
            results.append(f"Job creation: ❌ ({response.status_code})")
        
        # Test vendor webhook
        webhook_payload = {
            "job_id": "test-job-id",
            "data": {"result": "test"}
        }
        response = requests.post(f"{base_url}/vendor-webhook/test", json=webhook_payload, timeout=5)
        results.append(f"Webhook: {'✅' if response.status_code == 200 else '❌'} ({response.status_code})")
        
    except Exception as e:
        results.append(f"❌ Error testing endpoints: {e}")
    
    return "\n".join(results)


def main():
    """Main function to run load tests"""
    print("🚀 Multi-Vendor Data Fetch Service - Load Testing")
    print("=" * 60)
    
    # First, test individual endpoints
    endpoint_results = test_individual_endpoints()
    print(endpoint_results)
    print()
    
    # Create and run k6 test
    script = create_k6_script()
    results = run_k6_test(script, duration=60)
    
    # Analyze results
    analysis = analyze_results(results)
    print(analysis)
    
    # Save raw results
    with open("load_test_raw_output.txt", "w") as f:
        f.write("STDOUT:\n")
        f.write(results.get("stdout", ""))
        f.write("\n\nSTDERR:\n")
        f.write(results.get("stderr", ""))
    
    print(f"\n📄 Raw output saved to: load_test_raw_output.txt")
    
    if results["success"]:
        print("\n🎉 Load test completed successfully!")
    else:
        print("\n💥 Load test failed! Check the output above for details.")


if __name__ == "__main__":
    main() 