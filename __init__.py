import json
import requests

try:
    from bs4 import BeautifulSoup
    from nonebot import *
    from .FDConfig import Config  # 需确保Config类已添加owner字段
    from nonebot.adapters import Event, Message
    from nonebot.rule import startswith
    from nonebot.params import CommandArg

    # 使用自定义的Config.from_file()方法加载配置，确保配置正确保存和读取
    plugin_config = Config.from_file()


    async def is_enabled_for(event: Event) -> bool:
        return plugin_config.is_valid_user(event.get_session_id().split("_"))


    def is_admin(user_id: str) -> bool:
        return user_id in plugin_config.admin_users


    def is_owner(user_id: str) -> bool:
        """判断是否为所有者（仅owner可管理管理员）"""
        return user_id == plugin_config.owner


    # 插件版本信息
    PLUGIN_VERSION = "1.3.0"
    
    # 基础帮助文本（所有用户可见）
    BASE_HELP_TEXT = """目前支持的指令：
    查 [料号] → 精确查询Flash料号详情
    搜 [部分料号] → 模糊搜索Flash料号
    ID [颗粒ID] → 解析Flash颗粒ID（不足12位自动补0）
    查DRAM [料号] → 精确查询DRAM料号详情（例：查DRAM NT5AD1024M8C3-HR）
    /help → 显示此帮助内容
    /status → 显示插件状态信息
    /version → 显示插件版本信息"""
    
    # 管理员帮助文本（仅管理员和所有者可见）
    ADMIN_HELP_TEXT = """
    管理员命令：
    /api <url> → 显示/修改FlashDetector地址（仅管理员）
    黑白名单管理（仅管理员）：
    /whitelist add <user/group> <id> → 添加到白名单
    /whitelist remove [user/group] [id] → 移除（可省略参数）
    /whitelist list [user/group] → 列出（可省略参数）
    /blacklist 命令格式与whitelist相同"""
    
    # 所有者帮助文本（仅所有者可见）
    OWNER_HELP_TEXT = """
    所有者命令：
    /reload → 重载配置文件（仅所有者）
    快捷命令（所有者专用）：
    /op <user_id> → 将用户设为管理员
    /deop <user_id> → 移除用户的管理员权限
    /ban <user_id> → 将用户加入黑名单
    /pardon <user_id> → 将用户从黑名单移除
    管理员管理（仅所有者）：
    /admin add <id> → 添加管理员
    /admin remove <id> → 移除管理员
    /admin list → 列出所有管理员"""
    
    # 命令定义
    whitelist_cmd = on_command("whitelist", priority=1, rule=is_enabled_for, block=True)
    blacklist_cmd = on_command("blacklist", priority=1, rule=is_enabled_for, block=True)
    admin_cmd = on_command("admin", priority=1, rule=is_enabled_for, block=True)  # 管理员管理命令
    listened_commands = startswith(("ID", "id", 'iD', 'Id', "查", "搜"), ignorecase=False)
    MessageHandler = on_message(priority=10, rule=is_enabled_for & listened_commands, block=False)
    help_cmd = on_command("help", priority=1, rule=is_enabled_for, block=False)
    api_cmd = on_command("api", priority=1, rule=is_enabled_for, block=False)
    reload_cmd = on_command("reload", priority=1, rule=is_enabled_for, block=False)
    status_cmd = on_command("status", priority=1, rule=is_enabled_for, block=False)
    version_cmd = on_command("version", priority=1, rule=is_enabled_for, block=False)
    op_cmd = on_command("op", priority=1, rule=is_enabled_for, block=True)
    deop_cmd = on_command("deop", priority=1, rule=is_enabled_for, block=True)
    ban_cmd = on_command("ban", priority=1, rule=is_enabled_for, block=True)
    pardon_cmd = on_command("pardon", priority=1, rule=is_enabled_for, block=True)


    # 重载配置
    @reload_cmd.handle()
    async def reloadConfigHandler(event: Event):
        # 先检查是否为所有者
        if not is_owner(event.get_user_id()):
            await reload_cmd.finish("权限不足，只有所有者可以重载配置")
        else:
            try:
                plugin_config.load_config()
                await reload_cmd.finish("配置重载成功")
            except Exception as e:
                await reload_cmd.finish(f"配置重载失败: {str(e)}")
    
    # 状态查询命令
    @status_cmd.handle()
    async def statusHandler(event: Event):
        # 获取配置状态信息
        status_info = []
        status_info.append("FlashDetail 插件状态信息")
        status_info.append(f"版本: {PLUGIN_VERSION}")
        status_info.append(f"API地址: {plugin_config.api_url}")
        status_info.append(f"所有者: {plugin_config.owner}")
        status_info.append(f"管理员数量: {len(plugin_config.admin_users)}")
        status_info.append(f"白名单用户数: {len(plugin_config.whitelist_user)}")
        status_info.append(f"白名单群组数: {len(plugin_config.whitelist_group)}")
        status_info.append(f"黑名单用户数: {len(plugin_config.blacklist_user)}")
        status_info.append(f"黑名单群组数: {len(plugin_config.blacklist_group)}")
        
        # 检查API连接状态
        try:
            response = requests.get(f"{plugin_config.api_url}", timeout=3)
            api_status = "正常" if response.status_code == 200 else "异常"
        except Exception:
            api_status = "连接失败"
        status_info.append(f"API连接状态: {api_status}")
        
        await status_cmd.finish("\n".join(status_info))
    
    # 版本查询命令
    @version_cmd.handle()
    async def versionHandler(event: Event):
        version_info = [
            f"FlashDetail 插件 v{PLUGIN_VERSION}",
            "功能: Flash和DRAM料号查询工具",
            "支持命令: 查/搜/ID/查DRAM/help/api/admin/whitelist/blacklist/status/version/reload",
            "作者: Qikahome/3281",
            "仅供学习和测试使用"
        ]
        await version_cmd.finish("\n".join(version_info))
    # 帮助命令
    @help_cmd.handle()
    async def helpCommandHandler(event: Event):
        # 根据用户权限显示不同级别的帮助文本
        user_id = event.get_user_id()
        help_text = BASE_HELP_TEXT
        
        # 管理员和所有者可以看到管理员相关命令
        if is_admin(user_id) or is_owner(user_id):
            help_text += ADMIN_HELP_TEXT
        
        # 只有所有者可以看到所有者相关命令
        if is_owner(user_id):
            help_text += OWNER_HELP_TEXT
        
        await help_cmd.finish(help_text)


    # 消息命令
    @MessageHandler.handle()
    async def messageHandler(foo: Event):
        # 不再需要单独检查用户有效性，因为is_enabled_for规则已经做了检查
        result = get_message_result(foo.get_plaintext())
        if result and result[-1] == '\n':
            result = result[:-1]
        await MessageHandler.send(result or "未查询到结果")


    # API命令
    @api_cmd.handle()
    async def apiCommandHandler(event: Event, arg: Message = CommandArg()):
        # 不再需要单独检查用户有效性，因为is_enabled_for规则已经做了检查
        full_cmd = f"/api {arg.extract_plain_text().strip()}"
        api_result = handle_special_commands(full_cmd, user_id=event.get_user_id())
        await api_cmd.finish(api_result)


    # 白名单命令
    @whitelist_cmd.handle()
    async def whitelistHandler(event: Event, arg: Message = CommandArg()):
        user_id = event.get_user_id()
        if not is_admin(user_id):
            return
        args = arg.extract_plain_text().strip().split()
        result = handle_list_command("whitelist", args)
        if result:
            await whitelist_cmd.finish(result)


    # 黑名单命令
    @blacklist_cmd.handle()
    async def blacklistHandler(event: Event, arg: Message = CommandArg()):
        user_id = event.get_user_id()
        if not is_admin(user_id):
            return
        args = arg.extract_plain_text().strip().split()
        result = handle_list_command("blacklist", args)
        if result:
            await blacklist_cmd.finish(result)


    # 管理员管理命令（仅所有者可用）
    @admin_cmd.handle()
    async def adminHandler(event: Event, arg: Message = CommandArg()):
        user_id = event.get_user_id()
        if not is_owner(user_id):  # 仅所有者可操作
            return
        args = arg.extract_plain_text().strip().split()
        result = handle_admin_command(args)
        if result:
            await admin_cmd.finish(result)
    
    # 将用户设为管理员（仅所有者可用）
    @op_cmd.handle()
    async def opHandler(event: Event, arg: Message = CommandArg()):
        user_id = event.get_user_id()
        if not is_owner(user_id):
            return
        target_id = arg.extract_plain_text().strip()
        if not target_id:
            await op_cmd.finish("请指定要设置为管理员的用户ID")
            return
        if target_id in plugin_config.admin_users:
            await op_cmd.finish(f"用户 {target_id} 已是管理员")
            return
        plugin_config.admin_users.append(target_id)
        plugin_config.save_all()
        await op_cmd.finish(f"已将用户 {target_id} 设置为管理员")
    
    # 移除用户的管理员权限（仅所有者可用）
    @deop_cmd.handle()
    async def deopHandler(event: Event, arg: Message = CommandArg()):
        user_id = event.get_user_id()
        if not is_owner(user_id):
            return
        target_id = arg.extract_plain_text().strip()
        if not target_id:
            await deop_cmd.finish("请指定要移除管理员权限的用户ID")
            return
        if target_id not in plugin_config.admin_users:
            await deop_cmd.finish(f"用户 {target_id} 不是管理员")
            return
        plugin_config.admin_users.remove(target_id)
        plugin_config.save_all()
        await deop_cmd.finish(f"已移除用户 {target_id} 的管理员权限")
    
    # 将用户加入黑名单（仅所有者可用）
    @ban_cmd.handle()
    async def banHandler(event: Event, arg: Message = CommandArg()):
        user_id = event.get_user_id()
        if not is_owner(user_id):
            return
        target_id = arg.extract_plain_text().strip()
        if not target_id:
            await ban_cmd.finish("请指定要封禁的用户ID")
            return
        if target_id in plugin_config.blacklist_user:
            await ban_cmd.finish(f"用户 {target_id} 已在黑名单中")
            return
        plugin_config.blacklist_user.append(target_id)
        plugin_config.save_all()
        await ban_cmd.finish(f"已将用户 {target_id} 加入黑名单")
    
    # 将用户从黑名单移除（仅所有者可用）
    @pardon_cmd.handle()
    async def pardonHandler(event: Event, arg: Message = CommandArg()):
        user_id = event.get_user_id()
        if not is_owner(user_id):
            return
        target_id = arg.extract_plain_text().strip()
        if not target_id:
            await pardon_cmd.finish("请指定要解封的用户ID")
            return
        if target_id not in plugin_config.blacklist_user:
            await pardon_cmd.finish(f"用户 {target_id} 不在黑名单中")
            return
        plugin_config.blacklist_user.remove(target_id)
        plugin_config.save_all()
        await pardon_cmd.finish(f"已将用户 {target_id} 从黑名单移除")

