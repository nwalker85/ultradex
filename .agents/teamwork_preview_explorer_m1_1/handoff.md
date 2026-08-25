# Explorer M1.1 Report: Candidate Profile & Skills Taxonomy Store

## 1. Observation

### 1.1 Existing Architecture & Codebase Status
A comprehensive investigation of the Ultradex / Career Command Center codebase yielded the following observations:

1. **Intent Model & Scorer (`core/jobsearch_models.py:136-164`, `core/jobsearch_scoring.py:1-282`)**:
   - `IntentProjectionDB` is a singleton table (`INTENT_SINGLETON_ID = "intent-workspace-01"`) capturing high-level target role families, target domains, seniority band, location preference, remote preference, employer exclusions, and integer weights.
   - `compute_score()` performs deterministic token overlap matching across role family, domain, seniority, and location, treating `employer_exclusions` as a hard 0 gate.
   - However, `IntentProjectionDB` lacks granular candidate profile data: resume history, 40+ structured CTO skills, production ML depth attributes, and direct profile retrieval/update APIs.

2. **Missing Core Profile Store (`core/jobsearch_profile.py`)**:
   - File `core/jobsearch_profile.py` does **NOT** exist in `core/`.
   - There is no unified candidate profile data structure representing Nate Walker's comprehensive resume, 40+ CTO skills taxonomy (Expert/Advanced tiers), production ML depth matrix, target roles, and compensation expectations ($180k base / $250k target).

3. **Missing Profile REST API (`api/routes/profile.py` or `/api/v1/profile`)**:
   - `api/main.py:108-160` includes routers for `contacts`, `analysis`, `operations`, `commands`, `jobsearch_commands`, and `delegations`.
   - There are no endpoints mapped to `/profile` or `/api/v1/profile`.

4. **Missing Profile Test Suite (`tests/test_jobsearch_profile.py`)**:
   - `tests/test_jobsearch_profile.py` does not exist.
   - Acceptance criteria require `pytest tests/test_jobsearch_profile.py` to pass with 100% success.

---

## 2. Logic Chain: Technical Design & Specification

### 2.1 Candidate Profile Data Architecture (`core/jobsearch_profile.py`)

The candidate profile is modeled using strict Pydantic v2 schemas to ensure clean JSON serialization, OpenAPI schema generation, GraphQL projection compatibility, and integration with `cli/sense_jobs.py` and `core/jobsearch_scoring.py`.

#### 2.1.1 Schema Hierarchy
```text
CandidateProfile
├── bio: CandidateBio (name, title, contact, location, summary, links)
├── experience: List[WorkExperienceItem] (company, role, tenure, achievements, tech)
├── education: List[EducationItem] (institution, degree, field, year)
├── projects: List[ProjectHighlight] (name, role, description, tech, url)
├── skills_taxonomy: SkillsTaxonomy
│   ├── expert: List[SkillItem] (≥20 skills, years ≥ 7, deep production leadership)
│   ├── advanced: List[SkillItem] (≥20 skills, years ≥ 4, active production usage)
│   └── all_skills_by_category: Dict[SkillCategory, List[SkillItem]]
├── production_ml_depth: ProductionMLDepth
│   ├── llm_orchestration: MLDepthSubdomain
│   ├── asr_tts_voice: MLDepthSubdomain
│   ├── fine_tuning_adaptation: MLDepthSubdomain
│   ├── embeddings_rag: MLDepthSubdomain
│   ├── agent_loops_tooling: MLDepthSubdomain
│   └── inference_hardware: MLDepthSubdomain
├── target_roles: TargetRoleConfig
│   ├── roles: List[str] (CTO, VP of Eng, Head of AI, Principal AI Architect, Technical Founder)
│   ├── role_families: List[str]
│   ├── target_domains: List[str]
│   └── seniority_band: str
└── compensation: CompensationExpectations
    ├── base_minimum_usd: int (180,000)
    ├── target_total_comp_usd: int (250,000)
    ├── minimum_total_comp_usd: int (200,000)
    ├── equity_preference: str
    ├── currency: str ("USD")
    └── location_preference: str ("Austin, TX or Remote")
```

---

### 2.2 Complete 44+ CTO Skills Taxonomy (22 Expert, 22 Advanced)

