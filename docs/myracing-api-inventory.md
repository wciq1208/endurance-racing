# MyRacing 接口与参数清单

采样日期：2026-10-12。静态提取 73 个调用变体、58 个业务 flag；不代表每个接口均已实测。唯一未解析项是公共 ajaxRequest 包装器，其调用方已单独提取。

业务地址：`POST https://kart.xkarting.com/ajax/wxapi.ashx`，表单编码；上传地址 `https://kart.xkarting.com/ajax/wxupload.ashx`。成功响应通常 `flag=1`。

大小写必须保留：`userId/userID/userid`、`sysKey/syskey`、`timeStamp/timestamp` 并不统一。表中签名表达式为原客户端局部变量；需结合 api-calls.json 原调用及来源函数解析。

`createSysKey(a,b,...) = MD5(Token + "@" + a + "@" + b + ...)`；未登录时客户端 Token 为空，UID/UserID 为 0。UID 与 UserID 是不同概念。

| flag | 参数 | 来源函数 | 签名调用 |
|---|---|---|---|
| `get-user-msg-count` | `flag`, `timeStamp`, `userID`, `ssid`, `syskey` | `app.js → RefreshMsgNotice` | this.createSysKey(t,e,a) |
| `update-userinfo-auto` | `flag`, `timeStamp`, `uid`, `userID`, `nicname`, `photo`, `gender`, `country`, `province`, `city`, `syskey` | `app.js → updateUserInfoAuto` | this.createSysKey(n,s,t,a) |
| `update-userinfo` | `flag`, `timeStamp`, `uid`, `userID`, `nicname`, `photo`, `gender`, `country`, `province`, `city`, `syskey` | `app.js → updateUserInfo` | this.createSysKey(n,s,t,a) |
| `update-userinfo-photo-and-nicname` | `flag`, `timeStamp`, `uid`, `userID`, `nicname`, `photo`, `syskey` | `app.js → updateUserPhotoAndNicname` | this.createSysKey(s,i,t,a) |
| `wx-login-race` | `flag`, `ssid`, `wxcode` | `app.js → success` | 未使用此签名函数 |
| `create-member-qrcode` | `flag`, `timeStamp`, `uid`, `is_test`, `sysKey` | `pages/back/ecard.js → createDriverQRCode` | e.createSysKey(i,a,t) |
| `create-member-qrcode-safe` | `flag`, `timeStamp`, `uid`, `is_test`, `sysKey` | `pages/back/ecard.js → createSafeQRCode` | e.createSysKey(i,a,t) |
| `get-msg-list` | `flag`, `timeStamp`, `ssid`, `userId`, `status`, `pn`, `syskey` | `pages/message_/index.js → loadData` | t.createSysKey("get-msg-list",o,s) |
| `get-msg-by-id` | `flag`, `timeStamp`, `userId`, `id`, `syskey` | `pages/message_/view.js → loadData` | t.createSysKey(i,n,a,e) |
| `get-goods-buy` | `flag`, `timeStamp`, `ssid`, `userId`, `id`, `syskey` | `pages/store/buy.js → loadData` | t.createSysKey(r,n,e,o) |
| `get-calender-list` | `flag`, `timeStamp`, `ssid`, `userId`, `tid`, `pn`, `syskey` | `pages/store/index.js → loadData` | t.createSysKey(s,o,e) |
| `get-goods-by-id` | `flag`, `timeStamp`, `ssid`, `userId`, `id`, `syskey` | `pages/store/view.js → loadData` | t.createSysKey(n,o,e,i) |
| `get-station-by-id` | `flag`, `uid`, `id`, `timestamp`, `syskey` | `pages/index/index.js → loadStationInfo` | t.createSysKey(o,i,e,a) |
| `wx-login` | `flag`, `ssid`, `wxcode` | `pages/login/index.js → success` | 未使用此签名函数 |
| `get-race-result-init` | `flag`, `timeStamp`, `sysKey`, `uid`, `ssid`, `rid` | `pages/results/index.js → initData` | t.createSysKey(s,n,a,i,r) |
| `get-race-result-ritem-list` | `flag`, `ssid`, `userId`, `pid`, `itemId`, `timeStamp`, `sysKey` | `pages/results/index.js → loadResultList` | t.createSysKey(s,n,a) |
| `get-result-realtime-race` | `flag`, `ssid`, `uid`, `tab`, `pid`, `itemid`, `timeStamp`, `syskey` | `pages/results/index.js → loadResultRealTime` | t.createSysKey(n,o,d) |
| `get-race-result-top` | `uid`, `ssid`, `flag`, `pid`, `tname`, `timeStamp`, `sysKey` | `pages/results/index.js → loadResultTop` | t.createSysKey(s,o,a) |
| `get-race-list-group` | `flag`, `timeStamp`, `ssid`, `userId`, `pid`, `syskey` | `pages/results/index.js → loadRaceList` | t.createSysKey(r,s,a,i) |
| `get-race-result-round-list` | `flag`, `timeStamp`, `ssid`, `userId`, `pid`, `syskey` | `pages/results/index.js → loadRoundList` | t.createSysKey(r,s,a,i) |
| `get-race-list-group` | `flag`, `timeStamp`, `ssid`, `userId`, `pid`, `syskey` | `pages/results/index.js → loadRaceListTop` | t.createSysKey(r,s,a,i) |
| `get-race-result-round-list` | `flag`, `timeStamp`, `ssid`, `userId`, `pid`, `syskey` | `pages/results/index.js → loadRoundTopList` | t.createSysKey(r,s,a,i) |
| `get-race-result-by-pid` | `flag`, `timestamp`, `ssid`, `userId`, `pid`, `isTest`, `group`, `syskey` | `pages/results/view.js → loadResults` | t.createSysKey(n,r,e,i) |
| `get-race-result-item` | `flag`, `timestamp`, `ssid`, `userId`, `pid`, `syskey` | `pages/results/view.js → loadResultItem` | t.createSysKey(o,n,e,i) |
| `get-race-control-by-pid` | `flag`, `timestamp`, `ssid`, `userId`, `pid`, `syskey` | `pages/results/view.js → loadControlMsg` | t.createSysKey(o,n,e,i) |
| `get-race-docs-list` | `flag`, `timeStamp`, `ssid`, `userId`, `cid`, `rid`, `syskey` | `pages/docs/index.js → loadDocumentsList` | t.createSysKey(n,o,e) |
| `get-race-docs-init` | `flag`, `timeStamp`, `ssid`, `userId`, `rid`, `syskey` | `pages/docs/index.js → initData` | t.createSysKey(n,o,e) |
| `get-race-docs-by-id` | `flag`, `timeStamp`, `userId`, `ssid`, `id`, `syskey` | `pages/docs/view.js → loadData` | t.createSysKey(e,n,i,a) |
| `get-race-docs-search` | `flag`, `timeStamp`, `userId`, `id`, `ssid`, `syskey` | `pages/docs/search.js → loadData` | a.createSysKey(i,o,n,t) |
| `get-userinfo` | `flag`, `timeStamp`, `userId`, `syskey` | `pages/user/index.js → loadData` | t.createSysKey("get-userinfo",n,a) |
| `get-race-calendar-init` | `flag`, `timeStamp`, `ssid`, `userId`, `pid`, `syskey` | `pages/calendar/index.js → loadCalendarInit` | t.createSysKey(s,r,e,n) |
| `get-race-round-list` | `flag`, `timeStamp`, `ssid`, `userId`, `pid`, `syskey` | `pages/calendar/index.js → loadRoundList` | t.createSysKey(i,s,e,n) |
| `get-race-calendar-list` | `flag`, `timeStamp`, `ssid`, `userId`, `itemId`, `pid`, `syskey` | `pages/calendar/index.js → loadCalendarList` | t.createSysKey(i,s,e) |
| `get-orderinfo-by-id` | `flag`, `timestamp`, `userId`, `id`, `syskey` | `pages/calendar/view.js → loadData` | t.createSysKey(n,i,a,e) |
| `get-ticket-list` | `flag`, `timeStamp`, `ssid`, `userId`, `status`, `pn`, `syskey` | `pages/ticket/index.js → loadData` | t.createSysKey(o,d,i) |
| `get-ticket-info-by-id` | `flag`, `timestamp`, `userId`, `id`, `syskey` | `pages/ticket/view.js → loadData` | t.createSysKey(n,i,a,e) |
| `update-userinfo-all` | `flag`, `timeStamp`, `uid`, `userId`, `syskey`, `name`, `nicname`, `gender`, `mobile`, `birthday`, `team`, `nat`, `province`, `city`, `district`, `updateall` | `pages/user/userinfo.js → updateUserInfo` | a.createSysKey(i,t,d) |
| `get-userinfo-by-id` | `flag`, `timeStamp`, `userId`, `syskey` | `pages/user/userinfo.js → loadData` | a.createSysKey(i,n,e) |
| `get-userinfo-by-id` | `flag`, `timeStamp`, `userId`, `syskey` | `pages/user/userinfo.js → loadPhoto` | a.createSysKey(i,n,e) |
| `wx-user-msg-del-all` | `flag`, `timeStamp`, `ssid`, `userId`, `syskey` | `pages/message/index.js → ajaxRemove` | t.createSysKey(n,i,e) |
| `get-msg-list` | `flag`, `timeStamp`, `ssid`, `userId`, `status`, `pn`, `syskey` | `pages/message/index.js → loadData` | t.createSysKey("get-msg-list",o,s) |
| `wx-user-msg-del` | `flag`, `timeStamp`, `ssid`, `userId`, `id`, `syskey` | `pages/message/view.js → ajaxRemove` | t.createSysKey(o,s,e,i) |
| `get-msg-by-id` | `flag`, `timeStamp`, `userId`, `id`, `syskey` | `pages/message/view.js → loadData` | t.createSysKey(i,n,a,e) |
| `change-station` | `flag`, `ssid`, `uid`, `timeStamp`, `syskey` | `pages/user/station.js → changeStat` | t.createSysKey(n,i,a,e) |
| `add-station-black` | `flag`, `sid`, `uid`, `timeStamp`, `syskey` | `pages/user/station.js → cancelStat` | t.createSysKey(n,i,a,e) |
| `get-race-list-user` | `flag`, `timeStamp`, `uid`, `syskey` | `pages/user/station.js → loadData` | t.createSysKey(e,n,a) |
| `upload-user-photo` | `flag`, `userid`, `timestamp`, `syskey` | `pages/user/ecard.js → onChooseAvatar` | t.createSysKey(i,s,n) |
| `create-member-qrcode` | `flag`, `timeStamp`, `uid`, `userId`, `is_test`, `sysKey` | `pages/user/ecard.js → createDriverQRCode` | t.createSysKey(n,i,e) |
| `create-member-qrcode-safe` | `flag`, `timeStamp`, `uid`, `userId`, `is_test`, `sysKey` | `pages/user/ecard.js → createSafeQRCode` | t.createSysKey(n,i,e) |
| `get-orderinfo-by-id` | `flag`, `timestamp`, `userId`, `id`, `syskey` | `pages/order/view.js → loadData` | t.createSysKey(i,n,a,e) |
| `get-order-list` | `flag`, `timeStamp`, `ssid`, `userId`, `status`, `pn`, `syskey` | `pages/order/index.js → loadData` | t.createSysKey(o,d,s) |
| `get-race-station-list` | `flag`, `timeStamp`, `uid`, `tid`, `cid`, `pn`, `syskey` | `pages/station/index.js → loadData` | t.createSysKey(i,s,o) |
| `get-result-init` | `flag`, `timeStamp`, `sysKey`, `uid`, `ssid` | `pages/station/view.js → initData` | t.createSysKey(i,s,a,e) |
| `create-station-user` | `flag`, `timeStamp`, `uid`, `userId`, `ssid`, `nicname`, `photo`, `gender`, `country`, `province`, `city`, `syskey` | `pages/station/view.js → createUser` | t.createSysKey(n,o,a,i) |
| `wx-login` | `flag`, `ssid`, `wxcode`, `nicname`, `photo`, `gender`, `country`, `province`, `city` | `pages/station/view.js → success` | 未使用此签名函数 |
| `change-station` | `flag`, `ssid`, `uid`, `timeStamp`, `syskey` | `pages/station/view.js → changeStat` | t.createSysKey(i,s,a,e) |
| `get-station-by-id` | `flag`, `timeStamp`, `uid`, `id`, `syskey` | `pages/station/view.js → loadStationInfo` | t.createSysKey(i,s,a,e) |
| `get-result-top` | `uid`, `ssid`, `flag`, `team`, `timeStamp`, `sysKey` | `pages/station/view.js → loadResultTop` | t.createSysKey(s,o,r) |
| `get-result-top-week` | `uid`, `ssid`, `flag`, `team`, `timeStamp`, `sysKey`, `year`, `weeks` | `pages/station/view.js → loadResultTop` | t.createSysKey(s,o,r) |
| `get-result-top-month` | `uid`, `ssid`, `flag`, `team`, `timeStamp`, `sysKey`, `year`, `month` | `pages/station/view.js → loadResultTop` | t.createSysKey(s,o,r) |
| `get-result-top-year` | `uid`, `ssid`, `flag`, `team`, `timeStamp`, `sysKey`, `year` | `pages/station/view.js → loadResultTop` | t.createSysKey(s,o,r) |
| `get-result-top-date` | `uid`, `ssid`, `flag`, `team`, `timeStamp`, `sysKey`, `date` | `pages/station/view.js → loadResultTop` | t.createSysKey(s,o,r) |
| `get-result-realtime` | `flag`, `uid`, `ssid`, `itemId`, `timeStamp`, `syskey` | `pages/station/view.js → loadResultRealTime` | t.createSysKey(s,n,o) |
| `get-ticket-request-info` | `flag`, `timeStamp`, `ssid`, `userId`, `id`, `sysKey` | `pages/ticket/request.js → loadTicketInfo` | t.createSysKey(n,r,e,i) |
| `get-ticket-request-round` | `flag`, `timeStamp`, `ssid`, `userId`, `sysKey` | `pages/ticket/request.js → loadRoundList` | t.createSysKey(i,n,e) |
| `get-ticket-request-cars` | `flag`, `timeStamp`, `ssid`, `userId`, `id`, `rid`, `sysKey` | `pages/ticket/request.js → loadCarsList` | t.createSysKey(r,s,e,i,n) |
| `create-ticket-request` | `flag`, `timeStamp`, `ssid`, `userId`, `id`, `rid`, `car`, `name`, `nicname`, `sysKey` | `pages/ticket/request.js → createTicketRequest` | t.createSysKey(d,o,e,i) |
| `upload-user-photo` | `flag`, `userid`, `timestamp`, `syskey` | `pages/user/userphoto.js → onChooseAvatar` | t.createSysKey(o,i,n) |
| `upload-user-photo` | `flag`, `userid`, `timestamp`, `syskey` | `pages/user/userphoto.js → success` | t.createSysKey(n,s,i) |
| `get-userinfo-by-id` | `flag`, `timeStamp`, `userid`, `syskey` | `pages/user/userphoto.js → loadData` | t.createSysKey(e,o,a) |
| `get-station-by-id` | `flag`, `uid`, `id`, `timestamp`, `syskey` | `pages/index/map.js → loadStationInfo` | t.createSysKey(n,o,i,a) |
| `get-member-point-logs-list` | `flag`, `timeStamp`, `ssid`, `userId`, `status`, `pn`, `syskey` | `pages/point/index.js → loadData` | t.createSysKey(o,d,n) |
| `get-member-point-logs-by-id` | `flag`, `timestamp`, `userId`, `id`, `syskey` | `pages/point/view.js → loadData` | t.createSysKey(n,i,a,e) |

注意：pages/back、pages/message_、pages/store 下部分模块未在本次 app-config 页面列表注册，不应假定可从界面进入。更新用户资料、关注场地、票务预约、删除消息、上传照片等调用仅静态登记，未执行。

条件参数修正：get-result-top 各分支分别只带相应的 year/weeks/month/date；AST 原始 JSON 保留了同函数内赋值并集。
