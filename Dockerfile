FROM python:3.11-slim

WORKDIR /app

COPY main.py .

EXPOSE 9999/udp

CMD ["python", "main.py"]
