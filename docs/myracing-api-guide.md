# MyRacing 接口用途、参数与登录要求

2026-10-12，基于解包代码和公开接口实测。完整参数大小写与调用点见 `myracing-api-inventory.md`。

## 你需要的两个入口

**All Class** 是 `get-race-result-by-pid`，`group=""` 表示全组别成绩；指定组别传 `groupList[].name`，本场示例为 `24H耐力赛`。不是一个名为 all-class 的独立接口。

**Control Message** 是 `get-race-control-by-pid`，查询某场练习、排位或正赛的赛会公告，不是个人消息接口 `get-msg-list`。

两者均已用游客 `userId=0`、空 Token 取得正式比赛数据，无需登录或手机号。结论限于本次公开查询；不能推广到全部个人接口。

## 场地、赛事与场次怎么指定

```text
get-race-station-list → items[].id = 262（株洲入口）
  ↓ ssid=262
get-race-list-group (pid=0) → items[].id = 1018（2025年度赛事）
  ↓ ssid=262, pid=1018
get-race-result-round-list → items[].id = 4322（第七届）
  ↓ ssid=262, pid=4322, itemId=0
get-race-result-ritem-list
  → items[].id = 77378（24小时耐力赛组别/容器）
  → items[].ritems[].id = 2011448（正赛）
  ↓ ssid=262, pid=2011448
All Class / Control Message
  ↓ All Class items[].id = 6311729（25号车成绩记录）
get-race-result-item (ssid=262, pid=6311729) → 逐圈数据
```

`get-race-result-init(uid=0,ssid=262,rid=0)` 可一次取得默认年度赛事和届次，是首次加载的快捷入口。选择另一年度后仍须刷新其届次和场次，不能混用旧ID。

这里 `ssid` 始终是入口场地ID；`pid` 是当前接口所需父级/目标ID。`rid=4322` 在文件接口指届次。年度赛事1018、届次4322、场次2011448不可互换。实时 `itemid` 和历史成绩记录ID也不可想当然互换。

## 两个可直接复现的完整请求

地址：`POST https://kart.xkarting.com/ajax/wxapi.ashx`

Content-Type：`application/x-www-form-urlencoded`

时间变量 `T` 为发请求时的 Unix 毫秒整数。`MD5` 输出32位十六进制字符串。以下是游客请求，前导 `@` 来自空 Token。

```text
# All Class
flag=get-race-result-by-pid
ssid=262
userId=0
pid=2011448
isTest=1
group=
timestamp=T
syskey=MD5("@get-race-result-by-pid@" + T + "@0@2011448")

# Control Message
flag=get-race-control-by-pid
ssid=262
userId=0
pid=2011448
timestamp=T
syskey=MD5("@get-race-control-by-pid@" + T + "@0@2011448")
```

`isTest=1` 是原客户端固定传参，本次返回正式2025正赛，不能按字面将它解释为“只取测试赛”。All Class 返回 `items`、`groupList`、`round`；Control Message 返回公告 `items`，本场分别30条和107条。

已有请求工具会自动生成时间戳及正确签名：

```sh
uv run python .agents/skills/z24-race-manager/scripts/myracing_read.py get-race-result-by-pid '{"ssid":262,"userId":0,"pid":2011448,"isTest":1,"group":""}'
uv run python .agents/skills/z24-race-manager/scripts/myracing_read.py get-race-control-by-pid '{"ssid":262,"userId":0,"pid":2011448}'
```

## 实时成绩与实时赛会信息

`get-result-realtime-race` 传 `ssid,uid,pid,tab,itemid,timeStamp,syskey`。

- 首次 `pid=0,itemid=0,uid=0`，读取响应 `RaceList` 和 `raceItem.id`；后续选择真实返回的可用场次ID。
- `tab=1` Team Info，`2` Pos Info，`3` Result Info，`4` 分段成绩，`5` 赛会信息。客户端均用同一接口，但响应字段可能随tab变化。
- `itemid=0` 不展开单车；展开时传当前实时 `items[].id`。
- 游客签名为 `MD5("@get-result-realtime-race@" + T + "@0")`。
- 原页面约5秒请求一次。这个周期不等于服务端保证5秒内更新。
- **历史正赛ID不能直接套用**：传2011448本次仍返回2133495 TEST01。必须核对响应ID。
- tab=5此次返回 `flag=1,msg="暂无比赛#3"`，没有公告items；不能把它当成历史107条公告的替代接口。

## 全部58个业务接口

参数列省略 `flag` 与时间戳/签名公共字段；不同调用变体取并集，完整逐调用差异见原清单。公共字段存在大小写差异，不能自行统一。用途中未实测内容按客户端调用上下文说明。

“账户功能”表示语义上依赖当前用户，应通过正常登录会话使用；本次没有验证服务端对游客的具体拒绝行为。“未验证”不能理解为必须登录。

| flag | 作用 | 业务参数（不含时间戳/签名） | 登录结论 |
|---|---|---|---|

