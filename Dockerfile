FROM python:3.9-slim AS BASE

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

FROM scratch
COPY --from=BASE / /

LABEL maintainer="GioF71"
LABEL source="https://github.com/GioF71/upnp-scrobbler"

ENV DEVICE_URL ""
ENV LAST_FM_API_KEY ""
ENV LAST_FM_SHARED_SECRET ""
ENV LAST_FM_USERNAME ""
ENV LAST_FM_PASSWORD_HASH ""
ENV LAST_FM_PASSWORD ""

ENV DURATION_THRESHOLD ""

ENV PYTHONUNBUFFERED=1

RUN mkdir /code
COPY upnp_scrobbler/*.py /code/

VOLUME /config

WORKDIR /code

ENTRYPOINT [ "python3", "scrobbler.py" ]
