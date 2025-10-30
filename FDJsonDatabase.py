import json
import os
import threading
from typing import Dict, Any, Optional

class JsonDatabase:
    """基于JSON文件的简单数据库实现"""
    
    def __init__(self, db_path: str):
        """初始化JSON数据库
        
        Args:
            db_path: JSON数据库文件路径
        """
        self.db_path = db_path
        self.lock = threading.RLock()  # 使用可重入锁确保线程安全
        self.data = self._load_data()
    
    def _load_data(self) -> Dict[str, Dict[str, Any]]:
        """从文件加载数据
        
        Returns:
            数据库字典，格式为 {table_name: {key: value}}
        """
        if not os.path.exists(self.db_path):
            # 如果文件不存在，创建目录并返回空数据
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            return {}
        
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"加载JSON数据库失败: {e}")
            return {}
    
    def _save_data(self) -> bool:
        """保存数据到文件
        
        Returns:
            是否保存成功
        """
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            return True
        except IOError as e:
            print(f"保存JSON数据库失败: {e}")
            return False
    
    def get(self, table_name: str, key: str) -> Optional[Dict[str, Any]]:
        """从指定表获取数据
        
        Args:
            table_name: 表名
            key: 键名（将自动转换为小写进行不区分大小写查询）
            
        Returns:
            查询结果，如果不存在返回None
        """
        with self.lock:
            if table_name not in self.data:
                return None
            
            # 转换为小写进行不区分大小写查询
            lower_key = key.lower()
            return self.data[table_name].get(lower_key)
    
    def set(self, table_name: str, key: str, value: Dict[str, Any]) -> bool:
        """设置数据到指定表
        
        Args:
            table_name: 表名
            key: 键名（将自动转换为小写存储）
            value: 要存储的值
            
        Returns:
            是否设置成功
        """
        with self.lock:
            # 确保表存在
            if table_name not in self.data:
                self.data[table_name] = {}
            
            # 转换为小写存储
            lower_key = key.lower()
            self.data[table_name][lower_key] = value
            
            # 保存到文件
            return self._save_data()
    
    def delete(self, table_name: str, key: str) -> bool:
        """从指定表删除数据
        
        Args:
            table_name: 表名
            key: 键名（将自动转换为小写）
            
        Returns:
            是否删除成功
        """
        with self.lock:
            if table_name not in self.data:
                return False
            
            # 转换为小写进行不区分大小写删除
            lower_key = key.lower()
            if lower_key in self.data[table_name]:
                del self.data[table_name][lower_key]
                return self._save_data()
            return False
    
    def list_keys(self, table_name: str) -> list:
        """列出指定表的所有键
        
        Args:
            table_name: 表名
            
        Returns:
            键名列表
        """
        with self.lock:
            if table_name not in self.data:
                return []
            return list(self.data[table_name].keys())
    
    def clear_table(self, table_name: str) -> bool:
        """清空指定表
        
        Args:
            table_name: 表名
            
        Returns:
            是否清空成功
        """
        with self.lock:
            if table_name not in self.data:
                return False
            
            self.data[table_name] = {}
            return self._save_data()

# 创建全局数据库实例
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'flash_detail_db.json')
db_instance = JsonDatabase(DB_PATH)

# 数据库操作函数
def save_to_database(table_name: str, key: str, data: dict, debug: bool = False) -> bool:
    """保存数据到数据库
    
    Args:
        table_name: 表名
        key: 键名
        data: 要保存的数据
        debug: 是否显示调试信息
        
    Returns:
        是否保存成功
    """
    try:
        # 只保存字典中的关键部分
        save_data={}
        save_data["data"] = data["data"].copy()
        save_data["data"].pop('url') if 'url' in save_data["data"] else None
        save_data["data"].pop('urls') if 'urls' in save_data["data"] else None
        if debug:
            print(f"保存到JSON数据库: {table_name} - {key} - {save_data}")
            
        # 保存到数据库
        return db_instance.set(table_name, key, save_data)
    except Exception as e:
        print(f"保存到JSON数据库失败: {str(e)}")
        return False

def get_from_database(table_name: str, key: str, debug: bool = False) -> Optional[dict]:
    """从数据库获取数据
    
    Args:
        table_name: 表名
        key: 键名
        debug: 是否显示调试信息
        
    Returns:
        查询结果，如果不存在返回None
    """
    try:
        # 从数据库获取数据
        result = db_instance.get(table_name, key)
        
        if debug:
            print(f"从JSON数据库读取: {table_name} - {key} - {result}")
        
        # 如果获取到数据，添加accept方法（空操作）
        if result and isinstance(result, dict):
            result["accept"] = lambda: None
        
        return result
    except Exception as e:
        print(f"从JSON数据库读取失败: {str(e)}")
        return None