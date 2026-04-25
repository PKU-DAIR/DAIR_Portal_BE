FROM python:3.12

WORKDIR /app
COPY . .
EXPOSE 8000
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
RUN python -m playwright install --with-deps chromium
ENTRYPOINT ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
