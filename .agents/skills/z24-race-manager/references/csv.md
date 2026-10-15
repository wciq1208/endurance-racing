# Pydantic通用CSV与雷达契约

模型唯一来源是根目录`race_data/models.py`。赛事adapter将上游结构转换为Result、ControlMessage、Lap等模型；`race_data/csv_io.py`整批重新校验、序列化，然后同目录临时写入、flush/fsync、os.replace原子发布。任何行无效或ID重复时，整批拒绝，不覆盖成功文件。网络失败则单独发布error空表，不把旧成功记录当成新数据。

## 当前文件

本次身份和公开资源路径来自`.runtime/z24-race-manager/active.json`的token/data_output；公开目录为`.runtime/public/race-data/z24-race-manager/<run_id>/`。启动清理本skill旧产出，只保留本轮数据；日志和配置在私有`.runtime/z24-race-manager/outputs/`。不要搜索旧CSV或SQLite。

|文件|模型与用途|
|---|---|
|results.csv|Result：完整当前成绩，固定通用列|
|control_messages.csv|ControlMessage：完整公告，保留原文和更正|
|laps.csv|Lap：按需补查的本轮逐圈，覆盖而非追加|
|pace.csv|LapAnalysis：本轮每车配速、截止时间及状态，扁平列|
|weather.csv|WeatherFrame：雷达图相对路径、源帧时间与外推状态|
|radar.png|直接读取的源帧与实验外推，独立校验PNG元数据|

每份CSV第一行四格：`# collected_at,成功采集时间,envelope,JSON元数据`，JSON在CSV标准引号内；第二行是固定通用列名。envelope含schema_version=2、dataset、snapshot_id、run与collection。空表也始终保留元数据和列名。status为waiting/error时无数据行且collected_at为空，不能推断无人/无公告/无雨。JSON仅是小型元数据，不注入整库；数值分析读取CSV记录。

CSV为UTF-8、RFC4180，支持逗号、引号和多行公告。NULL编码为`\N`，非空文本的反斜杠编码为双反斜杠；所以空字符串、NULL、字面`\N`可以区分。不要split逗号，不要让pandas自动推断车号类型；优先使用提供的读取器解码并Pydantic校验。

## agent读取与计算

```sh
uv run python .agents/skills/z24-race-manager/scripts/race_csv_read.py --run-id '当前token' --dataset results
uv run python .agents/skills/z24-race-manager/scripts/race_csv_read.py --run-id '当前token' --dataset control_messages --limit 1000
```

工具返回query_now、新鲜度、元数据、row_count和限定行数；`--limit`只是展示限制，完整计算使用Python load：

```python
import sys
from pathlib import Path
sys.path.insert(0, '.agents/skills/z24-race-manager/scripts')
from race_csv_read import load
from race_data.csv_io import freshness
meta, rows = load(Path('.runtime/z24-race-manager/active.json'), '当前token', 'results')
assert freshness(meta)['fresh']
target = [r for r in rows if '用户完整车队名' in (r.team_name, r.driver_name)]
assert len(target) == 1
```

标识符是字符串，保留前导零。best_lap_seconds、total_seconds、gap_seconds、leader_gap_seconds统一为秒；gap_laps、leader_gap_laps是正的落后圈数，不能与秒差混算。未知值为None，0不自动表示实时并排。pit_stops是计数，不能替代进出站时间。published_at_source/event_time_source是未强行解析的上游字符串。extra_json只保留未明确语义的额外标量，不能猜单位。

各路采集独立，results和公告不保证同一时刻。读取核对同一run并分别判断年龄：成绩/公告/逐圈120秒，天气240秒；未来超过5秒不可用。laps和pace必须同snapshot_id，更新间隙发现混批就重新读取，不能自行拼接。发布器对同一路整批发布加跨进程锁；逐圈在完整写好新批次后原子切换指针，写入失败或进程中断时保留上一份完整批次。逐圈新鲜度同时检查补查开始及完成时间；pace查询返回每车pace_freshness，实时模式要求analysis_at和received_at均在120秒内，测试模式允许历史analysis_at，但received_at仍须新鲜。

前端用标准CSV解析器及由同一Pydantic模型导出的JSON Schema校验。修改模型后运行`uv run python scripts/export_csv_schema.py`同步契约。前端禁用缓存，读取前后核对公开active.run_id，单路失败不影响其他路。

逐圈文件实际位于`lap-batches/<snapshot_id>/laps.csv`和`pace.csv`，`laps-active.json`是唯一原子提交指针。读取工具先固定指针，再读取同一不可变批次；通用read_csv支持以run目录下的逻辑laps.csv/pace.csv路径读取，直接open时应使用read_lap_batch或lap_batch_folder解析实际路径。指针不存在时兼容上一版根目录CSV；指针存在但无效时拒绝读取。旧批次从被替换起保留5分钟供在途读取，下次成功发布时清理；失败遗留的未引用目录也在后续发布或重启时清理，不作为历史赛况输入。

PNG和weather.csv不是同一文件事务；必须实际看PNG并核对run、采集及源帧时间，不能只信weather.csv。雷达失败继续分析有效CSV。

版本2将通用成绩采集路命名为results；读取器支持升级版本1通用CSV的all_class采集路，写入始终使用版本2。旧接口透传CSV不兼容。
