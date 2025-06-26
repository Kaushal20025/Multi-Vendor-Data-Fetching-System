import os
import json
import time
from typing import Optional, Dict, Any
import redis
from shared.models import VendorRequest


class QueueManager:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.stream_name = "job_queue"
        self.group_name = "worker_group"
        self.consumer_name = "worker_1"
    
    def connect(self):
        """Connect to Redis"""
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = redis.from_url(redis_url)
        
        # Create consumer group if it doesn't exist
        try:
            self.redis_client.xgroup_create(self.stream_name, self.group_name, id="0", mkstream=True)
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
    
    def disconnect(self):
        """Disconnect from Redis"""
        if self.redis_client:
            self.redis_client.close()
    
    def enqueue_job(self, request_id: str, payload: Dict[str, Any], vendor_type: str) -> bool:
        """Add a job to the queue"""
        try:
            job_data = {
                "request_id": request_id,
                "payload": json.dumps(payload),
                "vendor_type": vendor_type,
                "timestamp": str(time.time())
            }
            
            self.redis_client.xadd(self.stream_name, job_data)
            return True
        except Exception as e:
            print(f"Error enqueueing job: {e}")
            return False
    
    def dequeue_job(self, timeout_ms: int = 1000) -> Optional[VendorRequest]:
        """Get next job from the queue"""
        try:
            # Read from stream with timeout
            messages = self.redis_client.xreadgroup(
                self.group_name,
                self.consumer_name,
                {self.stream_name: ">"},
                count=1,
                block=timeout_ms
            )
            
            if not messages:
                return None
            
            # Process the first message
            stream, message_list = messages[0]
            if not message_list:
                return None
            
            message_id, data = message_list[0]
            
            # Parse the message data
            vendor_request = VendorRequest(
                job_id=data[b"request_id"].decode(),
                payload=json.loads(data[b"payload"].decode())
            )
            
            # Acknowledge the message
            self.redis_client.xack(self.stream_name, self.group_name, message_id)
            
            return vendor_request
        except Exception as e:
            print(f"Error dequeuing job: {e}")
            return None
    
    def get_queue_length(self) -> int:
        """Get the current queue length"""
        try:
            return self.redis_client.xlen(self.stream_name)
        except Exception as e:
            print(f"Error getting queue length: {e}")
            return 0 