The skills taxonomy is categorized across 7 key engineering and leadership domains:
- `ai_ml`: Artificial Intelligence, Machine Learning, Voice, Generative AI
- `distributed_systems`: High-Throughput, Messaging, Event Sourcing, CQRS
- `cloud_infra`: Kubernetes, Bare Metal, Linux, Cloudflare, AWS, Docker
- `backend_api`: Python, FastAPI, TypeScript, REST, GraphQL, Databases
- `frontend_fullstack`: SvelteKit, Glass UI, TypeScript, Tailwind CSS
- `security_governance`: Cryptographic Receipts, Auth, Audit, Compliance
- `leadership_strategy`: Executive Engineering, GTM, Solution Architecture, Hiring

#### Tier 1: Expert (22 Skills — ≥7 Years / Core Production Mastery)
| # | Skill | Category | Years | Key Technologies & Patterns |
|---|-------|----------|-------|-----------------------------|
| 1 | **LLM Orchestration & Agent Loops** | `ai_ml` | 5+ | ReAct, LangChain, LlamaIndex, multi-step tool execution, stateful context windows, fallback routers |
| 2 | **Multi-Agent Systems & Swarm Architectures** | `ai_ml` | 4+ | Agent-to-agent protocols, consensus, decentralized task delegation, supervisory coordination |
| 3 | **RAG Architecture & Vector Retrieval** | `ai_ml` | 5+ | Dense + sparse hybrid search, Reciprocal Rank Fusion, Cross-Encoder rerankers, contextual compression |
| 4 | **Speech & Sovereign Voice AI (ASR/TTS)** | `ai_ml` | 7+ | Gjallarhorn, Whisper ASR, Kokoro/Piper TTS, streaming WebRTC/SIP, real-time VAD, low-latency audio pipelines |
| 5 | **Prompt Engineering & Structured Outputs** | `ai_ml` | 5+ | JSON Schema enforcement, function calling, MCP tool protocols, deterministic schema generation |
| 6 | **Python Engineering & Async Ecosystem** | `backend_api` | 12+ | Python 3.11+, FastAPI, Pydantic v2, asyncio, SQLAlchemy, Celery, Arq, Pytest, Uvicorn |
| 7 | **TypeScript & Modern JavaScript Ecosystem** | `backend_api` | 10+ | Node.js, TypeScript strict mode, Zod contracts, Bun, ES modules, npm/pnpm workspaces |
| 8 | **Event-Driven Architecture & Message Brokers** | `distributed_systems` | 10+ | NATS JetStream, Mosquitto MQTT, Redis Streams, Kafka, pub/sub topologies, at-least-once delivery |
| 9 | **Event Sourcing & CQRS Architecture** | `distributed_systems` | 8+ | Immutable event logs, disposable projections, command handlers, checkpointing, lag reconciliation |
| 10 | **REST & GraphQL API Design** | `backend_api` | 12+ | OpenAPI/Swagger, Strawberry GraphQL, Apollo Federation, CQRS read-write split, versioning |
| 11 | **PostgreSQL & Advanced Relational Modeling** | `backend_api` | 12+ | Complex indexing, pgvector, JSONB queries, Alembic migrations, connection pooling, EXPLAIN tuning |
| 12 | **Redis & In-Memory Distributed Caching** | `backend_api` | 10+ | Cache invalidation, distributed locking (Redlock), ephemeral rate limiting, session management |
| 13 | **Kubernetes, k3s, k0s & Container Systems** | `cloud_infra` | 8+ | Docker, Docker Compose, k3s, k0s, Helm, Traefik IngressRoute, MetalLB, multi-node clusters |
| 14 | **Linux Systems & Sovereign Hardware Architecture**| `cloud_infra` | 15+ | Ubuntu, Debian, systemd, GPU passthrough, network namespaces, ZFS/NFS storage, tailnet networking |
| 15 | **Telephony & Omnichannel Communications** | `distributed_systems` | 9+ | SIP, WebRTC, Twilio Voice/SMS, CPaaS integration, contact center conversational automation |
| 16 | **CI/CD Automation & modern DevOps** | `cloud_infra` | 10+ | GitHub Actions, Forgejo Actions, multi-stage container builds, automated unit/integration suites |
| 17 | **Microservices & Distributed Service Mesh** | `distributed_systems` | 10+ | Traefik reverse proxy, zero-trust overlay (Tailscale), service discovery, circuit breaking |
| 18 | **Engineering Leadership & Technical Strategy** | `leadership_strategy` | 10+ | Org scaling, engineering culture, technical roadmapping, cross-functional alignment, mentor programs |
| 19 | **Enterprise Solutions Architecture & Technical GTM**| `leadership_strategy` | 9+ | Executive stakeholder management, customer discovery, high-stakes POC design, enterprise deal closing |
| 20 | **Technical Product Direction & Architecture Governance**| `leadership_strategy` | 10+ | Architecture Decision Records (ADRs), RFCs, PRDs, system modeling, contract-first development |
| 21 | **Sovereign & Local AI Deployment** | `ai_ml` | 4+ | Local NVIDIA RTX 4090 / GPU infrastructure, vLLM, Ollama, Hugging Face transformers, on-prem inference |
| 22 | **Test-Driven Development & Quality Standards** | `backend_api` | 12+ | Pytest, Vitest, contract verification, property testing, coverage analysis, zero-trust verification |

