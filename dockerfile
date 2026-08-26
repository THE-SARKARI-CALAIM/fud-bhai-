FROM python:3.12-slim

# JDK + basic tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jdk-headless \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Metasploit via official installer (lightweight)
RUN wget -q https://downloads.metasploit.com/data/releases/metasploit-latest-linux-x64-installer.run -O /tmp/msfinstall.run && \
    chmod +x /tmp/msfinstall.run && \
    echo "y" | /tmp/msfinstall.run --prefix /opt/metasploit --mode unattended 2>&1 || echo "metasploit install attempted" && \
    rm -f /tmp/msfinstall.run
ENV PATH="/opt/metasploit/bin:${PATH}"

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
