from typing import Dict, Any
from app.agents.base_agent import BaseAgent


class ClassifierAgent(BaseAgent):
    """Agent responsible for document classification with enterprise features"""
    
    def __init__(self, ai_service):
        super().__init__("classifier", ai_service)
    
    async def process(self, document: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Process document classification with enhanced analysis"""
        try:
            # Log start of processing
            self.log_event(document, "started", "success", "Document classification started")
            
            # Validate document
            if not self.validate_input(document):
                raise ValueError("Invalid document for classification")
            
            # Get extracted text and entities
            extracted_text = document.get("extracted_text", "")
            entities = document.get("entities", {})
            
            # LLM-powered classification
            classification_result = await self.ai_service.classify_document(extracted_text, entities)
            
            # Extract classification details with enhanced fields
            document_type = classification_result.get("document_type", "unknown")
            confidence_score = classification_result.get("confidence_score", 0.0)
            reasoning = classification_result.get("reasoning", "No reasoning provided")
            sub_type = classification_result.get("sub_type", "general")
            priority_level = classification_result.get("priority_level", "medium")
            compliance_flags = classification_result.get("compliance_flags", [])
            processing_notes = classification_result.get("processing_notes", "")
            
            # Human review flag
            needs_review = (
                confidence_score < 0.3 or 
                len(compliance_flags) > 0 or
                priority_level == "high"
            )
            
            self.logger.info(f"[LLM] Classification: {document_type}, Confidence: {confidence_score}, Reasoning: {reasoning}, Needs review: {needs_review}")
            
            # Update document with enhanced classification data
            self.update_document_status(
                document,
                "classified" if not needs_review else "needs_review",
                document_type=document_type,
                confidence_score=confidence_score,
                sub_type=sub_type,
                priority_level=priority_level,
                compliance_flags=compliance_flags,
                processing_notes=processing_notes
            )
            
            # Log completion with enhanced details
            self.log_event(
                document,
                "completed",
                "success" if not needs_review else "warning",
                f"Document classified as {document_type} ({sub_type}) with {confidence_score:.1%} confidence",
                {
                    "document_type": document_type,
                    "confidence_score": confidence_score,
                    "reasoning": reasoning,
                    "sub_type": sub_type,
                    "priority_level": priority_level,
                    "compliance_flags": compliance_flags,
                    "processing_notes": processing_notes,
                    "needs_review": needs_review
                }
            )
            
            return {
                "status": "success",
                "document_type": document_type,
                "confidence_score": confidence_score,
                "reasoning": reasoning,
                "sub_type": sub_type,
                "priority_level": priority_level,
                "compliance_flags": compliance_flags,
                "processing_notes": processing_notes,
                "needs_review": needs_review,
                "next_agent": "router"  # Always continue to router
            }
            
        except Exception as e:
            self.logger.error(f"Error in classifier agent: {e}")
            self.log_event(document, "failed", "error", str(e))
            self.update_document_status(document, "failed")
            raise
    
    def validate_input(self, document: Dict[str, Any]) -> bool:
        """Validate document for classification"""
        if not document or not document.get("filename"):
            return False
        
        # Check if document has been extracted
        if document.get("status") not in ["extracted", "classified", "needs_review"]:
            return False
        
        # Check if we have extracted text
        if not document.get("extracted_text"):
            return False
        
        return True 