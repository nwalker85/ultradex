export const syntheticHealthResponse = {
  status: "ok",
  timestamp: "2026-07-29T12:00:00",
} as const;

export const syntheticReadinessResponse = {
  ready: true,
  timestamp: "2026-07-29T12:00:01",
} as const;

export const syntheticProjectionFreshness = {
  sourceEventId: "event-synthetic-001",
  sourceEventPosition: "SYNTHETIC:1",
  projectedAt: "2026-07-29T12:00:02+00:00",
  lagMs: 12,
  status: "fresh",
} as const;

export const syntheticContractHandleResponse = {
  contract_id: "contract-synthetic-001",
  operation_id: "operation-synthetic-001",
  status: "accepted",
  submitted_at: "2026-07-29T12:00:03+00:00",
  correlation_id: "correlation-synthetic-001",
  refusal_code: null,
  refusal_reason: null,
  expires_at: "2026-07-29T12:15:03+00:00",
  status_url: "/operations/operation-synthetic-001",
  events_url: "/operations/operation-synthetic-001/events",
} as const;

export const syntheticRefusedContractHandleResponse = {
  contract_id: "contract-synthetic-refused-001",
  operation_id: "operation-synthetic-refused-001",
  status: "refused",
  submitted_at: "2026-07-29T12:00:05+00:00",
  correlation_id: "correlation-synthetic-refused-001",
  refusal_code: "synthetic_policy_denied",
  refusal_reason: "Synthetic policy did not authorize this operation",
  expires_at: null,
  status_url: "/operations/operation-synthetic-refused-001",
  events_url: "/operations/operation-synthetic-refused-001/events",
} as const;

export const syntheticOperation = {
  id: "operation-synthetic-001",
  correlationId: "correlation-synthetic-001",
  command: "synthetic.inspect",
  status: "running",
  createdAt: "2026-07-29T12:00:03+00:00",
  startedAt: "2026-07-29T12:00:04+00:00",
  completedAt: null,
  result: null,
  error: null,
  freshness: syntheticProjectionFreshness,
} as const;

export const syntheticLifecycleEvent = {
  id: 101,
  operationId: "operation-synthetic-001",
  eventType: "synthetic.operation.accepted",
  timestamp: "2026-07-29T12:00:04+00:00",
  payload: {
    classification: "synthetic",
    lifecycleState: "accepted",
  },
} as const;

export const syntheticGraphQLData = {
  operation: {
    id: "operation-synthetic-001",
  },
} as const;

export const syntheticGraphQLErrors = {
  data: null,
  errors: [
    {
      message: "Synthetic operation is unavailable",
      path: ["operation"],
      extensions: {
        code: "SYNTHETIC_UNAVAILABLE",
      },
    },
  ],
} as const;

export const syntheticOpportunityPage = {
  items: [
    {
      opportunityId: "opportunity-synthetic-001",
      employer: "Synthetic Systems",
      title: "Platform Engineer",
      location: "Remote",
      roleFamily: "Engineering",
      status: "qualified",
      fitScore: 91,
      fitExplanation: "Strong synthetic platform fit.",
      riskFlags: ["compensation-unverified"],
      evidenceRefs: [
        {
          evidenceId: "evidence-synthetic-001",
          sourceKind: "manual",
          sourceRef: "source-synthetic-001",
          classification: "private",
          observedAt: "2026-07-29T12:00:00+00:00",
          commitment:
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          redactedSummary: "Synthetic public role metadata reviewed.",
        },
      ],
      freshness: syntheticProjectionFreshness,
      createdAt: "2026-07-29T11:59:00+00:00",
      updatedAt: "2026-07-29T12:00:02+00:00",
    },
  ],
  freshness: {
    sourceEventId: "event-checkpoint-opportunities",
    sourceEventPosition: "SYNTHETIC:2",
    projectedAt: "2026-07-29T12:00:03+00:00",
    lagMs: 13,
    status: "stale",
  },
  nextCursor: "opportunity-synthetic-001",
} as const;

