# Milestone M4 Technical Design & Specification Report: TypeScript SDK Extension (`@ultradex/sdk`)

**Package Path**: `sdk/typescript/`  
**Workspace Name**: `@ultradex/sdk`  
**Author**: Explorer M4.2  
**Target Milestone**: M4 (GraphQL Projections & TypeScript SDK Extension)  
**Date**: 2026-08-24  

---

## 1. Observation

Direct inspection of the repository revealed the architectural layout, core domain models, GraphQL schemas, and existing TypeScript SDK implementation patterns.

### 1.1 Existing SDK Architecture (`sdk/typescript/`)
- **Package Configuration** (`sdk/typescript/package.json:1-30`):
  - Package: `@ultradex/sdk@0.1.0`, ESM (`"type": "module"`), targeting Node `>=20`.
  - Dependencies: `"zod": "4.1.5"`.
  - Dev Dependencies: `"typescript": "5.9.3"`, `"vitest": "3.2.6"`.
  - Scripts: `"build": "tsc -p tsconfig.json"`, `"test": "vitest run"`.
- **Existing Source Structure**:
  - `src/index.ts` (`sdk/typescript/src/index.ts:1-76`): Barrel export for `UltradexClient`, types, command names, query inputs, and error classes.
  - `src/contracts.ts` (`sdk/typescript/src/contracts.ts:1-768`): Zod schemas and inferred types for projections (`Opportunity`, `Application`, `Relationship`, `Outreach`, `Operation`, `ApprovalEvidence`, `ExecutionReceiptEvidence`), freshness (`ProjectionFreshness`), and command parameter schemas (`JOB_SEARCH_COMMAND_NAMES` [9 commands]).
  - `src/jobsearch-queries.ts` (`sdk/typescript/src/jobsearch-queries.ts:1-243`): GraphQL query constants (`LIST_OPPORTUNITIES_QUERY`, `LIST_APPLICATIONS_QUERY`, etc.), input schemas and variable builders (`opportunityVariables`, `applicationVariables`), and result envelope schemas (`opportunitiesResultSchema`, etc.).
  - `src/jobsearch-commands.ts` (`sdk/typescript/src/jobsearch-commands.ts:1-226`): `JobSearchCommandExecutor` mapping camelCase SDK parameters to snake_case REST payloads dispatched to `POST /api/v2/job-search/commands/{command_name}` with mandatory `Idempotency-Key` and optional `X-Correlation-Id` / `X-Delegation-Id`.
  - `src/transport.ts` (`sdk/typescript/src/transport.ts:1-343`): Generic `UltradexTransport` interface, `UltradexRequestExecutor` validating REST and GraphQL endpoints against Zod schemas, error hierarchy (`UltradexAuthError`, `UltradexHttpError`, `UltradexGraphQLError`, `UltradexSchemaError`, `UltradexTimeoutError`, `UltradexTransportError`).
  - `src/client.ts` (`sdk/typescript/src/client.ts:1-337`): `UltradexReadClient` and `UltradexCommandClient` interfaces unified in `UltradexClient`.
- **Existing Vitest Test Suite** (`sdk/typescript/tests/`):
  - `tests/fixtures.ts`: Synthetic mock objects with full ISO timestamps.
  - `tests/client.test.ts` (16 tests passing): Transport errors, timeouts, auth errors, JSON parsing, GraphQL error handling.
  - `tests/commands.test.ts` (12 tests passing): 9 governed command submissions, parameter transformations, idempotency checks.
  - `tests/projections.test.ts` (9 tests passing): GraphQL document generation, pagination cursors, freshness validation, execution receipt verification.

### 1.2 Backend Domain & Model Observations
- **Candidate Profile & Skills Taxonomy** (`core/jobsearch_profile.py:18-230, 706-800`):
  - `CandidateProfileStore.get_profile()` returns `CandidateProfile` with `skills` (44 CTO skills, 22 Expert, 22 Advanced), `production_ml` (6 pillars: LLM Orchestration, Voice AI / ASR / TTS, Fine-Tuning & PEFT, Embeddings & RAG, Agent Loops & Tool Sandboxing, Inference Hardware), `target_roles`, `target_role_families`, `target_domains`, `compensation` ($180k min base / $250k target total comp), `experience`, `education`, `projects`, `bio`.
- **CRM Domain Models** (`core/jobsearch_models.py:190-287` and `core/models.py:162-205`):
  - `OrganizationDB`: `id`, `name`, `domain`, `industry`, `size`, `advocacy_rating`, `notes`, `source_event_id`, `source_event_position`, `projected_at`, `created_at`, `updated_at`.
  - `LeadDB`: `id`, `source_board`, `external_id`, `employer`, `organization_id`, `title`, `location`, `remote_type`, `salary_min`, `salary_max`, `salary_currency`, `url`, `description`, `requirements` (JSON list), `fit_score` (Float 0-100), `match_breakdown` (JSON dict), `risk_flags` (JSON list), `state` (`"discovered" | "unapplied" | "converted" | "dismissed"`), `converted_opportunity_id`.
  - `ContactDB`: `id`, `name`, `email`, `company`, `job_title`, `phone`, `notes`, `last_contacted`, `ai_value`, `ai_reason`, `outreach_strategy`, `suggested_timing`, `last_analyzed`, `advocacy_score`, `organization_id`, `crm_notes`, `communication_history` (JSON list of interaction dicts), `linkedin_url`, `relationship_tier`.
- **Governed Command Catalog** (`core/jobsearch_commands.py:22-29` and `core/jobsearch_executors.py:189-207`):
  - Extended command catalog includes 17 commands (`COMMAND_NAMES_CRM`):
    - Original 9: `sources.ingest`, `opportunities.create`, `opportunities.score`, `applications.transition`, `relationships.sync`, `outreach.prepare`, `outreach.approve`, `outreach.send`, `evidence.export`.
    - CRM Milestone additions: `leads.create`, `leads.convert`, `organizations.create`, `organizations.update`, `applications.create`, `outreach.cancel`, `workspace.initialize`, `intent.set`.
- **Copilot & Recruiter 3-Pill Replies** (`core/jobsearch_copilot.py:38-110, 220-330, 331-520`):
  - `NextBestAction`: `id`, `urgency` (`"P0" | "P1" | "P2" | "P3"`), `action_type` (`"reply_recruiter" | "follow_up_application" | "complete_application_task" | "convert_high_fit_lead" | "network_outreach" | "send_thank_you" | "schedule_interview"`), `title`, `description`, `entity_type`, `entity_id`, `score` (Float 0-100), `due_date`, `action_url`, `metadata`, `created_at`.
  - `RecruiterPillReply`: `pill_type` (`"accept_and_schedule" | "request_scope_and_comp" | "polite_pass"`), `label`, `subject`, `body_text`, `body_html`, `calendar_slots_injected` (List[str]), `requires_approval` (bool), `context_summary`.
  - `RecruiterPillSet`: `incoming_message_id`, `sender_name`, `sender_email_or_handle`, `role_mentioned`, `company_mentioned`, `pills` (List[RecruiterPillReply]), `generated_at`.
- **Google Calendar & Open Working-Hour Slot Sensing** (`core/jobsearch_calendar.py:33-106, 416-556`):
  - `CalendarEvent`: `id`, `summary`, `description`, `start`, `end`, `is_all_day`, `status` (`"confirmed" | "tentative" | "cancelled"`), `transparency` (`"opaque" | "transparent"`), `location`, `meeting_link`, `attendees`, `organizer_email`.
  - `TimeSlot`: `start`, `end`, `duration_minutes`, `day_key` ("YYYY-MM-DD"), `formatted_ct` ("10:00 AM – 10:30 AM CT").
  - `DailyAvailability`: `date_str`, `day_name`, `slots_30min` (List[TimeSlot]), `slots_45min` (List[TimeSlot]), `busy_intervals`.
- **Omnichannel Messaging & In-App Outbox** (`core/jobsearch_messaging.py:46-115, 335-480`):
  - `MessageChannel`: `"gmail" | "linkedin" | "dex"`.
  - `MessageStatus`: `"draft" | "pending_approval" | "approved" | "queued" | "sending" | "sent" | "failed" | "cancelled"`.
  - `OutboxMessage`: `id`, `channel`, `direction` (`"inbound" | "outbound"`), `recipient_address`, `recipient_name`, `recipient_id`, `subject`, `body_text`, `body_html`, `thread_id`, `in_reply_to`, `references`, `status`, `message_commitment`, `approval_id`, `sent_evidence_ref`, `external_message_id`, `error_message`, `created_at`, `sent_at`.
  - `SendResult`: `success`, `message_id`, `channel`, `external_id`, `thread_id`, `evidence_ref`, `error`, `sent_at`.
