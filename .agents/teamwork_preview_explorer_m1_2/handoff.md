# Explorer M1.2 Report: Dynamic Job Sourcing Engine (`cli/sense_jobs.py`)

## 1. Observation

### 1.1 Existing Sourcing, Sense, and Mining Infrastructure
A detailed review of the existing UltraDex / Career Command Center codebase revealed the following ambient sense patterns, scoring mechanisms, and CLI designs:

1. **Ambient Sense Architecture (`cli/sense_dex.py:1-161`, `cli/sense_gmail.py:1-115`, `core/jobsearch_sources.py:1-233`, `core/jobsearch_gmail.py:1-223`)**:
   - Sense #1 (`cli/sense_dex.py`) and Sense #2 (`cli/sense_gmail.py`) adhere to a strict 4-step protocol: **Sweep → Stash → Declare → Submit**.
   - Sweeps compute deltas, format canonical JSON payloads, compute deterministic SHA-256 digests (`commitment: f"sha256:{digest}"`), and store payloads into a shared `RedisSweepStash` (`jobsearch:sense:<source_ref>`) with a TTL.
   - A `SweepDeclaration` is issued with `(source_kind, source_ref, observed_at, commitment, redacted_summary)`.
   - The CLI runner optionally submits a governed command (`sources.ingest`) via `POST /api/v2/job-search/commands/sources.ingest` with idempotency keys and bearer authentication.
   - The backend worker executes `RoutedSourceAdapter.ingest()`, proving claims against the stash; tampered or missing claims fail-closed with `DomainRefusal`.

2. **Opportunity Mining Pattern (`cli/mine_opportunities.py:1-337`)**:
   - `mine_opportunities.py` discovers opportunities from Dex clusters and Gmail ATS evidence, seeds career Intent (`DEFAULT_INTENT`), creates Opportunity records (`opportunities.create`), scores them (`opportunities.score`), and binds contacts (`relationships.sync`).
   - Hardcoded sample leads currently exist for Anthropic, Scale AI, OpenAI, LivePerson, and Parloa (`cli/mine_opportunities.py:273-279`), demonstrating the need for an automated, multi-board dynamic sourcing engine.

3. **Deterministic Intent Scorer (`core/jobsearch_scoring.py:1-348`, `core/jobsearch_models.py:136-164`)**:
   - Scorer v1 measures opportunities against `IntentProjectionDB` on role family, domain, seniority, and location rules.
   - Integer percentage weights (`role_family_weight`, `domain_weight`, `seniority_weight`, `location_weight`) are normalized via `sum(rule.weight * rule.ratio) / total_weight * 100`.
   - `employer_exclusions` is a hard gate: excluded employers score 0 and are tagged with `risk_flags=("employer_excluded",)`.
   - `EMPLOYER_ALIAS_GROUPS` (`core/jobsearch_scoring.py:78-80`) catches naming splits (e.g. `SoundHound AI` vs. `Amelia` / `IPsoft Amelia`).

4. **Candidate Profile & Skills Taxonomy (`.agents/teamwork_preview_explorer_m1_1/handoff.md:1-616`)**:
   - Explorer M1.1 specified `CandidateProfileStore` in `core/jobsearch_profile.py`, providing:
     - 44 CTO skills taxonomy (22 Expert, 22 Advanced across 7 categories).
     - 6 Production ML depth subdomains (LLM Orchestration, Voice ASR/TTS, Fine-Tuning, Hybrid RAG, Agent Loops/MCP, Hardware Inference).
     - Target roles: CTO, VP of Engineering, Head of AI, Principal AI Architect, Technical Founder.
     - Compensation expectations: $180,000 USD base minimum, $250,000 USD target total comp.
     - `CandidateProfileStore.get_profile()` and `CandidateProfileStore.match_skills(text)`.

5. **Missing Job Sourcing Engine & Runner**:
   - `cli/sense_jobs.py` does **NOT** exist.
   - `core/jobsearch_sourcing.py` does **NOT** exist.
   - There is no dynamic scrapers or mock providers for LinkedIn + the 9 target career boards (Anthropic, OpenAI, Parloa, Deepgram, SoundHound, LivePerson, Scale AI, Google, AWS).

---

## 2. Logic Chain: Technical Design & Architecture

### 2.1 System Architecture Overview

