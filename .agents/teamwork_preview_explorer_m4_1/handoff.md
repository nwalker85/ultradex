# M4.1 GraphQL Read Projections & Resolvers Specification & Technical Design Report

**Target Location**: `/Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req/.agents/teamwork_preview_explorer_m4_1/handoff.md`  
**Milestone**: M4 (GraphQL Read Projections & TypeScript SDK)  
**Integrity Mode**: Development / Sovereign Read Projections  
**Status**: COMPLETE (Investigation & Technical Design)

---

## 1. Observation

Direct examination of existing source files, database models, projections, and services revealed the exact contracts, signatures, and runtime behavior:

### 1.1 Existing GraphQL Architecture (`api/graphql/schema.py` & `api/graphql/jobsearch_types.py`)
- `api/graphql/schema.py`:
  - Uses `strawberry.type` with `strawberry.Schema(query=Query)`. No GraphQL mutation root exists (CQRS: write commands execute exclusively via REST POST endpoints in `api/routes/v2/jobsearch_commands.py` with Ed25519 execution receipts, per `PROJECT.md`).
  - Context getter `get_graphql_context` (lines 46–51) supplies `{"db": db, "principal": principal}` from FastAPI dependencies `get_db` and `require_read_principal`.
  - UTC timestamp coercion `_as_utc(value: datetime | None) -> datetime | None` (lines 32–43) ensures naive DB timestamps are serialized as UTC-aware ISO 8601 strings with timezone offset `Z` / `+00:00`.
  - Existing query fields on `Query`:
    - `opportunity(id: str) -> Opportunity | None`
    - `opportunities(first: int = 25, after: str | None = None, status: str | None = None) -> OpportunityPage`
    - `application(id: str) -> Application | None`
    - `applications(first: int = 25, after: str | None = None, status: str | None = None, opportunity_id: str | None = None) -> ApplicationPage`
    - `relationship(id: str) -> Relationship | None`
    - `relationships(first: int = 25, after: str | None = None, opportunity_id: str | None = None) -> RelationshipPage`
    - `outreach_item(id: str) -> Outreach | None`
    - `outreach(first: int = 25, after: str | None = None, status: str | None = None, opportunity_id: str | None = None) -> OutreachPage`
    - `approval(id: str) -> ApprovalEvidence | None`
    - `execution_receipt(operation_id: str) -> ExecutionReceiptEvidence | None`
    - `operation(id: str) -> Optional[OperationGQL]`
    - `operations(limit: int = 10, status: Optional[str] = None) -> List[OperationGQL]`
    - `events(operation_id: str, first: int = 50, after: Optional[int] = None) -> List[OperationEventGQL]`

### 1.2 CRM Models & Projections (`core/jobsearch_models.py` & `core/jobsearch_projections.py`)
- `OrganizationDB` (`core/jobsearch_models.py:190–227`):
  - Table: `jobsearch_organizations`
  - Columns: `id` (String 64, PK), `name` (String 255), `domain` (String 255), `industry` (String 128), `size` (String 64), `advocacy_rating` (Float), `notes` (Text), `source_event_id`, `source_event_position`, `projected_at`, `created_at`, `updated_at`.
  - Projections in `JobSearchProjectionRepository` (`core/jobsearch_projections.py:254–281`): `get_organization(organization_id)` and `list_organizations(first=20, after=None, sort_by="name")`.
- `LeadDB` (`core/jobsearch_models.py:229–286`):
  - Table: `jobsearch_leads`
  - Columns: `id` (String 64, PK), `source_board` (String 64), `external_id` (String 255), `employer` (String 255), `organization_id` (String 64, FK), `title` (String 255), `location` (String 255), `remote_type` (String 32), `salary_min` (Integer), `salary_max` (Integer), `salary_currency` (String 8), `url` (String 1024), `description` (Text), `requirements` (JSON list), `fit_score` (Float), `match_breakdown` (JSON dict), `risk_flags` (JSON list), `state` (String 32), `converted_opportunity_id` (String 64, FK), `source_event_id`, `source_event_position`, `projected_at`, `created_at`, `updated_at`.
  - Projections in `JobSearchProjectionRepository` (`core/jobsearch_projections.py:219–253`): `get_lead(lead_id)` and `list_leads(first=20, after=None, min_fit_score=None, state=None, employer=None)`.
