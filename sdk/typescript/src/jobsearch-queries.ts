import { z } from "zod";

import {
  applicationPageSchema,
  applicationStatusSchema,
  approvalEvidenceSchema,
  calendarEventSchema,
  candidateProfileSchema,
  contactPageSchema,
  contactSchema,
  dailyAvailabilitySchema,
  executionReceiptEvidenceSchema,
  interviewDebriefPageSchema,
  interviewDebriefSchema,
  leadPageSchema,
  leadSchema,
  leadStatusSchema,
  messageChannelSchema,
  messagePageSchema,
  messageStatusSchema,
  nextBestActionSchema,
  operationLifecycleEventSchema,
  operationSchema,
  operationStatusSchema,
  opportunityPageSchema,
  opportunitySchema,
  opportunityStatusSchema,
  organizationPageSchema,
  organizationSchema,
  outreachPageSchema,
  outreachStatusSchema,
  recruiterPillSetSchema,
  relationshipPageSchema,
  relationshipSchema,
} from "./contracts.js";

export interface OpportunityListInput {
  readonly first?: number;
  readonly after?: string;
  readonly status?: z.infer<typeof opportunityStatusSchema>;
}

export interface ApplicationListInput {
  readonly first?: number;
  readonly after?: string;
  readonly status?: z.infer<typeof applicationStatusSchema>;
  readonly opportunityId?: string;
}

export interface RelationshipListInput {
  readonly first?: number;
  readonly after?: string;
  readonly opportunityId?: string;
}

export interface OutreachListInput {
  readonly first?: number;
  readonly after?: string;
  readonly status?: z.infer<typeof outreachStatusSchema>;
  readonly opportunityId?: string;
}

export interface OperationListInput {
  readonly limit?: number;
  readonly status?: z.infer<typeof operationStatusSchema>;
}

export interface EventPageInput {
  readonly first?: number;
  readonly after?: number;
}

export interface LeadListInput {
  readonly first?: number;
  readonly after?: string;
  readonly minFitScore?: number;
  readonly state?: z.infer<typeof leadStatusSchema>;
  readonly employer?: string;
}

export interface OrganizationListInput {
  readonly first?: number;
  readonly after?: string;
  readonly sortBy?: "name" | "id";
}

export interface ContactListInput {
  readonly first?: number;
  readonly after?: string;
  readonly organizationId?: string;
  readonly minAdvocacyScore?: number;
  readonly relationshipTier?: string;
  readonly search?: string;
}

export interface AvailabilityInput {
  readonly startDate: string;
  readonly endDate: string;
  readonly durationMinutes?: number;
  readonly bufferMinutes?: number;
}

export interface CalendarEventsInput {
  readonly startDate?: string;
  readonly endDate?: string;
  readonly timeMin?: string;
  readonly timeMax?: string;
}

export interface MessageListInput {
  readonly first?: number;
  readonly after?: string;
  readonly channel?: z.infer<typeof messageChannelSchema>;
  readonly status?: z.infer<typeof messageStatusSchema>;
  readonly threadId?: string;
  readonly recipientId?: string;
}

export interface InterviewDebriefListInput {
  readonly first?: number;
  readonly after?: string;
  readonly opportunityId?: string;
}

const firstSchema = z.number().int().min(1).max(100);
const cursorSchema = z.string().min(1);

const opportunityListInputSchema = z
  .object({
    first: firstSchema.optional(),
    after: cursorSchema.optional(),
    status: opportunityStatusSchema.optional(),
  })
  .strict();

const applicationListInputSchema = z
  .object({
    first: firstSchema.optional(),
    after: cursorSchema.optional(),
    status: applicationStatusSchema.optional(),
    opportunityId: cursorSchema.optional(),
  })
  .strict();

const relationshipListInputSchema = z
  .object({
    first: firstSchema.optional(),
    after: cursorSchema.optional(),
    opportunityId: cursorSchema.optional(),
  })
  .strict();

const outreachListInputSchema = z
  .object({
    first: firstSchema.optional(),
    after: cursorSchema.optional(),
    status: outreachStatusSchema.optional(),
    opportunityId: cursorSchema.optional(),
  })
  .strict();

const operationListInputSchema = z
  .object({
    limit: firstSchema.optional(),
    status: operationStatusSchema.optional(),
  })
  .strict();

const eventPageInputSchema = z
  .object({
    first: firstSchema.optional(),
    after: z.number().int().positive().optional(),
  })
  .strict();

const leadListInputSchema = z
  .object({
    first: firstSchema.optional(),
    after: cursorSchema.optional(),
    minFitScore: z.number().min(0).max(100).optional(),
    state: leadStatusSchema.optional(),
    employer: cursorSchema.optional(),
  })
  .strict();

