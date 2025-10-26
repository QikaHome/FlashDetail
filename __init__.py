import requests
import re
from .FDConfig import config_instance as plugin_config
from . import FDQueryMethods
import urllib3

# 抑制因忽略SSL验证产生的警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
try:
    from nonebot import *
    from nonebot.adapters import Event, Message
    from nonebot.rule import startswith
    from nonebot.params import CommandArg

    async def is_enabled_for(event: Event) -> bool:
        return plugin_config.is_valid_user(event.get_session_id().split("_"))


    def is_admin(user_id: str) -> bool:
        return user_id in plugin_config.admin_users


    def is_owner(user_id: str) -> bool:
        """判断是否为所有者（仅owner可管理管理员）"""
        return user_id == plugin_config.owner


    # 插件版本信息
    PLUGIN_VERSION = "2.0.0"
    
    # 基础帮助文本（所有用户可见）
    BASE_HELP_TEXT = """目前支持的指令：
    查 [料号] → 精确查询Flash料号详情
    搜 [部分料号] → 模糊搜索Flash料号
    ID [颗粒ID] → 解析Flash颗粒ID（不足12位自动补0）
    查DRAM [料号] → 精确查询DRAM料号详情（例：查DRAM NT5AD1024M8C3-HR）
    /micron [料号] → 解析Micron料号并返回完整part-number
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
    micron_cmd = on_command("micron", priority=1, rule=is_enabled_for, block=False)  # Micron料号解析命令
    listened_commands = startswith(("ID", "查", "搜"), ignorecase=True)
    MessageHandler = on_message(priority=10, rule=is_enabled_for & listened_commands, block=False)
    help_cmd = on_command("help", priority=1, rule=is_enabled_for, block=False)
    api_cmd = on_command("api", priority=1, rule=is_enabled_for, block=False)
    api_fe_cmd = on_command("api_fe", priority=1, rule=is_enabled_for, block=False)  # 不显示在帮助中
    reload_cmd = on_command("reload", priority=1, rule=is_enabled_for, block=False)
    status_cmd = on_command("status", priority=1, rule=is_enabled_for, block=False)
    version_cmd = on_command("version", priority=1, rule=is_enabled_for, block=False)
    op_cmd = on_command("op", priority=1, rule=is_enabled_for, block=True)
    deop_cmd = on_command("deop", priority=1, rule=is_enabled_for, block=True)
    ban_cmd = on_command("ban", priority=1, rule=is_enabled_for, block=True)
    pardon_cmd = on_command("pardon", priority=1, rule=is_enabled_for, block=True)


    # 重载配置
    @reload_cmd.handle()
    async def reload_config_handler(event: Event):
        # 先检查是否为所有者
        if not is_owner(event.get_user_id()):
            await reload_cmd.finish("权限不足，只有所有者可以重载配置")
        else:
            try:
                reload_cmd.send("正在尝试重载，可能需要一些时间\n重载完成后不会自动提醒，请手动检查状态")
                with open(__file__, "a") as f:
                    f.write("# reload\n")
            except Exception as e:
                await reload_cmd.finish(f"配置重载失败: {str(e)}")
    
    # 状态查询命令
    @status_cmd.handle()
    async def status_handler(event: Event):
        # 获取配置状态信息
        status_info = [
            f"FlashDetect API地址: {plugin_config.flash_detect_api_url}"
        ]
        status_info.append("FlashDetail 插件状态信息")
        status_info.append(f"版本: {PLUGIN_VERSION}")
        # 移除不再使用的api_url引用
        status_info.append(f"所有者: {plugin_config.owner}")
        status_info.append(f"管理员数量: {len(plugin_config.admin_users)}")
        status_info.append(f"白名单用户数: {len(plugin_config.whitelist_user)}")
        status_info.append(f"白名单群组数: {len(plugin_config.whitelist_group)}")
        status_info.append(f"黑名单用户数: {len(plugin_config.blacklist_user)}")
        status_info.append(f"黑名单群组数: {len(plugin_config.blacklist_group)}")
        
        # 检查API连接状态
        try:
            response = requests.get(f"{plugin_config.flash_detect_api_url}", timeout=3)
            api_status = "正常" if response.status_code == 200 else "异常"
        except Exception:
            api_status = "连接失败"
        status_info.append(f"API连接状态: {api_status}")
        
        await status_cmd.finish("\n".join(status_info))
    
    # 版本查询命令
    @version_cmd.handle()
    async def version_handler(event: Event):
        version_info = [
            f"FlashDetail 插件 v{PLUGIN_VERSION}",
            "功能: Flash和DRAM料号查询工具",
            "支持命令: 查/搜/ID/查DRAM/help/api/admin/whitelist/blacklist/status/version/reload/micron",
            "作者: Qikahome/3281",
            "仅供学习和测试使用"
        ]
        await version_cmd.finish("\n".join(version_info))
    # 帮助命令
    @help_cmd.handle()
    async def help_command_handler(event: Event):
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
    async def message_handler(foo: Event):
        # 不再需要单独检查用户有效性，因为is_enabled_for规则已经做了检查
        result = get_message_result(foo.get_plaintext())
        if result and result[-1] == '\n':
            result = result[:-1]
        if result: 
            await MessageHandler.finish(result)
        else:
            await MessageHandler.finish()


    # API命令
    @api_cmd.handle()
    async def api_command_handler(event: Event, arg: Message = CommandArg()):
        # 不再需要单独检查用户有效性，因为is_enabled_for规则已经做了检查
        user_id = event.get_user_id()
        arg_text = arg.extract_plain_text().strip()
        parts = arg_text.split() if arg_text else []
        
        if not parts:
            await api_cmd.finish(f"当前的api地址是：{plugin_config.flash_detect_api_url}")
            return
        elif len(parts) == 1:
            if user_id in plugin_config.admin_users:
                url = parts[0]
                if url[:4] not in ("http", "https"):
                    url = "http://" + url
                if url[-1] == '/':
                    url = url[:-1]
                plugin_config.flash_detect_api_url = url
                plugin_config.save_all()
                await api_cmd.finish(f"已将api地址设置为：{url}")
            else:
                await api_cmd.finish("你没有权限更改api地址")
        else:
            await api_cmd.finish("指令格式错误，正确用法：/api <url>（修改地址） 或 /api（显示地址）")


    # FlashExtra API命令（不显示在帮助中）
    @api_fe_cmd.handle()
    async def api_fe_command_handler(event: Event, arg: Message = CommandArg()):
        # 不再需要单独检查用户有效性，因为is_enabled_for规则已经做了检查
        user_id = event.get_user_id()
        arg_text = arg.extract_plain_text().strip()
        parts = arg_text.split() if arg_text else []
        
        if not parts:
            await api_fe_cmd.finish(f"当前的FlashExtra api地址是：{plugin_config.flash_extra_api_url}")
            return
        elif len(parts) == 1:
            if user_id in plugin_config.admin_users:
                url = parts[0]
                if url[:4] not in ("http", "https"):
                    url = "http://" + url
                if url[-1] == '/':
                    url = url[:-1]
                plugin_config.flash_extra_api_url = url
                plugin_config.save_all()
                await api_fe_cmd.finish(f"已将FlashExtra api地址设置为：{url}")
            else:
                await api_fe_cmd.finish("你没有权限更改api地址")
        else:
            await api_fe_cmd.finish("指令格式错误，正确用法：/api_fe <url>（修改地址） 或 /api_fe（显示地址）")
        
    # Micron料号解析命令
    @micron_cmd.handle()
    async def micron_handler(event: Event, arg: Message = CommandArg()):
        # 不再需要单独检查用户有效性，因为is_enabled_for规则已经做了检查
        args=arg.extract_plain_text().strip().split("--")
        args = [arga.strip() for arga in args]
        debug = "debug" in args
        pn = args[0]
        if not pn:
            await micron_cmd.finish("请输入Micron料号")
            return
        
        # 调用parse_micron_pn函数解析料号
        result = FDQueryMethods.parse_micron_pn(pn,debug=debug)
        
        # 检查并返回part-number
        if "detail" in result and "part-number" in result["detail"]:
            await micron_cmd.finish(f"完整料号: {result['detail']['part-number']}")
        elif "part-number" in result:
            await micron_cmd.finish(f"完整料号: {result['part-number']}")
        else:
            error_msg = result.get("error", "解析失败，未找到料号信息")
            await micron_cmd.finish(error_msg)


    # 白名单命令
    @whitelist_cmd.handle()
    async def whitelist_handler(event: Event, arg: Message = CommandArg()):
        user_id = event.get_user_id()
        if not is_admin(user_id):
            return
        args = arg.extract_plain_text().strip().split()
        result = handle_list_command("whitelist", args)
        if result:
            await whitelist_cmd.finish(result)


    # 黑名单命令
    @blacklist_cmd.handle()
    async def blacklist_handler(event: Event, arg: Message = CommandArg()):
        user_id = event.get_user_id()
        if not is_admin(user_id):
            return
        args = arg.extract_plain_text().strip().split()
        result = handle_list_command("blacklist", args)
        if result:
            await blacklist_cmd.finish(result)


    # 管理员管理命令（仅所有者可用）
    @admin_cmd.handle()
    async def admin_handler(event: Event, arg: Message = CommandArg()):
        user_id = event.get_user_id()
        if not is_owner(user_id):  # 仅所有者可操作
            return
        args = arg.extract_plain_text().strip().split()
        result = handle_admin_command(args)
        if result:
            await admin_cmd.finish(result)
    
    # 将用户设为管理员（仅所有者可用）
    @op_cmd.handle()
    async def op_handler(event: Event, arg: Message = CommandArg()):
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
    async def deop_handler(event: Event, arg: Message = CommandArg()):
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
    async def ban_handler(event: Event, arg: Message = CommandArg()):
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
    async def pardon_handler(event: Event, arg: Message = CommandArg()):
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

except Exception as e:
    print(f"not running in onebot: {e}")


def classification(arg: dict[str, int]) -> str:
    result=""
    if(arg.get('ch') and arg['ch']!="未知"):
        result += f"{translations['channel']}{arg['ch']}\n"
    if(arg.get('ce') and arg['ce']!="未知"):
        result += f"{translations['ce']}{arg['ce']}\n"
    if(arg.get('die') and arg['die']!="未知"):
        result += f"{translations['die']}{arg['die']}\n"
    return result

def flashId(arg: list[str]) -> str:
    return "" if not arg else f"{translations['availableID']}{', '.join(arg)}\n"


translations = {
    "id": "", "vendor": "厂商：", "die": "Die数量：", "plane": "平面数：",
    "pageSize": "页面大小：", "blockSize": "块大小：", "processNode": "制程：",
    "cellLevel": "单元类型：", "partNumber": "料号：", "type": "类型：", "density": "容量：",
    "channel": "通道数：","ce": "片选：","die": "Die数量：","availablePn": "可能的料号：",
    "deviceWidth": "位宽：","voltage": "电压：", "generation": "代数：", "package": "封装：", 
    "availableID": "可能的ID：","depth": "深度：","grade": "等级：","speed": "速度：",
    "vendor_code": "厂商代码：","version": "版本：","width": "位宽："
}

data_parsers = {"classification": classification, "availableID": flashId}


def result_to_text(arg: dict) -> str:
    if not arg.get("result", False):
        return f"未能查询到结果：{arg.get('error', '未知错误')}"
    result = ""
    data=arg.get("data", {})
    if isinstance(data,dict):
        for key,value in data.items():
            if(value == "未知" or not value):continue
            if(key == "density"):
                result += f"{translations[key]}{FDQueryMethods.format_density(value,int(data.get('width', 8)))}\n"
                continue
            func=data_parsers.get(key, None)
            if func:
                result += func(value)
            else:
                trans=translations.get(key, None)
                if trans:
                    result += f"{trans}{value}\n"
        if(result.count("\n")<2):
            result=""
    elif isinstance(data, list):
        result += f"{translations['availablePn']}{', '.join(data)}\n"
    return result

def all_numbers_alpha(string: str) -> bool:
    # 使用正则表达式判断字符是否在0-9A-Za-z_/:-范围内
    return string and all(re.match(r'^[0-9A-Za-z_/:\-]$', c) for c in string)

def ID(arg: str, refresh: bool=False,debug: bool=False) -> str:
    raw_result=FDQueryMethods.get_detail_from_ID(arg, refresh)
    result = result_to_text(raw_result)
    if result: raw_result["accept"]()
    if not result:
        if all_numbers_alpha(arg):
            result = "无结果"
    return result

def 查(arg: str, retry: bool=True, refresh: bool=False,debug: bool=False) -> str:
    raw_result=FDQueryMethods.get_detail(arg, refresh)
    result = result_to_text(raw_result)
    if result: raw_result["accept"]()
    if not result and retry:
        search_result = FDQueryMethods.search(arg)
        if search_result.get("result", False) and search_result.get("data", []):
            result = f"可能的料号：{search_result["data"][0].split()[-1]}\n{查(search_result["data"][0].split()[-1], False,debug)}"
    if not result:
        if all_numbers_alpha(arg):
            result = "无结果"
    return result

def 搜(arg: str,debug: bool=False) -> str:
    result = result_to_text(FDQueryMethods.search(arg,debug))
    if not result:
        if all_numbers_alpha(arg):
            result = "无结果"
    return result



def 查DRAM(arg: str, refresh: bool=False,debug: bool=False) -> str:
    raw_result=FDQueryMethods.get_dram_detail(arg, refresh)
    result = result_to_text(raw_result)
    if result: raw_result["accept"]()
    if not result:
        result = "无结果"
    return result

def get_message_result(message: str) -> str:
    try:
        
        # 如果有参数且长度超过32，则返回错误信息
        if len(message) > 32:
            return "查询参数过长，请输入不超过32个字符"
        args = message.split("--")
        args = [arg.strip() for arg in args]
        message=args[0]
        refresh_flag="refresh" in args
        debug_flag="debug" in args
        result = ""
        # 新增：处理DRAM查询指令（支持大小写不敏感）
        if message.lower().startswith("查dram"):
            result = 查DRAM(message[6:].strip(), refresh=refresh_flag,debug=debug_flag)
        # 原有Flash查询指令
        elif message.lower().startswith(("id")):
            result = ID(message[2:].strip(), refresh=refresh_flag,debug=debug_flag)
        elif message.startswith(("查")):
            result = 查(message[1:].strip(), refresh=refresh_flag,debug=debug_flag)
        elif message.startswith(("搜")):
            result = 搜(message[1:].strip(),debug=debug_flag)
        else:
            result = "未知命令(请使用/help获取帮助)"
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

# reload
# reload
# reload