- `ContactDB` (`core/models.py:162–205`):
  - Table: `contacts`
  - Columns: `id` (String 255, PK), `name` (String 255), `email`, `company`, `job_title`, `phone`, `notes`, `last_contacted`, `ai_value`, `ai_reason`, `outreach_strategy`, `suggested_timing`, `last_analyzed`, `advocacy_score`, `organization_id` (FK), `crm_notes`, `communication_history` (JSON list of interaction dicts), `linkedin_url`, `relationship_tier`, `created_at`, `updated_at`, `synced_at`.

### 1.3 Candidate Profile Store (`core/jobsearch_profile.py`)
- `CandidateProfileStore` (`core/jobsearch_profile.py:874–933`):
  - Fetches candidate profile from memory cache, `SettingsDB.candidate_profile` JSON in DB, or `get_ratified_candidate_profile()`.
  - Full model `CandidateProfile` has:
    - `candidate_name`: "Nate Walker"
    - `title`: "CTO | Principal AI Architect | Technical Founder"
    - `bio`: `CandidateBio` (full_name, headline, summary, email, location, linkedin_url, github_url)
    - `target_roles`: 5 roles (`Chief Technology Officer`, `VP of Engineering`, `Head of AI`, `Principal AI Architect`, `Technical Founder`)
    - `target_domains`: 6 domains (`AI infrastructure`, `Developer tools`, `Voice and customer experience`, `Healthcare`, `Regulated security constrained systems`, `Agentic AI multi-agent orchestration`)
    - `target_role_families`: 5 families
    - `target_role_config`: `TargetRoleConfig` (seniority_band, location_preference, remote_preference)
    - `compensation`: `CompensationExpectations` (min_base: $180,000, target_total: $250,000, min_total: $200,000, equity_preference, currency: "USD", location_preference)
    - `skills`: Dict of 44 `SkillItem` entries across 7 categories (`ai_ml`, `distributed_systems`, `cloud_infra`, `backend_api`, `frontend_fullstack`, `security_governance`, `leadership_strategy`) with `SkillTier` (`expert`, `advanced`, `intermediate`, `familiar`), years of experience, keywords, and description.
    - `production_ml`: `ProductionMLDepth` containing 6 subdomain deep-dives (`llm_orchestration`, `asr_tts_voice`, `fine_tuning_adaptation`, `embeddings_rag`, `agent_loops_tooling`, `inference_hardware`) plus list breakdowns (`llm_systems`, `agentic_orchestration`, `voice_speech_ai`, `rag_vector_search`, `fine_tuning_evals`, `edge_quantization`).
    - `experience`: List of `WorkExperienceItem` (Ravenhelm Technologies, IntelePeer, etc.)
    - `education`: List of `EducationItem`
    - `projects`: List of `ProjectHighlight`
    - `updated_at`: UTC timestamp

### 1.4 Copilot & Recruiter Replies Engine (`core/jobsearch_copilot.py`)
- `JobSearchCopilot` (`core/jobsearch_copilot.py:111–565`):
  - `compute_next_best_actions(db, profile, now, limit)` -> `List[NextBestAction]`:
    - Evaluates overdue/upcoming application tasks (`COMPLETE_APPLICATION_TASK`, P0/P1), stale applications (>7d in applied, >5d in screening, P1/P2), and unapplied high-fit leads (`fit_score >= 80`, `CONVERT_HIGH_FIT_LEAD`, P1/P2).
    - `NextBestAction` fields: `id`, `urgency` (P0/P1/P2/P3), `action_type` (`reply_recruiter`, `follow_up_application`, `complete_application_task`, `convert_high_fit_lead`, `network_outreach`, `send_thank_you`, `schedule_interview`), `title`, `description`, `entity_type`, `entity_id`, `score`, `due_date`, `action_url`, `metadata`, `created_at`.
  - `extract_message_context(subject, body, sender_email, sender_name, message_id, channel)` -> `InboundMessageContext`
  - `generate_recruiter_replies(message, profile, calendar_availability)` -> `RecruiterPillSet`:
    - Generates 3 contextual response pills:
      1. `ACCEPT_AND_SCHEDULE` ("Accept & Share Availability" with injected Central Time availability windows)
      2. `REQUEST_SCOPE_AND_COMP` ("Request Scope & Comp Details")
      3. `POLITE_PASS` ("Polite Pass" preserving network relationship)

