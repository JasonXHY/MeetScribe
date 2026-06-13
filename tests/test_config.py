#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe Config 单元测试
"""

import os
import tempfile
import pytest
from config import Config


class TestConfig:
    """Config 类测试"""

    def test_config_import(self):
        """测试 Config 类可以导入"""
        assert hasattr(Config, '__init__')

    def test_config_default_values(self):
        """测试默认配置值"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{}')
            temp_path = f.name

        try:
            config = Config(temp_path)
            assert config.get("recording_mode") == "dual"
            assert config.get("use_vb_cable") is False
        finally:
            os.remove(temp_path)

    def test_config_get_set(self):
        """测试配置读写"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{}')
            temp_path = f.name

        try:
            config = Config(temp_path)
            config.set("test_key", "test_value")
            assert config.get("test_key") == "test_value"
        finally:
            os.remove(temp_path)

    def test_config_save_load(self):
        """测试配置保存和加载"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{}')
            temp_path = f.name

        try:
            config = Config(temp_path)
            config.set("test_key", "test_value")
            config.save()

            # 重新加载
            config2 = Config(temp_path)
            assert config2.get("test_key") == "test_value"
        finally:
            os.remove(temp_path)

    def test_config_get_default_return(self):
        """测试 get 方法在 key 不存在时返回默认值"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{}')
            temp_path = f.name

        try:
            config = Config(temp_path)
            assert config.get("nonexistent_key") is None
            assert config.get("nonexistent_key", "fallback") == "fallback"
        finally:
            os.remove(temp_path)

    def test_config_as_dict(self):
        """测试 as_dict 返回完整配置字典"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{}')
            temp_path = f.name

        try:
            config = Config(temp_path)
            config.set("my_key", 42)
            d = config.as_dict()
            assert isinstance(d, dict)
            assert d["my_key"] == 42
            # 修改副本不应影响原配置
            d["my_key"] = 999
            assert config.get("my_key") == 42
        finally:
            os.remove(temp_path)

    def test_config_attr_access(self):
        """测试属性方式访问配置"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{}')
            temp_path = f.name

        try:
            config = Config(temp_path)
            assert config.recording_mode == "dual"
            with pytest.raises(AttributeError):
                _ = config.nonexistent_attribute
        finally:
            os.remove(temp_path)

    def test_config_persistence_integrity(self):
        """测试配置保存后数据完整性"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{}')
            temp_path = f.name

        try:
            config = Config(temp_path)
            config.set("string_val", "hello")
            config.set("int_val", 123)
            config.set("bool_val", True)
            config.set("list_val", [1, 2, 3])
            config.save()

            config2 = Config(temp_path)
            assert config2.get("string_val") == "hello"
            assert config2.get("int_val") == 123
            assert config2.get("bool_val") is True
            assert config2.get("list_val") == [1, 2, 3]
        finally:
            os.remove(temp_path)