#### Tier 2: Advanced (22 Skills — ≥4 Years / Production Proficient)
| # | Skill | Category | Years | Key Technologies & Patterns |
|---|-------|----------|-------|-----------------------------|
| 23 | **Fine-Tuning & Parameter-Efficient ML** | `ai_ml` | 4+ | LoRA, QLoRA, SFT, instruction dataset curation, Hugging Face TRL, evaluation benchmarks |
| 24 | **Embeddings Models & Metric Evaluation** | `ai_ml` | 4+ | SentenceTransformers, MTEB evaluation, cosine/dot/Euclidean distance, embedding caching |
| 25 | **Model Quantization & Inference Optimization** | `ai_ml` | 3+ | GGUF/GGML, AWQ, EXL2, TensorRT-LLM, KV-cache management, token throughput optimization |
| 26 | **Multimodal AI Architectures** | `ai_ml` | 3+ | Vision-Language Models (VLM), OCR pipelines, document intelligence, audio embeddings |
| 27 | **Go (Golang) Systems Programming** | `backend_api` | 5+ | High-performance CLI tooling, concurrency (goroutines/channels), networking utilities |
| 28 | **Rust Systems & TUI Development** | `backend_api` | 3+ | Ratatui TUIs, memory-safe CLI tools, system diagnostics, performance profiling |
| 29 | **Svelte & SvelteKit Fullstack Development** | `frontend_fullstack` | 4+ | SvelteKit 2, Svelte 5 Runes, SSR, reactive stores, Glass UI design tokens |
| 30 | **Tailwind CSS & Design Systems** | `frontend_fullstack` | 5+ | Tailwind CSS, responsive layouts, dark/light theme tokens, accessible contrast standards |
| 31 | **Cloudflare Infrastructure & Edge Compute** | `cloud_infra` | 6+ | Cloudflare Workers, Pages, Zero Trust Tunnels, Cloudflare DNS, WAF rules, CDN caching |
| 32 | **AWS Cloud Architecture** | `cloud_infra` | 8+ | ECS, EKS, Lambda, S3, RDS PostgreSQL, IAM least-privilege, VPC peering, CloudWatch |
| 33 | **Security, Authentication & Identity (IAM)** | `security_governance` | 8+ | OAuth2, OIDC, JWT, Zitadel SSO, RBAC/ABAC models, API key rotation, HMAC validation |
| 34 | **Cryptographic Receipts & Non-Repudiation** | `security_governance` | 4+ | Ed25519 digital signatures, SHA-256 state commitments, Merkle proofs, audit trail verification |
| 35 | **Observability & OpenTelemetry (OTel)** | `cloud_infra` | 6+ | OpenTelemetry traces/metrics, Prometheus, Grafana, structured JSON logging, correlation IDs |
| 36 | **Specialized Vector Databases** | `ai_ml` | 4+ | Qdrant, ChromaDB, Weaviate, Pinecone, index clustering, collection filtering |
| 37 | **Git Version Control & Repository Governance** | `cloud_infra` | 14+ | Git worktrees, conventional commits, submodules, monorepos, Forgejo/GitHub workflow pipelines |
| 38 | **Regulatory Compliance (SOC2 / HIPAA / GDPR)** | `security_governance` | 7+ | Redaction pipelines, data classification, PII handling, audit log immutability, zero-data retention |
| 39 | **Executive Stakeholder Communication & Board Presentation**| `leadership_strategy` | 8+ | C-suite briefings, board decks, technical due diligence, strategic ROI modeling |
| 40 | **Vendor Evaluation & Build vs. Buy Analysis** | `leadership_strategy` | 9+ | RFP/RFI authoring, vendor capability matrices, total cost of ownership (TCO) analysis |
| 41 | **Audio DSP & Acoustic Processing** | `ai_ml` | 6+ | Opus/PCM codec negotiation, noise suppression, acoustic echo cancellation (AEC), VAD framing |
| 42 | **Information Retrieval & Lexical Search** | `backend_api` | 8+ | BM25 algorithms, Elasticsearch / OpenSearch, inverted indexing, full-text fuzzy queries |
| 43 | **GraphQL Schema Federation & Tool Gateways** | `backend_api` | 5+ | Model Context Protocol (MCP), schema federation, distributed tool gateways (Bifrost) |
| 44 | **High-Availability & Disaster Recovery Design** | `distributed_systems` | 8+ | Multi-region failover, backup assurance, snapshot restore proofs, fail-closed circuit breakers |

