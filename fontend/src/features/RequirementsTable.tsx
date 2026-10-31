import { useLayoutEffect, useRef, type ComponentProps } from 'react';

const fields = ['产品', '数量', '规格', '目的地', '到货要求', '定制'] as const;
const fieldPattern = /^(产品|数量|规格|目的地|到货要求|定制)[：:][ \t]*/;

function GrowingInput(props: ComponentProps<'textarea'>) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    const resize = () => {
      if (!element.clientWidth) return;
      element.style.height = 'auto';
      element.style.height = `${element.scrollHeight + 2}px`;
    };
    resize();
    let width = element.clientWidth;
    const observer = new ResizeObserver(() => {
      if (width !== element.clientWidth) {
        width = element.clientWidth;
        resize();
      }
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [props.value]);
  return <textarea {...props} ref={ref} rows={1} />;
}

// Keep the original text between edits so existing drafts and generation keep
// using the same document format, including multiline values and extra notes.
function sections(text: string) {
  const lines = text.split('\n');
  const starts = lines.flatMap((line, index) => {
    const match = line.match(fieldPattern);
    return match ? [{ label: match[1], index, prefix: match[0] }] : [];
  });
  return {
    lines,
    starts: starts.map((item, index) => ({
      ...item,
      end: starts[index + 1]?.index ?? lines.length,
    })),
  };
}

export function RequirementsTable({
  value,
  onChange,
  readOnly,
}: {
  value: string;
  onChange: (value: string) => void;
  readOnly: boolean;
}) {
  const { lines, starts } = sections(value);
  const notesEnd = starts[0]?.index ?? lines.length;
  const notes = lines.slice(0, notesEnd).join('\n');
  function update(label: string, next: string) {
    const section = starts.find((item) => item.label === label);
    if (section) {
      onChange([
        ...lines.slice(0, section.index),
        `${section.prefix}${next}`,
        ...lines.slice(section.end),
      ].join('\n'));
    } else {
      onChange(`${value}${value ? '\n' : ''}${label}：${next}`);
    }
  }
  return (
    <div className="ic-requirements-editor">
      <table className="ic-requirements-table" aria-label="客户需求与规格">
        <thead><tr><th scope="col">需求字段</th><th scope="col">内容 · 点击填写</th></tr></thead>
        <tbody>
          {fields.map((label) => {
            const section = starts.find((item) => item.label === label);
            const text = section
              ? lines.slice(section.index, section.end).join('\n').slice(section.prefix.length)
              : '';
            return (
              <tr key={label}>
                <th scope="row">{label}</th>
                <td>
                  <GrowingInput
                    aria-label={`需求${label}`}
                    value={text}
                    readOnly={readOnly}
                    placeholder={`填写${label}，未确认可留空`}
                    onChange={(event) => update(label, event.target.value)}
                    spellCheck={false}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {notes && (
        <label className="ic-requirements-notes">
          补充说明
          <textarea
            aria-label="需求补充说明"
            rows={3}
            value={notes}
            readOnly={readOnly}
            onChange={(event) => onChange(
              [event.target.value, ...lines.slice(notesEnd)].filter(Boolean).join('\n'),
            )}
          />
        </label>
      )}
    </div>
  );
}