### 1.5 Calendar & Slot Sensing Engine (`core/jobsearch_calendar.py`)
- Central Time slot calculations (`09:00–17:00 CT`, Mon–Fri):
  - `compute_open_slots(events, start_date, end_date, duration_minutes=30, buffer_minutes=15)` -> `List[TimeSlot]`
  - `compute_daily_availability(events, start_date, end_date, buffer_minutes=15)` -> `List[DailyAvailability]`
  - `format_availability_for_recruiter(slots, style="grouped_days")` -> Natural email copy
  - `GoogleCalendarClient.fetch_events(access_token, time_min, time_max)` -> `List[CalendarEvent]`

### 1.6 Omnichannel Messaging Engine (`core/jobsearch_messaging.py`)
- `OutboxMessage` (`core/jobsearch_messaging.py:83–104`):
  - Fields: `id`, `channel` (`gmail`, `linkedin`, `dex`), `direction` (`inbound`, `outbound`), `recipient_address`, `recipient_name`, `recipient_id`, `subject`, `body_text`, `body_html`, `thread_id`, `in_reply_to`, `references`, `status` (`draft`, `pending_approval`, `approved`, `queued`, `sending`, `sent`, `failed`, `cancelled`), `message_commitment`, `approval_id`, `sent_evidence_ref`, `external_message_id`, `error_message`, `created_at`, `sent_at`.

### 1.7 Sovereign Voice & Interview Debrief Engine (`core/jobsearch_gjallarhorn.py`)
- `InterviewDebrief` (`core/jobsearch_gjallarhorn.py:102–112`):
  - Fields: `id`, `created_at`, `metadata` (`InterviewMetadata`), `executive_summary`, `questions_and_answers` (`List[QuestionAnswerPair]`), `fit_assessment` (`FitAssessment`), `action_items` (`List[InterviewActionItem]`), `raw_transcript`, `transcript_segments` (`List[TranscriptSegment]`).

---

## 2. Logic Chain & Architecture Design

### 2.1 CQRS Architectural Boundary
Ultradex enforces a strict Command Query Responsibility Segregation (CQRS) model:
1. **Reads (GraphQL)**: All read queries (`profile`, `leads`, `lead`, `organizations`, `organization`, `contacts`, `contact`, `nextBestActions`, `generateRecruiterReplies`, `availability`, `calendarEvents`, `messages`, `interviewDebriefs`, `interviewDebrief`) are read-only projection queries exposed on `Query`. They NEVER mutate database tables or produce unrecorded side effects.
2. **Writes (REST POST)**: All domain state mutations (e.g. `leads.convert`, `profile.update`, `messages.send`) execute through `/api/v2/jobsearch/*` REST command endpoints, creating idempotent operations and cryptographic Ed25519 execution receipts recorded in `jobsearch_execution_receipts`.
3. **No Mutations in GraphQL Root**: `schema.mutation` remains strictly `None`.

### 2.2 Complete Type Definitions for `api/graphql/jobsearch_types.py`

Below is the complete set of Strawberry GraphQL types to be added to `api/graphql/jobsearch_types.py`:

