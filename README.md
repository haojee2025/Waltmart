# Waltmart

## Description

This is the server for the Waltmart project.

## Cloning the repository

To clone the repository, run the following command:

```
git clone https://github.com/haojee2025/Waltmart.git
cd Waltmart
```

## Creating a virtual environment

To create a virtual environment, run the following command:

```
python -m venv venv

# (For Windows)
venv\Scripts\activate

# For Linux
source venv/bin/activate
```

## Installing the dependencies

To install the dependencies, run the following command:

```
pip install -r requirements.txt
```

> [!IMPORTANT]
> Update `.env` file configuration for PostgreSQL database if necessary.
> Update `init_db.py` IP address, account, and password for the sample work centres if necessary.

## Initializing the database

To initialize the database, run the following command:

```
python database/init_db.py
```

The ```init_db.py``` script will create the necessary tables and sample data for the project.

## Running the server

To run the server, run the following command:

```
python app.py