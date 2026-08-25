"""FastAPI REST router for Candidate Profile."""

from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from core.jobsearch_profile import (
    CandidateProfile,
    CandidateProfileStore,
    SkillCategory,
    SkillTier,
)

router = APIRouter()


@router.get("", response_model=CandidateProfile)
@router.get("/", response_model=CandidateProfile)
def get_profile(db: Session = Depends(get_db)):
    """Retrieve the authoritative Candidate Profile."""
    store = CandidateProfileStore(db)
    return store.get_profile()


@router.put("", response_model=CandidateProfile)
@router.put("/", response_model=CandidateProfile)
def update_profile(profile: CandidateProfile, db: Session = Depends(get_db)):
    """Update the Candidate Profile."""
    store = CandidateProfileStore(db)
    return store.update_profile(profile)


@router.get("/skills")
def get_skills(
    tier: Optional[SkillTier] = None,
    category: Optional[SkillCategory] = None,
    db: Session = Depends(get_db),
):
    """Retrieve skills taxonomy with optional tier and category filters."""
    store = CandidateProfileStore(db)
    profile = store.get_profile()
    skills_list = list(profile.skills.values())
    if tier:
        skills_list = [s for s in skills_list if s.tier == tier]
    if category:
        skills_list = [s for s in skills_list if s.category == category]
    return {
        "total": len(skills_list),
        "expert_count": len([s for s in skills_list if s.tier == SkillTier.EXPERT]),
        "advanced_count": len([s for s in skills_list if s.tier == SkillTier.ADVANCED]),
        "skills": skills_list,
    }


@router.get("/ml-depth")
def get_production_ml_depth(db: Session = Depends(get_db)):
    """Retrieve production ML depth matrix."""
    store = CandidateProfileStore(db)
    return store.get_profile().production_ml


@router.get("/roles")
def get_target_roles_and_comp(db: Session = Depends(get_db)):
    """Retrieve target roles and compensation expectations."""
    profile = CandidateProfileStore(db).get_profile()
    return {
        "target_roles": profile.target_roles,
        "target_domains": profile.target_domains,
        "compensation": profile.compensation,
    }
