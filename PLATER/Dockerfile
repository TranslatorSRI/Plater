FROM python:3.8.1-buster

ARG UID=1000
ARG GID=1000
RUN groupadd -o -g $GID plater
RUN useradd -m -u $UID -g $GID -s /bin/bash plater
WORKDIR /home/plater
RUN git clone https://github.com/TranslatorSRI/Plater.git
WORKDIR /home/plater/Plater
ENV PYTHONPATH=/home/plater/Plater

RUN pip install -r PLATER/requirements.txt
EXPOSE 8080
VOLUME logs
RUN mkdir -p PLATER/logs
RUN chown plater:plater PLATER/logs
USER plater
ENTRYPOINT ["./main.sh"]