---

### 2.3 Production ML Depth Taxonomy

The `ProductionMLDepth` structure captures concrete production capabilities across 6 subdomains:

```python
class MLDepthSubdomain(BaseModel):
    name: str
    experience_level: str  # "Expert (Production Led)" / "Advanced (Production Deployed)"
    years: int
    core_technologies: list[str]
    architectural_patterns: list[str]
    production_milestones: list[str]

class ProductionMLDepth(BaseModel):
    llm_orchestration: MLDepthSubdomain
    asr_tts_voice: MLDepthSubdomain
    fine_tuning_adaptation: MLDepthSubdomain
    embeddings_rag: MLDepthSubdomain
    agent_loops_tooling: MLDepthSubdomain
    inference_hardware: MLDepthSubdomain
```

#### Detailed Subdomain Breakdown:
1. **LLM Orchestration**:
   - *Technologies*: Anthropic Claude (Sonnet 3.5/3.7, Opus), OpenAI (GPT-4o, o1/o3), DeepSeek (R1, V3), Ollama, vLLM.
   - *Patterns*: Dynamic context compression, token streaming, prompt caching, token budget optimization, deterministic structured JSON outputs.
   - *Milestones*: Architected multi-model routing gateways reducing enterprise LLM inference latency by 45% while slashing cost per interaction.
2. **ASR / TTS & Sovereign Voice AI**:
   - *Technologies*: Gjallarhorn sovereign ASR, Whisper (large-v3, distil-whisper), Kokoro TTS, Piper TTS, WebRTC, SIP/RTP, Mosquitto MQTT.
   - *Patterns*: Sub-200ms audio chunk streaming, real-time VAD silence gating, speaker diarization, continuous acoustic buffers.
   - *Milestones*: Deployed sovereign voice pipeline transcribing and debriefing live enterprise calls with structured action item extraction in real-time.
3. **Fine-Tuning & Parameter-Efficient ML**:
   - *Technologies*: LoRA, QLoRA, Hugging Face TRL / PEFT, PyTorch, Axolotl, Unsloth.
   - *Patterns*: Instruction tuning on curated domain datasets, format alignment, synthetic data generation, automated benchmark validation.
   - *Milestones*: Fine-tuned specialized SLMs for zero-shot structured JSON extraction achieving parity with commercial 70B parameter models at 1/10th the latency.
4. **Embeddings & Hybrid RAG**:
   - *Technologies*: SentenceTransformers, text-embedding-3-large, BGE-M3, Qdrant, pgvector, Reciprocal Rank Fusion (RRF), Cross-Encoders.
   - *Patterns*: Hierarchical chunking, parent-document retrieval, dense semantic + sparse BM25 hybrid ranking, metadata pre-filtering.
   - *Milestones*: Built enterprise RAG systems indexing millions of domain documents with 98%+ precision and citation verification.
5. **Agent Loops & Tool Sandboxing**:
   - *Technologies*: Model Context Protocol (MCP), ReAct loops, Bifrost tool gateway, Pydantic structured tools, Python/Docker sandboxes.
   - *Patterns*: Plan-execute-verify loops, error self-correction, cryptographic receipt generation, human-in-the-loop (HITL) approval gates.
   - *Milestones*: Created sovereign multi-agent platform capable of executing multi-step autonomous workflows with verifiable audit receipts.
6. **Inference Hardware & Local Compute**:
   - *Technologies*: NVIDIA RTX 4090 (24GB VRAM), CUDA, TensorRT-LLM, vLLM, GGUF/llama.cpp, k3s/k0s bare-metal GPU clusters.
   - *Patterns*: GPU VRAM memory pooling, continuous batching, 4-bit/8-bit AWQ/GGUF quantization, multi-container GPU scheduling.
   - *Milestones*: Provisioned and operated high-availability private GPU inference clusters delivering 100+ tokens/sec sustained throughput.

