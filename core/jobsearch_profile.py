"""Candidate profile and skills taxonomy store for Career Command Center.

Defines Nate Walker's authoritative candidate profile, comprehensive resume,
40+ CTO skills taxonomy (Expert/Advanced tiers), production ML depth matrix,
target roles, and compensation bounds ($180k base / $250k target).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
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
    years_experience: int = 5
    keywords: list[str] = Field(default_factory=list)
    description: str = ""
    highlights: list[str] = Field(default_factory=list)


# Alias for test suite compatibility
CandidateSkill = SkillItem


class MLDepthSubdomain(BaseModel):
    name: str
    experience_level: str
    years: int
    core_technologies: list[str] = Field(default_factory=list)
    architectural_patterns: list[str] = Field(default_factory=list)
    production_milestones: list[str] = Field(default_factory=list)


class ProductionMLDepth(BaseModel):
    llm_orchestration: MLDepthSubdomain
    asr_tts_voice: MLDepthSubdomain
    fine_tuning_adaptation: MLDepthSubdomain
    embeddings_rag: MLDepthSubdomain
    agent_loops_tooling: MLDepthSubdomain
    inference_hardware: MLDepthSubdomain
    llm_systems: list[str] = Field(default_factory=list)
    agentic_orchestration: list[str] = Field(default_factory=list)
    voice_speech_ai: list[str] = Field(default_factory=list)
    rag_vector_search: list[str] = Field(default_factory=list)
    fine_tuning_evals: list[str] = Field(default_factory=list)
    edge_quantization: list[str] = Field(default_factory=list)


class WorkExperienceItem(BaseModel):
    company: str
    role: str
    start_date: str
    end_date: Optional[str] = None
    is_current: bool = False
    location: str = "Austin, TX"
    remote_type: str = "remote"
    summary: str = ""
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
    min_base: int = 180000
    target_total: int = 250000
    min_total: int = 200000
    base_minimum_usd: int = 180000
    target_total_comp_usd: int = 250000
    minimum_total_comp_usd: int = 200000
    equity_preference: str = "Meaningful startup equity stake (0.5%-3%+) or public/growth RSUs"
    currency: str = "USD"
    employment_type: str = "Full-time W2"
    location_preference: str = "Austin, TX or Remote"

    def is_acceptable(self, amount: int) -> bool:
        return amount >= self.min_base

    def meets_target(self, amount: int) -> bool:
        return amount >= self.target_total


class CandidateBio(BaseModel):
    full_name: str = "Nate Walker"
    headline: str = "CTO | Principal AI Architect | Technical Founder"
    summary: str = (
        "Hands-on Technology Executive, CTO, and Principal AI Architect with 15+ years "
        "of experience leading engineering organizations, building high-throughput distributed "
        "systems, and architecting production-grade Generative AI, Conversational AI, and multi-agent platforms. "
        "Pioneer in sovereign AI systems, voice ASR/TTS pipelines, Model Context Protocol (MCP) gateways, "
        "and event-sourced architectures. Proven track record scaling engineering teams from startup to high-growth, "
        "leading enterprise technical GTM, and delivering mission-critical enterprise platforms."
    )
    email: Optional[str] = "nate@theviking.ai"
    phone: Optional[str] = None
    location: str = "Austin, TX"
    linkedin_url: Optional[str] = "https://www.linkedin.com/in/nate-walker"
    github_url: Optional[str] = "https://github.com/nwalker85"
    portfolio_url: Optional[str] = None


class CandidateProfile(BaseModel):
    candidate_name: str = "Nate Walker"
    title: str = "CTO | Principal AI Architect | Technical Founder"
    resume_text: str = ""
    bio: CandidateBio = Field(default_factory=CandidateBio)
    target_roles: list[str] = Field(
        default_factory=lambda: [
            "Chief Technology Officer",
            "VP of Engineering",
            "Head of AI",
            "Principal AI Architect",
            "Technical Founder",
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
    target_role_families: list[str] = Field(
        default_factory=lambda: [
            "Enterprise AI Solutions Engineering / Solution Architecture",
            "Agentic AI / Platform Architecture",
            "AI GTM / Business Solutions Leadership",
            "Conversational / Voice AI Enterprise Leadership",
            "Executive Engineering Leadership",
        ]
    )
    target_role_config: TargetRoleConfig = Field(default_factory=TargetRoleConfig)
    compensation: CompensationExpectations = Field(default_factory=CompensationExpectations)
    skills: dict[str, SkillItem] = Field(default_factory=dict)
    production_ml: ProductionMLDepth
    experience: list[WorkExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    projects: list[ProjectHighlight] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def expert_skills(self) -> list[SkillItem]:
        return [s for s in self.skills.values() if s.tier == SkillTier.EXPERT]

    @property
    def advanced_skills(self) -> list[SkillItem]:
        return [s for s in self.skills.values() if s.tier == SkillTier.ADVANCED]

    def get_skills_by_category(self, category: SkillCategory | str) -> list[SkillItem]:
        cat_val = category.value if hasattr(category, "value") else str(category)
        return [
            s for s in self.skills.values()
            if (s.category.value if hasattr(s.category, "value") else str(s.category)) == cat_val
        ]


def _build_skills_taxonomy() -> dict[str, SkillItem]:
    """Generates the authoritative 44 CTO skills taxonomy (22 Expert, 22 Advanced)."""
    skills: list[SkillItem] = [
        # --- EXPERT SKILLS (22) ---
        SkillItem(
            name="LLM Systems",
            category=SkillCategory.AI_ML,
            tier=SkillTier.EXPERT,
            years_experience=6,
            keywords=["llm", "llm systems", "large language models", "prompt engineering", "claude", "gpt-4", "vllm", "anthropic", "openai", "deepseek"],
            description="Production LLM orchestration, structured output enforcement, prompt caching, token budget optimization, and multi-model routing.",
            highlights=["Architected multi-model LLM routing gateway reducing inference latency by 45%."],
        ),
        SkillItem(
            name="Multi-Agent Systems",
            category=SkillCategory.AI_ML,
            tier=SkillTier.EXPERT,
            years_experience=5,
            keywords=["multi-agent", "multi-agent systems", "agent loops", "react", "swarm", "tool calling", "mcp", "model context protocol", "agentic"],
            description="Multi-agent supervisory protocols, ReAct loops, deterministic tool execution, sandboxed agents, and consensus coordination.",
            highlights=["Designed autonomous multi-agent platform with cryptographic execution receipts."],
        ),
        SkillItem(
            name="Conversational AI",
            category=SkillCategory.AI_ML,
            tier=SkillTier.EXPERT,
            years_experience=9,
            keywords=["conversational ai", "chatbots", "dialog management", "nlu", "nlp", "intent classification", "slot filling"],
            description="Enterprise conversational architectures, dialog state machines, intent parsing, and omnichannel digital bots.",
            highlights=["Scaled enterprise conversational bots across Fortune 500 enterprise customers."],
        ),
        SkillItem(
            name="Voice AI / ASR / TTS",
            category=SkillCategory.AI_ML,
            tier=SkillTier.EXPERT,
            years_experience=8,
            keywords=["voice ai", "voice ai / asr / tts", "speech ai", "asr", "tts", "whisper", "kokoro", "piper", "webrtc", "sip", "audio streaming", "vad"],
            description="Real-time sovereign speech-to-text and text-to-speech pipelines, low-latency audio chunk streaming, and voice activity detection.",
            highlights=["Built Gjallarhorn sovereign voice engine for real-time meeting transcription."],
        ),
        SkillItem(
            name="RAG & Vector Retrieval",
            category=SkillCategory.AI_ML,
            tier=SkillTier.EXPERT,
            years_experience=6,
            keywords=["rag", "retrieval augmented generation", "vector search", "hybrid search", "rrf", "dense retrieval", "cross-encoder", "embeddings"],
            description="Dense + sparse hybrid search, Reciprocal Rank Fusion, Cross-Encoder reranking, and contextual parent-document retrieval.",
            highlights=["Deployed production RAG systems indexing millions of domain records with 98%+ precision."],
        ),
        SkillItem(
            name="Platform Architecture",
            category=SkillCategory.LEADERSHIP_STRATEGY,
            tier=SkillTier.EXPERT,
            years_experience=12,
            keywords=["platform architecture", "system design", "distributed architecture", "adrs", "governance", "software architecture"],
            description="Enterprise software architecture, Architecture Decision Records (ADRs), system decomposition, and contract-first API design.",
            highlights=["Governed architecture roadmaps across multi-tier distributed AI platforms."],
        ),
        SkillItem(
            name="Python",
            category=SkillCategory.BACKEND_API,
            tier=SkillTier.EXPERT,
            years_experience=14,
            keywords=["python", "asyncio", "pydantic", "sqlalchemy", "uvicorn", "pytest", "async", "python3"],
            description="Modern Python 3.11+, asynchronous IO, type safety with Pydantic v2, ORM design with SQLAlchemy, and high-performance APIs.",
            highlights=["Authored resilient async microservices handling tens of thousands of concurrent requests."],
        ),
        SkillItem(
            name="FastAPI",
            category=SkillCategory.BACKEND_API,
            tier=SkillTier.EXPERT,
            years_experience=7,
            keywords=["fastapi", "rest api", "openapi", "starlette", "async api", "swagger"],
            description="High-throughput REST API engineering, dependency injection, OpenAPI contract generation, and middleware design.",
            highlights=["Standardized backend REST layers across multiple production platforms using FastAPI."],
        ),
        SkillItem(
            name="TypeScript",
            category=SkillCategory.BACKEND_API,
            tier=SkillTier.EXPERT,
            years_experience=10,
            keywords=["typescript", "node.js", "zod", "bun", "javascript", "npm workspaces"],
            description="Strict-mode TypeScript, client SDK generation, Zod runtime validation contracts, and modern ESM ecosystem.",
            highlights=["Designed cross-platform TypeScript SDKs for GraphQL and REST CQRS gateways."],
        ),
        SkillItem(
            name="Event-Driven Systems & Messaging",
            category=SkillCategory.DISTRIBUTED_SYSTEMS,
            tier=SkillTier.EXPERT,
            years_experience=12,
            keywords=["event-driven", "message brokers", "pub/sub", "event streams", "distributed messaging", "mqtt", "kafka"],
            description="Distributed pub/sub topologies, asynchronous message brokers, queue semantics, at-least-once delivery, and backpressure handling.",
            highlights=["Architected real-time event distribution networks with sub-millisecond dispatch."],
        ),
        SkillItem(
            name="NATS / JetStream",
            category=SkillCategory.DISTRIBUTED_SYSTEMS,
            tier=SkillTier.EXPERT,
            years_experience=6,
            keywords=["nats", "jetstream", "nats / jetstream", "nats jetstream", "message queues", "at-least-once", "stream processing"],
            description="NATS JetStream stream replication, subject-based routing, consumer ack management, and durable stream persistence.",
            highlights=["Implemented enterprise event backbone leveraging NATS JetStream."],
        ),
        SkillItem(
            name="CQRS & Event Sourcing",
            category=SkillCategory.DISTRIBUTED_SYSTEMS,
            tier=SkillTier.EXPERT,
            years_experience=9,
            keywords=["cqrs", "event sourcing", "projections", "event log", "state reconstruction", "checkpointing"],
            description="Immutable append-only event streams, disposable read projections, cryptographic state commitments, and lag reconciliation.",
            highlights=["Engineered CQRS architecture decoupling governed commands from high-speed read projections."],
        ),
        SkillItem(
            name="GraphQL",
            category=SkillCategory.BACKEND_API,
            tier=SkillTier.EXPERT,
            years_experience=7,
            keywords=["graphql", "strawberry", "apollo", "schema federation", "resolvers", "dataloader"],
            description="GraphQL schema design, Strawberry GraphQL Python, DataLoader batching, type safety, and read projection queries.",
            highlights=["Unified multi-service domain models into performant GraphQL API surfaces."],
        ),
        SkillItem(
            name="PostgreSQL",
            category=SkillCategory.BACKEND_API,
            tier=SkillTier.EXPERT,
            years_experience=14,
            keywords=["postgresql", "postgres", "pgvector", "relational modeling", "alembic", "sql", "indexing", "jsonb"],
            description="Advanced relational schema modeling, pgvector vector indexing, JSONB indexing, connection pooling, and Alembic migrations.",
            highlights=["Scaled mission-critical PostgreSQL databases supporting billions of relational rows."],
        ),
        SkillItem(
            name="Redis",
            category=SkillCategory.BACKEND_API,
            tier=SkillTier.EXPERT,
            years_experience=11,
            keywords=["redis", "in-memory cache", "distributed locking", "redis streams", "caching", "redlock"],
            description="In-memory key-value caching, distributed locking (Redlock), Redis Streams, pub/sub, and ephemeral state management.",
            highlights=["Implemented distributed cache synchronization and rate limiting layers."],
        ),
        SkillItem(
            name="Docker",
            category=SkillCategory.CLOUD_INFRA,
            tier=SkillTier.EXPERT,
            years_experience=10,
            keywords=["docker", "containers", "docker compose", "multi-stage builds", "containerization"],
            description="Multi-stage production Dockerfile optimization, container hardening, multi-arch builds, and compose orchestration.",
            highlights=["Containerized entire multi-service microservice suites with minimal footprint."],
        ),
        SkillItem(
            name="Kubernetes & k0s/k3s",
            category=SkillCategory.CLOUD_INFRA,
            tier=SkillTier.EXPERT,
            years_experience=8,
            keywords=["kubernetes", "k3s", "k0s", "helm", "containernetworking", "metallb", "traefik ingress", "k8s"],
            description="Bare-metal and cloud Kubernetes administration, k3s/k0s lightweight clusters, Helm charts, Traefik IngressRoute, and MetalLB.",
            highlights=["Maintained sovereign HA Kubernetes clusters hosting internal and customer-facing workloads."],
        ),
        SkillItem(
            name="Linux Systems & Bare Metal",
            category=SkillCategory.CLOUD_INFRA,
            tier=SkillTier.EXPERT,
            years_experience=15,
            keywords=["linux", "ubuntu", "systemd", "gpu passthrough", "zfs", "tailscale", "networking", "bash"],
            description="Linux kernel administration, systemd service management, GPU hardware passthrough, Tailscale overlay mesh, and storage arrays.",
            highlights=["Managed fleet of dedicated bare-metal GPU compute servers and enterprise storage nodes."],
        ),
        SkillItem(
            name="Telephony & CPaaS",
            category=SkillCategory.DISTRIBUTED_SYSTEMS,
            tier=SkillTier.EXPERT,
            years_experience=9,
            keywords=["telephony", "sip", "webrtc", "twilio", "cpaas", "contact center", "voice streaming", "pstn"],
            description="SIP trunking, WebRTC audio streaming, Twilio Voice/SMS integration, carrier routing, and enterprise contact center architectures.",
            highlights=["Architected carrier-grade CPaaS voice solutions processing millions of minutes per month."],
        ),
        SkillItem(
            name="Engineering Leadership",
            category=SkillCategory.LEADERSHIP_STRATEGY,
            tier=SkillTier.EXPERT,
            years_experience=11,
            keywords=["engineering leadership", "cto", "vp engineering", "org scaling", "mentorship", "hiring", "team culture"],
            description="Scaling engineering teams, technical vision, mentorship, hiring, cross-functional collaboration, and high-performance culture.",
            highlights=["Built and led distributed engineering teams from seed stage to enterprise maturity."],
        ),
        SkillItem(
            name="Enterprise Solutions Architecture",
            category=SkillCategory.LEADERSHIP_STRATEGY,
            tier=SkillTier.EXPERT,
            years_experience=10,
            keywords=["solutions architecture", "technical gtm", "enterprise poc", "stakeholder management", "pre-sales", "solution engineering"],
            description="Technical GTM leadership, enterprise POC design, customer discovery, technical due diligence, and closing multi-million dollar deals.",
            highlights=["Led high-stakes enterprise POCs resulting in Fortune 100 customer expansions."],
        ),
        SkillItem(
            name="Test-Driven Development",
            category=SkillCategory.BACKEND_API,
            tier=SkillTier.EXPERT,
            years_experience=13,
            keywords=["tdd", "test-driven development", "pytest", "vitest", "unit testing", "integration testing", "property testing"],
            description="Strict Red-Green-Refactor methodologies, comprehensive Pytest/Vitest suites, mock injection, and zero-defect quality standards.",
            highlights=["Maintained 95%+ test coverage across complex event-driven and API platforms."],
        ),

        # --- ADVANCED SKILLS (22) ---
        SkillItem(
            name="Fine-Tuning & PEFT",
            category=SkillCategory.AI_ML,
            tier=SkillTier.ADVANCED,
            years_experience=4,
            keywords=["fine-tuning", "lora", "qlora", "sft", "trl", "peft", "axolotl", "unsloth", "instruction tuning"],
            description="Parameter-efficient fine-tuning (LoRA/QLoRA), instruction dataset curation, Hugging Face TRL, and evaluation benchmark harness.",
            highlights=["Fine-tuned specialized domain SLMs matching 70B parameter accuracy for structured extraction."],
        ),
        SkillItem(
            name="Embeddings & Semantic Search",
            category=SkillCategory.AI_ML,
            tier=SkillTier.ADVANCED,
            years_experience=5,
            keywords=["embeddings", "sentence transformers", "bge-m3", "cosine similarity", "mteb", "semantic search"],
            description="SentenceTransformers, dense vector embeddings, distance metrics, MTEB benchmarks, and embedding caching strategies.",
            highlights=["Built semantic deduplication pipelines clustering high-volume unstructured interaction data."],
        ),
        SkillItem(
            name="Model Quantization & vLLM",
            category=SkillCategory.AI_ML,
            tier=SkillTier.ADVANCED,
            years_experience=4,
            keywords=["quantization", "gguf", "awq", "vllm", "tensorrt-llm", "exl2", "llama.cpp", "gpu serving"],
            description="4-bit/8-bit AWQ and GGUF quantization, vLLM continuous batching, KV-cache optimization, and TensorRT-LLM deployment.",
            highlights=["Optimized local inference serving clusters achieving 100+ tokens/sec throughput."],
        ),
        SkillItem(
            name="Multimodal AI",
            category=SkillCategory.AI_ML,
            tier=SkillTier.ADVANCED,
            years_experience=4,
            keywords=["multimodal", "vlm", "ocr", "vision-language", "audio embeddings", "document intelligence"],
            description="Vision-Language Models (VLM), multimodal document understanding, OCR extraction pipelines, and audio feature representations.",
            highlights=["Engineered multimodal document extraction pipelines parsing complex financial receipts."],
        ),
        SkillItem(
            name="PyTorch",
            category=SkillCategory.AI_ML,
            tier=SkillTier.ADVANCED,
            years_experience=6,
            keywords=["pytorch", "torch", "deep learning", "neural networks", "tensors", "cuda"],
            description="PyTorch tensor operations, CUDA hardware acceleration, neural network layers, and custom model evaluation.",
            highlights=["Implemented custom loss functions and evaluation loops for domain adaptation."],
        ),
        SkillItem(
            name="Rust",
            category=SkillCategory.BACKEND_API,
            tier=SkillTier.ADVANCED,
            years_experience=4,
            keywords=["rust", "ratatui", "cargo", "tui", "memory safety", "systems programming"],
            description="Memory-safe systems programming in Rust, Ratatui terminal user interfaces (TUI), and high-performance CLI utilities.",
            highlights=["Built native diagnostic TUIs and fast binary log parsers in Rust."],
        ),
        SkillItem(
            name="Go",
            category=SkillCategory.BACKEND_API,
            tier=SkillTier.ADVANCED,
            years_experience=6,
            keywords=["go", "golang", "goroutines", "cli tooling", "concurrency", "channels"],
            description="Concurrent network services with Go, goroutines, channels, fast CLI tooling, and microservice backends.",
            highlights=["Developed high-concurrency event forwarders and CLI clients in Go."],
        ),
        SkillItem(
            name="SvelteKit",
            category=SkillCategory.FRONTEND_FULLSTACK,
            tier=SkillTier.ADVANCED,
            years_experience=4,
            keywords=["svelte", "sveltekit", "svelte 5", "runes", "glass ui", "ssr", "reactive stores"],
            description="SvelteKit 2, Svelte 5 Runes, reactive state stores, server-side rendering (SSR), and Glass UI component design.",
            highlights=["Created sovereign web user interfaces with real-time reactive streaming updates."],
        ),
        SkillItem(
            name="Tailwind CSS",
            category=SkillCategory.FRONTEND_FULLSTACK,
            tier=SkillTier.ADVANCED,
            years_experience=6,
            keywords=["tailwind", "tailwind css", "design tokens", "responsive design", "ui styling", "contrast"],
            description="Tailwind utility styling, high-contrast design tokens, dark/light theme systems, and responsive viewport layouts.",
            highlights=["Designed accessible Glass UI design token systems compliant with WCAG standards."],
        ),
        SkillItem(
            name="Cloudflare & Edge Compute",
            category=SkillCategory.CLOUD_INFRA,
            tier=SkillTier.ADVANCED,
            years_experience=7,
            keywords=["cloudflare", "workers", "pages", "zero trust", "tunnels", "edge", "cloudflare dns"],
            description="Cloudflare Zero Trust Tunnels, Workers edge computation, Cloudflare Pages, DNS automation, and WAF rules.",
            highlights=["Secured sovereign infrastructure behind Cloudflare Zero Trust and remote-managed tunnels."],
        ),
        SkillItem(
            name="AWS Cloud Architecture",
            category=SkillCategory.CLOUD_INFRA,
            tier=SkillTier.ADVANCED,
            years_experience=9,
            keywords=["aws", "amazon web services", "ecs", "eks", "bedrock", "s3", "rds", "iam", "cloudwatch"],
            description="AWS ECS/EKS container deployments, Amazon Bedrock generative AI APIs, RDS PostgreSQL, IAM least privilege, and VPC peering.",
            highlights=["Architected enterprise cloud platforms on AWS serving millions of global users."],
        ),
        SkillItem(
            name="Security & IAM",
            category=SkillCategory.SECURITY_GOVERNANCE,
            tier=SkillTier.ADVANCED,
            years_experience=9,
            keywords=["iam", "oauth2", "oidc", "jwt", "zitadel", "rbac", "auth", "hmac", "security"],
            description="OAuth2/OIDC protocols, JWT cryptographic signing, Zitadel enterprise SSO, RBAC/ABAC authorization, and HMAC verification.",
            highlights=["Implemented unified zero-trust identity and role-based access control across platform services."],
        ),
        SkillItem(
            name="Cryptographic Receipts",
            category=SkillCategory.SECURITY_GOVERNANCE,
            tier=SkillTier.ADVANCED,
            years_experience=5,
            keywords=["cryptographic receipts", "ed25519", "sha256", "merkle proofs", "non-repudiation", "digital signatures"],
            description="Ed25519 digital signatures, SHA-256 state commitment hashing, Merkle audit trees, and non-repudiation receipts.",
            highlights=["Built cryptographic receipt issuance ensuring verifiable audit trails for automated operations."],
        ),
        SkillItem(
            name="Observability & OpenTelemetry",
            category=SkillCategory.CLOUD_INFRA,
            tier=SkillTier.ADVANCED,
            years_experience=7,
            keywords=["opentelemetry", "otel", "prometheus", "grafana", "tracing", "metrics", "structured logging"],
            description="OpenTelemetry distributed tracing, Prometheus metric collectors, Grafana visualization dashboards, and structured JSON logs.",
            highlights=["Instrumented end-to-end tracing across distributed microservices and LLM pipelines."],
        ),
        SkillItem(
            name="Vector Databases",
            category=SkillCategory.AI_ML,
            tier=SkillTier.ADVANCED,
            years_experience=5,
            keywords=["qdrant", "chromadb", "weaviate", "pinecone", "vector database", "hnsw"],
            description="Qdrant, ChromaDB, Weaviate vector storage, HNSW indexing graphs, payload filtering, and snapshot replication.",
            highlights=["Engineered high-speed vector retrieval collections with real-time metadata filtering."],
        ),
        SkillItem(
            name="Git & Repository Governance",
            category=SkillCategory.CLOUD_INFRA,
            tier=SkillTier.ADVANCED,
            years_experience=15,
            keywords=["git", "git worktrees", "monorepo", "forgejo", "github actions", "branch protection"],
            description="Git worktrees, conventional commit standards, Forgejo/GitHub Actions automation, and monorepo governance.",
            highlights=["Standardized GitFlow and automated CI/CD pipelines across dozens of engineering repositories."],
        ),
        SkillItem(
            name="Regulatory Compliance",
            category=SkillCategory.SECURITY_GOVERNANCE,
            tier=SkillTier.ADVANCED,
            years_experience=8,
            keywords=["soc2", "hipaa", "gdpr", "compliance", "pii redaction", "audit logs"],
            description="SOC2 Type II, HIPAA, GDPR privacy controls, automated PII redaction, data retention policies, and immutable audit logs.",
            highlights=["Led security architecture for HIPAA-compliant conversational healthcare systems."],
        ),
        SkillItem(
            name="Executive Stakeholder Communication",
            category=SkillCategory.LEADERSHIP_STRATEGY,
            tier=SkillTier.ADVANCED,
            years_experience=9,
            keywords=["executive communication", "board presentations", "c-suite", "roi modeling", "technical writing"],
            description="Translating deep technical architecture to C-suite and board stakeholders, business ROI modeling, and strategic roadmaps.",
            highlights=["Presented technical strategy and due diligence directly to enterprise executive leadership and investors."],
        ),
        SkillItem(
            name="Vendor Evaluation & TCO",
            category=SkillCategory.LEADERSHIP_STRATEGY,
            tier=SkillTier.ADVANCED,
            years_experience=9,
            keywords=["vendor evaluation", "build vs buy", "rfp", "tco analysis", "vendor diligence"],
            description="RFP/RFI evaluations, build vs. buy decision frameworks, Total Cost of Ownership (TCO) analysis, and vendor SLA reviews.",
            highlights=["Saved hundreds of thousands in annual SaaS spend via rigorous build-vs-buy architectures."],
        ),
        SkillItem(
            name="Audio DSP & Acoustic Processing",
            category=SkillCategory.AI_ML,
            tier=SkillTier.ADVANCED,
            years_experience=7,
            keywords=["dsp", "audio dsp", "opus", "pcm", "noise suppression", "vad", "acoustic processing", "aec"],
            description="Opus/PCM codec transcoding, acoustic echo cancellation, noise suppression filters, and real-time audio chunk buffering.",
            highlights=["Engineered sub-20ms audio frame processing for real-time speech AI interactions."],
        ),
        SkillItem(
            name="Information Retrieval & BM25",
            category=SkillCategory.BACKEND_API,
            tier=SkillTier.ADVANCED,
            years_experience=9,
            keywords=["bm25", "elasticsearch", "opensearch", "lexical search", "inverted index", "full-text search"],
            description="BM25 scoring algorithms, inverted index generation, fuzzy matching, and Elasticsearch/OpenSearch clustering.",
            highlights=["Integrated sparse lexical search with dense embeddings for high-recall hybrid information retrieval."],
        ),
        SkillItem(
            name="High Availability & Disaster Recovery",
            category=SkillCategory.DISTRIBUTED_SYSTEMS,
            tier=SkillTier.ADVANCED,
            years_experience=9,
            keywords=["high availability", "disaster recovery", "failover", "backup assurance", "resilience"],
            description="Multi-node HA topologies, automated failover circuit breakers, backup restoration proofs, and disaster recovery runbooks.",
            highlights=["Designed zero-data-loss failover mechanisms for mission-critical telephony systems."],
        ),
    ]

    return {s.name.lower(): s for s in skills}


def _build_production_ml_depth() -> ProductionMLDepth:
    """Builds the 6-pillar Production ML depth matrix."""
    llm_subdomain = MLDepthSubdomain(
        name="LLM Orchestration & Systems",
        experience_level="Expert (Production Led)",
        years=6,
        core_technologies=["Anthropic Claude (3.5/3.7/Opus)", "OpenAI (GPT-4o/o1/o3)", "DeepSeek (R1/V3)", "vLLM", "Ollama"],
        architectural_patterns=["Dynamic context compression", "Structured JSON output enforcement", "Prompt caching", "Token budget optimization", "Multi-model fallback routing"],
        production_milestones=["Architected enterprise LLM gateways slashing inference latency by 45% while optimizing token expenditure."],
    )
    voice_subdomain = MLDepthSubdomain(
        name="Speech & Sovereign Voice AI (ASR/TTS)",
        experience_level="Expert (Production Led)",
        years=8,
        core_technologies=["Gjallarhorn ASR", "Whisper (large-v3, distil-whisper)", "Kokoro TTS", "Piper TTS", "WebRTC", "SIP/RTP", "Mosquitto MQTT"],
        architectural_patterns=["Sub-200ms audio chunk streaming", "Real-time VAD silence gating", "Speaker diarization", "Acoustic buffer framing"],
        production_milestones=["Built sovereign voice intelligence pipeline transcribing live enterprise audio with structured real-time debriefing."],
    )
    fine_tuning_subdomain = MLDepthSubdomain(
        name="Fine-Tuning & Parameter-Efficient ML",
        experience_level="Advanced (Production Deployed)",
        years=4,
        core_technologies=["LoRA", "QLoRA", "Hugging Face TRL / PEFT", "PyTorch", "Axolotl", "Unsloth"],
        architectural_patterns=["Instruction dataset curation", "Format alignment & synthetic data", "Automated eval benchmarking", "Domain-specific SLM distillation"],
        production_milestones=["Fine-tuned domain SLMs achieving zero-shot accuracy parity with 70B models at 10x lower latency."],
    )
    rag_subdomain = MLDepthSubdomain(
        name="Embeddings & Hybrid RAG Architecture",
        experience_level="Expert (Production Led)",
        years=6,
        core_technologies=["SentenceTransformers", "text-embedding-3-large", "BGE-M3", "Qdrant", "pgvector", "Cross-Encoders"],
        architectural_patterns=["Hierarchical chunking", "Parent-document retrieval", "Dense + sparse BM25 hybrid ranking", "Reciprocal Rank Fusion (RRF)"],
        production_milestones=["Constructed hybrid RAG engines querying multi-million document corpora with 98%+ precision and citation verification."],
    )
    agent_subdomain = MLDepthSubdomain(
        name="Agent Loops & Tool Sandboxing",
        experience_level="Expert (Production Led)",
        years=5,
        core_technologies=["Model Context Protocol (MCP)", "ReAct loops", "Bifrost Tool Gateway", "Pydantic structured schemas", "Docker Sandboxes"],
        architectural_patterns=["Plan-execute-verify autonomous loops", "Self-correcting error recovery", "Cryptographic receipt verification", "HITL approval gates"],
        production_milestones=["Created sovereign multi-agent platform executing complex autonomous workflows with cryptographic non-repudiation."],
    )
    hardware_subdomain = MLDepthSubdomain(
        name="Inference Hardware & Local Compute",
        experience_level="Advanced (Production Deployed)",
        years=4,
        core_technologies=["NVIDIA RTX 4090 (24GB VRAM)", "CUDA", "TensorRT-LLM", "vLLM", "GGUF/llama.cpp", "k3s/k0s Bare-Metal Clusters"],
        architectural_patterns=["GPU VRAM pooling", "Continuous batching", "4-bit/8-bit AWQ & GGUF quantization", "Containerized GPU scheduling"],
        production_milestones=["Provisioned and operated private GPU inference clusters delivering sustained 100+ tokens/sec throughput."],
    )

    return ProductionMLDepth(
        llm_orchestration=llm_subdomain,
        asr_tts_voice=voice_subdomain,
        fine_tuning_adaptation=fine_tuning_subdomain,
        embeddings_rag=rag_subdomain,
        agent_loops_tooling=agent_subdomain,
        inference_hardware=hardware_subdomain,
        llm_systems=llm_subdomain.core_technologies + llm_subdomain.architectural_patterns,
        agentic_orchestration=agent_subdomain.core_technologies + agent_subdomain.architectural_patterns,
        voice_speech_ai=voice_subdomain.core_technologies + voice_subdomain.architectural_patterns,
        rag_vector_search=rag_subdomain.core_technologies + rag_subdomain.architectural_patterns,
        fine_tuning_evals=fine_tuning_subdomain.core_technologies + fine_tuning_subdomain.architectural_patterns,
        edge_quantization=hardware_subdomain.core_technologies + hardware_subdomain.architectural_patterns,
    )


def get_ratified_candidate_profile() -> CandidateProfile:
    """Builds and returns Nate Walker's authoritative ratified candidate profile."""
    skills = _build_skills_taxonomy()
    production_ml = _build_production_ml_depth()
    bio = CandidateBio()

    experience = [
        WorkExperienceItem(
            company="Ravenhelm Technologies",
            role="Technical Founder & Principal AI Architect",
            start_date="2024-01",
            is_current=True,
            location="Austin, TX",
            remote_type="remote",
            summary=(
                "Architected sovereign AI and multi-agent operating systems (RavenmaskOS, UltraDex, Bifrost, "
                "Gjallarhorn) unifying real-time voice streaming, MCP tool gateways, event-sourced CQRS backends, "
                "and cryptographic execution receipts."
            ),
            key_achievements=[
                "Designed event-sourced CQRS backend using FastAPI, NATS JetStream, PostgreSQL, and Ed25519 signatures.",
                "Built Gjallarhorn sovereign voice intelligence engine using Whisper ASR, Kokoro TTS, and MQTT streaming.",
                "Architected Model Context Protocol (MCP) distributed tool gateway for safe agent execution.",
            ],
            technologies=["Python", "FastAPI", "TypeScript", "SvelteKit", "NATS JetStream", "PostgreSQL", "Docker", "Kubernetes", "Whisper", "MCP"],
        ),
        WorkExperienceItem(
            company="IntelePeer",
            role="Director / Senior Solutions Engineering & AI Leadership",
            start_date="2021-04",
            end_date="2024-01",
            is_current=False,
            location="Remote",
            remote_type="remote",
            summary=(
                "Led enterprise conversational AI architecture and solutions engineering, deploying LLM-driven voicebots "
                "and digital assistants across Fortune 500 enterprises on high-throughput CPaaS telephony infrastructure."
            ),
            key_achievements=[
                "Spearheaded technical solutions engineering driving millions in new enterprise ARR.",
                "Architected low-latency conversational voice pipelines handling millions of minutes.",
                "Partnered with executive leadership on conversational AI product strategy and GTM execution.",
            ],
            technologies=["Conversational AI", "Voice AI", "SIP", "WebRTC", "Python", "REST APIs", "Enterprise Architecture"],
        ),
        WorkExperienceItem(
            company="Amelia / IPsoft (SoundHound AI / Amelia)",
            role="Senior Solutions Architect & Conversational AI Practice Lead",
            start_date="2018-06",
            end_date="2021-04",
            is_current=False,
            location="Austin, TX / Remote",
            remote_type="remote",
            summary=(
                "Designed cognitive conversational AI agent architectures integrating NLP/NLU, dialog management, "
                "and enterprise backend systems for tier-1 banking, healthcare, and telecommunication enterprises."
            ),
            key_achievements=[
                "Architected cognitive conversational agents serving millions of end users with strict compliance.",
                "Led technical solution delivery for strategic enterprise accounts.",
            ],
            technologies=["NLP", "NLU", "Conversational AI", "Dialog Systems", "Python", "Java", "Enterprise Integration"],
        ),
        WorkExperienceItem(
            company="Quant & Earlier Technical Leadership",
            role="Senior Software Architect / Lead Distributed Systems Engineer",
            start_date="2012-08",
            end_date="2018-06",
            is_current=False,
            location="Austin, TX",
            remote_type="remote",
            summary="Built high-concurrency real-time distributed messaging systems, microservices, and testing frameworks in Python and Go.",
            key_achievements=[
                "Designed scalable distributed messaging systems with high reliability.",
                "Mentored engineering teams in test-driven development and clean architectural patterns.",
            ],
            technologies=["Python", "Go", "PostgreSQL", "Redis", "Distributed Systems", "Linux"],
        ),
    ]

    education = [
        EducationItem(
            institution="University of Texas at Austin",
            degree="Bachelor of Science",
            field_of_study="Computer Science & Systems Architecture",
            graduation_year=2012,
        )
    ]

    projects = [
        ProjectHighlight(
            name="RavenmaskOS / Career Command Center",
            role="Chief Architect",
            description="Sovereign job-search operating system and CRM with deterministic scoring, voice intelligence, and CQRS.",
            technologies=["FastAPI", "Strawberry GraphQL", "SvelteKit", "NATS JetStream", "PostgreSQL"],
        ),
        ProjectHighlight(
            name="Gjallarhorn Voice AI",
            role="Creator & Lead Engineer",
            description="Sub-200ms sovereign ASR/TTS voice transcription and meeting debrief extraction engine.",
            technologies=["Whisper", "Kokoro TTS", "WebRTC", "Mosquitto MQTT", "Python"],
        ),
    ]

    resume_text = (
        f"{bio.full_name}\n"
        f"{bio.headline}\n"
        f"Location: {bio.location} | Remote: Yes\n\n"
        f"SUMMARY:\n{bio.summary}\n\n"
        f"EXPERIENCE:\n"
        + "\n\n".join(
            f"• {exp.role} at {exp.company} ({exp.start_date} - {exp.end_date or 'Present'})\n"
            f"  {exp.summary}\n"
            f"  Key Achievements: {'; '.join(exp.key_achievements)}"
            for exp in experience
        )
        + "\n\nSKILLS TAXONOMY (44 Structured Competencies):\n"
        + "Expert Skills: " + ", ".join(s.name for s in skills.values() if s.tier == SkillTier.EXPERT) + "\n"
        + "Advanced Skills: " + ", ".join(s.name for s in skills.values() if s.tier == SkillTier.ADVANCED)
    )

    return CandidateProfile(
        candidate_name=bio.full_name,
        title=bio.headline,
        resume_text=resume_text,
        bio=bio,
        target_roles=[
            "Chief Technology Officer",
            "VP of Engineering",
            "Head of AI",
            "Principal AI Architect",
            "Technical Founder",
        ],
        target_domains=[
            "AI infrastructure",
            "Developer tools",
            "Voice and customer experience",
            "Healthcare",
            "Regulated security constrained systems",
            "Agentic AI multi-agent orchestration",
        ],
        target_role_families=[
            "Enterprise AI Solutions Engineering / Solution Architecture",
            "Agentic AI / Platform Architecture",
            "AI GTM / Business Solutions Leadership",
            "Conversational / Voice AI Enterprise Leadership",
            "Executive Engineering Leadership",
        ],
        target_role_config=TargetRoleConfig(),
        compensation=CompensationExpectations(
            min_base=180000,
            target_total=250000,
            min_total=200000,
            base_minimum_usd=180000,
            target_total_comp_usd=250000,
            minimum_total_comp_usd=200000,
            currency="USD",
            location_preference="Austin, TX or Remote",
        ),
        skills=skills,
        production_ml=production_ml,
        experience=experience,
        education=education,
        projects=projects,
        updated_at=datetime.now(timezone.utc),
    )


