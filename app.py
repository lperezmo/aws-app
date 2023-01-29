import streamlit as st
import pandas as pd
import s3fs
import os
import logging
import boto3
from botocore.exceptions import ClientError
import openai
import sqlite3
import numpy as np
from PIL import Image
import requests
from io import BytesIO
import io
import urllib.request
from PIL import Image
from deta import Deta
###########################################################################################################
# Set page configuration
st.set_page_config(page_title='Image Generator & Gallery', 
                    page_icon=':bar_chart:', 
                    layout='wide', 
                    initial_sidebar_state='auto')
hide_streamlit_style = """
			<style>
			footer {visibility: hidden;}
			</style>
			"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True) 
###########################################################################################################
# Create connection object.
# `anon=False` means not anonymous, i.e. it uses access keys to pull data.
fs = s3fs.S3FileSystem(anon=False)
###########################################################################################################
# Database
if "deta" not in st.session_state:
	st.session_state.deta = Deta(st.secrets["DETA_KEY"])
if "db" not in st.session_state:
	st.session_state.db = st.session_state.deta.Base("aws-app")
###########################################################################################################
# Retrieve file contents.
# Uses st.experimental_memo to only rerun when the query changes or after 10 min.
@st.experimental_memo(ttl=600)
def read_file(filename):
    with fs.open(filename) as f:
        return f.read().decode("utf-8")

def upload_file(file_name, bucket, object_name=None):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = os.path.basename(file_name)

    # Upload the file
    s3_client = boto3.client('s3')
    try:
        response = s3_client.upload_file(file_name, bucket, object_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True

def create_and_save_image(given_prompt):
    response = openai.Image.create(
      prompt=given_prompt,
      n=1,
      size="1024x1024"
    )
    image_url = response['data'][0]['url']
    unique_id = response['created']

    # Get current date from pandas
    now = pd.Timestamp('now')
    date_string = now.strftime('%Y-%m-%d')

    # Open the image from the URL
    with urllib.request.urlopen(image_url) as url:
        s = url.read()

    # Save the image to a file with a given string, current date and time
    file_name = f"output/{unique_id}_{date_string}.jpg"
    
    s3 = boto3.client('s3')
    with open(file_name, "rb") as f:
        s3.upload_fileobj(s, "aws-app")
    
    # Add entry to database
    st.session_state.db.put({'id': unique_id, 
                            'date': date_string, 
                            'prompt': given_prompt, 
                            'image': file_name})

    image = Image.open(BytesIO(s))

    return image
###########################################################################################################
st.title('Image Generator & Gallery')
st.write('This app uses OpenAI\'s DALLE API to generate images based on a given prompt. The images are then stored in an AWS S3 bucket and a database.')
st.write('The images are then displayed in a gallery below.')

with st.form(key='create_image'):
    # Create a text box for the user to enter a prompt
    prompt = st.text_input('Enter a prompt for the image generator', 'A Shiba Inu wearing a beret and a black turtle neck')

    # Create a button to generate the image
    if st.form_submit_button('Generate Image'):
        image = create_and_save_image(prompt)
        st.image(image, caption=prompt, use_column_width=True)

# Display the gallery
st.write('## Gallery')
st.write('The gallery below displays all the images generated by the app. Click on an image to view it in full size.')

# Get all the images from the database
df = st.session_state.db.fetch()

# Create a list of all the images
image_list = []
for image in df:
    image_list.append(read_file(df['image']))

# Display the images in a gallery
for idx, img in enumerate(image_list): 
    cols = st.beta_columns(4) 
    
    cols[0].image(image_list[idx], use_column_width=True)
    idx+=1
    cols[1].image(image_list[idx], use_column_width=True)
    idx+=idx
    cols[2].image(image_list[idx], use_column_width=True)
    idx+=idx
    cols[3].image(image_list[idx], use_column_width=True)
    idx+=idx
