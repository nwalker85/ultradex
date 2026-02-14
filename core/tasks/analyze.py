"""Analyze contacts task"""

import os
from datetime import datetime
from sqlalchemy.orm import Session
from ..database import Database
from ..operation_service import OperationService
from ..event_producer import EventProducer
from ..models import EventType
from ..dex_client import DexClient
from ..claude_client import ClaudeClient
from ..contact_analyzer import ContactAnalyzer


async def analyze_contacts_task(ctx, operation_id: str, parameters: dict):
    """
    Async task to analyze contacts.

    Called by: ARQ worker
    Arguments:
        - operation_id: Track operation status
        - parameters: {"limit": int, ...}
    """
    # Initialize database and clients
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://ultradex:ultradex_dev_password@localhost:5432/ultradex"
    )
    dex_api_key = os.getenv("DEX_API_KEY")
    claude_api_key = os.getenv("CLAUDE_API_KEY")

    db_service = Database(database_url)
    db = db_service.get_session()

    try:
        # Update operation: pending → running
        OperationService.start_operation(db, operation_id)

        # Emit task.started event
        EventProducer.emit(
            db,
            EventType.TASK_STARTED,
            operation_id,
            {"task": "analyze_contacts"}
        )

        # Initialize clients and analyzer
        dex = DexClient(dex_api_key)
        claude = ClaudeClient(claude_api_key)
        analyzer = ContactAnalyzer(dex, claude)

        # Execute analysis
        limit = parameters.get("limit")
        result = await analyzer.analyze_contacts(db, limit=limit)

        # Update operation: running → completed
        OperationService.complete_operation(db, operation_id, result)

        # Emit task.completed event
        EventProducer.emit(
            db,
            EventType.TASK_COMPLETED,
            operation_id,
            result
        )

        return {"status": "completed", "result": result}

    except Exception as e:
        # Update operation: running → failed
        OperationService.fail_operation(db, operation_id, str(e))

        # Emit task.failed event
        EventProducer.emit(
            db,
            EventType.TASK_FAILED,
            operation_id,
            {"error": str(e)}
        )
        raise

    finally:
        db.close()