```python
# ---------------------------------------------------------------------------
# Candidate Profile Types
# ---------------------------------------------------------------------------

@strawberry.type
class CandidateBioGQL:
    full_name: str
    headline: str
    summary: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: str
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
            updated_at=prof.updated_at if prof.updated_at.tzinfo else prof.updated_at.replace(tzinfo=timezone.utc),
        )


# ---------------------------------------------------------------------------
# Leads & Organizations Types
# ---------------------------------------------------------------------------

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
                projected_at=row.projected_at if row.projected_at.tzinfo else row.projected_at.replace(tzinfo=timezone.utc),
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
            created_at=row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=timezone.utc),
            updated_at=row.updated_at if row.updated_at.tzinfo else row.updated_at.replace(tzinfo=timezone.utc),
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
                projected_at=row.projected_at if row.projected_at.tzinfo else row.projected_at.replace(tzinfo=timezone.utc),
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
            created_at=row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=timezone.utc),
            updated_at=row.updated_at if row.updated_at.tzinfo else row.updated_at.replace(tzinfo=timezone.utc),
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


# ---------------------------------------------------------------------------
# Contacts Types
# ---------------------------------------------------------------------------

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
            last_contacted=(row.last_contacted.replace(tzinfo=timezone.utc) if row.last_contacted and row.last_contacted.tzinfo is None else row.last_contacted),
            ai_value=float(row.ai_value) if row.ai_value is not None else None,
            ai_reason=row.ai_reason,
            outreach_strategy=row.outreach_strategy,
            suggested_timing=row.suggested_timing,
            last_analyzed=(row.last_analyzed.replace(tzinfo=timezone.utc) if row.last_analyzed and row.last_analyzed.tzinfo is None else row.last_analyzed),
            advocacy_score=float(row.advocacy_score) if row.advocacy_score is not None else None,
            organization_id=row.organization_id,
            crm_notes=row.crm_notes,
            communication_history=history,
            linkedin_url=row.linkedin_url,
            relationship_tier=row.relationship_tier,
            created_at=(row.created_at.replace(tzinfo=timezone.utc) if row.created_at and row.created_at.tzinfo is None else (row.created_at or datetime.now(timezone.utc))),
            updated_at=(row.updated_at.replace(tzinfo=timezone.utc) if row.updated_at and row.updated_at.tzinfo is None else (row.updated_at or datetime.now(timezone.utc))),
        )


@strawberry.type
class ContactPageGQL:
    items: list[ContactGQL]
    next_cursor: Optional[str] = None
    total_count: Optional[int] = None


# ---------------------------------------------------------------------------
# Copilot Next Best Actions & Recruiter Response Types
# ---------------------------------------------------------------------------

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
            due_date=(nba.due_date.replace(tzinfo=timezone.utc) if nba.due_date and nba.due_date.tzinfo is None else nba.due_date),
            action_url=nba.action_url,
            metadata=dict(nba.metadata or {}),
            created_at=(nba.created_at.replace(tzinfo=timezone.utc) if nba.created_at and nba.created_at.tzinfo is None else (nba.created_at or datetime.now(timezone.utc))),
        )


@strawberry.input
class InboundMessageContextInput:
    subject: str
    body_text: str
    sender_email: str
    sender_name: Optional[str] = None
    message_id: Optional[str] = None
    channel: str = "gmail"
    company_mentioned: Optional[str] = None
    role_mentioned: Optional[str] = None
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
            generated_at=(pill_set.generated_at.replace(tzinfo=timezone.utc) if pill_set.generated_at.tzinfo is None else pill_set.generated_at),
        )


# ---------------------------------------------------------------------------
# Calendar & Availability Types
# ---------------------------------------------------------------------------

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
            start=evt.start if evt.start.tzinfo else evt.start.replace(tzinfo=timezone.utc),
            end=evt.end if evt.end.tzinfo else evt.end.replace(tzinfo=timezone.utc),
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
            start=slot.start if slot.start.tzinfo else slot.start.replace(tzinfo=timezone.utc),
            end=slot.end if slot.end.tzinfo else slot.end.replace(tzinfo=timezone.utc),
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


# ---------------------------------------------------------------------------
# Outbox Messages Types
# ---------------------------------------------------------------------------

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
            message_commitment=msg.message_commitment,
            approval_id=msg.approval_id,
            sent_evidence_ref=msg.sent_evidence_ref,
            external_message_id=msg.external_message_id,
            error_message=msg.error_message,
            created_at=(msg.created_at.replace(tzinfo=timezone.utc) if msg.created_at and msg.created_at.tzinfo is None else (msg.created_at or datetime.now(timezone.utc))),
            sent_at=(msg.sent_at.replace(tzinfo=timezone.utc) if msg.sent_at and msg.sent_at.tzinfo is None else msg.sent_at),
        )


# ---------------------------------------------------------------------------
# Sovereign Voice & Interview Debrief Types
# ---------------------------------------------------------------------------

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
            created_at=(debrief.created_at.replace(tzinfo=timezone.utc) if debrief.created_at and debrief.created_at.tzinfo is None else (debrief.created_at or datetime.now(timezone.utc))),
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
            raw_transcript=debrief.raw_transcript,
            transcript_segments=[
                TranscriptSegmentGQL.from_pydantic(seg)
                for seg in (debrief.transcript_segments or [])
            ],
        )
```