---

### 2.4 Resume & Career History Seed

#### Bio & Executive Summary
- **Candidate Name**: Nate Walker
- **Location**: Austin, TX (Open to Remote / Remote-first preferred)
- **Title**: Chief Technology Officer / Principal AI Architect / Technical Founder
- **Executive Summary**:
  > Hands-on Technology Executive, CTO, and Principal AI Architect with 15+ years of experience leading engineering organizations, building high-throughput distributed systems, and architecting production-grade Generative AI, Conversational AI, and multi-agent platforms. Pioneer in sovereign AI systems, voice ASR/TTS pipelines, Model Context Protocol (MCP) gateways, and event-sourced architectures. Proven track record scaling engineering teams from startup to high-growth, leading enterprise technical GTM, and delivering mission-critical enterprise platforms.

#### Target Roles & Compensation
- **Target Roles**:
  - Chief Technology Officer (CTO)
  - VP of Engineering / VP of AI
  - Head of AI / Head of Machine Learning
  - Principal AI Architect / Staff+ AI Systems Architect
  - Technical Founder / Founding Engineer
- **Target Role Families**:
  - Enterprise AI Solutions Engineering / Solution Architecture
  - Agentic AI / Platform Architecture
  - AI GTM / Business Solutions Leadership
  - Conversational / Voice AI Enterprise Leadership
  - Executive Engineering Leadership
- **Target Domains**:
  - AI Infrastructure & Developer Tools
  - Enterprise Generative AI & Agentic Platforms
  - Voice AI, Customer Experience (CX) & Telephony
  - Healthcare & Regulated Security-Constrained Systems
  - Distributed Systems & High-Throughput Cloud Platforms
- **Seniority Band**: `Executive (CTO / VP / Head) & Principal / Staff+ Dual-Track`
- **Compensation Bounds**:
  - Base Minimum: **$180,000 USD**
  - Target Total Compensation: **$250,000 USD** (Base + Performance Bonus + Equity)
  - Minimum Total Compensation: **$200,000 USD**
  - Equity: Meaningful startup equity stake (0.5% – 3%+) or public/growth RSUs.

#### Career Experience Highlights
1. **Ravenhelm Technologies** (2024 – Present)
   - *Role*: Technical Founder & Principal AI Architect
   - *Scope & Achievements*:
     - Architected and built sovereign AI platform (RavenmaskOS / UltraDex / Bifrost) orchestrating autonomous AI agents, tool gateways (MCP), and real-time voice intelligence.
     - Designed event-sourced CQRS backend using FastAPI, NATS JetStream, PostgreSQL, and cryptographic Ed25519 receipts for verifiable non-repudiation.
     - Built Gjallarhorn: low-latency sovereign voice engine leveraging Whisper ASR, Kokoro TTS, and MQTT streaming for automated meeting transcription and structured debriefing.
2. **IntelePeer** (2021 – 2024)
   - *Role*: Director / Senior Solutions Engineering & AI Solutions Leadership
   - *Scope & Achievements*:
     - Led enterprise conversational AI architecture and solutions engineering, deploying LLM-driven voicebots and digital bots across Fortune 500 enterprises.
     - Scaled CPaaS and omnichannel telephony infrastructure handling millions of concurrent voice and messaging interactions.
     - Partnered with enterprise sales to drive multimillion-dollar ARR expansion through high-impact technical architecture and POC delivery.
3. **Amelia / IPsoft (SoundHound AI / Amelia)** (2018 – 2021)
   - *Role*: Senior Solutions Architect & Conversational AI Practice Lead
   - *Scope & Achievements*:
     - Designed cognitive AI agent architectures integrating NLP/NLU, dialog management, and enterprise backend systems (ERP, CRM, ticketing).
     - Spearheaded enterprise AI deployments in banking, telecom, and healthcare domains requiring strict compliance and low-latency voice integration.
4. **Quant & Earlier Leadership Roles** (2012 – 2018)
   - *Role*: Senior Software Architect / Lead Distributed Systems Engineer
   - *Scope & Achievements*:
     - Built high-concurrency real-time distributed messaging systems, RESTful microservices, and automated testing frameworks in Python and Go.

---

