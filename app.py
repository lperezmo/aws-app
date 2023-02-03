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
from interactive_table import aggrid_multi_select
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
# LOGIN INFO
def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["USER_PASS"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("Password incorrect")
        return False
    else:
        # Password correct.
        return True
###########################################################################################################
if check_password():
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

    def create_and_save_image(given_prompt, width=1024, height=1024):
        response = openai.Image.create(
        prompt=given_prompt,
        n=1,
        size=f"{width}x{height}"
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
        file_name = f"{unique_id}_{date_string}.jpg"
        
        # Save the image to the local directory
        with open(file_name, 'wb') as f:
            f.write(s)
        
        upload_file(file_name, "luisappsbucket", object_name=None)
        
        # Add entry to database
        st.session_state.db.put({'id': unique_id, 
                                'date': date_string, 
                                'prompt': given_prompt, 
                                'image': file_name})

        image = Image.open(BytesIO(s))

        return image
    ###########################################################################################################
    st.title('Image Generator & Gallery')
    st.caption('By Luis Perez Morales')
    st.write("This app uses DALL-E's API to generate images based on a given prompt. The images are then stored in an AWS S3 bucket and a database.")
    st.write('The images are then displayed in a gallery below.')

    with st.form(key='create_image'):
        # Create a text box for the user to enter a prompt
        prompt = st.text_area('Enter a prompt for the image generator')
        width = st.slider(label, min_value=500, max_value=2500, value=1024)
        height = st.slider(label, min_value=500, max_value=2500, value=1024)
        
        # Create a button to generate the image
        if st.form_submit_button('Generate Image'):
            image = create_and_save_image(prompt, width, height)
            st.image(image, caption=prompt, use_column_width=False, width=500)

    # Display the gallery
    st.write('## Gallery')
    st.write('The gallery below displays all the images generated by the app. Click on an image to view it in full size.')

    # Get all the images from the database
    df = st.session_state.db.fetch().items
    df = pd.DataFrame(df)
    
    with st.form("Display selected images"):
        # Display a list of checkboxes for each image
        # options = st.multiselect('Select images to display', options = list(df['prompt']))
        selection = aggrid_multi_select(df.loc[:,['prompt','date','id','image','key']])

        # Create a button to display the selected images
        if st.form_submit_button('Display'):
            # Display the selected images
            filtered_selection = selection.iloc[:,1:]

            # Get the selected images
            selected_df = df[df['prompt'].isin(filtered_selection['prompt'])]

            image_list = []

            cols = st.columns(4)
            # Display the selected images
            count = 0
            for index, row in selected_df.iterrows():

                s3 = boto3.client('s3')
                with open('temp', 'wb') as f:
                    s3.download_fileobj('luisappsbucket', row['image'], f)

                image = Image.open('temp')
                image_list.append(image)

                with cols[count%4]:
                    st.image(image, caption=row['prompt'], use_column_width=True)
                count += 1

    # Breaks the image generating part of the app, removing until I can fix it
    # with st.form('Open prompt'):
    #     prompt = st.text_input('Enter prompt')
    #     submit = st.form_submit_button('Submit prompt')
    #     if submit:
    #         response = openai.Completion.create(
    #                    # engine="text-davinci-002",
    #                    prompt=f"{prompt}", # The prompt to start completing from
    #                    max_tokens=100, # The max number of tokens to generate
    #                    temperature=1.0, # A measure of randomness
    #                    echo=False, # Whether to return the prompt in addition to the generated completion
    #                    )
    #         response_text = response["choices"][0]["text"].strip()
    #         st.code(response_text)