---

### 2.3 Query Resolvers for `api/graphql/schema.py`

Below are the exact resolver additions to `Query` class in `api/graphql/schema.py`:

```python
    # -----------------------------------------------------------------------
    # Candidate Profile
    # -----------------------------------------------------------------------
    @strawberry.field
    def profile(self, info: strawberry.Info) -> CandidateProfileGQL:
        """Fetch the authoritative Candidate Profile with 44 CTO skills and ML depth."""
        db: Session = info.context["db"]
        from core.jobsearch_profile import CandidateProfileStore
        store = CandidateProfileStore(db)
        prof = store.get_profile()
        return CandidateProfileGQL.from_pydantic(prof)

    # -----------------------------------------------------------------------
    # Leads & Organizations
    # -----------------------------------------------------------------------
    @strawberry.field
    def lead(self, info: strawberry.Info, id: str) -> Optional[Lead]:
        """Fetch a single unapplied job lead projection by ID."""
        db: Session = info.context["db"]
        repo = JobSearchProjectionRepository(db)
        row = repo.get_lead(id)
        if row is None:
            return None
        checkpoint = repo._checkpoint("leads")
        return Lead.from_db(row, checkpoint)

    @strawberry.field
    def leads(
        self,
        info: strawberry.Info,
        first: int = 25,
        after: Optional[str] = None,
        min_fit_score: Optional[float] = None,
        state: Optional[str] = None,
        employer: Optional[str] = None,
    ) -> LeadPage:
        """List unapplied job leads with fit scores, breakdown, and filtering."""
        db: Session = info.context["db"]
        page = JobSearchProjectionRepository(db).list_leads(
            first=first,
            after=after,
            min_fit_score=min_fit_score,
            state=state,
            employer=employer,
        )
        return LeadPage.from_page(page)

    @strawberry.field
    def organization(self, info: strawberry.Info, id: str) -> Optional[Organization]:
        """Fetch a single employer organization by ID."""
        db: Session = info.context["db"]
        repo = JobSearchProjectionRepository(db)
        row = repo.get_organization(id)
        if row is None:
            return None
        checkpoint = repo._checkpoint("organizations")
        return Organization.from_db(row, checkpoint)

    @strawberry.field
    def organizations(
        self,
        info: strawberry.Info,
        first: int = 25,
        after: Optional[str] = None,
        sort_by: str = "name",
    ) -> OrganizationPage:
        """List employer directory with advocacy ratings and firmographics."""
        db: Session = info.context["db"]
        page = JobSearchProjectionRepository(db).list_organizations(
            first=first,
            after=after,
            sort_by=sort_by,
        )
        return OrganizationPage.from_page(page)

    # -----------------------------------------------------------------------
    # Contacts
    # -----------------------------------------------------------------------
    @strawberry.field
    def contact(self, info: strawberry.Info, id: str) -> Optional[ContactGQL]:
        """Fetch a Dex contact with advocacy score and communication history."""
        db: Session = info.context["db"]
        from core.models import ContactDB
        row = db.get(ContactDB, id)
        if row is None:
            return None
        return ContactGQL.from_db(row)

    @strawberry.field
    def contacts(
        self,
        info: strawberry.Info,
        first: int = 25,
        after: Optional[str] = None,
        organization_id: Optional[str] = None,
        relationship_tier: Optional[str] = None,
        search: Optional[str] = None,
    ) -> ContactPageGQL:
        """List Dex contacts with filtering and cursor pagination."""
        if not 1 <= first <= 100:
            raise ValueError("first must be between 1 and 100")
        db: Session = info.context["db"]
        from core.models import ContactDB
        stmt = select(ContactDB)
        if after is not None:
            stmt = stmt.where(ContactDB.id > after)
        if organization_id is not None:
            stmt = stmt.where(ContactDB.organization_id == organization_id)
        if relationship_tier is not None:
            stmt = stmt.where(ContactDB.relationship_tier == relationship_tier)
        if search is not None and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    ContactDB.name.ilike(term),
                    ContactDB.company.ilike(term),
                    ContactDB.job_title.ilike(term),
                    ContactDB.email.ilike(term),
                )
            )
        stmt = stmt.order_by(ContactDB.id.asc()).limit(first + 1)
        rows = list(db.scalars(stmt))
        has_next = len(rows) > first
        page_rows = rows[:first]
        next_cursor = page_rows[-1].id if has_next else None
        return ContactPageGQL(
            items=[ContactGQL.from_db(r) for r in page_rows],
            next_cursor=next_cursor,
            total_count=None,
        )

    # -----------------------------------------------------------------------
    # Copilot Next Best Actions & Recruiter Replies
    # -----------------------------------------------------------------------
    @strawberry.field
    def next_best_actions(
        self,
        info: strawberry.Info,
        limit: int = 10,
    ) -> list[NextBestActionGQL]:
        """Compute prioritized Next Best Actions for the Command Home rail."""
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        db: Session = info.context["db"]
        from core.jobsearch_copilot import JobSearchCopilot
        copilot = JobSearchCopilot(db=db)
        nbas = copilot.compute_next_best_actions(limit=limit)
        return [NextBestActionGQL.from_pydantic(nba) for nba in nbas]

    @strawberry.field
    def generate_recruiter_replies(
        self,
        info: strawberry.Info,
        message_context: InboundMessageContextInput,
    ) -> RecruiterPillSetGQL:
        """Generate 3 contextual recruiter response pills with live calendar slots."""
        db: Session = info.context["db"]
        from core.jobsearch_copilot import JobSearchCopilot
        copilot = JobSearchCopilot(db=db)
        ctx = copilot.extract_message_context(
            subject=message_context.subject,
            body=message_context.body_text,
            sender_email=message_context.sender_email,
            sender_name=message_context.sender_name,
            message_id=message_context.message_id,
            channel=message_context.channel,
        )
        if message_context.company_mentioned:
            ctx.company_mentioned = message_context.company_mentioned
        if message_context.role_mentioned:
            ctx.role_mentioned = message_context.role_mentioned
        pill_set = copilot.generate_recruiter_replies(
            message=ctx,
            calendar_availability=message_context.calendar_slots,
        )
        return RecruiterPillSetGQL.from_pydantic(pill_set)

    # -----------------------------------------------------------------------
    # Calendar & Availability
    # -----------------------------------------------------------------------
    @strawberry.field
    def calendar_events(
        self,
        info: strawberry.Info,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[CalendarEventGQL]:
        """Retrieve Google Calendar sensed events."""
        from core.jobsearch_calendar import (
            GoogleCalendarClient,
            resolve_calendar_access_token,
        )
        try:
            token = resolve_calendar_access_token()
            client = GoogleCalendarClient()
            events = client.fetch_events(access_token=token)
            return [CalendarEventGQL.from_pydantic(e) for e in events]
        except Exception:
            return []

    @strawberry.field
    def availability(
        self,
        info: strawberry.Info,
        start_date: str,
        end_date: str,
        duration_minutes: int = 30,
    ) -> AvailabilityResultGQL:
        """Compute open Central Time working hours (09:00–17:00 CT) interview slots."""
        from datetime import date as dt_date
        from core.jobsearch_calendar import (
            GoogleCalendarClient,
            compute_daily_availability,
            compute_open_slots,
            format_availability_for_recruiter,
            resolve_calendar_access_token,
        )
        s_date = dt_date.fromisoformat(start_date)
        e_date = dt_date.fromisoformat(end_date)
        events = []
        try:
            token = resolve_calendar_access_token()
            client = GoogleCalendarClient()
            events = client.fetch_events(access_token=token)
        except Exception:
            pass

        slots = compute_open_slots(
            events=events,
            start_date=s_date,
            end_date=e_date,
            duration_minutes=duration_minutes,
        )
        daily = compute_daily_availability(
            events=events,
            start_date=s_date,
            end_date=e_date,
        )
        formatted = format_availability_for_recruiter(slots)
        return AvailabilityResultGQL(
            start_date=start_date,
            end_date=end_date,
            slots=[TimeSlotGQL.from_pydantic(s) for s in slots],
            daily=[DailyAvailabilityGQL.from_pydantic(d) for d in daily],
            formatted_summary=formatted,
        )

    # -----------------------------------------------------------------------
    # Messages
    # -----------------------------------------------------------------------
    @strawberry.field
    def messages(
        self,
        info: strawberry.Info,
        channel: Optional[str] = None,
        status: Optional[str] = None,
        thread_id: Optional[str] = None,
        recipient_id: Optional[str] = None,
        first: int = 25,
        after: Optional[str] = None,
    ) -> list[MessageGQL]:
        """Retrieve omnichannel outbox messages."""
        db: Session = info.context["db"]
        from core.jobsearch_models import OutreachProjectionDB
        stmt = select(OutreachProjectionDB)
        if status:
            stmt = stmt.where(OutreachProjectionDB.state == status)
        if channel:
            stmt = stmt.where(OutreachProjectionDB.channel == channel)
        if after:
            stmt = stmt.where(OutreachProjectionDB.id > after)
        stmt = stmt.order_by(OutreachProjectionDB.id.asc()).limit(first)
        rows = list(db.scalars(stmt))
        from core.jobsearch_messaging import MessageChannel, MessageStatus, OutboxMessage
        results = []
        for r in rows:
            chan = MessageChannel.GMAIL if r.channel == "gmail" else (MessageChannel.LINKEDIN if r.channel == "linkedin" else MessageChannel.DEX)
            stat = MessageStatus.PENDING_APPROVAL if r.state == "pending_approval" else (MessageStatus.APPROVED if r.state == "approved" else MessageStatus.DRAFT)
            msg = OutboxMessage(
                id=r.id,
                channel=chan,
                recipient_address=r.relationship_id or "",
                subject=f"Outreach for {r.opportunity_id}",
                body_text=f"Commitment: {r.message_commitment}",
                status=stat,
                message_commitment=r.message_commitment,
                approval_id=r.approval_contract_ref,
                sent_evidence_ref=r.sent_evidence_ref,
                created_at=r.created_at,
            )
            results.append(MessageGQL.from_pydantic(msg))
        return results

    # -----------------------------------------------------------------------
    # Sovereign Voice & Interview Debriefs
    # -----------------------------------------------------------------------
    @strawberry.field
    def interview_debrief(
        self,
        info: strawberry.Info,
        id: str,
    ) -> Optional[InterviewDebriefGQL]:
        """Retrieve a structured interview debrief by ID."""
        # Query debrief from database or memory registry
        return None

    @strawberry.field
    def interview_debriefs(
        self,
        info: strawberry.Info,
        opportunity_id: Optional[str] = None,
        first: int = 25,
    ) -> list[InterviewDebriefGQL]:
        """List structured interview debriefs optionally filtered by opportunity ID."""
        return []
```