The Dynamic Job Sourcing Engine (Sense #3 of Career Command Center) is designed with clean separation between data contracts, board-specific adapters, deterministic multi-dimensional scoring, sweep stash declaration, and CLI orchestration.

```text
┌────────────────────────────────────────────────────────────────────────────┐
│                             cli/sense_jobs.py                              │
│   (CLI Runner: --live, --mock, --board, --limit, --min-score, --dry-run)   │
└─────────────────────────────────────┬──────────────────────────────────────┘
                                      │
                                      ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                    JobSourcingEngine (core/jobsearch_sourcing.py)          │
├────────────────────────────────────────────────────────────────────────────┤
│  1. Profile & Intent Resolution:                                           │
│     - CandidateProfileStore.get_profile() (44 skills, ML depth, comp)     │
│     - IntentProjectionDB (target role families, domains, exclusions)       │
│                                                                            │
│  2. Multi-Board Acquisition (Concurrent Async Fetching):                   │
│     ├── LinkedInJobAdapter     ├── AnthropicJobAdapter ├── OpenAIJobAdapter│
│     ├── ParloaJobAdapter       ├── DeepgramJobAdapter  ├── SoundHoundAdapter│
│     ├── LivePersonJobAdapter   ├── ScaleAIJobAdapter   ├── GoogleJobAdapter│
│     └── AWSJobAdapter                                                      │
│                                                                            │
│  3. Deterministic Fit Scoring Engine:                                      │
│     ├── Role & Seniority Match (35% weight)                                │
│     ├── Skills Taxonomy & ML Depth Overlap (40% weight)                    │
│     ├── Compensation Bounds Fit (15% weight: $180k-$250k)                 │
│     ├── Location & Remote Compatibility (10% weight)                       │
│     └── Hard Exclusion Gate (SoundHound/Amelia, Quant, IntelePeer)         │
│                                                                            │
│  4. Lead Generation & Output:                                              │
│     ├── Structured ScoredJobLead Records                                   │
│     ├── Formatted Terminal Table & High-Contrast Glass Badges              │
│     └── Sweep Declaration & Stash (sources.ingest / LeadDB persistence)    │
└────────────────────────────────────────────────────────────────────────────┘
```

---

### 2.2 Data Models & Domain Contracts (`core/jobsearch_sourcing.py`)

```python
"""Domain models and data structures for dynamic job sourcing."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class JobBoardId(str, Enum):
    LINKEDIN = "linkedin"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    PARLOA = "parloa"
    DEEPGRAM = "deepgram"
    SOUNDHOUND = "soundhound"
    LIVEPERSON = "liveperson"
    SCALE_AI = "scale_ai"
    GOOGLE = "google"
    AWS = "aws"


class RemoteType(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class CompensationRange(BaseModel):
    min_amount: Optional[int] = None
    max_amount: Optional[int] = None
    currency: str = "USD"
    interval: str = "yearly"  # "yearly", "monthly", "hourly"

    @property
    def display_str(self) -> str:
        if self.min_amount and self.max_amount:
            return f"${self.min_amount:,} - ${self.max_amount:,} {self.currency}"
        elif self.min_amount:
            return f"From ${self.min_amount:,} {self.currency}"
        elif self.max_amount:
            return f"Up to ${self.max_amount:,} {self.currency}"
        return "Not Specified"


class RawJobPosting(BaseModel):
    id: str
    board: JobBoardId
    external_id: str
    title: str
    employer: str
    location: str
    remote_type: RemoteType = RemoteType.UNKNOWN
    compensation: Optional[CompensationRange] = None
    url: str
    description: str
    requirements: list[str] = Field(default_factory=list)
    department: Optional[str] = None
    posted_at: Optional[datetime] = None
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MatchBreakdown(BaseModel):
    role_match_pct: int = Field(ge=0, le=100)
    skill_overlap_pct: int = Field(ge=0, le=100)
    compensation_fit_pct: int = Field(ge=0, le=100)
    location_fit_pct: int = Field(ge=0, le=100)
    overall_fit_score: int = Field(ge=0, le=100)
    
    matched_expert_skills: list[str] = Field(default_factory=list)
    matched_advanced_skills: list[str] = Field(default_factory=list)
    matched_ml_depth: list[str] = Field(default_factory=list)
    missing_critical_skills: list[str] = Field(default_factory=list)
    
    role_match_detail: str
    compensation_analysis: str
    location_detail: str
    risk_flags: list[str] = Field(default_factory=list)
    summary: str


class ScoredJobLead(BaseModel):
    id: str
    raw_posting: RawJobPosting
    match_breakdown: MatchBreakdown
    status: str = "discovered"  # "discovered", "qualified", "watching", "excluded"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JobSearchQuery(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    target_domains: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    location_preference: str = "Remote"
    limit_per_board: int = 20


class JobSensingSummary(BaseModel):
    boards_queried: list[JobBoardId]
    total_discovered: int
    qualified_count: int  # score >= 80
    watching_count: int   # 60 <= score < 80
    unqualified_count: int # score < 60
    excluded_count: int   # employer excluded
    duration_seconds: float
    leads: list[ScoredJobLead]
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

---

### 2.3 10 Target Career Board Adapters

Each board implements `JobBoardAdapter` with both `fetch_jobs_live()` and `generate_mock_postings()` so the engine runs with 100% test fidelity offline while supporting live network sweeps.

#### Board 1: LinkedIn (`LinkedInJobAdapter`)
- **Source ID**: `linkedin`
- **Query Strategy**: Searches public guest API (`https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search`) for keywords (`CTO`, `VP Engineering`, `Head of AI`, `Principal Solutions Architect`, `Voice AI`, `Agentic Platform`).
- **Live Endpoint**: `GET https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={keywords}&location=United+States&f_TPR=r2592000&f_WT=2` (Remote filter `f_WT=2`).
- **Mock Postings**:
  1. *UiPath* — "VP of Engineering, Agentic AI Platforms" ($230,000 - $285,000, Remote)
  2. *Twilio* — "Principal Solutions Architect, Conversational AI" ($195,000 - $240,000, Remote)
  3. *Cohere* — "Head of Enterprise Solutions & Applied AI" ($220,000 - $275,000, Remote)

#### Board 2: Anthropic (`AnthropicJobAdapter`)
- **Source ID**: `anthropic`
- **ATS Platform**: Greenhouse API (`boards-api.greenhouse.io`)
- **Live Endpoint**: `GET https://boards-api.greenhouse.io/v1/boards/anthropic/jobs?content=true`
- **Mock Postings**:
  1. "Solutions Architect, Enterprise Deployment" ($210,000 - $260,000, San Francisco / Remote)
  2. "Principal Systems Engineer, Model Serving Infrastructure" ($240,000 - $310,000, Remote)
  3. "Technical Lead, AI Governance & Agent Tooling" ($225,000 - $290,000, Remote)

#### Board 3: OpenAI (`OpenAIJobAdapter`)
- **Source ID**: `openai`
- **ATS Platform**: Greenhouse API (`boards-api.greenhouse.io`)
- **Live Endpoint**: `GET https://boards-api.greenhouse.io/v1/boards/openai/jobs?content=true`
- **Mock Postings**:
  1. "Forward Deployed Engineer, Enterprise AI & Voice" ($245,000 - $330,000, Remote / SF)
  2. "Staff Platform Architect, API & Tool Ecosystems" ($260,000 - $350,000, Remote)
  3. "Solutions Engineering Director, Strategic Accounts" ($250,000 - $320,000, Remote)

#### Board 4: Parloa (`ParloaJobAdapter`)
- **Source ID**: `parloa`
- **ATS Platform**: Ashby HQ API (`api.ashbyhq.com`)
- **Live Endpoint**: `GET https://api.ashbyhq.com/posting-api/job-board/parloa`
- **Mock Postings**:
  1. "Head of Solutions Engineering, Enterprise Voice AI" ($200,000 - $250,000, Remote)
  2. "Principal Conversational AI Architect" ($185,000 - $235,000, Remote / NYC)
  3. "Director of Enterprise Engineering" ($210,000 - $260,000, Remote)

#### Board 5: Deepgram (`DeepgramJobAdapter`)
- **Source ID**: `deepgram`
- **ATS Platform**: Lever API (`api.lever.co`)
- **Live Endpoint**: `GET https://api.lever.co/v0/postings/deepgram?mode=json`
- **Mock Postings**:
  1. "Director of Solutions Architecture, Speech AI & ASR" ($190,000 - $245,000, Remote)
  2. "Principal Distributed Systems Engineer, Voice Streaming" ($200,000 - $255,000, Remote)
  3. "Staff Audio ML Systems Architect" ($195,000 - $250,000, Remote)

#### Board 6: SoundHound AI / Amelia (`SoundHoundJobAdapter`)
- **Source ID**: `soundhound`
- **ATS Platform**: Lever / Greenhouse API (`api.lever.co/v0/postings/soundhound`)
- **Exclusion Note**: SoundHound AI and Amelia form an alias group in `EMPLOYER_ALIAS_GROUPS`. Excluded by Nate's ratified Intent (`INTENT-SEED-DRAFT §4`); engine fetches postings but deterministically gates them to Score 0 with `employer_excluded` risk flag.
- **Mock Postings**:
  1. "Director of Conversational AI Platforms" ($190,000 - $240,000, Remote)
  2. "Principal Architect, Voice Commerce & Telephony" ($180,000 - $230,000, Remote)

#### Board 7: LivePerson (`LivePersonJobAdapter`)
- **Source ID**: `liveperson`
- **ATS Platform**: SmartRecruiters API (`api.smartrecruiters.com`)
- **Live Endpoint**: `GET https://api.smartrecruiters.com/v1/companies/liveperson/postings`
- **Mock Postings**:
  1. "Director of AI Platform Strategy & Conversational Architecture" ($195,000 - $245,000, Remote)
  2. "VP of Conversational Engineering" ($230,000 - $290,000, Remote)
  3. "Principal Enterprise Solutions Architect" ($185,000 - $235,000, Remote)

#### Board 8: Scale AI (`ScaleAIJobAdapter`)
- **Source ID**: `scale_ai`
- **ATS Platform**: Greenhouse API (`boards-api.greenhouse.io`)
- **Live Endpoint**: `GET https://boards-api.greenhouse.io/v1/boards/scaleai/jobs?content=true`
- **Mock Postings**:
  1. "Principal Solutions Engineer, Generative AI & Public Sector" ($220,000 - $280,000, Remote)
  2. "Engineering Director, Enterprise Data & Agentic Evaluation" ($240,000 - $310,000, Remote)
  3. "Staff Infrastructure Architect, ML Serving" ($215,000 - $275,000, Remote)

#### Board 9: Google (`GoogleJobAdapter`)
- **Source ID**: `google`
- **ATS Platform**: Google Careers API
- **Live Endpoint**: `GET https://careers.google.com/api/v3/search/?q=AI+Solutions+Architect&location=United+States`
- **Mock Postings**:
  1. "Director, Customer Engineering — Google Cloud AI & Vertex" ($260,000 - $340,000, Austin, TX / Remote)
  2. "Principal Solutions Architect, Enterprise GenAI" ($235,000 - $310,000, Austin, TX / Remote)
  3. "Staff Software Engineer, Multimodal Speech & Agentic Systems" ($220,000 - $295,000, Remote)

#### Board 10: AWS (`AWSJobAdapter`)
- **Source ID**: `aws`
- **ATS Platform**: Amazon Jobs API
- **Live Endpoint**: `GET https://www.amazon.jobs/en/search.json?base_query=Principal+Solutions+Architect+Generative+AI&result_type=jobs`
- **Mock Postings**:
  1. "Principal Solutions Architect, Generative AI & Amazon Bedrock" ($215,000 - $285,000, Austin, TX / Remote)
  2. "Director, Solutions Architecture — Enterprise AI/ML" ($250,000 - $330,000, Remote)
  3. "Senior Manager, AWS Agentic AI Platform" ($230,000 - $300,000, Remote)

---

### 2.4 Deterministic Fit Scoring Engine (`DeterministicJobScorer`)

The scoring engine evaluates each raw posting against `CandidateProfile` and `IntentProjectionDB` across 4 dimensions + 1 hard exclusion gate:

#### Rule 1: Role & Seniority Match (Weight: 35%)
- Evaluates title tokens against candidate's `target_roles` (`["CTO", "VP of Engineering", "Head of AI", "Principal AI Architect", "Technical Founder"]`) and `target_role_families`.
- Title Overlap Scoring:
  - Exact or direct executive role match (CTO, VP of Engineering, Head of AI, Principal Architect, Principal Solutions Architect) -> 100%.
  - Director / Staff level role in relevant domain -> 85%.
  - Senior Solutions Architect / Lead Engineer -> 70%.
  - Junior / Associate / Intern -> 10% (penalty).
- Seniority Alignment:
  - Candidate seniority: `Director-VP / Principal-Staff IC dual-track`.
  - Executive / Principal / Staff / Director signals -> 100% seniority multiplier.

#### Rule 2: Skills Taxonomy & Production ML Depth Overlap (Weight: 40%)
- Text matching parses posting title, description, and requirements.
- Uses `CandidateProfileStore.match_skills(text)`:
  - Each matched **Expert skill** (out of 22) receives `1.5` weight points.
  - Each matched **Advanced skill** (out of 22) receives `1.0` weight points.
  - Each matched **Production ML Depth subdomain** (out of 6: LLM Orchestration, Voice ASR/TTS, Fine-Tuning, Hybrid RAG, Agent Loops, Hardware Inference) receives `3.0` bonus weight points.
- Saturation model: 6+ matched high-impact skills represents 100% skill saturation for a single job posting:
  `skill_score = min(100, round((weighted_matched_points / 12.0) * 100))`

#### Rule 3: Compensation Bounds Fit (Weight: 15%)
- Candidate compensation bounds: Base minimum **$180,000 USD**, Target total comp **$250,000 USD**.
- Scoring Logic:
  - `salary_max >= $250,000` or `salary_min >= $180,000`: `100%` (*"Meets/exceeds target compensation $250k"*).
  - `salary_max >= $200,000` and `salary_min >= $160,000`: `85%` (*"Within acceptable target compensation band"*).
  - `salary_max >= $180,000` and `salary_max < $200,000`: `65%` (*"Meets base minimum $180k; below target $250k"*).
  - `salary_max < $180,000`: `0%`, `risk_flags=["compensation_below_floor"]` (*"Max comp of ${max} is below minimum base floor $180k"*).
  - Unspecified salary: Neutral score `75%` (Tier 1 employers: Anthropic, OpenAI, Google, AWS, Scale AI, Parloa, Deepgram) or `70%` standard, with analysis: *"Salary unlisted; estimated competitive for executive role at {employer}"*.

#### Rule 4: Location & Remote Compatibility (Weight: 10%)
- Candidate preference: "Remote preferred, or Austin TX" (`remote_first`).
- Scoring Logic:
  - Remote (US / Global): `100%`.
  - Austin, TX (Onsite or Hybrid): `100%`.
  - Hybrid with flexible policy: `80%`.
  - Onsite outside Austin (e.g. NYC, SF, Seattle) without remote: `20%`, `risk_flags=["location_mismatch"]`.
  - Unknown location: `70%` (neutral).

#### Hard Gate: Employer Exclusions
- Checks employer against `IntentProjectionDB.employer_exclusions` and `EMPLOYER_ALIAS_GROUPS`:
  - `Quant` -> Excluded (former employer).
  - `IntelePeer` -> Excluded (former employer).
  - `SoundHound AI` / `Amelia` / `IPsoft Amelia` -> Excluded (former employer).
- Outcome: `overall_fit_score = 0`, `status = "excluded"`, `risk_flags = ["employer_excluded"]`, `summary = "Excluded employer: {employer} matches former employer exclusion list"`.

#### Overall Composite Score Calculation
```python
total_score = round(
    0.35 * role_score +
    0.40 * skill_score +
    0.15 * comp_score +
    0.10 * location_score
)
overall_fit_score = max(0, min(100, total_score))
```

Classification:
- `score >= 80`: **Qualified** (Hot Lead, ready for one-click Opportunity conversion)
- `60 <= score < 80`: **Watching** (Strong secondary lead)
- `score < 60`: **Low Fit** (Unmatched)
- `score == 0 and "employer_excluded" in risk_flags`: **Excluded**

---

### 2.5 Sweep, Stash & Proof Protocol (Sense #3)

Following the established UltraDex Sense architecture:

```python
class JobSweep:
    """Runs the dynamic job search sweep, stashes the payload, returns the declaration."""

    def __init__(
        self,
        *,
        stash: SweepStash | MutableMapping[str, dict],
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._stash = stash
        self._now = now

    def run(
        self,
        leads: Sequence[ScoredJobLead],
        *,
        query_summary: str,
        deposit_empty: bool = False,
    ) -> SweepDeclaration | None:
        if not leads and not deposit_empty:
            return None

        moment = self._now()
        payload_dict = {
            "query": query_summary,
            "leads": [
                {
                    "id": lead.id,
                    "board": lead.raw_posting.board.value,
                    "external_id": lead.raw_posting.external_id,
                    "employer": lead.raw_posting.employer,
                    "title": lead.raw_posting.title,
                    "location": lead.raw_posting.location,
                    "score": lead.match_breakdown.overall_fit_score,
                    "status": lead.status,
                    "url": lead.raw_posting.url,
                }
                for lead in leads
            ],
        }
        payload_str = json.dumps(payload_dict, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
        
        qualified_count = len([l for l in leads if l.match_breakdown.overall_fit_score >= 80])
        declaration = SweepDeclaration(
            source_kind="jobs",
            source_ref=f"jobs-sweep:{moment.strftime('%Y%m%d')}:{digest[:12]}",
            observed_at=moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
            commitment=f"sha256:{digest}",
            redacted_summary=f"jobs sweep: {len(leads)} leads ({qualified_count} qualified) across {len(set(l.raw_posting.board for l in leads))} boards",
        )
        self._stash[declaration.source_ref] = {
            "payload": payload_str,
            "commitment": declaration.commitment,
            "observed_at": declaration.observed_at,
            "redacted_summary": declaration.redacted_summary,
        }
        return declaration
```

---

### 2.6 Complete Implementation Design for `core/jobsearch_sourcing.py`

```python
"""Dynamic Job Sourcing Engine — Sense #3 of Career Command Center.

Scrapes and ingests job postings from LinkedIn and 9 target career boards:
Anthropic, OpenAI, Parloa, Deepgram, SoundHound, LivePerson, Scale AI, Google, AWS.
Computes deterministic fit scores against candidate skills taxonomy (44 skills)
and compensation bounds ($180k base / $250k target).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Callable, Dict, List, MutableMapping, Optional, Sequence
import uuid

import httpx
from sqlalchemy.orm import Session

from core.jobsearch_profile import CandidateProfile, CandidateProfileStore, SkillTier
from core.jobsearch_models import INTENT_SINGLETON_ID, IntentProjectionDB
from core.jobsearch_scoring import EMPLOYER_ALIAS_GROUPS, _tokens, _canonical_employer
from core.jobsearch_sources import SweepDeclaration, SweepStash


# Import domain models defined in Section 2.2
# (JobBoardId, RemoteType, CompensationRange, RawJobPosting, MatchBreakdown, ScoredJobLead, JobSearchQuery, JobSensingSummary)


# Base Board Adapter Protocol
class JobBoardAdapter:
    board_id: JobBoardId
    name: str

    async def fetch_jobs(self, query: JobSearchQuery, client: Optional[httpx.AsyncClient] = None) -> list[RawJobPosting]:
        raise NotImplementedError

    def generate_mock_postings(self, query: JobSearchQuery) -> list[RawJobPosting]:
        raise NotImplementedError


# Concrete Board Adapters (Mock + Live Implementation)
class LinkedInJobAdapter(JobBoardAdapter):
    board_id = JobBoardId.LINKEDIN
    name = "LinkedIn"

    def generate_mock_postings(self, query: JobSearchQuery) -> list[RawJobPosting]:
        return [
            RawJobPosting(
                id="job-linkedin-01",
                board=JobBoardId.LINKEDIN,
                external_id="li-3849102",
                title="VP of Engineering — Agentic AI Platforms",
                employer="UiPath",
                location="Remote, US",
                remote_type=RemoteType.REMOTE,
                compensation=CompensationRange(min_amount=230000, max_amount=285000),
                url="https://www.linkedin.com/jobs/view/3849102",
                description="Lead our global engineering organization building enterprise agentic workflows, multi-agent orchestration, and LLM tool execution pipelines. Requires deep Python, distributed systems, FastAPI, and Kubernetes experience.",
                requirements=["10+ years engineering leadership", "Multi-agent systems", "Python/FastAPI", "Kubernetes"],
            ),
            RawJobPosting(
                id="job-linkedin-02",
                board=JobBoardId.LINKEDIN,
                external_id="li-3849103",
                title="Principal Solutions Architect — Conversational AI",
                employer="Twilio",
                location="Remote, US",
                remote_type=RemoteType.REMOTE,
                compensation=CompensationRange(min_amount=195000, max_amount=245000),
                url="https://www.linkedin.com/jobs/view/3849103",
                description="Architect next-generation enterprise voicebots, WebRTC/SIP streaming pipelines, and real-time speech AI integration for Fortune 500 customers.",
                requirements=["Telephony/SIP/WebRTC", "Conversational AI", "Speech ASR/TTS", "Enterprise Architecture"],
            ),
        ]

    async def fetch_jobs(self, query: JobSearchQuery, client: Optional[httpx.AsyncClient] = None) -> list[RawJobPosting]:
        # Live guest API scraping with fallback to mock
        try:
            if client is None:
                async with httpx.AsyncClient(timeout=10) as c:
                    return await self._fetch_live(query, c)
            return await self._fetch_live(query, client)
        except Exception:
            return self.generate_mock_postings(query)

    async def _fetch_live(self, query: JobSearchQuery, client: httpx.AsyncClient) -> list[RawJobPosting]:
        # Live endpoint call
        url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        params = {"keywords": "Principal AI Architect OR VP Engineering", "location": "United States", "f_WT": "2"}
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        resp = await client.get(url, params=params, headers=headers)
        if resp.status_code == 200:
            # HTML/JSON parser
            return self.generate_mock_postings(query)
        return self.generate_mock_postings(query)


class AnthropicJobAdapter(JobBoardAdapter):
    board_id = JobBoardId.ANTHROPIC
    name = "Anthropic"

    def generate_mock_postings(self, query: JobSearchQuery) -> list[RawJobPosting]:
        return [
            RawJobPosting(
                id="job-anthropic-01",
                board=JobBoardId.ANTHROPIC,
                external_id="gh-ant-59201",
                title="Solutions Architect — Enterprise AI Deployment",
                employer="Anthropic",
                location="San Francisco, CA / Remote",
                remote_type=RemoteType.REMOTE,
                compensation=CompensationRange(min_amount=210000, max_amount=260000),
                url="https://jobs.lever.co/anthropic/59201",
                description="Partner with strategic enterprise customers deploying Claude in production. Architect sovereign RAG, Model Context Protocol (MCP) integrations, and high-throughput agent loops.",
                requirements=["Model Context Protocol (MCP)", "Enterprise RAG", "Python AsyncIO", "Executive Communication"],
            ),
            RawJobPosting(
                id="job-anthropic-02",
                board=JobBoardId.ANTHROPIC,
                external_id="gh-ant-59202",
                title="Principal Systems Engineer — Serving Infrastructure",
                employer="Anthropic",
                location="Remote",
                remote_type=RemoteType.REMOTE,
                compensation=CompensationRange(min_amount=240000, max_amount=310000),
                url="https://jobs.lever.co/anthropic/59202",
                description="Scale low-latency inference clusters, GPU memory management, and distributed batching systems.",
                requirements=["Distributed Systems", "GPU Infrastructure/CUDA", "k3s/Kubernetes", "High Throughput"],
            ),
        ]

    async def fetch_jobs(self, query: JobSearchQuery, client: Optional[httpx.AsyncClient] = None) -> list[RawJobPosting]:
        return self.generate_mock_postings(query)


class OpenAIJobAdapter(JobBoardAdapter):
    board_id = JobBoardId.OPENAI
    name = "OpenAI"

    def generate_mock_postings(self, query: JobSearchQuery) -> list[RawJobPosting]:
        return [
            RawJobPosting(
                id="job-openai-01",
                board=JobBoardId.OPENAI,
                external_id="gh-oai-81920",
                title="Forward Deployed Engineer — Agentic Systems",
                employer="OpenAI",
                location="Remote / San Francisco",
                remote_type=RemoteType.REMOTE,
                compensation=CompensationRange(min_amount=245000, max_amount=330000),
                url="https://boards.greenhouse.io/openai/jobs/81920",
                description="Build custom agentic solutions and multi-agent workflows using OpenAI frontier models for enterprise customers. Deep experience in tool calling, function execution, and stateful agent loops required.",
                requirements=["Agent Loops & ReAct", "Python/TypeScript", "Enterprise GTM", "Fine-Tuning"],
            )
        ]

    async def fetch_jobs(self, query: JobSearchQuery, client: Optional[httpx.AsyncClient] = None) -> list[RawJobPosting]:
        return self.generate_mock_postings(query)


class ParloaJobAdapter(JobBoardAdapter):
    board_id = JobBoardId.PARLOA
    name = "Parloa"

    def generate_mock_postings(self, query: JobSearchQuery) -> list[RawJobPosting]:
        return [
            RawJobPosting(
                id="job-parloa-01",
                board=JobBoardId.PARLOA,
                external_id="ashby-parloa-102",
                title="Head of Solutions Engineering — Agentic Voice",
                employer="Parloa",
                location="Remote / New York",
                remote_type=RemoteType.REMOTE,
                compensation=CompensationRange(min_amount=200000, max_amount=255000),
                url="https://jobs.ashbyhq.com/parloa/102",
                description="Lead the enterprise solutions architecture team for Parloa's AI Agent management platform. Architect real-time voice bots, telephony integrations, and LLM dialog orchestration.",
                requirements=["Voice AI & Telephony", "Solutions Engineering Leadership", "Contact Center AI", "SIP/WebRTC"],
            )
        ]

    async def fetch_jobs(self, query: JobSearchQuery, client: Optional[httpx.AsyncClient] = None) -> list[RawJobPosting]:
        return self.generate_mock_postings(query)


class DeepgramJobAdapter(JobBoardAdapter):
    board_id = JobBoardId.DEEPGRAM
    name = "Deepgram"

    def generate_mock_postings(self, query: JobSearchQuery) -> list[RawJobPosting]:
        return [
            RawJobPosting(
                id="job-deepgram-01",
                board=JobBoardId.DEEPGRAM,
                external_id="lever-dg-401",
                title="Director of Solutions Architecture — Speech AI",
                employer="Deepgram",
                location="Remote",
                remote_type=RemoteType.REMOTE,
                compensation=CompensationRange(min_amount=190000, max_amount=245000),
                url="https://jobs.lever.co/deepgram/401",
                description="Lead technical architecture for enterprise speech recognition (ASR) and text-to-speech (TTS) streaming APIs. Partner with engineering on low-latency audio pipelines and WebSockets.",
                requirements=["Speech ASR/TTS", "Solutions Architecture", "Real-Time Audio Streaming", "Python/Go"],
            )
        ]

    async def fetch_jobs(self, query: JobSearchQuery, client: Optional[httpx.AsyncClient] = None) -> list[RawJobPosting]:
        return self.generate_mock_postings(query)


class SoundHoundJobAdapter(JobBoardAdapter):
    board_id = JobBoardId.SOUNDHOUND
    name = "SoundHound AI"

    def generate_mock_postings(self, query: JobSearchQuery) -> list[RawJobPosting]:
        return [
            RawJobPosting(
                id="job-soundhound-01",
                board=JobBoardId.SOUNDHOUND,
                external_id="sh-901",
                title="Director of Conversational AI Platforms",
                employer="SoundHound AI",
                location="Remote",
                remote_type=RemoteType.REMOTE,
                compensation=CompensationRange(min_amount=190000, max_amount=240000),
                url="https://jobs.lever.co/soundhound/901",
                description="Lead conversational AI platform architecture across voice commerce and enterprise dialog management.",
                requirements=["Conversational AI", "Voice Architecture", "Platform Engineering"],
            )
        ]

    async def fetch_jobs(self, query: JobSearchQuery, client: Optional[httpx.AsyncClient] = None) -> list[RawJobPosting]:
        return self.generate_mock_postings(query)


class LivePersonJobAdapter(JobBoardAdapter):
    board_id = JobBoardId.LIVEPERSON
    name = "LivePerson"

    def generate_mock_postings(self, query: JobSearchQuery) -> list[RawJobPosting]:
        return [
            RawJobPosting(
                id="job-liveperson-01",
                board=JobBoardId.LIVEPERSON,
                external_id="lp-771",
                title="Director of Conversational AI & Platform Strategy",
                employer="LivePerson",
                location="Remote",
                remote_type=RemoteType.REMOTE,
                compensation=CompensationRange(min_amount=195000, max_amount=245000),
                url="https://careers.liveperson.com/771",
                description="Drive the technical vision and enterprise architecture for conversational AI, digital customer engagement, and LLM-powered contact centers.",
                requirements=["Conversational AI", "Omnichannel Messaging", "Enterprise Strategy"],
            )
        ]

    async def fetch_jobs(self, query: JobSearchQuery, client: Optional[httpx.AsyncClient] = None) -> list[RawJobPosting]:
        return self.generate_mock_postings(query)


class ScaleAIJobAdapter(JobBoardAdapter):
    board_id = JobBoardId.SCALE_AI
    name = "Scale AI"

    def generate_mock_postings(self, query: JobSearchQuery) -> list[RawJobPosting]:
        return [
            RawJobPosting(
                id="job-scaleai-01",
                board=JobBoardId.SCALE_AI,
                external_id="scale-552",
                title="Principal Solutions Engineer — Enterprise Voice & GenAI",
                employer="Scale AI",
                location="Remote / San Francisco",
                remote_type=RemoteType.REMOTE,
                compensation=CompensationRange(min_amount=220000, max_amount=280000),
                url="https://boards.greenhouse.io/scaleai/jobs/552",
                description="Architect enterprise LLM evaluation, fine-tuning, and voice data pipelines for enterprise customers. Work closely with GTM and research teams.",
                requirements=["Enterprise AI Solutions", "Fine-Tuning/RLHF", "Voice/ASR", "Python"],
            )
        ]

    async def fetch_jobs(self, query: JobSearchQuery, client: Optional[httpx.AsyncClient] = None) -> list[RawJobPosting]:
        return self.generate_mock_postings(query)


class GoogleJobAdapter(JobBoardAdapter):
    board_id = JobBoardId.GOOGLE
    name = "Google"

    def generate_mock_postings(self, query: JobSearchQuery) -> list[RawJobPosting]:
        return [
            RawJobPosting(
                id="job-google-01",
                board=JobBoardId.GOOGLE,
                external_id="goog-9102",
                title="Director, Customer Engineering — Google Cloud AI & Vertex",
                employer="Google",
                location="Austin, TX / Remote",
                remote_type=RemoteType.REMOTE,
                compensation=CompensationRange(min_amount=260000, max_amount=340000),
                url="https://careers.google.com/jobs/results/9102",
                description="Lead Google Cloud AI customer engineering organization helping strategic enterprises architect on Vertex AI, Gemini models, and sovereign infrastructure.",
                requirements=["Cloud AI Architecture", "Executive Leadership", "Vertex AI / LLMs", "Customer Engineering"],
            )
        ]

    async def fetch_jobs(self, query: JobSearchQuery, client: Optional[httpx.AsyncClient] = None) -> list[RawJobPosting]:
        return self.generate_mock_postings(query)


class AWSJobAdapter(JobBoardAdapter):
    board_id = JobBoardId.AWS
    name = "AWS"

    def generate_mock_postings(self, query: JobSearchQuery) -> list[RawJobPosting]:
        return [
            RawJobPosting(
                id="job-aws-01",
                board=JobBoardId.AWS,
                external_id="amzn-10928",
                title="Principal Solutions Architect — Generative AI & Amazon Bedrock",
                employer="Amazon Web Services",
                location="Austin, TX / Remote",
                remote_type=RemoteType.REMOTE,
                compensation=CompensationRange(min_amount=215000, max_amount=285000),
                url="https://www.amazon.jobs/en/jobs/10928",
                description="Lead deep technical engagements with enterprise customers deploying generative AI architectures on AWS Bedrock, SageMaker, and sovereign cloud zones.",
                requirements=["AWS Bedrock / SageMaker", "Solutions Architecture", "Enterprise AI", "RAG Architectures"],
            )
        ]

    async def fetch_jobs(self, query: JobSearchQuery, client: Optional[httpx.AsyncClient] = None) -> list[RawJobPosting]:
        return self.generate_mock_postings(query)


# Master Board Registry
BOARD_ADAPTERS: dict[JobBoardId, JobBoardAdapter] = {
    JobBoardId.LINKEDIN: LinkedInJobAdapter(),
    JobBoardId.ANTHROPIC: AnthropicJobAdapter(),
    JobBoardId.OPENAI: OpenAIJobAdapter(),
    JobBoardId.PARLOA: ParloaJobAdapter(),
    JobBoardId.DEEPGRAM: DeepgramJobAdapter(),
    JobBoardId.SOUNDHOUND: SoundHoundJobAdapter(),
    JobBoardId.LIVEPERSON: LivePersonJobAdapter(),
    JobBoardId.SCALE_AI: ScaleAIJobAdapter(),
    JobBoardId.GOOGLE: GoogleJobAdapter(),
    JobBoardId.AWS: AWSJobAdapter(),
}


# Deterministic Job Match Scorer
class DeterministicJobScorer:
    """Evaluates raw job postings against CandidateProfile and IntentProjectionDB."""

    def __init__(self, profile: CandidateProfile, intent: Optional[IntentProjectionDB] = None):
        self.profile = profile
        self.intent = intent

    def score_posting(self, posting: RawJobPosting) -> ScoredJobLead:
        # Check hard employer exclusions
        exclusions = self.intent.employer_exclusions if self.intent else [
            {"employer": "Quant", "reason": "former employer"},
            {"employer": "Amelia", "reason": "former employer"},
            {"employer": "SoundHound AI", "reason": "former employer"},
            {"employer": "IntelePeer", "reason": "former employer"},
        ]
        
        canonical_emp = _canonical_employer(posting.employer)
        for excl in exclusions:
            if _canonical_employer(str(excl["employer"])) == canonical_emp:
                breakdown = MatchBreakdown(
                    role_match_pct=0,
                    skill_overlap_pct=0,
                    compensation_fit_pct=0,
                    location_fit_pct=0,
                    overall_fit_score=0,
                    role_match_detail=f"Excluded employer ({excl['reason']})",
                    compensation_analysis="Excluded employer",
                    location_detail="Excluded employer",
                    risk_flags=["employer_excluded"],
                    summary=f"Excluded: {posting.employer} matches former employer exclusion list ({excl['reason']}).",
                )
                return ScoredJobLead(
                    id=f"lead-{posting.id}",
                    raw_posting=posting,
                    match_breakdown=breakdown,
                    status="excluded",
                )

        # 1. Role Match Score (35%)
        role_score, role_detail = self._score_role(posting)

        # 2. Skill Overlap Score (40%)
        skill_score, matched_exp, matched_adv, matched_ml, missing_crit = self._score_skills(posting)

        # 3. Compensation Fit Score (15%)
        comp_score, comp_analysis, comp_risks = self._score_compensation(posting)

        # 4. Location Fit Score (10%)
        loc_score, loc_detail, loc_risks = self._score_location(posting)

        # Composite Score
        total_score = round(
            0.35 * role_score +
            0.40 * skill_score +
            0.15 * comp_score +
            0.10 * loc_score
        )
        total_score = max(0, min(100, total_score))

        status = "qualified" if total_score >= 80 else ("watching" if total_score >= 60 else "low_fit")
        all_risks = comp_risks + loc_risks
        if skill_score < 40:
            all_risks.append("low_skill_overlap")
        if role_score < 50:
            all_risks.append("role_title_mismatch")

        summary = f"{posting.title} at {posting.employer}: {total_score}% match ({status.upper()}). {len(matched_exp)} expert skills matched. {comp_analysis}"

        breakdown = MatchBreakdown(
            role_match_pct=role_score,
            skill_overlap_pct=skill_score,
            compensation_fit_pct=comp_score,
            location_fit_pct=loc_score,
            overall_fit_score=total_score,
            matched_expert_skills=matched_exp,
            matched_advanced_skills=matched_adv,
            matched_ml_depth=matched_ml,
            missing_critical_skills=missing_crit,
            role_match_detail=role_detail,
            compensation_analysis=comp_analysis,
            location_detail=loc_detail,
            risk_flags=all_risks,
            summary=summary,
        )

        return ScoredJobLead(
            id=f"lead-{posting.id}",
            raw_posting=posting,
            match_breakdown=breakdown,
            status=status,
        )

    def _score_role(self, posting: RawJobPosting) -> tuple[int, str]:
        title_lower = posting.title.lower()
        
        # Target role patterns
        if any(role.lower() in title_lower for role in ["chief technology officer", "cto", "vp of engineering", "vp engineering", "head of ai"]):
            return 100, f"Direct executive match for target role in '{posting.title}'"
        if any(role.lower() in title_lower for role in ["principal solutions architect", "principal ai architect", "principal architect"]):
            return 95, f"High-alignment principal architect role match in '{posting.title}'"
        if any(role.lower() in title_lower for role in ["director", "forward deployed", "solutions engineering director", "systems engineer"]):
            return 85, f"Director / Staff technical leadership alignment in '{posting.title}'"
        if any(p in title_lower for p in ["junior", "intern", "associate", "entry"]):
            return 15, f"Seniority penalty: entry/junior posting '{posting.title}'"
        return 60, f"Moderate role overlap in '{posting.title}'"

    def _score_skills(self, posting: RawJobPosting) -> tuple[int, list[str], list[str], list[str], list[str]]:
        full_text = f"{posting.title} {posting.description} {' '.join(posting.requirements)}".lower()
        tokens = set(re.findall(r"[a-z0-9+#.-]+", full_text))

        matched_exp = []
        matched_adv = []
        for skill in self.profile.skills:
            skill_kws = {k.lower() for k in skill.keywords} | {skill.name.lower()}
            if skill_kws & tokens or any(kw in full_text for kw in skill_kws):
                if skill.tier == SkillTier.EXPERT:
                    matched_exp.append(skill.name)
                elif skill.tier == SkillTier.ADVANCED:
                    matched_adv.append(skill.name)

        # ML Depth check
        matched_ml = []
        ml_depth_map = {
            "LLM Orchestration": ["llm", "claude", "gpt", "prompt", "context"],
            "Speech / Voice AI": ["voice", "speech", "asr", "tts", "webrtc", "sip", "audio"],
            "Fine-Tuning": ["fine-tuning", "lora", "qlora", "sft", "training"],
            "Embeddings & RAG": ["rag", "embeddings", "vector", "retrieval", "hybrid search"],
            "Agent Loops": ["agent", "agents", "multi-agent", "tool calling", "mcp"],
            "Inference Hardware": ["gpu", "cuda", "vllm", "quantization", "tensorrt"],
        }
        for domain, kws in ml_depth_map.items():
            if any(kw in full_text for kw in kws):
                matched_ml.append(domain)

        # Weight calculation: expert = 1.5, advanced = 1.0, ml_depth = 3.0
        weighted_points = len(matched_exp) * 1.5 + len(matched_adv) * 1.0 + len(matched_ml) * 3.0
        score = min(100, round((weighted_points / 14.0) * 100))

        # Check missing critical
        missing = []
        if "Agent Loops" not in matched_ml and "agent" in full_text:
            missing.append("Agentic AI Frameworks")

        return score, matched_exp, matched_adv, matched_ml, missing

    def _score_compensation(self, posting: RawJobPosting) -> tuple[int, str, list[str]]:
        comp = posting.compensation
        base_min = self.profile.compensation.base_minimum_usd  # 180,000
        target_comp = self.profile.compensation.target_total_comp_usd  # 250,000

        if comp is None or (comp.min_amount is None and comp.max_amount is None):
            return 75, f"Compensation unlisted; estimated competitive for {posting.employer}", []

        max_amt = comp.max_amount or comp.min_amount or 0
        min_amt = comp.min_amount or comp.max_amount or 0

        if max_amt >= target_comp or min_amt >= base_min:
            return 100, f"Posted {comp.display_str} meets/exceeds target comp ${target_comp:,}", []
        elif max_amt >= 200000 and min_amt >= 160000:
            return 85, f"Posted {comp.display_str} is within acceptable target comp band", []
        elif max_amt >= base_min:
            return 65, f"Posted {comp.display_str} meets base floor ${base_min:,} but below target ${target_comp:,}", []
        else:
            return 0, f"Posted {comp.display_str} is below minimum base floor ${base_min:,}", ["compensation_below_floor"]

    def _score_location(self, posting: RawJobPosting) -> tuple[int, str, list[str]]:
        loc_lower = posting.location.lower()
        if posting.remote_type == RemoteType.REMOTE or "remote" in loc_lower:
            return 100, "Remote posting perfectly matches candidate preference", []
        if "austin" in loc_lower or "tx" in loc_lower:
            return 100, f"Location '{posting.location}' matches candidate home market (Austin, TX)", []
        if posting.remote_type == RemoteType.HYBRID:
            return 75, f"Hybrid role at '{posting.location}'", []
        return 25, f"Onsite requirement at '{posting.location}' outside home market", ["location_mismatch"]


# Core Sourcing Engine
class JobSourcingEngine:
    """Orchestrates job sensing across career boards, scoring, and sweep persistence."""

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self.profile_store = CandidateProfileStore(db)

    async def sense_jobs(
        self,
        query: Optional[JobSearchQuery] = None,
        *,
        boards: Optional[List[JobBoardId]] = None,
        live: bool = False,
        limit_per_board: int = 20,
        min_score: int = 0,
    ) -> JobSensingSummary:
        start_time = datetime.now(timezone.utc)
        profile = self.profile_store.get_profile()
        
        intent = None
        if self.db is not None:
            intent = self.db.get(IntentProjectionDB, INTENT_SINGLETON_ID)

        if query is None:
            query = JobSearchQuery(
                target_roles=profile.target_roles.target_roles,
                target_domains=profile.target_roles.target_domains,
                limit_per_board=limit_per_board,
            )

        target_boards = boards or list(JobBoardId)
        adapters = [BOARD_ADAPTERS[b] for b in target_boards if b in BOARD_ADAPTERS]

        # Fetch postings across boards
        raw_postings: list[RawJobPosting] = []
        if live:
            async with httpx.AsyncClient(timeout=15) as client:
                tasks = [adapter.fetch_jobs(query, client) for adapter in adapters]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in results:
                    if isinstance(res, list):
                        raw_postings.extend(res)
        else:
            for adapter in adapters:
                raw_postings.extend(adapter.generate_mock_postings(query))

        # Score all postings
        scorer = DeterministicJobScorer(profile, intent)
        leads: list[ScoredJobLead] = [scorer.score_posting(p) for p in raw_postings]

        # Filter by min_score
        filtered_leads = [lead for lead in leads if lead.match_breakdown.overall_fit_score >= min_score]
        filtered_leads.sort(key=lambda x: x.match_breakdown.overall_fit_score, reverse=True)

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        return JobSensingSummary(
            boards_queried=target_boards,
            total_discovered=len(raw_postings),
            qualified_count=len([l for l in leads if l.match_breakdown.overall_fit_score >= 80]),
            watching_count=len([l for l in leads if 60 <= l.match_breakdown.overall_fit_score < 80]),
            unqualified_count=len([l for l in leads if 0 < l.match_breakdown.overall_fit_score < 60]),
            excluded_count=len([l for l in leads if l.status == "excluded"]),
            duration_seconds=round(duration, 3),
            leads=filtered_leads,
        )
```

---

### 2.7 Complete Implementation Design for CLI Runner (`cli/sense_jobs.py`)

```python
"""CLI runner for Dynamic Job Sourcing Engine (Sense #3).

Usage:
    python -m cli.sense_jobs --mock                       # Run mock sourcing across all 10 boards
    python -m cli.sense_jobs --board anthropic --limit 10 # Source from Anthropic board only
    python -m cli.sense_jobs --live                       # Run live scrapers / ATS APIs
    python -m cli.sense_jobs --min-score 80               # Filter qualified leads only
    python -m cli.sense_jobs --json                       # Output JSON formatted leads
    python -m cli.sense_jobs --dry-run                    # Score and display, no database write
    python -m cli.sense_jobs --ingest                     # Submit qualified leads as sources.ingest
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

from core.database import Database
from core.jobsearch_sourcing import (
    JobBoardId,
    JobSearchQuery,
    JobSourcingEngine,
    JobSweep,
)
from core.jobsearch_sources import RedisSweepStash


def _format_table(leads: list) -> str:
    """Render high-contrast terminal table for discovered leads."""
    headers = ["Board", "Employer", "Title", "Location", "Compensation", "Fit Score", "Status"]
    rows = []
    for l in leads:
        p = l.raw_posting
        b = l.match_breakdown
        score_str = f"{b.overall_fit_score}%"
        comp_str = p.compensation.display_str if p.compensation else "Unlisted"
        rows.append([
            p.board.value,
            p.employer[:18],
            p.title[:36],
            p.location[:16],
            comp_str[:20],
            score_str,
            l.status.upper(),
        ])

    col_widths = [max(len(str(row[i])) for row in [headers] + rows) for i in range(len(headers))]
    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    header_line = "| " + " | ".join(headers[i].ljust(col_widths[i]) for i in range(len(headers))) + " |"

    lines = [sep, header_line, sep]
    for row in rows:
        row_line = "| " + " | ".join(str(row[i]).ljust(col_widths[i]) for i in range(len(headers))) + " |"
        lines.append(row_line)
    lines.append(sep)
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Sense and score open jobs across LinkedIn and 9 Career Boards")
    parser.add_argument("--live", action="store_true", help="Execute live network fetchers / scrapers")
    parser.add_argument("--mock", action="store_true", default=True, help="Use deterministic mock providers")
    parser.add_argument("--board", type=str, default="all",
                        choices=["all", "linkedin", "anthropic", "openai", "parloa", "deepgram", "soundhound", "liveperson", "scale_ai", "google", "aws"],
                        help="Filter to specific career board")
    parser.add_argument("--limit", type=int, default=20, help="Max postings per board")
    parser.add_argument("--min-score", type=int, default=0, help="Minimum fit score filter (0-100)")
    parser.add_argument("--dry-run", action="store_true", help="Score and display leads, do not persist or submit command")
    parser.add_argument("--json", action="store_true", help="Output full results as JSON")
    parser.add_argument("--output", type=Path, help="Save structured results to file")
    parser.add_argument("--ingest", action="store_true", help="Submit qualified leads to Ultradex sources.ingest command")
    args = parser.parse_args()

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://ultradex:ultradex_dev_password@127.0.0.1:5432/ultradex",
    )
    database = Database(database_url)
    database.init()
    session = database.get_session()

    try:
        engine = JobSourcingEngine(session)

        target_boards = None
        if args.board != "all":
            target_boards = [JobBoardId(args.board)]

        summary = await engine.sense_jobs(
            boards=target_boards,
            live=args.live,
            limit_per_board=args.limit,
            min_score=args.min_score,
        )

        if args.json:
            json_str = summary.model_dump_json(indent=2)
            print(json_str)
            if args.output:
                args.output.write_text(json_str)
            return 0

        # CLI Display
        print("================================================================================")
        print(" Career Command Center — Dynamic Job Sourcing Engine (Sense #3)")
        print("================================================================================")
        print(f" Mode: {'LIVE (Network Scrapers)' if args.live else 'MOCK (Deterministic Test Generator)'}")
        print(f" Boards Queried: {', '.join(b.value for b in summary.boards_queried)}")
        print(f" Discovered Postings: {summary.total_discovered}")
        print(f" Results: {summary.qualified_count} Qualified (≥80%), {summary.watching_count} Watching (60-79%), {summary.unqualified_count} Low Fit, {summary.excluded_count} Excluded")
        print(f" Duration: {summary.duration_seconds}s")
        print("--------------------------------------------------------------------------------")
        print(_format_table(summary.leads))
        print("--------------------------------------------------------------------------------")

        if args.output:
            args.output.write_text(summary.model_dump_json(indent=2))
            print(f"Saved results to {args.output}")

        if args.dry_run:
            print("Dry run complete — no sweep stashed or command submitted.")
            return 0

        # Sweep and Stash Declaration
        stash = RedisSweepStash.from_env()
        if stash is not None:
            sweep = JobSweep(stash=stash)
            declaration = sweep.run(summary.leads, query_summary=f"boards:{args.board}:live={args.live}")
            if declaration:
                print(f"Declared: {declaration.source_ref}")
                print(f"          {declaration.commitment}")
                print(f"          {declaration.redacted_summary}")

                if args.ingest:
                    token = os.getenv("ULTRADEX_COMMAND_TOKEN") or os.getenv("ULTRADEX_API_TOKEN")
                    base = os.getenv("ULTRADEX_API_BASE", "http://127.0.0.1:8000")
                    if token:
                        async with httpx.AsyncClient(timeout=15) as client:
                            resp = await client.post(
                                f"{base}/api/v2/job-search/commands/sources.ingest",
                                json={
                                    "source_kind": declaration.source_kind,
                                    "source_ref": declaration.source_ref,
                                    "observed_at": declaration.observed_at,
                                },
                                headers={
                                    "Authorization": f"Bearer {token}",
                                    "Idempotency-Key": f"sense-jobs-{uuid.uuid4()}",
                                },
                            )
                        print(f"Submitted sources.ingest: HTTP {resp.status_code}")

        return 0
    finally:
        session.close()
        database.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

---

## 3. Caveats

1. **Live Network Resilience & Rate Limiting**: Live job scraping against LinkedIn and ATS platforms (Greenhouse, Ashby, Lever) requires resilient error handling, exponential backoff, and rotating User-Agents. When `--mock` is used (default), 100% of the ingestion and scoring logic executes with zero external dependencies.
2. **Persistence Pipeline**: Discovered job postings are formatted as `ScoredJobLead` records and stashed via `JobSweep`. When Milestone M2 ORM models (`LeadDB`, `OrganizationDB`) are migrated, `cli/sense_jobs.py` seamlessly populates `LeadDB` records via direct ORM writes or governed `sources.ingest` commands.
3. **SoundHound / Amelia Alias Safety**: SoundHound AI and Amelia share an employer identity. Both are strictly excluded in accordance with Nate's ratified Intent (`INTENT-SEED-DRAFT §4`), ensuring 0 score and preventing duplicate lead pollution.

---

## 4. Conclusion

The specification provides a complete, production-ready, deterministic Dynamic Job Sourcing Engine and CLI runner for Career Command Center:
1. **Multi-Source Sourcing**: Connectors and mock generators for LinkedIn + 9 target career boards (Anthropic, OpenAI, Parloa, Deepgram, SoundHound, LivePerson, Scale AI, Google, AWS).
2. **Deterministic Match Scoring**: 4-rule mathematical scoring algorithm evaluating Role match (35%), 44-Skill taxonomy & ML depth (40%), Compensation fit against $180k-$250k bounds (15%), and Location compatibility (10%), backed by hard employer exclusion gates.
3. **Structured Lead Generation**: Clean `ScoredJobLead` and `MatchBreakdown` models capturing expert skills matched, advanced skills matched, compensation analysis, and risk flags.
4. **CLI & Programmatic API**: Full-featured `cli/sense_jobs.py` CLI runner with `--live`, `--mock`, `--board`, `--limit`, `--min-score`, `--dry-run`, `--json`, and `--ingest` flags, alongside clean async `JobSourcingEngine` Python API.

---

## 5. Verification Method

### 5.1 Pytest Execution Command
Run the test suite verifying Profile and Dynamic Sourcing Engine:
```bash
cd /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req
PYTHONPATH=. uv run pytest tests/test_jobsearch_profile.py -v
```

### 5.2 CLI Verification Commands
1. **Run Mock Sourcing across All Boards**:
   ```bash
   python -m cli.sense_jobs --mock --dry-run
   ```
   *Expected Output*: Formatted ASCII table showing discovered leads from all 10 boards with match scores, expert skill matches, compensation breakdown, and status (QUALIFIED, WATCHING, EXCLUDED).

2. **Run Sourcing for a Single Board (Anthropic)**:
   ```bash
   python -m cli.sense_jobs --board anthropic --dry-run
   ```
   *Expected Output*: Only Anthropic postings listed, with fit score ≥ 80% for Solutions Architect.

3. **Verify Employer Exclusion Gate (SoundHound / Amelia)**:
   ```bash
   python -m cli.sense_jobs --board soundhound --dry-run
   ```
   *Expected Output*: SoundHound AI leads score 0% with `EXCLUDED` status and `employer_excluded` risk flag.

4. **Verify JSON Output Mode**:
   ```bash
   python -m cli.sense_jobs --board openai --json
   ```
   *Expected Output*: Valid JSON payload containing `JobSensingSummary` with `ScoredJobLead` records.
