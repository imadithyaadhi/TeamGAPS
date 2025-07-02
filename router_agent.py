from typing import Dict, Any
from app.agents.base_agent import BaseAgent


class RouterAgent(BaseAgent):
    """Agent responsible for document routing with enterprise workflow support"""
    
    def __init__(self, ai_service):
        super().__init__("router", ai_service)
    
    async def process(self, document: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Process document routing with enhanced business logic"""
        try:
            # Log start of processing
            self.log_event(document, "started", "success", "Document routing started")
            
            # Validate document
            if not self.validate_input(document):
                raise ValueError("Invalid document for routing")
            
            # Get document type, entities, and extracted text
            document_type = document.get("document_type", "unknown")
            entities = document.get("entities", {})
            extracted_text = document.get("extracted_text", "")
            priority_level = document.get("priority_level", "medium")
            compliance_flags = document.get("compliance_flags", [])
            
            # Get classifier confidence score if available
            confidence_score = document.get("confidence_score")
            if confidence_score is None and isinstance(document.get("classifier"), dict):
                confidence_score = document["classifier"].get("confidence_score")
            
            # LLM or business rules for routing (now with extracted_text)
            routing_result = await self.ai_service.determine_routing(document_type, entities, extracted_text)
            
            # Extract routing details with enhanced fields
            destination = routing_result.get("destination", "general_archive")
            priority = routing_result.get("priority", priority_level)
            reasoning = routing_result.get("reasoning", "No reasoning provided")
            additional_actions = routing_result.get("additional_actions", [])
            compliance_notes = routing_result.get("compliance_notes", [])
            estimated_processing_time = routing_result.get("estimated_processing_time", "24-48 hours")
            fallback_destination = routing_result.get("fallback_destination", "general_archive")
            
            # Perform routing action
            routing_success = await self._perform_routing(
                document, 
                destination, 
                priority, 
                additional_actions,
                compliance_notes
            )
            
            # Fallback logic
            if not routing_success and fallback_destination != destination:
                self.logger.warning(f"Primary routing to {destination} failed, trying fallback {fallback_destination}")
                routing_success = await self._perform_routing(
                    document, 
                    fallback_destination, 
                    "low", 
                    ["manual review required"],
                    ["Fallback routing used"]
                )
            
            # Update document status
            final_status = "routed" if routing_success else "routing_failed"
            self.update_document_status(
                document, 
                final_status,
                routing_destination=destination if routing_success else fallback_destination,
                routing_priority=priority,
                routing_reasoning=reasoning,
                routing_actions=additional_actions,
                compliance_notes=compliance_notes,
                estimated_processing_time=estimated_processing_time,
                fallback_used=not routing_success and fallback_destination != destination
            )
            
            # Log completion with enhanced details
            self.log_event(
                document,
                "completed",
                "success" if routing_success else "error",
                f"Document routed to {destination if routing_success else fallback_destination} with {priority} priority",
                {
                    "destination": destination if routing_success else fallback_destination,
                    "priority": priority,
                    "reasoning": reasoning,
                    "additional_actions": additional_actions,
                    "compliance_notes": compliance_notes,
                    "estimated_processing_time": estimated_processing_time,
                    "routing_success": routing_success,
                    "fallback_used": not routing_success and fallback_destination != destination,
                    "ai_routing_result": routing_result,  # Log full AI response for audit
                    "confidence_score": confidence_score
                }
            )
            
            return {
                "status": "success" if routing_success else "failed",
                "destination": destination if routing_success else fallback_destination,
                "priority": priority,
                "reasoning": reasoning,
                "additional_actions": additional_actions,
                "compliance_notes": compliance_notes,
                "estimated_processing_time": estimated_processing_time,
                "routing_success": routing_success,
                "fallback_used": not routing_success and fallback_destination != destination,
                "next_agent": None,  # End of pipeline
                "confidence_score": confidence_score
            }
            
        except Exception as e:
            self.logger.error(f"Error in router agent: {e}")
            self.log_event(document, "failed", "error", str(e))
            self.update_document_status(document, "failed")
            raise
    
    async def _perform_routing(self, document: Dict[str, Any], destination: str, priority: str, 
                              additional_actions: list, compliance_notes: list) -> bool:
        """Perform the actual routing action with enhanced business logic"""
        try:
            # Simulate routing action (API call, upload, etc.)
            self.logger.info(f"Routing document {document.get('id')} to {destination} with priority {priority}")
            return True
        except Exception as e:
            self.logger.error(f"Routing action failed: {e}")
            return False
    
    def validate_input(self, document: Dict[str, Any]) -> bool:
        """Validate document for routing"""
        if not document or not document.get("filename"):
            return False
        
        # Check if document has been classified
        if document.get("status") not in ["classified", "routed", "needs_review"]:
            return False
        
        # Check if we have a document type
        if not document.get("document_type"):
            return False
        
        return True 