# 湖南24小时车队经理

交互与输出见[演示样例](examples.md)，这些早期演练截图仅示意。当前流程使用Pydantic通用CSV与雷达PNG，CSV字段与旧上游透传格式不同。

## 使用

在仓库根目录启动harness，发送“启动株洲24小时耐力赛车队经理，车队是「完整车队名称」，每1分钟检查并给策略”。agent按AGENTS.md确认赛事和skill后启动。

```sh
uv sync --locked
uv run python .agents/skills/z24-race-manager/scripts/race_live.py doctor
uv run python .agents/skills/z24-race-manager/scripts/race_live.py start --year 2026 --team '完整车队名称'
uv run python .agents/skills/z24-race-manager/scripts/race_live.py status
uv run python .agents/skills/z24-race-manager/scripts/race_live.py stop
```

历史测试显式用`--mode test --discovery tests/fixtures/discovery-2025.json`；2025静态终局数据不代表赛中排名，逐圈可按映射时钟截断。换人最低进站180秒与净比赛损失分别处理；无蓝旗，不假设让车。

start停止本skill旧进程后，清理本skill旧运行目录和公开资源，创建新run并原子发布运行指针。发现失败不保留旧active，stop停止采集并移除公开/私有指针。其他skill不受影响；需要保留数据请提前另行导出。旧SQLite及旧接口CSV不自动迁移，不作为当前输入。

## 通用CSV与Python计算

`.runtime/z24-race-manager/active.json`指向本次data_output。公开目录为`.runtime/public/race-data/z24-race-manager/<run_id>/`：results.csv、control_messages.csv、laps.csv、pace.csv、weather.csv及radar.png。配置、日志、雷达缓存仍在私有outputs/run_id。天气120秒，成绩公告60秒独立采集；单路异常重试、worker退出由监督进程重启。

采集器先将MyRacing字段转为race_data/models.py模型；整批校验后在目标同一目录写临时文件，fsync并os.replace。首行带采集时间与版本化envelope，次行固定通用列；数字统一秒数，圈差单独存储，车号和ID保持字符串。NULL与空字符串明确区分。失败发布error空表，waiting不冒充成功。

```sh
uv run python .agents/skills/z24-race-manager/scripts/race_csv_read.py --run-id '当前token' --dataset results
uv run python .agents/skills/z24-race-manager/scripts/race_laps.py --run-id '当前token' --team '完整车队名称' --all-cars --replay-cycle
```

agent用race_csv_read.load获取完整校验模型，再用Python筛选、聚合和计算，不用SQL。详见[通用CSV契约](../.agents/skills/z24-race-manager/references/csv.md)与[策略计算](../.agents/skills/z24-race-manager/references/strategy-data.md)。需要同时读取laps/pace时校验snapshot_id；天气失败继续分析有效赛事CSV。

## 静态看板

```sh
npm ci --prefix frontend
npm run dev --prefix frontend
```

打开终端提示的地址（默认http://127.0.0.1:5173）。也可以`npm run build --prefix frontend`后`npm run preview --prefix frontend`。只有Vite静态服务器，无业务后端、数据库或任意SQL接口。React直接读取静态CSV/PNG并禁用缓存、核对run、验证通用结构、分别显示新鲜度；前端从逐圈CSV计算上一圈和最近10圈均值、中位数与最快圈速，合并到可折叠成绩表；雷达与公告在顶部并排，整行可折叠。agent的策略仍在会话中给出。

修改Pydantic模型后执行`uv run python scripts/export_csv_schema.py`，与frontend/src/csv-schema.json一起提交。构建会自动重新导出；CI运行Python测试、前端解析/计算测试与构建。
