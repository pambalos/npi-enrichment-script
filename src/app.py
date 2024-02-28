import csv
import datetime
import math
import os.path
import time
import boto3
import requests
import concurrent.futures as cf
from botocore import UNSIGNED
from botocore.config import Config

# Configuration variables
CURRENT_DATE = datetime.date.today().strftime("%d-%m-%Y")
NPI_FILE = "npi_list.txt"
FAILED_NPI_FILE = "failed_npi_list.txt"
BASE_FILE_PATH = "../"
NPI_DATA_DIRECTORY = BASE_FILE_PATH + "npi-data/"
NPI_DATA_FILE_PREFIX = NPI_DATA_DIRECTORY + "npi_data_"
BUCKET_NAME = "reach-interview-data"
CMS_API_URL = "https://6irj0rgv1k.execute-api.us-east-2.amazonaws.com/test?npi="
MAX_RETRIES = 10
MAX_WAIT = 30
WAIT = 3
THREADS = 20


# method to get NPI numbers from file or S3 bucket, depending on if the bash script using awscli has already run or not
# also only take the numbers from [1:] to avoid the header
def get_npi_numbers(file_path=BASE_FILE_PATH + CURRENT_DATE + "-" + NPI_FILE):
    if not os.path.exists(file_path):
        print(f"File {file_path} does not exist. Getting NPI numbers from S3 bucket...")
        return get_npi_boto()
    else:
        with open(file_path, "r") as file:
            numbers = file.read().split()[1:]
            return numbers


# Method to get NPI numbers from S3 bucket using boto3
# also only take the numbers from [1:] to avoid the header
# also decided to save it to a file just to have a record of the NPI numbers from that date
def get_npi_boto():
    config = Config(signature_version=UNSIGNED)
    object_url = boto3.client('s3', config=config).generate_presigned_url('get_object',
                                                                          Params={'Bucket': BUCKET_NAME,
                                                                                  'Key': NPI_FILE})

    resp = requests.get(object_url)
    if resp.status_code == 200:
        content = resp.content.decode("utf-8").split()[1:]
        with open(BASE_FILE_PATH + CURRENT_DATE + "-" + NPI_FILE, "a") as file:
            file.write(resp.content.decode("utf-8"))
            file.close()
        return content
    else:
        Exception(f"Failed to get NPI data from {object_url}.")


# Exponential backoff method to retry the requests to the CMS API
def make_request(url, retries=MAX_RETRIES, wait=WAIT, max_wait=MAX_WAIT):
    for i in range(1, retries+1):
        resp = requests.get(url)
        if resp.status_code == 200:
            return resp
        else:
            sleep_time = min(math.pow(wait, i), max_wait)
            print(f"Failed to get data from {url} on attempt {i}. Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)
    return None


# Method to mark the NPI number failed if the request to the CMS API fails
def mark_failed_npi(npi):
    failed_path = BASE_FILE_PATH + CURRENT_DATE + "-" + FAILED_NPI_FILE
    with open(failed_path, "a") as file:
        file.write(npi + "\n")


# Overarching method to iterate through the NPI numbers and get the data from the CMS API
# Also calls the method to flatten and save the data to a CSV file
# Quick conversion of npi_numbers to a set so that we aren't making redundant requests
# Implemented a ThreadPoolExecutor to make the requests concurrently because it took so long the first time
def create_npi_data():
    current_date = datetime.date.today().strftime("%d-%m-%Y")
    start_time = time.time()
    create_npi_data_directory()
    npi_numbers = set(get_npi_numbers())
    print(f"# of NPI numbers: {str(len(npi_numbers))} for {current_date}")

    with cf.ThreadPoolExecutor(max_workers=THREADS) as thread_executor:
        futures = [thread_executor.submit(get_npi_data_from_npi_url, number) for number in npi_numbers]
        for future in cf.as_completed(futures):
            npi, data = future.result()
            if data is not None:
                if data['affiliatedPractices']['items'] is not None:
                    for practice in data['affiliatedPractices']['items']:
                        practice_state = practice['address']['state']
                        save_npi_data(current_date, practice_state, data)
                else:
                    save_npi_data(current_date, "None", data)
            else:
                mark_failed_npi(npi)

    end_time = time.time()
    print(f"Finished saving data for {current_date}")
    print(f"Time taken: {end_time - start_time} seconds")


# Method to create the directory to save the NPI data if it doesn't exist
def create_npi_data_directory():
    if not os.path.exists(NPI_DATA_DIRECTORY):
        os.makedirs(NPI_DATA_DIRECTORY)

# Method to get the data from the CMS API using the NPI number and return the response or None if the request fails
# Also returns the NPI number so that we can mark it as failed if the request fails
def get_npi_data_from_npi_url(npi):
    url = f"{CMS_API_URL}{npi}"
    resp = make_request(url)
    if resp is None:
        return npi, None
    return npi, resp.json()


# Method to save the data to a CSV file - checks if the file exists and if not, creates it and writes the header
def save_npi_data(current_date, state, data):
    prepped_data = prep_for_csv(data)
    this_file = f"{NPI_DATA_FILE_PREFIX}{current_date}_{state}.csv"
    if not os.path.exists(this_file):
        with open(this_file, "a+") as new_file:
            csv_writer = csv.writer(new_file, delimiter=",", lineterminator="\n")
            csv_writer.writerow(prepped_data.keys())
            csv_writer.writerow(prepped_data.values())
    else:
        with open(this_file, "a+") as file:
            csv_writer = csv.writer(file, delimiter=",", lineterminator="\n")
            csv_writer.writerow(prepped_data.values())


# Method to flatten the data from the CMS API so that it can be written to a CSV file
def prep_for_csv(data):
    flat_dict = {}
    for key, value in data.items():
        r_prep(key, value, flat_dict)
    return flat_dict


# Recursive helper method to flatten the data from the CMS API so that it can be written to a CSV file
def r_prep(key, value, flat_dict):
    if not isinstance(value, dict) and not isinstance(value, list):
        flat_dict.update({key: value})
    else:
        if isinstance(value, list):
            for i in range(len(value)):
                r_prep(key + "[" + str(i) + "]", value[i], flat_dict)
        else:
            for k, v in value.items():
                r_prep(key + "." + k, v, flat_dict)


# main method to run the script
create_npi_data()
