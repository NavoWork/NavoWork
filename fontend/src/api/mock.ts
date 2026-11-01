import { openDB, type DBSchema } from 'idb';
import Papa from 'papaparse';
import { ApiError } from './error';
import { demoSession, sampleRevision, seed } from './fixtures';
import type {
  Asset,
  BusinessStatus,
  Draft,
  ExportResult,
  ImportPreview,
  Inquiry,
  Locale,
  MaterialBundle,
  Run,
  RunContext,
} from './types';
import type { RequestOptions } from './index';
type MockFault = 'none' | 'network' | 'session' | 'forbidden' | 'draft-conflict' | 'run-failure';
let fault: MockFault = 'none';
export function setMockFault(value: MockFault) {
  fault = value;
}
interface State extends ReturnType<typeof seed> {
  draftHistory: Record<string, Draft>;
  runs: Record<string, Run & { fail?: boolean; assetVersionIds?: string[] }>;
  imports: Record<string, ImportPreview>;
  exports: Record<string, ExportResult>;
  files: Record<string, Blob>;
  idempotency: Record<string, { hash: string; response: unknown }>;
  bundles: Record<string, MaterialBundle[]>;
}
interface MockDB extends DBSchema {
  state: { key: string; value: State };
}
const database = () =>
  openDB<MockDB>('easywork-mock-v1', 1, {
    upgrade(db) {
      db.createObjectStore('state');
    },
  });
