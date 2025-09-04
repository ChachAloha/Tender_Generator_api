# 1. 使用官方 Python 运行时作为父镜像
FROM python:3.12-slim

# 2. 设置容器中的工作目录
WORKDIR /app

# 3. 设置环境变量，防止 Python 写入 .pyc 文件
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 5. 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.ustc.edu.cn/pypi/simple

# 6. 复制项目代码到工作目录
COPY . .

# 7. 创建应用需要的目录
RUN mkdir -p uploads output

# 8. 暴露应用程序运行的端口
EXPOSE 8000

# 9. 定义运行应用程序的命令
# 使用 --host 0.0.0.0 使容器内的服务可以从外部访问
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 