except Exception as e:
    print(f"not running in onebot: {e}")


def classification(arg: dict[str, int]) -> str:
    return f"通道数：{arg['ch']}\n片选：{arg['ce']}\nDie：{arg['die']}\n"


# 容量单位转换函数
def format_density(arg) -> str:
    """
    将容量值从 Tb/Gb/Mb/纯数字转换为 TB/GB/MB（按1024进位）
    输出规则：无小数则显示整数，有小数保留两位；末尾带换行符
    """
    try:
        arg=str(arg)
        value = arg.strip()
        bytes_val = 0.0  # 统一转换为 MB 作为中间单位

        # 提取数值并转换为 MB（1字节=8比特）
        if value.endswith("Tb"):
            num = float(value[:-2])
            bytes_val = num * 1024 * 1024 / 8  # Tb → MB
        elif value.endswith("Gb"):
            num = float(value[:-2])
            bytes_val = num * 1024 / 8  # Gb → MB
        elif value.endswith("Mb"):
            num = float(value[:-2])
            bytes_val = num / 8  # Mb → MB
        elif value.endswith("G"):
            num = float(value[:-1])
            bytes_val = num * 1024 * 2 
        elif value.endswith("M"):
            num = float(value[:-1])
            bytes_val = num * 2 
        else:
            num = float(value)  # 纯数字默认视为 Mb
            bytes_val = num / 8  # 转换为 MB

        # 按1024进位选择单位，并处理小数
        if bytes_val >= 1024 * 1024:
            # 转换为 TB
            tb = bytes_val / (1024 * 1024)
            if tb.is_integer():
                return f"容量：{int(tb)} TB\n"
            return f"容量：{tb:.2f} TB\n"
        elif bytes_val >= 1024:
            # 转换为 GB
            gb = bytes_val / 1024
            if gb.is_integer():
                return f"容量：{int(gb)} GB\n"
            return f"容量：{gb:.2f} GB\n"
        else:
            # 保留为 MB
            if bytes_val.is_integer():
                return f"容量：{int(bytes_val)} MB\n"
            return f"容量：{bytes_val:.2f} MB\n"
    except (ValueError, TypeError):
        # 格式无效时直接返回原始值（带前缀和换行）
        return f"容量：{arg}\n"


