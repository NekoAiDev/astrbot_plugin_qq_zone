"""
QQ空间动态查看 - 独立命令行脚本
无需 AstrBot，直接运行即可查看 QQ 空间动态

使用方法:
    python3 qq_zone_cli.py

依赖安装:
    pip install requests
"""

import json
import time
import re
import urllib.parse
import sys
import os
from typing import Optional

try:
    import requests
except ImportError:
    print("❌ 缺少依赖，请先运行: pip install requests")
    sys.exit(1)

# =========================================================
# Cookie 存储文件
# =========================================================
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".qq_zone_cookies.json")

BANNER = """
╔══════════════════════════════════════════╗
║   🐾 QQ空间动态查看工具  v1.0.0          ║
║   by NekoAi Team                         ║
╚══════════════════════════════════════════╝
"""


def load_cookies() -> dict:
    """加载已保存的 Cookie"""
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cookies(cookies: dict):
    """保存 Cookie 到文件"""
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    # 设置只有当前用户可读（保护隐私）
    try:
        os.chmod(COOKIE_FILE, 0o600)
    except Exception:
        pass


def parse_cookie_str(cookie_str: str) -> dict:
    """解析 Cookie 字符串"""
    cookies = {}
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            cookies[k.strip()] = v.strip()
    return cookies


def extract_uin(cookie_str: str) -> Optional[str]:
    """从 Cookie 中提取 QQ 号"""
    cookies = parse_cookie_str(cookie_str)
    uin = cookies.get("uin", "") or cookies.get("o_uin", "")
    if uin.startswith("o"):
        uin = uin[1:]
    return uin if uin else None


def get_gtk(skey: str) -> int:
    """计算 g_tk"""
    hash_val = 5381
    for char in skey:
        hash_val += (hash_val << 5) + ord(char)
    return hash_val & 0x7FFFFFFF


def build_headers(cookie_str: str) -> dict:
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


def fetch_moments(target_uin: str, owner_cookie: str, count: int = 10) -> dict:
    """获取 QQ 空间动态"""
    cookie_dict = parse_cookie_str(owner_cookie)
    skey = cookie_dict.get("skey", "") or cookie_dict.get("p_skey", "")
    g_tk = get_gtk(skey)

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

    resp = requests.get(full_url, headers=build_headers(owner_cookie), timeout=15)
    resp.raise_for_status()

    text = resp.text

    # 解析 JSONP
    json_str = re.sub(r"^_preloadCallback\(", "", text.strip())
    json_str = re.sub(r"\);?$", "", json_str)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", json_str, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(f"无法解析响应内容:\n{text[:300]}")

    return data


def format_moment(item: dict, index: int) -> str:
    """格式化单条动态"""
    lines = []

    ts = item.get("created_time", 0)
    time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(ts))) if ts else "未知时间"

    content = item.get("content", "").strip() or "[无文字内容]"
    content = re.sub(r"\s+", " ", content)

    lines.append(f"\n【动态 {index}】 {time_str}")
    lines.append(f"内容: {content}")

    pic_list = item.get("pic", [])
    if pic_list:
        lines.append(f"图片: {len(pic_list)} 张")
        for i, pic in enumerate(pic_list[:3], 1):
            url = pic.get("url1", "") or pic.get("url2", "")
            if url:
                lines.append(f"  [{i}] {url}")
        if len(pic_list) > 3:
            lines.append(f"  ... 还有 {len(pic_list) - 3} 张")

    like_num = item.get("likecnt", 0) or 0
    cmt_num = item.get("cmtnum", 0) or 0
    if like_num or cmt_num:
        lines.append(f"互动: 👍 {like_num} 赞  💬 {cmt_num} 评论")

    rt_con = item.get("rt_con", {})
    if rt_con:
        rt_content = rt_con.get("content", "").strip()
        if rt_content:
            lines.append(f"转发: {rt_content[:100]}")

    location = item.get("lbsinfo", {})
    if location and location.get("name"):
        lines.append(f"位置: 📍 {location['name']}")

    vid_info = item.get("video_info", {})
    if vid_info:
        vid_title = vid_info.get("title", "")
        if vid_title:
            lines.append(f"视频: 🎬 {vid_title}")

    return "\n".join(lines)


def print_separator(char="─", width=50):
    print(char * width)


def cmd_set_cookie(cookies: dict) -> dict:
    """交互式设置 Cookie"""
    print("\n🔑 设置账号 Cookie")
    print("=" * 50)
    print("获取步骤:")
    print("  1. 电脑浏览器打开并登录 QQ 空间 (qzone.qq.com)")
    print("  2. 按 F12 打开开发者工具")
    print("  3. 切换到「网络(Network)」标签")
    print("  4. 刷新页面，点击任意一个请求")
    print("  5. 在「标头(Headers)」中找到 Cookie 行并复制全部内容")
    print("=" * 50)

    cookie_str = input("\n请粘贴 Cookie 字符串（按回车确认）:\n> ").strip()

    if not cookie_str:
        print("❌ Cookie 不能为空")
        return cookies

    uin = extract_uin(cookie_str)

    if not uin:
        uin = input("⚠️ 无法自动识别 QQ 号，请手动输入: ").strip()
        if not uin or not uin.isdigit():
            print("❌ QQ 号格式错误")
            return cookies

    cookies[uin] = cookie_str
    save_cookies(cookies)
    print(f"\n✅ 已保存 QQ {uin} 的 Cookie")
    return cookies