export const syntheticApplicationPage = {
  items: [
    {
      applicationId: "application-synthetic-001",
      opportunityId: "opportunity-synthetic-001",
      status: "applied",
      stageHistory: [
        {
          status: "draft",
          occurredAt: "2026-07-29T11:00:00+00:00",
          evidenceRef: "evidence-synthetic-001",
        },
        {
          status: "applied",
          occurredAt: "2026-07-29T12:00:00+00:00",
          evidenceRef: "evidence-synthetic-002",
        },
      ],
      artifactRefs: ["artifact-synthetic-resume"],
      nextAction: "Synthetic follow-up",
      nextActionAt: "2026-07-30T12:00:00+00:00",
      freshness: syntheticProjectionFreshness,
      createdAt: "2026-07-29T11:00:00+00:00",
      updatedAt: "2026-07-29T12:00:02+00:00",
    },
  ],
  freshness: {
    sourceEventId: "event-checkpoint-applications",
    sourceEventPosition: "SYNTHETIC:3",
    projectedAt: "2026-07-29T12:00:04+00:00",
    lagMs: 14,
    status: "fresh",
  },
  nextCursor: null,
} as const;

export const syntheticRelationshipPage = {
  items: [
    {
      relationshipId: "relationship-synthetic-001",
      opportunityId: "opportunity-synthetic-001",
      dexContactRef: "dex-contact-synthetic-001",
      relevanceScore: 88,
      relevanceSummary: "Synthetic professional relationship.",
      freshness: syntheticProjectionFreshness,
      createdAt: "2026-07-29T11:30:00+00:00",
      updatedAt: "2026-07-29T12:00:02+00:00",
    },
  ],
  freshness: {
    sourceEventId: "event-checkpoint-relationships",
    sourceEventPosition: "SYNTHETIC:4",
    projectedAt: "2026-07-29T12:00:05+00:00",
    lagMs: 15,
    status: "fresh",
  },
  nextCursor: "relationship-synthetic-001",
} as const;

export const syntheticOutreachPage = {
  items: [
    {
      outreachId: "outreach-synthetic-001",
      opportunityId: "opportunity-synthetic-001",
      relationshipId: "relationship-synthetic-001",
      status: "approved",
      channel: "gmail",
      messageCommitment:
        "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      approvalContractId: "approval-synthetic-001",
      sentEvidenceRef: null,
      freshness: syntheticProjectionFreshness,
      createdAt: "2026-07-29T11:45:00+00:00",
      updatedAt: "2026-07-29T12:00:02+00:00",
    },
  ],
  freshness: {
    sourceEventId: "event-checkpoint-outreach",
    sourceEventPosition: "SYNTHETIC:5",
    projectedAt: "2026-07-29T12:00:06+00:00",
    lagMs: 16,
    status: "replaying",
  },
  nextCursor: null,
} as const;

export const syntheticCompletedOperation = {
  id: "operation-synthetic-completed-001",
  correlationId: "correlation-synthetic-completed-001",
  command: "opportunities.create",
  status: "completed",
  createdAt: "2026-07-29T12:00:03+00:00",
  startedAt: "2026-07-29T12:00:04+00:00",
  completedAt: "2026-07-29T12:00:05+00:00",
  result: {
    opportunity_id: "opportunity-synthetic-001",
  },
  error: null,
  freshness: null,
} as const;

export const syntheticApprovalEvidence = {
  approvalId: "approval-synthetic-001",
  outreachId: "outreach-synthetic-001",
  messageCommitment:
    "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  channel: "gmail",
  approvedBy: "operator:synthetic",
  issuedAt: "2026-07-29T12:00:00+00:00",
  expiresAt: "2026-07-30T12:00:00+00:00",
  status: "approved",
} as const;

