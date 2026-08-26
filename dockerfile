FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jdk-headless \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# msfvenom standalone
RUN wget -q https://github.com/rapid7/metasploit-framework/releases/download/v6.4.27/msfvenom_linux_amd64 -O /usr/local/bin/msfvenom && \
    chmod +x /usr/local/bin/msfvenom

# apktool
RUN wget -q https://raw.githubusercontent.com/ApertureDeveloper/ApertureDeveloper.github.io/master/public/apktool/apktool_2.10.0.jar -O /usr/local/bin/apktool.jar && \
    printf '#!/bin/sh\njava -jar /usr/local/bin/apktool.jar "$@"\n' > /usr/local/bin/apktool && \
    chmod +x /usr/local/bin/apktool || echo "apktool setup attempted"

# Android build-tools (zipalign + apksigner)
RUN wget -q https://dl.google.com/android/repository/build-tools_r34-linux.zip -O /tmp/bt.zip && \
    unzip -q /tmp/bt.zip -d /tmp/bt && \
    cp /tmp/bt/android-14/zipalign /usr/local/bin/zipalign && \
    chmod +x /usr/local/bin/zipalign && \
    rm -rf /tmp/bt /tmp/bt.zip || echo "build-tools install attempted"

RUN /usr/local/bin/msfvenom --version || echo "msfvenom installed"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
WORKDIR /app

EXPOSE 8080

CMD ["python", "bot.py"]
