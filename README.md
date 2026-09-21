# Auditable Scientist Lab

状态：`implementing`（T1 acceptance 已形成，T2–T5 bounded slices 已形成；仍有科学与发布 gates）

正式远程仓库：[wangyufanshuai/auditable-scientist-lab](https://github.com/wangyufanshuai/auditable-scientist-lab)
（MIT，默认分支 `main`）。当前远程仓库只有初始 `README.md` 和 `LICENSE`；本地规划材料
尚未推送。

这是一个离线优先、可回放的科学发现工作台。第一条垂直切片使用
`E:/xuexi/projects/05_hohmann_mars_transfer`，目标是把 Hohmann 火星转移
计算包装成：问题形式化 → 候选方程 → 留出集验证 → 反例检查 → 证据报告。

当前实现已经包含离线 CLI、回放与 T1 acceptance，以及 T2–T5 各自的有限 evaluator；
这些结果只支持声明范围内的 validated reproduction，不声称复现外部论文、真实世界因果、
生产 solver、安全湿实验或发现新物理。
外部 `symbolic-physics-engine` 路径尚未确认，因此首版使用内置的有界符号候选器；
外部引擎适配保持 `blocked`。

长期路线覆盖共享任务契约中的五个科学垂直切片：物理定律发现、因果物理世界、
物理动力学基础、携证模拟和生化协议验证。它们共享审计内核，但分别由领域评估器
验收，不能由一个总分或一次 demo 代替。

## 当前入口

- [implementation-plan.md](implementation-plan.md)：阶段、依赖、验收和最小实现顺序。
- [source_inventory.json](source_inventory.json)：本地源项目和来源状态。
- [schemas/run.schema.json](schemas/run.schema.json)：Run、Event、Claim、Evidence 契约草案。
- [docs/EVIDENCE_POLICY.md](docs/EVIDENCE_POLICY.md)：证据等级和禁止性表述。
- [docs/DECISIONS.md](docs/DECISIONS.md)：已确认的范围决策。
- [artifacts/p1-contract-report.md](artifacts/p1-contract-report.md)：P1 工程检查收据。
- [artifacts/acceptance.json](artifacts/acceptance.json)：T1 acceptance 清单和边界。
- [artifacts/track-portfolio.json](artifacts/track-portfolio.json)：T1–T5 独立 evaluator 收据。
- [artifacts/portfolio-status.md](artifacts/portfolio-status.md)：五轨状态、开放 gate 和发布边界。
- [artifacts/acceptance-runs-v6/run-7a65020acaf83cfc/report.md](artifacts/acceptance-runs-v6/run-7a65020acaf83cfc/report.md)：当前 T1 回放报告。

## 非目标

首版不做自主联网爬虫、自动发表、多租户、大模型训练、自动声称新物理或 Web UI。