export const syntheticExecutionReceiptPayload = {
  contract_version: "accountability.v1",
  receipt_id: "opaque:v1:RRRRRRRRRRRRRRRRRRRRRR",
  event_id: "opaque:v1:EEEEEEEEEEEEEEEEEEEEEE",
  stream_pairwise_id: "pairwise:v1:SSSSSSSSSSSSSSSSSSSSSS",
  sequence: 1,
  subject_pairwise_id: "pairwise:v1:UUUUUUUUUUUUUUUUUUUUUU",
  tenant_scope: {
    scheme: "hmac_sha256_v1",
    purpose: "jobsearch_operation",
    digest:
      "sha256:1111111111111111111111111111111111111111111111111111111111111111",
  },
  purpose: "jobsearch_operation",
  request_id: "opaque:v1:QQQQQQQQQQQQQQQQQQQQQQ",
  idempotency_key: "opaque:v1:IIIIIIIIIIIIIIIIIIIIII",
  action_commitment: {
    scheme: "hmac_sha256_v1",
    purpose: "jobsearch_operation",
    digest:
      "sha256:2222222222222222222222222222222222222222222222222222222222222222",
  },
  execution_id: "opaque:v1:XXXXXXXXXXXXXXXXXXXXXX",
  executor_pairwise_id: "pairwise:v1:ZZZZZZZZZZZZZZZZZZZZZZ",
  status: "succeeded",
  started_at: "2026-07-29T12:00:00.000Z",
  completed_at: "2026-07-29T12:01:00.000Z",
  result_commitment: {
    scheme: "hmac_sha256_v1",
    purpose: "jobsearch_operation",
    digest:
      "sha256:3333333333333333333333333333333333333333333333333333333333333333",
  },
  reason_code: null,
  daml_transaction: null,
  signature: {
    algorithm: "ed25519",
    key_id: "pairwise:v1:KKKKKKKKKKKKKKKKKKKKKK",
    signature:
      "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
  },
} as const;

export const syntheticExecutionReceiptEvidence = {
  receiptId: "opaque:v1:RRRRRRRRRRRRRRRRRRRRRR",
  operationId: "operation-synthetic-completed-001",
  eventId: "opaque:v1:EEEEEEEEEEEEEEEEEEEEEE",
  status: "succeeded",
  reasonCode: null,
  payload: syntheticExecutionReceiptPayload,
  receiptHash:
    "sha256:e18c64598f2b5ed18116c8a00403bba04bb3f219d222377880a66fa56683d145",
  createdAt: "2026-07-29T12:01:00+00:00",
  completedAt: "2026-07-29T12:01:00.000Z",
  proofStatus: "server-recorded",
} as const;

