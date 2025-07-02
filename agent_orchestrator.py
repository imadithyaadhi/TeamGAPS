import asyncio
from typing import Dict, Any, List
from app.agents.ingestor_agent import IngestorAgent
from app.agents.extractor_agent import ExtractorAgent
from app.agents.classifier_agent import ClassifierAgent
from app.agents.router_agent import RouterAgent
from app.services.ai_service import AIService
from app.storage import storage
import logging

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Orchestrates the multi-agent document processing workflow with enhanced enterprise features"""
    
    def __init__(self):
        self.ai_service = AIService()
        
        # Initialize agents
        self.ingestor = IngestorAgent(self.ai_service)
        self.extractor = ExtractorAgent(self.ai_service)
        self.classifier = ClassifierAgent(self.ai_service)
        self.router = RouterAgent(self.ai_service)
        
        # Dynamic pipeline
        self._default_pipeline = [
            ("ingestor", self.ingestor, "uploaded"),
            ("extractor", self.extractor, "ingested"),
            ("classifier", self.classifier, "extracted"),
            ("router", self.router, "classified")
        ]
    
    def get_pipeline(self):
        pipeline_conf = storage.get_pipeline().get("pipeline")
        if pipeline_conf and isinstance(pipeline_conf, list):
            # Map names to agent instances
            agent_map = {
                "ingestor": self.ingestor,
                "extractor": self.extractor,
                "classifier": self.classifier,
                "router": self.router
            }
            return [(step["name"], agent_map[step["name"]], step.get("status", "")) for step in pipeline_conf if step["name"] in agent_map]
        return self._default_pipeline
    
    async def process_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Process a document through the entire agent pipeline with enhanced tracking"""
        try:
            logger.info(f"Starting document processing for document {document.get('id')}")
            
            results = {}
            current_document = document
            processing_start_time = asyncio.get_event_loop().time()
            
            # Process through each agent in the pipeline
            for agent_name, agent, expected_status in self.get_pipeline():
                try:
                    logger.info(f"Processing with {agent_name} agent")
                    
                    # Check if document is in expected state
                    if current_document.get("status") != expected_status:
                        logger.warning(f"Document {document.get('id')} not in expected state for {agent_name}. Current: {current_document.get('status')}, Expected: {expected_status}")
                    
                    # Process with current agent
                    agent_start_time = asyncio.get_event_loop().time()
                    result = await agent.process(current_document)
                    agent_processing_time = asyncio.get_event_loop().time() - agent_start_time
                    
                    # Add processing time to result
                    result["processing_time"] = agent_processing_time
                    results[agent_name] = result
                    
                    # Check if processing should continue
                    if result.get("status") != "success":
                        logger.warning(f"Agent {agent_name} failed: {result}")
                        break
                    
                    # Check if next agent is specified
                    next_agent = result.get("next_agent")
                    if next_agent is None:
                        # Special handling for classifier - continue to router even if needs_review
                        if agent_name == "classifier" and result.get("needs_review"):
                            logger.info(f"Document needs review but continuing to router for routing decision")
                            next_agent = "router"
                        else:
                            logger.info(f"Pipeline completed at {agent_name} agent")
                            break
                    
                    # Refresh document from storage to get latest state
                    current_document = storage.get_document(document.get("id"))
                    if not current_document:
                        logger.error(f"Document {document.get('id')} not found in storage")
                        break
                    
                except Exception as e:
                    logger.error(f"Error in {agent_name} agent: {e}")
                    results[agent_name] = {
                        "status": "error",
                        "error": str(e),
                        "processing_time": 0
                    }
                    break
            
            # Calculate total processing time
            total_processing_time = asyncio.get_event_loop().time() - processing_start_time
            
            # Final status update
            final_status = self._determine_final_status(results)
            storage.update_document(document.get("id"), {
                "status": final_status,
                "total_processing_time": total_processing_time,
                "agent_results": results
            })
            
            logger.info(f"Document processing completed. Final status: {final_status}, Total time: {total_processing_time:.2f}s")
            
            return {
                "document_id": document.get("id"),
                "final_status": final_status,
                "results": results,
                "total_processing_time": total_processing_time,
                "success": final_status in ["routed", "completed", "needs_review"]
            }
            
        except Exception as e:
            logger.error(f"Error in document processing: {e}")
            return {
                "document_id": document.get("id"),
                "final_status": "failed",
                "error": str(e),
                "success": False
            }
    
    async def reprocess_document(self, document: Dict[str, Any], from_agent: str = None) -> Dict[str, Any]:
        """Reprocess a document from a specific agent with enhanced error handling"""
        try:
            logger.info(f"Reprocessing document {document.get('id')} from agent: {from_agent}")
            
            # Determine starting point
            start_index = 0
            if from_agent:
                for i, (agent_name, _, _) in enumerate(self.get_pipeline()):
                    if agent_name == from_agent:
                        start_index = i
                        break
            
            # Reset document status to the starting point
            status_mapping = {
                0: "uploaded",
                1: "ingested", 
                2: "extracted",
                3: "classified"
            }
            
            reset_status = status_mapping.get(start_index, "uploaded")
            storage.update_document(document.get("id"), {"status": reset_status})
            
            # Process from the specified agent
            results = {}
            current_document = storage.get_document(document.get("id"))
            processing_start_time = asyncio.get_event_loop().time()
            
            for i, (agent_name, agent, expected_status) in enumerate(self.get_pipeline()[start_index:], start_index):
                try:
                    logger.info(f"Reprocessing with {agent_name} agent")
                    
                    agent_start_time = asyncio.get_event_loop().time()
                    result = await agent.process(current_document)
                    agent_processing_time = asyncio.get_event_loop().time() - agent_start_time
                    
                    result["processing_time"] = agent_processing_time
                    results[agent_name] = result
                    
                    if result.get("status") != "success":
                        break
                    
                    next_agent = result.get("next_agent")
                    if next_agent is None:
                        break
                    
                    current_document = storage.get_document(document.get("id"))
                    
                except Exception as e:
                    logger.error(f"Error in {agent_name} agent during reprocessing: {e}")
                    results[agent_name] = {
                        "status": "error",
                        "error": str(e),
                        "processing_time": 0
                    }
                    break
            
            # Calculate total processing time
            total_processing_time = asyncio.get_event_loop().time() - processing_start_time
            
            # Final status update
            final_status = self._determine_final_status(results)
            storage.update_document(document.get("id"), {
                "status": final_status,
                "total_processing_time": total_processing_time,
                "agent_results": results
            })
            
            return {
                "document_id": document.get("id"),
                "final_status": final_status,
                "results": results,
                "total_processing_time": total_processing_time,
                "success": final_status in ["routed", "completed", "needs_review"]
            }
            
        except Exception as e:
            logger.error(f"Error in document reprocessing: {e}")
            return {
                "document_id": document.get("id"),
                "final_status": "failed",
                "error": str(e),
                "success": False
            }
    
    def _determine_final_status(self, results: Dict[str, Any]) -> str:
        """Determine the final status based on agent results with enhanced logic"""
        if not results:
            return "failed"
        
        # Check if any agent failed
        for agent_name, result in results.items():
            if result.get("status") == "error":
                return "failed"
        
        # Enhanced status determination based on agent results
        if "router" in results and results["router"].get("status") == "success":
            routing_result = results["router"]
            if routing_result.get("routing_success"):
                return "routed"
            else:
                return "routing_failed"
        elif "classifier" in results and results["classifier"].get("status") == "success":
            classification_result = results["classifier"]
            if classification_result.get("needs_review"):
                return "needs_review"
            else:
                return "classified"
        elif "extractor" in results and results["extractor"].get("status") == "success":
            return "extracted"
        elif "ingestor" in results and results["ingestor"].get("status") == "success":
            return "ingested"
        else:
            return "failed"
    
    async def get_processing_status(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Get the current processing status of a document with enhanced details"""
        try:
            # Get document status from storage
            status = storage.get_document_status(document.get("id"))
            
            if not status:
                return {
                    "document_id": document.get("id"),
                    "error": "Document not found"
                }
            
            # Add enhanced status information
            document_data = storage.get_document(document.get("id"))
            if document_data:
                status.update({
                    "document_type": document_data.get("document_type"),
                    "confidence_score": document_data.get("confidence_score"),
                    "entities": document_data.get("entities"),
                    "routing_destination": document_data.get("routing_destination"),
                    "priority": document_data.get("priority"),
                    "total_processing_time": document_data.get("total_processing_time")
                })
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting processing status: {e}")
            return {
                "document_id": document.get("id"),
                "error": str(e)
            }
    
    async def get_pipeline_statistics(self) -> Dict[str, Any]:
        """Get overall pipeline statistics"""
        try:
            documents = storage.get_all_documents()
            
            # Calculate statistics by status
            status_counts = {}
            document_types = {}
            processing_times = []
            
            for doc in documents:
                status = doc.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
                
                doc_type = doc.get("document_type", "unknown")
                document_types[doc_type] = document_types.get(doc_type, 0) + 1
                
                if doc.get("total_processing_time"):
                    processing_times.append(doc.get("total_processing_time"))
            
            # Calculate averages
            avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
            
            return {
                "total_documents": len(documents),
                "status_distribution": status_counts,
                "document_type_distribution": document_types,
                "average_processing_time": avg_processing_time,
                "success_rate": self._calculate_success_rate(status_counts)
            }
            
        except Exception as e:
            logger.error(f"Error getting pipeline statistics: {e}")
            return {
                "error": str(e)
            }
    
    def _calculate_success_rate(self, status_counts: Dict[str, int]) -> float:
        """Calculate success rate based on status counts"""
        total = sum(status_counts.values())
        if total == 0:
            return 0.0
        
        successful_statuses = ["routed", "completed", "classified"]
        successful_count = sum(status_counts.get(status, 0) for status in successful_statuses)
        
        return (successful_count / total) * 100 