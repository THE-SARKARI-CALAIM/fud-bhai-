FROM python:3.12-slim

# JDK + tools + Kali repo for metasploit
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jdk-headless \
    wget \
    unzip \
    gnupg2 \
    curl \
    && curl -fsSL https://archive.kali.org/archive-key.asc | gpg --dearmor -o /usr/share/keyrings/kali-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/kali-archive-keyring.gpg] http://http.kali.org/kali kali-rolling main non-free non-free-firmware contrib" > /etc/apt/sources.list.d/kali.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends metasploit-framework \
    && rm -rf /var/lib/apt/lists/*

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