export const syntheticCandidateProfile = {
  candidateName: "Nate Walker",
  title: "Principal AI Architect / CTO",
  bio: {
    fullName: "Nate Walker",
    headline: "AI Systems Architect & Engineering Executive",
    summary: "Proven leader building sovereign AI platforms, distributed systems, and real-time voice AI pipelines.",
    email: "nate@example.com",
    phone: "+1-555-0199",
    location: "Austin, TX / Remote",
    linkedinUrl: "https://linkedin.com/in/nwalker85",
    githubUrl: "https://github.com/nwalker85",
    portfolioUrl: "https://ravenhelm.dev",
  },
  targetRoles: [
    "VP of AI Engineering",
    "Chief Technology Officer",
    "Principal AI Architect",
    "Head of Machine Learning",
    "Distinguished Engineer",
  ],
  targetDomains: [
    "Agentic Workflow Systems",
    "Real-Time Conversational AI",
    "Applied LLM Infrastructure",
    "Enterprise AI Governance",
    "Developer Tooling Platforms",
  ],
  compensation: {
    minBase: 180000,
    targetTotal: 250000,
    minTotal: 200000,
    currency: "USD",
  },
  skills: [
    {
      name: "Python",
      category: "backend_api",
      tier: "expert",
      yearsExperience: 10,
      keywords: ["asyncio", "fastapi"],
      description: "Core language for backend AI services.",
      highlights: ["Built high-throughput inference proxies."],
    },
  ],
  productionMl: {
    llmOrchestration: {
      name: "LLM Orchestration & Systems",
      experienceLevel: "expert",
      years: 4,
      coreTechnologies: ["LangChain", "LlamaIndex", "MCP"],
      architecturalPatterns: ["ReAct", "Plan-and-Solve"],
      productionMilestones: ["Deployed multi-agent coordinator to production."],
    },
    asrTtsVoice: {
      name: "ASR / TTS Voice Pipelines",
      experienceLevel: "expert",
      years: 3,
      coreTechnologies: ["faster-whisper", "Deepgram", "Cartesia"],
      architecturalPatterns: ["Streaming WebSockets"],
      productionMilestones: ["Sub-200ms latency voice pipeline."],
    },
    fineTuningAdaptation: {
      name: "Fine-Tuning & Model Adaptation",
      experienceLevel: "advanced",
      years: 3,
      coreTechnologies: ["LoRA", "QLoRA", "Unsloth"],
      architecturalPatterns: ["Instruction Tuning"],
      productionMilestones: ["Tuned domain models with eval suites."],
    },
    embeddingsRag: {
      name: "Embeddings & Vector Search",
      experienceLevel: "expert",
      years: 4,
      coreTechnologies: ["pgvector", "Qdrant"],
      architecturalPatterns: ["Hybrid Dense/Sparse Search"],
      productionMilestones: ["Scaled hybrid vector index."],
    },
    agentLoopsTooling: {
      name: "Agent Loops & Tool Execution",
      experienceLevel: "expert",
      years: 3,
      coreTechnologies: ["MCP", "Function Calling"],
      architecturalPatterns: ["Governed Tool Handlers"],
      productionMilestones: ["Zero unverified tool executions."],
    },
    inferenceHardware: {
      name: "Inference Hardware & Acceleration",
      experienceLevel: "advanced",
      years: 3,
      coreTechnologies: ["vLLM", "TensorRT-LLM"],
      architecturalPatterns: ["Continuous Batching"],
      productionMilestones: ["Optimized GPU utilization on single 4090."],
    },
    llmSystems: ["vLLM", "Ollama"],
    agenticOrchestration: ["MCP Tool Protocol", "State Machines"],
    voiceSpeechAi: ["faster-whisper", "Kokoro TTS"],
    ragVectorSearch: ["pgvector", "Hybrid Reranking"],
    fineTuningEvals: ["RAGAS", "Promptfoo"],
    edgeQuantization: ["AWQ", "GGUF"],
  },
  updatedAt: "2026-08-24T00:00:00+00:00",
} as const;

export const syntheticLeadPage = {
  items: [
    {
      id: "lead-synthetic-001",
      sourceBoard: "Anthropic Careers",
      externalId: "ext-lead-001",
      employer: "Anthropic",
      organizationId: "org-synthetic-anthropic",
      title: "Principal AI Architect",
      location: "San Francisco, CA / Remote",
      remoteType: "remote",
      salaryMin: 220000,
      salaryMax: 280000,
      salaryCurrency: "USD",
      url: "https://anthropic.com/careers/arch",
      description: "Lead inference infrastructure.",
      requirements: ["LLM", "Distributed Systems"],
      fitScore: 94.5,
      matchBreakdown: { skills: 95, seniority: 94 },
      riskFlags: [],
      state: "discovered",
      convertedOpportunityId: null,
      createdAt: "2026-08-24T01:00:00+00:00",
      updatedAt: "2026-08-24T01:00:00+00:00",
    },
  ],
  freshness: syntheticProjectionFreshness,
  nextCursor: null,
} as const;

export const syntheticOrganizationPage = {
  items: [
    {
      id: "org-synthetic-anthropic",
      name: "Anthropic",
      domain: "anthropic.com",
      industry: "AI Research",
      size: "500+",
      advocacyRating: 95,
      notes: "High mission alignment.",
      createdAt: "2026-08-24T01:00:00+00:00",
      updatedAt: "2026-08-24T01:00:00+00:00",
    },
  ],
  freshness: syntheticProjectionFreshness,
  nextCursor: null,
} as const;

