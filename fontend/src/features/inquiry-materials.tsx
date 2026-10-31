import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Archive, Check, FilePlus2, Paperclip } from 'lucide-react';
import { api } from '../api';
import type { Asset, Locale, MaterialBundle, Revision } from '../api/types';
import { EmptyState, ErrorNotice, Loading, Modal } from '../components/ui';
export function MaterialsPanel({
  base,
  path,
  scope,
  revision,
  readOnly,
  pending,
  draftVersions,
  selectedAssets,
  onSelect,
}: {
  base: string;
  path: string;
  scope: string;
  revision: Revision;
  readOnly: boolean;
  pending: boolean;
  draftVersions: Partial<Record<Locale, number>>;
  selectedAssets: string[] | null;
  onSelect: (ids: string[]) => void;
}) {
  const [choosing, setChoosing] = useState(false);
  const [selection, setSelection] = useState<string[]>([]);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const queryClient = useQueryClient();
  const assets = useQuery({
    queryKey: ['assets-for-inquiry', scope],
    queryFn: ({ signal }) => api.get<{ items: Asset[] }>(`${base}/assets`, signal),
    enabled: choosing,
  });
  const bundles = useQuery({
    queryKey: ['materials', scope],
    queryFn: ({ signal }) =>
      api.get<{ items: MaterialBundle[] }>(`${path}/material-bundles`, signal),
  });
  const items = bundles.data?.items.filter((b) => b.revision === revision.number) || [];
  async function bundle() {
    if (busy) return;
    setBusy(true);
    setError(undefined);
    try {
      await api.post<MaterialBundle>(`${path}/material-bundles`, {
        revision: revision.number,
        draftVersions,
        assetVersionIds: revision.assetRefs,
        sourceVersionIds: revision.sourceRefs.map((s) => s.sourceVersionId),
      });
      await queryClient.invalidateQueries({ queryKey: ['materials', scope] });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="iw-materials">
      <div className="iw-section-heading">
        <span className="iw-kicker">MATERIALS & REFERENCES</span>
        <h3>让资料随版本一起保留</h3>
      </div>
      <div className="iw-material-actions">
        <button
          className="button"
          disabled={readOnly}
          onClick={() => {
            setSelection(selectedAssets ?? revision.assetRefs);
            setChoosing(true);
          }}
        >
          <Paperclip size={13} />
          选择引用素材
        </button>
        <button className="button" disabled={readOnly || pending || busy} onClick={bundle}>
          <Archive size={13} />
          {busy ? '整理中…' : '整理材料草稿'}
        </button>
      </div>
      {selectedAssets !== null && (
        <p className="iw-note">
          已为下一次处理选择 {selectedAssets.length}{' '}
          份素材。点击「处理反馈」后由服务端校验并写入新版本；当前版本尚未改变。
        </p>
      )}
      <div className="iw-asset-refs">
        {revision.assetRefs.length ? (
          revision.assetRefs.map((id) => (
            <div key={id}>
              <Paperclip size={12} />
              <span>{id}</span>
              <small>本版本已引用</small>
            </div>
          ))
        ) : (
          <p className="iw-muted">
            此版本尚未引用素材。可从已上传的资料中选择与方案 SKU 一致的版本。
          </p>
        )}
      </div>
      <ErrorNotice
        error={error || bundles.error}
        onRetry={bundles.error ? () => void bundles.refetch() : undefined}
      />
      {bundles.isPending ? (
        <Loading label="正在读取材料清单" />
      ) : (
        items.length > 0 && (
          <div className="iw-material-list">
            {items.map((b) => (
              <article key={b.id}>
                <FilePlus2 size={17} />
                <div>
                  <strong>V{b.revision} 材料草稿</strong>
                  <p>
                    英语草稿 V{b.draftVersions['en-US']} · 西语草稿 V{b.draftVersions['es-MX']} ·{' '}
                    {b.assetVersionIds?.length || 0} 份素材
                  </p>
                  <small>{b.id}</small>
                </div>
                <span>
                  <Check size={11} />
                  已整理 · 未发送
                </span>
              </article>
            ))}
          </div>
        )
      )}
      {choosing && (
        <Modal title="选择本次运行引用的素材" onClose={() => setChoosing(false)}>
          <p className="iw-muted">
            当前方案：{revision.proposal.selectedSku || '尚未确定'}。素材按固定版本引用；不匹配的
            SKU 需要先修改方案。
          </p>
          {assets.isPending ? (
            <Loading />
          ) : assets.error ? (
            <ErrorNotice error={assets.error} onRetry={() => void assets.refetch()} />
          ) : assets.data?.items.length ? (
            <div className="iw-asset-chooser">
              {assets.data.items.map((a) => {
                const id = `${a.id}:v${a.version}`;
                const matches =
                  !!revision.proposal.selectedSku &&
                  a.skuScope.includes(revision.proposal.selectedSku);
                return (
                  <label key={id} className={!matches ? 'unavailable' : ''}>
                    <input
                      type="checkbox"
                      checked={selection.includes(id)}
                      disabled={!matches}
                      onChange={(e) =>
                        setSelection((old) =>
                          e.target.checked ? [...old, id] : old.filter((v) => v !== id),
                        )
                      }
                    />
                    <div>
                      <strong>
                        {a.title} <small>V{a.version}</small>
                      </strong>
                      <p>
                        {a.skuScope.join('、') || '未指定 SKU'} · {a.locale} · {a.mediaType}
                      </p>
                      <p>{a.source}</p>
                      {!matches && <span>与当前方案 SKU 不匹配，不能引用</span>}
                    </div>
                  </label>
                );
              })}
            </div>
          ) : (
            <EmptyState
              title="还没有可引用素材"
              description="先到资产库上传资料并填写 SKU 范围。"
            />
          )}
          <div className="iw-modal-actions">
            <button className="button" onClick={() => setChoosing(false)}>
              取消
            </button>
            <button
              className="button button-primary"
              disabled={!assets.data || !!assets.error}
              onClick={() => {
                onSelect(selection);
                setChoosing(false);
              }}
            >
              确认选择 {selection.length} 份素材
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
