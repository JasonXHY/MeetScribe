"""pytest 配置: sys.path 设置 & 自定义 marker 注册"""

import os
import sys

# 将 src 目录加入 sys.path，供所有测试使用
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def pytest_configure(config):
    config.addinivalue_line("markers", "gui: 标记需要图形界面环境的测试")
    config.addinivalue_line("markers", "timeout: 设置测试超时时间（秒）")
