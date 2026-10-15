# 无业务后端的静态数据看板

```text
赛事接口 → skill/scripts赛事适配 → Pydantic通用模型 → 原子替换CSV
                                                   ├─ React解析、校验、计算与展示
                                                   └─ agent用Python读取、计算策略
天气接口 → 公共scripts → 雷达PNG + 通用weather.csv ─────┘
```

race_data/models.py定义统一字段、秒单位、字符串标识符、可空值和采集envelope；race_data/csv_io.py负责整批校验、RFC4180编解码与os.replace发布。没有FastAPI或SQLite。前端契约由Pydantic JSON Schema导出，Papa Parse解析CSV、Ajv校验记录；不能用字符串split或自动数值推断处理车号。

当前结果及全量公告每轮替换；逐圈由接口补查历史并按本轮截止过滤，每次替换本轮车队集合，不追加本地历史。laps/pace共用snapshot_id，先写不可变批次目录，再原子切换laps-active.json；读取固定同一指针，发布失败或中断不破坏上一份完整批次。旧批次被替换后保留5分钟供在途读取，再清理。单个CSV不会被读取一半，但多个CSV并非跨文件事务，所以各路必须单独核对采集时间与run。失败发布明确error空表，不能理解为没有参赛者/公告。PNG和weather.csv也独立校验。

公开资源在.runtime/public/race-data/<skill>/<run>/，只有CSV、雷达PNG及安全运行指针可以由Vite静态提供。配置、PID、私有路径、日志与原始雷达缓存放私有run目录。Vite开发和构建预览均禁用资源缓存，路由白名单及realpath限制防止公开其他项目文件。生产部署需自行提供同等静态资源映射；静态看板不承担登录、多租户或公网授权。

启动先停止本skill旧进程，移除私有/公开active指针，清理本skill旧产出，再创建新run，首轮成功前发布waiting CSV。发现失败时保持无active；stop停止并移除指针。其他skill不受清理影响。仅雷达连续帧缓存、启动身份及用户现场反馈需要短期状态；默认不保存历史快照。用户换人/进出站反馈留在会话约束中，不从采集数据臆测。

agent不依赖看板进程，只读通用CSV和PNG并使用Python计算。持续AI分析仍依赖活跃harness；静态看板每30秒刷新不等于后台LLM策略。
