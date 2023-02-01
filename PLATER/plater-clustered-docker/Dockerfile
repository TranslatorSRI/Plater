FROM ghcr.io/translatorsri/plater:latest

USER root
ENV MODE="deploy"
RUN pip install gunicorn
COPY ./main.sh /home/plater/Plater/
RUN chmod 777 /home/plater/Plater/main.sh
COPY ./heartbeat.py /home/plater/Plater/PLATER/services/
USER nru








