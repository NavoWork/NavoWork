export type BusinessStatus = 'todo' | 'active' | 'waiting' | 'done';
export type Locale = 'en-US' | 'es-MX';
export interface Session {
  user: { id: string; name: string; role: 'admin' | 'member' };
  workspace: { id: string; name: string };
}
export interface Inquiry {
  nodeWarnings?: Record<string, { question: string; runId: string; skipped: boolean }[]>;
  demoScenarioId?: string;
  demoDataScope?: 'reference' | 'full';
  customerContext?: CustomerContext;
  id: string;
  workspaceId: string;
  title: string;
  customer: string;
  originalText: string;
  requestedLocales: Locale[];
  destination?: string;
  businessStatus: BusinessStatus;
  waiting?: { waitingFor: string; waitingReason: string; nextAction: string; followUpAt?: string };
  closeReason?: string;
  metadataVersion: number;
  currentRevision: number;
  activeRunId: string | null;
  pendingRunId?: string;
  latestRunId?: string | null;
  updatedAt: string;
  nextAction: string;
}
export interface CustomerContext {
  channel: 'unknown' | 'email' | 'website' | 'alibaba' | 'amazon' | 'linkedin' | 'referral';
  sourceRef?: string;
  email?: string;
  website?: string;
  linkedin?: string;
  company?: string;
  country?: string;
  business?: string;
  summary?: string;
  simulation?: boolean;
  checks?: { label: string; status: 'pending' | 'matched' | 'review'; detail: string }[];
}
export interface Message {
  images?: { artifactId: string; version: number; title: string; url: string; proposalUrl?: string; generationMode?: 'preset' | 'provider' }[];
  id: string;
  inquiryId: string;
  role: 'user' | 'assistant';
  text: string;
  runId?: string;
  createdAt: string;
  context?: RunContext;
}
export interface KnowledgeContext {
  sourceVersionId?: string;
  id: string;
  title: string;
  folder: string;
  content: string;
  updated: string;
}
export interface RunContext {
  skills: { id: string; name: string; instructions: string[] }[];
  knowledge: KnowledgeContext[];
}
export interface Quote {
  sku: string;
  quantity: number;
  currency: 'USD';
  unitPriceMinor: number;
  goodsSubtotalMinor: number;
  freightMinor: number | null;
  taxMinor: number | null;
  totalMinor: number | null;
  quoteStatus: 'draft';
  sourceVersionIds: string[];
  timing: {
    dispatchDays: number | null;
    productionDays?: number | null;
    startsAfter: string;
    transitDays: number | null;
    arrivalGuaranteed: boolean;
  };
}
export interface SourceRef {
  sourceVersionId: string;
  sourceId: string;
  title: string;
  version: number;
  locator: { row?: number; field?: string; section?: string };
  supports: string[];
  contentHash: string;
}
export interface Risk {
  id: string;
  severity: 'error' | 'warning' | 'info';
  category: string;
  message: string;
  suggestedAction: string;
  status: 'open' | 'read' | 'resolved';
  evidenceRefs: string[];
}
export interface Revision {
  parentRevision?: number;
  restoredFromRevision?: number;
  restoredNode?: string;
  generatedNode?: string;
  artifactVersionIds?: Record<string, string>;
  nodeArtifacts?: Record<string, WorkbenchArtifact>;
  inquiryId: string;
  number: number;
  runId: string;
  requirements: {
    requestedProduct: string | null;
    specification: string | null;
    quantity: number | null;
    destination: string | null;
    requestedArrival: string | null;
    customization: string | null;
    certificationRequests: string[];
    missingFields: string[];
    evidenceRefs: string[];
  };
  proposal: {
    proposalId: string;
    version: number;
    requestedSku: string | null;
    selectedSku: string | null;
    differences: string[];
    status: 'requested' | 'proposed' | 'accepted';
    acceptanceEvidence?: string;
  };
  quote: Quote | null;
  replies: Record<Locale, string>;
  risks: Risk[];
  checks: { label: string; status: 'passed' | 'warning' | 'error' }[];
  sourceRefs: SourceRef[];
  assetRefs: string[];
  ruleSetVersion: string;
  createdAt: string;
  changeSummary: string[];
  context?: RunContext;
}
export interface Run {
  executionMode?: 'simulation' | 'live';
  skippedQuestions?: string[];
  executionOutcome?: 'partial' | 'failed' | null;
  failedTools?: { tool: string; status: string; code?: string; summary?: string }[];
  node?: string | null;
  fileOutputs?: { file_id: string; name: string; sha256: string; downloadUrl: string }[];
  agentVerification?: { liveExecuted: boolean; mode: string } | null;
  completedPhases?: string[];
  id: string;
  runId: string;
  inquiryId: string;
  baseRevision: number;
  status: 'queued' | 'running' | 'succeeded' | 'needs_input' | 'failed' | 'cancelled';
  phase: 'understanding' | 'retrieving' | 'calculating' | 'composing' | 'validating' | 'committing';
  action: string;
  instruction: string;
  lastSeq: number;
  outputRevision?: number;
  error?: { code: string; message: string };
  clarification?: { questions: { id: string; question: string }[] };
  createdAt: string;
  context?: RunContext;
}
export interface Draft {
  inquiryId: string;
  revision: number;
  locale: Locale;
  draftVersion: number;
  text: string;
  reviewStatus: 'needs_review' | 'reviewed';
  updatedAt: string;
}
export interface Source {
  id: string;
  sourceId: string;
  title: string;
  version: number;
  kind: 'knowledge' | 'product' | 'price';
  status: 'draft' | 'published' | 'revoked';
  content: string;
  editVersion: number;
  updatedAt: string;
  locator?: string;
}
export interface Asset {
  space?: 'company' | 'personal';
  id: string;
  title: string;
  name: string;
  version: number;
  skuScope: string[];
  locale: string;
  mediaType: string;
  source: string;
  size: number;
  createdAt: string;
  url?: string;
}
export interface Capability {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  required: boolean;
  version: string;
  category: string;
}
export interface ImportPreview {
  id: string;
  status: 'preview' | 'published';
  rows: Record<string, string>[];
  errors: { row: number; field: string; message: string }[];
  validCount: number;
  totalCount: number;
}
export interface Page<T> {
  items: T[];
  nextCursor: string | null;
  matchedCount: number;
}
export interface ReviewResult {
  status: 'passed' | 'blocked';
  errors: { message: string }[];
  warnings: { message: string }[];
  revision: number;
  draftVersions: Partial<Record<Locale, number>>;
}
export interface ExportResult {
  exportId: string;
  status: 'ready' | 'pending' | 'failed';
  downloadUrl?: string;
  html?: string;
  error?: string;
}

