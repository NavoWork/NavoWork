# guilimao 工作台宿主映射（2026-11-01）

主链保持 guilimao 的 `agent_runtime` + `WorkbenchToolbox`，业务工具负责规格、BOM、核价、样品和订单。`workbench_files.py` 只组合 Agent Kit 的六类文件工具：`file_list_context`、`file_read_document`、`file_list_artifacts`、`file_create_working_copy`、`file_edit_file`、`file_validate_artifact`。不暴露第二套报价/发布工具给原生工作台 Agent。独立 CLI/legacy `agentFileTools` 入口仍保留，不作为工作台默认主链。

`HostAdapter` 校验 CaseAccess、Case/Run/Job、活动修订、WorkItem generation/租约、输入哈希和授权文件。人工 Office 编辑版本、原生导出、Agent 文件均以不可变引用进入同 Case 文件列表；没有任意路径或 shell 执行入口。权限撤销和迟到任务不能继续提交。此处是工具与工作空间隔离，不是操作系统沙箱；未来开放任意代码/外部工具应另加进程或容器隔离。

真实文件输出保存在宿主 Blob，版本登记为 Artifact/Export，并通过 Run.fileOutputs 呈现。原件不可改写；编辑创建工作副本和新版本，未知业务映射触发影响覆盖待复核。已纳管的规格/BOM 模板由 Office 路径提交精确业务字段，再执行依赖传播。

Agent 缺资料会进入可恢复 checkpoint，补证后在同一 Case/Job 继续。未恢复的工具失败使 Run 明确失败；已有成功文件、成果和修订保留，并返回 executionOutcome=partial、failedTools。PDF 成功不能掩盖 XLSX 分支失败。

验收包括真实 FastAPI/SQLite/Blob、授权下载、实际 LangGraph 文件编辑和补证继续；模型为离线替身。另有实际 Edge 内联编辑浏览器验收。真实模型解释、图像生成与 VLM 质量不由离线测试证明，参见 [PRD 验收](../../doc/19-guilimao-prd-acceptance.md) 和 [真实服务验收入口](../../backend/tests/live/README.md)。
