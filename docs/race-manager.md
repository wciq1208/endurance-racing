# 湖南24小时车队经理

交互与输出示例见[车队经理演示样例](examples.md)，包含前后车配速、雷达回波、进站窗口及追近机会分析。

## 目录

- `.agents/skills/z24-race-manager/SKILL.md`：agent流程、策略规则及数据使用边界。
- `.agents/skills/z24-race-manager/scripts/`：启动器、独立成绩/公告采集、游客接口、赛事发现、CSV查询、逐圈分析和赛程时钟。
- `.agents/skills/z24-race-manager/references/`：CSV契约及补充接口/策略方法。
- `scripts/`：雷达采集、绘图、字体和天气依赖。
- `tests/fixtures/`：历史测试配置，不是可用于实时分析的产出。
- `.runtime/z24-race-manager/active.json`：当前进程组、运行ID及产出位置。
- `.runtime/z24-race-manager/outputs/<run_id>/`：本次PNG、两份CSV、analysis、archive、日志和天气缓存；重新启动会全部清空。

## 运行

Python 3.10+、uv，Windows/macOS/Linux（启动器自动识别系统）。在项目根目录执行：

```sh
uv sync --locked
uv run python .agents/skills/z24-race-manager/scripts/race_live.py start --year 2026 --team '车队完整名称'
uv run python .agents/skills/z24-race-manager/scripts/race_live.py status
uv run python .agents/skills/z24-race-manager/scripts/race_live.py stop
```

2025接口测试：

```sh
uv run python .agents/skills/z24-race-manager/scripts/race_live.py start \
  --mode test --discovery tests/fixtures/discovery-2025.json \
  --team '丰速上海宝山来开赛车SDT 一队'
```

每次start先停止并确认旧进程退出，再清空受管产出目录。删除范围固定为`.runtime/z24-race-manager/outputs/`，拒绝运行目录符号链接；不根据外部输入路径删除其他文件。发现失败时也没有旧产出可误读。首次请求完成前CSV和图片明确标为waiting。每路独立轮询，默认天气120秒、成绩和公告60秒；错误继续重试，worker退出由监督进程重启。stop停止进程并移除当前指针，产出留到下次start清理。若需保留记录，应在重启前由用户另行导出到受管目录以外。

主输入为radar.png、all_class.csv、control_message.csv。CSV首行为采集元数据，第二行列名；PNG顶部标采集时间并内嵌元数据。失败输出明确标错，不冒充无雨或无公告。查询建议携带启动结果的token：

```sh
uv run python .agents/skills/z24-race-manager/scripts/race_csv_query.py '当前目录/all_class.csv' \
  --run-id '当前token' --sql 'SELECT carNo,carTeam,pos,laps FROM data ORDER BY pos LIMIT 10'
```

逐圈补查输出在本次analysis目录；详细用法见skill引用文档。启动器默认live拒绝已结束场次，测试必须显式标记test；这不把历史终局成绩自动转换成真实回放。

脚本以自身位置定位项目，不依赖个人绝对路径；运行时路径由本次启动生成，移动项目后重新启动。天气字体需系统安装中文字体（例如Noto Sans CJK SC），未安装可能缺字。AI每1分钟读取并解释数据依赖活跃会话；采集脚本不会自动唤醒LLM。

验证：`uv run python -m unittest discover -s tests`。旧MD流程、SQLite采集器、Raceby逆向工具和历史测试产出已经移除，可从Git历史找回此前已提交的文件。

项目名称为endurance-racing。本skill的雷达站、经纬度和地名统一定义在启动器VENUE_WEATHER中，调用根目录天气脚本时显式传参。公共天气脚本不导入任何赛事skill。多赛事结构与剩余能力边界见architecture.md。
