FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SERVER_HOST=0.0.0.0

WORKDIR /app

RUN addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app app

# 先复制依赖文件，利用 Docker 缓存
COPY requirements.txt .
RUN pip install -r requirements.txt -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple

# 复制项目文件
COPY --chown=app:app backend/ ./backend/
COPY --chown=app:app frontend/ ./frontend/
COPY --chown=app:app data/ ./data/
COPY --chown=app:app assets/ ./assets/
COPY --chown=app:app run.py ./
COPY --chown=app:app view_memory.py ./

# 创建可挂载、可持久化的运行时目录
RUN mkdir -p recipes memory && chown -R app:app /app

USER app

#环境变量
ENV LLM_API_KEY=''
# API Base URL（OpenAI: https://api.openai.com/v1  智谱GLM: https://open.bigmodel.cn/api/paas/v4 ）
ENV LLM_BASE_URL=''
# 模型名称（gpt-4o / glm-4-plus / glm-4-flash 等）
ENV LLM_MODEL=''

# ===== 服务器配置 =====
ENV SERVER_HOST=''
ENV SERVER_PORT=''
# 对外可访问的基础URL（用于生成二维码指向的菜谱页地址；部署到云端时改为实际域名）
ENV SERVER_URL=''

# ===== 数据与存储路径 =====
ENV DATA_DIR=''
ENV RECIPES_DIR=''
ENV MEMORY_DB=''

# ==图像生成=====
ENV IMAGE_GENERATION_ENABLED=''
# false 时完整方案不会自动生成图片，只能通过单菜按钮手动触发。
ENV IMAGE_AUTO_GENERATION_ENABLED=''
# true 时任一菜谱图片失败会终止方案保存；默认 false，失败时回退到原有图文菜谱。
ENV IMAGE_GENERATION_REQUIRED=''
ENV IMAGE_API_BASE_URL=''
# 留空时复用 LLM_API_KEY；如图片服务使用独立令牌则单独填写。
ENV IMAGE_API_KEY=''
ENV IMAGE_MODEL=''
# 部分兼容网关不读取 multipart 中的 model；路由错误时自动追加 ?model=...
ENV IMAGE_MODEL_QUERY_FALLBACK=''
ENV IMAGE_REFERENCE_PATH='assets/recipe-card-reference.png'
ENV IMAGE_SIZE=''
ENV IMAGE_QUALITY=''
ENV IMAGE_TIMEOUT_SECONDS=''
ENV IMAGE_MAX_CONCURRENCY=''
ENV IMAGE_MAX_RESPONSE_BYTES=''

# 暴露端口（Railway 会通过 PORT 环境变量指定实际端口）
EXPOSE 8000

VOLUME ["/app/data", "/app/memory", "/app/recipes"]

# 启动命令
CMD ["python", "run.py"]
