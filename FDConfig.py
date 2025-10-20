from pydantic import BaseModel, field_validator, ValidationError
import json
from pathlib import Path
from typing import Any
import os


class Config(BaseModel):
    # 核心配置字段
    admin_users: list[str] = ["1828665870"]  # 默认管理员包含所有者
    api_url: str = "https://fd.sakuracg.com"
    whitelist_user: list[str] = []
    blacklist_user: list[str] = []
    whitelist_group: list[str] = []
    blacklist_group: list[str] = []

    # 新增：所有者ID（拥有最高权限）
    owner: str = "1828665870"  # 默认所有者

    # 验证器
    @field_validator("admin_users", "whitelist_user", "blacklist_user", "whitelist_group", "blacklist_group", "owner")
    def id_must_be_str(cls, v):
        if isinstance(v, list):
            if not all(isinstance(id_, str) for id_ in v):
                raise ValueError("ID列表元素必须为字符串")
        else:  # 对owner字段单独验证
            if not isinstance(v, str):
                raise ValueError("所有者ID必须为字符串")
        return v

    @field_validator("api_url")
    def api_url_must_be_valid(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("API URL必须以http://或https://开头")
        return v

    def save_all(self, path: str = None) -> None:
        # 如果没有指定路径，使用插件目录下的config.json
        if path is None:
            # 获取当前文件所在目录的绝对路径
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(plugin_dir, "config.json")
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.model_dump(), f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"保存配置失败: {e}")

    @classmethod
    def from_file(cls, path: str = None, **kwargs: Any) -> "Config":
        # 如果没有指定路径，使用插件目录下的config.json
        if path is None:
            # 获取当前文件所在目录的绝对路径
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(plugin_dir, "config.json")
        
        if Path(path).exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                
                # 确保所有必要的字段都存在
                default_config = cls()
                for key, default_value in default_config.model_dump().items():
                    if key not in config_data:
                        config_data[key] = default_value
                
                config_data.update(kwargs)
                config = cls(**config_data)
                return config
            except (IOError, json.JSONDecodeError, ValidationError) as e:
                print(f"加载配置失败，使用默认配置并保存: {e}")
                # 创建默认配置并保存
                config = cls(**kwargs)
                config.save_all(path)
                return config
        else:
            # 文件不存在，创建默认配置并保存
            print(f"配置文件不存在，创建默认配置: {path}")
            config = cls(**kwargs)
            config.save_all(path)
            return config
    
    def load_config(self, path: str = None) -> None:
        """从文件重新加载配置到当前实例"""
        # 如果没有指定路径，使用插件目录下的config.json
        if path is None:
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(plugin_dir, "config.json")
        
        if Path(path).exists():
            try:
                # 先创建一个新的实例以确保验证通过
                new_config = self.from_file(path)
                
                # 验证通过后，更新当前实例的所有字段
                for key, value in new_config.model_dump().items():
                    if hasattr(self, key):
                        setattr(self, key, value)
                
                print(f"配置已从{path}重载")
            except (IOError, json.JSONDecodeError, ValidationError) as e:
                print(f"重载配置失败: {e}")
                raise
        else:
            print(f"配置文件不存在: {path}")
            raise FileNotFoundError(f"配置文件不存在: {path}")

    def is_valid_user(self, args: list[str]) -> bool:
        # 检查参数有效性
        if not args or len(args) < 1:
            return False
        
        user_id = args[0]
        # 处理群组消息情况
        if len(args) >= 3 and args[0] == "group":
            group_id = args[1]
            user_id = args[2]
            
            # 检查群组权限
            if self.whitelist_group and group_id not in self.whitelist_group:
                return False
            if group_id in self.blacklist_group:
                return False
        
        # 检查用户权限
        if self.whitelist_user and user_id not in self.whitelist_user:
            return False
        if user_id in self.blacklist_user:
            return False
        
        return True