export const syntheticContactPage = {
  items: [
    {
      id: "contact-synthetic-001",
      name: "Alice Recruiter",
      email: "alice@anthropic.com",
      company: "Anthropic",
      jobTitle: "Lead Technical Recruiter",
      phone: null,
      notes: "Met at AI systems conference.",
      lastContacted: "2026-08-20T10:00:00+00:00",
      aiValue: 95,
      aiReason: "Direct contact with AI systems hiring manager.",
      outreachStrategy: "Warm intro via recent publication.",
      suggestedTiming: "This week",
      lastAnalyzed: "2026-08-20T12:00:00+00:00",
      advocacyScore: 92,
      organizationId: "org-synthetic-anthropic",
      crmNotes: "Prefers email.",
      communicationHistory: [
        {
          id: "comm-01",
          timestamp: "2026-08-20T10:00:00+00:00",
          channel: "gmail",
          direction: "inbound",
          subject: "Principal Architect Role",
          summary: "Inbound outreach regarding Principal Architect role.",
          messageId: "msg-01",
          evidenceRef: "evidence-synthetic-001",
          threadId: "thread-01",
        },
      ],
      linkedinUrl: "https://linkedin.com/in/alice-recruiter",
      relationshipTier: "tier_1",
      createdAt: "2026-08-20T10:00:00+00:00",
      updatedAt: "2026-08-20T10:00:00+00:00",
    },
  ],
  freshness: syntheticProjectionFreshness,
  nextCursor: null,
} as const;

export const syntheticNextBestActions = [
  {
    id: "nba-01",
    urgency: "P0",
    actionType: "reply_recruiter",
    title: "Reply to Alice Recruiter (Anthropic)",
    description: "Inbound recruiter message received 2 hours ago.",
    entityType: "message",
    entityId: "msg-01",
    score: 98,
    dueDate: "2026-08-24T18:00:00+00:00",
    actionUrl: "/messages/msg-01",
    metadata: { company: "Anthropic" },
    createdAt: "2026-08-24T02:00:00+00:00",
  },
] as const;

export const syntheticRecruiterPillSet = {
  incomingMessageId: "msg-01",
  senderName: "Alice Recruiter",
  senderEmailOrHandle: "alice@anthropic.com",
  roleMentioned: "Principal AI Architect",
  companyMentioned: "Anthropic",
  pills: [
    {
      pillType: "accept_and_schedule",
      label: "Accept & Propose Availability",
      subject: "Re: Principal Architect Role",
      bodyText: "Hi Alice, thank you for reaching out. Here is my availability.",
      bodyHtml: null,
      calendarSlotsInjected: ["Tuesday 10:00 AM CT", "Wednesday 2:00 PM CT"],
      requiresApproval: true,
      contextSummary: "Accepts interview and injects verified CT availability slots.",
    },
  ],
  generatedAt: "2026-08-24T02:00:00+00:00",
} as const;

export const syntheticDailyAvailability = [
  {
    dateStr: "2026-08-25",
    dayName: "Tuesday",
    slots30min: [
      {
        start: "2026-08-25T15:00:00+00:00",
        end: "2026-08-25T15:30:00+00:00",
        durationMinutes: 30,
        dayKey: "2026-08-25",
        formattedCt: "10:00 AM - 10:30 AM CT",
      },
    ],
    slots45min: [
      {
        start: "2026-08-25T15:00:00+00:00",
        end: "2026-08-25T15:45:00+00:00",
        durationMinutes: 45,
        dayKey: "2026-08-25",
        formattedCt: "10:00 AM - 10:45 AM CT",
      },
    ],
  },
] as const;

export const syntheticCalendarEvents = [
  {
    id: "cal-event-01",
    summary: "1:1 Architecture Sync",
    description: null,
    start: "2026-08-25T14:00:00+00:00",
    end: "2026-08-25T14:30:00+00:00",
    isAllDay: false,
    status: "confirmed",
    transparency: "opaque",
    location: "Google Meet",
    meetingLink: "https://meet.google.com/xyz",
    attendees: ["alice@anthropic.com"],
    organizerEmail: "alice@anthropic.com",
    isBusy: true,
  },
] as const;