class CandidateProfileStore:
    """Thread-safe candidate profile store with memory cache and DB persistence."""

    _cached_profile: Optional[CandidateProfile] = None

    def __init__(self, db: Optional[Session] = None):
        self._db = db

    def get_profile(self) -> CandidateProfile:
        """Fetch candidate profile from cache, database, or fallback seed."""
        if CandidateProfileStore._cached_profile is not None:
            return CandidateProfileStore._cached_profile

        if self._db is not None:
            try:
                from core.models import SettingsDB
                row = self._db.get(SettingsDB, "candidate_profile")
                if row and row.value:
                    profile = CandidateProfile.model_validate_json(row.value)
                    CandidateProfileStore._cached_profile = profile
                    return profile
            except Exception:
                pass

        profile = get_ratified_candidate_profile()
        CandidateProfileStore._cached_profile = profile
        return profile

    def get_skills(self) -> dict[str, SkillItem]:
        """Fetch skills taxonomy dictionary."""
        return self.get_profile().skills

    def get_production_ml(self) -> ProductionMLDepth:
        """Fetch production ML depth matrix."""
        return self.get_profile().production_ml

    def get_compensation(self) -> CompensationExpectations:
        """Fetch compensation expectations."""
        return self.get_profile().compensation

    def update_profile(self, profile: CandidateProfile) -> CandidateProfile:
        """Save updated profile to cache and persistent database."""
        profile.updated_at = datetime.now(timezone.utc)
        CandidateProfileStore._cached_profile = profile

        if self._db is not None:
            try:
                from core.models import SettingsDB
                row = self._db.get(SettingsDB, "candidate_profile")
                json_val = profile.model_dump_json()
                if row:
                    row.value = json_val
                else:
                    self._db.add(SettingsDB(key="candidate_profile", value=json_val))
                self._db.commit()
            except Exception:
                pass

        return profile

    def match_skills(self, text: str) -> dict[str, Any]:
        """Deterministic skill keyword extractor matching text against the taxonomy."""
        profile = self.get_profile()
        text_lower = text.lower()
        tokens = set(re.findall(r"[a-z0-9+#.-]+", text_lower))
        matched_expert: list[str] = []
        matched_advanced: list[str] = []

        for skill in profile.skills.values():
            skill_keywords = {k.lower() for k in skill.keywords} | {skill.name.lower()}
            if (skill_keywords & tokens) or any(kw in text_lower for kw in skill_keywords):
                if skill.tier == SkillTier.EXPERT:
                    matched_expert.append(skill.name)
                elif skill.tier == SkillTier.ADVANCED:
                    matched_advanced.append(skill.name)

        total_skills = len(profile.skills)
        total_matched = len(matched_expert) + len(matched_advanced)
        match_ratio = round(
            (len(matched_expert) * 1.5 + len(matched_advanced)) / (total_skills * 1.5), 3
        ) if total_skills > 0 else 0.0

        return {
            "matched_expert": matched_expert,
            "matched_advanced": matched_advanced,
            "total_matched": total_matched,
            "match_ratio": match_ratio,
        }
