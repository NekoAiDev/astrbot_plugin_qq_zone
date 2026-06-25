"""
AstrBot 插件：QQ空间动态一键查看
作者: NekoAi Team
版本: 1.0.0
描述: 通过 Cookie 访问 QQ 空间动态，支持好友非公开内容查看
"""

import json
import time
import re
import hashlib
import urllib.parse
from typing import Optional
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import aiohttp


@register(
    "astrbot_plugin_qq_zone",
    "NekoAi Team",
    "QQ空间动态一键查看，支持好友非公开动态",
    "1.0.0",
    "https://github.com/NekoAiDev/astrbot_plugin_qq_zone",
)
class QQZonePlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context, config)
        self.config = config
        # Cookie 存储：key = QQ号，value = cookie字符串
        self.cookies: dict[str, str] = {}
        # 从配置加载 Cookie
        self._load_cookies_from_config()

    def _load_cookies_from_config(self):
        """从插件配置加载 Cookie"""
        saved = self.config.get("cookies", {})
        if isinstance(saved, dict):
            self.cookies.update(saved)

    def _parse_cookie_str(self, cookie_str: str) -> dict:
        """解析 Cookie 字符串为字典"""
        cookies = {}
        for item in cookie_str.split(";"):
            item = item.strip()
            if "=" in item:
                k, v = item.split("=", 1)
                cookies[k.strip()] = v.strip()
        return cookies

    def _extract_uin(self, cookie_str: str) -> Optional[str]:
        """从 Cookie 中提取 uin（QQ号）"""
        cookies = self._parse_cookie_str(cookie_str)
        uin = cookies.get("uin", "") or cookies.get("o_uin", "")
        # uin 格式通常是 o0123456789，去掉前面的 o
        if uin.startswith("o"):
            uin = uin[1:]
        return uin if uin else None

    def _get_gtk(self, skey: str) -> int:
        """根据 skey 计算 g_tk 参数"""
        hash_val = 5381
        for char in skey:
            hash_val += (hash_val << 5) + ord(char)
        return hash_val & 0x7FFFFFFF

    def _build_headers(self, cookie_str: str) -> dict:
        """构建请求头"""
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Cookie": cookie_str,
            "Referer": "https://qzone.qq.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    async def _fetch_moments(
        self, target_uin: str, owner_cookie: str, count: int = 10
    ) -> dict:
        """
        获取指定 QQ 的动态列表
        :param target_uin: 目标 QQ 号
        :param owner_cookie: 访问者 Cookie（自己账号）
        :param count: 获取数量
        """
        cookie_dict = self._parse_cookie_str(owner_cookie)
        skey = cookie_dict.get("skey", "") or cookie_dict.get("p_skey", "")
        g_tk = self._get_gtk(skey)

        params = {
            "uin": target_uin,
            "ftype": "0",
            "sort": "0",
            "pos": "0",
            "num": str(count),
            "replynum": "100",
            "g_tk": str(g_tk),
            "callback": "_preloadCallback",
            "code_version": "1",
            "format": "jsonp",
            "need_private_comment": "1",
        }

        url = "https://user.qzone.qq.com/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_msglist_v6"
        query_string = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
        full_url = f"{url}?{query_string}"

        headers = self._build_headers(owner_cookie)

        async with aiohttp.ClientSession() as session:
            async with session.get(full_url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                text = await resp.text(encoding="utf-8")

        # 解析 JSONP 回调
        json_str = re.sub(r"^_preloadCallback\(", "", text.strip())
        json_str = re.sub(r"\);?$", "", json_str)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # 尝试提取 JSON 内容
            match = re.search(r"\{.*\}", json_str, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                raise ValueError(f"无法解析响应: {text[:200]}")

        return data

    async def _fetch_profile(self, target_uin: str, owner_cookie: str) -> dict:
        """获取目标 QQ 的基本资料"""
        cookie_dict = self._parse_cookie_str(owner_cookie)
        skey = cookie_dict.get("skey", "") or cookie_dict.get("p_skey", "")
        g_tk = self._get_gtk(skey)

        url = (
            f"https://r.qzone.qq.com/fcg-bin/cgi_get_portrait.fcg"
            f"?get_nick=1&uins={target_uin}"
        )
        headers = self._build_headers(owner_cookie)

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                text = await resp.text(encoding="gbk", errors="replace")

        return {"raw": text}

    def _format_moment(self, item: dict, index: int) -> str:
        """格式化单条动态"""
        lines = []

        # 时间戳转换
        ts = item.get("created_time", 0)
        time_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(int(ts))) if ts else "未知时间"

        # 内容
        content = item.get("content", "").strip() or "[无文字内容]"
        # 去除多余空白
        content = re.sub(r"\s+", " ", content)
        # 截断超长内容
        if len(content) > 200:
            content = content[:200] + "..."

        lines.append(f"📌 **动态 {index}** · {time_str}")
        lines.append(f"💬 {content}")

        # 图片数量
        pic_list = item.get("pic", [])
        if pic_list:
            lines.append(f"🖼️ 含 {len(pic_list)} 张图片")

        # 点赞数
        like_info = item.get("cmtinfo", {})
        like_num = item.get("likecnt", 0) or 0
        cmt_num = item.get("cmtnum", 0) or 0
        if like_num or cmt_num:
            lines.append(f"👍 {like_num} 赞  💭 {cmt_num} 评论")

        # 转发/分享
        rt_con = item.get("rt_con", {})
        if rt_con:
            rt_content = rt_con.get("content", "").strip()
            if rt_content:
                lines.append(f"🔁 转发: {rt_content[:80]}...")

        # 位置
        location = item.get("lbsinfo", {})
        if location and location.get("name"):
            lines.append(f"📍 {location['name']}")

        return "\n".join(lines)

    def _format_response(self, data: dict, target_uin: str, count: int) -> str:
        """格式化最终回复内容"""
        ret = data.get("ret", -1)
        if ret != 0:
            msg_map = {
                "-3000": "❌ 访问被拒绝，Cookie 可能已过期",
                "-10000": "❌ 对方设置了仅好友可见，或你没有访问权限",
                "-100001": "❌ Cookie 失效，请重新配置",
                "-3": "❌ 账号被限制访问",
            }
            err_msg = msg_map.get(str(ret), f"❌ 请求失败（错误码: {ret}）")
            return err_msg

        msg_list = data.get("msglist", [])
        if not msg_list:
            return f"📭 QQ {target_uin} 的空间没有公开动态，或动态列表为空。"

        lines = [f"📋 **QQ {target_uin} 的最新 {len(msg_list)} 条动态**\n"]
        for i, item in enumerate(msg_list[:count], 1):
            lines.append(self._format_moment(item, i))
            lines.append("─" * 20)

        return "\n".join(lines)

    # ==================== AstrBot 指令 ====================

    @filter.command("qq动态")
    async def cmd_qq_zone(self, event: AstrMessageEvent) -> MessageEventResult:
        """
        查看 QQ 空间动态
        用法:
          /qq动态 帮助
          /qq动态 设置Cookie <cookie字符串>
          /qq动态 <QQ号> [数量]
          /qq动态 我的 [数量]
        """
        args = event.get_plain_text().strip().split()[1:]  # 去掉命令本身

        if not args or args[0] == "帮助":
            return event.plain_result(self._help_text())

        if args[0] == "设置Cookie":
            return await self._cmd_set_cookie(event, args[1:])

        if args[0] == "清除Cookie":
            return await self._cmd_clear_cookie(event, args[1:])

        if args[0] == "我的":
            return await self._cmd_my_moments(event, args[1:])

        # 普通查看：/qq动态 <QQ号> [数量]
        target_qq = args[0]
        count = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
        count = min(max(count, 1), 20)  # 限制 1-20 条

        return await self._fetch_and_reply(event, target_qq, count)

    async def _cmd_set_cookie(self, event: AstrMessageEvent, args: list) -> MessageEventResult:
        """设置 Cookie"""
        if not args:
            return event.plain_result(
                "❓ 请提供 Cookie 字符串\n\n"
                "格式: `/qq动态 设置Cookie <cookie>`\n\n"
                "📖 获取方式:\n"
                "1. 电脑浏览器打开 QQ 空间\n"
                "2. 按 F12 → 网络(Network) 标签\n"
                "3. 刷新页面，找到任意请求\n"
                "4. 复制请求头中的 Cookie 值\n\n"
                "⚠️ Cookie 包含账号敏感信息，请勿泄露给他人"
            )

        cookie_str = " ".join(args)
        uin = self._extract_uin(cookie_str)

        if not uin:
            # 尝试让用户确认 QQ 号
            return event.plain_result(
                "⚠️ 无法从 Cookie 自动识别 QQ 号。\n"
                "请使用格式: `/qq动态 设置Cookie <QQ号> <cookie>`\n"
                "例: `/qq动态 设置Cookie 123456789 uin=o123456789; skey=...`"
            )

        self.cookies[uin] = cookie_str
        # 持久化（写回 config）
        if hasattr(self, 'config'):
            if "cookies" not in self.config:
                self.config["cookies"] = {}
            self.config["cookies"][uin] = cookie_str

        logger.info(f"[QQZone] 已为 QQ {uin} 设置 Cookie")
        return event.plain_result(
            f"✅ 已为 QQ **{uin}** 设置 Cookie！\n\n"
            f"现在可以使用:\n"
            f"• `/qq动态 我的` - 查看自己动态\n"
            f"• `/qq动态 <好友QQ号>` - 查看好友动态\n\n"
            f"🔑 当前已配置账号: {', '.join(self.cookies.keys())}"
        )

    async def _cmd_clear_cookie(self, event: AstrMessageEvent, args: list) -> MessageEventResult:
        """清除 Cookie"""
        if args and args[0].isdigit():
            qq = args[0]
            if qq in self.cookies:
                del self.cookies[qq]
                return event.plain_result(f"✅ 已清除 QQ {qq} 的 Cookie")
            else:
                return event.plain_result(f"❌ 未找到 QQ {qq} 的 Cookie 记录")
        else:
            count = len(self.cookies)
            self.cookies.clear()
            return event.plain_result(f"✅ 已清除全部 {count} 个账号的 Cookie")

    async def _cmd_my_moments(self, event: AstrMessageEvent, args: list) -> MessageEventResult:
        """查看自己的动态"""
        if not self.cookies:
            return event.plain_result(
                "❌ 未配置任何账号 Cookie\n"
                "请先使用: `/qq动态 设置Cookie <cookie字符串>`"
            )

        # 使用第一个配置的账号
        uin = list(self.cookies.keys())[0]
        count = int(args[0]) if args and args[0].isdigit() else 10
        count = min(max(count, 1), 20)

        return await self._fetch_and_reply(event, uin, count, owner_uin=uin)

    async def _fetch_and_reply(
        self,
        event: AstrMessageEvent,
        target_qq: str,
        count: int = 10,
        owner_uin: Optional[str] = None,
    ) -> MessageEventResult:
        """通用：获取动态并回复"""
        if not target_qq.isdigit():
            return event.plain_result("❌ QQ号格式错误，请输入纯数字 QQ 号")

        if not self.cookies:
            return event.plain_result(
                "❌ 未配置账号 Cookie，无法访问 QQ 空间\n"
                "请先使用: `/qq动态 设置Cookie <cookie字符串>`"
            )

        # 选择 Cookie：优先使用 owner_uin 指定的，否则使用第一个
        if owner_uin and owner_uin in self.cookies:
            cookie = self.cookies[owner_uin]
        else:
            cookie = list(self.cookies.values())[0]
            owner_uin = list(self.cookies.keys())[0]

        await event.send(event.plain_result(f"🔍 正在获取 QQ {target_qq} 的动态，请稍候..."))

        try:
            data = await self._fetch_moments(target_qq, cookie, count)
            result = self._format_response(data, target_qq, count)
            return event.plain_result(result)

        except aiohttp.ClientError as e:
            logger.error(f"[QQZone] 网络请求失败: {e}")
            return event.plain_result(f"❌ 网络请求失败: {str(e)[:100]}")
        except ValueError as e:
            logger.error(f"[QQZone] 数据解析失败: {e}")
            return event.plain_result(f"❌ 数据解析失败: {str(e)[:100]}")
        except Exception as e:
            logger.error(f"[QQZone] 未知错误: {e}", exc_info=True)
            return event.plain_result(f"❌ 发生错误: {str(e)[:100]}")

    def _help_text(self) -> str:
        configured = list(self.cookies.keys())
        status = (
            f"🔑 已配置账号: {', '.join(configured)}" if configured
            else "⚠️ 尚未配置任何账号 Cookie"
        )
        return (
            "📋 **QQ空间动态查看插件** v1.0.0\n\n"
            "**指令说明:**\n"
            "• `/qq动态 <QQ号>` - 查看指定 QQ 最新10条动态\n"
            "• `/qq动态 <QQ号> <数量>` - 查看指定数量（最多20条）\n"
            "• `/qq动态 我的` - 查看自己最新动态\n"
            "• `/qq动态 设置Cookie <cookie>` - 配置账号 Cookie\n"
            "• `/qq动态 清除Cookie` - 清除所有 Cookie\n"
            "• `/qq动态 清除Cookie <QQ号>` - 清除指定账号\n"
            "• `/qq动态 帮助` - 显示此帮助\n\n"
            "**Cookie 获取方法:**\n"
            "1. 电脑浏览器打开并登录 QQ 空间\n"
            "2. 按 F12 打开开发者工具\n"
            "3. 切换到「网络(Network)」标签\n"
            "4. 刷新页面，任意点一个请求\n"
            "5. 在「标头(Headers)」中找到 Cookie 行并复制\n\n"
            f"{status}\n\n"
            "⚠️ Cookie 包含账号凭据，请妥善保管，勿在公开场合使用"
        )