- **Sovereign Voice & Interview Debriefs** (`core/jobsearch_gjallarhorn.py:39-112, 234-405`):
  - `TranscriptSegment`: `offset_ms`, `speaker`, `role` (`"candidate" | "interviewer" | "recruiter" | "unknown"`), `text`, `confidence`.
  - `InterviewMetadata`: `company`, `role`, `round_type`, `interview_date`, `interviewer_names`, `interviewer_titles`, `duration_minutes`, `audio_ref`, `opportunity_id`, `contact_ids`.
  - `QuestionAnswerPair`: `id`, `question`, `asked_by`, `category`, `answer_summary`, `key_points_mentioned`, `effectiveness_score` (Float 0-10), `follow_up_needed`.
  - `FitAssessment`: `overall_score` (Float 0-100), `technical_alignment`, `leadership_alignment`, `compensation_alignment`, `green_flags`, `red_flags`, `culture_notes`, `recommendation`.
  - `InterviewActionItem`: `id`, `title`, `action_type`, `priority` (`"p0" | "p1" | "p2"`), `due_date`, `recipient_name`, `recipient_email`, `draft_content`, `opportunity_id`, `is_completed`.
  - `InterviewDebrief`: `id`, `created_at`, `metadata`, `executive_summary`, `questions_and_answers`, `fit_assessment`, `action_items`, `raw_transcript`, `transcript_segments`.

---

## 2. Logic Chain

1. **CQRS Strict Consistency**:
   - Following the established pattern in `sdk/typescript/src/client.ts`, read operations must query GraphQL projections through `requestGraphQL()` (or designated typed REST endpoints via `requestRest()`), validating envelopes strictly through Zod schemas.
   - Governed state mutations must proceed via `JobSearchCommandExecutor.submit()` to `POST /api/v2/job-search/commands/{command_name}`, guaranteeing atomic idempotency, delegation tracking, event sourcing, and cryptographic execution receipts.
2. **Schema Type Safety & Bidirectional Interoperability**:
   - All TypeScript types must be inferred directly from Zod schemas (`z.infer<typeof schema>`).
   - String validation must reject malformed timestamps using `isoTimestampSchema`, enforce 0-100 ranges for scores/advocacy, and check enum discriminant values.
   - CamelCase TypeScript properties must map cleanly to snake_case wire parameters during command serialization.
3. **Comprehensive Method Surface**:
   - To satisfy both the CQRS contract convention and client application ergonomics (e.g. SvelteKit frontend in `apps/web/`), `UltradexClient` will expose both standard command methods (`submitLeadCreate`, `submitLeadConvert`, `submitOrganizationCreate`, `submitOrganizationUpdate`) and direct ergonomic query/action methods (`getProfile`, `getLeads`, `getLead`, `createLead`, `convertLead`, `getOrganizations`, `getOrganization`, `createOrganization`, `updateOrganization`, `getContacts`, `getContact`, `getNextBestActions`, `generateRecruiterReplies`, `getAvailability`, `getCalendarEvents`, `sendMessage`, `createDraft`, `getMessages`, `getInterviewDebriefs`, `getInterviewDebrief`).
4. **Complete Test Rigor**:
   - Every added schema and client method must have corresponding mock fixtures and Vitest test coverage ensuring schema validation, parameter marshaling, network error classification, and response decoding pass with 100% reliability.

---

## 3. Detailed Specification & Code Design

### 3.1 Type Definitions & Zod Schemas (`sdk/typescript/src/contracts.ts`)

