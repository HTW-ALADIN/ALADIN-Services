.PHONY: build run clean

build:
	docker build -t noise-generation-service .

run:
	docker run -p 3000:3000 noise-generation-service

clean:
	docker rmi noise-generation-service