const organizationListInputSchema = z
  .object({
    first: firstSchema.optional(),
    after: cursorSchema.optional(),
    sortBy: z.enum(["name", "id"]).optional(),
  })
  .strict();

const contactListInputSchema = z
  .object({
    first: firstSchema.optional(),
    after: cursorSchema.optional(),
    organizationId: cursorSchema.optional(),
    minAdvocacyScore: z.number().min(0).max(100).optional(),
    relationshipTier: cursorSchema.optional(),
    search: cursorSchema.optional(),
  })
  .strict();

const messageListInputSchema = z
  .object({
    first: firstSchema.optional(),
    after: cursorSchema.optional(),
    channel: messageChannelSchema.optional(),
    status: messageStatusSchema.optional(),
    threadId: cursorSchema.optional(),
    recipientId: cursorSchema.optional(),
  })
  .strict();

const interviewDebriefListInputSchema = z
  .object({
    first: firstSchema.optional(),
    after: cursorSchema.optional(),
    opportunityId: cursorSchema.optional(),
  })
  .strict();

export function optionalVariables(
  values: Readonly<Record<string, unknown>>,
): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(values).filter(([, value]) => value !== undefined),
  );
}

export function opportunityVariables(
  input: OpportunityListInput = {},
): Record<string, unknown> {
  const value = opportunityListInputSchema.parse(input);
  return optionalVariables({
    first: value.first ?? 25,
    after: value.after,
    status: value.status,
  });
}

export function applicationVariables(
  input: ApplicationListInput = {},
): Record<string, unknown> {
  const value = applicationListInputSchema.parse(input);
  return optionalVariables({
    first: value.first ?? 25,
    after: value.after,
    status: value.status,
    opportunityId: value.opportunityId,
  });
}

export function relationshipVariables(
  input: RelationshipListInput = {},
): Record<string, unknown> {
  const value = relationshipListInputSchema.parse(input);
  return optionalVariables({
    first: value.first ?? 25,
    after: value.after,
    opportunityId: value.opportunityId,
  });
}

export function outreachVariables(
  input: OutreachListInput = {},
): Record<string, unknown> {
  const value = outreachListInputSchema.parse(input);
  return optionalVariables({
    first: value.first ?? 25,
    after: value.after,
    status: value.status,
    opportunityId: value.opportunityId,
  });
}

export function operationVariables(
  input: OperationListInput = {},
): Record<string, unknown> {
  const value = operationListInputSchema.parse(input);
  return optionalVariables({
    limit: value.limit ?? 10,
    status: value.status,
  });
}

export function eventVariables(
  operationId: string,
  input: EventPageInput = {},
): Record<string, unknown> {
  const id = cursorSchema.parse(operationId);
  const value = eventPageInputSchema.parse(input);
  return optionalVariables({
    operationId: id,
    first: value.first ?? 50,
    after: value.after,
  });
}

export function leadVariables(
  input: LeadListInput = {},
): Record<string, unknown> {
  const value = leadListInputSchema.parse(input);
  return optionalVariables({
    first: value.first ?? 25,
    after: value.after,
    minFitScore: value.minFitScore,
    state: value.state,
    employer: value.employer,
  });
}

export function organizationVariables(
  input: OrganizationListInput = {},
): Record<string, unknown> {
  const value = organizationListInputSchema.parse(input);
  return optionalVariables({
    first: value.first ?? 25,
    after: value.after,
    sortBy: value.sortBy ?? "name",
  });
}

export function contactVariables(
  input: ContactListInput = {},
): Record<string, unknown> {
  const value = contactListInputSchema.parse(input);
  return optionalVariables({
    first: value.first ?? 25,
    after: value.after,
    organizationId: value.organizationId,
    minAdvocacyScore: value.minAdvocacyScore,
    relationshipTier: value.relationshipTier,
    search: value.search,
  });
}

export function messageVariables(
  input: MessageListInput = {},
): Record<string, unknown> {
  const value = messageListInputSchema.parse(input);
  return optionalVariables({
    first: value.first ?? 25,
    after: value.after,
    channel: value.channel,
    status: value.status,
    threadId: value.threadId,
    recipientId: value.recipientId,
  });
}

export function interviewDebriefVariables(
  input: InterviewDebriefListInput = {},
): Record<string, unknown> {
  const value = interviewDebriefListInputSchema.parse(input);
  return optionalVariables({
    first: value.first ?? 25,
    after: value.after,
    opportunityId: value.opportunityId,
  });
}

const availabilityInputSchema = z
  .object({
    startDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/u),
    endDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/u),
    durationMinutes: z.number().int().positive().optional(),
    bufferMinutes: z.number().int().nonnegative().optional(),
  })
  .strict();

