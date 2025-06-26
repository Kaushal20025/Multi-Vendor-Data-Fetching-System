import os
from typing import Optional, Dict, Any
from datetime import datetime
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from shared.models import JobStatus, JobStatusResponse


class DatabaseManager:
    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None
        self.jobs_collection: Optional[Collection] = None
    
    def connect(self):
        """Connect to MongoDB"""
        mongodb_uri = os.getenv("MONGODB_URI", "mongodb://admin:password@localhost:27017/")
        self.client = MongoClient(mongodb_uri)
        self.db = self.client.get_database("multivendor_service")
        self.jobs_collection = self.db.get_collection("jobs")
        
        # Create indexes
        self.jobs_collection.create_index("request_id", unique=True)
        self.jobs_collection.create_index("status")
        self.jobs_collection.create_index("created_at")
    
    def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
    
    def create_job(self, request_id: str, payload: Dict[str, Any]) -> bool:
        """Create a new job in the database"""
        try:
            now = datetime.utcnow()
            job_doc = {
                "request_id": request_id,
                "payload": payload,
                "status": JobStatus.PENDING,
                "created_at": now,
                "updated_at": now,
                "result": None,
                "error": None
            }
            self.jobs_collection.insert_one(job_doc)
            return True
        except Exception as e:
            print(f"Error creating job: {e}")
            return False
    
    def get_job(self, request_id: str) -> Optional[JobStatusResponse]:
        """Get job status and result by request_id"""
        try:
            job_doc = self.jobs_collection.find_one({"request_id": request_id})
            if not job_doc:
                return None
            
            return JobStatusResponse(
                status=JobStatus(job_doc["status"]),
                result=job_doc.get("result"),
                error=job_doc.get("error"),
                created_at=job_doc["created_at"],
                updated_at=job_doc["updated_at"]
            )
        except Exception as e:
            print(f"Error getting job: {e}")
            return None
    
    def update_job_status(self, request_id: str, status: JobStatus, 
                         result: Optional[Dict[str, Any]] = None, 
                         error: Optional[str] = None) -> bool:
        """Update job status and optionally result/error"""
        try:
            update_data = {
                "status": status,
                "updated_at": datetime.utcnow()
            }
            
            if result is not None:
                update_data["result"] = result
            
            if error is not None:
                update_data["error"] = error
            
            result = self.jobs_collection.update_one(
                {"request_id": request_id},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"Error updating job status: {e}")
            return False


# Global database manager instance
db_manager = DatabaseManager() 