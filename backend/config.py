"""
配置管理模块
从 .env 文件加载配置，提供全局 config 对象
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（如果不存在则使用环境变量或默认值）
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """全局配置"""

    # ---- LLM API ----
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o")

    # ---- 服务器 ----
    HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("SERVER_PORT", "8080"))
    # 对外可访问的基础 URL（二维码菜谱页地址前缀）
    SERVER_URL: str = os.getenv("SERVER_URL", f"http://localhost:{PORT}")

    # ---- 路径 ----
    DATA_DIR: Path = BASE_DIR / os.getenv("DATA_DIR", "data")
    RECIPES_DIR: Path = BASE_DIR / os.getenv("RECIPES_DIR", "recipes")
    MEMORY_DB: Path = BASE_DIR / os.getenv("MEMORY_DB", "memory/memory.db")
    FRONTEND_DIR: Path = BASE_DIR / "frontend"

    # ---- Memory ----
    MEMORY_TOP_K: int = 5  # 检索历史样例数量

    @property
    def mock_mode(self) -> bool:
        """是否为 Mock 模式（未配置 API Key 时自动启用）"""
        return not self.LLM_API_KEY

    def ensure_dirs(self):
        """确保所需目录存在"""
        self.RECIPES_DIR.mkdir(parents=True, exist_ok=True)
        self.MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)


config = Config()
