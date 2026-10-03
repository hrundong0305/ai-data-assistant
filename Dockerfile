# 电商经营AI问答助手 - 魔搭/通用云平台 Docker 镜像
FROM python:3.11-slim

WORKDIR /app

# 先装依赖（利用缓存层）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝项目文件
COPY . .

# 数据文件路径（容器内相对路径）
ENV DATA_PATH=data/ecommerce_sales.csv

# 云平台会注入 PORT 环境变量；本地默认 8000
EXPOSE 8000

CMD ["python", "app.py"]
