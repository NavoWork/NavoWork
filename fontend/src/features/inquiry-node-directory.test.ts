import { describe, expect, it } from 'vitest';
import type { WorkbenchData, Revision } from '../api/types';
import type { WorkspaceDocument } from './inquiry-canvas-model';
import { filterNodeFolders, nodeDirectoryFolders, nodeReferenceDocuments } from './inquiry-node-directory';

const doc = (id: string, kind: WorkspaceDocument['kind'], title: string): WorkspaceDocument => ({
  id, kind, title, folder: 'analysis', text: '', caption: '',
});
const original = doc('original', 'original', '客户原始询盘');
const requirements = doc('requirements:4', 'requirements', '客户需求与规格');
const quote = doc('quote:4', 'quote', '方案与报价草稿');
const data = {
  case: { id: 'current' },
  evidence: [
    { id: 'email', title: '客户邮件', sourceRole: 'customer_request', text: 'A navy backpack' },
    { id: 'factory', title: '工厂报价单', sourceRole: 'supplier_quote', text: 'CNY 44' },
  ],
  knowledge: [
    { id: 'spec:v1', sourceId: 'spec', title: '参考规格', version: 1, caseId: 'current' },
    { id: 'foreign:v1', sourceId: 'foreign', title: '其他询盘规格', version: 1, caseId: 'other' },
  ],
} as WorkbenchData;

describe('node folders', () => {
  it('shows one folder per visible node and keeps old snapshots out of current content', () => {
    const old = doc('requirements:1', 'requirements', requirements.title);
    const history = { ...doc('revision:1', 'revision', 'V1 · 历史版本'), revision: { number: 1 } as Revision };
    const folders = nodeDirectoryFolders([original, requirements, quote], [original, requirements, quote, old, history, history]);
    expect(folders.map((folder) => folder.title)).toEqual(['客户原始询盘', '客户需求与规格', '方案与报价草稿', '版本记录']);
    expect(folders[1].items.map((item) => item.doc.id)).toEqual(['requirements:4']);
    expect(folders[3].items).toHaveLength(1);
  });

  it('keeps originals reachable, then groups factory files under the newly revealed quote node', () => {
    const sources = nodeReferenceDocuments(data);
    expect(sources.some((source) => source.id === 'source:foreign:v1')).toBe(false);
    expect(sources.every((source) => source.directoryOnly)).toBe(true);
    const docs = [original, requirements, quote, ...sources];
    const initial = nodeDirectoryFolders([original, requirements], docs, data);
    expect(initial[0].items.map((item) => item.doc.id)).toContain('evidence:factory');
    const progressed = nodeDirectoryFolders([original, requirements, quote], docs, data);
    expect(progressed[0].items.map((item) => item.doc.id)).not.toContain('evidence:factory');
    expect(progressed[2].items.map((item) => item.doc.id)).toContain('evidence:factory');
    expect(progressed[1].items.map((item) => item.doc.id)).toContain('source:spec:v1');
  });

  it('preserves the parent folder when searching the file name or its raw data', () => {
    const folders = nodeDirectoryFolders([original, requirements, quote], [original, requirements, quote, ...nodeReferenceDocuments(data)], data);
    const match = filterNodeFolders(folders, 'CNY 44');
    expect(match).toHaveLength(1);
    expect(match[0].title).toBe(quote.title);
    expect(match[0].items.map((item) => item.title)).toEqual(['工厂报价单']);
    expect(filterNodeFolders(folders, '客户需求与规格')[0].items).toHaveLength(2);
    expect(filterNodeFolders(folders, '不存在的内容')).toEqual([]);
  });
});
