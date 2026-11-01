import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';
import { ErrorNotice } from '../../components/ui';
import type { WorkbenchData } from '../../api/types';
import './research.css';

type Entry = Record<string, any>;
interface Research {
  artifacts: Entry[];
  imageAttempts: Entry[];
  bomCandidates: Entry[];
}
interface Section {
  locator: Record<string, unknown>;
  text: string;
}
interface Observation {
  evidence_id: string;
  competitor: string;
  attribute: string;
  excerpt: string;
  locator: Record<string, unknown>;
  observed_at: string;
  applicable_scope: string;
}
const fields = [
  'material_name',
  'specification',
  'quantity',
  'unit',
  'unit_price',
  'currency',
  'subtotal',
];
const labels: Record<string, string> = {
  material_name: '物料',
  specification: '规格',
  quantity: '用量',
  unit: '单位',
  unit_price: '单价',
  currency: '币种',
  subtotal: '小计',
};

export function ResearchPanel({
  path,
  data,
  disabled,
  onChanged,
  onGenerateImage,
}: {
  path: string;
  data: WorkbenchData;
  disabled: boolean;
  onChanged: () => void;
  onGenerateImage: (prompt: string) => Promise<boolean>;
}) {
  const endpoint = `${path}/workbench/research`;
  const research = useQuery({
    queryKey: ['case-research', path, data.case.currentRevision],
    queryFn: () => api.get<Research>(endpoint),
  });
  const [source, setSource] = useState('');
  const [bomSource, setBomSource] = useState('');
  const [sectionIndex, setSectionIndex] = useState(0);
  const sections = useQuery({
    queryKey: ['research-source', path, source],
    enabled: !!source,
    queryFn: () =>
      api.get<{ sections: Section[] }>(`${endpoint}/sources/${encodeURIComponent(source)}`),
  });
  const [competitor, setCompetitor] = useState('');
  const [attribute, setAttribute] = useState('');
  const [scope, setScope] = useState('');
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [observations, setObservations] = useState<Observation[]>([]);
  const [suggestion, setSuggestion] = useState('');
  const [adopted, setAdopted] = useState<number[]>([]);
  const [prompt, setPrompt] = useState('');
  const [reason, setReason] = useState('');
  const [patches, setPatches] = useState<Record<string, Record<string, Entry>>>({});
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const latest = (kind: string) =>
    research.data?.artifacts
      .filter((entry) => entry.kind === kind)
      .sort((a, b) => b.version - a.version)[0];
  const analysis = latest('competitor_analysis');
  const image = latest('concept_image');
  const brief = latest('design_brief');
  const spec = data.artifacts.spec;
  const locked = disabled || busy;

  async function operate(action: () => Promise<unknown>) {
    setBusy(true);
    setError(undefined);
    setNotice('');
    try {
      const result = (await action()) as Entry;
      setNotice(result?.summary || '已保存新的待复核版本。');
      await research.refetch();
      onChanged();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  function addObservation() {
    const section = sections.data?.sections[sectionIndex];
    if (!section || !competitor.trim() || !attribute.trim() || !scope.trim() || !date) return;
    setObservations((old) => [
      ...old,
      {
        evidence_id: source,
        competitor,
        attribute,
        excerpt: section.text.slice(0, 2000),
        locator: section.locator,
        observed_at: date,
        applicable_scope: scope,
      },
    ]);
  }

  return (
    <section className="case-research" aria-label="竞品、概念图与 BOM 识别">
      <details>
        <summary>竞品、概念图与 BOM 识别</summary>
        <ErrorNotice
          error={error || research.error || sections.error}
          onRetry={() => {
            setError(undefined);
            void research.refetch();
          }}
        />
        {notice && <p role="status">{notice}</p>}
        <h3>有来源的竞品比较</h3>
        <p>选取已上传资料的原文，记录日期与适用范围；建议另列，不作为自家成本或制造承诺。</p>
        <div className="research-form">
          <label>
            资料
            <select
              aria-label="竞品资料"
              value={source}
              onChange={(event) => {
                setSource(event.target.value);
                setSectionIndex(0);
              }}
            >
              <option value="">选择原件</option>
              {data.evidence.map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {entry.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            来源定位
            <select
              aria-label="来源定位"
              value={sectionIndex}
              onChange={(event) => setSectionIndex(Number(event.target.value))}
            >
              {sections.data?.sections.map((section, index) => (
                <option key={index} value={index}>
                  {JSON.stringify(section.locator)} · {section.text.slice(0, 70)}
                </option>
              ))}
            </select>
          </label>
          <label>
            竞品名称
            <input
              aria-label="竞品名称"
              value={competitor}
              onChange={(event) => setCompetitor(event.target.value)}
            />
          </label>
          <label>
            比较维度
            <input
              aria-label="比较维度"
              placeholder="如面料、结构、零售价"
              value={attribute}
              onChange={(event) => setAttribute(event.target.value)}
            />
          </label>
          <label>
            观察日期
            <input
              aria-label="观察日期"
              type="date"
              value={date}
              max={new Date().toISOString().slice(0, 10)}
              onChange={(event) => setDate(event.target.value)}
            />
          </label>
          <label>
            适用范围
            <input
              aria-label="适用范围"
              value={scope}
              onChange={(event) => setScope(event.target.value)}
              placeholder="地区、渠道、款式或时间范围"
            />
          </label>
        </div>
        {sections.data?.sections[sectionIndex] && (
          <blockquote>{sections.data.sections[sectionIndex].text.slice(0, 2000)}</blockquote>
        )}
        <button
          className="button"
          disabled={
            locked || !sections.data?.sections[sectionIndex] || !competitor || !attribute || !scope
          }
          onClick={addObservation}
        >
          加入比较
        </button>
        <ul>
          {observations.map((entry, index) => (
            <li key={index}>
              {entry.competitor} · {entry.attribute} · {entry.applicable_scope}{' '}
              <button
                aria-label={`移除观察 ${index + 1}`}
                onClick={() => setObservations((old) => old.filter((_, i) => i !== index))}
              >
                移除
              </button>
            </li>
          ))}
        </ul>
        <label>
          候选设计建议
          <textarea
            aria-label="候选设计建议"
            value={suggestion}
            onChange={(event) => setSuggestion(event.target.value)}
          />
        </label>
        <button
          className="button"
          disabled={locked || !observations.length}
          onClick={() =>
            void operate(() =>
              api.post(`${endpoint}/competitors`, {
                baseRevision: data.case.currentRevision,
                base_version: analysis?.version || 0,
                observations,
                suggestions: suggestion.trim()
                  ? [
                      {
                        text: suggestion,
                        observation_indices: observations.map((_, index) => index),
                      },
                    ]
                  : [],
                assumptions: [],
              }),
            )
          }
        >
          保存竞品比较与设计简报
        </button>
        {analysis && (
          <div className="research-result">
            <strong>竞品比较 V{analysis.version} · 待复核</strong>
            {analysis.content.observations.map((entry: Entry, index: number) => (
              <blockquote key={index}>
                <b>
                  {entry.competitor} · {entry.attribute}
                </b>
                <p>{entry.excerpt}</p>
                <small>
                  {entry.observed_at} · {entry.applicable_scope} · {entry.evidence_id} ·{' '}
                  {JSON.stringify(entry.locator)}
                </small>
              </blockquote>
            ))}
            {analysis.content.suggestions.map((entry: Entry, index: number) => (
              <p key={index}>候选建议：{entry.text}</p>
            ))}
          </div>
        )}
        {brief && (
          <div className="research-result">
            <strong>设计简报 V{brief.version}</strong>
            {brief.content.competitorSuggestions?.map((entry: Entry, index: number) => (
              <label key={index}>
                <span>
                  <input
                    type="checkbox"
                    aria-label={`采纳建议 ${index + 1}`}
                    checked={adopted.includes(index)}
                    onChange={(event) =>
                      setAdopted((old) =>
                        event.target.checked
                          ? [...old, index]
                          : old.filter((value) => value !== index),
                      )
                    }
                  />{' '}
                  {entry.text}
                </span>
              </label>
            ))}
            <button
              className="button"
              disabled={locked || !adopted.length}
              onClick={() =>
                void operate(() =>
                  api.post(`${endpoint}/design-briefs/${brief.itemId || brief.id}/adopt`, {
                    baseRevision: data.case.currentRevision,
                    indices: adopted,
                  }),
                )
              }
            >
              记录采纳的设计方向
            </button>
            {brief.content.adoptedSuggestions?.map((entry: Entry, index: number) => (
              <p key={index}>已采纳方向：{entry.text} · 制造可行性、规格和成本仍待核对</p>
            ))}
          </div>
        )}
        <h3>规格绑定的产品概念图</h3>
        <label>
          生成或修改要求
          <textarea
            aria-label="概念图要求"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="描述产品、材料、颜色、LOGO 和需要修改的部分"
          />
        </label>
        <button
          className="button"
          disabled={locked || !spec || !prompt.trim()}
          onClick={() =>
            void onGenerateImage(prompt)
          }
        >
          生成概念图草稿（Mock）
        </button>
        {!spec && <p>先保存规格草稿，概念图将绑定具体规格版本。</p>}
        {image && (
          <figure>
            <img src={image.content.downloadUrl} alt={`概念图 V${image.version}，仅供视觉沟通`} />
            <figcaption>
              {image.content.generationMode === 'preset' && '预置演示图 · '}
              V{image.version} · 规格 {image.content.specVersionId} ·{' '}
              {['stale', 'needs_review', 'superseded'].includes(image.freshness?.status)
                ? '设计输入已变化，待更新或复核'
                : '视觉匹配待人工复核；非工程图、非实物样品'}{' '}
              <a href={image.content.downloadUrl}>下载原图</a>
              {image.content.proposalDownloadUrl && (
                <>
                  {' '}
                  · <a href={image.content.proposalDownloadUrl}>下载可编辑设计提案 DOCX</a>
                </>
              )}
            </figcaption>
          </figure>
        )}
        {research.data?.imageAttempts
          .filter((attempt) => attempt.status === 'failed')
          .map((attempt) => (
            <p key={attempt.id}>
              {attempt.message || attempt.code || '图像生成失败'}{' '}
              <button
                className="button"
                disabled={locked || !attempt.retryable}
                onClick={() =>
                  void onGenerateImage(attempt.prompt)
                }
              >
                使用 Mock 重新生成
              </button>
            </p>
          ))}
        <h3>BOM 图片识别与逐行复核</h3>
        <label>
          供应商或内部 BOM 原件
          <select
            aria-label="BOM 图片原件"
            value={bomSource}
            onChange={(event) => setBomSource(event.target.value)}
          >
            <option value="">选择 PNG/JPEG 原件</option>
            {data.evidence.map((entry) => (
              <option key={entry.id} value={entry.id}>
                {entry.title}
              </option>
            ))}
          </select>
        </label>
        <button
          className="button"
          disabled={locked || !bomSource}
          onClick={() =>
            void operate(() =>
              api.request(`${endpoint}/bom-candidates`, {
                method: 'POST',
                timeoutMs: 150000,
                body: { baseRevision: data.case.currentRevision, evidenceId: bomSource },
              }),
            )
          }
        >
          识别为待复核候选
        </button>
        <label>
          纠正依据
          <input
            aria-label="BOM 纠正依据"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
        {research.data?.bomCandidates
          .filter(
            (candidate, _, all) =>
              !all.some(
                (other) =>
                  other.candidate_id === candidate.candidate_id &&
                  other.revision > candidate.revision,
              ),
          )
          .map((candidate) => (
            <div className="research-result" key={candidate.id}>
              <strong>BOM 候选 V{candidate.revision} · 待复核，未核定价格</strong>
              <div className="research-table">
                <table>
                  <thead>
                    <tr>
                      {fields.map((field) => (
                        <th key={field}>{labels[field]}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {candidate.rows.map((row: Entry) => (
                      <tr key={row.id}>
                        {fields.map((field) => (
                          <td key={field}>
                            <input
                              aria-label={`${row.id} ${labels[field]}`}
                              defaultValue={row[field] || ''}
                              onChange={(event) =>
                                setPatches((old) => ({
                                  ...old,
                                  [candidate.id]: {
                                    ...old[candidate.id],
                                    [`${row.id}:${field}`]: {
                                      row_id: row.id,
                                      field,
                                      value: event.target.value,
                                    },
                                  },
                                }))
                              }
                            />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {candidate.validation?.issues?.map((issue: Entry, index: number) => (
                <p key={index}>
                  {issue.row_id} {issue.field}: {issue.question}
                </p>
              ))}
              <button
                className="button"
                disabled={
                  locked || !reason.trim() || !Object.keys(patches[candidate.id] || {}).length
                }
                onClick={() =>
                  void operate(() =>
                    api.patch(`${endpoint}/bom-candidates/${candidate.id}`, {
                      baseRevision: data.case.currentRevision,
                      expectedVersion: candidate.revision,
                      reason,
                      patches: Object.values(patches[candidate.id] || {}),
                    }),
                  )
                }
              >
                保存纠正版并重新校验
              </button>
            </div>
          ))}
      </details>
    </section>
  );
}

const statusLabel: Record<string, string> = {
  synced: '已同步',
  updating: '更新中',
  failed: '更新失败',
  needs_review: '待复核',
  blocked: '待上游处理',
  ready: '已生成',
  pending: '待生成',
};
export function PropagationPanel({
  path,
  revision,
  disabled,
  onChanged,
}: {
  path: string;
  revision: number;
  disabled: boolean;
  onChanged: () => void;
}) {
  const groups = useQuery({
    queryKey: ['case-propagation', path, revision],
    queryFn: () => api.get<{ runs: Entry[] }>(`${path}/workbench/dependencies`),
  });
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  async function retry(group: Entry, kind: string) {
    setBusy(true);
    setError(undefined);
    try {
      await api.post(`${path}/workbench/propagation/${group.id}/retry/${kind}`);
      await groups.refetch();
      onChanged();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="case-research" aria-label="跨文件同步">
      <details>
        <summary>跨文件同步 · {groups.data?.runs.length || 0} 次变更</summary>
        <ErrorNotice
          error={error || groups.error}
          onRetry={() => {
            setError(undefined);
            void groups.refetch();
          }}
        />
        {!groups.data?.runs.length && (
          <p>修改已纳管成果后，将在这里显示精确影响、版本和同步状态。</p>
        )}
        {groups.data?.runs
          .slice()
          .reverse()
          .map((group) => (
            <article className="research-result" key={group.id}>
              <strong>{statusLabel[group.status] || group.status}</strong>
              <small> · 第 {group.sequence || group.version} 次变更</small>
              {!group.coverageComplete && <p>部分修改没有显式映射，影响覆盖待复核。</p>}
              <ul>
                {group.changes?.map((change: Entry, index: number) => (
                  <li key={index}>
                    {change.field}: {String(change.before ?? '未知')} →{' '}
                    {String(change.after ?? '未知')}
                  </li>
                ))}
              </ul>
              {Object.entries(group.nodes || {}).map(([kind, raw]) => {
                const node = raw as Entry;
                return (
                  <div key={kind}>
                    <b>
                      {kind} · {statusLabel[node.status] || node.status}
                    </b>
                    <p>{node.error}</p>
                    {node.outputId && (
                      <details>
                        <summary>查看版本依据</summary>
                        <small>{node.outputId}</small>
                      </details>
                    )}
                    <ul>
                      {Object.entries(node.exports || {}).map(([format, value]) => (
                        <li key={format}>
                          {format}:{' '}
                          {statusLabel[(value as Entry).status] || (value as Entry).status}
                        </li>
                      ))}
                    </ul>
                    {node.status !== 'synced' && (
                      <button
                        className="button"
                        disabled={disabled || busy}
                        onClick={() => void retry(group, kind)}
                      >
                        重试 {kind} 分支
                      </button>
                    )}
                  </div>
                );
              })}
            </article>
          ))}
      </details>
    </section>
  );
}