export const syntheticMessagePage = {
  items: [
    {
      id: "msg-outbox-001",
      channel: "gmail",
      direction: "outbound",
      recipientAddress: "alice@anthropic.com",
      recipientName: "Alice Recruiter",
      recipientId: "contact-synthetic-001",
      subject: "Re: Principal AI Architect",
      bodyText: "Looking forward to speaking.",
      bodyHtml: null,
      threadId: "thread-01",
      inReplyTo: "msg-inbound-01",
      references: "msg-inbound-01",
      status: "sent",
      messageCommitment:
        "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      approvalId: "approval-synthetic-001",
      sentEvidenceRef: "evidence-synthetic-002",
      externalMessageId: "gmail-ext-01",
      errorMessage: null,
      createdAt: "2026-08-24T02:00:00+00:00",
      sentAt: "2026-08-24T02:05:00+00:00",
    },
  ],
  freshness: syntheticProjectionFreshness,
  nextCursor: null,
} as const;

export const syntheticInterviewDebriefPage = {
  items: [
    {
      id: "debrief-synthetic-001",
      createdAt: "2026-08-24T03:00:00+00:00",
      metadata: {
        company: "SoundHound",
        role: "VP of Conversational AI",
        roundType: "System Design",
        interviewDate: "2026-08-24",
        interviewerNames: ["Dr. Voice", "Lead Architect"],
        interviewerTitles: ["VP Research", "Principal Architect"],
        durationMinutes: 45,
        audioRef: null,
        opportunityId: "opp-synthetic-001",
        contactIds: ["contact-synthetic-001"],
      },
      executiveSummary: "Strong technical alignment on real-time streaming voice pipelines.",
      questionsAndAnswers: [
        {
          id: "qa-01",
          question: "How do you achieve sub-200ms voice streaming?",
          askedBy: "Dr. Voice",
          category: "System Design",
          answerSummary: "Detailed faster-whisper ASR GPU streaming and chunked TTS synthesis.",
          keyPointsMentioned: ["WebSockets", "Streaming ASR", "Chunked TTS"],
          effectivenessScore: 9.5,
          followUpNeeded: false,
        },
      ],
      fitAssessment: {
        overallScore: 94,
        technicalAlignment: "Excellent",
        leadershipAlignment: "Strong",
        compensationAlignment: "Aligned",
        greenFlags: ["Deep voice streaming architecture expertise"],
        redFlags: [],
        cultureNotes: "High engineering rigor.",
        recommendation: "Strong hire.",
      },
      actionItems: [
        {
          id: "action-01",
          title: "Send follow-up thank you note to Dr. Voice",
          actionType: "thank_you",
          priority: "P0",
          dueDate: "2026-08-25",
          recipientName: "Dr. Voice",
          recipientEmail: "voice@soundhound.com",
          draftContent: "Thank you for the discussion on sub-200ms latency pipelines.",
          opportunityId: "opp-synthetic-001",
          isCompleted: false,
        },
      ],
      rawTranscript: "[00:01] Dr. Voice: How do you achieve sub-200ms voice streaming?\n[00:05] Nate: WebSockets and streaming ASR.",
      transcriptSegments: [
        {
          offsetMs: 1000,
          speaker: "Dr. Voice",
          role: "interviewer",
          text: "How do you achieve sub-200ms voice streaming?",
          confidence: 0.98,
        },
      ],
    },
  ],
  freshness: syntheticProjectionFreshness,
  nextCursor: null,
} as const;

export const syntheticSendResult = {
  success: true,
  messageId: "msg-outbox-001",
  channel: "gmail",
  externalId: "gmail-ext-01",
  threadId: "thread-01",
  evidenceRef: "evidence-synthetic-002",
  error: null,
  sentAt: "2026-08-24T02:05:00+00:00",
} as const;

