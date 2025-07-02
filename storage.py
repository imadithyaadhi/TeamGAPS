import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import threading
import base64

from app.config import settings

class LocalStorage:
    """Local file-based storage using JSON files"""
    
    def __init__(self):
        self.storage_dir = Path(settings.upload_dir) / "data"
        self.documents_file = self.storage_dir / "documents.json"
        self.events_file = self.storage_dir / "events.json"
        self.lock = threading.Lock()  # For thread safety
        
        # Ensure storage directory exists
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize files if they don't exist
        self._init_storage_files()
    
    def _init_storage_files(self):
        """Initialize storage files if they don't exist"""
        if not self.documents_file.exists():
            self._save_documents({})
        
        if not self.events_file.exists():
            self._save_events({})
        
        # New: initialize comments, assignments, notifications, pipeline
        for file in [self._comments_file(), self._assignments_file(), self._notifications_file()]:
            if not file.exists():
                self._save_json(file, {})
        if not self._pipeline_file().exists():
            self._save_json(self._pipeline_file(), {"pipeline": []})
    
    def _load_documents(self) -> Dict[str, Any]:
        """Load documents from JSON file"""
        try:
            with open(self.documents_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_documents(self, documents: Dict[str, Any]):
        """Save documents to JSON file"""
        with self.lock:
            with open(self.documents_file, 'w', encoding='utf-8') as f:
                json.dump(documents, f, indent=2, default=str)
    
    def _load_events(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load events from JSON file"""
        try:
            with open(self.events_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_events(self, events: Dict[str, List[Dict[str, Any]]]):
        """Save events to JSON file"""
        with self.lock:
            with open(self.events_file, 'w', encoding='utf-8') as f:
                json.dump(events, f, indent=2, default=str)
    
    def create_document(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new document"""
        documents = self._load_documents()
        
        # Generate unique ID
        doc_id = str(uuid.uuid4())
        
        # Add document with metadata
        document = {
            "id": doc_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "status": "uploaded",
            "user_id": document_data.get("user_id", "unknown"),
            "user_email": document_data.get("user_email", "unknown"),
            "user_role": document_data.get("user_role", "unknown"),
            **document_data
        }
        print(f"DEBUG: [create_document] doc_id type: {type(doc_id)}, value: {doc_id}")
        print(f"DEBUG: [create_document] document keys: {list(document.keys())}")
        documents[doc_id] = document
        self._save_documents(documents)
        return document
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID"""
        documents = self._load_documents()
        return documents.get(doc_id)
    
    def get_all_documents(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get all documents with optional filtering"""
        documents = self._load_documents()
        docs_list = list(documents.values())
        
        # Apply filters
        if filters:
            if filters.get('status'):
                docs_list = [doc for doc in docs_list if doc.get('status') == filters['status']]
            
            if filters.get('document_type'):
                docs_list = [doc for doc in docs_list if doc.get('document_type') == filters['document_type']]
            
            if filters.get('user_id'):
                docs_list = [doc for doc in docs_list if doc.get('user_id') == filters['user_id']]
            
            if filters.get('user_email'):
                docs_list = [doc for doc in docs_list if doc.get('user_email') == filters['user_email']]
            
            if filters.get('user_role'):
                docs_list = [doc for doc in docs_list if doc.get('user_role') == filters['user_role']]
        
        # Sort by created_at (newest first)
        docs_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        return docs_list
    
    def update_document(self, doc_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a document"""
        documents = self._load_documents()
        print(f"DEBUG: [update_document] doc_id type: {type(doc_id)}, value: {doc_id}")
        print(f"DEBUG: [update_document] updates keys: {list(updates.keys())}")
        if doc_id not in documents:
            return None
        documents[doc_id].update(updates)
        documents[doc_id]['updated_at'] = datetime.utcnow().isoformat()
        self._save_documents(documents)
        return documents[doc_id]
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document"""
        documents = self._load_documents()
        
        if doc_id not in documents:
            return False
        
        # Remove document
        del documents[doc_id]
        self._save_documents(documents)
        
        # Remove associated events
        events = self._load_events()
        if doc_id in events:
            del events[doc_id]
            self._save_events(events)
        
        return True
    
    def create_event(self, doc_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new processing event"""
        events = self._load_events()
        print(f"DEBUG: [create_event] doc_id type: {type(doc_id)}, value: {doc_id}")
        print(f"DEBUG: [create_event] event_data keys: {list(event_data.keys())}")
        if doc_id not in events:
            events[doc_id] = []
        event = {
            "id": str(uuid.uuid4()),
            "document_id": doc_id,
            "created_at": datetime.utcnow().isoformat(),
            **event_data
        }
        events[doc_id].append(event)
        self._save_events(events)
        return event
    
    def get_document_events(self, doc_id: str) -> List[Dict[str, Any]]:
        """Get all events for a document"""
        events = self._load_events()
        document_events = events.get(doc_id, [])
        print(f"DEBUG: Storage - Requested events for doc_id: {doc_id}")
        print(f"DEBUG: Storage - Available document IDs in events: {list(events.keys())}")
        print(f"DEBUG: Storage - Returning {len(document_events)} events for document {doc_id}")
        return document_events
    
    def get_document_status(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed status for a document"""
        document = self.get_document(doc_id)
        if not document:
            return None
        
        events = self.get_document_events(doc_id)
        
        # Group events by agent
        agent_statuses = {}
        for event in events:
            agent_name = event.get('agent_name')
            if agent_name not in agent_statuses:
                agent_statuses[agent_name] = []
            agent_statuses[agent_name].append(event)
        
        # Get latest status for each agent
        agent_status_summary = {}
        for agent_name, agent_events in agent_statuses.items():
            # Sort by timestamp and get latest
            latest_event = sorted(agent_events, key=lambda x: x.get('created_at', ''))[-1]
            agent_status_summary[agent_name] = {
                "status": latest_event.get('status'),
                "event_type": latest_event.get('event_type'),
                "message": latest_event.get('message'),
                "processing_time": latest_event.get('processing_time'),
                "timestamp": latest_event.get('created_at')
            }
        
        return {
            "document_id": doc_id,
            "current_status": document.get('status'),
            "agent_statuses": agent_status_summary,
            "total_events": len(events)
        }

    def get_user_statistics(self, user_email: str = None, user_role: str = None) -> Dict[str, Any]:
        """Get statistics for a specific user or role"""
        documents = self._load_documents()
        docs_list = list(documents.values())
        
        # Filter by user if specified
        if user_email:
            docs_list = [doc for doc in docs_list if doc.get('user_email') == user_email]
        elif user_role:
            docs_list = [doc for doc in docs_list if doc.get('user_role') == user_role]
        
        # Calculate statistics
        total_documents = len(docs_list)
        completed_documents = len([doc for doc in docs_list if doc.get('status') in ['completed', 'routed']])
        processing_documents = len([doc for doc in docs_list if doc.get('status') in ['uploaded', 'ingested', 'extracted', 'classified']])
        failed_documents = len([doc for doc in docs_list if doc.get('status') in ['failed', 'routing_failed']])
        
        success_rate = (completed_documents / total_documents * 100) if total_documents > 0 else 0
        
        return {
            "total_documents": total_documents,
            "completed_documents": completed_documents,
            "processing_documents": processing_documents,
            "failed_documents": failed_documents,
            "success_rate": round(success_rate, 1)
        }
    
    def get_all_users_statistics(self) -> Dict[str, Any]:
        """Get statistics for all users"""
        documents = self._load_documents()
        docs_list = list(documents.values())
        
        # Group documents by user
        user_stats = {}
        for doc in docs_list:
            user_email = doc.get('user_email', 'unknown')
            user_role = doc.get('user_role', 'unknown')
            
            if user_email not in user_stats:
                user_stats[user_email] = {
                    "user_email": user_email,
                    "user_role": user_role,
                    "total_documents": 0,
                    "completed_documents": 0,
                    "processing_documents": 0,
                    "failed_documents": 0
                }
            
            user_stats[user_email]["total_documents"] += 1
            
            if doc.get('status') in ['completed', 'routed']:
                user_stats[user_email]["completed_documents"] += 1
            elif doc.get('status') in ['uploaded', 'ingested', 'extracted', 'classified']:
                user_stats[user_email]["processing_documents"] += 1
            elif doc.get('status') in ['failed', 'routing_failed']:
                user_stats[user_email]["failed_documents"] += 1
        
        # Calculate success rates
        for user_email, stats in user_stats.items():
            if stats["total_documents"] > 0:
                stats["success_rate"] = round((stats["completed_documents"] / stats["total_documents"]) * 100, 1)
            else:
                stats["success_rate"] = 0
        
        return user_stats

    def _comments_file(self):
        return self.storage_dir / "comments.json"

    def _assignments_file(self):
        return self.storage_dir / "assignments.json"

    def _notifications_file(self):
        return self.storage_dir / "notifications.json"

    def _pipeline_file(self):
        return self.storage_dir / "pipeline.json"

    def _load_json(self, file):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_json(self, file, data):
        with self.lock:
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)

    # Comments
    def get_comments(self, doc_id: str) -> list:
        comments = self._load_json(self._comments_file())
        return comments.get(doc_id, [])

    def add_comment(self, doc_id: str, comment: dict):
        comments = self._load_json(self._comments_file())
        comments.setdefault(doc_id, []).append(comment)
        self._save_json(self._comments_file(), comments)

    # Assignments
    def get_assignments(self, doc_id: str) -> list:
        assignments = self._load_json(self._assignments_file())
        return assignments.get(doc_id, [])

    def assign_user(self, doc_id: str, assignment: dict):
        assignments = self._load_json(self._assignments_file())
        assignments.setdefault(doc_id, []).append(assignment)
        self._save_json(self._assignments_file(), assignments)

    # Notifications
    def get_notifications(self, user_id: str) -> list:
        notifications = self._load_json(self._notifications_file())
        return notifications.get(user_id, [])

    def add_notification(self, user_id: str, notification: dict):
        notifications = self._load_json(self._notifications_file())
        notifications.setdefault(user_id, []).append(notification)
        self._save_json(self._notifications_file(), notifications)

    # Pipeline config
    def get_pipeline(self) -> dict:
        return self._load_json(self._pipeline_file())

    def save_pipeline(self, pipeline: dict):
        self._save_json(self._pipeline_file(), pipeline)

# Global storage instance
storage = LocalStorage()

__all__ = [
    "LocalStorage",
    "storage",
    # Comments/Assignments/Notifications/Pipeline
    "get_comments", "add_comment",
    "get_assignments", "assign_user",
    "get_notifications", "add_notification",
    "get_pipeline", "save_pipeline"
] 