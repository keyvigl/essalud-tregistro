FROM python:3.11-slim

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY startup.sh .
RUN chmod +x startup.sh

EXPOSE 8000

CMD ["./startup.sh"]
