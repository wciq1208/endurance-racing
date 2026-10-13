# endurance-racing

耐力赛车队经理的 agent skill 集合：采集赛事成绩、赛会公告和雷达回波，通过代码计算配速、时间差与进站成本，为用户指定的车队提供策略建议。

每个赛事独立一个 skill；当前支持湖南／株洲国际卡丁车场24小时耐力赛。赛事接口使用游客查询，无需微信登录。

## ⚡️ 启动

环境：Windows/macOS/Linux、Python 3.10+ 和 [uv](https://docs.astral.sh/uv/getting-started/installation/)。安装 uv 后，在项目根目录同步依赖（uv 会创建 `.venv`，缺少合适的 Python 时会自动下载）：

```sh
uv sync --locked
```

依赖统一声明在 `pyproject.toml`，版本由 `uv.lock` 锁定：NumPy 用于雷达外推，Pillow 用于图片处理，Matplotlib 用于绘图。psutil 用于进程识别与清理，portalocker 用于跨平台文件锁；接口请求和 CSV 查询使用 Python 标准库。运行命令统一使用 `uv run python`，无需手动激活虚拟环境。

将 Codex、Claude Code 或 Hermes 的**项目/工作目录设为这个仓库根目录**（包含 `pyproject.toml` 的 `endurance-racing` 文件夹），不要设为 skill 子目录。命令行使用时，先 `cd` 到该目录，再启动对应 harness；桌面应用选择“打开项目/文件夹”。

| Harness | 入口与准备 |
| --- | --- |
| Codex | 读取根目录 `AGENTS.md` 和 `.agents/skills/` |
| Claude Code | 根目录 `CLAUDE.md` 引入项目约定，`.claude/skills/` 薄入口引用正式skill |
| Hermes | 支持项目skill发现的版本可读取 `.agents/skills/`；在仓库根目录执行 `hermes skills trust`，再进入该项目会话 |

统一发送这句话即可，不需要记住skill目录：

> 启动株洲24小时耐力赛车队经理，车队是「完整车队名称」，每1分钟检查并给策略。

赛事名也可写为 **株洲24**、**株洲24小时卡丁车耐力赛** 或 **湖南24小时**。未指定车队名时，agent会先询问。指定年份可加“使用2026年赛事”；历史测试说：

> 用2025年历史数据测试株洲24车队经理，车队是「丰速上海宝山来开赛车SDT 一队」，每1分钟检查并给策略。

停止时说“停止车队经理和采集”。如果宿主未发现skill，可明确要求它读取根目录 `AGENTS.md` 和 `.agents/skills/z24-race-manager/SKILL.md`。

也可以在仓库根目录直接诊断和启动采集。以下单行命令适用于 PowerShell、bash 和 zsh：

```sh
uv run python .agents/skills/z24-race-manager/scripts/race_live.py doctor
uv run python .agents/skills/z24-race-manager/scripts/race_live.py start --year 2026 --team '完整车队名称'
```

启动器自动识别操作系统：Windows 使用分离后台进程，macOS/Linux 使用独立会话；按脚本路径及本次随机token清理所有采集进程，包括遗留子进程，不按进程名称批量结束Python。

**每次启动会停止该skill的旧进程，并删除其旧产出，包括CSV、图片、分析结果和日志。** 需要保留的记录请提前导出。其他赛事skill的运行数据不受影响。

天气采集默认每2分钟轮询，成绩和公告默认每1分钟轮询，单路失败持续重试，不阻断其他路。脚本不调用LLM；AI策略分析由活跃的agent会话每1分钟执行。启动参数`--interval`控制成绩/公告间隔，`--weather-interval`独立控制天气间隔，单位均为秒。

## 输出与常用命令

当前产出位置由 `.runtime/z24-race-manager/active.json` 指定，主要文件为：

| 文件 | 用途 |
| --- | --- |
| `radar.png` | 雷达回波源帧及实验外推，标注采集和源帧时间 |
| `all_class.csv` | 全场成绩，第一行为采集元数据 |
| `control_message.csv` | 完整赛会公告，第一行为采集元数据 |
| `analysis/` | 按需补查的逐圈记录及配速计算结果 |

```sh
# 查询状态
uv run python .agents/skills/z24-race-manager/scripts/race_live.py status

# 停止采集
uv run python .agents/skills/z24-race-manager/scripts/race_live.py stop

# 用2025历史赛事测试采集（不是实时比赛）
uv run python .agents/skills/z24-race-manager/scripts/race_live.py start --mode test --discovery tests/fixtures/discovery-2025.json --team '丰速上海宝山来开赛车SDT 一队'
```

## 目录结构

```text
endurance-racing/
├── pyproject.toml                    # uv项目配置与Python依赖
├── uv.lock                           # 锁定依赖版本，提交Git
├── CLAUDE.md                         # Claude Code项目入口
├── .claude/skills/                   # 引用正式skill的薄入口
├── .github/workflows/tests.yml       # Windows/macOS/Linux测试矩阵
├── AGENTS.md                         # 项目约定、赛事skill路由
├── .agents/skills/
│   └── z24-race-manager/
│       ├── SKILL.md                  # 株洲赛事流程和策略规则
│       ├── agents/openai.yaml        # Skill展示信息
│       ├── references/               # CSV字段、补充接口和策略方法
│       └── scripts/                  # 启动器、赛事采集、查询和计算
├── scripts/                          # 通用天气采集、外推、绘图
├── tests/
│   └── fixtures/                     # 历史测试配置，与运行产出隔离
├── docs/                             # 架构、使用说明和接口文档
├── .runtime/<skill-id>/              # 运行状态和产出，不入Git
│   ├── active.json                   # 当前运行ID、进程及输出路径
│   └── outputs/<run-id>/
└── .gitignore
```

新增赛事放入 `.agents/skills/<赛事skill>/`，规则及接口逻辑留在该skill内。天气脚本通过参数复用：株洲启动器传入经纬度 `27.8206, 113.062648`、雷达站 `az9731` 和场地名称，公共天气脚本不依赖任何赛事skill。

`.venv/`、`.runtime/`、各层 `__pycache__/`、`*.pyc`、`.env` 和 `.DS_Store` 已被Git忽略。

## 🧪 验证与说明

```sh
uv run python -m unittest discover -s tests
```

- 已实现Windows/macOS/Linux分支；当前本机只实测macOS，Windows/Linux由测试矩阵验证，未运行CI前不宣称通过。
- `doctor`检查系统、依赖、文件锁、进程访问和中文字体。缺字时安装Noto Sans CJK SC或使用系统已有中文字体。
- agent还需确认宿主能执行命令、看图和可中断等待；脚本无法替宿主证明这些能力。不能看图时仍可分析CSV。
- 后台采集不等于每1分钟AI分析。持续策略需宿主保持活跃执行；休眠、会话结束或缺少持续运行能力时，模型不会自动保持工作。
- 雷达外推为实验估计；天气失败不影响赛事分析。
- 历史最终成绩不代表某个赛中时刻的排名；进站建议需注明数据依据和假设。

详细操作见[车队经理使用说明](docs/race-manager.md)；扩展赛事前阅读[项目架构](docs/architecture.md)。接口与天气来源分别见[MyRacing接口说明](docs/myracing-api-guide.md)和[雷达说明](docs/weather-radar.md)。

宿主入口依据：[Claude Code skills](https://code.claude.com/docs/en/skills)、[Hermes项目skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills#project-local-skills)。Claude Code/Hermes入口尚未在本机对应harness中端到端验证。
