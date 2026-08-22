FROM python:3.14-slim

RUN apt-get update && apt-get install -y \
    default-jdk \
    wget \
    unzip \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# No msfvenom – FUD processing disabled, APK sirf store hoga

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
WORKDIR /app

EXPOSE 8080

CMD ["python", "app.py"]
