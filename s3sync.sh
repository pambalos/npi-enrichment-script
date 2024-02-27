/bin/bash

pip install awscli

TODAY=$(date +'%d-%m-%Y')

aws s3 --no-sign-request cp s3://reach-interview-data/npi_list.txt "${TODAY}"-npi_list.txt
