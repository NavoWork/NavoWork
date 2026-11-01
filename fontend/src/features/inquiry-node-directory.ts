import type { Revision, WorkbenchData } from '../api/types';
import { workflowKinds, type WorkspaceDocument } from './inquiry-canvas-model';
import { artifactText, stageDocuments } from './inquiry-stage-documents';

export interface NodeFolder {
  id: string;
  title: string;
  node?: WorkspaceDocument;
  items: { doc: WorkspaceDocument; title: string }[];
}

const contentTitles: Record<string, string> = {
  original: '客户原文', requirements: '需求数据', risks: '风险清单',
  quote: '方案与报价', reply: '回复内容', result: '成果内容',
  competitor: '对比结论', design: '产品概念图', sample: '样品记录', order: 'PO 与 PI', production: '生产资料',
};

export function nodeReferenceDocuments(data?: WorkbenchData, revision?: Revision): WorkspaceDocument[] {
  if (!data) return [];
  return [
    ...stageDocuments.flatMap((stage) => stage.artifacts.slice(1).flatMap((key) => {
      const artifact = revision?.nodeArtifacts?.[key];
      return artifact ? [{ id: `artifact:${artifact.itemId}`, kind: 'source' as const, title: artifact.title,
        folder: stage.kind, text: artifactText(artifact), caption: `V${artifact.version} · 节点原始数据`, directoryOnly: true }] : [];
    })),
    ...data.evidence.map((item) => ({
      id: `evidence:${item.id}`, title: item.title, kind: 'source' as const,
      folder: 'materials', text: item.text, caption: '询盘原件',
      evidenceId: item.id, directoryOnly: true,
    })),
    ...data.knowledge.filter((item) => item.caseId === data.case.id).map((item) => ({
      id: `source:${item.id}`, title: item.title, kind: 'source' as const,
      folder: 'materials', text: '', caption: `参考资料 · V${item.version}`,
      reference: { sourceId: item.sourceId, version: item.version }, directoryOnly: true,
    })),
  ];
}

/** Derive navigation from visible nodes, never from the flattened revision archive. */
export function nodeDirectoryFolders(
  nodes: WorkspaceDocument[], documents: WorkspaceDocument[], data?: WorkbenchData,
): NodeFolder[] {
  const byId = new Map(documents.map((doc) => [doc.id, doc]));
  const folders: NodeFolder[] = nodes.map((doc) => ({
    id: `node:${doc.kind === 'original' || workflowKinds.includes(doc.kind) ? doc.kind : doc.id}`,
    title: doc.title, node: doc,
    items: [{ doc, title: contentTitles[doc.kind] || doc.title }],
  }));
  const folderFor = (kind: string) => folders.find((folder) => folder.node?.kind === kind);
  const add = (folder: NodeFolder | undefined, id: string) => {
    const doc = byId.get(id);
    if (folder && doc && !folder.items.some((item) => item.doc.id === id))
      folder.items.push({ doc, title: doc.title });
  };
  for (const evidence of data?.evidence || []) {
    // Quotes live with the quote node once it exists; all originals remain reachable before then.
    const kind = evidence.node || (evidence.sourceRole === 'supplier_quote' ? 'quote'
      : /样品/.test(evidence.title) ? 'sample' : /订单|定金|PO|PI/.test(evidence.title) ? 'order'
      : /生产条件/.test(evidence.title) ? 'production' : /竞品/.test(evidence.title) ? 'competitor' : 'original');
    const owner = folderFor(kind);
    add(owner || folderFor('original'), `evidence:${evidence.id}`);
  }
  for (const folder of folders) {
    const node = folder.node!;
    for (const doc of documents) if (doc.directoryOnly && doc.id.startsWith('artifact:') && doc.folder === node.kind) add(folder, doc.id);
    if (['requirements', 'quote', 'risks', 'reply'].includes(node.kind)) {
      const refs = node.kind === 'requirements' ? node.revision?.requirements.evidenceRefs
        : node.kind === 'risks' ? node.revision?.risks.flatMap((risk) => risk.evidenceRefs) : [];
      for (const ref of refs || []) add(folder, `evidence:${ref}`);
      for (const ref of node.revision?.sourceRefs || []) add(folder, `source:${ref.sourceVersionId}`);
      if (node.kind === 'requirements' || node.kind === 'quote') {
        for (const reference of data?.knowledge || [])
          if (reference.caseId === data?.case.id) add(folder, `source:${reference.id}`);
      }
    }
  }
  const records = documents.filter((doc) => doc.kind === 'conversation' || doc.id === 'result:hub');
  const extraRecords = records.filter((doc) => !nodes.some((node) => node.id === doc.id));
  if (extraRecords.length) folders.push({ id: 'records', title: '沟通与成果', items: extraRecords.map((doc) => ({ doc, title: doc.title })) });
  const history = [...new Map(documents.filter((doc) => doc.kind === 'revision').map((doc) => [doc.id, doc])).values()]
    .sort((a, b) => (b.revision?.number || 0) - (a.revision?.number || 0));
  if (history.length) folders.push({ id: 'history', title: '版本记录', items: history.map((doc) => ({ doc, title: doc.title })) });
  return folders;
}

export function filterNodeFolders(folders: NodeFolder[], search: string): NodeFolder[] {
  const query = search.trim().toLowerCase();
  if (!query) return folders;
  return folders.flatMap((folder) => {
    const items = folder.title.toLowerCase().includes(query) ? folder.items : folder.items.filter(({ doc, title }) =>
      `${title} ${doc.title} ${doc.text}`.toLowerCase().includes(query));
    return items.length ? [{ ...folder, items }] : [];
  });
}