def flashId(arg: list[str]) -> str:
    return "" if not arg else f"可能的ID：{', '.join(arg)}\n"
# result_translate 映射（新增DRAM字段）
result_translate = {
    # 原有Flash字段
    "id": "", "vendor": "厂商：", "die": "Die数量：", "plane": "平面数：",
    "pageSize": "页面大小：", "blockSize": "块大小：", "processNode": "制程：",
    "cellLevel": "单元类型：", "partNumber": "料号：", "type": "类型：",
    "density": format_density,
    "deviceWidth": "位宽：", "classification": classification, "voltage": "电压：",
    "generation": "代数：", "package": "封装：", "flashId": flashId,
    # 新增DRAM专属字段
    "depth": "深度：",
    "grade": "等级：",
    "speed": "速度：",
    "vendor_code": "厂商代码：",
    "version": "版本：",
    "width": "位宽："
}


import urllib3
# 抑制因忽略SSL验证产生的警告（可选）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_html_with_requests(url):
    try:
        # 添加 verify=False 忽略SSL证书验证
        response = requests.get(url, timeout=10, verify=False)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return response
    except requests.exceptions.HTTPError as e:
        print(f"HTTP错误: {str(e)}")
    except requests.exceptions.ConnectionError:
        print("连接错误")
    except requests.exceptions.Timeout:
        print("请求超时")
    except Exception as e:
        print(f"发生错误: {str(e)}")
    return None