const initial = (): State => ({
  ...seed(),
  draftHistory: {},
  runs: {},
  imports: {},
  exports: {},
  files: {},
  idempotency: {},
  bundles: {},
});
const now = () => new Date().toISOString();
const fail = (
  code: string,
  message: string,
  status = 409,
  details: Record<string, unknown> = {},
): never => {
  throw new ApiError(code, message, status, crypto.randomUUID(), details);
};
const uid = (prefix: string) => `${prefix}_${crypto.randomUUID().slice(0, 8)}`;
const clone = <T>(value: T): T => structuredClone(value);
const locales: Locale[] = ['en-US', 'es-MX'];
function readOnly(i: Inquiry) {
  if (i.businessStatus === 'done') fail('INQUIRY_CLOSED', '询盘已结束，请先重新打开');
  if (i.activeRunId)
    fail('RUN_IN_PROGRESS', '当前询盘正在运行，请稍后再修改', 409, { runId: i.activeRunId });
}
function change(i: Inquiry) {
  i.metadataVersion++;
  i.updatedAt = now();
}
function reconcile(s: State) {
  for (const run of Object.values(s.runs)) {
    if (!['queued', 'running'].includes(run.status)) continue;
    const i = s.inquiries.find((v) => v.id === run.inquiryId);
    if (!i || i.activeRunId !== run.id) continue;
    const elapsed = Date.now() - Date.parse(run.createdAt);
    const phases = [
      'understanding',
      'retrieving',
      'calculating',
      'composing',
      'validating',
      'committing',
    ] as const;
    run.status = 'running';
    run.phase = phases[Math.min(5, Math.floor(elapsed / 700))];
    run.lastSeq = Math.min(7, Math.floor(elapsed / 700) + 2);
    if (elapsed < 4400) continue;
    i.activeRunId = null;
    run.lastSeq = 9;
    if (run.fail) {
      run.status = 'failed';
      run.error = {
        code: 'MODEL_TIMEOUT',
        message: '模拟模型超时，上一成功版本与草稿已保留。请重试。',
      };
      change(i);
      s.messages[i.id].push({
        id: uid('msg'),
        inquiryId: i.id,
        role: 'assistant',
        text: run.error.message,
        runId: run.id,
        createdAt: now(),
      });
      continue;
    }
    if (!['inq_mx026', 'inq_us008', 'inq_uk012'].includes(i.id)) {
      run.status = 'needs_input';
      run.clarification = {
        questions: [
          {
            id: 'mock-resource',
            question:
              '当前是固定案例 Mock，无法解析新原文。请接入真实服务完成需求理解；原文已保留。',
          },
        ],
      };
      i.nextAction = '接入真实服务或使用墨西哥示例验证生成流程';
    } else if (/900/.test(run.instruction)) {
      run.status = 'failed';
      run.error = {
        code: 'BUSINESS_VALIDATION_FAILED',
        message: '900 件超过示例库存 800 件，未生成新报价。上一成功版本已保留。',
      };
    } else {
      const previous = s.revisions[i.id]?.at(-1);
      const revision = sampleRevision(
        i.id,
        i.currentRevision + 1,
        /600/.test(run.instruction) ? 600 : 300,
      );
      if (run.action === 'accept_proposal' && previous) {
        revision.requirements = clone(previous.requirements);
        revision.proposal = {
          ...previous.proposal,
          status: 'accepted',
          acceptanceEvidence: run.instruction,
        };
        revision.quote = clone(previous.quote);
        revision.replies = clone(previous.replies);
        revision.replies['en-US'] = revision.replies['en-US'].replace(
          'Please confirm whether this alternative is acceptable.',
          'We have recorded your acceptance of this specific proposal.',
        );
        revision.replies['es-MX'] = revision.replies['es-MX'].replace(
          'Por favor confirme si acepta esta alternativa.',
          'Hemos registrado su aceptación de esta propuesta específica.',
        );
        revision.risks = previous.risks.filter((r) => r.id !== 'customization-difference');
      }
      revision.assetRefs = clone(run.assetVersionIds ?? previous?.assetRefs ?? []);
      revision.context = run.context ? clone(run.context) : undefined;
      revision.runId = run.id;
      revision.createdAt = now();
      revision.changeSummary =
        run.action === 'accept_proposal'
          ? ['记录客户对指定版本方案的明确接受依据']
          : ['根据本次指令生成示例版本，重新审校并保留未知项'];
      if (
        revision.sourceRefs.some(
          (ref) =>
            !s.sources.some(
              (source) =>
                source.sourceId === ref.sourceId &&
                source.version === ref.version &&
                source.status === 'published',
            ),
        )
      ) {
        run.status = 'failed';
        run.error = {
          code: 'BUSINESS_VALIDATION_FAILED',
          message: '本次所需资料已撤销或不可用，请重新取证后重试。',
        };
        change(i);
        s.messages[i.id].push({
          id: uid('msg'),
          inquiryId: i.id,
          role: 'assistant',
          text: run.error.message,
          runId: run.id,
          createdAt: now(),
        });
        continue;
      }
      s.revisions[i.id].push(revision);
      i.currentRevision = revision.number;
      for (const locale of locales)
        s.drafts[`${i.id}:${revision.number}:${locale}`] = {
          inquiryId: i.id,
          revision: revision.number,
          locale,
          draftVersion: 1,
          text: revision.replies[locale],
          reviewStatus: 'needs_review',
          updatedAt: now(),
        };
      run.status = 'succeeded';
      run.outputRevision = revision.number;
      i.nextAction = '核对报价与双语回复，确认待处理事项';
    }
    change(i);
    s.messages[i.id].push({
      id: uid('msg'),
      inquiryId: i.id,
      role: 'assistant',
      text:
        run.status === 'succeeded'
          ? `V${run.outputRevision} 已生成。请核对报价、回复与待确认项。`
          : run.clarification?.questions[0]?.question || run.error?.message || '',
      runId: run.id,
      createdAt: now(),
    });
  }
}
function validateRunContext(value: unknown): RunContext | undefined {
  if (value === undefined) return undefined;
  const record = (item: unknown): item is Record<string, unknown> =>
    typeof item === 'object' && item !== null && !Array.isArray(item);
  const text = (item: unknown): item is string => typeof item === 'string' && !!item.trim();
  if (
    !record(value) ||
    !Array.isArray(value.skills) ||
    !Array.isArray(value.knowledge) ||
    value.skills.some(
      (skill) =>
        !record(skill) ||
        !text(skill.id) ||
        !text(skill.name) ||
        !Array.isArray(skill.instructions) ||
        !skill.instructions.length ||
        !skill.instructions.every(text),
    ) ||
    value.knowledge.some(
      (doc) =>
        !record(doc) ||
        !['id', 'title', 'folder', 'content', 'updated'].every((key) => text(doc[key])),
    )
  )
    fail('INVALID_INPUT', '技能或知识库引用不完整，请重新选择后提交', 400);
  const context = value as RunContext;
  if (
    new Set(context.skills.map((skill) => skill.id)).size !== context.skills.length ||
    new Set(context.knowledge.map((doc) => doc.id)).size !== context.knowledge.length
  )
    fail('INVALID_INPUT', '同一技能或知识文档不能重复引用', 400);
  return clone(context);
}
function validateAssets(s: State, refs: unknown, sku: string | null): string[] {
  if (!Array.isArray(refs) || refs.some((ref) => typeof ref !== 'string'))
    fail('INVALID_INPUT', '素材引用必须为固定版本标识数组', 400);
  const result: string[] = [];
  for (const ref of refs as string[]) {
    const asset = s.assets.find(
      (a) => `${a.id}:v${a.version}` === ref || `${a.id}:${a.version}` === ref,
    );
    if (!asset) fail('NOT_FOUND', '引用素材不存在或无权访问', 404);
    if (asset!.skuScope.length && (!sku || !asset!.skuScope.includes(sku)))
      fail(
        'BUSINESS_VALIDATION_FAILED',
        `素材「${asset!.title}」适用 SKU 与当前方案不匹配，请选择正确素材`,
        422,
      );
    result.push(`${asset!.id}:v${asset!.version}`);
  }
  return [...new Set(result)];
}
function validateDrafts(
  s: State,
  i: Inquiry,
  revision: number,
  versions: Partial<Record<Locale, number>>,
) {
  const r = s.revisions[i.id]?.find((x) => x.number === revision);
  if (!r) fail('NOT_FOUND', '未找到指定版本', 404);
  const selected = locales.map((locale) => {
    const current = s.drafts[`${i.id}:${revision}:${locale}`];
    return current?.draftVersion === versions[locale]
      ? current
      : s.draftHistory[`${i.id}:${revision}:${locale}:${versions[locale]}`];
  });
  if (selected.some((d) => !d))
    fail('DRAFT_CONFLICT', '指定草稿版本不可用，请保存并刷新后重试', 409);
  const errors: { message: string }[] = [];
  for (const ref of r!.sourceRefs) {
    const source = s.sources.find((v) => v.sourceId === ref.sourceId && v.version === ref.version);
    if (!source || source.status === 'revoked')
      errors.push({ message: `关键依据 ${ref.title} 已撤销或不可用，请重新取证` });
  }
  const expected = r!.quote ? (r!.quote.goodsSubtotalMinor / 100).toFixed(2) : null;
  for (const d of selected) {
    if (d.text.trim().length < 10)
      errors.push({ message: `${d.locale} 回复内容过短，请补充完整材料` });
    if (expected && !d.text.includes(expected))
      errors.push({ message: `${d.locale} 商品小计与报价不一致，预期 USD ${expected}` });
    if (
      /guarantee(?:d)?\s+(?:delivery|arrival)|certified|保证.*到货|garantizamos.*llegada/i.test(
        d.text,
      )
    )
      errors.push({ message: `${d.locale} 包含未证实的到货或认证承诺` });
  }
  return {
    r: r!,
    selected,
    result: {
      status: errors.length ? ('blocked' as const) : ('passed' as const),
      errors,
      warnings: r!.risks
        .filter((x) => x.severity === 'warning')
        .map((x) => ({ message: x.message })),
      revision,
      draftVersions: versions,
    },
  };
}
const escape = (s: unknown) =>
  String(s ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!,
  );
