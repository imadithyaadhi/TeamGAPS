from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Query, Form, Body, Depends
from typing import List, Optional
import os
import uuid
import shutil
from datetime import datetime
from fastapi.responses import FileResponse, JSONResponse

from app.storage import storage
from app.services.agent_orchestrator import AgentOrchestrator
from app.config import settings
from app.services.post_routing_email import send_routing_notification

router = APIRouter(prefix="/api/documents", tags=["documents"])


def compute_priority(user_email, file_size, folder=None):
    """Compute document priority based on user, file size, and folder context"""
    # VIP senders get high priority
    vip_senders = ['ceo@company.com', 'finance@company.com', 'admin@company.com']
    if user_email in vip_senders:
        return 'high'
    
    # Urgent folder gets high priority
    if folder and 'urgent' in folder.lower():
        return 'high'
    
    # Very large files (>50MB) get high priority
    if file_size > 50 * 1024 * 1024:
        return 'high'
    
    # Small files (<1MB) or archive folders get low priority
    if file_size < 1 * 1024 * 1024 or (folder and 'archive' in folder.lower()):
        return 'low'
    
    # Medium files (1-50MB) get medium priority
    if file_size < 10 * 1024 * 1024:
        return 'medium'
    
    # Large files (10-50MB) get high priority
    return 'high'


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Form(...),
    user_email: str = Form(...),
    user_role: str = Form(...)
):
    """Upload a document for processing"""
    try:
        print(f"Upload request received - File: {file.filename}, User: {user_email}, Role: {user_role}")
        
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Check file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        print(f"File size: {file_size} bytes")
        
        if file_size > settings.max_file_size:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large. Maximum size is {settings.max_file_size} bytes"
            )
        
        # Create user-specific folder
        user_folder = os.path.join(settings.upload_dir, user_email.replace('@', '_').replace('.', '_'))
        os.makedirs(user_folder, exist_ok=True)
        print(f"Created user folder: {user_folder}")
        
        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(user_folder, unique_filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        print(f"File saved to: {file_path}")
        
        # Compute priority
        priority = compute_priority(user_email, file_size, user_folder)
        # Create document record with user information
        document_data = {
            "filename": os.path.basename(file_path),
            "original_filename": file.filename,
            "file_path": file_path,
            "file_size": file_size,
            "mime_type": file.content_type or "application/octet-stream",
            "user_id": user_id,
            "user_email": user_email,
            "user_role": user_role,
            "priority": priority
        }
        
        document = storage.create_document(document_data)
        print(f"Document created with ID: {document['id']}")
        
        # Start background processing
        background_tasks.add_task(process_document_background, document["id"])
        
        return document
        
    except Exception as e:
        print(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def get_documents(
    status: Optional[str] = None,
    document_type: Optional[str] = None,
    user_email: Optional[str] = None,
    user_role: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Get all documents with optional filtering"""
    try:
        filters = {}
        if status:
            filters['status'] = status
        if document_type:
            filters['document_type'] = document_type
        if user_email:
            filters['user_email'] = user_email
        if user_role:
            filters['user_role'] = user_role
        
        documents = storage.get_all_documents(filters)
        
        # Apply pagination
        total = len(documents)
        documents = documents[offset:offset + limit]
        
        return {
            "documents": documents,
            "total": total,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}")
async def get_document(document_id: str):
    """Get a specific document by ID"""
    try:
        document = storage.get_document(document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return document
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """Delete a document"""
    try:
        success = storage.delete_document(document_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {"message": "Document deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/status")
async def get_document_status(document_id: str):
    """Get detailed processing status for a document"""
    try:
        document = storage.get_document(document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        orchestrator = AgentOrchestrator()
        status = await orchestrator.get_processing_status(document)
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: str,
    from_agent: Optional[str] = None
):
    """Reprocess a document from a specific agent"""
    try:
        document = storage.get_document(document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        orchestrator = AgentOrchestrator()
        result = await orchestrator.reprocess_document(document, from_agent)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/events")
async def get_document_events(document_id: str):
    """Get all processing events for a document"""
    try:
        print(f"DEBUG: Requesting events for document_id: {document_id}")
        events = storage.get_document_events(document_id)
        print(f"DEBUG: Found {len(events)} events for document {document_id}")
        print(f"DEBUG: Event document_ids: {[event.get('document_id') for event in events]}")
        
        if not events:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {"events": events}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/pipeline")
async def get_pipeline_statistics():
    """Get overall pipeline statistics"""
    try:
        documents = storage.get_all_documents()
        
        total_documents = len(documents)
        completed_documents = len([doc for doc in documents if doc.get('status') in ['completed', 'routed']])
        processing_documents = len([doc for doc in documents if doc.get('status') in ['uploaded', 'ingested', 'extracted', 'classified']])
        failed_documents = len([doc for doc in documents if doc.get('status') in ['failed', 'routing_failed']])
        
        success_rate = (completed_documents / total_documents * 100) if total_documents > 0 else 0
        
        return {
            "total_documents": total_documents,
            "completed_documents": completed_documents,
            "processing_documents": processing_documents,
            "failed_documents": failed_documents,
            "success_rate": round(success_rate, 1)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/user/{user_email}")
async def get_user_statistics(user_email: str):
    """Get statistics for a specific user"""
    try:
        stats = storage.get_user_statistics(user_email=user_email)
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/users/all")
async def get_all_users_statistics():
    """Get statistics for all users"""
    try:
        stats = storage.get_all_users_statistics()
        return {"users": stats}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/health")
async def get_health_status():
    """Get system health status"""
    try:
        # Check storage health
        try:
            documents = storage.get_all_documents()
            storage_healthy = True
        except Exception:
            storage_healthy = False
        
        # Check if upload directory exists and is writable
        upload_dir_healthy = os.path.exists(settings.upload_dir) and os.access(settings.upload_dir, os.W_OK)
        
        # Get basic statistics
        total_documents = len(documents) if storage_healthy else 0
        
        return {
            "status": "healthy" if storage_healthy and upload_dir_healthy else "unhealthy",
            "components": {
                "storage": "healthy" if storage_healthy else "unhealthy",
                "upload_directory": "healthy" if upload_dir_healthy else "unhealthy"
            },
            "statistics": {
                "total_documents": total_documents
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/{document_id}/download")
async def download_document_file(document_id: str):
    """Download the raw file for a document (for backend verification)"""
    document = storage.get_document(document_id)
    if not document or not document.get("file_path"):
        raise HTTPException(status_code=404, detail="Document or file not found")
    file_path = document["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    filename = document.get("original_filename", "document.pdf")
    if filename.lower().endswith(".docx"):
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif filename.lower().endswith(".doc"):
        media_type = "application/msword"
    elif filename.lower().endswith(".pdf"):
        media_type = "application/pdf"
    else:
        media_type = "application/octet-stream"
    return FileResponse(file_path, filename=filename, media_type=media_type)


async def process_document_background(document_id: str):
    """Background task to process a document through the agent pipeline"""
    try:
        # Get document from storage
        document = storage.get_document(document_id)
        
        if not document:
            return
        
        orchestrator = AgentOrchestrator()
        result = await orchestrator.process_document(document)
        
        print(f"Background processing completed for document {document_id}: {result}")
        
        # Send routing notification if routed
        if result.get("final_status") == "routed":
            # Get the latest document and router result
            updated_document = storage.get_document(document_id)
            router_result = result["results"].get("router", {})
            try:
                send_routing_notification(updated_document, router_result)
                print(f"Routing notification email sent for document {document_id}")
            except Exception as e:
                print(f"Failed to send routing notification email: {e}")
            # --- Post-routing hook for custom actions ---
            try:
                post_routing_hook(updated_document, router_result)
                print(f"Post-routing hook executed for document {document_id}")
            except Exception as e:
                print(f"Post-routing hook failed for document {document_id}: {e}")
        
    except Exception as e:
        print(f"Background processing failed for document {document_id}: {e}")
        # Update document status to failed
        try:
            storage.update_document(document_id, {"status": "failed"})
        except:
            pass

# COMMENTS
@router.get("/{document_id}/comments")
def get_comments(document_id: str):
    return {"comments": storage.get_comments(document_id)}

@router.post("/{document_id}/comments")
def add_comment(document_id: str, user_id: str = Body(...), text: str = Body(...)):
    comment = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "text": text,
        "created_at": datetime.utcnow().isoformat()
    }
    storage.add_comment(document_id, comment)
    # Notify all assigned users
    for assignment in storage.get_assignments(document_id):
        storage.add_notification(assignment["user_id"], {
            "type": "comment",
            "document_id": document_id,
            "comment_id": comment["id"],
            "text": text,
            "from_user": user_id,
            "created_at": comment["created_at"]
        })
    return {"success": True, "comment": comment}

# ASSIGNMENTS
@router.get("/{document_id}/assignments")
def get_assignments(document_id: str):
    return {"assignments": storage.get_assignments(document_id)}

@router.post("/{document_id}/assign")
def assign_user(document_id: str, user_id: str = Body(...), assigned_by: str = Body(...)):
    assignment = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "assigned_by": assigned_by,
        "created_at": datetime.utcnow().isoformat()
    }
    storage.assign_user(document_id, assignment)
    # Notify assigned user
    storage.add_notification(user_id, {
        "type": "assignment",
        "document_id": document_id,
        "assigned_by": assigned_by,
        "created_at": assignment["created_at"]
    })
    return {"success": True, "assignment": assignment}

# NOTIFICATIONS
@router.get("/notifications/{user_id}")
def get_notifications(user_id: str):
    return {"notifications": storage.get_notifications(user_id)}

# PIPELINE CONFIG
@router.get("/pipeline")
def get_pipeline():
    return storage.get_pipeline() or {"pipeline": []}

@router.post("/pipeline")
def save_pipeline(pipeline: dict = Body(...)):
    storage.save_pipeline(pipeline)
    return {"success": True, "pipeline": pipeline}

# --- Post-routing hook function ---
def post_routing_hook(document, router_result):
    """Custom actions to perform after successful routing (archive, analytics, etc.)"""
    # Example: Log, archive, analytics, etc.
    print(f"[PostRoutingHook] Document {document.get('id')} routed to {router_result.get('destination')}")
    # Add your custom logic here (archive, analytics, etc.) 