FROM python:3.14-slim

# System deps + Java 21
RUN apt-get update && apt-get install -y \
    openjdk-21-jdk \
    wget \
    curl \
    git \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Metasploit Framework (official installer)
# This script automatically adds repo and installs latest msfvenom
RUN curl https://raw.githubusercontent.com/rapid7/metasploit-omnibus/master/config/templates/metasploit-framework-wrappers/msfupdate.erb > msfinstall && \
    chmod 755 msfinstall && \
    ./msfinstall && \
    rm msfinstall

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bot code
COPY . /app
WORKDIR /app

EXPOSE 8080

CMD ["python", "bot.py"]