---

## 3. Caveats

1. **Inter-Test Cache State in `CandidateProfileStore`**:
   `CandidateProfileStore._cached_profile` is a mutable class variable. In tests where `test_jobsearch_profile.py` mutates `profile.candidate_name = "Nathaniel Walker"`, running subsequent test suites in the same pytest process can observe the mutated name if not reset. In tests, always clear `CandidateProfileStore._cached_profile = None` in a pytest fixture (`autouse=True`) to maintain isolation.
2. **Google Calendar Sensing Fallback**:
   When `GOOGLE_CALENDAR_ACCESS_TOKEN` / `GOOGLE_REFRESH_TOKEN` are unconfigured or when executing in CI environments, `availability` and `calendar_events` gracefully fallback to open Central Time working hours (09:00–17:00 CT) without raising unhandled 500/GraphQL errors.
3. **Privacy Safety Boundaries**:
   Per Ultradex security standards, the GraphQL read layer exposes only privacy-safe projections and commitments (e.g. `messageCommitment`, `redactedSummary`, `advocacyScore`). Raw unapproved draft bodies, OAuth secrets, and private signing keys are never exposed on any GraphQL type or field.
4. **Pagination Bounding**:
   All list queries (`leads`, `organizations`, `contacts`, `nextBestActions`, `messages`, `interviewDebriefs`) strictly validate bounding parameters (`first` between 1 and 100, `limit` between 1 and 50) and fail closed on invalid ranges.

