# CSV和图片契约

启动路径为项目根目录的 `.agents/skills/z24-race-manager/scripts/race_live.py`。本次目录从启动结果或 `.runtime/z24-race-manager/active.json` 读取，不硬编码历史run。

## 文件

- `all_class.csv`：完整当前成绩，每轮原子替换。
- `control_message.csv`：完整赛会公告，含历史更正，每轮原子替换。
- `radar.png`：回波源帧＋5/10/20分钟实验外推，顶部第一行采集时间，第二行场地，源帧时间另列；失败时为明确失败卡。PNG text元数据含status、run_id、collected_at、attempted_at、source_time、经纬度。
- 其他目录仅为配置、日志、原始雷达缓存及历史CSV归档；主分析输入是以上三个文件。

CSV为UTF-8，第一行是键值交错元数据：`# collected_at,时间,attempted_at,时间,status,ok,...`；第二行为标准列名，后续为标准CSV，可包含正确引号包围的多行公告。采集失败时collected_at留空，attempted_at更新，status=error，表格无数据行，不能将空表解释成无人参赛或无公告。waiting同理。

Python标准读取：

```python
import sys
sys.path.insert(0, '.agents/skills/z24-race-manager/scripts')
from race_live_common import read_csv
meta, columns, rows = read_csv('本次目录/all_class.csv')
```

pandas读取数据用 `pd.read_csv(path, skiprows=1, dtype={'carNo':str,'id':str})`，元数据另用read_csv取。不要用简单split逗号。车号和ID是标识符，保留前导零。

## 查询与字段

```sh
uv run python .agents/skills/z24-race-manager/scripts/race_csv_query.py '本次目录/all_class.csv' --sql 'SELECT carNo,carTeam,pos,laps,bestTm/1000.0 AS best_seconds,diff,gap FROM data ORDER BY pos LIMIT 10'
uv run python .agents/skills/z24-race-manager/scripts/race_csv_query.py '本次目录/control_message.csv' --sql 'SELECT "index",c_time,cont FROM data ORDER BY "index" DESC LIMIT 20'
```

查询工具返回CSV和query_now、age_seconds、fresh，SQL只读。用户车队名作为SQL值时使用正确参数绑定或Python筛选，不直接拼接未转义输入。先在完整表中用carTeam/nicname精确匹配；重复或没有匹配时不要自选目标。

|字段|含义|
|---|---|
|id|成绩条目或公告ID，非pid|
|carNo|车号，字符串|
|carTeam / nicname|车队显示名称，用于精确匹配|
|pos / pic|接口总名次/组别名次，保留原始值|
|laps|完成圈数|
|bestTm / totalTm|毫秒；最佳圈/累计计时，后者不能直接当当前时钟|
|bestLap|最佳圈所在圈次|
|diff / gap|负数为落后圈数；正数为毫秒差；零不可无条件解释为实时并排|
|pitstops|若接口有提供则保留；空白不是0，不能当作进站时间戳|
|st|原始条目状态码，未核实含义不自行解释|
|index / c_time / cont|公告序号/接口发布时间原文/完整正文；时间没有时区时不要默认为UTC|

额外标量字段原名保留，未核实单位不自行推断。运行失败、当前时间变化或快照之间并非同一时刻，都需体现在结论置信度里。
