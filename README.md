# NPI Data Enrichment Script for ReachRx Interview
(Bradley Justice)
## Overview
This is a simple couple of scripts that download NPI numbers from the S3 item given, iterate over them, and enrich them with data from the second API resource given (AWS API Gateway?), then save the data into 51 possible files for any given day.

## Installation
1. Install the python packages: `$ pipenv install -r requirements.txt`

## Usage
There are two scripts in this repo, one is the `s3sync.sh` script which simply uses the aws cli to download the files from the s3 bucket, and the main python `app.py` script which does everything. 

I mainly included the `s3sync.sh` script just because that's how I originally checked if the file was available, and that's how I would have checked on a cloud environment.
 
1. The `app.py` file is the main script, and should be run with the following command (from the `/src` directory):
```bash
python3 app.py
```

## Configuration
The `app.py` script can be configured by modifying the following variables at the top of the script:
- ```CURRENT_DATE_KEY```: The key to use for the current date post-fix for the file names
- ```NPI_FILE```: The file name of the NPI list to download from S3
- ```FAILED_NPI_FILE```: The file name to record failed NPI numbers
- ```BASE_FILE_PATH```: The base file path to save the files to (setup to run from the `/src` directory)
- ```NPI_DATA_DIRECTORY```: The directory to save the NPI data to
- ```NPI_DATA_FILE_PREFIX```: The prefix to use for the NPI data files
- ```BUCKET_NAME```: The name of the S3 bucket to download the NPI list from
- ```CMS_API_URL```: The URL of the CMS API to fetch the NPI data from
- ```MAX_RETRIES```: The number of times to retry a failed request
- ```MAX_WAIT```: The maximum time to wait between retries (exponential backoff)
- ```WAIT```: The default time to wait between requests
- ```THREADS```: The number of threads to use for concurrent requests
- ```ASYNC_WRITES```: Whether to use asynchronous writes or not
- ```LOOP_TILL_DONE```: Whether to loop till all NPI numbers are fetched or not
- ```PRE_REQUEST_SLEEP_RANGE```: The range of time to sleep before making a request, used to help avoid rate limiting/overloading the API

## Script Output
The script will write the results to csv files in the npi_data directory, one for each state, plus None and Failed. This can be configured using the above configuration variables.


## Notes

### Assumptions
- I assume that the npi_list will always have a header that I need to skip, will be a `\n` delimited file, and not a dictionary.
- I assume that the only possible 200 response from the second API resource is the one that contains the data I need and that the data is always in the same format.
- I assume that we are interested in `'active':false` NPI records, as well as records without any practice listings, assigned to a 51st 'None' state file.
- I assume that we want to fail with an Exception if we fail to fetch the NPI list from s3.


### Design Decisions

- I decided to flatten the data structure of the second API resource from a multi-level JSON to a flat CSV format, for a couple of reasons. 
  - Firstly, I decided it would be easier to work with in the future, without the need for additional computation. 
  - Secondly, after considering saving the data as a JSON Object I came up with two issues;
    - The first was that simply adding a JSON object to each new line of the file would not be a valid JSON file, 
    - The second was that I would have to read the entire file into memory to append the new JSON object to the end of the file or construct the file manually which I don't like.
    - If I were using a mongoDB, I would probably just save each item as a separate document, but I decided to go with a CSV file for simplicity in this case.
- I also considered using the Pandas library to handle the data, but I decided against it because I was only fetching the data from the API and saving it to a file. Although I did need to do some data manipulation, I decided a simple recursive function to flatten the JSON data structures was sufficient.
- I decided to use a ThreadPoolExecutor to handle the API requests because I was making a lot of requests, and after my initial test took >10 minutes to run, I wanted to make them concurrently. 
- I decided to just add CONFIG_VARIABLES at the top of the file because I didn't want to add a whole new library just to handle a couple of variables.
- I also was considering what database I would use to save this data more long-term, and the format for it. 
  - If I wanted a live and updated resource that I could use internally to quickly fetch information on NPI numbers, and I know I will mainly be accessing it via the NPI number, I would probably opt for a NoSQL database like MongoDB.
  - Alternatively, if I planned on building a larger set of records, one which might rope in further separate but relational data sources, and I can envision building APIs with index based queries, I would probably opt for a SQL database.
