import { BookOpen, Sparkles } from 'lucide-react';
import type { RunContext } from '../api';

export function InvocationContext({ context }: { context?: RunContext }) {
  if (!context || (!context.skills.length && !context.knowledge.length)) return null;
  return (
    <div className="iw-invocation-context" aria-label="本轮技能与知识">
      {context.skills.map((skill) => (
        <span className="iw-invocation-skill" key={skill.id} title={skill.instructions.join('\n')}>
          <Sparkles size={12} />
          {skill.name}
        </span>
      ))}
      {context.knowledge.map((doc) => (
        <details key={doc.id}>
          <summary>
            <BookOpen size={12} />
            {doc.title}
          </summary>
          <small>
            {doc.folder} · {doc.updated}
          </small>
          <pre>{doc.content}</pre>
        </details>
      ))}
    </div>
  );
}
