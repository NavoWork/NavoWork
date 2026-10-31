export type BusinessStatus = 'todo' | 'active' | 'waiting' | 'done';
export type Locale = 'en-US' | 'es-MX';
export interface Session {
  user: { id: string; name: string; role: 'admin' | 'member' };
  workspace: { id: string; name: string };
}
export interface Inquiry {
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
  id: string;
  inquiryId: string;
  role: 'user' | 'assistant';
  text: string;
  runId?: string;
  createdAt: string;
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
export type RequirementDetail = string | number | boolean | null | RequirementDetail[] | { [key: string]: RequirementDetail };
export interface Revision {
  parentRevision?: number;
  restoredFromRevision?: number;
  restoredNode?: string;
  generatedNode?: string;
  artifactVersionIds?: Record<string, string>;
  inquiryId: string;
  number: number;
  runId: string;
  requirements: {
    requestedProduct: string | null;
    specification: RequirementDetail;
    quantity: number | null;
    destination: string | null;
    requestedArrival: string | null;
    customization: RequirementDetail;
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
}
export interface AgentToolCall {
  id: string;
  name: string;
  label?: string;
  status: 'running' | 'succeeded' | 'failed';
  summary?: string;
  startedAt?: string;
  finishedAt?: string;
}
export interface Run {
  toolCalls?: AgentToolCall[];
  loadedSkills?: string[];
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
