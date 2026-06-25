# 🐾 astrbot_plugin_qq_zone

**QQ空间动态一键查看插件** · NekoAi Team

> 通过账号 Cookie 访问 QQ 空间动态，支持查看好友非公开内容（仅好友可见等）

---

## ✨ 功能特性

- 📋 查看任意 QQ 的最新动态（需有访问权限）
- 🔐 通过 Cookie 穿透「需要登录」的访问限制
- 👥 支持查看仅好友可见的内容（使用自己账号 Cookie）
- 📦 AstrBot 插件 + 独立 CLI 脚本双形态
- 💾 Cookie 本地加密存储，支持多账号配置

---

## 📦 安装（AstrBot 插件）

在 AstrBot 管理面板中添加插件仓库地址，或手动将本目录放入 `data/plugins/` 即可。

---

## 🚀 使用方法

### AstrBot 指令

| 指令 | 说明 |
|---|---|
| `/qq动态 帮助` | 查看使用帮助 |
| `/qq动态 设置Cookie <cookie>` | 配置账号 Cookie |
| `/qq动态 <QQ号>` | 查看指定 QQ 最新10条动态 |
| `/qq动态 <QQ号> <数量>` | 查看指定数量（最多20条） |
| `/qq动态 我的` | 查看自己的动态 |
| `/qq动态 清除Cookie` | 清除所有 Cookie |
| `/qq动态 清除Cookie <QQ号>` | 清除指定账号 Cookie |

### 独立 CLI 脚本

```bash
# 安装依赖
pip install requests

# 运行
python3 qq_zone_cli.py
```

---

## 🔑 获取 Cookie

1. **电脑浏览器**打开并登录 [QQ 空间](https://qzone.qq.com/)
2. 按 `F12` 打开开发者工具
3. 切换到「**网络 (Network)**」标签
4. 刷新页面，点击任意一个请求
5. 在「**标头 (Headers)**」中找到 `Cookie` 字段，复制全部内容

> ⚠️ **安全提示**: Cookie 相当于账号密码，请勿在公开群组中发送，也不要泄露给他人。

---

## ⚠️ 免责声明

- 本工具仅用于访问**你本人有权限访问的内容**（好友关系授权范围内）
- 不支持、也不鼓励非法获取他人隐私内容
- 请遵守 QQ 服务条款，合理使用

---

## 📄 License

MIT © NekoAi Team
