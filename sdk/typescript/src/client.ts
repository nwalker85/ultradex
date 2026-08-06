import {
  healthStatusSchema,
  readinessStatusSchema,
  type ApplicationTransitionParameters,
  type ApplicationPage,
  type ApprovalEvidence,
  type ContractHandle,
  type EvidenceExportParameters,
  type ExecutionReceiptEvidence,
  type HealthStatus,
  type OpportunityCreateParameters,
  type OpportunityScoreParameters,
  type OpportunityPage,
  type Operation,
  type OperationLifecycleEvent,
  type OutreachApproveParameters,
  type OutreachPrepareParameters,
  type OutreachSendParameters,
  type OutreachPage,
  type ReadinessStatus,
  type RelationshipSyncParameters,
  type RelationshipPage,
  type SourcesIngestParameters,
} from "./contracts.js";
import {
  JobSearchCommandExecutor,
  type JobSearchCommandOptions,
} from "./jobsearch-commands.js";
import {
  GET_APPROVAL_QUERY,
  GET_EXECUTION_RECEIPT_QUERY,
  GET_OPERATION_EVENTS_QUERY,
  GET_OPERATION_QUERY,
  LIST_APPLICATIONS_QUERY,
  LIST_OPERATIONS_QUERY,
  LIST_OPPORTUNITIES_QUERY,
  LIST_OUTREACH_QUERY,
  LIST_RELATIONSHIPS_QUERY,
  applicationVariables,
  applicationsResultSchema,
  approvalResultSchema,
  eventVariables,
  eventsResultSchema,
  exactIdVariables,
  executionReceiptResultSchema,
  operationResultSchema,
  operationVariables,
  operationsResultSchema,
  opportunitiesResultSchema,
  opportunityVariables,
  outreachResultSchema,
  outreachVariables,
  relationshipVariables,
  relationshipsResultSchema,
  type ApplicationListInput,
  type EventPageInput,
  type OperationListInput,
  type OpportunityListInput,
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
  submitEvidenceExport(
    parameters: EvidenceExportParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle>;
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

  submitEvidenceExport(
    parameters: EvidenceExportParameters,
    options: JobSearchCommandOptions,
  ): Promise<ContractHandle> {
    return this.commandExecutor.submit(
      { commandName: "evidence.export", parameters },
      options,
    );
  }
}