def is_hex(arg:str) -> bool:
    try:
        int(arg, 16)
        return True
    except ValueError:
        return False

def get_detail(arg: str, firstTime: bool = True) -> dict:
    if not arg.strip():
        result = {"result": False, "error": "料号不能为空"}
        # 在return前添加格式化输出
        formatted_output = result_to_text(result)
        # 这里可以根据需要修改formatted_output
        return result
    try:
        if is_hex(arg) and len(arg) > 6:
            return get_detail_from_ID(arg)
        html = get_html_with_requests(f"{plugin_config.api_url}/decode?lang=chs&pn={arg}")
        if not html:
            return "API请求失败"
        soup = BeautifulSoup(html.text, 'lxml')
        p_tags = soup.find('p')
        if p_tags:
            result = json.loads(p_tags.get_text())
            # 在return前添加格式化输出
            formatted_output = result_to_text(result)
            if formatted_output == "无结果" and firstTime:
                search_result = search(arg)
                if len(search_result.get("data",[])):
                    return f"可能的料号：{search_result.get("data")[0].split(' ')[-1]} \n{get_detail(search_result.get("data")[0].split(' ')[-1],False)}"
            # 这里可以根据需要修改formatted_output
            return formatted_output
        return "未找到有效数据"
    except json.JSONDecodeError:
        return "API返回格式错误（非JSON）"
    except Exception as e:
        return str(e)