const calendarEventsInputSchema = z
  .object({
    startDate: z.string().optional(),
    endDate: z.string().optional(),
    timeMin: z.string().optional(),
    timeMax: z.string().optional(),
  })
  .strict();

export function availabilityVariables(
  input: AvailabilityInput,
): Record<string, unknown> {
  const value = availabilityInputSchema.parse(input);
  return optionalVariables({
    startDate: value.startDate,
    endDate: value.endDate,
    durationMinutes: value.durationMinutes,
    bufferMinutes: value.bufferMinutes,
  });
}

export function calendarEventsVariables(
  input: CalendarEventsInput = {},
): Record<string, unknown> {
  const value = calendarEventsInputSchema.parse(input);
  return optionalVariables({
    startDate: value.startDate,
    endDate: value.endDate,
    timeMin: value.timeMin,
    timeMax: value.timeMax,
  });
}

export function exactIdVariables(
  key: "id" | "operationId",
  value: string,
): Record<string, unknown> {
  return { [key]: cursorSchema.parse(value) };
}

export const LIST_OPPORTUNITIES_QUERY =
  "query ListOpportunities($first: Int!, $after: String, $status: String) { opportunities(first: $first, after: $after, status: $status) { items { opportunityId employer title location roleFamily status fitScore fitExplanation riskFlags evidenceRefs { evidenceId sourceKind sourceRef classification observedAt commitment redactedSummary } freshness { sourceEventId sourceEventPosition projectedAt lagMs status } createdAt updatedAt } freshness { sourceEventId sourceEventPosition projectedAt lagMs status } nextCursor } }";

export const LIST_APPLICATIONS_QUERY =
  "query ListApplications($first: Int!, $after: String, $status: String, $opportunityId: String) { applications(first: $first, after: $after, status: $status, opportunityId: $opportunityId) { items { applicationId opportunityId status stageHistory { status occurredAt evidenceRef } artifactRefs nextAction nextActionAt freshness { sourceEventId sourceEventPosition projectedAt lagMs status } createdAt updatedAt } freshness { sourceEventId sourceEventPosition projectedAt lagMs status } nextCursor } }";

export const LIST_RELATIONSHIPS_QUERY =
  "query ListRelationships($first: Int!, $after: String, $opportunityId: String) { relationships(first: $first, after: $after, opportunityId: $opportunityId) { items { relationshipId opportunityId dexContactRef relevanceScore relevanceSummary freshness { sourceEventId sourceEventPosition projectedAt lagMs status } createdAt updatedAt } freshness { sourceEventId sourceEventPosition projectedAt lagMs status } nextCursor } }";

export const GET_RELATIONSHIP_QUERY =
  "query GetRelationship($id: String!) { relationship(id: $id) { relationshipId opportunityId dexContactRef relevanceScore relevanceSummary freshness { sourceEventId sourceEventPosition projectedAt lagMs status } createdAt updatedAt } }";

export const GET_OPPORTUNITY_QUERY =
  "query GetOpportunity($id: String!) { opportunity(id: $id) { opportunityId employer title location roleFamily status fitScore fitExplanation riskFlags evidenceRefs { evidenceId sourceKind sourceRef classification observedAt commitment redactedSummary } freshness { sourceEventId sourceEventPosition projectedAt lagMs status } createdAt updatedAt } }";

export const LIST_OUTREACH_QUERY =
  "query ListOutreach($first: Int!, $after: String, $status: String, $opportunityId: String) { outreach(first: $first, after: $after, status: $status, opportunityId: $opportunityId) { items { outreachId opportunityId relationshipId status channel messageCommitment approvalContractId sentEvidenceRef freshness { sourceEventId sourceEventPosition projectedAt lagMs status } createdAt updatedAt } freshness { sourceEventId sourceEventPosition projectedAt lagMs status } nextCursor } }";

export const LIST_OPERATIONS_QUERY =
  "query ListOperations($limit: Int!, $status: String) { operations(limit: $limit, status: $status) { id correlationId command status createdAt startedAt completedAt result error freshness { sourceEventId sourceEventPosition projectedAt lagMs status } } }";

export const GET_OPERATION_QUERY =
  "query GetOperation($id: String!) { operation(id: $id) { id correlationId command status createdAt startedAt completedAt result error freshness { sourceEventId sourceEventPosition projectedAt lagMs status } } }";

export const GET_OPERATION_EVENTS_QUERY =
  "query GetOperationEvents($operationId: String!, $first: Int!, $after: Int) { events(operationId: $operationId, first: $first, after: $after) { id operationId eventType timestamp payload } }";

