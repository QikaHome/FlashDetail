import json
import requests
import sqlite3
import os
from bs4 import BeautifulSoup
import urllib3

from .FDConfig import config_instance as config

# 抑制因忽略SSL验证产生的警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), 'flash_data.db')

# 初始化数据库
def init_database():
    """初始化SQLite数据库和表结构"""
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        # 连接数据库
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 创建flash详情表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS flash_detail (
            part_number TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            timestamp INTEGER DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 创建dram详情表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS dram_detail (
            part_number TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            timestamp INTEGER DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 创建flash ID详情表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS flash_id_detail (
            flash_id TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            timestamp INTEGER DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 创建micron_pn_decode表，用于存储镁光料号解码结果
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS micron_pn_decode (
            part_number TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            timestamp INTEGER DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 创建索引提升查询性能
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_flash_timestamp ON flash_detail(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_dram_timestamp ON dram_detail(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_flash_id_timestamp ON flash_id_detail(timestamp)')
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"数据库初始化失败: {str(e)}")

# 数据库读写函数
def save_to_database(table_name, key, data):
    """保存数据到数据库，只存储data部分"""
    try:
        # 只保存字典中的data部分，避免存储accept方法
        if isinstance(data, dict):
            # 创建一个新字典，只包含result和data字段
            save_data = {
                "result": data.get("result", False),
                "data": data.get("data", {})
            }
            # 如果有error字段也保存
            if "error" in data:
                save_data["error"] = data["error"]
        else:
            save_data = data
            
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        json_data = json.dumps(save_data)
        
        # 使用UPSERT语法（SQLite 3.24+支持）
        cursor.execute(
            f"INSERT OR REPLACE INTO {table_name} VALUES (?, ?, CURRENT_TIMESTAMP)",
            (key, json_data)
        )
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"保存到数据库失败: {str(e)}")
        return False

def get_from_database(table_name, key):
    """从数据库获取数据，并确保返回格式正确"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 根据不同的表名确定正确的主键名
        if table_name == 'flash_id_detail':
            primary_key = 'flash_id'
        elif table_name == 'micron_pn_decode':
            primary_key = 'part_number'
        else:
            primary_key = table_name[:-7]  # 移除"_detail"后缀
            
        cursor.execute(f"SELECT data FROM {table_name} WHERE {primary_key} = ?", (key,))
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            data = json.loads(result[0])
            # 确保返回的字典格式正确，包含result和data字段
            if isinstance(data, dict):
                # 为返回的数据添加accept方法（空操作，因为数据已经在数据库中）
                data["accept"] = lambda: None
            return data
        return None
    except Exception as e:
        print(f"从数据库读取失败: {str(e)}")
        return None

# 初始化数据库
init_database()

# 容量单位转换函数
def format_density(arg,width:int=8) -> str:
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
        elif value.endswith("G"): #对于dram需要特殊处理
            num = float(value[:-1])
            bytes_val = num * 1024 * width / 8
        elif value.endswith("M"):
            num = float(value[:-1])
            bytes_val = num * width / 8 
        else:
            num = float(value)  # 纯数字默认视为 Mb
            bytes_val = num / 8  # 转换为 MB

        # 按1024进位选择单位，并处理小数
        if bytes_val >= 1024 * 1024:
            # 转换为 TB
            tb = bytes_val / (1024 * 1024)
            if tb.is_integer():
                return f"{int(tb)} TB"
            return f"{tb:.2f} TB"
        elif bytes_val >= 1024:
            # 转换为 GB
            gb = bytes_val / 1024
            if gb.is_integer():
                return f"{int(gb)} GB"
            return f"{gb:.2f} GB"
        else:
            # 保留为 MB
            if bytes_val.is_integer():
                return f"{int(bytes_val)} MB"       
            return f"{bytes_val:.2f} MB"
    except (ValueError, TypeError) as e:
        print(f"容量单位转换错误: {str(e)}")
        # 格式无效时直接返回原始值（带前缀和换行）
        return f"{arg}"

# HTTP请求工具函数
def get_html_with_requests(url: str,debug: bool=False) -> requests.Response:
    """使用requests库获取HTML内容，忽略HTTPS证书验证错误"""
    if debug:
        print(f"请求URL: {url}")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # 添加verify=False参数以忽略SSL证书验证错误
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        return response
    except Exception as e:
        print(f"HTTP请求失败: {str(e)}")
        return None

# 十六进制验证函数
def is_hex(s: str) -> bool:
    """检查字符串是否全为十六进制字符"""
    try:
        int(s, 16)
        return True
    except ValueError:
        return False

def get_detail(arg: str, refresh: bool = False,debug: bool=False) -> dict:
    """获取闪存料号详细信息
    
    Args:
        arg: 闪存料号
        firstTime: 是否首次查询
        refresh: 是否强制刷新数据（不使用缓存）
        debug: 是否开启调试模式
        
    Returns:
        查询结果字典，包含accept方法用于保存数据到数据库
    """
    if not arg.strip():
        result = {"result": False, "error": "料号不能为空"}
        # 添加accept方法（对于失败结果，不执行任何操作）
        result["accept"] = lambda: None
        return result
    
    try:
        # 尝试从缓存获取数据（如果不是强制刷新）
        if not refresh:
            cached_data = get_from_database('flash_detail', arg)
            if cached_data:
                # 为缓存数据添加accept方法（不执行任何操作，因为已经在数据库中）
                cached_data["accept"] = lambda: None
                return cached_data
                
        if is_hex(arg) and arg.startswith("89","45","2C","EC","AD","98","9B"):
            return get_detail_from_ID(arg,debug)
            
        html = get_html_with_requests(f"{config.flash_detect_api_url}/decode?lang=chs&pn={arg}",debug)
        if not html:
            result = {"result": False, "error": "API请求失败"}
            result["accept"] = lambda: None
            return result
            
        soup = BeautifulSoup(html.text, 'lxml')
        p_tags = soup.find('p')
        if p_tags:
            result = json.loads(p_tags.get_text())
            # 添加accept方法，仅在调用时保存数据到数据库
            if result.get("result"):
                def accept_func():
                    save_to_database('flash_detail', arg, result)
                    # 移除accept方法，避免重复调用
                    if "accept" in result:
                        del result["accept"]
                result["accept"] = accept_func
            else:
                result["accept"] = lambda: None
            return result
            
        result = {"result": False, "error": "未找到有效数据"}
        result["accept"] = lambda: None
        return result
    except json.JSONDecodeError:
        result = {"result": False, "error": "API返回格式错误（非JSON）"}
        result["accept"] = lambda: None
        return result
    except Exception as e:
        result = {"result": False, "error": str(e)}
        result["accept"] = lambda: None
        return result


def search(arg: str,debug: bool=False) -> dict:
    """搜索闪存料号
    
    Args:
        arg: 搜索关键词
        debug: 是否开启调试模式
        
    Returns:
        搜索结果字典
    """
    if not arg.strip():
        return {"result": False, "error": "搜索关键词不能为空"}
    
    try:
        html = get_html_with_requests(f"{config.flash_detect_api_url}/searchPn?limit=10&lang=chs&pn={arg}",debug)
        if not html:
            return {"result": False, "error": "API请求失败"}
            
        soup = BeautifulSoup(html.text, 'lxml')
        p_tags = soup.find('p')
        if p_tags:
            result = json.loads(p_tags.get_text())
            return result
            
        return {"result": False, "error": "未找到有效数据"}
    except json.JSONDecodeError:
        return {"result": False, "error": "API返回格式错误（非JSON）"}
    except Exception as e:
        return {"result": False, "error": str(e)}


def get_detail_from_ID(arg: str, refresh: bool = False,debug: bool=False) -> dict:
    """通过闪存ID获取详细信息
    
    Args:
        arg: 闪存ID
        refresh: 是否强制刷新数据（不使用缓存）
        debug: 是否开启调试模式
        
    Returns:
        查询结果字典，包含accept方法用于保存数据到数据库
    """
    if not arg.strip():
        result = {"result": False, "error": "ID不能为空"}
        result["accept"] = lambda: None
        return result
    
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
        
        # 尝试从缓存获取数据（如果不是强制刷新）
        if not refresh:
            cached_data = get_from_database('flash_id_detail', id_str)
            if cached_data:
                cached_data["accept"] = lambda: None
                return cached_data
                
        html = get_html_with_requests(f"{config.flash_detect_api_url}/decodeId?lang=chs&id={id_str}")
        if not html:
            result = {"result": False, "error": "API请求失败"}
            result["accept"] = lambda: None
            return result
            
        soup = BeautifulSoup(html.text, 'lxml')
        p_tags = soup.find('p')
        if p_tags:
            result = json.loads(p_tags.get_text())
            # 添加accept方法，仅在调用时保存数据到数据库
            if result.get("result"):
                def accept_func():
                    save_to_database('flash_id_detail', id_str, result)
                    # 移除accept方法，避免重复调用
                    if "accept" in result:
                        del result["accept"]
                result["accept"] = accept_func
            else:
                result["accept"] = lambda: None
            return result
            
        result = {"result": False, "error": "未找到有效数据"}
        result["accept"] = lambda: None
        return result
    except json.JSONDecodeError:
        result = {"result": False, "error": "API返回格式错误（非JSON）"}
        result["accept"] = lambda: None
        return result
    except Exception as e:
        result = {"result": False, "error": str(e)}
        result["accept"] = lambda: None
        return result


# Micron料号解析函数
def parse_micron_pn(arg: str, refresh: bool = False, debug: bool=False) -> dict:
    """解析Micron PN
    
    Args:
        arg: 镁光料号
        refresh: 是否强制刷新数据（不使用缓存）
        debug: 是否开启调试模式
        
    Returns:
        查询结果字典，包含accept方法用于保存数据到数据库
    """
    if not arg.strip():
        result = {"result": False, "error": "料号不能为空"}
        result["accept"] = lambda: None
        return result
    
    pn = arg.strip().upper()
    
    # 尝试从缓存获取数据（如果不是强制刷新）
    if not refresh:
        cached_data = get_from_database('micron_pn_decode', pn)
        if cached_data:
            cached_data["accept"] = lambda: None
            return cached_data
    
    # 访问micron-online接口获取完整part-number
    micron_url = f"{config.flash_extra_api_url}/micron-online?param={pn}"
    micron_response = get_html_with_requests(micron_url, debug)
    if not micron_response:
        result = {"result": False, "error": "解码镁光料号失败"}
        result["accept"] = lambda: None
        return result
    
    try:
        # 尝试解析JSON响应
        response_data = json.loads(micron_response.text)
        # 确保返回的数据结构包含必要字段
        if "detail" not in response_data and "part-number" in response_data:
            # 如果part-number直接在根级别，将其移到detail字典中以保持一致性
            response_data["detail"] = {"part-number": response_data["part-number"]}
        
        # 添加accept方法，仅在调用时保存数据到数据库
        if response_data.get("result", True):  # 如果没有result字段，默认为True
            def accept_func():
                save_to_database('micron_pn_decode', pn, response_data)
                # 移除accept方法，避免重复调用
                if "accept" in response_data:
                    del response_data["accept"]
            response_data["accept"] = accept_func
        else:
            response_data["accept"] = lambda: None
        
        return response_data
    except json.JSONDecodeError:
        result = {"result": False, "error": "返回数据格式错误"}
        result["accept"] = lambda: None
        return result
    except Exception as e:
        result = {"result": False, "error": str(e)}
        result["accept"] = lambda: None
        return result

# DRAM料号查询函数
def get_dram_detail(arg: str, refresh: bool = False) -> dict:
    """查询DRAM详情（适配DRAM专属API）
    
    Args:
        arg: DRAM料号
        refresh: 是否强制刷新数据（不使用缓存）
        
    Returns:
        查询结果字典，包含accept方法用于保存数据到数据库
    """
    if not arg.strip():
        result = {"result": False, "error": "DRAM料号不能为空"}
        result["accept"] = lambda: None
        return result
    
    pn = arg.strip()
    
    # 处理5位DRAM料号特殊逻辑
    if len(pn) == 5:
        micron_json = parse_micron_pn(pn, refresh)
        if not micron_json.get("result"):
            result = {"result": False, "error": f"未能获取完整DRAM料号：{micron_json.get('error', '未知错误')}"}
            result["accept"] = lambda: None
            return result
        
        # 获取完整的part-number并使用它调用DRAM接口
        # 兼容不同的数据结构：part-number可能在detail字典或直接在根级别
        if "detail" in micron_json and "part-number" in micron_json["detail"]:
            full_pn = micron_json["detail"]["part-number"]
        elif "part-number" in micron_json:
            full_pn = micron_json["part-number"]
        else:
            result = {"result": False, "error": "获取完整DRAM料号失败：找不到part-number字段"}
            result["accept"] = lambda: None
            return result
        micron_json["accept"]()
    else:
        full_pn = pn
    
    # 如果不强制刷新，先尝试从数据库读取
    if not refresh:
        cached_data = get_from_database('dram_detail', full_pn)
        if cached_data:
            cached_data["accept"] = lambda: None
            return cached_data
    
    try:
        # 使用原始料号或从micron-online获取的完整料号调用DRAM接口
        url = f"{config.flash_extra_api_url}/DRAM?param={full_pn}"
        response = get_html_with_requests(url)
        if not response:
            result = {"result": False, "error": "DRAM API请求失败"}
            result["accept"] = lambda: None
            return result

        # 解析API返回的JSON
        resp_json = json.loads(response.text)
        if not resp_json.get("result"):
            result = {"result": False, "error": "未查询到DRAM信息"}
            result["accept"] = lambda: None
            return result

        # 自动将detail中所有键名转换为小写并放入data对象
        detail = resp_json.get("detail", {})
        # 先创建小写键名的字典
        data = {key.lower(): value for key, value in detail.items()}
        # 然后添加vendor字段
        data["vendor"] = resp_json.get("Vendor", "未知")
            
        result = {
            "result": True,
            "data": data
        }
        
        # 添加accept方法，仅在调用时保存数据到数据库
        def accept_func():
            save_to_database('dram_detail', full_pn, result)
            # 移除accept方法，避免重复调用
            if "accept" in result:
                del result["accept"]
        result["accept"] = accept_func
        
        return result
    except json.JSONDecodeError:
        result = {"result": False, "error": "DRAM API返回格式错误"}
        result["accept"] = lambda: None
        return result
    except Exception as e:
        result = {"result": False, "error": f"错误：{str(e)}"}
        result["accept"] = lambda: None
        return result
