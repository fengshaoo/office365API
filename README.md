# Office365Auto

自动调用Azure接口实现对Office365E5续订



一、身份与用户信息类
用于登录用户基本信息、用户头像、组织信息等。

权限名	描述	适用场景
User.Read.All	读取和更新所有用户详细信息	管理后台需要查看修改所有员工资料

二、邮件相关（Outlook Mail）
用于收发邮件、读取用户邮箱内容。

权限名	描述	适用场景
Mail.ReadWrite	读取并修改用户邮件	自动邮件整理

三、日历与事件
管理和读取用户日历，创建会议等。

权限名	描述	适用场景
Calendars.ReadWrite	读取和编辑日历事件	创建/删除会议

四、OneDrive 与文件
访问用户个人 OneDrive 或组织共享文件。

权限名	描述	适用场景
Files.ReadWrite.All	读写所有文件	文件同步客户端

### 必运行
登陆并获取用户信息、拉取邮件和日程

### 随机运行
发送邮件、上传文件、添加日历


八、常用组合推荐（开发者最常配置）
场景	推荐权限组合
登录 + 基本信息	openid, offline_access, User.Read
获取邮件并发送	Mail.ReadWrite, Mail.Send
文件管理	Files.ReadWrite, Sites.Read.All
日程安排	Calendars.ReadWrite, OnlineMeetings.ReadWrite
Bot 与 Teams 互动	Chat.ReadWrite, ChannelMessage.Read.All


五、Microsoft Teams（待添加）
用于读取 Teams 信息、消息或会议。

权限名	描述	适用场景
Chat.Read	读取登录用户的 Teams 聊天消息	聊天机器人
Chat.ReadWrite	读写 Teams 聊天消息	自动应答助手
ChannelMessage.Read.All	读取所有 Teams 渠道消息	日志分析
OnlineMeetings.ReadWrite	管理在线会议（如 Zoom）	创建 Teams 会议

六、SharePoint（待添加）
操作 SharePoint Online 网站、文档库等。

权限名	描述	适用场景
Sites.Read.All	读取所有站点内容	内容聚合
Sites.ReadWrite.All	修改站点内容	表单系统、CMS

设备 & 身份验证辅助（待添加）
用于多设备管理、登录状态监控等。

权限名	描述	适用场景
Device.Read.All	读取组织中设备信息	管理后台
openid / offline_access	用于登录 + 刷新 Token	必备登录流程