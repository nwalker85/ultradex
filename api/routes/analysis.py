"""Analysis management endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from core import (
    AnalysisRunDB,
    ContactAnalyzer,
    get_db,
    OperationService,
)
from ..dependencies import get_analyzer

router = APIRouter()


@router.post("/analyze", deprecated=True)
async def run_analysis(
    limit: Optional[int] = None,
    analyzer: ContactAnalyzer = Depends(get_analyzer),
    db: Session = Depends(get_db)
):
    """
    Run AI analysis on contacts that need analysis

    ⚠️ **DEPRECATED** - Use POST /api/v2/contacts/commands/analyze instead.
    This endpoint will be removed in 6 months (Aug 2026).
    """
    # Create operation
    operation = OperationService.create_operation(db, command="analyze")
    OperationService.start_operation(db, operation.id)

    try:
        result = await analyzer.analyze_contacts(db, limit=limit)
        OperationService.complete_operation(db, operation.id, result)

        return {
            "status": "success",
            "operation_id": operation.id,
            "analyzed": result.get("analyzed"),
            "neglected": result.get("neglected"),
            "tokens": result.get("tokens"),
            "cost": result.get("cost"),
            "timestamp": datetime.now().isoformat(),
            "_warning": "This endpoint is deprecated. Use /api/v2/contacts/commands/analyze instead."
        }
    except Exception as e:
        OperationService.fail_operation(db, operation.id, str(e))
        raise HTTPException(status_code=500, detail=f"Error running analysis: {str(e)}")


@router.get("/analyze/runs")
async def get_analysis_runs(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get recent analysis runs"""
    try:
        runs = db.query(AnalysisRunDB).order_by(
            AnalysisRunDB.timestamp.desc()
        ).limit(limit).all()
        
        return [
            {
                "id": run.id,
                "timestamp": run.timestamp.isoformat(),
                "contacts_analyzed": run.contacts_analyzed,
                "neglected_contacts_found": run.neglected_contacts_found,
                "estimated_tokens": run.estimated_tokens,
                "estimated_cost": run.estimated_cost,
                "success": run.success,
                "error_message": run.error_message
            }
            for run in runs
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching analysis runs: {str(e)}")


@router.get("/analyze/runs/{run_id}")
async def get_analysis_run(
    run_id: str,
    db: Session = Depends(get_db)
):
    """Get details of a specific analysis run"""
    try:
        run = db.query(AnalysisRunDB).filter(AnalysisRunDB.id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Analysis run not found")
        
        return {
            "id": run.id,
            "timestamp": run.timestamp.isoformat(),
            "contacts_analyzed": run.contacts_analyzed,
            "neglected_contacts_found": run.neglected_contacts_found,
            "estimated_tokens": run.estimated_tokens,
            "estimated_cost": run.estimated_cost,
            "success": run.success,
            "error_message": run.error_message
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching analysis run: {str(e)}")


@router.get("/stats")
async def get_analysis_stats(db: Session = Depends(get_db)):
    """Get aggregate statistics about analysis"""
    try:
        total_runs = db.query(AnalysisRunDB).count()
        total_analyzed = sum([
            run.contacts_analyzed for run in db.query(AnalysisRunDB).all()
        ])
        total_cost = sum([
            run.estimated_cost for run in db.query(AnalysisRunDB).all()
        ])
        total_neglected = sum([
            run.neglected_contacts_found for run in db.query(AnalysisRunDB).all()
        ])
        
        return {
            "total_runs": total_runs,
            "total_contacts_analyzed": total_analyzed,
            "total_neglected_found": total_neglected,
            "total_cost": total_cost,
            "average_cost_per_run": total_cost / max(total_runs, 1),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating stats: {str(e)}")
