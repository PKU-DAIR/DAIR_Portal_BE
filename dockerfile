FROM python:3.10

WORKDIR /app
COPY . .
EXPOSE 8000
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
# WORKDIR /app/api/
ENTRYPOINT ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]