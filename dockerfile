FROM python:3.12-slim

# JDK + tools (default-jdk picks whatever is available)
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jdk-headless \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# msfvenom standalone
RUN wget -q https://github.com/rapid7/metasploit-framework/releases/download/v6.4.27/msfvenom_linux_amd64 -O /usr/local/bin/msfvenom && \
    chmod +x /usr/local/bin/msfvenom || echo "msfvenom download attempted"

# apktool
RUN wget -q https://github.com/iBotPeaches/Apktool/releases/download/v2.10.0/apktool_2.10.0.jar -O /usr/local/bin/apktool.jar && \
    printf '#!/bin/sh\njava -jar /usr/local/bin/apktool.jar "$@"\n' > /usr/local/bin/apktool && \
    chmod +x /usr/local/bin/apktool || echo "apktool setup attempted"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
WORKDIR /app

EXPOSE 8080

CMD ["python", "bot.py"]
