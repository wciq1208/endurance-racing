# endurance-racing

项目是面向多赛事的agent技能集合，没有独立于宿主的LLM运行服务。没有唯一强制的“标准agent目录”，本项目采用以下边界：

- CLAUDE.md和.claude/skills：Claude Code薄入口，只引用正式约定和skill。Hermes通过项目skills信任流程发现.agents/skills。
- AGENTS.md：项目路由和通用约定，不混入某场赛事规则。
- .agents/skills/<skill-id>/SKILL.md：该赛事的决策流程和输出要求；references按需展开字段与方法。
- 同skill的scripts：赛事数据工具、确定性计算、启动和监督。
- 根目录scripts：无赛事反向依赖的公共天气工具；由skill提供位置、雷达站、标签、输出路径、run_id和间隔。
- .runtime/<skill-id>：各赛事运行隔离；重启清理只影响本skill。当前产出只认active.json，数值结论依赖代码计算。

株洲skill启动器中定义VENUE_WEATHER，传给公共天气脚本的参数为`--lat 27.8206 --lon 113.062648 --station az9731 --location 株洲国际卡丁车场`。公共脚本不自动寻找最近雷达站：经纬度必须在给定站点图幅范围内，否则输出错误状态，不把错误场地图当可用数据。

当前仍有的边界：

1. 持续采集与AI决策是两层。宿主活跃会话执行决策轮询；后台采集不能保证后台AI被唤醒。需要全天无人值守时，应额外接入具有明确重试、状态恢复和调用预算的agent执行器。
2. 不是独立发布的Python库。skill依赖本仓库布局；复制整个项目可移植，仅复制一个skill时还需公共天气脚本。启动器自动选择Windows或POSIX后台启动方式，使用psutil校验脚本路径和token并清理所有相关进程，使用portalocker加锁。平台验证状态见README。
3. 车手计划、现场反馈和精确出站交通模型仍是策略能力，不是靠目录标准化就能补齐的数据。后续应增加已知输入/预期建议的策略评估用例，区分工具计算测试与模型行为评估。

增加第二个赛事时，使用唯一skill-id和独立运行命名空间；先复用天气CLI，不提前把不同赛事的数据接口强行抽象成同一套协议。
