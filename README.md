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
外部 `symbolic-physics-engine` 路径尚未确认，因此首版使用内置的有界符号候选器；
外部引擎适配保持 `blocked`。

长期路线覆盖共享任务契约中的五个科学垂直切片：物理定律发现、因果物理世界、
物理动力学基础、携证模拟和生化协议验证。它们共享审计内核，但分别由领域评估器
验收，不能由一个总分或一次 demo 代替。

## 离线 Quickstart

在一个干净的 Python 3.10+ 环境中执行：

```powershell
python -m pip install -e ".[test]"
python -m pytest -q
python -m auditable_scientist.cli run examples/hohmann/run.json --offline --seed 17 --output-dir artifacts/local-runs
python -m auditable_scientist.cli inspect artifacts/local-runs/run-<input-hash-prefix>
python -m auditable_scientist.cli replay artifacts/local-runs/run-<input-hash-prefix>
python -m auditable_scientist.cli run-track T2 examples/causal/fixture.json --output-dir artifacts/local-track-runs
python -m auditable_scientist.cli replay artifacts/local-track-runs/run-t2-<input-hash-prefix>
```

仓库中已提交的验收收据另用 `python scripts/verify_acceptance.py` 核查；该命令
要求与收据记录的 Python 和依赖版本一致。普通新环境可运行测试及生成自己的运行包，
版本不一致时旧收据会按设计拒绝回放。

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

`run` 的输出目录必须是空目录或新的目录；回放命令会验证输入、代码版本、运行环境、
seed、源码/证据快照、候选顺序和完整计算输出。正式收据和可复核样例位于
`artifacts/acceptance-runs-v18/`。`run-track` 还接受 `T2P`、`T3`、`T3N`、`T4`、`T5` 和相应
的本地 JSON fixture；运行记录会保留工具调用、负例、源码/证据指纹和边界标签。
新版运行包保存输入快照，并使用 `run://`、`root://` 受限路径；五轨已在复制的
源码目录和移动后的 wheel 运行目录中回放。回放仍要求记录的依赖环境与源码字节一致；
跨操作系统和不同依赖版本尚未验收。
T3 的 Velocity-Verlet 与独立实现的固定步长 RK4、解析解和 Euler 负例比较
见 [docs/T3_METHOD.md](docs/T3_METHOD.md)。T3N 是等边三体解析轨道子轨道，
对照独立 RK4 并拒绝错误力方向；它不代表一般多体或真实任务验证，
见 [docs/T3_NBODY_METHOD.md](docs/T3_NBODY_METHOD.md)。另有可选的受扰动三体有限时域
交叉核验，使用已审计的 SciPy DOP853 环境，见 [docs/T3_PERTURBED_METHOD.md](docs/T3_PERTURBED_METHOD.md)；
它尚未纳入核心 Run，也不证明混沌长时精度。T2P 是 100 场景二维小球干预与
反事实子轨道，见 [docs/T2_PHYSICAL_METHOD.md](docs/T2_PHYSICAL_METHOD.md)；它只支持
声明的模拟器内部因果效应，不证明真实世界因果识别。当前七份 CLI 收据在
`artifacts/track-runs-v13/` 和 `artifacts/acceptance-runs-v18/`。

## 当前入口

- [implementation-plan.md](implementation-plan.md)：阶段、依赖、验收和最小实现顺序。
- [source_inventory.json](source_inventory.json)：初始本地来源盘点的历史快照。
- [artifacts/symbolic-engine-audit.json](artifacts/symbolic-engine-audit.json)：新发现的本地符号引擎源码指纹、实现与许可证阻断原因。
- [schemas/run.schema.json](schemas/run.schema.json)：Run、Event、Claim、Evidence 契约草案。
- [docs/EVIDENCE_POLICY.md](docs/EVIDENCE_POLICY.md)：证据等级和禁止性表述。
- [docs/T1_SYMBOLIC_GRAMMAR.md](docs/T1_SYMBOLIC_GRAMMAR.md)：T1 十表达式语法、训练集选择与发现边界。
- [docs/DECISIONS.md](docs/DECISIONS.md)：已确认的范围决策。
- [docs/T3_METHOD.md](docs/T3_METHOD.md)：T3 双后端方法、来源和适用边界。
- [docs/T2_PHYSICAL_METHOD.md](docs/T2_PHYSICAL_METHOD.md)：T2 二维碰撞干预、反事实与科学边界。
- [docs/T3_NBODY_METHOD.md](docs/T3_NBODY_METHOD.md)：T3 等边三体子轨道、解析参照和门槛。
- [docs/T3_PERTURBED_METHOD.md](docs/T3_PERTURBED_METHOD.md)：可选受扰动三体数值交叉核验与边界。
- [docs/T3_SWEEP.md](docs/T3_SWEEP.md)：T3 固定参数与步长网格、收敛门槛和边界。
- [docs/T3_EXTERNAL_SOLVER.md](docs/T3_EXTERNAL_SOLVER.md)：可选 SciPy 交叉核验、版本与许可证来源。
- [artifacts/t3-external-run-audit.json](artifacts/t3-external-run-audit.json)：可选 SciPy Tool/Provider Run 的回放、搬移与篡改负例收据。
- [docs/T4_METHOD.md](docs/T4_METHOD.md)：T4 精确转移见证、完整义务集和证明边界。
- [artifacts/p1-contract-report.md](artifacts/p1-contract-report.md)：P1 工程检查收据。
- [artifacts/acceptance.json](artifacts/acceptance.json)：T1 acceptance 清单和边界。
- [artifacts/track-portfolio.json](artifacts/track-portfolio.json)：T1–T5 独立 evaluator 收据。
- [artifacts/portfolio-status.md](artifacts/portfolio-status.md)：五轨状态、开放 gate 和发布边界。
- [artifacts/wheel-audit.json](artifacts/wheel-audit.json)：独立 wheel 安装与七份 CLI 回放收据。
- [artifacts/relocation-audit.json](artifacts/relocation-audit.json)：复制源码目录后的七份回放与篡改失败收据。
- [artifacts/replay-environment-audit.json](artifacts/replay-environment-audit.json)：固定环境的版本闭包与七份 manifest 核验。
- [artifacts/acceptance-runs-v18/run-02a00f229aabd3d2/report.md](artifacts/acceptance-runs-v18/run-02a00f229aabd3d2/report.md)：当前 T1 回放报告。

## 非目标

首版不做自主联网爬虫、自动发表、多租户、大模型训练、自动声称新物理或 Web UI。
