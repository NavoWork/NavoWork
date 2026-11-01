import { afterEach, expect, it, vi } from 'vitest';
import { api } from '../api';
import type { Inquiry } from '../api/types';
import { generateInquiryNode } from './inquiry-generation';

afterEach(() => vi.restoreAllMocks());

it('sends edited content and image prompts only to the simulation route', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({});
  const inquiry = { currentRevision: 4 } as Inquiry;
  await generateInquiryNode('/inquiries/test', inquiry, 'sample', undefined, { editedText: '客户修改后的打样说明' });
  expect(post).toHaveBeenLastCalledWith('/inquiries/test/workbench/simulations', expect.objectContaining({ node: 'sample', editedText: '客户修改后的打样说明' }));
  await generateInquiryNode('/inquiries/test', inquiry, 'design', undefined, { imagePrompt: '蓝色手提带' });
  expect(post).toHaveBeenLastCalledWith('/inquiries/test/workbench/simulations', expect.objectContaining({ node: 'design', imagePrompt: '蓝色手提带' }));
});

it('runs incomplete inquiry nodes through local simulation without an API key', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({});
  await generateInquiryNode('/inquiries/test', {
    demoDataScope: 'incomplete', currentRevision: 0,
  } as Inquiry, 'requirements');
  expect(post).toHaveBeenCalledWith('/inquiries/test/workbench/simulations', expect.objectContaining({
    node: 'requirements', contextScope: 'inquiry', baseRevision: 0,
  }));
});

it('keeps the complete demo on its existing simulation route', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({});
  await generateInquiryNode('/inquiries/test', {
    demoDataScope: 'full', currentRevision: 0,
  } as Inquiry, 'requirements');
  expect(post).toHaveBeenCalledWith('/inquiries/test/workbench/simulations', expect.objectContaining({
    node: 'requirements', baseRevision: 0,
  }));
});