```typescript
// ==========================================
// 1. CANDIDATE PROFILE & TAXONOMY
// ==========================================

export const skillTierSchema = z.enum([
  "expert",
  "advanced",
  "intermediate",
  "familiar",
]);

export const skillCategorySchema = z.enum([
  "ai_ml",
  "distributed_systems",
  "cloud_infra",
  "backend_api",
  "frontend_fullstack",
  "security_governance",
  "leadership_strategy",
]);

export const skillItemSchema = z
  .object({
    name: nonEmptyStringSchema,
    category: skillCategorySchema,
    tier: skillTierSchema,
    yearsExperience: z.number().int().nonnegative(),
    keywords: z.array(nonEmptyStringSchema),
    description: z.string(),
    highlights: z.array(nonEmptyStringSchema),
  })
  .strict();

export const mlDepthSubdomainSchema = z
  .object({
    name: nonEmptyStringSchema,
    experienceLevel: nonEmptyStringSchema,
    years: z.number().int().nonnegative(),
    coreTechnologies: z.array(nonEmptyStringSchema),
    architecturalPatterns: z.array(nonEmptyStringSchema),
    productionMilestones: z.array(nonEmptyStringSchema),
  })
  .strict();

export const productionMLDepthSchema = z
  .object({
    llmOrchestration: mlDepthSubdomainSchema,
    asrTtsVoice: mlDepthSubdomainSchema,
    fineTuningAdaptation: mlDepthSubdomainSchema,
    embeddingsRag: mlDepthSubdomainSchema,
    agentLoopsTooling: mlDepthSubdomainSchema,
    inferenceHardware: mlDepthSubdomainSchema,
    llmSystems: z.array(nonEmptyStringSchema),
    agenticOrchestration: z.array(nonEmptyStringSchema),
    voiceSpeechAi: z.array(nonEmptyStringSchema),
    ragVectorSearch: z.array(nonEmptyStringSchema),
    fineTuningEvals: z.array(nonEmptyStringSchema),
    edgeQuantization: z.array(nonEmptyStringSchema),
  })
  .strict();

export const workExperienceItemSchema = z
  .object({
    company: nonEmptyStringSchema,
    role: nonEmptyStringSchema,
    startDate: nonEmptyStringSchema,
    endDate: nonEmptyStringSchema.nullable(),
    isCurrent: z.boolean(),
    location: nonEmptyStringSchema,
    remoteType: nonEmptyStringSchema,
    summary: z.string(),
    keyAchievements: z.array(nonEmptyStringSchema),
    technologies: z.array(nonEmptyStringSchema),
  })
  .strict();

export const educationItemSchema = z
  .object({
    institution: nonEmptyStringSchema,
    degree: nonEmptyStringSchema,
    fieldOfStudy: nonEmptyStringSchema,
    graduationYear: z.number().int().nullable(),
    notes: z.string().nullable(),
  })
  .strict();

export const projectHighlightSchema = z
  .object({
    name: nonEmptyStringSchema,
    role: nonEmptyStringSchema,
    description: z.string(),
    url: z.string().url().nullable(),
    technologies: z.array(nonEmptyStringSchema),
  })
  .strict();

export const targetRoleConfigSchema = z
  .object({
    targetRoles: z.array(nonEmptyStringSchema),
    targetRoleFamilies: z.array(nonEmptyStringSchema),
    targetDomains: z.array(nonEmptyStringSchema),
    seniorityBand: nonEmptyStringSchema,
    locationPreference: nonEmptyStringSchema,
    remotePreference: nonEmptyStringSchema,
  })
  .strict();

export const compensationExpectationsSchema = z
  .object({
    minBase: z.number().int().positive(),
    targetTotal: z.number().int().positive(),
    minTotal: z.number().int().positive(),
    baseMinimumUsd: z.number().int().positive(),
    targetTotalCompUsd: z.number().int().positive(),
    minimumTotalCompUsd: z.number().int().positive(),
    equityPreference: nonEmptyStringSchema,
    currency: nonEmptyStringSchema,
    employmentType: nonEmptyStringSchema,
    locationPreference: nonEmptyStringSchema,
  })
  .strict();

export const candidateBioSchema = z
  .object({
    fullName: nonEmptyStringSchema,
    headline: nonEmptyStringSchema,
    summary: nonEmptyStringSchema,
    email: z.string().email().nullable(),
    phone: z.string().nullable(),
    location: nonEmptyStringSchema,
    linkedinUrl: z.string().url().nullable(),
    githubUrl: z.string().url().nullable(),
    portfolioUrl: z.string().url().nullable(),
  })
  .strict();

export const candidateProfileSchema = z
  .object({
    candidateName: nonEmptyStringSchema,
    title: nonEmptyStringSchema,
    resumeText: z.string(),
    bio: candidateBioSchema,
    targetRoles: z.array(nonEmptyStringSchema),
    targetDomains: z.array(nonEmptyStringSchema),
    targetRoleFamilies: z.array(nonEmptyStringSchema),
    targetRoleConfig: targetRoleConfigSchema,
    compensation: compensationExpectationsSchema,
    skills: z.record(z.string(), skillItemSchema),
    productionMl: productionMLDepthSchema,
    experience: z.array(workExperienceItemSchema),
    education: z.array(educationItemSchema),
    projects: z.array(projectHighlightSchema),
    updatedAt: isoTimestampSchema,
  })
  .strict();

// ==========================================
// 2. LEADS
// ==========================================

export const leadStatusSchema = z.enum([
  "discovered",
  "unapplied",
  "converted",
  "dismissed",
]);

export const leadSchema = z
  .object({
    id: nonEmptyStringSchema,
    sourceBoard: nonEmptyStringSchema,
    externalId: nonEmptyStringSchema.nullable(),
    employer: nonEmptyStringSchema,
    organizationId: nonEmptyStringSchema.nullable(),
    title: nonEmptyStringSchema,
    location: nonEmptyStringSchema.nullable(),
    remoteType: nonEmptyStringSchema,
    salaryMin: z.number().int().nullable(),
    salaryMax: z.number().int().nullable(),
    salaryCurrency: nonEmptyStringSchema,
    url: z.string().nullable(),
    description: z.string().nullable(),
    requirements: z.array(nonEmptyStringSchema),
    fitScore: z.number().min(0).max(100).nullable(),
    matchBreakdown: z.record(z.string(), jsonValueSchema),
    riskFlags: z.array(nonEmptyStringSchema),
    state: leadStatusSchema,
    convertedOpportunityId: nonEmptyStringSchema.nullable(),
    freshness: projectionFreshnessSchema,
    createdAt: isoTimestampSchema,
    updatedAt: isoTimestampSchema,
  })
  .strict();

export const leadPageSchema = z
  .object({
    items: z.array(leadSchema),
    freshness: projectionFreshnessSchema.nullable(),
    nextCursor: nonEmptyStringSchema.nullable(),
  })
  .strict();

export const leadCreateParametersSchema = z
  .object({
    employer: nonEmptyStringSchema,
    title: nonEmptyStringSchema,
    sourceBoard: nonEmptyStringSchema.optional(),
    externalId: nonEmptyStringSchema.optional(),
    organizationId: nonEmptyStringSchema.optional(),
    location: nonEmptyStringSchema.optional(),
    remoteType: nonEmptyStringSchema.optional(),
    salaryMin: z.number().int().positive().optional(),
    salaryMax: z.number().int().positive().optional(),
    salaryCurrency: nonEmptyStringSchema.optional(),
    url: z.string().optional(),
    description: z.string().optional(),
    requirements: z.array(nonEmptyStringSchema).optional(),
    fitScore: z.number().min(0).max(100).optional(),
    matchBreakdown: z.record(z.string(), jsonValueSchema).optional(),
    riskFlags: z.array(nonEmptyStringSchema).optional(),
  })
  .strict();

export const leadConvertParametersSchema = z
  .object({
    leadId: nonEmptyStringSchema,
    stage: applicationStatusSchema.optional(),
    occurredAt: isoTimestampSchema.optional(),
    customTitle: nonEmptyStringSchema.optional(),
    targetRoleFamily: nonEmptyStringSchema.optional(),
    contactRefs: z.array(nonEmptyStringSchema).optional(),
    nextAction: nonEmptyStringSchema.optional(),
    nextActionDeadline: isoTimestampSchema.optional(),
  })
  .strict();

// ==========================================
// 3. ORGANIZATIONS
// ==========================================

export const organizationSchema = z
  .object({
    id: nonEmptyStringSchema,
    name: nonEmptyStringSchema,
    domain: nonEmptyStringSchema.nullable(),
    industry: nonEmptyStringSchema.nullable(),
    size: nonEmptyStringSchema.nullable(),
    advocacyRating: z.number().min(0).max(100).nullable(),
    notes: z.string().nullable(),
    freshness: projectionFreshnessSchema,
    createdAt: isoTimestampSchema,
    updatedAt: isoTimestampSchema,
  })
  .strict();

export const organizationPageSchema = z
  .object({
    items: z.array(organizationSchema),
    freshness: projectionFreshnessSchema.nullable(),
    nextCursor: nonEmptyStringSchema.nullable(),
  })
  .strict();

export const organizationCreateParametersSchema = z
  .object({
    name: nonEmptyStringSchema,
    domain: nonEmptyStringSchema.optional(),
    industry: nonEmptyStringSchema.optional(),
    size: nonEmptyStringSchema.optional(),
    advocacyRating: z.number().min(0).max(100).optional(),
    notes: z.string().optional(),
  })
  .strict();

export const organizationUpdateParametersSchema = z
  .object({
    organizationId: nonEmptyStringSchema,
    name: nonEmptyStringSchema.optional(),
    domain: nonEmptyStringSchema.optional(),
    industry: nonEmptyStringSchema.optional(),
    size: nonEmptyStringSchema.optional(),
    advocacyRating: z.number().min(0).max(100).optional(),
    notes: z.string().optional(),
  })
  .strict();

// ==========================================
// 4. CONTACTS
// ==========================================

export const communicationEntrySchema = z
  .object({
    id: nonEmptyStringSchema,
    timestamp: isoTimestampSchema,
    channel: z.enum(["gmail", "linkedin", "dex"]),
    direction: z.enum(["inbound", "outbound"]),
    subject: nonEmptyStringSchema,
    summary: z.string(),
    messageId: nonEmptyStringSchema,
    evidenceRef: nonEmptyStringSchema,
    threadId: nonEmptyStringSchema.nullable().optional(),
  })
  .strict();

export const contactSchema = z
  .object({
    id: nonEmptyStringSchema,
    name: nonEmptyStringSchema,
    email: z.string().email().nullable(),
    company: nonEmptyStringSchema.nullable(),
    jobTitle: nonEmptyStringSchema.nullable(),
    phone: z.string().nullable(),
    notes: z.string().nullable(),
    lastContacted: isoTimestampSchema.nullable(),
    aiValue: z.number().min(0).max(100).nullable(),
    aiReason: z.string().nullable(),
    outreachStrategy: z.string().nullable(),
    suggestedTiming: z.string().nullable(),
    lastAnalyzed: isoTimestampSchema.nullable(),
    advocacyScore: z.number().min(0).max(100).nullable(),
    organizationId: nonEmptyStringSchema.nullable(),
    crmNotes: z.string().nullable(),
    communicationHistory: z.array(communicationEntrySchema),
    linkedinUrl: z.string().url().nullable(),
    relationshipTier: nonEmptyStringSchema.nullable(),
    createdAt: isoTimestampSchema,
    updatedAt: isoTimestampSchema,
  })
  .strict();

export const contactPageSchema = z
  .object({
    items: z.array(contactSchema),
    freshness: projectionFreshnessSchema.nullable(),
    nextCursor: nonEmptyStringSchema.nullable(),
  })
  .strict();

// ==========================================
// 5. NEXT BEST ACTIONS (COPILOT)
// ==========================================

export const actionUrgencySchema = z.enum(["P0", "P1", "P2", "P3"]);

export const actionTypeSchema = z.enum([
  "reply_recruiter",
  "follow_up_application",
  "complete_application_task",
  "convert_high_fit_lead",
  "network_outreach",
  "send_thank_you",
  "schedule_interview",
]);

export const nextBestActionSchema = z
  .object({
    id: nonEmptyStringSchema,
    urgency: actionUrgencySchema,
    actionType: actionTypeSchema,
    title: nonEmptyStringSchema,
    description: z.string(),
    entityType: z.enum([
      "lead",
      "application",
      "opportunity",
      "contact",
      "message",
    ]),
    entityId: nonEmptyStringSchema,
    score: z.number().min(0).max(100),
    dueDate: isoTimestampSchema.nullable(),
    actionUrl: nonEmptyStringSchema,
    metadata: z.record(z.string(), jsonValueSchema),
    createdAt: isoTimestampSchema,
  })
  .strict();

// ==========================================
// 6. RECRUITER 3-PILL REPLIES
// ==========================================

export const recruiterPillTypeSchema = z.enum([
  "accept_and_schedule",
  "request_scope_and_comp",
  "polite_pass",
]);

export const recruiterPillReplySchema = z
  .object({
    pillType: recruiterPillTypeSchema,
    label: nonEmptyStringSchema,
    subject: nonEmptyStringSchema,
    bodyText: nonEmptyStringSchema,
    bodyHtml: z.string().nullable(),
    calendarSlotsInjected: z.array(nonEmptyStringSchema),
    requiresApproval: z.boolean(),
    contextSummary: nonEmptyStringSchema,
  })
  .strict();

export const recruiterPillSetSchema = z
  .object({
    incomingMessageId: nonEmptyStringSchema,
    senderName: nonEmptyStringSchema,
    senderEmailOrHandle: nonEmptyStringSchema,
    roleMentioned: nonEmptyStringSchema.nullable(),
    companyMentioned: nonEmptyStringSchema.nullable(),
    pills: z.array(recruiterPillReplySchema),
    generatedAt: isoTimestampSchema,
  })
  .strict();

export const inboundMessageContextSchema = z
  .object({
    messageId: nonEmptyStringSchema.optional(),
    senderName: nonEmptyStringSchema,
    senderEmailOrHandle: nonEmptyStringSchema,
    subject: nonEmptyStringSchema,
    bodyText: nonEmptyStringSchema,
    receivedAt: isoTimestampSchema.optional(),
    channel: z.enum(["gmail", "linkedin"]).optional(),
    companyMentioned: nonEmptyStringSchema.optional(),
    roleMentioned: nonEmptyStringSchema.optional(),
    salaryMentioned: nonEmptyStringSchema.optional(),
    techStackMentioned: z.array(nonEmptyStringSchema).optional(),
  })
  .strict();

// ==========================================
// 7. CALENDAR & AVAILABILITY
// ==========================================

export const calendarEventStatusSchema = z.enum([
  "confirmed",
  "tentative",
  "cancelled",
]);

export const calendarTransparencySchema = z.enum(["opaque", "transparent"]);

export const interviewRoundTypeSchema = z.enum([
  "recruiter_screen",
  "hiring_manager_screen",
  "technical_deep_dive",
  "system_design",
  "coding_architecture",
  "executive_culture",
  "onsite_loop",
  "offer_review",
  "unknown",
]);

export const calendarEventSchema = z
  .object({
    id: nonEmptyStringSchema,
    summary: nonEmptyStringSchema,
    description: z.string().nullable(),
    start: isoTimestampSchema,
    end: isoTimestampSchema,
    isAllDay: z.boolean(),
    status: calendarEventStatusSchema,
    transparency: calendarTransparencySchema,
    location: z.string().nullable(),
    meetingLink: z.string().nullable(),
    attendees: z.array(nonEmptyStringSchema),
    organizerEmail: z.string().nullable(),
  })
  .strict();

export const timeSlotSchema = z
  .object({
    start: isoTimestampSchema,
    end: isoTimestampSchema,
    durationMinutes: z.number().int().positive(),
    dayKey: z.string().regex(/^\d{4}-\d{2}-\d{2}$/u),
    formattedCt: nonEmptyStringSchema,
  })
  .strict();

export const dailyAvailabilitySchema = z
  .object({
    dateStr: z.string().regex(/^\d{4}-\d{2}-\d{2}$/u),
    dayName: nonEmptyStringSchema,
    slots30min: z.array(timeSlotSchema),
    slots45min: z.array(timeSlotSchema),
  })
  .strict();

// ==========================================
// 8. OMNICHANNEL MESSAGING
// ==========================================

export const messageChannelSchema = z.enum(["gmail", "linkedin", "dex"]);
export const messageDirectionSchema = z.enum(["inbound", "outbound"]);
export const messageStatusSchema = z.enum([
  "draft",
  "pending_approval",
  "approved",
  "queued",
  "sending",
  "sent",
  "failed",
  "cancelled",
]);

export const composeMessageInputSchema = z
  .object({
    recipientAddress: nonEmptyStringSchema,
    subject: nonEmptyStringSchema,
    bodyText: nonEmptyStringSchema,
    bodyHtml: z.string().optional(),
    channel: messageChannelSchema.optional(),
    recipientName: nonEmptyStringSchema.optional(),
    recipientId: nonEmptyStringSchema.optional(),
    threadId: nonEmptyStringSchema.optional(),
    inReplyTo: nonEmptyStringSchema.optional(),
    references: nonEmptyStringSchema.optional(),
    opportunityId: nonEmptyStringSchema.optional(),
    relationshipId: nonEmptyStringSchema.optional(),
  })
  .strict();

export const outboxMessageSchema = z
  .object({
    id: nonEmptyStringSchema,
    channel: messageChannelSchema,
    direction: messageDirectionSchema,
    recipientAddress: nonEmptyStringSchema,
    recipientName: nonEmptyStringSchema.nullable(),
    recipientId: nonEmptyStringSchema.nullable(),
    subject: nonEmptyStringSchema,
    bodyText: nonEmptyStringSchema,
    bodyHtml: z.string().nullable(),
    threadId: nonEmptyStringSchema.nullable(),
    inReplyTo: nonEmptyStringSchema.nullable(),
    references: nonEmptyStringSchema.nullable(),
    status: messageStatusSchema,
    messageCommitment: sha256DigestSchema,
    approvalId: nonEmptyStringSchema.nullable(),
    sentEvidenceRef: nonEmptyStringSchema.nullable(),
    externalMessageId: nonEmptyStringSchema.nullable(),
    errorMessage: z.string().nullable(),
    createdAt: isoTimestampSchema,
    sentAt: isoTimestampSchema.nullable(),
  })
  .strict();

export const messagePageSchema = z
  .object({
    items: z.array(outboxMessageSchema),
    freshness: projectionFreshnessSchema.nullable(),
    nextCursor: nonEmptyStringSchema.nullable(),
  })
  .strict();

export const sendResultSchema = z
  .object({
    success: z.boolean(),
    messageId: nonEmptyStringSchema,
    channel: messageChannelSchema,
    externalId: nonEmptyStringSchema.nullable(),
    threadId: nonEmptyStringSchema.nullable(),
    evidenceRef: nonEmptyStringSchema.nullable(),
    error: z.string().nullable(),
    sentAt: isoTimestampSchema,
  })
  .strict();

// ==========================================
// 9. INTERVIEW DEBRIEFS (SOVEREIGN VOICE)
// ==========================================

export const speakerRoleSchema = z.enum([
  "candidate",
  "interviewer",
  "recruiter",
  "unknown",
]);

export const transcriptSegmentSchema = z
  .object({
    offsetMs: z.number().int().nonnegative(),
    speaker: nonEmptyStringSchema,
    role: speakerRoleSchema,
    text: nonEmptyStringSchema,
    confidence: z.number().min(0).max(1),
  })
  .strict();

export const interviewMetadataSchema = z
  .object({
    company: nonEmptyStringSchema,
    role: nonEmptyStringSchema,
    roundType: nonEmptyStringSchema,
    interviewDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/u),
    interviewerNames: z.array(nonEmptyStringSchema),
    interviewerTitles: z.array(nonEmptyStringSchema),
    durationMinutes: z.number().int().positive(),
    audioRef: nonEmptyStringSchema.nullable(),
    opportunityId: nonEmptyStringSchema.nullable(),
    contactIds: z.array(nonEmptyStringSchema),
  })
  .strict();

export const questionAnswerPairSchema = z
  .object({
    id: nonEmptyStringSchema,
    question: nonEmptyStringSchema,
    askedBy: nonEmptyStringSchema,
    category: nonEmptyStringSchema,
    answerSummary: nonEmptyStringSchema,
    keyPointsMentioned: z.array(nonEmptyStringSchema),
    effectivenessScore: z.number().min(0).max(10),
    followUpNeeded: z.boolean(),
  })
  .strict();

export const fitAssessmentSchema = z
  .object({
    overallScore: z.number().min(0).max(100),
    technicalAlignment: nonEmptyStringSchema,
    leadershipAlignment: nonEmptyStringSchema,
    compensationAlignment: nonEmptyStringSchema,
    greenFlags: z.array(nonEmptyStringSchema),
    redFlags: z.array(nonEmptyStringSchema),
    cultureNotes: z.string(),
    recommendation: nonEmptyStringSchema,
  })
  .strict();

export const interviewActionItemSchema = z
  .object({
    id: nonEmptyStringSchema,
    title: nonEmptyStringSchema,
    actionType: nonEmptyStringSchema,
    priority: z.enum(["p0", "p1", "p2"]),
    dueDate: nonEmptyStringSchema,
    recipientName: nonEmptyStringSchema.nullable(),
    recipientEmail: z.string().email().nullable(),
    draftContent: z.string().nullable(),
    opportunityId: nonEmptyStringSchema.nullable(),
    isCompleted: z.boolean(),
  })
  .strict();

export const interviewDebriefSchema = z
  .object({
    id: nonEmptyStringSchema,
    createdAt: isoTimestampSchema,
    metadata: interviewMetadataSchema,
    executiveSummary: nonEmptyStringSchema,
    questionsAndAnswers: z.array(questionAnswerPairSchema),
    fitAssessment: fitAssessmentSchema,
    actionItems: z.array(interviewActionItemSchema),
    rawTranscript: z.string(),
    transcriptSegments: z.array(transcriptSegmentSchema),
  })
  .strict();

export const interviewDebriefPageSchema = z
  .object({
    items: z.array(interviewDebriefSchema),
    freshness: projectionFreshnessSchema.nullable(),
    nextCursor: nonEmptyStringSchema.nullable(),
  })
  .strict();

// ==========================================
// EXTENDED GOVERNED COMMAND CATALOG
// ==========================================

export const JOB_SEARCH_COMMAND_NAMES = [
  "sources.ingest",
  "opportunities.create",
  "opportunities.score",
  "applications.create",
  "applications.transition",
  "relationships.sync",
  "outreach.prepare",
  "outreach.approve",
  "outreach.send",
  "outreach.cancel",
  "evidence.export",
  "leads.create",
  "leads.convert",
  "organizations.create",
  "organizations.update",
  "workspace.initialize",
  "intent.set",
] as const;

export const jobSearchCommandSchema = z.discriminatedUnion("commandName", [
  z.object({ commandName: z.literal("sources.ingest"), parameters: sourcesIngestParametersSchema }).strict(),
  z.object({ commandName: z.literal("opportunities.create"), parameters: opportunityCreateParametersSchema }).strict(),
  z.object({ commandName: z.literal("opportunities.score"), parameters: opportunityScoreParametersSchema }).strict(),
  z.object({ commandName: z.literal("applications.transition"), parameters: applicationTransitionParametersSchema }).strict(),
  z.object({ commandName: z.literal("relationships.sync"), parameters: relationshipSyncParametersSchema }).strict(),
  z.object({ commandName: z.literal("outreach.prepare"), parameters: outreachPrepareParametersSchema }).strict(),
  z.object({ commandName: z.literal("outreach.approve"), parameters: outreachApproveParametersSchema }).strict(),
  z.object({ commandName: z.literal("outreach.send"), parameters: outreachSendParametersSchema }).strict(),
  z.object({ commandName: z.literal("evidence.export"), parameters: evidenceExportParametersSchema }).strict(),
  z.object({ commandName: z.literal("leads.create"), parameters: leadCreateParametersSchema }).strict(),
  z.object({ commandName: z.literal("leads.convert"), parameters: leadConvertParametersSchema }).strict(),
  z.object({ commandName: z.literal("organizations.create"), parameters: organizationCreateParametersSchema }).strict(),
  z.object({ commandName: z.literal("organizations.update"), parameters: organizationUpdateParametersSchema }).strict(),
]);
```