| `add-station-black` | 将场地加入个人黑名单/屏蔽（按调用命名，具体服务端行为未验证） | `sid`, `uid` | 账户功能，登录态使用；未实测 |
| `change-station` | 切换当前关注场地 | `ssid`, `uid` | 账户功能，登录态使用；未实测 |
| `create-member-qrcode` | 生成会员二维码 | `uid`, `is_test`, `userId` | 账户功能，登录态使用；未实测 |
| `create-member-qrcode-safe` | 生成安全版会员二维码 | `uid`, `is_test`, `userId` | 账户功能，登录态使用；未实测 |
| `create-station-user` | 建立场地会员/关注关系 | `uid`, `userId`, `ssid`, `nicname`, `photo`, `gender`, `country`, `province`, `city` | 账户功能，登录态使用；未实测 |
| `create-ticket-request` | 提交用票/发车预约 | `ssid`, `userId`, `id`, `rid`, `car`, `name`, `nicname` | 账户功能，登录态使用；未实测 |
| `get-calender-list` | 商城/活动列表（原flag拼写如此，未注册旧页面） | `ssid`, `userId`, `tid`, `pn` | 未实测登录要求 |
| `get-goods-buy` | 购买页商品资料（不是已验证下单接口） | `ssid`, `userId`, `id` | 未实测登录要求 |
| `get-goods-by-id` | 商品详情 | `ssid`, `userId`, `id` | 未实测登录要求 |
| `get-member-point-logs-by-id` | 积分记录详情 | `userId`, `id` | 账户功能，登录态使用；未实测 |
| `get-member-point-logs-list` | 积分记录列表 | `ssid`, `userId`, `status`, `pn` | 账户功能，登录态使用；未实测 |
| `get-msg-by-id` | 个人消息详情；不是赛会公告 | `userId`, `id` | 账户功能，登录态使用；未实测 |
| `get-msg-list` | 个人消息列表；不是Control Message | `ssid`, `userId`, `status`, `pn` | 账户功能，登录态使用；未实测 |
| `get-order-list` | 个人订单列表 | `ssid`, `userId`, `status`, `pn` | 账户功能，登录态使用；未实测 |
| `get-orderinfo-by-id` | 订单详情 | `userId`, `id` | 账户功能，登录态使用；未实测 |
| `get-race-calendar-init` | 赛程页初始化，年度赛事列表 | `ssid`, `userId`, `pid` | 无需登录，实测成功 |
| `get-race-calendar-list` | 届次下赛程/场次列表 | `ssid`, `userId`, `itemId`, `pid` | 无需登录，实测成功 |
| `get-race-control-by-pid` | Control Message：指定场次的赛会公告 | `ssid`, `userId`, `pid` | 无需登录，实测成功 |
| `get-race-docs-by-id` | 赛事文件详情 | `userId`, `ssid`, `id` | 未实测登录要求 |
| `get-race-docs-init` | 赛事文件分类与当前届次初始化 | `ssid`, `userId`, `rid` | 无需登录，实测成功 |
| `get-race-docs-list` | 指定届次、分类的赛事文件列表 | `ssid`, `userId`, `cid`, `rid` | 游客返回暂无数据，未确认有数据时行为 |
| `get-race-docs-search` | 赛事文件搜索/筛选（参数id具体业务语义待验证） | `userId`, `id`, `ssid` | 未实测登录要求 |
| `get-race-list-group` | 场地/场地组下的年度赛事列表 | `ssid`, `userId`, `pid` | 无需登录，实测成功 |
| `get-race-list-user` | 当前用户关注的赛事/场地 | `uid` | 账户功能，登录态使用；未实测 |
| `get-race-result-by-pid` | All Class或指定组别的场次成绩 | `ssid`, `userId`, `pid`, `isTest`, `group` | 无需登录，实测成功 |
| `get-race-result-init` | 成绩页初始化：赛事、届次、场地分组 | `uid`, `ssid`, `rid` | 无需登录，实测成功 |
| `get-race-result-item` | 某参赛成绩记录的逐圈明细 | `ssid`, `userId`, `pid` | 无需登录，实测成功 |
| `get-race-result-ritem-list` | 届次下组别和练习/排位/正赛场次 | `ssid`, `userId`, `pid`, `itemId` | 无需登录，实测成功 |
| `get-race-result-round-list` | 年度赛事下的届次列表 | `ssid`, `userId`, `pid` | 无需登录，实测成功 |
| `get-race-result-top` | 赛事圈速排行榜，可按tname筛选 | `uid`, `ssid`, `pid`, `tname` | 未实测登录要求 |
| `get-race-round-list` | 赛程页使用的届次列表 | `ssid`, `userId`, `pid` | 未实测登录要求 |
| `get-race-station-list` | 公开场地/赛事组织目录，支持分页与分类 | `uid`, `tid`, `cid`, `pn` | 无需登录，实测成功 |
| `get-result-init` | 场地成绩/排行榜初始化 | `uid`, `ssid` | 未实测登录要求 |
| `get-result-realtime` | 场地页实时成绩（区别于赛事实时接口） | `uid`, `ssid`, `itemId` | 未实测登录要求 |
| `get-result-realtime-race` | 赛事实时成绩；tab=5为实时赛会信息视图 | `ssid`, `uid`, `tab`, `pid`, `itemid` | 无需登录，实测成功 |
| `get-result-top` | 场地总榜 | `uid`, `ssid`, `team` | 未实测登录要求 |
| `get-result-top-date` | 场地指定日期榜 | `uid`, `ssid`, `team`, `date` | 未实测登录要求 |
| `get-result-top-month` | 场地月榜 | `uid`, `ssid`, `team`, `year`, `month` | 未实测登录要求 |
| `get-result-top-week` | 场地周榜 | `uid`, `ssid`, `team`, `year`, `weeks` | 未实测登录要求 |
| `get-result-top-year` | 场地年榜 | `uid`, `ssid`, `team`, `year` | 未实测登录要求 |
| `get-station-by-id` | 场地/赛事组织详情 | `uid`, `id` | 无需登录，实测成功 |
| `get-ticket-info-by-id` | 个人票券详情 | `userId`, `id` | 账户功能，登录态使用；未实测 |
| `get-ticket-list` | 个人票券列表 | `ssid`, `userId`, `status`, `pn` | 账户功能，登录态使用；未实测 |
| `get-ticket-request-cars` | 预约可用车辆 | `ssid`, `userId`, `id`, `rid` | 账户功能，登录态使用；未实测 |
| `get-ticket-request-info` | 用票预约初始化信息 | `ssid`, `userId`, `id` | 账户功能，登录态使用；未实测 |
| `get-ticket-request-round` | 预约可选场次 | `ssid`, `userId` | 账户功能，登录态使用；未实测 |
| `get-user-msg-count` | 个人未读消息数量 | `userID`, `ssid` | 账户功能，登录态使用；未实测 |
| `get-userinfo` | 当前用户资料 | `userId` | 账户功能，登录态使用；未实测 |
| `get-userinfo-by-id` | 指定当前用户ID的资料查询 | `userId`, `userid` | 账户功能，登录态使用；未实测 |
| `update-userinfo` | 更新用户资料 | `uid`, `userID`, `nicname`, `photo`, `gender`, `country`, `province`, `city` | 账户功能，登录态使用；未实测 |
| `update-userinfo-all` | 完整用户资料更新 | `uid`, `userId`, `name`, `nicname`, `gender`, `mobile`, `birthday`, `team`, `nat`, `province`, `city`, `district`, `updateall` | 账户功能，登录态使用；未实测 |
| `update-userinfo-auto` | 自动同步微信用户资料 | `uid`, `userID`, `nicname`, `photo`, `gender`, `country`, `province`, `city` | 账户功能，登录态使用；未实测 |
| `update-userinfo-photo-and-nicname` | 更新头像和昵称 | `uid`, `userID`, `nicname`, `photo` | 账户功能，登录态使用；未实测 |
| `upload-user-photo` | 上传用户照片 | `userid` | 账户功能，登录态使用；未实测 |
| `wx-login` | 微信登录/建立会话 | `ssid`, `wxcode`, `nicname`, `photo`, `gender`, `country`, `province`, `city` | 用于登录，需wx.login提供wxcode |
| `wx-login-race` | 赛事版微信登录/建立会话 | `ssid`, `wxcode` | 用于登录，需wx.login提供wxcode |
| `wx-user-msg-del` | 删除个人消息 | `ssid`, `userId`, `id` | 账户功能，登录态使用；未实测 |
| `wx-user-msg-del-all` | 删除全部个人消息 | `ssid`, `userId` | 账户功能，登录态使用；未实测 |

