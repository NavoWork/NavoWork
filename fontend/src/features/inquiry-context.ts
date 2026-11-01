import type { KnowledgeContext, RunContext } from '../api';
import { marketItems } from './skill-market-data';

export interface ComposerContext {
  skillIds: string[];
  knowledge: KnowledgeContext[];
}
export const emptyComposerContext = (): ComposerContext => ({ skillIds: [], knowledge: [] });

export function runContext(selection: ComposerContext): RunContext | undefined {
  const skills = selection.skillIds.map((id) => {
    const skill = marketItems.skills.find((item) => item.id === id);
    if (!skill) throw new Error('选中的技能已不可用，请移除后重新选择。');
    return { id: skill.id, name: skill.name, instructions: skill.includes };
  });
  return skills.length || selection.knowledge.length
    ? { skills, knowledge: selection.knowledge }
    : undefined;
}

export function restoreContext(context?: RunContext): ComposerContext {
  return {
    skillIds: context?.skills.map((skill) => skill.id) || [],
    knowledge: context?.knowledge || [],
  };
}

export function inlineContextToken(value: string, caret: number) {
  const match = value.slice(0, caret).match(/(?:^|\s)([/@])([^\s/@]*)$/);
  if (!match) return null;
  return {
    kind: match[1] === '/' ? ('skills' as const) : ('knowledge' as const),
    query: match[2],
    start: caret - match[2].length - 1,
    end: caret,
  };
}