---

### 3.2 GraphQL Query Documents & Variable Builders (`sdk/typescript/src/jobsearch-queries.ts`)

```typescript
// ==========================================
// 1. CANDIDATE PROFILE QUERY
// ==========================================

export const GET_PROFILE_QUERY = `
query GetProfile {
  profile {
    candidateName
    title
    resumeText
    bio {
      fullName
      headline
      summary
      email
      phone
      location
      linkedinUrl
      githubUrl
      portfolioUrl
    }
    targetRoles
    targetDomains
    targetRoleFamilies
    targetRoleConfig {
      targetRoles
      targetRoleFamilies
      targetDomains
      seniorityBand
      locationPreference
      remotePreference
    }
    compensation {
      minBase
      targetTotal
      minTotal
      baseMinimumUsd
      targetTotalCompUsd
      minimumTotalCompUsd
      equityPreference
      currency
      employmentType
      locationPreference
    }
    skills {
      name
      category
      tier
      yearsExperience
      keywords
      description
      highlights
    }
    productionMl {
      llmOrchestration { name experienceLevel years coreTechnologies architecturalPatterns productionMilestones }
      asrTtsVoice { name experienceLevel years coreTechnologies architecturalPatterns productionMilestones }
      fineTuningAdaptation { name experienceLevel years coreTechnologies architecturalPatterns productionMilestones }
      embeddingsRag { name experienceLevel years coreTechnologies architecturalPatterns productionMilestones }
      agentLoopsTooling { name experienceLevel years coreTechnologies architecturalPatterns productionMilestones }
      inferenceHardware { name experienceLevel years coreTechnologies architecturalPatterns productionMilestones }
      llmSystems
      agenticOrchestration
      voiceSpeechAi
      ragVectorSearch
      fineTuningEvals
      edgeQuantization
    }
    experience {
      company
      role
      startDate
      endDate
      isCurrent
      location
      remoteType
      summary
      keyAchievements
      technologies
    }
    education {
      institution
      degree
      fieldOfStudy
      graduationYear
      notes
    }
    projects {
      name
      role
      description
      url
      technologies
    }
    updatedAt
  }
}
`.trim();

export const profileResultSchema = z.object({ profile: candidateProfileSchema }).strict();

// ==========================================
// 2. LEADS QUERIES
// ==========================================

export interface LeadListInput {
  readonly first?: number;
  readonly after?: string;
  readonly minFitScore?: number;
  readonly state?: z.infer<typeof leadStatusSchema>;
  readonly employer?: string;
}

export function leadVariables(input: LeadListInput = {}): Record<string, unknown> {
  return optionalVariables({
    first: input.first ?? 20,
    after: input.after,
    minFitScore: input.minFitScore,
    state: input.state,
    employer: input.employer,
  });
}

export const LIST_LEADS_QUERY = `
query ListLeads($first: Int!, $after: String, $minFitScore: Float, $state: String, $employer: String) {
  leads(first: $first, after: $after, minFitScore: $minFitScore, state: $state, employer: $employer) {
    items {
      id
      sourceBoard
      externalId
      employer
      organizationId
      title
      location
      remoteType
      salaryMin
      salaryMax
      salaryCurrency
      url
      description
      requirements
      fitScore
      matchBreakdown
      riskFlags
      state
      convertedOpportunityId
      freshness { sourceEventId sourceEventPosition projectedAt lagMs status }
      createdAt
      updatedAt
    }
    freshness { sourceEventId sourceEventPosition projectedAt lagMs status }
    nextCursor
  }
}
`.trim();

export const GET_LEAD_QUERY = `
query GetLead($id: String!) {
  lead(id: $id) {
    id
    sourceBoard
    externalId
    employer
    organizationId
    title
    location
    remoteType
    salaryMin
    salaryMax
    salaryCurrency
    url
    description
    requirements
    fitScore
    matchBreakdown
    riskFlags
    state
    convertedOpportunityId
    freshness { sourceEventId sourceEventPosition projectedAt lagMs status }
    createdAt
    updatedAt
  }
}
`.trim();

export const leadsResultSchema = z.object({ leads: leadPageSchema }).strict();
export const leadResultSchema = z.object({ lead: leadSchema.nullable() }).strict();

// ==========================================
// 3. ORGANIZATIONS QUERIES
// ==========================================

export interface OrganizationListInput {
  readonly first?: number;
  readonly after?: string;
  readonly sortBy?: "name" | "id";
}

export function organizationVariables(input: OrganizationListInput = {}): Record<string, unknown> {
  return optionalVariables({
    first: input.first ?? 20,
    after: input.after,
    sortBy: input.sortBy ?? "name",
  });
}

export const LIST_ORGANIZATIONS_QUERY = `
query ListOrganizations($first: Int!, $after: String, $sortBy: String) {
  organizations(first: $first, after: $after, sortBy: $sortBy) {
    items {
      id
      name
      domain
      industry
      size
      advocacyRating
      notes
      freshness { sourceEventId sourceEventPosition projectedAt lagMs status }
      createdAt
      updatedAt
    }
    freshness { sourceEventId sourceEventPosition projectedAt lagMs status }
    nextCursor
  }
}
`.trim();

export const GET_ORGANIZATION_QUERY = `
query GetOrganization($id: String!) {
  organization(id: $id) {
    id
    name
    domain
    industry
    size
    advocacyRating
    notes
    freshness { sourceEventId sourceEventPosition projectedAt lagMs status }
    createdAt
    updatedAt
  }
}
`.trim();

export const organizationsResultSchema = z.object({ organizations: organizationPageSchema }).strict();
export const organizationResultSchema = z.object({ organization: organizationSchema.nullable() }).strict();

// ==========================================
// 4. CONTACTS QUERIES
// ==========================================

export interface ContactListInput {
  readonly first?: number;
  readonly after?: string;
  readonly organizationId?: string;
  readonly minAdvocacyScore?: number;
  readonly relationshipTier?: string;
}

export function contactVariables(input: ContactListInput = {}): Record<string, unknown> {
  return optionalVariables({
    first: input.first ?? 25,
    after: input.after,
    organizationId: input.organizationId,
    minAdvocacyScore: input.minAdvocacyScore,
    relationshipTier: input.relationshipTier,
  });
}

export const LIST_CONTACTS_QUERY = `
query ListContacts($first: Int!, $after: String, $organizationId: String, $minAdvocacyScore: Float, $relationshipTier: String) {
  contacts(first: $first, after: $after, organizationId: $organizationId, minAdvocacyScore: $minAdvocacyScore, relationshipTier: $relationshipTier) {
    items {
      id
      name
      email
      company
      jobTitle
      phone
      notes
      lastContacted
      aiValue
      aiReason
      outreachStrategy
      suggestedTiming
      lastAnalyzed
      advocacyScore
      organizationId
      crmNotes
      communicationHistory { id timestamp channel direction subject summary messageId evidenceRef threadId }
      linkedinUrl
      relationshipTier
      createdAt
      updatedAt
    }
    freshness { sourceEventId sourceEventPosition projectedAt lagMs status }
    nextCursor
  }
}
`.trim();

export const GET_CONTACT_QUERY = `
query GetContact($id: String!) {
  contact(id: $id) {
    id
    name
    email
    company
    jobTitle
    phone
    notes
    lastContacted
    aiValue
    aiReason
    outreachStrategy
    suggestedTiming
    lastAnalyzed
    advocacyScore
    organizationId
    crmNotes
    communicationHistory { id timestamp channel direction subject summary messageId evidenceRef threadId }
    linkedinUrl
    relationshipTier
    createdAt
    updatedAt
  }
}
`.trim();

export const contactsResultSchema = z.object({ contacts: contactPageSchema }).strict();
export const contactResultSchema = z.object({ contact: contactSchema.nullable() }).strict();

// ==========================================
// 5. NEXT BEST ACTIONS QUERY
// ==========================================

export const GET_NEXT_BEST_ACTIONS_QUERY = `
query GetNextBestActions($limit: Int) {
  nextBestActions(limit: $limit) {
    id
    urgency
    actionType
    title
    description
    entityType
    entityId
    score
    dueDate
    actionUrl
    metadata
    createdAt
  }
}
`.trim();

export const nextBestActionsResultSchema = z.object({ nextBestActions: z.array(nextBestActionSchema) }).strict();

// ==========================================
// 6. RECRUITER 3-PILL REPLIES QUERY
// ==========================================

export const GENERATE_RECRUITER_REPLIES_QUERY = `
query GenerateRecruiterReplies($message: InboundMessageContextInput!, $calendarAvailability: [String!]) {
  generateRecruiterReplies(message: $message, calendarAvailability: $calendarAvailability) {
    incomingMessageId
    senderName
    senderEmailOrHandle
    roleMentioned
    companyMentioned
    pills {
      pillType
      label
      subject
      bodyText
      bodyHtml
      calendarSlotsInjected
      requiresApproval
      contextSummary
    }
    generatedAt
  }
}
`.trim();

export const recruiterRepliesResultSchema = z.object({ generateRecruiterReplies: recruiterPillSetSchema }).strict();

// ==========================================
// 7. CALENDAR AVAILABILITY & EVENTS QUERIES
// ==========================================

export interface AvailabilityInput {
  readonly startDate: string;
  readonly endDate: string;
  readonly durationMinutes?: number;
  readonly bufferMinutes?: number;
}

export interface CalendarEventsInput {
  readonly timeMin: string;
  readonly timeMax: string;
}

export const GET_AVAILABILITY_QUERY = `
query GetAvailability($startDate: String!, $endDate: String!, $durationMinutes: Int, $bufferMinutes: Int) {
  availability(startDate: $startDate, endDate: $endDate, durationMinutes: $durationMinutes, bufferMinutes: $bufferMinutes) {
    dateStr
    dayName
    slots30min { start end durationMinutes dayKey formattedCt }
    slots45min { start end durationMinutes dayKey formattedCt }
  }
}
`.trim();

export const GET_CALENDAR_EVENTS_QUERY = `
query GetCalendarEvents($timeMin: String!, $timeMax: String!) {
  calendarEvents(timeMin: $timeMin, timeMax: $timeMax) {
    id
    summary
    description
    start
    end
    isAllDay
    status
    transparency
    location
    meetingLink
    attendees
    organizerEmail
  }
}
`.trim();

export const availabilityResultSchema = z.object({ availability: z.array(dailyAvailabilitySchema) }).strict();
export const calendarEventsResultSchema = z.object({ calendarEvents: z.array(calendarEventSchema) }).strict();

// ==========================================
// 8. OMNICHANNEL MESSAGING QUERIES & DISPATCH
// ==========================================

export interface MessageListInput {
  readonly first?: number;
  readonly after?: string;
  readonly channel?: z.infer<typeof messageChannelSchema>;
  readonly status?: z.infer<typeof messageStatusSchema>;
  readonly threadId?: string;
  readonly recipientId?: string;
}

export const LIST_MESSAGES_QUERY = `
query ListMessages($first: Int!, $after: String, $channel: String, $status: String, $threadId: String, $recipientId: String) {
  messages(first: $first, after: $after, channel: $channel, status: $status, threadId: $threadId, recipientId: $recipientId) {
    items {
      id
      channel
      direction
      recipientAddress
      recipientName
      recipientId
      subject
      bodyText
      bodyHtml
      threadId
      inReplyTo
      references
      status
      messageCommitment
      approvalId
      sentEvidenceRef
      externalMessageId
      errorMessage
      createdAt
      sentAt
    }
    freshness { sourceEventId sourceEventPosition projectedAt lagMs status }
    nextCursor
  }
}
`.trim();

export const messagesResultSchema = z.object({ messages: messagePageSchema }).strict();

// ==========================================
// 9. INTERVIEW DEBRIEFS QUERIES
// ==========================================

export interface InterviewDebriefListInput {
  readonly first?: number;
  readonly after?: string;
  readonly opportunityId?: string;
}

export const LIST_INTERVIEW_DEBRIEFS_QUERY = `
query ListInterviewDebriefs($first: Int!, $after: String, $opportunityId: String) {
  interviewDebriefs(first: $first, after: $after, opportunityId: $opportunityId) {
    items {
      id
      createdAt
      metadata { company role roundType interviewDate interviewerNames interviewerTitles durationMinutes audioRef opportunityId contactIds }
      executiveSummary
      questionsAndAnswers { id question askedBy category answerSummary keyPointsMentioned effectivenessScore followUpNeeded }
      fitAssessment { overallScore technicalAlignment leadershipAlignment compensationAlignment greenFlags redFlags cultureNotes recommendation }
      actionItems { id title actionType priority dueDate recipientName recipientEmail draftContent opportunityId isCompleted }
      rawTranscript
      transcriptSegments { offsetMs speaker role text confidence }
    }
    freshness { sourceEventId sourceEventPosition projectedAt lagMs status }
    nextCursor
  }
}
`.trim();

export const GET_INTERVIEW_DEBRIEF_QUERY = `
query GetInterviewDebrief($id: String!) {
  interviewDebrief(id: $id) {
    id
    createdAt
    metadata { company role roundType interviewDate interviewerNames interviewerTitles durationMinutes audioRef opportunityId contactIds }
    executiveSummary
    questionsAndAnswers { id question askedBy category answerSummary keyPointsMentioned effectivenessScore followUpNeeded }
    fitAssessment { overallScore technicalAlignment leadershipAlignment compensationAlignment greenFlags redFlags cultureNotes recommendation }
    actionItems { id title actionType priority dueDate recipientName recipientEmail draftContent opportunityId isCompleted }
    rawTranscript
    transcriptSegments { offsetMs speaker role text confidence }
  }
}
`.trim();

export const interviewDebriefsResultSchema = z.object({ interviewDebriefs: interviewDebriefPageSchema }).strict();
export const interviewDebriefResultSchema = z.object({ interviewDebrief: interviewDebriefSchema.nullable() }).strict();
```

