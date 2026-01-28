FROM python:3.11-slim

WORKDIR /app

ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY *.py ./

RUN mkdir -p /app/data /app/logs

ENV PYTHONUNBUFFERED=1

VOLUME ["/app/data", "/app/logs"]

CMD ["python", "main.py", "--monitor"]
