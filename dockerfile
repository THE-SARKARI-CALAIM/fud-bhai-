FROM python:3.14-slim

# System deps + Java + Ruby (for gem install)
RUN apt-get update && apt-get install -y \
    default-jdk \
    wget \
    unzip \
    git \
    curl \
    ruby \
    ruby-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install msfvenom using Ruby gem (lightweight, no apt repo issues)
RUN gem install msfvenom

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bot code
COPY . /app
WORKDIR /app

EXPOSE 8080

CMD ["python", "app.py"]