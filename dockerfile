FROM python:3.14-slim

# System deps + Java + Metasploit (msfvenom)
RUN apt-get update && apt-get install -y \
    openjdk-17-jdk \
    wget \
    unzip \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Metasploit (includes msfvenom)
RUN wget https://github.com/rapid7/metasploit-framework/releases/download/6.4.18/metasploit-framework_6.4.18_linux_amd64.deb && \
    dpkg -i metasploit-framework_6.4.18_linux_amd64.deb || true && \
    apt-get install -f -y && \
    rm metasploit-framework_6.4.18_linux_amd64.deb

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bot code
COPY . /app
WORKDIR /app

EXPOSE 8080

CMD ["python", "devil_bot.py"]