- I decided to manually build in the create directory step just for ease of use.
- Too much concurrency while writing could slow things down as threads have to wait and compete for locks. I wanted to test my initial thoughts that async fetches, and then synchronous writes could be faster than asynchronous fetches and writes. The results are as follows;
  - Initial test with `THREADS=20, MAX_RETRIES=10, MAX_WAIT=15, WAIT=3, ASYNC_WRITES=True` took 61 seconds to run, the second took 50 seconds
  - Initial test with `THREADS=20, MAX_RETRIES=10, MAX_WAIT=15, WAIT=3, ASYNC_WRITES=False` took 59 seconds to run, the second took 70 seconds
  - Another test with `THREADS=200, MAX_RETRIES=10, MAX_WAIT=15, WAIT=3, ASYNC_WRITES=True` took 28 seconds to run
  - Another test with `THREADS=200, MAX_RETRIES=10, MAX_WAIT=15, WAIT=3, ASYNC_WRITES=False` took 43 seconds to run
  - Clearly, I was wrong about my initial predictions regarding being able to perceive the trade-off. More in #Lessons Learnt

### Improvements
- Tests could be good. Although by its nature of being a script, it's pretty easy to test manually.
- If I wanted to invest more time, I would add some overarching daily handler. Either set it up as a timed function in a constantly running app that runs once a day, or set it up as a cron job, both of which have their advantages depending on the use case.
- There are some extraneous libraries in the requirements.txt file from my dev environment, I would remove them if I was going to use this in a production environment.
- Depending on how much load the second API can handle, I might want to increase or decrease the number of worker threads.
- For example, I ran it again today to see how it performed, and it took 3 minutes to run, a drastic improvement, but it also completely failed to fetch one of the npi numbers data. As such, perhaps I lower the max wait time but increase the number of retries on the request setup.
  - The setup with a single failure included `MAX_RETRIES = 5, MAX_WAIT = 60, WAIT = 3, THREADS = 20` 
  - Today I changed it to `MAX_RETRIES = 10, MAX_WAIT = 30, WAIT = 3, THREADS = 20` and managed to get all the data in a minute.
- Another improvement I would make is to make it adaptable for re-runs for failed npi_numbers, as well as build in a mechanism to double-check if all the NPI numbers have been properly fetched. Generally, I would want to make it a bit more configurable on several points
  - The first is an added option via script arguments to re-run the script on the list of failed npi_numbers the main script generates
  - The second is to add a run option that checks if all the npi_numbers have been fetched properly for the day, then fetches any missing ones (maybe from script failures caused by machine outages or anything else)
  - A third is to add the option to input any of the CONFIG_VARIABLES at run time, to offer greater flexibility and ease of use when running the script remotely from some management system.
- Another improvement that could be made is to add a locking mechanism to handle the writing of the files, for asynchronously managed writes (I may do this anyway just for fun...) (Done!)
- I also wanted to mention how I can envision connecting this script to a Kafka cluster and setting it up as a producer to a topic so that other services in the ecosystem can subscribe to the topic and consume the data quite easily.
- I might also remove the individual npi completion logs so the logs take up less space on the machine.

## Lessons Learnt
- My initial prediction that I would be able to see the performance trade-off with async writes turned out to be wrong. I think there are several reasons for this; 
  - I think that the thread-to-file ratio isn't high enough to see a significant difference in performance. If there were more threads and fewer files, I think we would see a bit of a difference.
- Initially, I ran into some trouble with the mutex Locks, but that was because I had accidentally imported the multiprocessing library instead of the threading library, so I know I need to be careful with that in the future.
- Greater concurrency seems to be the way to go and has all the advantages with performance, but when implemented, it should be done carefully and thoughtfully, and ideally, with a ton of performance testing!


## Edits
### 2024-02-27
- Added a make directory call to the program and updated readme.

### 2024-02-28
- Added asynchronous file writing, along with Mutex to handle that.
- Added loop till done functionality.
- Added some run config.

### 2024-02-29
- Added some more run config.
- Added some notes on improvement and added Edits section to the README.md

