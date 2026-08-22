FROM python:3.14-slim

# Install system deps + Java (default-jdk works on trixie)
RUN apt-get update && apt-get install -y \
    default-jdk \
    wget \
    unzip \
    git \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Metasploit Framework via direct .deb (latest stable)
RUN wget https://github.com/rapid7/metasploit-framework/releases/download/6.4.18/metasploit-framework_6.4.18_linux_amd64.deb && \
    dpkg -i metasploit-framework_6.4.18_linux_amd64.deb 2>/dev/null || true && \
    apt-get install -f -y && \
    rm metasploit-framework_6.4.18_linux_amd64.deb

# If direct .deb fails, fallback to gem install (lightweight)
RUN apt-get install -y ruby ruby-dev build-essential && \
    gem install msfvenom && \
    apt-get remove -y build-essential && apt-get autoremove -y

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bot code
COPY . /app
WORKDIR /app

EXPOSE 8080

CMD ["python", "app.py"]