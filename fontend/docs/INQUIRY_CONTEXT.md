# 询盘对话中的技能与知识库

更新日期：2026-11-01

询盘右侧的 AI 输入区可组合选择技能和知识文档，并随本轮指令一起提交。选择适用于单条消息，可同时添加多个技能和多篇文档。

## 使用方式

- 点击「技能」，或在输入框行首、空格后输入 `/`，按名称、用途或技能 ID 搜索。Mock 使用示例技能；real 模式读取技能市场中已接入且未停用的技能。
- 点击「知识库」，或输入 `@`，按文档标题、目录和正文搜索。知识库中的新建、导入文档保存成功后即可被引用。
- 使用方向键切换候选，Enter 或 Tab 确认，Esc 关闭；也可直接点击候选。确认后移除快捷输入片段，正文保留。
- 已选内容显示为输入框上方的标签，可逐项移除。Enter 发送，Shift+Enter 或 Ctrl+Enter 换行；中文输入法确认候选时不发送。
- 未发送的文字与选择按用户、工作空间和询盘分别暂存，刷新后恢复。保存失败时保留当前输入并显示提示。
- 提交成功后清空当前输入与选择；提交失败时保留。运行失败后的「恢复指令并重试」同时恢复文字、技能及知识快照。
- Mock 模式已发送的用户消息和运行详情显示本轮引用。知识标签可展开查看提交时的全文。

## 数据与存储

运行 POST 请求新增可选的 `context` 字段：

```ts
{
  skills: { id: string; name: string; instructions: string[] }[];
  knowledge: {
    id: string;
    title: string;
    folder: string;
    content: string;
    updated: string;
  }[];
}
```

`instructions` 来自技能市场中的能力说明；知识引用包含完整正文和更新时间。Mock 接口校验结构与重复引用，并分别在 Run、用户消息及成功生成的 Revision 中保存快照。之后修改知识库不会改变既有运行记录，失败与取消也不会改写上一成功版本。

Mock 知识库使用 `navowork:wiki:<userId>:<workspaceId>` 保存到 localStorage，页面及询盘选择器共享查询缓存，并响应当前窗口和其他窗口的存储更新。新建、导入及收藏刷新后仍保留。损坏或无法写入的存储会显示错误，原数据保留。

## 当前范围与后端接入

Mock 运行固定案例，选定技能和知识不会驱动真实模型推理，也不会直接改变示例报价。德国陶瓷杯等未支持案例继续明确返回需补充信息。

真实模式的知识引用通过 `sourceVersionIds` 提交，后端核验权限与撤销状态并冻结对应版本正文，不依赖客户端正文作为知识来源。技能选择来自服务端可用目录，能力说明附加到本轮用户指令，实际工具执行仍由后端路由与权限控制。`context` 的 UI 快照回读当前仅在 Mock 中实现；real 模式通过指令及固定来源留档。旧本机草稿中没有服务端版本号的引用需要重新选择。

真实知识库保存到服务端并复用后端权限；Mock 知识库保存在本机浏览器。插件、专家套件、自动技能选择、自动知识检索及自定义技能导入不属于本次实现。

## 实现与验证

- `src/features/InquiryComposer.tsx`：按钮、快捷输入、搜索选择器、键盘行为及选择标签。
- `src/features/inquiry-context.ts`、`InvocationContext.tsx`：上下文转换与记录展示。
- `src/features/wiki-store.ts`、`StaticLibrary.tsx`：知识持久化、创建、导入及共享查询。
- `src/features/InquiryWorkspace.tsx`、`src/api/types.ts`、`src/api/mock.ts`：请求、草稿、失败恢复及运行快照。
- `src/api/mock.test.ts`、`tests/e2e/inquiry-context.spec.ts`、`tests/e2e/resources.spec.ts`：接口快照、交互、持久化、失败恢复及移动布局验证。

2026-11-01 合并前 Mock 验证记录：

- `npm run build`：通过，包含 TypeScript 检查。Vite 仍提示现有主包超过 500 KB。
- `npm test`：3 个测试文件、30 项测试通过。
- `inquiry-context.spec.ts`、`inquiry-results.spec.ts`、`workspace.spec.ts`：18 项浏览器回归通过。
- `resources.spec.ts`：6 项浏览器回归通过。
- 相关文件 Prettier 检查及 `git diff --check`：通过。已检查桌面浅色与手机深色截图。

验证使用本地 Mock 环境，未进行真实模型或后端联调。
