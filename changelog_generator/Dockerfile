ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-pip git bash

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY app/ ./app/
COPY run.sh /
COPY default_system_prompt.md /app/

RUN chmod a+x /run.sh

CMD ["/run.sh"]
