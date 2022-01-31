FROM renciorg/renci-python-image:v0.0.1

WORKDIR /home/plater
RUN git clone https://github.com/TranslatorSRI/Plater.git
WORKDIR /home/plater/Plater
ENV PYTHONPATH=/home/plater/Plater
COPY ./requirements.txt PLATER/requirements.txt
RUN pip install --upgrade pip
RUN pip install -r PLATER/requirements.txt
EXPOSE 8080
RUN mkdir -p PLATER/logs
RUN chown nru:nru PLATER/logs
USER nru
ENTRYPOINT ["./main.sh"]
