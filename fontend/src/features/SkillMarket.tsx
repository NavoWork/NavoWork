import { useId, useRef, useState, type KeyboardEvent } from 'react';
import { ArrowRight, Check, Layers3, Puzzle, Search, Sparkles, X } from 'lucide-react';
import { EmptyState, Modal } from '../components/ui';
import { marketItems, marketTabs, type MarketItem, type MarketTab } from './skill-market-data';
import './skill-market.css';

const tabIcons = { skills: Sparkles, plugins: Puzzle, suites: Layers3 };

export function SkillMarket() {
  const [tab, setTab] = useState<MarketTab>('skills');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<MarketItem | null>(null);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const id = useId();
  const current = marketTabs.find((item) => item.id === tab)!;
  const keyword = query.trim().toLocaleLowerCase();
  const items = marketItems[tab].filter((item) =>
    [item.name, item.description, item.category, ...item.tags, ...item.includes]
      .join(' ')
      .toLocaleLowerCase()
      .includes(keyword),
  );

  function changeTab(next: MarketTab) {
    setTab(next);
    setQuery('');
    setSelected(null);
  }

  function navigateTabs(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next: number;
    if (event.key === 'ArrowRight') next = (index + 1) % marketTabs.length;
    else if (event.key === 'ArrowLeft') next = (index + marketTabs.length - 1) % marketTabs.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = marketTabs.length - 1;
    else return;
    event.preventDefault();
    changeTab(marketTabs[next].id);
    tabRefs.current[next]?.focus();
  }

  return (
    <div className="feature-page skill-market">
      <header className="market-heading">
        <h1>技能市场</h1>
      </header>

      <div className="market-toolbar">
        <div className="market-tabs" role="tablist" aria-label="技能市场分类">
          {marketTabs.map((item, index) => {
            const Icon = tabIcons[item.id];
            return (
              <button
                key={item.id}
                ref={(element) => {
                  tabRefs.current[index] = element;
                }}
                type="button"
                role="tab"
                id={`${id}-tab-${item.id}`}
                aria-selected={tab === item.id}
                aria-controls={`${id}-panel-${item.id}`}
                tabIndex={tab === item.id ? 0 : -1}
                onClick={() => changeTab(item.id)}
                onKeyDown={(event) => navigateTabs(event, index)}
              >
                <Icon size={16} />
                {item.label}
                <span className="market-tab-count">{marketItems[item.id].length}</span>
              </button>
            );
          })}
        </div>
        <div className="market-search">
          <Search size={15} aria-hidden="true" />
          <input
            type="search"
            aria-label={`搜索${current.label}`}
            placeholder={`搜索${current.label}…`}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          {query && (
            <button
              type="button"
              className="icon-button"
              aria-label="清空搜索"
              onClick={() => setQuery('')}
            >
              <X size={13} />
            </button>
          )}
        </div>
      </div>

      {marketTabs.map((item) => (
        <section
          key={item.id}
          role="tabpanel"
          id={`${id}-panel-${item.id}`}
          aria-labelledby={`${id}-tab-${item.id}`}
          hidden={tab !== item.id}
          tabIndex={0}
          className="market-panel"
        >
          {tab === item.id && (
            <>
              <div className="market-section-heading">
                <h2>
                  {keyword
                    ? '搜索结果'
                    : `探索${current.label === 'Skill' ? ' Skill' : current.label}`}
                </h2>
                <span role="status">
                  {items.length} 个{current.label === 'Skill' ? ' Skill' : current.label}
                </span>
              </div>
              {items.length ? (
                <div className={`market-grid market-grid-${tab}`}>
                  {items.map((entry) => (
                    <MarketCard
                      key={entry.id}
                      item={entry}
                      tab={tab}
                      onSelect={() => setSelected(entry)}
                    />
                  ))}
                </div>
              ) : (
                <div className="market-empty">
                  <EmptyState title="没有匹配的内容" description="换个关键词，或者清空搜索看看。" />
                  <button className="button" onClick={() => setQuery('')}>
                    清空搜索
                  </button>
                </div>
              )}
            </>
          )}
        </section>
      ))}

      {selected && (
        <Modal title={selected.name} onClose={() => setSelected(null)}>
          <div className={`market-detail market-tone-${tab}`}>
            <div className="market-detail-intro">
              <span className="market-item-icon">
                <selected.icon size={25} strokeWidth={1.6} />
              </span>
              <div>
                <span>
                  {current.label} · {selected.category}
                </span>
                <p>{selected.description}</p>
              </div>
            </div>
            <h3>{tab === 'suites' ? '套件包含' : '可以帮你做什么'}</h3>
            <ul>
              {selected.includes.map((item) => (
                <li key={item}>
                  <Check size={15} />
                  {item}
                </li>
              ))}
            </ul>
            <button className="button" onClick={() => setSelected(null)}>
              返回市场
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function MarketCard({
  item,
  tab,
  onSelect,
}: {
  item: MarketItem;
  tab: MarketTab;
  onSelect: () => void;
}) {
  return (
    <article className={`market-card market-tone-${tab}`}>
      <div className="market-card-top">
        <span className="market-item-icon">
          <item.icon size={23} strokeWidth={1.6} />
        </span>
      </div>
      <h3>{item.name}</h3>
      <p>{item.description}</p>
      <div className="market-tags">
        {item.tags.map((tag) => (
          <span key={tag}>{tag}</span>
        ))}
      </div>
      <div className="market-card-bottom">
        {tab === 'suites' && <span>{item.includes.length} 项专业技能</span>}
        <button type="button" aria-label={`查看${item.name}详情`} onClick={onSelect}>
          查看详情
          <ArrowRight size={14} />
        </button>
      </div>
    </article>
  );
}