def search(arg: str) -> dict:
    if not arg.strip():
        result = {"result": False, "error": "搜索关键词不能为空"}
        # 在return前添加格式化输出
        formatted_output = "搜索失败：" + result.get("error", "未知错误")
        # 这里可以根据需要修改formatted_output
        return result
    try:
        html = get_html_with_requests(f"{plugin_config.api_url}/searchPn?limit=10&lang=chs&pn={arg}")
        if not html:
            result = {"result": False, "error": "API请求失败"}
            # 在return前添加格式化输出
            formatted_output = "搜索失败：" + result.get("error", "未知错误")
            # 这里可以根据需要修改formatted_output
            return result
        soup = BeautifulSoup(html.text, 'lxml')
        p_tags = soup.find('p')
        if p_tags:
            result = json.loads(p_tags.get_text())
            # 在return前添加格式化输出
            if result.get("result", False):
                data = result.get("data", [])
                formatted_output = "可能的结果：\n" + "\n".join(data[:10])
            else:
                formatted_output = "搜索失败：" + result.get("error", "未知错误")
            # 这里可以根据需要修改formatted_output
            return result
        result = {"result": False, "error": "未找到有效数据"}
        # 在return前添加格式化输出
        formatted_output = "搜索失败：" + result.get("error", "未知错误")
        # 这里可以根据需要修改formatted_output
        return result
    except json.JSONDecodeError:
        result = {"result": False, "error": "API返回格式错误（非JSON）"}
        # 在return前添加格式化输出
        formatted_output = "搜索失败：" + result.get("error", "未知错误")
        # 这里可以根据需要修改formatted_output
        return result
    except Exception as e:
        result = {"result": False, "error": str(e)}
        # 在return前添加格式化输出
        formatted_output = "搜索失败：" + result.get("error", "未知错误")
        # 这里可以根据需要修改formatted_output
        return result


def get_detail_from_ID(arg: str) -> str:
    """处理ID：提取有效字符后，不足12位则补0"""
    if not arg.strip():
        return "ID不能为空"
    try:
        # 提取有效字符（字母/数字）
        id_clean = []
        for c in arg:
            if c.isalnum():
                id_clean.append(c)
            if len(id_clean) >= 12:
                break  # 超过12位则截断
        # 不足12位则补0
        if len(id_clean) < 12:
            id_clean += ['0'] * (12 - len(id_clean))
        id_str = ''.join(id_clean[:12])  # 确保正好12位

        html = get_html_with_requests(f"{plugin_config.api_url}/decodeId?lang=chs&id={id_str}")
        if not html:
            return "API请求失败"
        soup = BeautifulSoup(html.text, 'lxml')
        p_tags = soup.find('p')
        if p_tags:
            result = json.loads(p_tags.get_text())
            # 在return前添加格式化输出
            formatted_output = result_to_text(result)
            # 这里可以根据需要修改formatted_output
            return formatted_output
        return "未找到有效数据"
    except json.JSONDecodeError:
        return "API返回格式错误（非JSON）"
    except Exception as e:
        return str(e)


def parse_micron_pn(arg:str) -> dict:
    """解析Micron PN"""
    # 访问micron-online接口获取完整part-number
    micron_url = f"https://fe-backend.barryblueice.cn/micron-online?param={arg.upper()}"
    micron_response = get_html_with_requests(micron_url)
    if not micron_response:
        return {"result": False, "error": "解码镁光料号失败"}
    try:
        # 尝试解析JSON响应
        response_data = json.loads(micron_response.text)
        # 确保返回的数据结构包含必要字段
        if "detail" not in response_data and "part-number" in response_data:
            # 如果part-number直接在根级别，将其移到detail字典中以保持一致性
            response_data["detail"] = {"part-number": response_data["part-number"]}
        return response_data
    except json.JSONDecodeError:
        return {"result": False, "error": "返回数据格式错误"}