---

### 3.3 Command Parameters Serializer (`sdk/typescript/src/jobsearch-commands.ts`)

```typescript
function commandParameters(command: JobSearchCommand): Readonly<Record<string, unknown>> {
  switch (command.commandName) {
    case "sources.ingest":
      return {
        source_kind: command.parameters.sourceKind,
        source_ref: command.parameters.sourceRef,
        observed_at: command.parameters.observedAt,
      };
    case "opportunities.create":
      return {
        employer: command.parameters.employer,
        title: command.parameters.title,
        source_evidence_id: command.parameters.sourceEvidenceId,
      };
    case "opportunities.score":
      return {
        opportunity_id: command.parameters.opportunityId,
        lens: command.parameters.lens,
      };
    case "applications.transition":
      return {
        application_id: command.parameters.applicationId,
        status: command.parameters.status,
        occurred_at: command.parameters.occurredAt,
      };
    case "relationships.sync":
      return {
        opportunity_id: command.parameters.opportunityId,
        dex_contact_ref: command.parameters.dexContactRef,
      };
    case "outreach.prepare":
      return {
        opportunity_id: command.parameters.opportunityId,
        channel: command.parameters.channel,
        message_commitment: command.parameters.messageCommitment,
        ...(command.parameters.relationshipId === undefined ? {} : { relationship_id: command.parameters.relationshipId }),
      };
    case "outreach.approve":
      return {
        outreach_id: command.parameters.outreachId,
        message_commitment: command.parameters.messageCommitment,
      };
    case "outreach.send":
      return {
        outreach_id: command.parameters.outreachId,
        approval_contract_id: command.parameters.approvalContractId,
        message_commitment: command.parameters.messageCommitment,
        channel: command.parameters.channel,
      };
    case "evidence.export":
      return {
        subject_type: command.parameters.subjectType,
        subject_id: command.parameters.subjectId,
        profile: command.parameters.profile,
      };
    case "leads.create":
      return {
        employer: command.parameters.employer,
        title: command.parameters.title,
        ...(command.parameters.sourceBoard ? { source_board: command.parameters.sourceBoard } : {}),
        ...(command.parameters.externalId ? { external_id: command.parameters.externalId } : {}),
        ...(command.parameters.organizationId ? { organization_id: command.parameters.organizationId } : {}),
        ...(command.parameters.location ? { location: command.parameters.location } : {}),
        ...(command.parameters.remoteType ? { remote_type: command.parameters.remoteType } : {}),
        ...(command.parameters.salaryMin !== undefined ? { salary_min: command.parameters.salaryMin } : {}),
        ...(command.parameters.salaryMax !== undefined ? { salary_max: command.parameters.salaryMax } : {}),
        ...(command.parameters.salaryCurrency ? { salary_currency: command.parameters.salaryCurrency } : {}),
        ...(command.parameters.url ? { url: command.parameters.url } : {}),
        ...(command.parameters.description ? { description: command.parameters.description } : {}),
        ...(command.parameters.requirements ? { requirements: command.parameters.requirements } : {}),
        ...(command.parameters.fitScore !== undefined ? { fit_score: command.parameters.fitScore } : {}),
        ...(command.parameters.matchBreakdown ? { match_breakdown: command.parameters.matchBreakdown } : {}),
        ...(command.parameters.riskFlags ? { risk_flags: command.parameters.riskFlags } : {}),
      };
    case "leads.convert":
      return {
        lead_id: command.parameters.leadId,
        ...(command.parameters.stage ? { stage: command.parameters.stage } : {}),
        ...(command.parameters.occurredAt ? { occurred_at: command.parameters.occurredAt } : {}),
        ...(command.parameters.customTitle ? { custom_title: command.parameters.customTitle } : {}),
        ...(command.parameters.targetRoleFamily ? { target_role_family: command.parameters.targetRoleFamily } : {}),
        ...(command.parameters.contactRefs ? { contact_refs: command.parameters.contactRefs } : {}),
        ...(command.parameters.nextAction ? { next_action: command.parameters.nextAction } : {}),
        ...(command.parameters.nextActionDeadline ? { next_action_deadline: command.parameters.nextActionDeadline } : {}),
      };
    case "organizations.create":
      return {
        name: command.parameters.name,
        ...(command.parameters.domain ? { domain: command.parameters.domain } : {}),
        ...(command.parameters.industry ? { industry: command.parameters.industry } : {}),
        ...(command.parameters.size ? { size: command.parameters.size } : {}),
        ...(command.parameters.advocacyRating !== undefined ? { advocacy_rating: command.parameters.advocacyRating } : {}),
        ...(command.parameters.notes ? { notes: command.parameters.notes } : {}),
      };
    case "organizations.update":
      return {
        organization_id: command.parameters.organizationId,
        ...(command.parameters.name ? { name: command.parameters.name } : {}),
        ...(command.parameters.domain ? { domain: command.parameters.domain } : {}),
        ...(command.parameters.industry ? { industry: command.parameters.industry } : {}),
        ...(command.parameters.size ? { size: command.parameters.size } : {}),
        ...(command.parameters.advocacyRating !== undefined ? { advocacy_rating: command.parameters.advocacyRating } : {}),
        ...(command.parameters.notes ? { notes: command.parameters.notes } : {}),
      };
  }
}
```

