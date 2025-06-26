import os
import time
import asyncio
import random
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional


class ProcessRequest(BaseModel):
    job_id: str
    payload: Dict[str, Any]
    webhook_url: Optional[str] = None


class VendorMock:
    """Base class for vendor mocks"""
    
    def __init__(self, vendor_type: str):
        self.vendor_type = vendor_type
        self.rate_limit_counter = 0
        self.last_reset_time = time.time()
    
    def check_rate_limit(self, max_calls_per_minute: int = 60) -> bool:
        """Simple rate limiting check"""
        current_time = time.time()
        
        # Reset counter every minute
        if current_time - self.last_reset_time >= 60:
            self.rate_limit_counter = 0
            self.last_reset_time = current_time
        
        if self.rate_limit_counter >= max_calls_per_minute:
            return False
        
        self.rate_limit_counter += 1
        return True
    
    def generate_mock_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mock response data based on payload"""
        # Simulate some processing time
        time.sleep(random.uniform(0.1, 0.5))
        
        # Generate mock data
        mock_data = {
            "vendor_type": self.vendor_type,
            "processed_at": time.time(),
            "input_payload": payload,
            "result": {
                "status": "success",
                "data_points": random.randint(5, 20),
                "confidence_score": round(random.uniform(0.7, 0.99), 3),
                "processing_time_ms": random.randint(100, 500),
                "metadata": {
                    "source": f"{self.vendor_type}_vendor",
                    "version": "1.0.0",
                    "timestamp": time.time()
                }
            }
        }
        
        # Add some sample data that might need cleaning
        if random.random() < 0.3:  # 30% chance to add PII-like data
            mock_data["result"]["user_info"] = {
                "email": "  user@example.com  ",  # Extra whitespace
                "phone": "555-123-4567",
                "name": "  John Doe  "  # Extra whitespace
            }
        
        return mock_data


class SyncVendorMock(VendorMock):
    """Synchronous vendor mock - returns result immediately"""
    
    def __init__(self):
        super().__init__("sync")
    
    def process(self, request: ProcessRequest) -> Dict[str, Any]:
        """Process request synchronously"""
        if not self.check_rate_limit(max_calls_per_minute=100):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        return {
            "success": True,
            "data": self.generate_mock_data(request.payload)
        }


class AsyncVendorMock(VendorMock):
    """Asynchronous vendor mock - accepts request and sends result via webhook"""
    
    def __init__(self):
        super().__init__("async")
    
    def process(self, request: ProcessRequest) -> Dict[str, Any]:
        """Process request asynchronously"""
        if not self.check_rate_limit(max_calls_per_minute=50):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        if not request.webhook_url:
            raise HTTPException(status_code=400, detail="Webhook URL required for async vendor")
        
        # Start async processing
        asyncio.create_task(self._process_async(request))
        
        return {
            "success": True,
            "message": "Request accepted for processing",
            "job_id": request.job_id
        }
    
    async def _process_async(self, request: ProcessRequest):
        """Process request asynchronously and send result via webhook"""
        try:
            # Simulate processing delay (2-5 seconds)
            await asyncio.sleep(random.uniform(2, 5))
            
            # Generate result
            result_data = self.generate_mock_data(request.payload)
            
            # Send result via webhook
            async with httpx.AsyncClient(timeout=30.0) as client:
                webhook_payload = {
                    "job_id": request.job_id,
                    "data": result_data
                }
                
                response = await client.post(request.webhook_url, json=webhook_payload)
                
                if response.status_code == 200:
                    print(f"Async vendor: Successfully sent result for job {request.job_id}")
                else:
                    print(f"Async vendor: Failed to send webhook for job {request.job_id}: {response.status_code}")
                    
        except Exception as e:
            print(f"Async vendor: Error processing job {request.job_id}: {e}")


# Initialize vendor based on environment
vendor_type = os.getenv("VENDOR_TYPE", "sync")
vendor_port = int(os.getenv("VENDOR_PORT", "8001"))

if vendor_type == "sync":
    vendor = SyncVendorMock()
else:
    vendor = AsyncVendorMock()

# Create FastAPI app
app = FastAPI(title=f"{vendor_type.capitalize()} Vendor Mock", version="1.0.0")


@app.post("/process")
async def process_request(request: ProcessRequest):
    """Process a vendor request"""
    try:
        result = vendor.process(request)
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": f"{vendor_type}_vendor",
        "rate_limit_counter": vendor.rate_limit_counter
    }


if __name__ == "__main__":
    import uvicorn
    print(f"Starting {vendor_type} vendor mock on port {vendor_port}")
    uvicorn.run(app, host="0.0.0.0", port=vendor_port) 