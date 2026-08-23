FROM python:3.14-slim

# System deps + Java (openjdk-21) + tools
RUN apt-get update && apt-get install -y \
    openjdk-21-jdk \
    wget \
    unzip \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Metasploit Framework (includes msfvenom)
# Using the official deb package from Rapid7
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

# Run bot with increased timeouts (we'll handle in code)
CMD ["python", "bot.py"]
