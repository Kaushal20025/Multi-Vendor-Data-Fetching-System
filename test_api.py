#!/usr/bin/env python3
"""
Simple API Test Script
Tests all endpoints of the Multi-Vendor Data Fetch Service
"""

import requests
import json
import time
from typing import Dict, Any


def test_health_endpoint(base_url: str) -> bool:
    """Test the health endpoint"""
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Health check passed")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False


def test_create_job(base_url: str) -> str:
    """Test job creation and return the request_id"""
    try:
        payload = {
            "user_id": 12345,
            "query": "test_query",
            "metadata": {
                "source": "test_script",
                "timestamp": time.time()
            }
        }
        
        response = requests.post(f"{base_url}/jobs", json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            request_id = result.get("request_id")
            print(f"✅ Job created successfully: {request_id}")
            return request_id
        else:
            print(f"❌ Job creation failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Job creation error: {e}")
        return None


def test_get_job_status(base_url: str, request_id: str) -> bool:
    """Test getting job status"""
    try:
        response = requests.get(f"{base_url}/jobs/{request_id}", timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            status = result.get("status")
            print(f"✅ Job status retrieved: {status}")
            
            # If job is complete, show the result
            if status == "complete" and result.get("result"):
                print(f"   Result: {json.dumps(result['result'], indent=2)}")
            
            return True
        else:
            print(f"❌ Get job status failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Get job status error: {e}")
        return False


def test_webhook_endpoint(base_url: str) -> bool:
    """Test the webhook endpoint"""
    try:
        webhook_payload = {
            "job_id": "test-webhook-job",
            "data": {
                "result": "test_result",
                "processed_at": time.time()
            }
        }
        
        response = requests.post(f"{base_url}/vendor-webhook/test", json=webhook_payload, timeout=5)
        
        if response.status_code == 200:
            print("✅ Webhook endpoint test passed")
            return True
        else:
            print(f"❌ Webhook endpoint test failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Webhook endpoint error: {e}")
        return False


def test_complete_workflow(base_url: str) -> bool:
    """Test the complete workflow: create job -> wait -> check status"""
    print("\n🔄 Testing complete workflow...")
    
    # Create job
    request_id = test_create_job(base_url)
    if not request_id:
        return False
    
    # Wait a bit for processing
    print("⏳ Waiting for job processing...")
    time.sleep(3)
    
    # Check status multiple times
    for i in range(5):
        print(f"📊 Checking job status (attempt {i+1}/5)...")
        if test_get_job_status(base_url, request_id):
            result = requests.get(f"{base_url}/jobs/{request_id}", timeout=5).json()
            if result.get("status") in ["complete", "failed"]:
                print(f"✅ Job finished with status: {result['status']}")
                return True
        
        if i < 4:  # Don't sleep after the last attempt
            time.sleep(2)
    
    print("⚠️  Job did not complete within expected time")
    return False


def main():
    """Main test function"""
    base_url = "http://localhost:8000"
    
    print("🧪 Multi-Vendor Data Fetch Service - API Tests")
    print("=" * 50)
    
    # Test health endpoint
    if not test_health_endpoint(base_url):
        print("❌ Health check failed, stopping tests")
        return
    
    # Test webhook endpoint
    test_webhook_endpoint(base_url)
    
    # Test complete workflow
    test_complete_workflow(base_url)
    
    print("\n🎉 API tests completed!")


if __name__ == "__main__":
    main() 