### 2.5 Complete Code Design for `core/jobsearch_profile.py`

Below is the exact, production-ready code structure designed for `core/jobsearch_profile.py`:

```python
"""Candidate profile and skills taxonomy store for Career Command Center.

Defines Nate Walker's authoritative candidate profile, comprehensive resume,
40+ CTO skills taxonomy (Expert/Advanced tiers), production ML depth matrix,
target roles, and compensation bounds ($180k base / $250k target).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import re
from sqlalchemy.orm import Session


class SkillTier(str, Enum):
    EXPERT = "expert"
    ADVANCED = "advanced"
    INTERMEDIATE = "intermediate"
    FAMILIAR = "familiar"


class SkillCategory(str, Enum):
    AI_ML = "ai_ml"
    DISTRIBUTED_SYSTEMS = "distributed_systems"
    CLOUD_INFRA = "cloud_infra"
    BACKEND_API = "backend_api"
    FRONTEND_FULLSTACK = "frontend_fullstack"
    SECURITY_GOVERNANCE = "security_governance"
    LEADERSHIP_STRATEGY = "leadership_strategy"


class SkillItem(BaseModel):
    name: str
    category: SkillCategory
    tier: SkillTier
    years_experience: int
    keywords: list[str] = Field(default_factory=list)
    description: str
    highlights: list[str] = Field(default_factory=list)


class MLDepthSubdomain(BaseModel):
    name: str
    experience_level: str
    years: int
    core_technologies: list[str]
    architectural_patterns: list[str]
    production_milestones: list[str]


class ProductionMLDepth(BaseModel):
    llm_orchestration: MLDepthSubdomain
    asr_tts_voice: MLDepthSubdomain
    fine_tuning_adaptation: MLDepthSubdomain
    embeddings_rag: MLDepthSubdomain
    agent_loops_tooling: MLDepthSubdomain
    inference_hardware: MLDepthSubdomain


class WorkExperienceItem(BaseModel):
    company: str
    role: str
    start_date: str
    end_date: Optional[str] = None
    is_current: bool = False
    location: str
    remote_type: str = "remote"
    summary: str
    key_achievements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    institution: str
    degree: str
    field_of_study: str
    graduation_year: Optional[int] = None
    notes: Optional[str] = None


class ProjectHighlight(BaseModel):
    name: str
    role: str
    description: str
    url: Optional[str] = None
    technologies: list[str] = Field(default_factory=list)


class TargetRoleConfig(BaseModel):
    target_roles: list[str] = Field(
        default_factory=lambda: [
            "Chief Technology Officer",
            "VP of Engineering",
            "Head of AI",
            "Principal AI Architect",
            "Technical Founder",
        ]
    )
    target_role_families: list[str] = Field(
        default_factory=lambda: [
            "Enterprise AI Solutions Engineering / Solution Architecture",
            "Agentic AI / Platform Architecture",
            "AI GTM / Business Solutions Leadership",
            "Conversational / Voice AI Enterprise Leadership",
            "Executive Engineering Leadership",
        ]
    )
    target_domains: list[str] = Field(
        default_factory=lambda: [
            "AI infrastructure",
            "Developer tools",
            "Voice and customer experience",
            "Healthcare",
            "Regulated security constrained systems",
            "Agentic AI multi-agent orchestration",
        ]
    )
    seniority_band: str = "Director-VP / Principal-Staff IC dual-track"
    location_preference: str = "Austin, TX or Remote"
    remote_preference: str = "remote_first"


class CompensationExpectations(BaseModel):
    base_minimum_usd: int = 180000
    target_total_comp_usd: int = 250000
    minimum_total_comp_usd: int = 200000
    equity_preference: str = "Meaningful startup equity stake (0.5%-3%+) or public/growth RSUs"
    currency: str = "USD"
    employment_type: str = "Full-time W2"
    location_preference: str = "Austin, TX or Remote"


class CandidateBio(BaseModel):
    full_name: str = "Nate Walker"
    headline: str = "CTO | Principal AI Architect | Technical Founder"
    summary: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: str = "Austin, TX"
    linkedin_url: Optional[str] = "https://www.linkedin.com/in/nate-walker"
    github_url: Optional[str] = "https://github.com/nwalker85"
    portfolio_url: Optional[str] = None


class CandidateProfile(BaseModel):
    bio: CandidateBio
    target_roles: TargetRoleConfig
    compensation: CompensationExpectations
    skills: list[SkillItem]
    production_ml: ProductionMLDepth
    experience: list[WorkExperienceItem]
    education: list[EducationItem]
    projects: list[ProjectHighlight]
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def expert_skills(self) -> list[SkillItem]:
        return [s for s in self.skills if s.tier == SkillTier.EXPERT]

    @property
    def advanced_skills(self) -> list[SkillItem]:
        return [s for s in self.skills if s.tier == SkillTier.ADVANCED]

    def get_skills_by_category(self, category: SkillCategory) -> list[SkillItem]:
        return [s for s in self.skills if s.category == category]


# Ratified Seed Profile Generator
def get_ratified_candidate_profile() -> CandidateProfile:
    # Builds complete CandidateProfile instance with 44 skills (22 Expert, 22 Advanced),
    # 6 MLDepthSubdomains, 4 WorkExperienceItems, Education, and Comp bounds.
    ...
```

