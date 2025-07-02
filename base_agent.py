from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio
import json
import logging

from app.storage import storage

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all agents in the multi-agent system"""
    
    def __init__(self, name: str, ai_service):
        self.name = name
        self.ai_service = ai_service
        self.logger = logging.getLogger(f"agent.{name}")
    
    @abstractmethod
    async def process(self, document: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Process a document and return results"""
        pass
    
    def log_event(self, document: Dict[str, Any], event_type: str, status: str, 
                  message: Optional[str] = None, details: Optional[Dict] = None,
                  processing_time: Optional[float] = None):
        """Log a processing event to storage and notify assigned users"""
        try:
            event_data = {
                "agent_name": self.name,
                "event_type": event_type,
                "status": status,
                "message": message,
                "details": details,
                "processing_time": processing_time
            }
            
            storage.create_event(document["id"], event_data)
            self.logger.info(f"Event logged: {event_type} - {status}")
            
            # Notify assigned users (except agent itself)
            for assignment in storage.get_assignments(document["id"]):
                user_id = assignment.get("user_id")
                if user_id and user_id != self.name:
                    storage.add_notification(user_id, {
                        "type": "event",
                        "document_id": document["id"],
                        "event_type": event_type,
                        "agent_name": self.name,
                        "message": message,
                        "created_at": event_data.get("created_at", None)
                    })
        except Exception as e:
            self.logger.error(f"Failed to log event: {e}")
    
    def update_document_status(self, document: Dict[str, Any], status: str, **kwargs):
        """Update document status and metadata"""
        try:
            updates = {
                "status": status,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Add additional fields if provided
            for key, value in kwargs.items():
                updates[key] = value
            
            storage.update_document(document["id"], updates)
            self.logger.info(f"Document {document['id']} status updated to: {status}")
        except Exception as e:
            self.logger.error(f"Failed to update document status: {e}")
    
    async def execute_with_timing(self, func, *args, **kwargs):
        """Execute a function and measure its execution time"""
        start_time = datetime.utcnow()
        try:
            result = await func(*args, **kwargs)
            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()
            return result, processing_time
        except Exception as e:
            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()
            raise e
    
    def validate_input(self, document: Dict[str, Any]) -> bool:
        """Validate that the document is in the expected state for this agent"""
        return True  # Override in subclasses if needed 