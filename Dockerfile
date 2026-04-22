FROM python:3.13-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -e ".[mysql]" gunicorn

RUN chmod +x entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]