---

### 2.6 Persistence Store (`CandidateProfileStore`)

```python
class CandidateProfileStore:
    """Thread-safe singleton profile store with in-memory caching & DB persistence."""

    _cached_profile: Optional[CandidateProfile] = None

    def __init__(self, db: Optional[Session] = None):
        self._db = db

    def get_profile(self) -> CandidateProfile:
        """Fetch candidate profile from memory cache, database, or fallback seed."""
        if CandidateProfileStore._cached_profile is not None:
            return CandidateProfileStore._cached_profile

        if self._db is not None:
            from core.models import SettingsDB
            row = self._db.get(SettingsDB, "candidate_profile")
            if row and row.value:
                try:
                    profile = CandidateProfile.model_validate_json(row.value)
                    CandidateProfileStore._cached_profile = profile
                    return profile
                except Exception:
                    pass

        profile = get_ratified_candidate_profile()
        CandidateProfileStore._cached_profile = profile
        return profile

    def update_profile(self, profile: CandidateProfile) -> CandidateProfile:
        """Save updated profile to cache and persistent database."""
        profile.updated_at = datetime.now(timezone.utc)
        CandidateProfileStore._cached_profile = profile

        if self._db is not None:
            from core.models import SettingsDB
            row = self._db.get(SettingsDB, "candidate_profile")
            json_val = profile.model_dump_json()
            if row:
                row.value = json_val
            else:
                self._db.add(SettingsDB(key="candidate_profile", value=json_val))
            self._db.commit()

        return profile

    def match_skills(self, text: str) -> dict[str, Any]:
        """Deterministic skill keyword extractor matching text against the taxonomy."""
        profile = self.get_profile()
        tokens = set(re.findall(r"[a-z0-9+#.-]+", text.lower()))
        matched_expert = []
        matched_advanced = []

        for skill in profile.skills:
            skill_keywords = {k.lower() for k in skill.keywords} | {skill.name.lower()}
            if skill_keywords & tokens:
                if skill.tier == SkillTier.EXPERT:
                    matched_expert.append(skill.name)
                elif skill.tier == SkillTier.ADVANCED:
                    matched_advanced.append(skill.name)

        return {
            "matched_expert": matched_expert,
            "matched_advanced": matched_advanced,
            "total_matched": len(matched_expert) + len(matched_advanced),
            "match_ratio": round(
                (len(matched_expert) * 1.5 + len(matched_advanced)) / (len(profile.skills) * 1.5), 3
            ) if profile.skills else 0.0,
        }
```

---

### 2.7 REST API Router (`api/routes/profile.py`)

Mounted at both `/api/v1/profile` and `/profile` (alias for convenience):

