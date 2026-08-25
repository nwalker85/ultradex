import {
  healthStatusSchema,
  readinessStatusSchema,
  sendResultSchema,
  type ApplicationCreateParameters,
  type ApplicationTransitionParameters,
  type ApplicationPage,
  type ApprovalEvidence,
  type CalendarEvent,
  type CandidateProfile,
  type ComposeMessageInput,
  type Contact,
  type ContactPage,
  type ContractHandle,
  type DailyAvailability,
  type EvidenceExportParameters,
  type ExecutionReceiptEvidence,
  type HealthStatus,
  type InboundMessageContext,
  type IntentSetParameters,
  type InterviewDebrief,
  type InterviewDebriefPage,
  type Lead,
  type LeadCreateParameters,
  type LeadConvertParameters,
  type LeadPage,
  type MessagePage,
  type NextBestAction,
  type OpportunityCreateParameters,
  type OpportunityScoreParameters,
  type OpportunityPage,
  type Operation,
  type OperationLifecycleEvent,
  type Organization,
  type OrganizationCreateParameters,
  type OrganizationUpdateParameters,
  type OrganizationPage,
  type OutreachApproveParameters,
  type OutreachCancelParameters,
  type OutreachPrepareParameters,
  type OutreachSendParameters,
  type OutreachPage,
  type ReadinessStatus,
  type RecruiterPillSet,
  type RelationshipSyncParameters,
  type RelationshipPage,
  type SendResult,
  type SourcesIngestParameters,
  type WorkspaceInitializeParameters,
} from "./contracts.js";
import {
  JobSearchCommandExecutor,
  type JobSearchCommandOptions,
} from "./jobsearch-commands.js";
import {
  GENERATE_RECRUITER_REPLIES_QUERY,
  GET_APPROVAL_QUERY,
  GET_AVAILABILITY_QUERY,
  GET_CALENDAR_EVENTS_QUERY,
  GET_CONTACT_QUERY,
  GET_EXECUTION_RECEIPT_QUERY,
  GET_INTERVIEW_DEBRIEF_QUERY,
  GET_LEAD_QUERY,
  GET_NEXT_BEST_ACTIONS_QUERY,
  GET_OPERATION_EVENTS_QUERY,
  GET_OPERATION_QUERY,
  GET_ORGANIZATION_QUERY,
  GET_PROFILE_QUERY,
  LIST_APPLICATIONS_QUERY,
  LIST_CONTACTS_QUERY,
  LIST_INTERVIEW_DEBRIEFS_QUERY,
  LIST_LEADS_QUERY,
  LIST_MESSAGES_QUERY,
  LIST_OPERATIONS_QUERY,
  LIST_OPPORTUNITIES_QUERY,
  LIST_ORGANIZATIONS_QUERY,
  LIST_OUTREACH_QUERY,
  LIST_RELATIONSHIPS_QUERY,
  applicationVariables,
  applicationsResultSchema,
  approvalResultSchema,
  availabilityResultSchema,
  availabilityVariables,
  calendarEventsResultSchema,
  calendarEventsVariables,
  contactResultSchema,
  contactVariables,
  contactsResultSchema,
  eventVariables,
  eventsResultSchema,
  exactIdVariables,
  executionReceiptResultSchema,
  interviewDebriefResultSchema,
  interviewDebriefVariables,
  interviewDebriefsResultSchema,
  leadResultSchema,
  leadVariables,
  leadsResultSchema,
  messageVariables,
  messagesResultSchema,
  nextBestActionsResultSchema,
  operationResultSchema,
  operationVariables,
  operationsResultSchema,
  opportunitiesResultSchema,
  opportunityVariables,
  organizationResultSchema,
  organizationVariables,
  organizationsResultSchema,
  outreachResultSchema,
  outreachVariables,
  profileResultSchema,
  recruiterRepliesResultSchema,
  relationshipVariables,
  relationshipsResultSchema,
  type ApplicationListInput,
  type AvailabilityInput,
  type CalendarEventsInput,
  type ContactListInput,
  type EventPageInput,
  type InterviewDebriefListInput,
  type LeadListInput,
  type MessageListInput,
  type OperationListInput,
  type OpportunityListInput,
  type OrganizationListInput,
  type OutreachListInput,
  type RelationshipListInput,
} from "./jobsearch-queries.js";
import {
  UltradexRequestExecutor,
  type UltradexTransport,
} from "./transport.js";

