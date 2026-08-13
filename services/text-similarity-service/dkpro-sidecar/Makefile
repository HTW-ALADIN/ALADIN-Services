.PHONY: prep build test lint start clean docker-build generate-openapi

SERVICE := text-similarity-dkpro-service
JAR := target/$(SERVICE)-0.1.0.jar
PORT ?= 8100

prep:
	mvn dependency:resolve

build:
	mvn package -DskipTests

test:
	mvn test

lint:
	@echo "Java lint: checkstyle not configured yet; skipping"

start:
	mvn spring-boot:run

clean:
	mvn clean
	rm -f $(SERVICE).openapi.json

docker-build:
	docker build -f Dockerfile -t $(SERVICE) .

generate-openapi:
	@echo "OpenAPI generation not yet implemented for Java service"