def get_dram_detail(arg: str) -> str:
    """查询DRAM详情（适配DRAM专属API）"""
    if not arg.strip():
        return "DRAM料号不能为空"
    try:
        pn = arg.strip()
        # 处理5位DRAM料号特殊逻辑
        if len(pn) == 5:
            micron_json = parse_micron_pn(pn)
            if not micron_json.get("result"):
                return "未能获取完整DRAM料号"
            
            # 获取完整的part-number并使用它调用DRAM接口
            # 兼容不同的数据结构：part-number可能在detail字典或直接在根级别
            if "detail" in micron_json and "part-number" in micron_json["detail"]:
                pn = micron_json["detail"]["part-number"]
            elif "part-number" in micron_json:
                pn = micron_json["part-number"]
            else:
                return "获取完整DRAM料号失败：找不到part-number字段"
        
        # 使用原始料号或从micron-online获取的完整料号调用DRAM接口
        url = f"https://fe-backend.barryblueice.cn/DRAM?param={pn}"
        response = get_html_with_requests(url)
        if not response:
            return "DRAM API请求失败"

        # 解析API返回的JSON
        resp_json = json.loads(response.text)
        if not resp_json.get("result"):
            return "未查询到DRAM信息"

        # 转换为与现有result_to_text兼容的格式
        detail = resp_json.get("detail", {})
        result = {
            "result": True,
            "data": {
                "vendor": resp_json.get("Vendor", "未知"),
                "density": detail.get("Density", "未知"),  # 复用format_density转换
                "depth": detail.get("Depth", "未知"),
                "grade": detail.get("Grade", "未知"),
                "package": detail.get("Package", "未知"),
                "speed": detail.get("Speed", "未知"),
                "type": detail.get("Type", "未知"),
                "vendor_code": detail.get("Vendor_Code", "未知"),
                "version": detail.get("Version", "未知"),
                "voltage": detail.get("Voltage", "未知"),
                "width": detail.get("Width", "未知")
            }
        }
        # 在return前添加格式化输出
        formatted_output = result_to_text(result)
        # 这里可以根据需要修改formatted_output
        return formatted_output
    except json.JSONDecodeError:
        return "DRAM API返回格式错误"
    except Exception as e:
        return f"错误：{str(e)}"


def result_to_text(arg: dict) -> str:
    if not arg.get("result", False):
        return f"未能查询到结果：{arg.get('error', '未知错误')}"
    result = ""
    for key in arg["data"]:
        try:
            title = result_translate[key]
            if arg["data"][key] == "未知":continue
            if isinstance(title, str):
                result += f"{title}{arg['data'][key]}\n"
            elif callable(title):
                result += title(arg["data"][key])
        except:
            continue
    if result.count("\n") <= 1:
        result = "无结果"
    return result


def handle_special_commands(message: str, user_id: str = None) -> str:
    message = message.strip()
    if not message.startswith("/"):
        return None

    if message == "/help":
        # 由于helpCommandHandler已经根据权限生成了帮助文本，这里返回基础帮助文本
        # 主要用于向后兼容，实际显示会由helpCommandHandler处理
        return BASE_HELP_TEXT

    if message.startswith("/api"):
        parts = message.split()
        if len(parts) == 1:
            return f"当前的api地址是：{plugin_config.api_url}"
        elif len(parts) == 2:
            current_user = user_id if user_id is not None else (
                plugin_config.admin_users[0] if plugin_config.admin_users else "")
            if current_user in plugin_config.admin_users:
                url = parts[1]
                if url[:4] not in ("http", "https"):
                    url = "http://" + url
                if url[-1] == '/':
                    url = url[:-1]
                plugin_config.api_url = url
                plugin_config.save_all()
                return f"已将api地址设置为：{url}"
            else:
                return "你没有权限更改api地址"
        else:
            return "指令格式错误，正确用法：/api <url>（修改地址） 或 /api（显示地址）"

    return "未知指令，输入/help查看支持的指令"