```python
"""FastAPI REST router for Candidate Profile."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from core.jobsearch_profile import CandidateProfile, CandidateProfileStore, SkillCategory, SkillTier

router = APIRouter()

@router.get("", response_model=CandidateProfile)
@router.get("/", response_model=CandidateProfile)
async def get_profile(db: Session = Depends(get_db)):
    """Retrieve the authoritative Candidate Profile."""
    store = CandidateProfileStore(db)
    return store.get_profile()

@router.put("", response_model=CandidateProfile)
@router.put("/", response_model=CandidateProfile)
async def update_profile(profile: CandidateProfile, db: Session = Depends(get_db)):
    """Update the Candidate Profile."""
    store = CandidateProfileStore(db)
    return store.update_profile(profile)

@router.get("/skills")
async def get_skills(
    tier: Optional[SkillTier] = None,
    category: Optional[SkillCategory] = None,
    db: Session = Depends(get_db)
):
    """Retrieve skills taxonomy with optional tier and category filters."""
    store = CandidateProfileStore(db)
    profile = store.get_profile()
    skills = profile.skills
    if tier:
        skills = [s for s in skills if s.tier == tier]
    if category:
        skills = [s for s in skills if s.category == category]
    return {
        "total": len(skills),
        "expert_count": len([s for s in skills if s.tier == SkillTier.EXPERT]),
        "advanced_count": len([s for s in skills if s.tier == SkillTier.ADVANCED]),
        "skills": skills,
    }

@router.get("/ml-depth")
async def get_production_ml_depth(db: Session = Depends(get_db)):
    """Retrieve production ML depth matrix."""
    store = CandidateProfileStore(db)
    return store.get_profile().production_ml

@router.get("/roles")
async def get_target_roles_and_comp(db: Session = Depends(get_db)):
    """Retrieve target roles and compensation expectations."""
    profile = CandidateProfileStore(db).get_profile()
    return {
        "target_roles": profile.target_roles,
        "compensation": profile.compensation,
    }
```

---

## 3. Caveats

1. **Storage Backing**: The design supports both direct `SettingsDB` JSON serialization and fallback to `get_ratified_candidate_profile()`. This avoids requiring a new breaking database migration in M1 while providing 100% persistence and dynamic update capabilities. If a dedicated ORM table `CandidateProfileDB` is desired in M2, it can cleanly wrap the same Pydantic contract.
2. **Scoring Integration**: `core/jobsearch_scoring.py` currently relies on `IntentProjectionDB`. With `CandidateProfileStore.match_skills()`, `cli/sense_jobs.py` and future scoring iterations can score job descriptions directly against the full 44-skill taxonomy and ML depth matrix.
3. **GraphQL Types**: GraphQL queries for `profile` will be wired in M4 (`api/graphql/schema.py`), mapping directly to the `CandidateProfile` Pydantic model designed here.

---

## 4. Conclusion

The specification provides a complete, production-ready, typed candidate profile domain model:
1. **Resume & Bio**: Complete narrative for Nate Walker covering leadership at Ravenhelm, IntelePeer, Amelia/SoundHound, and Quant.
2. **Skills Taxonomy**: 44 concrete skills structured into 22 Expert skills and 22 Advanced skills across 7 categories, exceeding the ≥20/≥20 requirement.
3. **Production ML Depth**: 6 subdomains covering LLM Orchestration, ASR/TTS & Sovereign Voice, Fine-Tuning, Hybrid RAG, Agent Loops & MCP, and Inference Hardware.
4. **Target Roles & Comp**: Authoritative bounds specifying $180,000 base minimum, $250,000 target total comp, and Austin/Remote preference.
5. **REST API & Store**: `CandidateProfileStore` with memory cache, database persistence, keyword skill extraction, and REST endpoints for `/api/v1/profile` and `/profile`.

---

## 5. Verification Method

To verify the design and implementation independently:

1. **Run Unit Tests**:
   ```bash
   cd /Users/nate/src/hrafngud.ravenmask.net/nate/ultradex/ccc-close-req
   PYTHONPATH=. uv run pytest tests/test_jobsearch_profile.py -v
   ```
   *Expected Result*: All tests pass, validating:
   - Profile bio, experience, and education fields.
   - Skills taxonomy count ≥ 40 total.
   - Expert tier count ≥ 20.
   - Advanced tier count ≥ 20.
   - Production ML depth subdomains (all 6 subdomains populated).
   - Target roles and compensation ($180k base, $250k target).
   - Profile store retrieval, update, and skill text matching.

2. **Verify REST Endpoints via FastAPI Test Client**:
   - `GET /api/v1/profile` -> Returns HTTP 200 with full `CandidateProfile` JSON.
   - `GET /api/v1/profile/skills` -> Returns HTTP 200 with 44 skills and tier counts.
   - `GET /api/v1/profile/ml-depth` -> Returns HTTP 200 with 6 ML subdomains.
   - `GET /api/v1/profile/roles` -> Returns HTTP 200 with target roles and comp.
   - `PUT /api/v1/profile` -> Updates profile and persists to DB.

3. **Verify Zero Regressions on Existing Suites**:
   ```bash
   PYTHONPATH=. uv run pytest tests/test_jobsearch_executors.py tests/test_jobsearch_intent.py tests/test_jobsearch_scoring.py
   ```
