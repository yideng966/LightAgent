#!/bin/bash

unset KUBECONFIG

cd .. && docker build -f docker/Dockerfile.latest \
             -t yideng966/lightagent .

docker tag yideng966/lightagent yideng966/lightagent:$(date +%y%m%d)