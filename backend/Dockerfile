# ===== 后端 Dockerfile（生产用 gunicorn） =====
FROM python:3.11-slim

# 设置时区（与 settings.TIME_ZONE 一致）
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 工作目录
WORKDIR /app

# 安装系统依赖（mysqlclient 需要）
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    pkg-config \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件，利用 Docker 缓存层
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 静态文件收集目录（entrypoint 会跑 collectstatic）
RUN mkdir -p /app/staticfiles /app/media

# 暴露端口
EXPOSE 8000

# 启动命令：用 entrypoint 跑 migrate + collectstatic + gunicorn
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