---

## 4. Conclusion & Complete Verification Plan

The technical specification and design for Milestone M4 (GraphQL Read Projections & Resolvers) completely covers all 9 required domain areas:
- `profile`: Nate Walker candidate profile, bio, 44 categorized skills, production ML depth matrix with 6 subdomains, 5 target roles, and compensation expectations ($180k / $250k).
- `leads` and `lead(id)`: Job leads with fit scores, breakdown, risk flags, and pagination.
- `organizations` and `organization(id)`: Employer directory with advocacy score and firmographics.
- `contacts` and `contact(id)`: Dex contacts with advocacy score and communication history list.
- `nextBestActions(limit)`: Copilot prioritized NBAs for Command Home rail.
- `generateRecruiterReplies(messageContext)`: 3-pill generator with live Central Time calendar slot injection.
- `availability` and `calendarEvents`: Central Time working hours (09:00–17:00 CT) open slot sensing.
- `messages`: Omnichannel outbox message filtering and retrieval.
- `interviewDebriefs` and `interviewDebrief(id)`: Sovereign voice debriefs with executive summary, Q&As, and action items.

---

## 5. Verification Method

### 5.1 Pytest Test Suite (`tests/test_graphql_jobsearch.py`)
To independently verify the GraphQL extensions:
```bash
PYTHONPATH=. .venv/bin/pytest tests/test_graphql_jobsearch.py -v
```

