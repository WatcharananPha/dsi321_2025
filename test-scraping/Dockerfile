FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates procps \
    libxss1 libasound2 libnspr4 libnss3 xdg-utils \
    fonts-liberation unzip libglib2.0-0 && \
    mkdir -p /etc/apt/keyrings && \
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google.gpg && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends google-chrome-stable && \
    wget -q "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/124.0.6367.207/linux64/chromedriver-linux64.zip" -O chromedriver_linux64.zip && \
    unzip chromedriver_linux64.zip -d /tmp/chromedriver_temp && \
    mv /tmp/chromedriver_temp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    rm chromedriver_linux64.zip && \
    rm -rf /tmp/chromedriver_temp && \
    apt-get purge -y --auto-remove wget unzip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV CHROMEDRIVER_PATH=/usr/local/bin/chromedriver

RUN useradd -m -u 1000 prefect_user
USER prefect_user
WORKDIR /home/prefect_user/app

COPY --chown=prefect_user:prefect_user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt && \
    pip install --no-cache-dir --user "prefect==3.4.1" selenium webdriver-manager lakefs-client pyarrow

ENV PATH="/home/prefect_user/.local/bin:${PATH}"

COPY --chown=prefect_user:prefect_user . .

RUN echo '#!/bin/bash\n\
prefect config set PREFECT_API_URL="$PREFECT_API_URL"\n\
cd /home/prefect_user/app\n\
prefect deploy --all\n\
exec "$@"' > /home/prefect_user/deploy.sh && \
    chmod +x /home/prefect_user/deploy.sh