本次额外验证：年度列表1018/854、2025届次4322均游客可读；`group="24H耐力赛"` 返回30条，与本场唯一组别一致。这不证明该年度有多组别过滤样本。

## 数据处理注意

- `diff/gap` 的负数表示落后圈数，正数为毫秒时间差，不能统一除以1000。
- Control Message 保留 `id,cont,c_time,index,time`，公告正文可能包含事件时间，`c_time` 是发布时间，两者可能相差很久。
- 公告可能更正之前处罚，不能只累加罚圈。
- 没有取得精确进出站时间，`pitstops` 计数不能替代现场停站计时。


## 策略补查更新（2026-10-12）

游客逐圈接口已再次验证25、22、26号2025正式赛，返回毫秒圈速及带日期的过线时间；不应将All Class没有逐圈字段误判为接口无法获取逐圈。新工具 `.agents/skills/z24-race-manager/scripts/race_laps.py` 可从当前run的通用results.csv取真实成绩ID，补查后原子发布通用laps.csv/pace.csv；`--replay-cycle`按当前16:00赛程映射截取历史逐圈，严格排除截止时刻之后的圈。

实时接口tab=4、itemid=618437在TEST01返回lapItems；场次2133495不是2025正赛2011448，不能混用。场地实时接口只返回该TEST场次；排行榜接口对2025正赛返回暂无排行。没有验证到精确进出站或车手交接时间。完整计算规范见 `.agents/skills/z24-race-manager/references/strategy-data.md`。
