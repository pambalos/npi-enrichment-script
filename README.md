# NPI Data Enrichment Script for ReachRx Interview
(Bradley Justice)
## Overview
This is a simple couple of scripts that download NPI numbers from the S3 item given, then iterates over them and enriches them with data from the second API resource given (AWS API Gateway?), then saves the data into 51 possible files for any given day.

## Installation
1. Install the python packages: `$ pipenv install -r requirements.txt`

## Usage
There are two scripts in this repo, one is the `s3sync.sh` script which simply uses the aws cli to download the files from the s3 bucket, and the main python `app.py` script which does everything. 

I mainly included the `s3sync.sh` script just because that's how I originally checked if the file was available, and thats how I would have checked on a cloud environment.
 
1. The `app.py` file is the main script, and should be run with the following command (from the `/src` directory):
```bash
python3 app.py
```

## Notes

### Assumptions
- I assume that the npi_list will always have a header that I need to skip, will be a `\n` delimited file, and not a dictionary.
- I assume that the only possible 200 response from the second API resource is the one that contains the data I need, and that the data is always in the same format.
- I assume that we are actually interested in `'active':false` NPI records, as well as records without any practice listings, assigned to a 51st 'None' state file.
- I assume that we want to fail with an Exception if we fail to fetch the NPI list from s3.


### Design Decisions

- I decided to flatten the data structure of the second API resource from a multi level JSON to a flat csv format, for a couple of reasons. 
  - Firstly, I decided it would be easier to work with in the future, without the need for additional computation. 
  - Secondly, after considering saving the data as a JSON Object I came up with two issues;
    - The first was that simply adding a json object to each new line of the file would not be a valid JSON file, 
    - The second was that I would have to read the entire file into memory to append the new JSON object to the end of the file, or construct the file manually which I don't like.
- I also considered using the pandas library to handle the data, but I decided against it because I was only fetching the data from the API and saving it to a file. Although I did need to do some data manipulation, I decided a simple recursive function to flatten the json data structures was sufficient.
- I decided to use a ThreadPoolExecutor to handle the API requests, because I was making a lot of requests, and after my initial test took >10 minutes to run, I wanted to make them concurrently. 
- I decided to just add CONFIG_VARIABLES at the top of the file, because I didn't want to add a whole new library just to handle a couple of variables.
- I also was considering what database I would use to save this data more long-term, and the format for it. 
  - If I wanted a live and updated resource that I could use internally to quickly fetch information on NPI numbers, and I know I will mainly be accessing it via the NPI number, I would probably opt for a NoSQL database like MongoDB.
  - Alternatively, if I planned on building a larger set of records, one which might rope in further separate but relational data sources, and I can envision building APIs with index based queries, I would probably opt for a SQL database.
- I decided to manually build in the create directory step just for ease of use.
- Too much concurrency while writing could definitely slow things down as threads have to wait and compete for locks. I wanted to test my initial thoughts that async fetches, then synchronous writes could be faster than asynchronous fetches and writes. The results are as follows;
  - Initial test with `THREADS=20, MAX_RETRIES=10, MAX_WAIT=15, WAIT=3, ASYNC_WRITES=True` took 61 seconds to run, the second took 50 seconds
  - Initial test with `THREADS=20, MAX_RETRIES=10, MAX_WAIT=15, WAIT=3, ASYNC_WRITES=False` took 59 seconds to run, the second took 70 seconds
  - Another test with `THREADS=200, MAX_RETRIES=10, MAX_WAIT=15, WAIT=3, ASYNC_WRITES=True` took 28 seconds to run
  - - Another test with `THREADS=200, MAX_RETRIES=10, MAX_WAIT=15, WAIT=3, ASYNC_WRITES=False` took 43 seconds to run
  - Clearly I was wrong about my initial predictions regarding being able to perceive the trade-off. More in #Lessons Learnt

### Improvements
- Tests could be good. Although by its nature of being a script, it's pretty easy to test manually.
- If I wanted to invest more time, I would add some overarching daily handler. Either set it up as a timed function in a constantly running app that runs once a day, or set it up as a cron job, both of which have their advantages depending on the use case.
- There are some extraneous libraries in the requirements.txt file from my dev environment, I would remove them if I was going to use this in a production environment.
- Depending on how much load the second API can handle, I might want to increase or decrease the number of worker threads.
- For example, I ran it again today to see how it performed, and it took 3 minutes to run, a drastic improvement, but it also completely failed to fetch one of the npi numbers data. As such, perhaps I lower the max wait time but increase the number of retries on the request setup.
  - The setup with a single failure included `MAX_RETRIES = 5, MAX_WAIT = 60, WAIT = 3, THREADS = 20` 
  - Today I changed it to `MAX_RETRIES = 10, MAX_WAIT = 30, WAIT = 3, THREADS = 20` and managed to get all the data in a minute.
- Another improvement I would make is to make it adaptable for re-runs for failed npi_numbers, as well as build in a mechanism to double-check if all the NPI numbers have been properly fetched. Generally I would want to make it bit more configurable on a number of points
  - The first is an added option via script arguments to re-run the script on the list of failed npi_numbers the main script generates
  - The second is to add a run option which checks if all the npi_numbers have been fetched properly for the day, then fetch any missing ones (maybe from script failures caused by machine outages or anything else)
  - A third is to add the option to input any of the CONFIG_VARIABLES at run time, to offer greater flexibility and ease of use when running the script remotely from some management system.
- Another improvement that could be made is to add a locking mechanism to handle the writing of the files, for asynchronously managed writes (I may actually do this anyway just for fun...)

## Lessons Learnt
- My initial prediction that I would be able to see the performance trade-off with async writes turned out to be wrong. I think there are a numer of reasons for this; 
  - I think that the thread-to-file ratio isn't high enough to see a significant difference in performance. If there were more threads and fewer files, I think we would see a bit of a difference.
- Initially I ran into some trouble with the mutex Locks, but that was because I had accidentally imported the multiprocessing library instead of the threading library, so I know I need to be careful with that in the future.
- Greater concurrency seems to be the way to go, and definitely has all the advantages in regard to performance, but when implemented, it should to be done carefully and thoughtfully, and ideally, with a ton of performance testing!