function previewCsv(text: string): ImportPreview {
  const parsed = Papa.parse<Record<string, string>>(text, {
    header: true,
    skipEmptyLines: true,
    transformHeader: (h) => h.trim(),
  });
  const rows = parsed.data;
  const errors: ImportPreview['errors'] = parsed.errors.map((e) => ({
    row: (e.row ?? 0) + 2,
    field: 'csv',
    message: e.message,
  }));
  const required = [
    'sku',
    'name',
    'specification',
    'moq',
    'stock',
    'stockObservedAt',
    'minQuantity',
    'maxQuantity',
    'unitPriceMinor',
    'currency',
    'productionDays',
    'dispatchDays',
    'startsAfter',
    'source',
  ];
  for (const field of required)
    if (!parsed.meta.fields?.includes(field))
      errors.push({ row: 1, field, message: `缺少 ${field} 列` });
  if (rows.length > 1000)
    errors.push({ row: 1002, field: 'csv', message: 'CSV 最多允许 1,000 行' });
  const tiers = new Map<string, { min: number; max: number; signature: string }[]>();
  rows.forEach((r, n) => {
    const err = (field: string, message: string) => errors.push({ row: n + 2, field, message });
    for (const field of ['sku', 'name', 'specification', 'startsAfter', 'source'])
      if (!r[field]?.trim()) err(field, '必填字段不能为空');
    for (const field of ['moq', 'minQuantity', 'unitPriceMinor'])
      if (!/^\d+$/.test(r[field] || '') || Number(r[field]) < 1) err(field, '必须为正整数');
    for (const field of ['stock', 'maxQuantity', 'productionDays', 'dispatchDays'])
      if (r[field] && !/^\d+$/.test(r[field]) && r[field] !== 'unknown')
        err(field, '必须为非负整数、unknown 或留空');
    if (r.currency !== 'USD') err('currency', '本期仅支持 USD');
    if (
      r.stock &&
      r.stock !== 'unknown' &&
      (!r.stockObservedAt || Number.isNaN(Date.parse(r.stockObservedAt)))
    )
      err('stockObservedAt', '已知库存必须提供有效记录时间');
    const min = Number(r.minQuantity),
      max = r.maxQuantity && r.maxQuantity !== 'unknown' ? Number(r.maxQuantity) : Infinity;
    if (min > max) err('maxQuantity', '价阶结束数量不能小于起始数量');
    const signature = JSON.stringify(
      [
        'name',
        'specification',
        'moq',
        'stock',
        'stockObservedAt',
        'productionDays',
        'dispatchDays',
        'startsAfter',
        'source',
      ].map((k) => r[k]),
    );
    const previous = tiers.get(r.sku) || [];
    if (previous.some((t) => t.min <= max && min <= t.max))
      err('minQuantity', '同 SKU 价阶重叠或重复');
    if (previous.some((t) => t.signature !== signature)) err('sku', '同 SKU 商品元信息不一致');
    previous.push({ min, max, signature });
    tiers.set(r.sku, previous);
  });
  if (!rows.length) errors.push({ row: 1, field: 'csv', message: '文件中没有商品行' });
  return {
    id: uid('import'),
    status: 'preview',
    rows,
    errors,
    totalCount: rows.length,
    validCount: rows.filter((_, n) => !errors.some((e) => e.row === n + 2 || e.row === 1)).length,
  };
}
function route(
  s: State,
  path: string,
  method: string,
  b: Record<string, any>,
  form: FormData | null,
  fileText: string,
): unknown {
  const u = new URL(path, 'http://mock.local');
  const p = u.pathname.split('/').filter(Boolean);
  const query = u.searchParams;
  if (path === '/auth/session' && method === 'POST') {
    s.session = clone(demoSession);
    s.session.user.name = String(b.name || b.email || 'Alex')
      .split('@')[0]
      .slice(0, 60);
    if (b.role === 'member') s.session.user.role = 'member';
    return s.session;
  }
  if (path === '/auth/session' && method === 'DELETE') {
    s.session = null;
    return {};
  }
  if (!s.session) fail('SESSION_EXPIRED', '请登录后继续', 401);
  if (p[0] === 'me') return s.session;
  if (p[0] !== 'workspaces' || p[1] !== s.session!.workspace.id)
    fail('NOT_FOUND', '未找到可访问的工作空间', 404);
  const admin = () => {
    if (s.session?.user.role !== 'admin') fail('FORBIDDEN', '此操作仅管理员可执行', 403);
  };
  const group = p[2],
    id = p[3],
    action = p[4];
  if (group === 'inquiries') {
    if (id === 'summary')
      return s.inquiries.reduce(
        (a, i) => {
          a[i.businessStatus]++;
          return a;
        },
        { todo: 0, active: 0, waiting: 0, done: 0 },
      );
    if (!id && method === 'GET') {
      const status = query.get('status'),
        q = (query.get('q') || '').toLowerCase(),
        offset = Math.max(0, Number(query.get('cursor') || 0)),
        limit = Math.min(100, Math.max(1, Number(query.get('limit') || 20)));
      const all = s.inquiries
        .filter(
          (i) =>
            (!status || status === 'all' || i.businessStatus === status) &&
            `${i.title} ${i.customer} ${i.id}`.toLowerCase().includes(q),
        )
        .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt) || b.id.localeCompare(a.id));
      return {
        items: all.slice(offset, offset + limit),
        matchedCount: all.length,
        nextCursor: offset + limit < all.length ? String(offset + limit) : null,
      };
    }
    if (!id && method === 'POST') {
      for (const [key, max] of [
        ['title', 80],
        ['customer', 120],
        ['originalText', 20000],
      ] as const)
        if (typeof b[key] !== 'string' || !b[key].trim() || b[key].length > max)
          throw new ApiError('INVALID_INPUT', `请填写有效的 ${key}`, 400, undefined, {}, [
            { field: key, message: `必填，最多 ${max} 字符` },
          ]);
      const i: Inquiry = {
        id: uid('inq'),
        workspaceId: s.session!.workspace.id,
        title: b.title.trim(),
        customer: b.customer.trim(),
        originalText: b.originalText.trim(),
        requestedLocales: b.requestedLocales || locales,
        destination: b.destination,
        businessStatus: 'todo',
        metadataVersion: 1,
        currentRevision: 0,
        activeRunId: null,
        nextAction: '读懂客户原文，确认需求与缺项',
        updatedAt: now(),
      };
      s.inquiries.push(i);
      s.revisions[i.id] = [];
      s.messages[i.id] = [
        { id: uid('msg'), inquiryId: i.id, role: 'user', text: i.originalText, createdAt: now() },
      ];
      return i;
    }
    const i = s.inquiries.find((v) => v.id === id);
    if (!i) fail('NOT_FOUND', '询盘不存在或无权查看', 404);
    if (!action && method === 'GET') return { ...i!, latestRunId: i!.latestRunId || Object.values(s.runs).filter(run => run.inquiryId === id).at(-1)?.id || null };
    if (!action && method === 'PATCH') {
      readOnly(i!);
      if (b.metadataVersion !== i!.metadataVersion)
        fail('METADATA_CONFLICT', '询盘信息已有更新，请刷新后重试', 409, {
          metadataVersion: i!.metadataVersion,
        });
      for (const key of ['title', 'customer'] as const)
        if (typeof b[key] === 'string' && b[key].trim()) i![key] = b[key].trim();
      if (b.originalText !== undefined) {
        if (i!.currentRevision || s.messages[id].some((x) => x.runId))
          fail('INVALID_INPUT', '首次处理后原文留档，请追加反馈', 400);
        i!.originalText = b.originalText;
      }
      change(i!);
      return i;
    }
    if (action === 'status-transitions' && method === 'POST') {
      if (i!.activeRunId) fail('RUN_IN_PROGRESS', '请先取消或等待本询盘运行完成');
      if (b.metadataVersion !== i!.metadataVersion || b.from !== i!.businessStatus)
        fail('METADATA_CONFLICT', '询盘状态已有更新，请刷新后重试', 409, { current: i });
      const allowed: Record<BusinessStatus, BusinessStatus[]> = {
        todo: ['active', 'done'],
        active: ['waiting', 'done'],
        waiting: ['active', 'done'],
        done: ['active'],
      };
      if (!allowed[i!.businessStatus].includes(b.to))
        fail('INVALID_STATUS_TRANSITION', '不允许此状态转换');
      if (
        b.to === 'waiting' &&
        (!b.waiting?.waitingFor ||
          !b.waiting?.waitingReason?.trim() ||
          !b.waiting?.nextAction?.trim())
      )
        fail('INVALID_INPUT', '请填写等待对象、等待事项和下一步', 400);
      if (b.to === 'done' && !b.closeReason?.trim()) fail('INVALID_INPUT', '请选择结束原因', 400);
      i!.businessStatus = b.to;
      i!.waiting = b.to === 'waiting' ? b.waiting : undefined;
      i!.closeReason = b.to === 'done' ? b.closeReason : undefined;
      i!.nextAction =
        b.to === 'waiting'
          ? b.waiting.nextAction
          : b.to === 'done'
            ? '已结束，可查看历史与导出草稿材料'
            : '继续处理当前询盘';
      change(i!);
      return i;
    }
    if (action === 'messages') {
      if (method === 'GET') {
        return { items: s.messages[id] || [] };
      }
      readOnly(i!);
      if (!b.text?.trim()) fail('INVALID_INPUT', '消息不能为空', 400);
      const message = {
        id: uid('msg'),
        inquiryId: id,
        role: 'user' as const,
        text: b.text,
        createdAt: now(),
      };
      s.messages[id].push(message);
      change(i!);
      return message;
    }
    if (action === 'runs' && method === 'POST') {
      readOnly(i!);
      if (i!.businessStatus === 'waiting') fail('INVALID_STATUS_TRANSITION', '请先恢复处理');
      if (b.baseRevision !== i!.currentRevision)
        fail('REVISION_CONFLICT', '询盘已有新版本，请查看后重新提交', 409, {
          currentRevision: i!.currentRevision,
        });
      if (s.capabilities.some((c) => c.required && !c.enabled))
        fail('TOOL_UNAVAILABLE', '必需能力已停用，请联系管理员启用后重试', 503);
      if (!['analyze', 'revise', 'accept_proposal'].includes(b.action))
        fail('INVALID_INPUT', '未知运行动作', 400);
      const context = validateRunContext(b.context);
      if (b.action === 'accept_proposal') {
        const previous = s.revisions[id].at(-1);
        const evidence =
          typeof b.acceptanceEvidence === 'string'
            ? b.acceptanceEvidence
            : b.acceptanceEvidence?.text;
        if (
          !b.proposalRef ||
          !evidence?.trim() ||
          /是否|尚未|不接受|请客户|not accept|\?/i.test(evidence)
        )
          fail('INVALID_INPUT', '请提供客户明确接受此方案的反馈依据', 400);
        const pid = typeof b.proposalRef === 'string' ? b.proposalRef : b.proposalRef.proposalId;
        if (
          pid !== previous?.proposal.proposalId ||
          (typeof b.proposalRef === 'object' &&
            b.proposalRef.version !== previous?.proposal.version)
        )
          fail('REVISION_CONFLICT', '所确认方案不属于当前版本');
      }
      const assetVersionIds = validateAssets(
        s,
        b.assetVersionIds ?? s.revisions[id].at(-1)?.assetRefs ?? [],
        s.revisions[id].at(-1)?.proposal.selectedSku ?? null,
      );
      const run: State['runs'][string] = {
        id: uid('run'),
        runId: '',
        inquiryId: id,
        baseRevision: b.baseRevision,
        status: 'queued',
        phase: 'understanding',
        action: b.action,
        instruction: b.instruction || b.acceptanceEvidence || '',
        lastSeq: 1,
        createdAt: now(),
        fail: fault === 'run-failure',
        assetVersionIds,
        context,
      };
      run.runId = run.id;
      if (run.fail) fault = 'none';
      s.runs[run.id] = run;
      i!.activeRunId = run.id;
      i!.latestRunId = run.id;
      i!.businessStatus = 'active';
      change(i!);
      s.messages[id].push({
        id: uid('msg'),
        inquiryId: id,
        role: 'user',
        text: String(b.instruction || '开始处理此询盘'),
        context: context ? clone(context) : undefined,
        runId: run.id,
        createdAt: now(),
      });
      return run;
    }
    if (action === 'revisions') {
      const rev = Number(p[5]);
      if (!p[5]) return { items: s.revisions[id] };
      const r = s.revisions[id].find((v) => v.number === rev);
      if (!r) fail('NOT_FOUND', '版本不存在', 404);
      if (!p[6]) return r;
      if (p[6] === 'reply-drafts') {
        const locale = (p[7] || query.get('locale')) as Locale | null;
        if (method === 'GET') {
          if (locale) {
            const draft = s.drafts[`${id}:${rev}:${locale}`];
            if (!draft) fail('NOT_FOUND', '草稿不存在', 404);
            if (query.has('draftVersion')) {
              const version = Number(query.get('draftVersion'));
              if (version !== draft!.draftVersion) {
                const historical = s.draftHistory[`${id}:${rev}:${locale}:${version}`];
                if (!historical) fail('NOT_FOUND', '草稿版本不存在', 404);
                return historical;
              }
            }
            return draft;
          }
          return { items: locales.map((l) => s.drafts[`${id}:${rev}:${l}`]) };
        }
        readOnly(i!);
        if (rev !== i!.currentRevision) fail('REVISION_CONFLICT', '历史版本只读，请回到当前版本');
        if (!locales.includes(locale!)) fail('INVALID_INPUT', '不支持此语言', 400);
        const draft = s.drafts[`${id}:${rev}:${locale}`];
        if (fault === 'draft-conflict') {
          fault = 'none';
          draft.draftVersion++;
          draft.text += '\n\n[其他编辑者的模拟修改]';
          draft.reviewStatus = 'needs_review';
        }
        if (b.baseDraftVersion !== draft.draftVersion)
          fail(
            'DRAFT_CONFLICT',
            '此草稿已被其他编辑者修改。你的文字已保留，请比较后再保存。',
            409,
            {
              currentDraft: clone(draft),
              latestDraft: clone(draft),
              draftVersion: draft.draftVersion,
              text: draft.text,
            },
          );
        if (typeof b.text !== 'string' || b.text.length > 50000)
          fail('INVALID_INPUT', '草稿内容无效或超过 50,000 字符', 400);
        if (b.text !== draft.text) {
          draft.draftVersion++;
          draft.text = b.text;
          draft.reviewStatus = 'needs_review';
          draft.updatedAt = now();
        }
        return draft;
      }
    }
    if (action === 'reviews' && method === 'POST') {
      const { selected, result } = validateDrafts(s, i!, b.revision, b.draftVersions || {});
      if (
        i!.businessStatus !== 'done' &&
        b.revision === i!.currentRevision &&
        !i!.activeRunId &&
        result.status === 'passed'
      )
        selected.forEach((d) => {
          const current = s.drafts[`${i!.id}:${d.revision}:${d.locale}`];
          if (current?.draftVersion === d.draftVersion) current.reviewStatus = 'reviewed';
        });
      return result;
    }
    if (action === 'exports' && method === 'POST') {
      let manifest = b;
      if (b.bundleId) {
        if (b.revision || b.draftVersions || b.assetVersionIds)
          fail('INVALID_INPUT', '材料清单与显式版本参数不能混用', 400);
        const found = s.bundles[id]?.find((v) => v.id === b.bundleId);
        if (!found) fail('NOT_FOUND', '材料清单不存在', 404);
        manifest = found!;
      }
      const { r, selected, result } = validateDrafts(
        s,
        i!,
        manifest.revision,
        manifest.draftVersions || {},
      );
      const assetRefs = validateAssets(
        s,
        manifest.assetVersionIds ?? r.assetRefs,
        r.proposal.selectedSku,
      );
      if (result.errors.length)
        fail('REVIEW_BLOCKED', result.errors.map((x) => x.message).join('；'), 422, {
          errors: result.errors,
        });
      const html = `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>${escape(i!.title)} · 草稿材料</title><style>body{font:16px sans-serif;max-width:860px;margin:48px auto;line-height:1.8;padding:24px}pre{white-space:pre-wrap}small{color:#666}</style><h1>${escape(i!.title)}</h1><p>Mock 合成测试草稿 · 不可对客使用 · 未发送</p><p>客户：${escape(i!.customer)} · V${r.number} · ${escape(now())}</p><h2>报价</h2><p>${r.quote ? `${escape(r.quote.quantity)} 件 / ${escape(r.quote.sku)} / USD ${escape((r.quote.goodsSubtotalMinor / 100).toFixed(2))} 商品小计` : '没有可用报价'}</p><p>运费、税费、最终总额、运输时效待确认。</p>${selected.map((d) => `<h2>${escape(d.locale)} · 草稿 ${d.draftVersion}</h2><pre>${escape(d.text)}</pre>`).join('')}<h2>待确认事项</h2><ul>${r.risks.map((x) => `<li>${escape(x.message)}</li>`).join('')}</ul><h2>引用素材</h2><ul>${assetRefs.map((ref) => `<li>${escape(ref)}</li>`).join('')}</ul><h2>来源</h2><ul>${r.sourceRefs.map((x) => `<li>${escape(x.title)} · ${escape(x.sourceVersionId)}</li>`).join('')}</ul></html>`;
      const output: ExportResult = { exportId: uid('export'), status: 'ready', html };
      s.exports[output.exportId] = output;
      return output;
    }
    if (action === 'material-bundles') {
      if (method === 'GET') return { items: s.bundles[id] || [] };
      readOnly(i!);
      const { r, result } = validateDrafts(s, i!, b.revision, b.draftVersions || {});
      if (result.errors.length)
        fail('REVIEW_BLOCKED', result.errors.map((x) => x.message).join('；'), 422, {
          errors: result.errors,
        });
      const assetVersionIds = validateAssets(
        s,
        b.assetVersionIds ?? r.assetRefs,
        r.proposal.selectedSku,
      );
      const bundle: MaterialBundle = {
        id: uid('bundle'),
        inquiryId: id,
        revision: r.number,
        draftVersions: clone(b.draftVersions),
        assetVersionIds,
        sourceVersionIds: r.sourceRefs.map((ref) => ref.sourceVersionId),
        status: 'draft',
        createdAt: now(),
      };
      (s.bundles[id] ??= []).push(bundle);
      return bundle;
    }
  }
  if (group === 'runs') {
    const run = s.runs[id];
    if (!run) fail('NOT_FOUND', '运行记录不存在', 404);
    if (action === 'cancel' && method === 'POST') {
      if (['queued', 'running'].includes(run.status)) {
        run.status = 'cancelled';
        run.lastSeq++;
        const i = s.inquiries.find((v) => v.id === run.inquiryId)!;
        i.activeRunId = null;
        change(i);
      }
      return run;
    }
    if (action === 'events')
      return {
        items: [
          {
            runId: run.id,
            inquiryId: run.inquiryId,
            seq: run.lastSeq,
            type: `run.${run.status}`,
            payload: { phase: run.phase },
            createdAt: now(),
          },
        ].filter((e) => e.seq > Number(query.get('after') || 0)),
      };
    return run;
  }
  if (group === 'exports') {
    const item = s.exports[id];
    if (!item) fail('NOT_FOUND', '导出记录不存在', 404);
    if (action === 'download') return new Blob([item.html || ''], { type: 'text/html' });
    return item;
  }
  if (group === 'knowledge' || group === 'products' || group === 'sources') {
    if (!id && method === 'GET')
      return {
        items: s.sources.filter((v) =>
          group === 'knowledge' ? v.kind === 'knowledge' : v.kind !== 'knowledge',
        ),
      };
    if (group === 'knowledge' && !id && method === 'POST') {
      if (!b.title?.trim() || !b.content?.trim() || b.content.length > 50000)
        fail('INVALID_INPUT', '请填写标题和正文，正文最多 50,000 字符', 400);
      const sid = uid('knowledge');
      const source = {
        id: sid,
        sourceId: sid,
        title: b.title,
        content: b.content,
        kind: 'knowledge' as const,
        status: 'draft' as const,
        version: 1,
        editVersion: 1,
        updatedAt: now(),
      };
      s.sources.push(source);
      return source;
    }
    if (action === 'versions') {
      const version = Number(p[5]);
      if (!p[5] && method === 'POST') {
        const previous = s.sources
          .filter((v) => v.id === id)
          .sort((a, b) => b.version - a.version)[0];
        if (!previous) fail('NOT_FOUND', '资料不存在', 404);
        const next = {
          ...previous,
          version: previous.version + 1,
          status: 'draft' as const,
          editVersion: 1,
          content: b.content ?? previous.content,
          title: b.title ?? previous.title,
          updatedAt: now(),
        };
        s.sources.push(next);
        return next;
      }
      const source = s.sources.find((v) => v.id === id && v.version === version);
      if (!source) fail('NOT_FOUND', '资料版本不存在', 404);
      if (method === 'GET') return source;
      if (b.editVersion !== source!.editVersion && p[6] !== 'revoke')
        fail('METADATA_CONFLICT', '资料已被修改，请刷新后比较', 409, { current: source });
      if (p[6] === 'publish') {
        admin();
        if (source!.status !== 'draft') fail('INVALID_INPUT', '只能发布草稿', 400);
        source!.status = 'published';
        source!.editVersion++;
        return source;
      }
      if (p[6] === 'revoke') {
        admin();
        if (!b.reason?.trim()) fail('INVALID_INPUT', '请填写撤销原因', 400);
        source!.status = 'revoked';
        return source;
      }
      if (source!.status !== 'draft')
        fail('INVALID_INPUT', '已发布资料不可修改，请创建新版本', 400);
      if (typeof b.content === 'string') {
        if (b.content.length > 50000) fail('INVALID_INPUT', '正文超过 50,000 字符', 400);
        source!.content = b.content;
      }
      if (b.title) source!.title = b.title;
      source!.editVersion++;
      source!.updatedAt = now();
      return source;
    }
  }
  if (group === 'product-imports') {
    if (!id && method === 'POST') {
      const file = form?.get('file');
      if (!(file instanceof Blob) || file.size > 5 * 1024 * 1024)
        fail('INVALID_INPUT', '请上传不超过 5MB 的 CSV 文件', 400);
      const preview = previewCsv(fileText);
      s.imports[preview.id] = preview;
      return preview;
    }
    const preview = s.imports[id];
    if (!preview) fail('NOT_FOUND', '导入记录不存在', 404);
    if (action === 'publish' && method === 'POST') {
      admin();
      if (preview.errors.length)
        fail('BUSINESS_VALIDATION_FAILED', '导入存在错误，请修正后重新上传', 422);
      if (preview.status === 'published') return preview;
      for (const sku of new Set(preview.rows.map((r) => r.sku))) {
        const rows = preview.rows.filter((r) => r.sku === sku);
        const sid = `product-${sku}`;
        s.sources.push({
          id: sid,
          sourceId: sid,
          title: rows[0].name,
          kind: 'product',
          status: 'published',
          version: Math.max(0, ...s.sources.filter((x) => x.id === sid).map((x) => x.version)) + 1,
          editVersion: 1,
          content: JSON.stringify(rows, null, 2),
          updatedAt: now(),
        });
      }
      preview.status = 'published';
      return preview;
    }
    return preview;
  }
  if (group === 'assets') {
    if (!id && method === 'GET') return { items: s.assets };
    if ((!id || action === 'versions') && method === 'POST') {
      const value = form?.get('file');
      if (!(value instanceof Blob)) fail('INVALID_INPUT', '请选择文件', 400);
      const file = value as Blob;
      if (
        file!.size > 20 * 1024 * 1024 ||
        !['image/jpeg', 'image/png', 'image/webp', 'application/pdf'].includes(file!.type)
      )
        fail('INVALID_INPUT', '仅支持不超过 20MB 的 JPEG、PNG、WebP 或 PDF', 400);
      if (file instanceof File && !/\.(jpe?g|png|webp|pdf)$/i.test(file.name))
        fail('INVALID_INPUT', '扩展名与允许类型不匹配', 400);
      const get = (key: string) => String(form?.get(key) || '');
      const aid = id || uid('asset');
      const previous = s.assets.filter((a) => a.id === aid);
      const rawSku = get('skuScope');
      let skuScope: string[];
      try {
        const parsed = JSON.parse(rawSku);
        skuScope = Array.isArray(parsed) ? parsed : rawSku.split(',');
      } catch {
        skuScope = rawSku.split(',');
      }
      const asset: Asset = {
        id: aid,
        title: get('title') || get('name') || (file as File).name,
        name: get('name') || (file as File).name,
        version: Math.max(0, ...previous.map((x) => x.version)) + 1,
        skuScope: skuScope.map((x) => x.trim()).filter(Boolean),
        locale: get('locale') || 'zh-CN',
        source: get('source') || '用户上传',
        mediaType: file!.type,
        size: file!.size,
        createdAt: now(),
      };
      s.assets.push(asset);
      s.files[`${aid}:${asset.version}`] = file!;
      return asset;
    }
    if (action === 'versions' && p[6] === 'download') {
      const asset = s.assets.find((a) => a.id === id && a.version === Number(p[5]));
      if (!asset) fail('NOT_FOUND', '素材不存在', 404);
      const file = s.files[`${id}:${p[5]}`];
      if (!file) fail('NOT_FOUND', '示例素材仅有元信息，请上传自己的文件验证预览与下载', 404);
      return file;
    }
  }
  if (group === 'capabilities') {
    if (!id) return { items: s.capabilities };
    admin();
    const c = s.capabilities.find((v) => v.id === id);
    if (!c) fail('NOT_FOUND', '能力不存在', 404);
    if (typeof b.enabled === 'boolean') c!.enabled = b.enabled;
    return c;
  }
  return fail('NOT_FOUND', `此接口未实现：${method} ${u.pathname}`, 404);
}
export async function mockRequest(path: string, options: RequestOptions = {}): Promise<unknown> {
  const delay = import.meta.env.MODE === 'test' ? 0 : 180;
  await new Promise<void>((resolve, reject) => {
    if (options.signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'));
      return;
    }
    const timer = setTimeout(resolve, delay);
    options.signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timer);
        reject(new DOMException('Aborted', 'AbortError'));
      },
      { once: true },
    );
  });
  if (options.signal?.aborted) throw new DOMException('Aborted', 'AbortError');
  if (fault === 'network') fail('NETWORK_ERROR', '模拟断线：请恢复连接后重试，输入已保留。', 0);
  if (fault === 'session' && path !== '/auth/session') {
    window.dispatchEvent(new CustomEvent('easywork:session-expired'));
    fail('SESSION_EXPIRED', '会话已过期，请重新登录', 401);
  }
  if (fault === 'forbidden' && path !== '/me' && path !== '/auth/session')
    fail('FORBIDDEN', '模拟无访问权限', 403);
  if (path === '/auth/session' && options.method === 'POST' && fault === 'session') fault = 'none';
  const form = options.body instanceof FormData ? options.body : null;
  const file = form?.get('file');
  const fileText =
    path.includes('product-imports') && file instanceof Blob ? await file.text() : '';
  if (path.includes('/assets') && file instanceof Blob) {
    const header = new Uint8Array(await file.slice(0, 12).arrayBuffer());
    const signatures: Record<string, boolean> = {
      'image/jpeg': header[0] === 255 && header[1] === 216 && header[2] === 255,
      'image/png': header[0] === 137 && header[1] === 80 && header[2] === 78 && header[3] === 71,
      'image/webp':
        String.fromCharCode(...header.slice(0, 4)) === 'RIFF' &&
        String.fromCharCode(...header.slice(8, 12)) === 'WEBP',
      'application/pdf': String.fromCharCode(...header.slice(0, 5)) === '%PDF-',
    };
    if (!signatures[file.type])
      fail('INVALID_INPUT', '文件内容与声明的类型不匹配，请选择有效的图片或 PDF', 400);
  }

  const db = await database();
  const tx = db.transaction('state', 'readwrite');
  const s = (await tx.store.get('main')) || initial();
  s.draftHistory ??= {};
  for (const [key, draft] of Object.entries(s.drafts))
    s.draftHistory[`${key}:${draft.draftVersion}`] ??= clone(draft);
  reconcile(s);
  const method = options.method || 'GET';
  const b = (form ? {} : options.body || {}) as Record<string, any>;
  const key = options.idempotencyKey
    ? `${s.session?.user.id || 'guest'}:${method}:${path}:${options.idempotencyKey}`
    : null;
  const hash = JSON.stringify(
    options.body instanceof FormData
      ? [...options.body.entries()].map(([k, v]) => [
          k,
          v instanceof File ? { name: v.name, size: v.size, type: v.type } : v,
        ])
      : options.body || {},
  );
  try {
    if (key && s.idempotency[key]) {
      if (s.idempotency[key].hash !== hash)
        fail('IDEMPOTENCY_CONFLICT', '同一请求标识对应不同内容，请重新发起');
      const response = clone(s.idempotency[key].response);
      await tx.store.put(s, 'main');
      await tx.done;
      return response;
    }
    const result = route(s, path, method, b, form, fileText);
    if (key) s.idempotency[key] = { hash, response: clone(result) };
    await tx.store.put(s, 'main');
    await tx.done;
    return clone(result);
  } catch (error) {
    await tx.store.put(s, 'main');
    await tx.done;
    throw error;
  } finally {
    db.close();
  }
}
/** Isolated test helper. Never called by production UI. */
export async function resetMockForTests() {
  fault = 'none';
  const db = await database();
  await db.put('state', initial(), 'main');
  db.close();
}
