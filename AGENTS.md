# endurance-racing

本项目按赛事组织agent skill。`.agents/skills/<赛事skill>/SKILL.md`定义该赛事的流程与规则，赛事专属脚本放其`scripts/`，通用天气工具放根目录`scripts/`。

根据用户指定的赛事选择skill；“株洲24小时耐力赛”“株洲24”“株洲24小时卡丁车耐力赛”“湖南24小时”均使用`z24-race-manager`，运行必须指定车队完整名称。新增赛事独立建skill，不将其参数和规则写入公共天气脚本。

运行状态按skill隔离：`.runtime/<skill-id>/active.json`指向唯一当前产出。启动只停止本skill的旧进程并清空本skill的outputs；必须核对run_id与采集时间。历史测试显式使用`--mode test`，不将fixture当作当前赛况。

## 唤醒后的启动确认

用户唤醒车队经理后，先识别赛事并读取对应skill，在执行启动命令前向用户明确列出**赛事名和skill名**并请求确认。例如：“确认启动赛事「株洲24小时耐力赛」，使用skill「z24-race-manager」吗？”若缺少车队完整名称，在同一次询问中补齐。

只有用户明确确认本次赛事与skill的组合，且已提供车队完整名称后，才继续启动采集与策略分析。未确认、回答含糊或用户要求调整时，保持等待；不得启动、重启、清理旧进程或删除旧产出，不得将超时或沉默当作确认。用户调整赛事或skill后，重新展示调整后的组合并请求确认。同一次启动已确认且组合未变时，不重复询问；正常后续轮询无需再次确认。

## Python环境与依赖

项目依赖uv，先按[官方安装说明](https://docs.astral.sh/uv/getting-started/installation/)安装uv。以下命令均在项目根目录执行：

```sh
# 按已提交的锁文件安装依赖，自动创建.venv
uv sync --locked

# 执行脚本（示例仅查询状态，不启动采集）
uv run python .agents/skills/z24-race-manager/scripts/race_live.py status

# 运行测试
uv run python -m unittest discover -s tests
```

要求Python 3.10+、Windows/macOS/Linux；uv可在缺少合适解释器时自动下载Python。所有采集、查询、分析与测试命令均使用`uv run python`，不要依赖全局Python环境。子进程使用`sys.executable`继承同一个环境。

依赖仅维护在根目录`pyproject.toml`，新增或删除依赖使用`uv add 包名`、`uv remove 包名`；手动修改配置后执行`uv lock`及`uv sync --locked`，验证测试后一起提交`pyproject.toml`和`uv.lock`。`.venv/`和`__pycache__/`不提交Git。

启动harness时将工作目录设为仓库根目录。首次启动先执行skill启动器的`doctor`命令，检查当前宿主的命令执行、看图和可中断等待能力；无法持续运行模型时明确告知，不把后台采集说成持续AI分析。Claude Code的入口位于`.claude/skills/`，仅引用`.agents/skills/`内的正式skill，不复制策略正文。
