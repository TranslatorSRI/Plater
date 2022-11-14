FROM neo4j:4.4.10

ARG GDS_VERSION=2.1.9
ARG APOC_VERSION=4.4.0.8
ENV APOC_URI https://github.com/neo4j-contrib/neo4j-apoc-procedures/releases/download/${APOC_VERSION}/apoc-${APOC_VERSION}-all.jar
ENV GDS_URL https://graphdatascience.ninja/neo4j-graph-data-science-${GDS_VERSION}.zip

RUN apt-get update
RUN apt-get install unzip

RUN mkdir /plugins

WORKDIR /plugins

RUN wget $APOC_URI

RUN wget $GDS_URL

RUN unzip neo4j-graph-data-science-${GDS_VERSION}.zip

RUN rm neo4j-graph-data-science-${GDS_VERSION}.zip

WORKDIR /

EXPOSE 7474 7473 7687

CMD ["neo4j"]