export interface UltradexClientOptions {
  readonly baseUrl: string;
  readonly token: string;
  readonly transport: UltradexTransport;
  readonly timeoutMs?: number;
}

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
  getOperationEvents(
    operationId: string,
    input?: EventPageInput,
  ): Promise<OperationLifecycleEvent[]>;
  getApproval(approvalId: string): Promise<ApprovalEvidence | null>;
  getExecutionReceipt(
    operationId: string,
  ): Promise<ExecutionReceiptEvidence | null>;

  // Milestone M4 Read Projections
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
  getCalendarEvents(input?: CalendarEventsInput): Promise<CalendarEvent[]>;
  getMessages(input?: MessageListInput): Promise<MessagePage>;
  getInterviewDebriefs(input?: InterviewDebriefListInput): Promise<InterviewDebriefPage>;
  getInterviewDebrief(id: string): Promise<InterviewDebrief | null>;
}

export interface UltradexCommandClient {
  submitSourcesIngest(
    parameters: SourcesIngestParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
  submitOpportunityCreate(
    parameters: OpportunityCreateParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
  submitOpportunityScore(
    parameters: OpportunityScoreParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
  submitApplicationCreate(
    parameters: ApplicationCreateParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
  submitApplicationTransition(
    parameters: ApplicationTransitionParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
  submitRelationshipSync(
    parameters: RelationshipSyncParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
  submitOutreachPrepare(
    parameters: OutreachPrepareParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
  submitOutreachApprove(
    parameters: OutreachApproveParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
  submitOutreachSend(
    parameters: OutreachSendParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
  submitOutreachCancel(
    parameters: OutreachCancelParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
  submitEvidenceExport(
    parameters: EvidenceExportParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;

  // Milestone M4 Governed Command Submissions
  submitLeadCreate(
    parameters: LeadCreateParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
  submitLeadConvert(
    parameters: LeadConvertParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
  submitOrganizationCreate(
    parameters: OrganizationCreateParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
  submitOrganizationUpdate(
    parameters: OrganizationUpdateParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
  submitWorkspaceInitialize(
    parameters: WorkspaceInitializeParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
  submitIntentSet(
    parameters: IntentSetParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;

  // Milestone M4 Direct Dispatchers & Aliases
  createLead(
    parameters: LeadCreateParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
  convertLead(
    parameters: LeadConvertParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
  createOrganization(
    parameters: OrganizationCreateParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
  updateOrganization(
    parameters: OrganizationUpdateParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
  sendMessage(parameters: ComposeMessageInput): Promise<SendResult>;
  createDraft(parameters: ComposeMessageInput): Promise<SendResult>;
}

export class UltradexClient
  implements UltradexReadClient, UltradexCommandClient
{
  private readonly executor: UltradexRequestExecutor;
  private readonly commandExecutor: JobSearchCommandExecutor;

  constructor(options: UltradexClientOptions) {
    this.executor = new UltradexRequestExecutor(options);
    this.commandExecutor = new JobSearchCommandExecutor(options);
  }

  getHealth(): Promise<HealthStatus> {
    return this.executor.requestRest("/health", healthStatusSchema);
  }

  getReadiness(): Promise<ReadinessStatus> {
    return this.executor.requestRest("/health/ready", readinessStatusSchema);
  }

  async getProfile(): Promise<CandidateProfile> {
    const result = await this.executor.requestGraphQL(
      GET_PROFILE_QUERY,
      {},
      profileResultSchema,
    );
    return result.profile;
  }

  async listOpportunities(
    input: OpportunityListInput = {},
  ): Promise<OpportunityPage> {
    const result = await this.executor.requestGraphQL(
      LIST_OPPORTUNITIES_QUERY,
      opportunityVariables(input),
      opportunitiesResultSchema,
    );
    return result.opportunities;
  }

  async listApplications(
    input: ApplicationListInput = {},
  ): Promise<ApplicationPage> {
    const result = await this.executor.requestGraphQL(
      LIST_APPLICATIONS_QUERY,
      applicationVariables(input),
      applicationsResultSchema,
    );
    return result.applications;
  }

  async listRelationships(
    input: RelationshipListInput = {},
  ): Promise<RelationshipPage> {
    const result = await this.executor.requestGraphQL(
      LIST_RELATIONSHIPS_QUERY,
      relationshipVariables(input),
      relationshipsResultSchema,
    );
    return result.relationships;
  }

  async listOutreach(
    input: OutreachListInput = {},
  ): Promise<OutreachPage> {
    const result = await this.executor.requestGraphQL(
      LIST_OUTREACH_QUERY,
      outreachVariables(input),
      outreachResultSchema,
    );
    return result.outreach;
  }

  async listOperations(
    input: OperationListInput = {},
  ): Promise<Operation[]> {
    const result = await this.executor.requestGraphQL(
      LIST_OPERATIONS_QUERY,
      operationVariables(input),
      operationsResultSchema,
    );
    return result.operations;
  }

  async getOperation(operationId: string): Promise<Operation | null> {
    const result = await this.executor.requestGraphQL(
      GET_OPERATION_QUERY,
      exactIdVariables("id", operationId),
      operationResultSchema,
    );
    return result.operation;
  }

  async getOperationEvents(
    operationId: string,
    input: EventPageInput = {},
  ): Promise<OperationLifecycleEvent[]> {
    const result = await this.executor.requestGraphQL(
      GET_OPERATION_EVENTS_QUERY,
      eventVariables(operationId, input),
      eventsResultSchema,
    );
    return result.events;
  }

  async getApproval(approvalId: string): Promise<ApprovalEvidence | null> {
    const result = await this.executor.requestGraphQL(
      GET_APPROVAL_QUERY,
      exactIdVariables("id", approvalId),
      approvalResultSchema,
    );
    return result.approval;
  }

  async getExecutionReceipt(
    operationId: string,
  ): Promise<ExecutionReceiptEvidence | null> {
    const result = await this.executor.requestGraphQL(
      GET_EXECUTION_RECEIPT_QUERY,
      exactIdVariables("operationId", operationId),
      executionReceiptResultSchema,
    );
    return result.executionReceipt;
  }

  // --- Leads ---
  async getLeads(input: LeadListInput = {}): Promise<LeadPage> {
    const result = await this.executor.requestGraphQL(
      LIST_LEADS_QUERY,
      leadVariables(input),
      leadsResultSchema,
    );
    return result.leads;
  }

  async getLead(leadId: string): Promise<Lead | null> {
    const result = await this.executor.requestGraphQL(
      GET_LEAD_QUERY,
      exactIdVariables("id", leadId),
      leadResultSchema,
    );
    return result.lead;
  }

  submitLeadCreate(
    parameters: LeadCreateParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.commandExecutor.submit(
      { commandName: "leads.create", parameters },
      options,
    );
  }

  submitLeadConvert(
    parameters: LeadConvertParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.commandExecutor.submit(
      { commandName: "leads.convert", parameters },
      options,
    );
  }

  createLead(
    parameters: LeadCreateParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.submitLeadCreate(parameters, options);
  }

  convertLead(
    parameters: LeadConvertParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.submitLeadConvert(parameters, options);
  }

  // --- Organizations ---
  async getOrganizations(input: OrganizationListInput = {}): Promise<OrganizationPage> {
    const result = await this.executor.requestGraphQL(
      LIST_ORGANIZATIONS_QUERY,
      organizationVariables(input),
      organizationsResultSchema,
    );
    return result.organizations;
  }

  async getOrganization(organizationId: string): Promise<Organization | null> {
    const result = await this.executor.requestGraphQL(
      GET_ORGANIZATION_QUERY,
      exactIdVariables("id", organizationId),
      organizationResultSchema,
    );
    return result.organization;
  }

  submitOrganizationCreate(
    parameters: OrganizationCreateParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.commandExecutor.submit(
      { commandName: "organizations.create", parameters },
      options,
    );
  }

  submitOrganizationUpdate(
    parameters: OrganizationUpdateParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.commandExecutor.submit(
      { commandName: "organizations.update", parameters },
      options,
    );
  }

  createOrganization(
    parameters: OrganizationCreateParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.submitOrganizationCreate(parameters, options);
  }

  updateOrganization(
    parameters: OrganizationUpdateParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.submitOrganizationUpdate(parameters, options);
  }

  // --- Contacts ---
  async getContacts(input: ContactListInput = {}): Promise<ContactPage> {
    const result = await this.executor.requestGraphQL(
      LIST_CONTACTS_QUERY,
      contactVariables(input),
      contactsResultSchema,
    );
    return result.contacts;
  }

  async getContact(contactId: string): Promise<Contact | null> {
    const result = await this.executor.requestGraphQL(
      GET_CONTACT_QUERY,
      exactIdVariables("id", contactId),
      contactResultSchema,
    );
    return result.contact;
  }

  // --- Next Best Actions ---
  async getNextBestActions(limit = 10): Promise<NextBestAction[]> {
    const result = await this.executor.requestGraphQL(
      GET_NEXT_BEST_ACTIONS_QUERY,
      { limit },
      nextBestActionsResultSchema,
    );
    return result.nextBestActions;
  }

  // --- Recruiter Replies ---
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

  // --- Calendar & Availability ---
  async getAvailability(input: AvailabilityInput): Promise<DailyAvailability[]> {
    const result = await this.executor.requestGraphQL(
      GET_AVAILABILITY_QUERY,
      availabilityVariables(input),
      availabilityResultSchema,
    );
    return result.availability;
  }

  async getCalendarEvents(input: CalendarEventsInput = {}): Promise<CalendarEvent[]> {
    const result = await this.executor.requestGraphQL(
      GET_CALENDAR_EVENTS_QUERY,
      calendarEventsVariables(input),
      calendarEventsResultSchema,
    );
    return result.calendarEvents;
  }

  // --- Messages ---
  async getMessages(input: MessageListInput = {}): Promise<MessagePage> {
    const result = await this.executor.requestGraphQL(
      LIST_MESSAGES_QUERY,
      messageVariables(input),
      messagesResultSchema,
    );
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
    const result = await this.executor.requestGraphQL(
      LIST_INTERVIEW_DEBRIEFS_QUERY,
      interviewDebriefVariables(input),
      interviewDebriefsResultSchema,
    );
    return result.interviewDebriefs;
  }

  async getInterviewDebrief(id: string): Promise<InterviewDebrief | null> {
    const result = await this.executor.requestGraphQL(
      GET_INTERVIEW_DEBRIEF_QUERY,
      exactIdVariables("id", id),
      interviewDebriefResultSchema,
    );
    return result.interviewDebrief;
  }

  // --- Other Commands ---
  submitSourcesIngest(
    parameters: SourcesIngestParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.commandExecutor.submit(
      { commandName: "sources.ingest", parameters },
      options,
    );
  }

  submitOpportunityCreate(
    parameters: OpportunityCreateParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.commandExecutor.submit(
      { commandName: "opportunities.create", parameters },
      options,
    );
  }

  submitOpportunityScore(
    parameters: OpportunityScoreParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.commandExecutor.submit(
      { commandName: "opportunities.score", parameters },
      options,
    );
  }

  submitApplicationCreate(
    parameters: ApplicationCreateParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.commandExecutor.submit(
      { commandName: "applications.create", parameters },
      options,
    );
  }

  submitApplicationTransition(
    parameters: ApplicationTransitionParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.commandExecutor.submit(
      { commandName: "applications.transition", parameters },
      options,
    );
  }

  submitRelationshipSync(
    parameters: RelationshipSyncParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.commandExecutor.submit(
      { commandName: "relationships.sync", parameters },
      options,
    );
  }

  submitOutreachPrepare(
    parameters: OutreachPrepareParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.commandExecutor.submit(
      { commandName: "outreach.prepare", parameters },
      options,
    );
  }

  submitOutreachApprove(
    parameters: OutreachApproveParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.commandExecutor.submit(
      { commandName: "outreach.approve", parameters },
      options,
    );
  }

  submitOutreachSend(
    parameters: OutreachSendParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.commandExecutor.submit(
      { commandName: "outreach.send", parameters },
      options,
    );
  }

  submitOutreachCancel(
    parameters: OutreachCancelParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.commandExecutor.submit(
      { commandName: "outreach.cancel", parameters },
      options,
    );
  }

  submitEvidenceExport(
    parameters: EvidenceExportParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.commandExecutor.submit(
      { commandName: "evidence.export", parameters },
      options,
    );
  }

  submitWorkspaceInitialize(
    parameters: WorkspaceInitializeParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.commandExecutor.submit(
      { commandName: "workspace.initialize", parameters },
      options,
    );
  }

  submitIntentSet(
    parameters: IntentSetParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.commandExecutor.submit(
      { commandName: "intent.set", parameters },
      options,
    );
  }
}
