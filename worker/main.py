import os
import time
import asyncio
import httpx
from typing import Optional
from shared.database import db_manager
from shared.queue import QueueManager
from shared.models import JobStatus, VendorRequest, clean_vendor_data


class RateLimiter:
    """Simple rate limiter for vendor calls"""
    
    def __init__(self, calls_per_second: int = 10):
        self.calls_per_second = calls_per_second
        self.last_call_time = 0
        self.min_interval = 1.0 / calls_per_second
    
    def wait_if_needed(self):
        """Wait if we need to respect rate limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_call_time
        
        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_call_time = time.time()


class VendorClient:
    """Client for calling vendor APIs"""
    
    def __init__(self):
        self.sync_url = os.getenv("VENDOR_SYNC_URL", "http://localhost:8001")
        self.async_url = os.getenv("VENDOR_ASYNC_URL", "http://localhost:8002")
        self.api_url = os.getenv("API_URL", "http://localhost:8000")
        self.sync_rate_limiter = RateLimiter(calls_per_second=5)  # 5 calls per second
        self.async_rate_limiter = RateLimiter(calls_per_second=3)  # 3 calls per second
    
    async def call_sync_vendor(self, vendor_request: VendorRequest) -> Optional[dict]:
        """Call synchronous vendor"""
        try:
            self.sync_rate_limiter.wait_if_needed()
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.sync_url}/process",
                    json={
                        "job_id": vendor_request.job_id,
                        "payload": vendor_request.payload
                    }
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Sync vendor error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            print(f"Error calling sync vendor: {e}")
            return None
    
    async def call_async_vendor(self, vendor_request: VendorRequest) -> bool:
        """Call asynchronous vendor"""
        try:
            self.async_rate_limiter.wait_if_needed()
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.async_url}/process",
                    json={
                        "job_id": vendor_request.job_id,
                        "payload": vendor_request.payload,
                        "webhook_url": f"{self.api_url}/vendor-webhook/async"
                    }
                )
                
                if response.status_code == 200:
                    return True
                else:
                    print(f"Async vendor error: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            print(f"Error calling async vendor: {e}")
            return False


class Worker:
    """Main worker class"""
    
    def __init__(self):
        self.db_manager = db_manager
        self.queue_manager = QueueManager()
        self.vendor_client = VendorClient()
        self.running = False
    
    def start(self):
        """Start the worker"""
        print("Starting worker...")
        self.db_manager.connect()
        self.queue_manager.connect()
        self.running = True
        
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            print("Worker stopped by user")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the worker"""
        print("Stopping worker...")
        self.running = False
        self.db_manager.disconnect()
        self.queue_manager.disconnect()
    
    async def run(self):
        """Main worker loop"""
        print("Worker started, waiting for jobs...")
        
        while self.running:
            try:
                # Get job from queue
                vendor_request = self.queue_manager.dequeue_job(timeout_ms=1000)
                
                if vendor_request:
                    await self.process_job(vendor_request)
                else:
                    # No jobs available, small delay
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                print(f"Error in worker loop: {e}")
                await asyncio.sleep(1)
    
    async def process_job(self, vendor_request: VendorRequest):
        """Process a single job"""
        try:
            print(f"Processing job: {vendor_request.job_id}")
            
            # Update status to processing
            self.db_manager.update_job_status(
                vendor_request.job_id, 
                JobStatus.PROCESSING
            )
            
            # Determine vendor type (in real app, this would come from queue message)
            # For demo, we'll alternate between sync and async
            vendor_type = "sync" if hash(vendor_request.job_id) % 2 == 0 else "async"
            
            if vendor_type == "sync":
                # Call sync vendor
                result = await self.vendor_client.call_sync_vendor(vendor_request)
                
                if result:
                    # Clean the data
                    cleaned_result = clean_vendor_data(result.get("data", {}))
                    
                    # Update job as complete
                    self.db_manager.update_job_status(
                        vendor_request.job_id,
                        JobStatus.COMPLETE,
                        result=cleaned_result
                    )
                    print(f"Job {vendor_request.job_id} completed successfully")
                else:
                    # Mark as failed
                    self.db_manager.update_job_status(
                        vendor_request.job_id,
                        JobStatus.FAILED,
                        error="Sync vendor call failed"
                    )
                    print(f"Job {vendor_request.job_id} failed")
            
            else:
                # Call async vendor
                success = await self.vendor_client.call_async_vendor(vendor_request)
                
                if success:
                    # Job is now waiting for webhook
                    print(f"Job {vendor_request.job_id} sent to async vendor")
                else:
                    # Mark as failed
                    self.db_manager.update_job_status(
                        vendor_request.job_id,
                        JobStatus.FAILED,
                        error="Async vendor call failed"
                    )
                    print(f"Job {vendor_request.job_id} failed")
                    
        except Exception as e:
            print(f"Error processing job {vendor_request.job_id}: {e}")
            
            # Mark job as failed
            self.db_manager.update_job_status(
                vendor_request.job_id,
                JobStatus.FAILED,
                error=str(e)
            )


def main():
    """Main entry point"""
    worker = Worker()
    worker.start()


if __name__ == "__main__":
    main() 