def handle_list_command(list_type: str, args: list) -> str:
    """处理黑白名单命令"""
    # 如果没有参数，默认执行list操作
    if not args:
        args = ["list"]

    list_mapping = {
        ("whitelist", "user"): "whitelist_user",
        ("whitelist", "group"): "whitelist_group",
        ("blacklist", "user"): "blacklist_user",
        ("blacklist", "group"): "blacklist_group"
    }
    all_types = ["user", "group"]
    operation = args[0].lower()

    if operation == "add":
        if len(args) != 3:
            return f"添加指令格式错误：/{list_type} add <user/group> <id>"
        target_type, target_id = args[1].lower(), args[2].strip()
        if target_type not in all_types:
            return "类型错误，只能是user或group"
        list_field = list_mapping[(list_type, target_type)]
        target_list = getattr(plugin_config, list_field)
        if target_id in target_list:
            return f"{list_type}中已存在{target_type} {target_id}"
        target_list.append(target_id)
        plugin_config.save_all()
        return f"已将{target_type} {target_id}添加到{list_type}"

    elif operation == "remove":
        if len(args) == 1:
            for target_type in all_types:
                setattr(plugin_config, list_mapping[(list_type, target_type)], [])
            plugin_config.save_all()
            return f"已清空{list_type}的所有用户和群组"
        if len(args) == 2:
            target_type = args[1].lower()
            if target_type not in all_types:
                return "类型错误，只能是user或group"
            list_field = list_mapping[(list_type, target_type)]
            if not getattr(plugin_config, list_field):
                return f"{list_type}的{target_type}列表已为空"
            setattr(plugin_config, list_field, [])
            plugin_config.save_all()
            return f"已清空{list_type}的{target_type}列表"
        if len(args) == 3:
            target_type, target_id = args[1].lower(), args[2].strip()
            if target_type not in all_types:
                return "类型错误，只能是user或group"
            list_field = list_mapping[(list_type, target_type)]
            target_list = getattr(plugin_config, list_field)
            if target_id not in target_list:
                return f"{list_type}的{target_type}列表中不存在{target_id}"
            target_list.remove(target_id)
            plugin_config.save_all()
            return f"已从{list_type}的{target_type}列表移除{target_id}"
        return f"移除指令格式错误，最多3个参数：/{list_type} remove [user/group] [id]"

    elif operation == "list":
        if len(args) == 1:
            result = [f"{list_type}列表："]
            for target_type in all_types:
                list_field = list_mapping[(list_type, target_type)]
                target_list = getattr(plugin_config, list_field)
                result.append(f"\n{target_type}列表：")
                result.extend([f"- {id_}" for id_ in target_list]) if target_list else result.append("(空)")
            return "\n".join(result)
        if len(args) == 2:
            target_type = args[1].lower()
            if target_type not in all_types:
                return "类型错误，只能是user或group"
            list_field = list_mapping[(list_type, target_type)]
            target_list = getattr(plugin_config, list_field)
            result = [f"{list_type}的{target_type}列表："]
            result.extend([f"- {id_}" for id_ in target_list]) if target_list else result.append("(空)")
            return "\n".join(result)
        return f"列表指令格式错误，最多2个参数：/{list_type} list [user/group]"

    else:
        return f"未知操作：{operation}，支持add/remove/list"