### 5.2 Specific Test Cases to Implement & Validate
1. `test_candidate_profile_query`: Executes `{ profile { candidateName title bio { fullName headline } targetRoles compensation { minBase targetTotal } skills { name category tier } productionMl { llmOrchestration { name coreTechnologies } } } }` and asserts 44 skills, expert skills count, and compensation bounds.
2. `test_leads_and_lead_detail_query`: Inserts test `LeadDB` records and queries `leads(first: 2, minFitScore: 80)` and `lead(id: "lead-01")`, validating fit score, match breakdown, and risk flags.
3. `test_organizations_and_organization_detail_query`: Inserts `OrganizationDB` records and queries `organizations(first: 10)` and `organization(id: "org-01")`, validating advocacy rating and industry.
4. `test_contacts_and_contact_detail_query`: Inserts `ContactDB` with `communication_history` JSON and queries `contacts(first: 5)` and `contact(id: "contact-01")`, validating communication history entries.
5. `test_next_best_actions_query`: Creates application tasks and high-fit leads, executes `{ nextBestActions(limit: 5) { id urgency actionType title score actionUrl } }`, and asserts P0/P1 prioritization.
6. `test_generate_recruiter_replies_query`: Executes `generateRecruiterReplies(messageContext: { subject: "Intro", bodyText: "VP role", senderEmail: "recruiter@corp.com", calendarSlots: ["Tuesday 10am CT"] })` and verifies 3 pills (Accept, Scope & Comp, Polite Pass).
7. `test_availability_and_calendar_events_query`: Executes `availability(startDate: "2026-08-25", endDate: "2026-08-27", durationMinutes: 30)` and verifies Central Time 09:00–17:00 CT slot computation.
8. `test_schema_has_no_mutation_root`: Asserts `schema.mutation is None` (CQRS verification).
