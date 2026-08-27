"""Explicit GraphQL types for canonical job-search read projections."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import strawberry
from ravenhelm_contracts import (
    ApplicationStageV1,
    ApplicationV1,
    JobSearchEvidenceReferenceV1,
    OpportunityV1,
    ProjectionFreshnessV1,
    RelationshipV1,
)
from strawberry.scalars import JSON

from core import ProjectedOutreach, ProjectionPage
from core.jobsearch_projections import (
    ApprovalEvidence as ApprovalEvidenceProjection,
    ExecutionReceiptEvidence as ExecutionReceiptEvidenceProjection,
)


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@strawberry.type
class EvidenceReference:
    evidence_id: str
    source_kind: str
    source_ref: str
    classification: str
    observed_at: datetime
    commitment: str
    redacted_summary: str

    @classmethod
    def from_contract(
        cls,
        contract: JobSearchEvidenceReferenceV1,
    ) -> "EvidenceReference":
        return cls(
            evidence_id=contract.evidence_id,
            source_kind=contract.source_kind,
            source_ref=contract.source_ref,
            classification=contract.classification,
            observed_at=_datetime(contract.observed_at),
            commitment=contract.commitment,
            redacted_summary=contract.redacted_summary,
        )


@strawberry.type
class ProjectionFreshness:
    source_event_id: str
    source_event_position: str
    projected_at: datetime
    lag_ms: float
    status: str

    @classmethod
    def from_contract(
        cls,
        contract: ProjectionFreshnessV1,
    ) -> "ProjectionFreshness":
        return cls(
            source_event_id=contract.source_event_id,
            source_event_position=contract.source_event_position,
            projected_at=_datetime(contract.projected_at),
            lag_ms=float(contract.lag_ms),
            status=contract.status,
        )


@strawberry.type
class ApplicationStage:
    status: str
    occurred_at: datetime
    evidence_ref: str | None

    @classmethod
    def from_contract(cls, contract: ApplicationStageV1) -> "ApplicationStage":
        return cls(
            status=contract.status,
            occurred_at=_datetime(contract.occurred_at),
            evidence_ref=contract.evidence_ref,
        )


@strawberry.type
class Opportunity:
    opportunity_id: str
    employer: str
    title: str
    location: str | None
    role_family: str | None
    status: str
    fit_score: float | None
    fit_explanation: str | None
    risk_flags: list[str]
    evidence_refs: list[EvidenceReference]
    freshness: ProjectionFreshness
    created_at: datetime
    updated_at: datetime
    organization_id: str | None = None

    @classmethod
    def from_contract(
        cls,
        contract: OpportunityV1,
        *,
        organization_id: str | None = None,
    ) -> "Opportunity":
        return cls(
            opportunity_id=contract.opportunity_id,
            employer=contract.employer,
            title=contract.title,
            location=contract.location,
            role_family=contract.role_family,
            status=contract.status,
            fit_score=(
                None if contract.fit_score is None else float(contract.fit_score)
            ),
            fit_explanation=contract.fit_explanation,
            risk_flags=list(contract.risk_flags),
            evidence_refs=[
                EvidenceReference.from_contract(item)
                for item in contract.evidence_refs
            ],
            freshness=ProjectionFreshness.from_contract(contract.freshness),
            created_at=_datetime(contract.created_at),
            updated_at=_datetime(contract.updated_at),
            organization_id=organization_id,
        )


@strawberry.type
class Application:
    application_id: str
    opportunity_id: str
    status: str
    stage_history: list[ApplicationStage]
    artifact_refs: list[str]
    next_action: str | None
    next_action_at: datetime | None
    freshness: ProjectionFreshness
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_contract(cls, contract: ApplicationV1) -> "Application":
        return cls(
            application_id=contract.application_id,
            opportunity_id=contract.opportunity_id,
            status=contract.status,
            stage_history=[
                ApplicationStage.from_contract(stage)
                for stage in contract.stage_history
            ],
            artifact_refs=list(contract.artifact_refs),
            next_action=contract.next_action,
            next_action_at=(
                None
                if contract.next_action_at is None
                else _datetime(contract.next_action_at)
            ),
            freshness=ProjectionFreshness.from_contract(contract.freshness),
            created_at=_datetime(contract.created_at),
            updated_at=_datetime(contract.updated_at),
        )


@strawberry.type
class Relationship:
    relationship_id: str
    opportunity_id: str
    dex_contact_ref: str
    relevance_score: float | None
    relevance_summary: str | None
    freshness: ProjectionFreshness
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_contract(cls, contract: RelationshipV1) -> "Relationship":
        return cls(
            relationship_id=contract.relationship_id,
            opportunity_id=contract.opportunity_id,
            dex_contact_ref=contract.dex_contact_ref,
            relevance_score=(
                None
                if contract.relevance_score is None
                else float(contract.relevance_score)
            ),
            relevance_summary=contract.relevance_summary,
            freshness=ProjectionFreshness.from_contract(contract.freshness),
            created_at=_datetime(contract.created_at),
            updated_at=_datetime(contract.updated_at),
        )


@strawberry.type
class Outreach:
    outreach_id: str
    opportunity_id: str
    relationship_id: str | None
    status: str
    channel: str
    message_commitment: str
    approval_contract_id: str | None
    sent_evidence_ref: str | None
    freshness: ProjectionFreshness
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_projection(cls, projection: ProjectedOutreach) -> "Outreach":
        contract = projection.item
        return cls(
            outreach_id=contract.outreach_id,
            opportunity_id=contract.opportunity_id,
            relationship_id=contract.relationship_id,
            status=contract.status,
            channel=contract.channel,
            message_commitment=contract.message_commitment,
            approval_contract_id=contract.approval_contract_id,
            sent_evidence_ref=contract.sent_evidence_ref,
            freshness=ProjectionFreshness.from_contract(projection.freshness),
            created_at=_datetime(contract.created_at),
            updated_at=_datetime(contract.updated_at),
        )


@strawberry.type
class ApprovalEvidence:
    approval_id: str
    outreach_id: str
    message_commitment: str
    channel: str
    approved_by: str
    issued_at: datetime
    expires_at: datetime
    status: str

    @classmethod
    def from_projection(
        cls,
        projection: ApprovalEvidenceProjection,
    ) -> "ApprovalEvidence":
        return cls(
            approval_id=projection.approval_id,
            outreach_id=projection.outreach_id,
            message_commitment=projection.message_commitment,
            channel=projection.channel,
            approved_by=projection.approved_by,
            issued_at=_datetime(projection.issued_at),
            expires_at=_datetime(projection.expires_at),
            status=projection.status,
        )


@strawberry.type
class ExecutionReceiptEvidence:
    receipt_id: str
    operation_id: str
    event_id: str
    status: str
    reason_code: str | None
    payload: JSON
    receipt_hash: str
    created_at: datetime
    completed_at: datetime
    proof_status: str

    @classmethod
    def from_projection(
        cls,
        projection: ExecutionReceiptEvidenceProjection,
    ) -> "ExecutionReceiptEvidence":
        receipt = projection.receipt
        return cls(
            receipt_id=receipt.receipt_id,
            operation_id=projection.operation_id,
            event_id=receipt.event_id,
            status=receipt.status,
            reason_code=receipt.reason_code,
            payload=receipt.to_dict(),
            receipt_hash=projection.receipt_hash,
            created_at=_datetime(projection.created_at),
            completed_at=_datetime(projection.completed_at),
            proof_status=projection.proof_status,
        )


@strawberry.type
class OpportunityPage:
    items: list[Opportunity]
    freshness: ProjectionFreshness | None
    next_cursor: str | None

    @classmethod
    def from_page(
        cls,
        page: ProjectionPage[OpportunityV1],
        *,
        organization_ids: dict[str, str | None] | None = None,
    ) -> "OpportunityPage":
        org_map = organization_ids or {}
        return cls(
            items=[
                Opportunity.from_contract(
                    item,
                    organization_id=org_map.get(item.opportunity_id),
                )
                for item in page.items
            ],
            freshness=(
                None
                if page.freshness is None
                else ProjectionFreshness.from_contract(page.freshness)
            ),
            next_cursor=page.next_cursor,
        )


@strawberry.type
class ApplicationPage:
    items: list[Application]
    freshness: ProjectionFreshness | None
    next_cursor: str | None

    @classmethod
    def from_page(
        cls,
        page: ProjectionPage[ApplicationV1],
    ) -> "ApplicationPage":
        return cls(
            items=[Application.from_contract(item) for item in page.items],
            freshness=(
                None
                if page.freshness is None
                else ProjectionFreshness.from_contract(page.freshness)
            ),
            next_cursor=page.next_cursor,
        )


@strawberry.type
class RelationshipPage:
    items: list[Relationship]
    freshness: ProjectionFreshness | None
    next_cursor: str | None

    @classmethod
    def from_page(
        cls,
        page: ProjectionPage[RelationshipV1],
    ) -> "RelationshipPage":
        return cls(
            items=[Relationship.from_contract(item) for item in page.items],
            freshness=(
                None
                if page.freshness is None
                else ProjectionFreshness.from_contract(page.freshness)
            ),
            next_cursor=page.next_cursor,
        )


@strawberry.type
class OutreachPage:
    items: list[Outreach]
    freshness: ProjectionFreshness | None
    next_cursor: str | None

    @classmethod
    def from_page(
        cls,
        page: ProjectionPage[ProjectedOutreach],
    ) -> "OutreachPage":
        return cls(
            items=[Outreach.from_projection(item) for item in page.items],
            freshness=(
                None
                if page.freshness is None
                else ProjectionFreshness.from_contract(page.freshness)
            ),
            next_cursor=page.next_cursor,
        )


# ===========================================================================
# Candidate Profile & Taxonomy Types
# ===========================================================================

@strawberry.type
class CandidateBioGQL:
    full_name: str
    headline: str
    summary: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: str = "Austin, TX"
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None

    @classmethod
    def from_pydantic(cls, bio: Any) -> "CandidateBioGQL":
        return cls(
            full_name=bio.full_name,
            headline=bio.headline,
            summary=bio.summary,
            email=bio.email,
            phone=bio.phone,
            location=bio.location,
            linkedin_url=bio.linkedin_url,
            github_url=bio.github_url,
            portfolio_url=bio.portfolio_url,
        )


@strawberry.type
class SkillItemGQL:
    name: str
    category: str
    tier: str
    years_experience: int
    keywords: list[str]
    description: str
    highlights: list[str]

    @classmethod
    def from_pydantic(cls, item: Any) -> "SkillItemGQL":
        return cls(
            name=item.name,
            category=item.category.value if hasattr(item.category, "value") else str(item.category),
            tier=item.tier.value if hasattr(item.tier, "value") else str(item.tier),
            years_experience=item.years_experience,
            keywords=list(item.keywords or []),
            description=item.description,
            highlights=list(item.highlights or []),
        )


@strawberry.type
class MLDepthSubdomainGQL:
    name: str
    experience_level: str
    years: int
    core_technologies: list[str]
    architectural_patterns: list[str]
    production_milestones: list[str]

    @classmethod
    def from_pydantic(cls, sub: Any) -> "MLDepthSubdomainGQL":
        return cls(
            name=sub.name,
            experience_level=sub.experience_level,
            years=sub.years,
            core_technologies=list(sub.core_technologies or []),
            architectural_patterns=list(sub.architectural_patterns or []),
            production_milestones=list(sub.production_milestones or []),
        )


@strawberry.type
class ProductionMLDepthGQL:
    llm_orchestration: MLDepthSubdomainGQL
    asr_tts_voice: MLDepthSubdomainGQL
    fine_tuning_adaptation: MLDepthSubdomainGQL
    embeddings_rag: MLDepthSubdomainGQL
    agent_loops_tooling: MLDepthSubdomainGQL
    inference_hardware: MLDepthSubdomainGQL
    llm_systems: list[str]
    agentic_orchestration: list[str]
    voice_speech_ai: list[str]
    rag_vector_search: list[str]
    fine_tuning_evals: list[str]
    edge_quantization: list[str]

    @classmethod
    def from_pydantic(cls, ml: Any) -> "ProductionMLDepthGQL":
        return cls(
            llm_orchestration=MLDepthSubdomainGQL.from_pydantic(ml.llm_orchestration),
            asr_tts_voice=MLDepthSubdomainGQL.from_pydantic(ml.asr_tts_voice),
            fine_tuning_adaptation=MLDepthSubdomainGQL.from_pydantic(ml.fine_tuning_adaptation),
            embeddings_rag=MLDepthSubdomainGQL.from_pydantic(ml.embeddings_rag),
            agent_loops_tooling=MLDepthSubdomainGQL.from_pydantic(ml.agent_loops_tooling),
            inference_hardware=MLDepthSubdomainGQL.from_pydantic(ml.inference_hardware),
            llm_systems=list(ml.llm_systems or []),
            agentic_orchestration=list(ml.agentic_orchestration or []),
            voice_speech_ai=list(ml.voice_speech_ai or []),
            rag_vector_search=list(ml.rag_vector_search or []),
            fine_tuning_evals=list(ml.fine_tuning_evals or []),
            edge_quantization=list(ml.edge_quantization or []),
        )


@strawberry.type
class WorkExperienceGQL:
    company: str
    role: str
    start_date: str
    end_date: Optional[str] = None
    is_current: bool = False
    location: str = "Austin, TX"
    remote_type: str = "remote"
    summary: str = ""
    key_achievements: list[str]
    technologies: list[str]

    @classmethod
    def from_pydantic(cls, exp: Any) -> "WorkExperienceGQL":
        return cls(
            company=exp.company,
            role=exp.role,
            start_date=exp.start_date,
            end_date=exp.end_date,
            is_current=exp.is_current,
            location=exp.location,
            remote_type=exp.remote_type,
            summary=exp.summary,
            key_achievements=list(exp.key_achievements or []),
            technologies=list(exp.technologies or []),
        )


@strawberry.type
class EducationGQL:
    institution: str
    degree: str
    field_of_study: str
    graduation_year: Optional[int] = None
    notes: Optional[str] = None

    @classmethod
    def from_pydantic(cls, edu: Any) -> "EducationGQL":
        return cls(
            institution=edu.institution,
            degree=edu.degree,
            field_of_study=edu.field_of_study,
            graduation_year=edu.graduation_year,
            notes=edu.notes,
        )


@strawberry.type
class ProjectHighlightGQL:
    name: str
    role: str
    description: str
    url: Optional[str] = None
    technologies: list[str]

    @classmethod
    def from_pydantic(cls, proj: Any) -> "ProjectHighlightGQL":
        return cls(
            name=proj.name,
            role=proj.role,
            description=proj.description,
            url=proj.url,
            technologies=list(proj.technologies or []),
        )


@strawberry.type
class CompensationExpectationsGQL:
    min_base: int
    target_total: int
    min_total: int
    base_minimum_usd: int
    target_total_comp_usd: int
    minimum_total_comp_usd: int
    equity_preference: str
    currency: str
    employment_type: str
    location_preference: str

    @classmethod
    def from_pydantic(cls, comp: Any) -> "CompensationExpectationsGQL":
        return cls(
            min_base=comp.min_base,
            target_total=comp.target_total,
            min_total=comp.min_total,
            base_minimum_usd=comp.base_minimum_usd,
            target_total_comp_usd=comp.target_total_comp_usd,
            minimum_total_comp_usd=comp.minimum_total_comp_usd,
            equity_preference=comp.equity_preference,
            currency=comp.currency,
            employment_type=comp.employment_type,
            location_preference=comp.location_preference,
        )


@strawberry.type
class TargetRoleConfigGQL:
    target_roles: list[str]
    target_role_families: list[str]
    target_domains: list[str]
    seniority_band: str
    location_preference: str
    remote_preference: str

    @classmethod
    def from_pydantic(cls, trc: Any) -> "TargetRoleConfigGQL":
        return cls(
            target_roles=list(trc.target_roles or []),
            target_role_families=list(trc.target_role_families or []),
            target_domains=list(trc.target_domains or []),
            seniority_band=trc.seniority_band,
            location_preference=trc.location_preference,
            remote_preference=trc.remote_preference,
        )


@strawberry.type
class CandidateProfileGQL:
    candidate_name: str
    title: str
    resume_text: str
    bio: CandidateBioGQL
    target_roles: list[str]
    target_domains: list[str]
    target_role_families: list[str]
    target_role_config: TargetRoleConfigGQL
    compensation: CompensationExpectationsGQL
    skills: list[SkillItemGQL]
    production_ml: ProductionMLDepthGQL
    experience: list[WorkExperienceGQL]
    education: list[EducationGQL]
    projects: list[ProjectHighlightGQL]
    expert_skills: list[SkillItemGQL]
    advanced_skills: list[SkillItemGQL]
    updated_at: datetime

    @classmethod
    def from_pydantic(cls, prof: Any) -> "CandidateProfileGQL":
        all_skills = [SkillItemGQL.from_pydantic(s) for s in prof.skills.values()]
        return cls(
            candidate_name=prof.candidate_name,
            title=prof.title,
            resume_text=prof.resume_text,
            bio=CandidateBioGQL.from_pydantic(prof.bio),
            target_roles=list(prof.target_roles or []),
            target_domains=list(prof.target_domains or []),
            target_role_families=list(prof.target_role_families or []),
            target_role_config=TargetRoleConfigGQL.from_pydantic(prof.target_role_config),
            compensation=CompensationExpectationsGQL.from_pydantic(prof.compensation),
            skills=all_skills,
            production_ml=ProductionMLDepthGQL.from_pydantic(prof.production_ml),
            experience=[WorkExperienceGQL.from_pydantic(e) for e in (prof.experience or [])],
            education=[EducationGQL.from_pydantic(e) for e in (prof.education or [])],
            projects=[ProjectHighlightGQL.from_pydantic(p) for p in (prof.projects or [])],
            expert_skills=[SkillItemGQL.from_pydantic(s) for s in prof.expert_skills],
            advanced_skills=[SkillItemGQL.from_pydantic(s) for s in prof.advanced_skills],
            updated_at=_as_utc(prof.updated_at),
        )


# ===========================================================================
# Leads & Organizations Types
# ===========================================================================

@strawberry.type
class Lead:
    id: str
    source_board: str
    external_id: Optional[str]
    employer: str
    organization_id: Optional[str]
    title: str
    location: Optional[str]
    remote_type: str
    salary_min: Optional[int]
    salary_max: Optional[int]
    salary_currency: str
    url: Optional[str]
    description: Optional[str]
    requirements: list[str]
    fit_score: Optional[float]
    match_breakdown: JSON
    risk_flags: list[str]
    state: str
    converted_opportunity_id: Optional[str]
    freshness: Optional[ProjectionFreshness]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_db(
        cls,
        row: Any,
        checkpoint: Optional[ProjectionFreshnessV1] = None,
    ) -> "Lead":
        freshness_obj = None
        if checkpoint is not None:
            freshness_obj = ProjectionFreshness(
                source_event_id=row.source_event_id,
                source_event_position=row.source_event_position,
                projected_at=_as_utc(row.projected_at),
                lag_ms=float(checkpoint.lag_ms),
                status=checkpoint.status,
            )
        return cls(
            id=row.id,
            source_board=row.source_board,
            external_id=row.external_id,
            employer=row.employer,
            organization_id=row.organization_id,
            title=row.title,
            location=row.location,
            remote_type=row.remote_type,
            salary_min=row.salary_min,
            salary_max=row.salary_max,
            salary_currency=row.salary_currency,
            url=row.url,
            description=row.description,
            requirements=list(row.requirements or []),
            fit_score=float(row.fit_score) if row.fit_score is not None else None,
            match_breakdown=dict(row.match_breakdown or {}),
            risk_flags=list(row.risk_flags or []),
            state=row.state,
            converted_opportunity_id=row.converted_opportunity_id,
            freshness=freshness_obj,
            created_at=_as_utc(row.created_at),
            updated_at=_as_utc(row.updated_at),
        )


@strawberry.type
class LeadPage:
    items: list[Lead]
    freshness: Optional[ProjectionFreshness]
    next_cursor: Optional[str]

    @classmethod
    def from_page(cls, page: ProjectionPage[Any]) -> "LeadPage":
        return cls(
            items=[Lead.from_db(item, page.freshness) for item in page.items],
            freshness=(
                None
                if page.freshness is None
                else ProjectionFreshness.from_contract(page.freshness)
            ),
            next_cursor=page.next_cursor,
        )


@strawberry.type
class Organization:
    id: str
    name: str
    domain: Optional[str]
    industry: Optional[str]
    size: Optional[str]
    advocacy_rating: Optional[float]
    notes: Optional[str]
    freshness: Optional[ProjectionFreshness]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_db(
        cls,
        row: Any,
        checkpoint: Optional[ProjectionFreshnessV1] = None,
    ) -> "Organization":
        freshness_obj = None
        if checkpoint is not None:
            freshness_obj = ProjectionFreshness(
                source_event_id=row.source_event_id,
                source_event_position=row.source_event_position,
                projected_at=_as_utc(row.projected_at),
                lag_ms=float(checkpoint.lag_ms),
                status=checkpoint.status,
            )
        return cls(
            id=row.id,
            name=row.name,
            domain=row.domain,
            industry=row.industry,
            size=row.size,
            advocacy_rating=float(row.advocacy_rating) if row.advocacy_rating is not None else None,
            notes=row.notes,
            freshness=freshness_obj,
            created_at=_as_utc(row.created_at),
            updated_at=_as_utc(row.updated_at),
        )


@strawberry.type
class OrganizationPage:
    items: list[Organization]
    freshness: Optional[ProjectionFreshness]
    next_cursor: Optional[str]

    @classmethod
    def from_page(cls, page: ProjectionPage[Any]) -> "OrganizationPage":
        return cls(
            items=[Organization.from_db(item, page.freshness) for item in page.items],
            freshness=(
                None
                if page.freshness is None
                else ProjectionFreshness.from_contract(page.freshness)
            ),
            next_cursor=page.next_cursor,
        )


# ===========================================================================
# Contacts Types
# ===========================================================================

@strawberry.type
class CommunicationHistoryEntryGQL:
    id: str
    timestamp: str
    channel: str
    direction: str
    subject: str
    summary: str
    message_id: Optional[str] = None
    evidence_ref: Optional[str] = None
    thread_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CommunicationHistoryEntryGQL":
        return cls(
            id=data.get("id", ""),
            timestamp=data.get("timestamp", ""),
            channel=data.get("channel", "gmail"),
            direction=data.get("direction", "outbound"),
            subject=data.get("subject", ""),
            summary=data.get("summary", ""),
            message_id=data.get("message_id"),
            evidence_ref=data.get("evidence_ref"),
            thread_id=data.get("thread_id"),
        )


@strawberry.type
class ContactGQL:
    id: str
    name: str
    email: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    last_contacted: Optional[datetime] = None
    ai_value: Optional[float] = None
    ai_reason: Optional[str] = None
    outreach_strategy: Optional[str] = None
    suggested_timing: Optional[str] = None
    last_analyzed: Optional[datetime] = None
    advocacy_score: Optional[float] = None
    organization_id: Optional[str] = None
    crm_notes: Optional[str] = None
    communication_history: list[CommunicationHistoryEntryGQL]
    linkedin_url: Optional[str] = None
    relationship_tier: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_db(cls, row: Any) -> "ContactGQL":
        history = [
            CommunicationHistoryEntryGQL.from_dict(item)
            for item in (row.communication_history or [])
            if isinstance(item, dict)
        ]
        return cls(
            id=row.id,
            name=row.name,
            email=row.email,
            company=row.company,
            job_title=row.job_title,
            phone=row.phone,
            notes=row.notes,
            last_contacted=_as_utc(row.last_contacted),
            ai_value=float(row.ai_value) if row.ai_value is not None else None,
            ai_reason=row.ai_reason,
            outreach_strategy=row.outreach_strategy,
            suggested_timing=row.suggested_timing,
            last_analyzed=_as_utc(row.last_analyzed),
            advocacy_score=float(row.advocacy_score) if row.advocacy_score is not None else None,
            organization_id=row.organization_id,
            crm_notes=row.crm_notes,
            communication_history=history,
            linkedin_url=row.linkedin_url,
            relationship_tier=row.relationship_tier,
            created_at=_as_utc(row.created_at) or datetime.now(timezone.utc),
            updated_at=_as_utc(row.updated_at) or datetime.now(timezone.utc),
        )


@strawberry.type
class ContactPageGQL:
    items: list[ContactGQL]
    freshness: Optional[ProjectionFreshness] = None
    next_cursor: Optional[str] = None
    total_count: Optional[int] = None


# ===========================================================================
# Copilot Next Best Actions & Recruiter Replies Types
# ===========================================================================

@strawberry.type
class NextBestActionGQL:
    id: str
    urgency: str
    action_type: str
    title: str
    description: str
    entity_type: str
    entity_id: str
    score: float
    due_date: Optional[datetime] = None
    action_url: str
    metadata: JSON
    created_at: datetime

    @classmethod
    def from_pydantic(cls, nba: Any) -> "NextBestActionGQL":
        return cls(
            id=nba.id,
            urgency=nba.urgency.value if hasattr(nba.urgency, "value") else str(nba.urgency),
            action_type=nba.action_type.value if hasattr(nba.action_type, "value") else str(nba.action_type),
            title=nba.title,
            description=nba.description,
            entity_type=nba.entity_type,
            entity_id=nba.entity_id,
            score=float(nba.score),
            due_date=_as_utc(nba.due_date),
            action_url=nba.action_url,
            metadata=dict(nba.metadata or {}),
            created_at=_as_utc(nba.created_at) or datetime.now(timezone.utc),
        )


@strawberry.input
class InboundMessageContextInput:
    subject: str
    body_text: str
    sender_email: Optional[str] = None
    sender_email_or_handle: Optional[str] = None
    sender_name: Optional[str] = None
    message_id: Optional[str] = None
    received_at: Optional[str] = None
    channel: Optional[str] = "gmail"
    company_mentioned: Optional[str] = None
    role_mentioned: Optional[str] = None
    salary_mentioned: Optional[str] = None
    tech_stack_mentioned: Optional[list[str]] = None
    calendar_slots: Optional[list[str]] = None


@strawberry.type
class RecruiterPillReplyGQL:
    pill_type: str
    label: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    calendar_slots_injected: list[str]
    requires_approval: bool
    context_summary: str

    @classmethod
    def from_pydantic(cls, pill: Any) -> "RecruiterPillReplyGQL":
        return cls(
            pill_type=pill.pill_type.value if hasattr(pill.pill_type, "value") else str(pill.pill_type),
            label=pill.label,
            subject=pill.subject,
            body_text=pill.body_text,
            body_html=pill.body_html,
            calendar_slots_injected=list(pill.calendar_slots_injected or []),
            requires_approval=pill.requires_approval,
            context_summary=pill.context_summary,
        )


@strawberry.type
class RecruiterPillSetGQL:
    incoming_message_id: str
    sender_name: str
    sender_email_or_handle: str
    role_mentioned: Optional[str] = None
    company_mentioned: Optional[str] = None
    pills: list[RecruiterPillReplyGQL]
    generated_at: datetime

    @classmethod
    def from_pydantic(cls, pill_set: Any) -> "RecruiterPillSetGQL":
        return cls(
            incoming_message_id=pill_set.incoming_message_id,
            sender_name=pill_set.sender_name,
            sender_email_or_handle=pill_set.sender_email_or_handle,
            role_mentioned=pill_set.role_mentioned,
            company_mentioned=pill_set.company_mentioned,
            pills=[RecruiterPillReplyGQL.from_pydantic(p) for p in pill_set.pills],
            generated_at=_as_utc(pill_set.generated_at) or datetime.now(timezone.utc),
        )


# ===========================================================================
# Calendar & Availability Types
# ===========================================================================

@strawberry.type
class CalendarEventGQL:
    id: str
    summary: str
    description: Optional[str] = None
    start: datetime
    end: datetime
    is_all_day: bool = False
    status: str = "confirmed"
    transparency: str = "opaque"
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    attendees: list[str]
    organizer_email: Optional[str] = None
    is_busy: bool = True

    @classmethod
    def from_pydantic(cls, evt: Any) -> "CalendarEventGQL":
        return cls(
            id=evt.id,
            summary=evt.summary,
            description=evt.description,
            start=_as_utc(evt.start),
            end=_as_utc(evt.end),
            is_all_day=evt.is_all_day,
            status=evt.status.value if hasattr(evt.status, "value") else str(evt.status),
            transparency=evt.transparency.value if hasattr(evt.transparency, "value") else str(evt.transparency),
            location=evt.location,
            meeting_link=evt.meeting_link,
            attendees=list(evt.attendees or []),
            organizer_email=evt.organizer_email,
            is_busy=evt.is_busy,
        )


@strawberry.type
class TimeSlotGQL:
    start: datetime
    end: datetime
    duration_minutes: int
    day_key: str
    formatted_ct: str

    @classmethod
    def from_pydantic(cls, slot: Any) -> "TimeSlotGQL":
        return cls(
            start=_as_utc(slot.start),
            end=_as_utc(slot.end),
            duration_minutes=slot.duration_minutes,
            day_key=slot.day_key,
            formatted_ct=slot.formatted_ct,
        )


@strawberry.type
class DailyAvailabilityGQL:
    date_str: str
    day_name: str
    slots_30min: list[TimeSlotGQL]
    slots_45min: list[TimeSlotGQL]

    @classmethod
    def from_pydantic(cls, daily: Any) -> "DailyAvailabilityGQL":
        return cls(
            date_str=daily.date_str,
            day_name=daily.day_name,
            slots_30min=[TimeSlotGQL.from_pydantic(s) for s in daily.slots_30min],
            slots_45min=[TimeSlotGQL.from_pydantic(s) for s in daily.slots_45min],
        )


@strawberry.type
class AvailabilityResultGQL:
    start_date: str
    end_date: str
    slots: list[TimeSlotGQL]
    daily: list[DailyAvailabilityGQL]
    formatted_summary: str


# ===========================================================================
# Outbox Messages Types
# ===========================================================================

@strawberry.type
class MessageGQL:
    id: str
    channel: str
    direction: str
    recipient_address: str
    recipient_name: Optional[str] = None
    recipient_id: Optional[str] = None
    subject: str
    body_text: str
    body_html: Optional[str] = None
    thread_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    references: Optional[str] = None
    status: str
    message_commitment: str
    approval_id: Optional[str] = None
    sent_evidence_ref: Optional[str] = None
    external_message_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None

    @classmethod
    def from_pydantic(cls, msg: Any) -> "MessageGQL":
        return cls(
            id=msg.id,
            channel=msg.channel.value if hasattr(msg.channel, "value") else str(msg.channel),
            direction=msg.direction.value if hasattr(msg.direction, "value") else str(msg.direction),
            recipient_address=msg.recipient_address,
            recipient_name=msg.recipient_name,
            recipient_id=msg.recipient_id,
            subject=msg.subject,
            body_text=msg.body_text,
            body_html=msg.body_html,
            thread_id=msg.thread_id,
            in_reply_to=msg.in_reply_to,
            references=msg.references,
            status=msg.status.value if hasattr(msg.status, "value") else str(msg.status),
            message_commitment=msg.message_commitment or "",
            approval_id=msg.approval_id,
            sent_evidence_ref=msg.sent_evidence_ref,
            external_message_id=msg.external_message_id,
            error_message=msg.error_message,
            created_at=_as_utc(msg.created_at) or datetime.now(timezone.utc),
            sent_at=_as_utc(msg.sent_at),
        )


@strawberry.type
class MessagePageGQL:
    items: list[MessageGQL]
    freshness: Optional[ProjectionFreshness] = None
    next_cursor: Optional[str] = None


# ===========================================================================
# Sovereign Voice & Interview Debrief Types
# ===========================================================================

@strawberry.type
class TranscriptSegmentGQL:
    offset_ms: int
    speaker: str
    role: str
    text: str
    confidence: float

    @classmethod
    def from_pydantic(cls, seg: Any) -> "TranscriptSegmentGQL":
        return cls(
            offset_ms=seg.offset_ms,
            speaker=seg.speaker,
            role=seg.role.value if hasattr(seg.role, "value") else str(seg.role),
            text=seg.text,
            confidence=float(seg.confidence),
        )


@strawberry.type
class InterviewMetadataGQL:
    company: str
    role: str
    round_type: str
    interview_date: str
    interviewer_names: list[str]
    interviewer_titles: list[str]
    duration_minutes: int
    audio_ref: Optional[str] = None
    opportunity_id: Optional[str] = None
    contact_ids: list[str]

    @classmethod
    def from_pydantic(cls, meta: Any) -> "InterviewMetadataGQL":
        return cls(
            company=meta.company,
            role=meta.role,
            round_type=meta.round_type,
            interview_date=meta.interview_date,
            interviewer_names=list(meta.interviewer_names or []),
            interviewer_titles=list(meta.interviewer_titles or []),
            duration_minutes=meta.duration_minutes,
            audio_ref=meta.audio_ref,
            opportunity_id=meta.opportunity_id,
            contact_ids=list(meta.contact_ids or []),
        )


@strawberry.type
class QuestionAnswerPairGQL:
    id: str
    question: str
    asked_by: str
    category: str
    answer_summary: str
    key_points_mentioned: list[str]
    effectiveness_score: float
    follow_up_needed: bool

    @classmethod
    def from_pydantic(cls, qa: Any) -> "QuestionAnswerPairGQL":
        return cls(
            id=qa.id,
            question=qa.question,
            asked_by=qa.asked_by,
            category=qa.category,
            answer_summary=qa.answer_summary,
            key_points_mentioned=list(qa.key_points_mentioned or []),
            effectiveness_score=float(qa.effectiveness_score),
            follow_up_needed=qa.follow_up_needed,
        )


@strawberry.type
class FitAssessmentGQL:
    overall_score: float
    technical_alignment: str
    leadership_alignment: str
    compensation_alignment: str
    green_flags: list[str]
    red_flags: list[str]
    culture_notes: str
    recommendation: str

    @classmethod
    def from_pydantic(cls, fit: Any) -> "FitAssessmentGQL":
        return cls(
            overall_score=float(fit.overall_score),
            technical_alignment=fit.technical_alignment,
            leadership_alignment=fit.leadership_alignment,
            compensation_alignment=fit.compensation_alignment,
            green_flags=list(fit.green_flags or []),
            red_flags=list(fit.red_flags or []),
            culture_notes=fit.culture_notes,
            recommendation=fit.recommendation,
        )


@strawberry.type
class InterviewActionItemGQL:
    id: str
    title: str
    action_type: str
    priority: str
    due_date: str
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    draft_content: Optional[str] = None
    opportunity_id: Optional[str] = None
    is_completed: bool = False

    @classmethod
    def from_pydantic(cls, act: Any) -> "InterviewActionItemGQL":
        return cls(
            id=act.id,
            title=act.title,
            action_type=act.action_type,
            priority=act.priority,
            due_date=act.due_date,
            recipient_name=act.recipient_name,
            recipient_email=act.recipient_email,
            draft_content=act.draft_content,
            opportunity_id=act.opportunity_id,
            is_completed=act.is_completed,
        )


@strawberry.type
class InterviewDebriefGQL:
    id: str
    created_at: datetime
    metadata: InterviewMetadataGQL
    executive_summary: str
    questions_and_answers: list[QuestionAnswerPairGQL]
    fit_assessment: FitAssessmentGQL
    action_items: list[InterviewActionItemGQL]
    raw_transcript: str
    transcript_segments: list[TranscriptSegmentGQL]

    @classmethod
    def from_pydantic(cls, debrief: Any) -> "InterviewDebriefGQL":
        return cls(
            id=debrief.id,
            created_at=_as_utc(debrief.created_at) or datetime.now(timezone.utc),
            metadata=InterviewMetadataGQL.from_pydantic(debrief.metadata),
            executive_summary=debrief.executive_summary,
            questions_and_answers=[
                QuestionAnswerPairGQL.from_pydantic(qa)
                for qa in (debrief.questions_and_answers or [])
            ],
            fit_assessment=FitAssessmentGQL.from_pydantic(debrief.fit_assessment),
            action_items=[
                InterviewActionItemGQL.from_pydantic(act)
                for act in (debrief.action_items or [])
            ],
            raw_transcript=debrief.raw_transcript or "",
            transcript_segments=[
                TranscriptSegmentGQL.from_pydantic(seg)
                for seg in (debrief.transcript_segments or [])
            ],
        )


@strawberry.type
class InterviewDebriefPageGQL:
    items: list[InterviewDebriefGQL]
    freshness: Optional[ProjectionFreshness] = None
    next_cursor: Optional[str] = None