export const GET_APPROVAL_QUERY =
  "query GetApproval($id: String!) { approval(id: $id) { approvalId outreachId messageCommitment channel approvedBy issuedAt expiresAt status } }";

export const GET_EXECUTION_RECEIPT_QUERY =
  "query GetExecutionReceipt($operationId: String!) { executionReceipt(operationId: $operationId) { receiptId operationId eventId status reasonCode payload receiptHash createdAt completedAt proofStatus } }";

// Milestone M4: Candidate Profile Query
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
    expertSkills {
      name
      category
      tier
      yearsExperience
      keywords
      description
      highlights
    }
    advancedSkills {
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

// Milestone M4: Leads Queries
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

// Milestone M4: Organizations Queries
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

// Milestone M4: Contacts Queries
export const LIST_CONTACTS_QUERY = `
query ListContacts($first: Int!, $after: String, $organizationId: String, $minAdvocacyScore: Float, $relationshipTier: String, $search: String) {
  contacts(first: $first, after: $after, organizationId: $organizationId, minAdvocacyScore: $minAdvocacyScore, relationshipTier: $relationshipTier, search: $search) {
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

// Milestone M4: Copilot Next Best Actions Query
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

// Milestone M4: Recruiter 3-Pill Replies Query
export const GENERATE_RECRUITER_REPLIES_QUERY = `
query GenerateRecruiterReplies($message: InboundMessageContextInput, $messageContext: InboundMessageContextInput, $calendarAvailability: [String!]) {
  generateRecruiterReplies(message: $message, messageContext: $messageContext, calendarAvailability: $calendarAvailability) {
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

// Milestone M4: Calendar & Availability Queries
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
query GetCalendarEvents($startDate: String, $endDate: String, $timeMin: String, $timeMax: String) {
  calendarEvents(startDate: $startDate, endDate: $endDate, timeMin: $timeMin, timeMax: $timeMax) {
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
    isBusy
  }
}
`.trim();

// Milestone M4: Messages Query
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

// Milestone M4: Interview Debriefs Queries
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

// Result Envelope Schemas
export const opportunitiesResultSchema = z
  .object({ opportunities: opportunityPageSchema })
  .strict();
export const opportunityResultSchema = z
  .object({ opportunity: opportunitySchema.nullable() })
  .strict();
export const applicationsResultSchema = z
  .object({ applications: applicationPageSchema })
  .strict();
export const relationshipsResultSchema = z
  .object({ relationships: relationshipPageSchema })
  .strict();
export const relationshipResultSchema = z
  .object({ relationship: relationshipSchema.nullable() })
  .strict();
export const outreachResultSchema = z
  .object({ outreach: outreachPageSchema })
  .strict();
export const operationsResultSchema = z
  .object({ operations: z.array(operationSchema) })
  .strict();
export const operationResultSchema = z
  .object({ operation: operationSchema.nullable() })
  .strict();
export const eventsResultSchema = z
  .object({ events: z.array(operationLifecycleEventSchema) })
  .strict();
export const approvalResultSchema = z
  .object({ approval: approvalEvidenceSchema.nullable() })
  .strict();
export const executionReceiptResultSchema = z
  .object({ executionReceipt: executionReceiptEvidenceSchema.nullable() })
  .strict();

export const profileResultSchema = z
  .object({ profile: candidateProfileSchema })
  .strict();
export const leadsResultSchema = z
  .object({ leads: leadPageSchema })
  .strict();
export const leadResultSchema = z
  .object({ lead: leadSchema.nullable() })
  .strict();
export const organizationsResultSchema = z
  .object({ organizations: organizationPageSchema })
  .strict();
export const organizationResultSchema = z
  .object({ organization: organizationSchema.nullable() })
  .strict();
export const contactsResultSchema = z
  .object({ contacts: contactPageSchema })
  .strict();
export const contactResultSchema = z
  .object({ contact: contactSchema.nullable() })
  .strict();
export const nextBestActionsResultSchema = z
  .object({ nextBestActions: z.array(nextBestActionSchema) })
  .strict();
export const recruiterRepliesResultSchema = z
  .object({ generateRecruiterReplies: recruiterPillSetSchema })
  .strict();
export const availabilityResultSchema = z
  .object({ availability: z.array(dailyAvailabilitySchema) })
  .strict();
export const calendarEventsResultSchema = z
  .object({ calendarEvents: z.array(calendarEventSchema) })
  .strict();
export const messagesResultSchema = z
  .object({ messages: messagePageSchema })
  .strict();
export const interviewDebriefsResultSchema = z
  .object({ interviewDebriefs: interviewDebriefPageSchema })
  .strict();
export const interviewDebriefResultSchema = z
  .object({ interviewDebrief: interviewDebriefSchema.nullable() })
  .strict();
