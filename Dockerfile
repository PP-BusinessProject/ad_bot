# set base image (host OS)
FROM python:3.11.2

# set the working directory in the container
WORKDIR /

# copy the dependencies file to the working directory
COPY requirements.txt .

# install dependencies
RUN pip install -r requirements.txt

# command to run on container start
CMD [ "python", "-m", "bin.main" ]