def handle_admin_command(args: list) -> str:
    """处理管理员管理命令（仅所有者可用）"""
    if not args:
        return "管理员命令格式错误，示例：\n" \
               "/admin add <id> → 添加管理员\n" \
               "/admin remove <id> → 移除管理员\n" \
               "/admin list → 列出所有管理员"

    operation = args[0].lower()

    # 添加管理员
    if operation == "add":
        if len(args) != 2:
            return "添加管理员格式错误：/admin add <id>"
        admin_id = args[1].strip()
        if admin_id in plugin_config.admin_users:
            return f"ID {admin_id} 已是管理员"
        # 防止移除所有者的管理员权限（如果所有者在admin_users中）
        if admin_id == plugin_config.owner and admin_id not in plugin_config.admin_users:
            plugin_config.admin_users.append(admin_id)
            plugin_config.save_all()
            return f"已添加所有者 {admin_id} 为管理员"
        plugin_config.admin_users.append(admin_id)
        plugin_config.save_all()
        return f"已添加 {admin_id} 为管理员"

    # 移除管理员
    elif operation == "remove":
        if len(args) != 2:
            return "移除管理员格式错误：/admin remove <id>"
        admin_id = args[1].strip()
        # 禁止移除所有者
        if admin_id == plugin_config.owner:
            return "禁止移除所有者的管理员权限"
        if admin_id not in plugin_config.admin_users:
            return f"ID {admin_id} 不是管理员"
        plugin_config.admin_users.remove(admin_id)
        plugin_config.save_all()
        return f"已移除 {admin_id} 的管理员权限"

    # 列出管理员
    elif operation == "list":
        if len(args) != 1:
            return "列出管理员格式错误：/admin list"
        result = ["管理员列表："]
        if plugin_config.admin_users:
            for idx, admin_id in enumerate(plugin_config.admin_users, 1):
                # 标记所有者
                mark = "（所有者）" if admin_id == plugin_config.owner else ""
                result.append(f"{idx}. {admin_id}{mark}")
        else:
            result.append("(空)")
        return "\n".join(result)

    else:
        return f"未知操作：{operation}，支持add/remove/list"


def get_message_result(message: str) -> str:
    try:
        message = message.strip()
        if not message:
            return "请输入查询内容（格式：查[料号] / 搜[关键词] / ID[12位ID] / 查DRAM[料号]）"
        # 全局判断查询参数长度，提取参数部分并检查
        if message.lower().startswith("查dram"):
            # 对于查DRAM命令，提取命令后的部分
            param = message[6:].strip()  # 6=len("查dram")
        elif message.lower().startswith("id"):
            # 对于ID命令，提取命令后的部分
            param = message[2:].strip()
        elif message.startswith("查") or message.startswith("搜"):
            # 对于查和搜命令，提取命令后的部分
            param = message[1:].strip()
        else:
            # 其他命令不进行长度检查
            param = None
        
        # 如果有参数且长度超过32，则返回错误信息
        if param is not None and len(param) > 32:
            return "查询参数过长，请输入不超过32个字符"

        result = ""
        # 新增：处理DRAM查询指令（支持大小写不敏感）
        if message.lower().startswith("查dram"):
            dram_pn = message[6:].strip()  # 截取"查DRAM"后的料号（6=len("查dram")）
            result = get_dram_detail(dram_pn)
        # 原有Flash查询指令
        elif message.lower().startswith(("id")):
            result = get_detail_from_ID(message[2:].strip())
        elif message.startswith(("查")):
            result = get_detail(message[1:].strip())
        elif message.startswith(("搜")):
            search_res = search(message[1:].strip())
            if not search_res.get("result", False):
                result = f"搜索失败：{search_res.get('error', '未知错误')}"
            else:
                data = search_res.get("data", [])
                result = "可能的结果：\n" + "\n".join(data[:10])
        else:
            result = "未知命令（支持：查[料号] / 搜[关键词] / ID[12位ID] / 查DRAM[料号] / /help）"
        return result
    except Exception as e:
        return f"处理错误：{str(e)}"


def instance():
    print("命令行模式：支持 查/搜/ID/查DRAM 指令，也可使用 /help 查看帮助（exit退出）")
    while True:
        try:
            message = input("> ")
            if message.lower() == "exit":
                break
            print(get_message_result(message))
        except Exception as e:
            print(f"错误：{e}")


if __name__ == "__main__":
    if 'plugin_config' not in globals():
        from .FDConfig import Config

        # 不传递路径参数，让Config内部处理正确的配置文件路径
        plugin_config = Config.from_file()
    instance()