---

### 3.4 Extended Client Interfaces & Implementation (`sdk/typescript/src/client.ts`)

```typescript
export interface UltradexReadClient {
  getHealth(): Promise<HealthStatus>;
  getReadiness(): Promise<ReadinessStatus>;
  getProfile(): Promise<CandidateProfile>;
  listOpportunities(input?: OpportunityListInput): Promise<OpportunityPage>;
  listApplications(input?: ApplicationListInput): Promise<ApplicationPage>;
  listRelationships(input?: RelationshipListInput): Promise<RelationshipPage>;
  listOutreach(input?: OutreachListInput): Promise<OutreachPage>;
  listOperations(input?: OperationListInput): Promise<Operation[]>;
  getOperation(operationId: string): Promise<Operation | null>;
  getOperationEvents(operationId: string, input?: EventPageInput): Promise<OperationLifecycleEvent[]>;
  getApproval(approvalId: string): Promise<ApprovalEvidence | null>;
  getExecutionReceipt(operationId: string): Promise<ExecutionReceiptEvidence | null>;

  // Milestone M4 CRM & Copilot Read Projections
  getLeads(input?: LeadListInput): Promise<LeadPage>;
  getLead(leadId: string): Promise<Lead | null>;
  getOrganizations(input?: OrganizationListInput): Promise<OrganizationPage>;
  getOrganization(organizationId: string): Promise<Organization | null>;
  getContacts(input?: ContactListInput): Promise<ContactPage>;
  getContact(contactId: string): Promise<Contact | null>;
  getNextBestActions(limit?: number): Promise<NextBestAction[]>;
  generateRecruiterReplies(
    message: InboundMessageContext,
    calendarAvailability?: string[],
  ): Promise<RecruiterPillSet>;
  getAvailability(input: AvailabilityInput): Promise<DailyAvailability[]>;
  getCalendarEvents(input: CalendarEventsInput): Promise<CalendarEvent[]>;
  getMessages(input?: MessageListInput): Promise<MessagePage>;
  getInterviewDebriefs(input?: InterviewDebriefListInput): Promise<InterviewDebriefPage>;
  getInterviewDebrief(id: string): Promise<InterviewDebrief | null>;
}

export interface UltradexCommandClient {
  submitSourcesIngest(parameters: SourcesIngestParameters, options: JobSearchCommandOptions): Promise<ContractHandle>;
  submitOpportunityCreate(parameters: OpportunityCreateParameters, options: JobSearchCommandOptions): Promise<ContractHandle>;
  submitOpportunityScore(parameters: OpportunityScoreParameters, options: JobSearchCommandOptions): Promise<ContractHandle>;
  submitApplicationTransition(parameters: ApplicationTransitionParameters, options: JobSearchCommandOptions): Promise<ContractHandle>;
  submitRelationshipSync(parameters: RelationshipSyncParameters, options: JobSearchCommandOptions): Promise<ContractHandle>;
  submitOutreachPrepare(parameters: OutreachPrepareParameters, options: JobSearchCommandOptions): Promise<ContractHandle>;
  submitOutreachApprove(parameters: OutreachApproveParameters, options: JobSearchCommandOptions): Promise<ContractHandle>;
  submitOutreachSend(parameters: OutreachSendParameters, options: JobSearchCommandOptions): Promise<ContractHandle>;
  submitEvidenceExport(parameters: EvidenceExportParameters, options: JobSearchCommandOptions): Promise<ContractHandle>;

  // Milestone M4 Governed Command Submissions
  submitLeadCreate(parameters: LeadCreateParameters, options: JobSearchCommandOptions): Promise<ContractHandle>;
  submitLeadConvert(parameters: LeadConvertParameters, options: JobSearchCommandOptions): Promise<ContractHandle>;
  submitOrganizationCreate(parameters: OrganizationCreateParameters, options: JobSearchCommandOptions): Promise<ContractHandle>;
  submitOrganizationUpdate(parameters: OrganizationUpdateParameters, options: JobSearchCommandOptions): Promise<ContractHandle>;

  // Milestone M4 Direct Dispatchers & Aliases
  createLead(parameters: LeadCreateParameters, options: JobSearchCommandOptions): Promise<ContractHandle>;
  convertLead(parameters: LeadConvertParameters, options: JobSearchCommandOptions): Promise<ContractHandle>;
  createOrganization(parameters: OrganizationCreateParameters, options: JobSearchCommandOptions): Promise<ContractHandle>;
  updateOrganization(parameters: OrganizationUpdateParameters, options: JobSearchCommandOptions): Promise<ContractHandle>;
  sendMessage(parameters: ComposeMessageInput): Promise<SendResult>;
  createDraft(parameters: ComposeMessageInput): Promise<SendResult>;
}
```

