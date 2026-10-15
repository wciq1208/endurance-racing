# 雷达回波

天气脚本在根目录scripts，常驻入口race_weather.py由skill启动器管理，每2分钟独立轮询。底层weather_radar_collect.py下载中国天气网长沙az9731连续帧，并绘制湖南国际卡丁车场（113.062648E，27.820600N）附近的源帧及+5/+10/+20分钟实验外推。雷达图在当前run目录radar.png，原图缓存同目录weather-cache。

来源：中国天气网 https://www.weather.com.cn/weatherMap/ ，雷达索引 https://img.weather.com.cn/new_radar/json/az9731.json ，定位范围 https://img.weather.com.cn/radarinfo/img_bounds.json 。图中使用原始像素和官方dBZ色标，透明区域不等于确定无雨。

运动估计使用连续帧的实际时间间隔，取有效帧对位移速度中位数；将源帧延迟计入累计外推时间。源图超过45分钟、移动估计不足或不一致时禁用外推；稀疏回波仅允许明确标注的保持基线。不是官方预报，不能预测回波新生、增长或消散，更不能推算赛车场积水深度。经纬度图幅投影为近似定位，不能作赛道弯角级定位。

天气依赖安装：`uv sync --locked`。常规使用统一启动器；单独诊断底层采集需显式指定--output，不能将其产出冒充当前run。天气失败不会阻断成绩和公告；失败卡显示本轮尝试时间，成功图首行显示采集时间，并单独标明源帧时刻。

公共天气入口现已与赛事skill解耦，必须由调用者提供位置、雷达站和名称，例如：

```sh
uv run python scripts/race_weather.py --lat 27.8206 --lon 113.062648 \
  --station az9731 --location '株洲国际卡丁车场' \
  --output '.runtime/z24-race-manager/outputs/当前run' --token '当前run' --interval 120 --mode test
```

正常运行无需手动执行此命令：株洲skill的启动器通过VENUE_WEATHER配置构建完整参数。其他赛事传入其他位置和覆盖该位置的雷达站，公共天气脚本无需修改。天气PNG保持独立文件，并将路径、源帧时间和采集状态发布到Pydantic通用weather.csv；赛事成绩和公告由各自skill转换为统一模型后原子发布CSV。
