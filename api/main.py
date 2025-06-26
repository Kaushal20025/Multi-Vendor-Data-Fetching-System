import os
import random
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from shared.models import JobRequest, JobResponse, JobStatusResponse, WebhookRequest
from shared.database import db_manager
from shared.queue import QueueManager
from shared.models import generate_request_id, JobStatus

app = FastAPI(title="Multi-Vendor Data Fetch Service", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize managers
queue_manager = QueueManager()


@app.on_event("startup")
async def startup_event():
    """Initialize database and queue connections"""
    db_manager.connect()
    queue_manager.connect()
    print("API server started and connected to database and queue")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections"""
    db_manager.disconnect()
    queue_manager.disconnect()
    print("API server shutdown")


@app.post("/jobs", response_model=JobResponse)
async def create_job(job_request: JobRequest):
    """
    Create a new job and return a request_id immediately
    """
    try:
        # Generate unique request ID
        request_id = generate_request_id()
        
        # Store job in database
        if not db_manager.create_job(request_id, job_request.payload):
            raise HTTPException(status_code=500, detail="Failed to create job")
        
        # Determine vendor type (randomly for demo, in real app this would be based on payload)
        vendor_type = random.choice(["sync", "async"])
        
        # Add job to queue
        if not queue_manager.enqueue_job(request_id, job_request.payload, vendor_type):
            raise HTTPException(status_code=500, detail="Failed to queue job")
        
        return JobResponse(request_id=request_id)
    
    except Exception as e:
        print(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/jobs/{request_id}", response_model=JobStatusResponse)
async def get_job_status(request_id: str):
    """
    Get job status and result by request_id
    """
    try:
        job = db_manager.get_job(request_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return job
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/vendor-webhook/{vendor}")
async def vendor_webhook(vendor: str, webhook_request: WebhookRequest):
    """
    Webhook endpoint for async vendors to send results
    """
    try:
        # Update job with result
        if not db_manager.update_job_status(
            webhook_request.job_id, 
            JobStatus.COMPLETE, 
            result=webhook_request.data
        ):
            raise HTTPException(status_code=404, detail="Job not found")
        
        return {"status": "success", "message": "Webhook processed successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 