import os
import uuid
from typing import Dict, Any
from datetime import datetime
import mimetypes
from app.agents.base_agent import BaseAgent


class IngestorAgent(BaseAgent):
    """Agent responsible for document ingestion and initial processing with enterprise features"""
    
    def __init__(self, ai_service):
        super().__init__("ingestor", ai_service)
    
    async def process(self, document: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Process document ingestion"""
        try:
            # Log start of processing
            self.log_event(document, "started", "success", "Document ingestion started")
            
            # Validate document
            if not self.validate_input(document):
                raise ValueError("Invalid document for ingestion")
            
            # Gather extra metadata if available
            sender = document.get("sender")
            folder = document.get("folder")
            file_share_event = document.get("file_share_event")
            email_body = document.get("email_body")
            event_type = document.get("event_type", "upload")
            
            # Determine priority based on sender, file size, folder, or event type
            priority = await self._determine_priority(document, sender, folder, event_type)
            
            # Extract basic metadata
            metadata = await self._extract_metadata(document, sender, folder, file_share_event, event_type)
            
            # LLM-powered context extraction for emails
            context_summary = None
            if email_body and self.ai_service and self.ai_service.client:
                context_summary = await self.ai_service.summarize_email_context(email_body)
                metadata["email_context_summary"] = context_summary
                self.logger.info(f"[LLM] Email context summary: {context_summary}")
            
            # Update document with metadata
            self.update_document_status(
                document, 
                "ingested", 
                metadata=metadata,
                priority=priority,
                context_summary=context_summary
            )
            
            # Log completion
            self.log_event(
                document, 
                "completed", 
                "success", 
                f"Document ingested. Priority: {priority}, Event: {event_type}",
                {"priority": priority, "metadata": metadata, "context_summary": context_summary}
            )
            
            return {
                "status": "success",
                "priority": priority,
                "metadata": metadata,
                "context_summary": context_summary,
                "next_agent": "extractor"
            }
            
        except Exception as e:
            self.logger.error(f"Error in ingestor agent: {e}")
            self.log_event(document, "failed", "error", str(e))
            self.update_document_status(document, "failed")
            raise
    
    async def _determine_priority(self, document: Dict[str, Any], sender=None, folder=None, event_type=None) -> str:
        """Determine processing priority based on document characteristics"""
        try:
            if sender and sender.endswith("@vip.com"):
                return "high"
            if folder and "urgent" in folder.lower():
                return "high"
            if document.get("file_size", 0) > 5 * 1024 * 1024:  # > 5MB
                return "low"
            elif document.get("mime_type") in ["application/pdf", "image/jpeg", "image/png"]:
                return "high"
            elif event_type == "email":
                return "medium"
            else:
                return "medium"
        except Exception as e:
            self.logger.warning(f"Error determining priority: {e}")
            return "medium"
    
    async def _extract_metadata(self, document: Dict[str, Any], sender=None, folder=None, file_share_event=None, event_type=None) -> Dict[str, Any]:
        """Extract basic metadata from document"""
        try:
            metadata = {
                "upload_timestamp": datetime.utcnow().isoformat(),
                "file_extension": os.path.splitext(document.get("original_filename", ""))[1],
                "is_image": document.get("mime_type", "").startswith("image/"),
                "is_pdf": document.get("mime_type") == "application/pdf",
                "is_text": document.get("mime_type", "").startswith("text/"),
                "estimated_pages": self._estimate_pages(document),
                "sender": sender,
                "folder": folder,
                "file_share_event": file_share_event,
                "event_type": event_type
            }
            
            # Add AI-powered metadata extraction for text files
            if document.get("mime_type", "").startswith("text/"):
                # For text files, we can do some basic analysis
                metadata["content_preview"] = "Text document detected"
            
            return metadata
        except Exception as e:
            self.logger.warning(f"Error extracting metadata: {e}")
            return {"upload_timestamp": datetime.utcnow().isoformat()}
    
    def _estimate_pages(self, document: Dict[str, Any]) -> int:
        """Estimate number of pages based on file size and type"""
        try:
            if document.get("mime_type") == "application/pdf":
                # Rough estimate: 1MB ≈ 10 pages
                return max(1, document.get("file_size", 0) // (1024 * 1024) * 10)
            elif document.get("mime_type", "").startswith("image/"):
                return 1
            else:
                return 1
        except Exception:
            return 1
    
    def validate_input(self, document: Dict[str, Any]) -> bool:
        """Validate document for ingestion"""
        if not document or not document.get("filename"):
            return False
        
        # Check if file exists
        if not os.path.exists(document.get("file_path", "")):
            return False
        
        # Check file size
        if document.get("file_size", 0) > 50 * 1024 * 1024:  # 50MB limit
            return False
        
        return True 