from pydantic import BaseModel, field_validator, ValidationError
import json
from pathlib import Path
from typing import Any
import os


class Config(BaseModel):
    # 核心配置字段
    admin_users: list[str] = ["1828665870"]  # 默认管理员包含所有者
    flash_detect_api_urls: list[str] = ["https://fd.sakuracg.com"]
    flash_extra_api_urls: list[str] = ["https://fe-backend.barryblueice.cn"]    
    configs: dict[str, Any] = {"auto_join_group": True,"repeater": 4,"cat": True}  #其他非核心配置项
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

    @field_validator("flash_detect_api_urls", "flash_extra_api_urls")
    def api_url_must_be_valid(cls, v: list[str]) -> list[str]:
        if not all((url.startswith("http://") or url.startswith("https://")) for url in v):
            raise ValueError("API URL列表元素必须以http://或https://开头")
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
                
                # 确保所有必要的字段都存在，并自动更新旧配置
                default_config = cls()
                default_data = default_config.model_dump()
                
                # 复制旧配置中的所有字段到新配置
                updated_config = {**default_data, **config_data}
                
                # 更新额外的kwargs
                updated_config.update(kwargs)
                
                # 尝试创建配置实例
                try:
                    config = cls(**updated_config)
                    # 检查是否需要保存更新后的配置
                    needs_update = False
                    for key, value in default_data.items():
                        if key not in config_data:
                            needs_update = True
                            print(f"自动添加配置项: {key} = {value}")
                    
                    if needs_update:
                        config.save_all(path)
                        print(f"配置已自动更新: {path}")
                    
                    return config
                except ValidationError as e:
                    print(f"配置验证失败，尝试修复: {e}")
                    # 验证失败时，逐个字段尝试修复
                    fixed_config = {}
                    for key, default_value in default_data.items():
                        try:
                            # 尝试使用旧配置的值
                            if key in config_data:
                                # 使用Pydantic的验证机制检查单个字段
                                validator = getattr(cls, f"validate_{key}", None)
                                if validator:
                                    fixed_config[key] = validator(config_data[key])
                                else:
                                    fixed_config[key] = config_data[key]
                            else:
                                fixed_config[key] = default_value
                        except Exception:
                            # 字段验证失败，使用默认值
                            print(f"字段 {key} 验证失败，使用默认值: {default_value}")
                            fixed_config[key] = default_value
                    
                    # 使用修复后的配置
                    config = cls(**fixed_config)
                    config.save_all(path)
                    print(f"配置已修复并保存: {path}")
                    return config
                    
            except (IOError, json.JSONDecodeError) as e:
                print(f"加载配置文件失败，使用默认配置: {e}")
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
        """从文件重新加载配置到当前实例，支持自动更新旧版配置"""
        # 如果没有指定路径，使用插件目录下的config.json
        if path is None:
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(plugin_dir, "config.json")
        
        try:
            # 使用增强版的from_file方法，它会自动处理旧配置
            new_config = self.from_file(path)
            
            # 更新当前实例的所有字段
            for key, value in new_config.model_dump().items():
                if hasattr(self, key):
                    setattr(self, key, value)
            
            print(f"配置已成功重载: {path}")
        except Exception as e:
            print(f"重载配置时遇到问题，但将继续使用自动修复的配置: {e}")
            # 即使有异常，from_file方法也会返回可用的配置，所以继续更新当前实例
            try:
                new_config = self.from_file(path)
                for key, value in new_config.model_dump().items():
                    if hasattr(self, key):
                        setattr(self, key, value)
            except Exception:
                print("无法完全修复配置，部分设置可能使用默认值")

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

config_instance=Config.from_file()