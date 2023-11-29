import os
from os.path import join, dirname
from dotenv import load_dotenv

dotenv_path = join(dirname(__file__), 'key.env')
load_dotenv(dotenv_path)

AK = os.environ.get('api_key')
SK = os.environ.get('secret')