def cmd_view_moments(cookies: dict):
    """查看动态"""
    if not cookies:
        print("❌ 未配置任何账号 Cookie，请先执行「设置Cookie」")
        return

    print("\n📋 查看 QQ 空间动态")
    print("=" * 50)

    # 选择访问账号
    accounts = list(cookies.keys())
    if len(accounts) == 1:
        owner_uin = accounts[0]
        print(f"🔑 使用账号: QQ {owner_uin}")
    else:
        print("可用账号:")
        for i, qq in enumerate(accounts, 1):
            print(f"  [{i}] QQ {qq}")
        choice = input("选择账号编号（默认1）: ").strip() or "1"
        try:
            owner_uin = accounts[int(choice) - 1]
        except (ValueError, IndexError):
            print("❌ 选择无效")
            return

    # 目标 QQ
    target_input = input("\n要查看的 QQ 号（留空则查看自己）: ").strip()
    target_uin = target_input if target_input else owner_uin

    if not target_uin.isdigit():
        print("❌ QQ 号格式错误")
        return

    # 数量
    count_input = input("获取数量（默认10，最多20）: ").strip() or "10"
    try:
        count = min(max(int(count_input), 1), 20)
    except ValueError:
        count = 10

    print(f"\n🔍 正在获取 QQ {target_uin} 的最新 {count} 条动态...")
    print_separator()

    try:
        data = fetch_moments(target_uin, cookies[owner_uin], count)
    except requests.exceptions.ConnectionError:
        print("❌ 网络连接失败，请检查网络")
        return
    except requests.exceptions.Timeout:
        print("❌ 请求超时，请稍后重试")
        return
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        return

    ret = data.get("ret", -1)
    if ret != 0:
        err_map = {
            -3000: "Cookie 可能已过期，请重新配置",
            -10000: "对方设置了仅好友可见，或你没有访问权限",
            -100001: "Cookie 失效，请重新配置",
            -3: "账号被限制访问",
        }
        err_msg = err_map.get(ret, f"请求失败（错误码: {ret}）")
        print(f"❌ {err_msg}")
        return

    msg_list = data.get("msglist", [])
    if not msg_list:
        print(f"📭 QQ {target_uin} 的空间没有动态，或动态列表为空")
        return

    print(f"✅ 获取到 {len(msg_list)} 条动态\n")

    for i, item in enumerate(msg_list[:count], 1):
        print(format_moment(item, i))
        print_separator()

    # 是否保存到文件
    save = input("\n是否将结果保存到文件？(y/N): ").strip().lower()
    if save == "y":
        filename = f"qq_zone_{target_uin}_{int(time.time())}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"QQ空间动态 - {target_uin}\n")
            f.write(f"获取时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n")
            for i, item in enumerate(msg_list[:count], 1):
                f.write(format_moment(item, i) + "\n")
                f.write("─" * 50 + "\n")
        print(f"✅ 已保存到: {filename}")


def cmd_list_cookies(cookies: dict):
    """列出已配置的账号"""
    if not cookies:
        print("⚠️ 暂无已配置的账号")
        return

    print(f"\n🔑 已配置 {len(cookies)} 个账号:")
    for qq in cookies:
        cookie_preview = cookies[qq][:30] + "..." if len(cookies[qq]) > 30 else cookies[qq]
        print(f"  • QQ {qq}: {cookie_preview}")


def cmd_remove_cookie(cookies: dict) -> dict:
    """删除 Cookie"""
    if not cookies:
        print("⚠️ 暂无已配置的账号")
        return cookies

    cmd_list_cookies(cookies)
    qq = input("\n请输入要删除的 QQ 号（留空取消）: ").strip()

    if not qq:
        return cookies

    if qq in cookies:
        del cookies[qq]
        save_cookies(cookies)
        print(f"✅ 已删除 QQ {qq} 的 Cookie")
    else:
        print(f"❌ 未找到 QQ {qq} 的记录")

    return cookies


def main():
    print(BANNER)

    cookies = load_cookies()

    if cookies:
        print(f"💡 已加载 {len(cookies)} 个账号配置: {', '.join(cookies.keys())}")
    else:
        print("💡 提示: 首次使用请先设置 Cookie")

    while True:
        print("\n" + "=" * 50)
        print("请选择操作:")
        print("  [1] 查看 QQ 空间动态")
        print("  [2] 设置账号 Cookie")
        print("  [3] 查看已配置账号")
        print("  [4] 删除账号 Cookie")
        print("  [0] 退出")
        print("=" * 50)

        choice = input("请输入编号: ").strip()

        if choice == "1":
            cmd_view_moments(cookies)
        elif choice == "2":
            cookies = cmd_set_cookie(cookies)
        elif choice == "3":
            cmd_list_cookies(cookies)
        elif choice == "4":
            cookies = cmd_remove_cookie(cookies)
        elif choice == "0":
            print("\n👋 再见！")
            break
        else:
            print("❌ 无效选项，请重新输入")


if __name__ == "__main__":
    main()
