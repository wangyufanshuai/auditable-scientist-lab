# Auditable Scientist Lab

状态：`implementing`（T1 acceptance 已形成，T2–T5 bounded slices 已形成；仍有科学与发布 gates）

正式远程仓库：[wangyufanshuai/auditable-scientist-lab](https://github.com/wangyufanshuai/auditable-scientist-lab)
（MIT，默认分支 `main`）。本地实现及验收记录尚未推送。

这是一个离线优先、可回放的科学发现工作台。第一条垂直切片使用
`E:/xuexi/projects/05_hohmann_mars_transfer`，目标是把 Hohmann 火星转移
计算包装成：问题形式化 → 候选方程 → 留出集验证 → 反例检查 → 证据报告。

当前实现已经包含离线 CLI、回放与 T1 acceptance，以及 T2–T5 各自通过同一
Tool/Policy 入口执行的有限 evaluator；
这些结果只支持声明范围内的 validated reproduction，不声称复现外部论文、真实世界因果、
生产 solver、安全湿实验或发现新物理。
已定位外部 `symbolic-physics-engine` 目录，但入口仍是未实现的桩，且缺少范围明确的许可证；
因此首版使用内置有界符号候选器，外部适配保持 `blocked`。

长期路线覆盖共享任务契约中的五个科学垂直切片：物理定律发现、因果物理世界、
物理动力学基础、携证模拟和生化协议验证。它们共享审计内核，但分别由领域评估器
验收，不能由一个总分或一次 demo 代替。

## 离线 Quickstart

在一个干净的 Python 3.10+ 环境中执行：

```powershell
python -m pip install -e ".[test]"
python -m pytest -q
auditable-scientist init hohmann.json
$runPath = auditable-scientist run hohmann.json --offline --seed 17 --output-dir artifacts/local-runs
auditable-scientist replay $runPath
auditable-scientist inspect $runPath
auditable-scientist export-report $runPath --output artifacts/local-report.md
auditable-scientist init-track T2 causal.json
$trackPath = auditable-scientist run-track T2 causal.json --output-dir artifacts/local-track-runs
auditable-scientist replay $trackPath
```

仓库中已提交的验收收据另用 `python scripts/verify_acceptance.py` 核查；该命令
要求与收据记录的 Python 和依赖版本一致。普通新环境可运行测试及生成自己的运行包，
版本不一致时旧收据会按设计拒绝回放。

基础轨道生成脚本被已提交 Run 的源码指纹绑定。需要重新生成轨道证据时，
先在隔离副本中依次运行 `python scripts/generate_track_artifacts.py`、
`python scripts/sync_optional_acceptance.py --write` 和
`python scripts/verify_acceptance.py`；第二步从已保存的 T2/T3/T4 可选审计重建验收行，
并按 [状态契约](docs/PORTFOLIO_STATUS_CONTRACT.json) 重建状态表。
`python scripts/sync_optional_acceptance.py --verify` 可只读检查当前收据。
仓库测试会在临时副本执行完整生成链，确认历史 CLI Run 仍可回放。
详细边界见 [再生成方法](docs/REGENERATION_METHOD.md)。

重放**已提交**的五轨运行包时，在 Windows AMD64 的 CPython 3.12.3 上新建
虚拟环境，并从仓库根目录执行：

```powershell
$replayVenv = Join-Path $env:TEMP ("auditable-scientist-replay-" + [guid]::NewGuid().ToString("N"))
python -m venv $replayVenv
$replayPython = Join-Path $replayVenv "Scripts\python.exe"
& $replayPython -m pip install -e ".[test]" -c requirements-replay-win-py312.txt
& $replayPython -m pip check
& $replayPython scripts/verify_replay_environment.py
& $replayPython scripts/verify_acceptance.py
```

`requirements-replay-win-py312.txt` 固定运行和测试依赖的版本闭包；
`artifacts/replay-environment-audit.json` 记录一次在仓库外新建虚拟环境的核验。
约束文件不锁定 wheel 或 Python 解释器的原始字节，跨系统重放也未验收。

独立 wheel 安装后无需源码仓库：先运行 `auditable-scientist init hohmann.json`，
它会在配置旁复制所需数据；再运行 `auditable-scientist run hohmann.json --offline`
与 `auditable-scientist replay <run-dir>`。T2–T5 可先运行
`auditable-scientist init-track T2 t2.json`，再执行
`auditable-scientist run-track T2 t2.json`。这些命令只使用随 wheel 打包的
schema、策略文档和示例 fixture。
`python -m auditable_scientist` 与控制台命令使用同一版本路由；旧 Run 通过固定的
历史源码包回放，新 Run 绑定当前源码。底层 `python -m auditable_scientist.cli`
保留供历史实现检查，不是跨版本回放入口。

`run` 的输出目录必须是空目录或新的目录；回放命令会验证输入、代码版本、运行环境、
seed、源码/证据快照、候选顺序和完整计算输出。正式收据和可复核样例位于
`artifacts/acceptance-runs-v18/`。`run-track` 还接受 `T2P`、`T3`、`T3N`、`T4`、`T4O`、`T5` 和相应
的本地 JSON fixture；运行记录会保留工具调用、负例、源码/证据指纹和边界标签。
新版运行包保存输入快照，并使用 `run://`、`root://` 受限路径；五轨已在复制的
源码目录和移动后的 wheel 运行目录中回放。回放仍要求记录的依赖环境与源码字节一致；
跨操作系统和不同依赖版本尚未验收。
T3 的 Velocity-Verlet 与独立实现的固定步长 RK4、解析解和 Euler 负例比较
见 [docs/T3_METHOD.md](docs/T3_METHOD.md)。T3N 是等边三体解析轨道子轨道，
对照独立 RK4 并拒绝错误力方向；它不代表一般多体或真实任务验证，
见 [docs/T3_NBODY_METHOD.md](docs/T3_NBODY_METHOD.md)。另有可选的受扰动三体有限时域
交叉核验，使用已审计的 SciPy DOP853 环境，见 [docs/T3_PERTURBED_METHOD.md](docs/T3_PERTURBED_METHOD.md)；
独立的可选 Tool/Provider Run 见 [artifacts/t3-perturbed-run-audit.json](artifacts/t3-perturbed-run-audit.json)。
扩展的 [0.75 周期数值网格](docs/T3_HORIZON_GRID.md) 通过预设误差和守恒门槛，
1.0 周期近距离案例被排除；这组网格经过可行性预探，不能视作未触碰的科学留出集。
新增的 [已发表“8 字”三体数值核验](docs/T3_FIGURE_EIGHT_RESULT.md) 按独立预先固定的协议
覆盖 1 与 10 个近似周期，并包含 10 周期动量守恒扰动、错误引力负例和计算预算。
这些可选核验未纳入核心 T3N Run，也不证明混沌长时精度。T2P 是 100 场景二维小球干预与
反事实子轨道，见 [docs/T2_PHYSICAL_METHOD.md](docs/T2_PHYSICAL_METHOD.md)；它只支持
声明的模拟器内部因果效应，不证明真实世界因果识别。独立的整段飞行终点估计器又核对了
100 个既有场景和 24 个变初态留出场景；仍只属合成模拟器证据，见
[docs/T2_INDEPENDENT_ENDPOINT.md](docs/T2_INDEPENDENT_ENDPOINT.md)。
估计器另有可选的离线 Tool/Policy/Provider Run，保存两份输入快照并通过搬移回放及篡改负例，
见 [artifacts/t2-independent-run-audit.json](artifacts/t2-independent-run-audit.json)；真实世界 Claim 仍为 `unverified`。
另有 [T2 真实抛射测量来源盘点](docs/T2_PROJECTILE_SOURCE.md)：论文明确区分光电门测量的初速度和最小二乘拟合的 `v0`，
并说补充文件展示测得初速度；但工作簿列名没有说明保存的是哪个阶段。官方补充工作簿含 179 个采样点、
30 个试验，而论文报告 82 次实验；第二份工作簿是带公式的数值示例，不作为观测数据。
目前 15 个试验的 `v0` 超出论文所述发射速度范围，列级映射、试验覆盖、补充文件再利用权利、
官方补充页的权利文字已审阅，但原始 XLSX 直接再分发仍未确认。物理模型比较及试验级留出均未通过。
它不是干预数据，不能证明真实因果识别；
[来源审计](artifacts/t2-projectile-source-audit.json) 只验证本地原件的结构与指纹，Claim 仍为 `unverified`。
未来比较无阻力与球形阻力模型的[冻结协议](docs/T2_PROJECTILE_MODEL_PROTOCOL.md)只定义整试验留出、指标和负例，
在 `v0` 列映射、权利和试验覆盖 gates 关闭前禁止拟合，也不构成外部预注册。
T4O 把证明收据接到 T3
谐振子数值模块，核对单位、源码、解析解、RK4 和能量漂移；其形式证明仍未配置，
见 [docs/T4_METHOD.md](docs/T4_METHOD.md)。
T4 另有可选的精确有理数线性不变量证明：两个通用系数恒等式证书由独立检查器复核，
泄漏系统作为负例；它不验证物理模型或一般形式证明后端，见
[docs/T4_LINEAR_INVARIANTS.md](docs/T4_LINEAR_INVARIANTS.md)。
这项证明另有独立的离线 Tool/Policy/Provider Run，包含输入快照、事件链、搬移回放和篡改负例，
见 [artifacts/t4-linear-run-audit.json](artifacts/t4-linear-run-audit.json)；物理 Claim 仍是 `unverified`。
T5 是带逐字段文本位置与文档哈希的合成教学审查；
它只给 `demo/text-reviewed`，始终要求人工复核且禁止实验执行，见
[docs/T5_METHOD.md](docs/T5_METHOD.md)。当前八份 CLI 收据在
`artifacts/track-runs-v16/` 和 `artifacts/acceptance-runs-v18/`。
另有 [T5 真实来源 PDF 审计](docs/T5_PBS_SOURCE_RESULT.md)：固定 DOI、许可声明、三页文本哈希与
六步引用位置，只作来源盘点和专家复核提示；不生成可执行协议。
其[只读 T5 Run](artifacts/t5-pbs-source-run-audit.json)纳入共享工具与策略链，
检查搬移回放、篡改拒绝和单次离线调用，Claim 仍为 `unverified`。
独立 [Poppler 交叉抽取审计](docs/T5_PBS_CROSS_READER.md)覆盖三页逐行哈希、引用位置和遗漏负例；
来源许可范围、视觉遗漏、生物安全与人工验收仍未通过。
T1 另有只读 NASA fact-sheet 圆整轨道参数敏感性核对；来源权利和独立任务轨道验证仍未通过，
见 [docs/T1_NASA_PARAMETER_SENSITIVITY.md](docs/T1_NASA_PARAMETER_SENSITIVITY.md)。
可选的固定 SciPy DOP853 环境还从初始状态积分到远日点，对九个合成样例和一个圆整参数样例
核对飞行时间、末态和守恒量；它只覆盖圆轨道出发的二体模型，见
[docs/T1_EXTERNAL_ORBIT.md](docs/T1_EXTERNAL_ORBIT.md)。
该核对另有独立的离线 Tool/Policy/Provider Run 和搬移回放、篡改负例；新版 T1 Run
另调用内置 RK4 工具，仍只覆盖合成圆轨道二体假设。
可选的 [DE440s 固定日期几何核对](docs/T1_DE440S_EPHEMERIS.md) 使用 NAIF
未修改 kernel 的官方校验值、来源规则与本地 SHA-256，比较地球与火星质心的星历状态。
kernel 不入 Git，运行时不联网；它不能验证火星中心会合或航天器任务轨迹。
独立的[离线星历快照 Run](docs/T1_DE440S_RUN.md)将两组状态向量绑定到 Tool/Policy/Provider、
事件链与可搬移回放，并验证输出及快照篡改会失败。回放只从已保存状态重算几何；
若要重新向 NAIF kernel 查询，仍需单独执行星历动态核对。任务 Claim 保持 `unverified`。
可选的 [MAR099s 火星中心核对](docs/T1_MARS_CENTER_EPHEMERIS.md) 从 NAIF 第二个校验过的
kernel 读取火星中心（499）相对质心（4）的状态；两次日期的中心修正小于 0.2 m，
无法消除数千万公里的理想到达位置缺口。它提供中心状态，不提供航天器轨迹或任务会合证明。
可选的 [MAVEN 归档航天器状态核对](docs/T1_MAVEN_MISSION_SOURCE.md) 使用 PDS4 产品标签与
校验过的重建巡航 SPK，在三个探索性时刻读取航天器到火星中心的状态，并核验内含段中心切换。
这项来源核对本身不传播航天器，也不证明任务有效性。
新增的 [MAVEN 短弧传播预检](docs/T1_MAVEN_PROPAGATION_PREFLIGHT.md) 在本地 Git 固定两段
24 小时太阳二体 RK4 对照后才读取 NAV 端点；位置误差约 0.536 km、0.285 km，错误引力
方向负例失败。它通过工程预检，不构成完整任务力学、科学 holdout 或会合验证。
另有 [离线 MAVEN 短弧 Run](docs/T1_MAVEN_PREFLIGHT_RUN.md) 将已保存状态绑定到一次
Tool/Policy/Provider 调用、事件链和可搬移回放；重放独立重算 RK4，不查询 NAIF kernel。
独立的 [MAVEN 行星摄动诊断](docs/T1_MAVEN_PLANETARY_FORCE_RESULT.md) 在固定协议下加入
地月及火星系统质心引力潮汐，两段已看过的 NAV 端点误差降至约 0.068 km、0.217 km。
它仍缺机动及其他力项、独立观测与科学 holdout，任务 Claim 保持 `unverified`。
固定窗口的 [MAVEN 运行事件目录核对](docs/T1_MAVEN_OPS_EVENT_SEARCH_RESULT.md) 从 PDS
产品检查 185,321 条记录：两段巡航短弧内均无卸载/机动关键词记录，附近有反作用轮卸载事件。
目录不含冲量向量，也不能证明记录完整；[PDS 官方 ancillary SIS 的范围说明](docs/T1_MAVEN_ANC_SIS_SOURCE_NOTE.md)
明确事件列表并不穷尽，且公共归档省略部分工程遥测；任务 Claim 不变。
另有 [NAIF 小力文件来源盘点](docs/T1_MAVEN_SFF_EXPLORATORY_RESULT.md) 检查固定短弧附近
九份文件的哈希、原文时间与重复记录；这是事后探索，缺格式 SIS，未将数值列用于传播。
预先固定的 [太阳辐射压敏感性网格](docs/T1_MAVEN_SRP_SENSITIVITY_RESULT.md) 用八个泛化场景
量化简化径向光压对两段终点的条件响应；没有拟合 NAV，也不代表 MAVEN 已校准的平板模型。

## 当前入口

- [implementation-plan.md](implementation-plan.md)：阶段、依赖、验收和最小实现顺序。
- [source_inventory.json](source_inventory.json)：初始本地来源盘点的历史快照。
- [artifacts/symbolic-engine-audit.json](artifacts/symbolic-engine-audit.json)：新发现的本地符号引擎源码指纹、实现与许可证阻断原因。
- [schemas/run.schema.json](schemas/run.schema.json)：Run、Event、Claim、Evidence 契约草案。
- [docs/EVIDENCE_POLICY.md](docs/EVIDENCE_POLICY.md)：证据等级和禁止性表述。
- [docs/T1_SYMBOLIC_GRAMMAR.md](docs/T1_SYMBOLIC_GRAMMAR.md)：T1 十表达式语法、训练集选择与发现边界。
- [docs/T1_NASA_PARAMETER_SENSITIVITY.md](docs/T1_NASA_PARAMETER_SENSITIVITY.md)：外部圆整参数的离线敏感性审计与来源边界。
- [docs/T1_EXTERNAL_ORBIT.md](docs/T1_EXTERNAL_ORBIT.md)：可选外部求解器的二体数值核对、负例与适用边界。
- [docs/T1_DE440S_EPHEMERIS.md](docs/T1_DE440S_EPHEMERIS.md)：NAIF DE440s 来源权利、固定日期坐标契约和任务边界。
- [docs/DECISIONS.md](docs/DECISIONS.md)：已确认的范围决策。
- [docs/T3_METHOD.md](docs/T3_METHOD.md)：T3 双后端方法、来源和适用边界。
- [docs/T2_PHYSICAL_METHOD.md](docs/T2_PHYSICAL_METHOD.md)：T2 二维碰撞干预、反事实与科学边界。
- [docs/T2_INDEPENDENT_ENDPOINT.md](docs/T2_INDEPENDENT_ENDPOINT.md)：T2 独立终点估计器、124 场景核验与合成证据边界。
- [artifacts/t2-independent-run-audit.json](artifacts/t2-independent-run-audit.json)：T2 独立估计器的可选 Tool/Policy/Provider Run 回放与篡改收据。
- [docs/T2_PROJECTILE_SOURCE.md](docs/T2_PROJECTILE_SOURCE.md)：T2 真实抛射测量的来源、覆盖缺口与科学边界。
- [artifacts/t2-projectile-source-audit.json](artifacts/t2-projectile-source-audit.json)：只读来源结构、哈希和负例审计；不含原始 PDF/XLSX。
- [docs/T2_PROJECTILE_MODEL_PROTOCOL.md](docs/T2_PROJECTILE_MODEL_PROTOCOL.md)：T2 试验级模型比较的阻断协议草案。
- [docs/T3_NBODY_METHOD.md](docs/T3_NBODY_METHOD.md)：T3 等边三体子轨道、解析参照和门槛。
- [docs/T3_PERTURBED_METHOD.md](docs/T3_PERTURBED_METHOD.md)：可选受扰动三体数值交叉核验与边界。
- [docs/T3_HORIZON_GRID.md](docs/T3_HORIZON_GRID.md)：0.75 周期平滑网格、1.0 周期近距离排除案例与计算预算。
- [artifacts/t3-perturbed-run-audit.json](artifacts/t3-perturbed-run-audit.json)：可选受扰动三体 Run 的回放、迁移与篡改负例。
- [docs/T3_SWEEP.md](docs/T3_SWEEP.md)：T3 固定参数与步长网格、收敛门槛和边界。
- [docs/T3_EXTERNAL_SOLVER.md](docs/T3_EXTERNAL_SOLVER.md)：可选 SciPy 交叉核验、版本与许可证来源。
- [artifacts/t3-external-run-audit.json](artifacts/t3-external-run-audit.json)：可选 SciPy Tool/Provider Run 的回放、搬移与篡改负例收据。
- [docs/T4_METHOD.md](docs/T4_METHOD.md)：T4 精确转移见证与 T4O 振子携证收据的边界。
- [docs/T4_LINEAR_INVARIANTS.md](docs/T4_LINEAR_INVARIANTS.md)：T4 有理线性不变量证明与独立证书核验的边界。
- [artifacts/t4-linear-run-audit.json](artifacts/t4-linear-run-audit.json)：T4 精确证明的可选 Tool/Policy/Provider Run 回放与篡改收据。
- [docs/T5_METHOD.md](docs/T5_METHOD.md)：T5 文本字段引用、确定性检查与执行边界。
- [artifacts/t5-pbs-source-run-audit.json](artifacts/t5-pbs-source-run-audit.json)：真实 PBS 来源的只读 Run 回放与策略边界。
- [artifacts/t5-pbs-cross-reader-audit.json](artifacts/t5-pbs-cross-reader-audit.json)：独立 PDF 抽取器的全文覆盖与遗漏负例收据。
- [artifacts/p1-contract-report.md](artifacts/p1-contract-report.md)：P1 工程检查收据。
- [artifacts/acceptance.json](artifacts/acceptance.json)：T1 acceptance 清单和边界。
- [artifacts/track-portfolio.json](artifacts/track-portfolio.json)：T1–T5 独立 evaluator 收据。
- [artifacts/portfolio-status.md](artifacts/portfolio-status.md)：五轨状态、开放 gate 和发布边界。
- [artifacts/t1-nasa-factsheet-audit.json](artifacts/t1-nasa-factsheet-audit.json)：T1 圆整参数敏感性与未通过的外部来源 gate。
- [artifacts/t1-external-orbit-audit.json](artifacts/t1-external-orbit-audit.json)：十例远日点积分及错误引力方向负例的固定环境收据。
- [artifacts/t1-external-run-audit.json](artifacts/t1-external-run-audit.json)：可选外部求解器 Run 的回放、策略拒绝与篡改负例。
- [artifacts/t1-combined-cli-audit-v4.json](artifacts/t1-combined-cli-audit-v4.json)：组合式 T1 Run 与历史版本路由回放。
- [artifacts/t1-de440s-ephemeris-audit.json](artifacts/t1-de440s-ephemeris-audit.json)：固定日期、来源哈希和使命边界收据。
- [artifacts/t1-de440s-run-audit.json](artifacts/t1-de440s-run-audit.json)：星历快照 Run 的搬移回放、策略拒绝和篡改负例收据。
- [artifacts/t1-mars-center-ephemeris-audit.json](artifacts/t1-mars-center-ephemeris-audit.json)：MAR099s 来源校验、火星中心状态与任务边界收据。
- [artifacts/t1-maven-source-audit.json](artifacts/t1-maven-source-audit.json)：MAVEN 重建巡航 SPK 来源、坐标链和探索性采样边界收据。
- [artifacts/t1-maven-ops-event-search-audit.json](artifacts/t1-maven-ops-event-search-audit.json)：PDS 运行事件目录的固定窗口筛选、来源哈希和证据边界。
- [artifacts/t1-maven-sff-exploratory-audit.json](artifacts/t1-maven-sff-exploratory-audit.json)：NAIF 小力文件的事后来源盘点和未入模边界。
- [artifacts/t1-maven-preflight-run-audit.json](artifacts/t1-maven-preflight-run-audit.json)：短弧 RK4 快照 Run 的搬移回放、篡改失败和策略拒绝收据。
- [artifacts/wheel-audit.json](artifacts/wheel-audit.json)：独立 wheel 安装、九个当前 Run 家族与九个历史控制台回放。
- [artifacts/relocation-audit.json](artifacts/relocation-audit.json)：复制源码目录后的八份回放与篡改失败收据。
- [artifacts/replay-environment-audit.json](artifacts/replay-environment-audit.json)：固定环境的版本闭包与八份 manifest 核验。
- [artifacts/acceptance-runs-v18/run-02a00f229aabd3d2/report.md](artifacts/acceptance-runs-v18/run-02a00f229aabd3d2/report.md)：当前 T1 回放报告。

## 非目标

首版不做自主联网爬虫、自动发表、多租户、大模型训练、自动声称新物理或 Web UI。
