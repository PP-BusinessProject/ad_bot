# set base image (host OS)
FROM python:3.11.2

# set the working directory in the container
WORKDIR /app

# copy the dependencies file to the working directory
COPY requirements.txt .

#  copy the application files
COPY /bin /app
COPY /lib /app/lib

# install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# set environment variables
ENV PORT 8080

# expose the port
EXPOSE 8080

# command to run on container start
CMD [ "python", "-m", "main" ]