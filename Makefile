TAG=docker-pihole-dns-shim:latest

build:
	docker build . -t ${TAG}

run:
	docker run -it \
	-v ${PWD}/shim.py:/app/shim.py \
	--env-file .env \
	${TAG} 