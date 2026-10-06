import os
import sys

# 让 pytest 在未安装包的情况下也能直接导入项目根目录下的 app 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