Implementation in `UltradexClient`:

```typescript
export class UltradexClient implements UltradexReadClient, UltradexCommandClient {
  private readonly executor: UltradexRequestExecutor;
  private readonly commandExecutor: JobSearchCommandExecutor;

  constructor(options: UltradexClientOptions) {
    this.executor = new UltradexRequestExecutor(options);
    this.commandExecutor = new JobSearchCommandExecutor(options);
  }

  // --- Profile ---
  async getProfile(): Promise<CandidateProfile> {
    const result = await this.executor.requestGraphQL(GET_PROFILE_QUERY, {}, profileResultSchema);
    return result.profile;
  }

  // --- Leads ---
  async getLeads(input: LeadListInput = {}): Promise<LeadPage> {
    const result = await this.executor.requestGraphQL(LIST_LEADS_QUERY, leadVariables(input), leadsResultSchema);
    return result.leads;
  }

  async getLead(leadId: string): Promise<Lead | null> {
    const result = await this.executor.requestGraphQL(GET_LEAD_QUERY, exactIdVariables("id", leadId), leadResultSchema);
    return result.lead;
  }

  submitLeadCreate(parameters: LeadCreateParameters, options: JobSearchCommandOptions): Promise<ContractHandle> {
    return this.commandExecutor.submit({ commandName: "leads.create", parameters }, options);
  }

  submitLeadConvert(parameters: LeadConvertParameters, options: JobSearchCommandOptions): Promise<ContractHandle> {
    return this.commandExecutor.submit({ commandName: "leads.convert", parameters }, options);
  }

  createLead(parameters: LeadCreateParameters, options: JobSearchCommandOptions): Promise<ContractHandle> {
    return this.submitLeadCreate(parameters, options);
  }

  convertLead(parameters: LeadConvertParameters, options: JobSearchCommandOptions): Promise<ContractHandle> {
    return this.submitLeadConvert(parameters, options);
  }

  // --- Organizations ---
  async getOrganizations(input: OrganizationListInput = {}): Promise<OrganizationPage> {
    const result = await this.executor.requestGraphQL(LIST_ORGANIZATIONS_QUERY, organizationVariables(input), organizationsResultSchema);
    return result.organizations;
  }

  async getOrganization(organizationId: string): Promise<Organization | null> {
    const result = await this.executor.requestGraphQL(GET_ORGANIZATION_QUERY, exactIdVariables("id", organizationId), organizationResultSchema);
    return result.organization;
  }

  submitOrganizationCreate(parameters: OrganizationCreateParameters, options: JobSearchCommandOptions): Promise<ContractHandle> {
    return this.commandExecutor.submit({ commandName: "organizations.create", parameters }, options);
  }

  submitOrganizationUpdate(parameters: OrganizationUpdateParameters, options: JobSearchCommandOptions): Promise<ContractHandle> {
    return this.commandExecutor.submit({ commandName: "organizations.update", parameters }, options);
  }

  createOrganization(parameters: OrganizationCreateParameters, options: JobSearchCommandOptions): Promise<ContractHandle> {
    return this.submitOrganizationCreate(parameters, options);
  }

  updateOrganization(parameters: OrganizationUpdateParameters, options: JobSearchCommandOptions): Promise<ContractHandle> {
    return this.submitOrganizationUpdate(parameters, options);
  }

  // --- Contacts ---
  async getContacts(input: ContactListInput = {}): Promise<ContactPage> {
    const result = await this.executor.requestGraphQL(LIST_CONTACTS_QUERY, contactVariables(input), contactsResultSchema);
    return result.contacts;
  }

  async getContact(contactId: string): Promise<Contact | null> {
    const result = await this.executor.requestGraphQL(GET_CONTACT_QUERY, exactIdVariables("id", contactId), contactResultSchema);
    return result.contact;
  }

  // --- Next Best Actions ---
  async getNextBestActions(limit = 10): Promise<NextBestAction[]> {
    const result = await this.executor.requestGraphQL(GET_NEXT_BEST_ACTIONS_QUERY, { limit }, nextBestActionsResultSchema);
    return result.nextBestActions;
  }

  // --- Recruiter 3-Pill Replies ---
  async generateRecruiterReplies(
    message: InboundMessageContext,
    calendarAvailability?: string[],
  ): Promise<RecruiterPillSet> {
    const result = await this.executor.requestGraphQL(
      GENERATE_RECRUITER_REPLIES_QUERY,
      { message, calendarAvailability },
      recruiterRepliesResultSchema,
    );
    return result.generateRecruiterReplies;
  }

  // --- Calendar Availability & Events ---
  async getAvailability(input: AvailabilityInput): Promise<DailyAvailability[]> {
    const result = await this.executor.requestGraphQL(GET_AVAILABILITY_QUERY, input, availabilityResultSchema);
    return result.availability;
  }

  async getCalendarEvents(input: CalendarEventsInput): Promise<CalendarEvent[]> {
    const result = await this.executor.requestGraphQL(GET_CALENDAR_EVENTS_QUERY, input, calendarEventsResultSchema);
    return result.calendarEvents;
  }

  // --- Omnichannel Messaging ---
  async getMessages(input: MessageListInput = {}): Promise<MessagePage> {
    const result = await this.executor.requestGraphQL(LIST_MESSAGES_QUERY, optionalVariables(input), messagesResultSchema);
    return result.messages;
  }

  async sendMessage(parameters: ComposeMessageInput): Promise<SendResult> {
    return this.executor.requestRest("/api/v2/messages/send", sendResultSchema);
  }

  async createDraft(parameters: ComposeMessageInput): Promise<SendResult> {
    return this.executor.requestRest("/api/v2/messages/draft", sendResultSchema);
  }

  // --- Interview Debriefs ---
  async getInterviewDebriefs(input: InterviewDebriefListInput = {}): Promise<InterviewDebriefPage> {
    const result = await this.executor.requestGraphQL(LIST_INTERVIEW_DEBRIEFS_QUERY, optionalVariables(input), interviewDebriefsResultSchema);
    return result.interviewDebriefs;
  }

  async getInterviewDebrief(id: string): Promise<InterviewDebrief | null> {
    const result = await this.executor.requestGraphQL(GET_INTERVIEW_DEBRIEF_QUERY, exactIdVariables("id", id), interviewDebriefResultSchema);
    return result.interviewDebrief;
  }
}
```

