"""
配置管理模块
从 .env 文件加载配置，提供全局 config 对象
"""
import math
import os
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

# 加载 .env 文件（如果不存在则使用环境变量或默认值）
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_choice(name: str, default: str, allowed: set[str]) -> str:
    value = os.getenv(name, default).strip().lower()
    if value not in allowed:
        raise ValueError(
            f"{name} must be one of: {', '.join(sorted(allowed))}"
        )
    return value


def _env_positive_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _env_temperature(name: str, default: float) -> float:
    value = float(os.getenv(name, str(default)))
    if not math.isfinite(value) or not 0 <= value <= 2:
        raise ValueError(f"{name} must be a finite number between 0 and 2")
    return value


class Config:
    """全局配置"""

    # ---- LLM API ----
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o")
    LLM_PROVIDER: str = _env_choice(
        "LLM_PROVIDER",
        "auto",
        {"auto", "openai", "zhipu", "opencode", "generic", "legacy"},
    )
    LLM_MAX_TOKENS: int = _env_positive_int("LLM_MAX_TOKENS", 8192)
    LLM_TEMPERATURE: float = _env_temperature("LLM_TEMPERATURE", 0.7)
    LLM_REASONING_EFFORT: str = _env_choice(
        "LLM_REASONING_EFFORT",
        "max",
        {"max", "xhigh", "high", "medium", "low", "minimal", "none"},
    )

    # ---- MCP 经营数据 Agent ----
    MCP_ENABLED: bool = _env_bool("MCP_ENABLED", False)
    MCP_SERVER_URL: str = os.getenv(
        "MCP_SERVER_URL", "http://127.0.0.1:8765/mcp"
    )
    MCP_AUTH_TOKEN: str = os.getenv("MCP_AUTH_TOKEN", "")
    MCP_REQUIRED: bool = _env_bool("MCP_REQUIRED", True)
    MCP_TIMEOUT_SECONDS: float = float(os.getenv("MCP_TIMEOUT_SECONDS", "10"))
    MCP_MAX_RESPONSE_BYTES: int = int(
        os.getenv("MCP_MAX_RESPONSE_BYTES", "1000000")
    )
    AGENT_SALES_WINDOW_DAYS: int = int(
        os.getenv("AGENT_SALES_WINDOW_DAYS", "28")
    )
    AGENT_MAX_PRODUCTS: int = int(os.getenv("AGENT_MAX_PRODUCTS", "100"))

    # ---- 服务器 ----
    HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    # Railway 提供 PORT 环境变量，优先读取；其次读 SERVER_PORT
    PORT: int = int(os.getenv("PORT", os.getenv("SERVER_PORT", "8000")))
    # 对外可访问的基础 URL（二维码菜谱页地址前缀）
    SERVER_URL: str = os.getenv("SERVER_URL", f"http://localhost:{PORT}")

    # ---- 路径 ----
    DATA_DIR: Path = BASE_DIR / os.getenv("DATA_DIR", "data")
    RECIPES_DIR: Path = BASE_DIR / os.getenv("RECIPES_DIR", "recipes")
    MEMORY_DB: Path = BASE_DIR / os.getenv("MEMORY_DB", "memory/memory.db")
    FRONTEND_DIR: Path = BASE_DIR / "frontend"

    # ---- Memory ----
    MEMORY_TOP_K: int = 5  # 检索历史样例数量

    def __init__(self) -> None:
        if self.resolved_llm_provider == "zhipu" and self.LLM_TEMPERATURE > 1:
            raise ValueError("LLM_TEMPERATURE must be between 0 and 1 for Zhipu")

    @property
    def mock_mode(self) -> bool:
        """是否为 Mock 模式（未配置 API Key 时自动启用）"""
        return not self.LLM_API_KEY

    @property
    def resolved_llm_provider(self) -> str:
        """Resolve vendor request semantics without guessing from model alone."""
        if self.LLM_PROVIDER != "auto":
            return self.LLM_PROVIDER
        hostname = (urlparse(self.LLM_BASE_URL).hostname or "").lower()
        model = self.LLM_MODEL.strip().lower()
        if hostname in {"open.bigmodel.cn", "api.z.ai"} and model.startswith("glm-"):
            return "zhipu"
        if hostname == "opencode.ai" or hostname.endswith(".opencode.ai"):
            return "opencode"
        if hostname == "api.openai.com":
            return "openai"
        return "generic"

    def ensure_dirs(self):
        """确保所需目录存在"""
        self.RECIPES_DIR.mkdir(parents=True, exist_ok=True)
        self.MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)


config = Config()