export interface MaterialBundle {
  id: string;
  inquiryId: string;
  revision: number;
  draftVersions: Partial<Record<Locale, number>>;
  assetVersionIds: string[];
  sourceVersionIds: string[];
  status: 'draft';
  createdAt: string;
}

export type WorkbenchStageStatus = 'empty' | 'draft' | 'ready' | 'confirmed' | 'blocked' | 'locked';
export interface WorkbenchGateGap {
  code: string;
  message: string;
  stage: string;
}
export interface WorkbenchGate {
  status: 'passed' | 'blocked';
  missing: WorkbenchGateGap[];
}
export interface WorkbenchStage {
  key: string;
  title: string;
  short: string;
  status: WorkbenchStageStatus;
  summary: string;
  missing: string[];
  nextAction: string;
  artifactVersionIds: string[];
  available: boolean;
  gate?: WorkbenchGate;
}
export interface WorkbenchArtifact {
  itemId: string;
  kind: string;
  title: string;
  version: number;
  status: string;
  content: Record<string, any>;
}
export interface WorkbenchEvidence {
  id: string;
  title: string;
  sourceRole: string;
  parseStatus: string;
  blobId?: string | null;
  text: string;
  createdAt: string;
  node?: string;
}
export interface WorkbenchKnowledge {
  id: string;
  sourceId: string;
  title: string;
  version: number;
  folder?: string;
  caseId?: string;
}
export interface WorkbenchAsset {
  id: string;
  title: string;
  name: string;
  version: number;
  mediaType: string;
  size: number;
  folder?: string;
}
export interface SupplierOffer {
  id: string;
  supplier: string;
  baseCny: string;
  packagingCny: string;
  localCny: string;
  costLines?: { category: string; label: string; amountCny: string; scope: string }[];
  moq: number;
  leadDays: number;
  currency: string;
  includesPackaging: boolean;
  validUntil?: string | null;
  incoterm?: string | null;
  namedPlace?: string | null;
  paymentTerms?: string | null;
  notes?: string;
  evidenceSourceId: string;
}
export interface WorkbenchApproval {
  id: string;
  scope: string;
  targetVersionId: string;
  decision: string;
  evidenceRefs: string[];
  note?: string;
  actorId: string;
  createdAt: string;
}
export interface WorkbenchSpecField {
  key: string;
  label: string;
  required?: boolean;
  group: string;
}
export interface WorkbenchSpecGroup {
  key: string;
  title: string;
  fields: { key: string; label: string; required?: boolean }[];
}
export interface WorkbenchData {
  case: Inquiry;
  customerContext: CustomerContext;
  customerProfile: { profile?: Record<string, any>; version?: number } | null;
  stages: WorkbenchStage[];
  artifacts: Record<string, WorkbenchArtifact>;
  evidence: WorkbenchEvidence[];
  knowledge: WorkbenchKnowledge[];
  assets: WorkbenchAsset[];
  supplierOffers: SupplierOffer[];
  approvals: WorkbenchApproval[];
  gate: WorkbenchGate;
  schema: {
    specGroups: WorkbenchSpecGroup[];
    specFields: WorkbenchSpecField[];
    costCategories: { key: string; label: string }[];
    sampleChecks: string[];
    sampleTypes: string[];
  };
  nextAction: string;
}