---

## 4. Vitest Test Suite Architecture (`sdk/typescript/tests/`)

### 4.1 Mock Fixtures (`tests/fixtures.ts`)
Add structured synthetic fixtures for:
1. `syntheticCandidateProfile`: Complete 44-skill taxonomy (22 Expert, 22 Advanced), 6-subdomain ML depth, comp bounds ($180k base / $250k target), resume, bio.
2. `syntheticLeadPage` & `syntheticLead`: Source board ("Anthropic"), fit score 94, match breakdown, risk flags.
3. `syntheticOrganizationPage` & `syntheticOrganization`: Employer directory item, advocacy score 88, domain, notes.
4. `syntheticContactPage` & `syntheticContact`: Dex contact with advocacy score 92, communication history entries.
5. `syntheticNextBestActions`: Prioritized list with P0/P1/P2 urgencies, composite scores, action URLs.
6. `syntheticRecruiterPillSet`: 3 pills (Accept & Availability, Scope & Comp, Polite Pass) with injected calendar slots.
7. `syntheticDailyAvailability` & `syntheticCalendarEvents`: Working hours slots (09:00–17:00 CT) with 30-min/45-min durations.
8. `syntheticMessagePage`, `syntheticOutboxMessage` & `syntheticSendResult`: Outbound Gmail message with sha256 commitment.
9. `syntheticInterviewDebriefPage` & `syntheticInterviewDebrief`: Full interview debrief with executive summary, Q&As, fit assessment (92.0 score), and P0/P1 action items.

### 4.2 Test Files & Coverage Plan
- `tests/projections.test.ts`:
  - Verify `getProfile()` parses candidate profile and skills taxonomy without loss.
  - Verify `getLeads()` and `getLead(id)` handle pagination cursors, filters, and null states.
  - Verify `getOrganizations()` and `getOrganization(id)` validate firmographics and advocacy ratings.
  - Verify `getContacts()` and `getContact(id)` parse communication history and metadata.
  - Verify `getNextBestActions()` parses urgency enums, scores, and action URLs.
  - Verify `generateRecruiterReplies()` validates 3 pills and injected slots.
  - Verify `getAvailability()` and `getCalendarEvents()` enforce Central Time timestamps.
  - Verify `getMessages()` parses outbox status and sha256 commitments.
  - Verify `getInterviewDebriefs()` and `getInterviewDebrief(id)` parse executive summary, Q&As, fit score, and action items.
- `tests/commands.test.ts`:
  - Verify `submitLeadCreate` / `createLead` formats `leads.create` payload to snake_case.
  - Verify `submitLeadConvert` / `convertLead` formats `leads.convert` payload with stage and contact refs.
  - Verify `submitOrganizationCreate` / `createOrganization` formats `organizations.create` payload.
  - Verify `submitOrganizationUpdate` / `updateOrganization` formats `organizations.update` payload.
  - Verify missing/empty idempotency key triggers instant validation refusal before network I/O.
  - Verify server refusals (503/403) parse structured refusal reasons (`synthetic_policy_denied`).
- `tests/client.test.ts`:
  - Verify client instantiation, same-origin proxy defaults, token passing, and HTTP error mappings (401, 403, 500, 503).

---

## 5. Caveats

1. **GraphQL Projections vs. REST Fallbacks**:
   - The primary design models read projections as GraphQL queries via `requestGraphQL()`. If specific standalone REST endpoints (such as `GET /profile` or `POST /api/v2/messages/send`) are invoked by specific UI adapters, `UltradexRequestExecutor.requestRest()` is fully available and type-safe.
2. **Signature Verification & Proof Status**:
   - As established in earlier contracts, cryptographic execution receipts emitted by the backend are marked as `"server-recorded"`. The SDK validates structural integrity and SHA-256 payload commitments without asserting third-party public key signature verification.
3. **Workspace Singleton Commands**:
   - Commands like `workspace.initialize` and `intent.set` operate on fixed singletons (`workspace-private` and `intent-workspace-01`). The SDK passes parameters directly without requiring client-side ID generation for singletons.

---

## 6. Conclusion

The specification above delivers a comprehensive, production-grade extension of `@ultradex/sdk` covering:
1. **Candidate Profile Store & Skills Taxonomy**: Type-safe access to 44 CTO skills, 6 ML depth subdomains, and comp bounds.
2. **Leads Domain**: Full CRUD read projections and atomic `leads.create` / `leads.convert` governed commands.
3. **Organizations Domain**: Employer directory reads and `organizations.create` / `organizations.update` governed commands.
4. **Contacts Domain**: Rich CRM contacts with advocacy scores and communication history.
5. **Copilot Next Best Actions**: Prioritized Command Home recommendations.
6. **Recruiter 3-Pill Replies**: Contextual responses with live availability injection.
7. **Google Calendar & Open Slots**: 09:00–17:00 CT availability sensing for 30-min and 45-min slots.
8. **Omnichannel In-App Messaging**: Outbox message tracking and direct delivery.
9. **Sovereign Voice & Interview Debriefs**: Structured debriefs with executive summary, Q&A pairs, and action items.

All interfaces, Zod schemas, variable builders, and command parameters maintain 100% parity with the backend domain models and the CQRS governance architecture.

---

## 7. Verification Method

To independently verify the TypeScript SDK extension once implemented:

1. **Run TypeScript Compilation**:
   ```bash
   npm run build --workspace=@ultradex/sdk
   ```
   *Expected output*: `tsc -p tsconfig.json` exits with code 0 and zero type diagnostics.

2. **Run Vitest Test Suite**:
   ```bash
   npm test --workspace=@ultradex/sdk
   ```
   *Expected output*: All unit, fixture, projection, and command test suites pass with 100% success.

3. **Verify Downstream Web Application Compilation**:
   ```bash
   npm run check --workspace=ccc-glass || npm test --workspace=ccc-glass
   ```
   *Expected output*: Frontend SvelteKit application imports all types and client methods without import or type errors.
