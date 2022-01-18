FROM neo4j:4.2.14

ENV APOC_URI https://github.com/neo4j-contrib/neo4j-apoc-procedures/releases/download/4.2.0.1/apoc-4.2.0.1-all.jar
ENV GDS_URL https://s3-eu-west-1.amazonaws.com/com.neo4j.graphalgorithms.dist/graph-data-science/neo4j-graph-data-science-1.1.5-standalone.zip

RUN apt-get update
RUN apt-get install unzip

RUN mkdir /plugins

WORKDIR /plugins

RUN wget $APOC_URI

RUN wget $GDS_URL

RUN unzip neo4j-graph-data-science-1.1.5-standalone.zip

RUN rm neo4j-graph-data-science-1.1.5-standalone.zip

WORKDIR /

EXPOSE 7474 7473 7687

CMD ["neo4j"]