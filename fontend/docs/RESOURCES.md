# EasyWork 资源页面与联调说明

本项目负责前端资源管理体验，默认使用明确标识的 Mock。正式知识、商品、文件权限与发布校验仍由服务端提供。

## 页面与操作

| 入口                 | 可操作流程                                         | 关键状态                                               |
| -------------------- | -------------------------------------------------- | ------------------------------------------------------ |
| 知识 Wiki → 业务知识 | 新建 → 保存草稿 → 发布；已发布资料创建新版后再编辑 | 未保存、保存失败、编辑版本冲突、草稿、已发布、历史只读 |
| 知识 Wiki → 商品目录 | 下载模板 → 上传 CSV → 逐行错误与预览 → 确认发布    | 上传/校验中、错误阻断、待发布、已发布                  |
| 资产库               | 上传文件与元信息 → 查看固定版本 → 授权预览/下载    | 文件错误、上传中、读取失败、可预览/下载                |
| 能力目录             | 查看内置能力 → 管理员启停                          | 必需/可选、启用/停用、保存中、失败                     |

知识编辑使用 `editVersion`。冲突时展示服务端内容，保留本地文本，让用户选择以最新草稿为基准继续保存；已发布版本不可直接覆盖。列表和编辑器均以资料 ID + 版本标识，历史引用不受更新影响。

成员可以维护知识草稿、预览商品导入及上传素材；资源发布、撤销与能力开关由管理员操作。界面提示不代替服务端授权检查。

## 数据请求

数据通过 `src/api/index.ts` 的统一客户端读取，列表由 TanStack Query 管理。缓存键包含账号、工作空间及资源种类，查询使用 AbortSignal；保存成功后使相关列表失效并重新获取，不把本地乐观修改当作服务端成功。

所有路径以 `/api/v1/workspaces/{workspaceId}` 为前缀：

- 知识：`GET/POST /knowledge`、`POST /knowledge/{id}/versions`、`PATCH /knowledge/{id}/versions/{version}`、`POST .../publish`。
- 商品：`GET /products`、`POST /product-imports`、`POST /product-imports/{id}/publish`。
- 素材：`GET/POST /assets`、`GET /assets/{id}/versions/{version}/download`。
- 能力：`GET /capabilities`、`PATCH /capabilities/{id}`。

列表返回 `{ items: [...] }`，其他成功响应直接返回对应对象。下载通过带会话的 `api.download` 取得 Blob。React 以文本展示知识内容，不执行 Markdown 中的 HTML。图片预览使用临时 Blob URL，关闭后释放。

CSV 模板字段：`sku,name,specification,moq,stock,stockObservedAt,minQuantity,maxQuantity,unitPriceMinor,currency,productionDays,dispatchDays,startsAfter,source`。价格使用 USD 最小货币单位；每个价阶一行。模板带一条明确标注的合成示例，需要替换为真实、已核实资料。前端仅提示扩展名和大小限制，逐行校验与正式发布以接口响应为准。

素材上传使用 FormData：`file,title,skuScope,locale,source`。SKU 用英文逗号分隔；`source` 记录来源和用途。前端提示单文件 20 MB 上限及 JPEG/PNG/WebP/PDF 类型，正式文件内容检查由后端完成。

## 验证入口

`tests/e2e/resources.spec.ts` 包含 4 条浏览器测试：

1. 知识保存与发布后创建新版，旧版内容保持不变。
2. 非法价格导入显示字段错误且禁止发布，修正后发布成功。
3. 上传 PNG 后读取相同固定版本的图片预览与下载。
4. 停用必需能力后运行被阻止，用户输入与业务版本保留。

从仓库根目录运行：`npm run test:e2e -- tests/e2e/resources.spec.ts`；或在 `fontend/` 下执行 `npx playwright test tests/e2e/resources.spec.ts`。并行运行其他 Playwright 进程时应使用不同的 `--output`，避免测试产物目录被互相清理。

## 当前边界

- Mock 数据与上传文件保存在当前浏览器 IndexedDB，用于联调演示；不代表后端数据库或真实文件存储交付。
- 初始示例素材只有元信息。点击预览/下载会明确提示缺少文件，上传自己的测试文件后可验证完整读取流程。
- 真实服务尚需确认列表和错误 DTO、文件内容检查、账号权限、资源语义与保存策略。测试通过不等同真实服务验收。
- CSV 页面先展示前 30 行，错误列表和发布基于接口返回的全量校验结果。
- PDF 使用浏览器内置预览；浏览器不支持时可下载查看，不进行 PDF/OCR 解析。
- 素材与知识如何参与某一次询盘由运行接口和后端规则确定；资源页面不直接改写已有业务版本。
