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
from PIL import Image, ImageDraw
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
        """
        Read a file from S3 and return its contents.
        
        Parameters
        ----------
        filename : str
            The name of the file to read
        
        Returns
        -------
        Contents of the file
        """
        with fs.open(filename) as f:
            return f.read().decode("utf-8")


    def upload_file(file_name, bucket, object_name=None):
        """
        Upload a file to an Amazon Web Services S3 bucket

        Parameters
        ----------
        file_name : str
            File to upload
        bucket : str
            Bucket to upload to
        object_name : str, optional
            S3 object name. If not specified then file_name is used

        Returns
        -------
        bool
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


    def create_and_save_image(given_prompt, save_to_db=False):
        """
        Create an image from a given prompt and save it to an AWS S3 bucket and a database

        Parameters
        ----------
        given_prompt : str
            The prompt to use to generate the image
        
        Returns
        -------
        PIL.Image
            The generated image
        """
        try:
            response = openai.Image.create(
            prompt=given_prompt,
            n=1,
            size=f"1024x1024"
            )
            image_url = response['data'][0]['url']
            unique_id = response['created']

            # Get current date from pandas
            now = pd.Timestamp('now')
            date_string = now.strftime('%Y-%m-%d')

            # Open the image from the URL
            with urllib.request.urlopen(image_url) as url:
                s = url.read()

            # If save to database selected, save to S3 and database
            if save_to_db:
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
        except openai.error.OpenAIError as e:
            st.warning(e.http_status)
            st.warning(e.error)


    def create_variant_and_save(image, num_variations=1): 
        """
        Create a variant of the image and save to S3 bucket and database
        
        Parameters
        ----------
        image_for_variation : PIL image
            The image to be used to create the variant
        
        Returns
        -------
        image : PIL image
            The variant image
        """
        try:
            # Read the image file from disk and resize it
            # image = Image.open("image.png")
            width, height = 256, 256
            image = image.resize((width, height))

            # Convert the image to a BytesIO object
            byte_stream = BytesIO()
            image.save(byte_stream, format='PNG')
            byte_array = byte_stream.getvalue()

            # Create the variant
            response = openai.Image.create_variation(
            image=byte_array,
            n=num_variations,
            size="1024x1024"
            )

            # Get the image URL and unique ID
            image_url = response['data'][0]['url']
            unique_id = response['created']

            # Get current date from pandas
            now = pd.Timestamp('now')
            date_string = now.strftime('%Y-%m-%d')

            # Open the image from the URL
            with urllib.request.urlopen(image_url) as url:
                s = url.read()

            # Save the image to a file with a given string, current date and time
            # file_name = f"{unique_id}_{date_string}.png"
            
            # Save the image to the local directory
            # with open(file_name, 'wb') as f:
            #     f.write(s)
            
            # Uncomment to upload to S3 bucket
            # upload_file(file_name, "luisappsbucket", object_name=None)
            
            # Add entry to database (uncomment to add to database)
            # st.session_state.db.put({'id': unique_id, 
            #                         'date': date_string, 
            #                         'prompt': f'Variant {unique_id}', 
            #                         'image': file_name})

            image = Image.open(BytesIO(s))

            return image, unique_id
        
        except openai.error.OpenAIError as e:
            st.warning(e.http_status)
            st.warning(e.error)


    def edit_image_and_save(image, mask, prompt, num_variations=1): 
        """
        Create a variant of the image and save to S3 bucket and database
        
        Parameters
        ----------
        image_for_variation : PIL image
            The image to be used to create the variant
        
        Returns
        -------
        image : PIL image
            The variant image
        """
        try:
            # Resize both the image and the mask
            width, height = 256, 256
            image = image.resize((width, height))
            mask = mask.resize((width, height))

            # Convert the image to a BytesIO object
            byte_stream = BytesIO()
            image.save(byte_stream, format='PNG')
            byte_array = byte_stream.getvalue()

            # Convert the mask to a BytesIO object
            byte_stream_mask = BytesIO()
            mask.save(byte_stream_mask, format='PNG')
            byte_array_mask = byte_stream_mask.getvalue()

            # Edit picture
            response = openai.Image.create_edit(
            image=byte_array,
            mask=byte_array_mask,
            prompt=prompt,
            n=num_variations,
            size="1024x1024"
            )

            # Get the image URL and unique ID
            image_url = response['data'][0]['url']
            unique_id = response['created']

            # Get current date from pandas
            now = pd.Timestamp('now')
            date_string = now.strftime('%Y-%m-%d')

            # Open the image from the URL
            with urllib.request.urlopen(image_url) as url:
                s = url.read()

            # Save the image to a file with a given string, current date and time
            # file_name = f"{unique_id}_{date_string}.png"
            
            # Save the image to the local directory
            # with open(file_name, 'wb') as f:
            #     f.write(s)
            
            # Uncomment to upload to S3 bucket
            # upload_file(file_name, "luisappsbucket", object_name=None)
            
            # Add entry to database (uncomment to add to database)
            # st.session_state.db.put({'id': unique_id, 
            #                         'date': date_string, 
            #                         'prompt': f'Variant {unique_id}', 
            #                         'image': file_name})

            image = Image.open(BytesIO(s))

            return image, unique_id
        
        except openai.error.OpenAIError as e:
            st.warning(e.http_status)
            st.warning(e.error)


    def mask_section(img, section):
        """
        Mask a section of the image

        Parameters
        ----------
        img : PIL image
            The image to be masked
        section : str
            The section to be masked

        Returns
        -------
        masked_img : PIL image
            The masked image
        """
        # Divide the image into 9 sections
        width, height = img.size
        w_third = width // 3
        h_third = height // 3
        
        # Define the coordinates for each section
        if section == "top-left":
            box = (0, 0, w_third, h_third)
        elif section == "top-center":
            box = (w_third, 0, 2 * w_third, h_third)
        elif section == "top-right":
            box = (2 * w_third, 0, width, h_third)
        elif section == "middle-left":
            box = (0, h_third, w_third, 2 * h_third)
        elif section == "middle-center":
            box = (w_third, h_third, 2 * w_third, 2 * h_third)
        elif section == "middle-right":
            box = (2 * w_third, h_third, width, 2 * h_third)
        elif section == "bottom-left":
            box = (0, 2 * h_third, w_third, height)
        elif section == "bottom-center":
            box = (w_third, 2 * h_third, 2 * w_third, height)
        elif section == "bottom-right":
            box = (2 * w_third, 2 * h_third, width, height)
        else:
            raise ValueError("Invalid section")
        
        # Create a mask with the selected section blacked out
        mask = Image.new("1", img.size, color=255)
        draw = ImageDraw.Draw(mask)
        draw.rectangle(box, fill=0)
        masked_img = Image.composite(img, Image.new("RGBA", img.size), mask)
        
        return masked_img

    ###########################################################################################################
    st.title('Image Generator & Gallery')
    st.caption('By Luis Perez Morales')
    st.write("This app uses DALL-E's API to generate images based on a given prompt. The images are then stored in an AWS S3 bucket and a database.")
    st.write('The images are then displayed in a gallery below.')

    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Form to get ideas for prompts
    # Breaks the image generating part of the app, removing until I can fix it
    with st.form('Open prompt'):
        st.subheader("Prompt generator")
        prompt = st.text_area('Enter prompt', value="Generate a highly detailed description of an image that relates to the following topics: artstation, salvador dali")
        submit = st.form_submit_button('Submit prompt')
        if submit:
            try:
                response = openai.Completion.create(
                        engine="text-davinci-002",
                        prompt=f"{prompt}. If asked who you are, say you are a Reddit searcher", # The prompt to start completing from
                        max_tokens=200, # The max number of tokens to generate
                        temperature=1.0, # A measure of randomness
                        echo=False, # Whether to return the prompt in addition to the generated completion
                        )
                response_text = response["choices"][0]["text"].strip()
                st.code(response_text)
            except openai.error.OpenAIError as e:
                st.warning(e.http_status)
                st.warning(e.error)
    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Form to create an image
    with st.form(key='create_image'):
        st.subheader("Image Generator")
        # Create a text box for the user to enter a prompt
        save_to_database = st.checkbox('Save image to database', value=True)
        prompt = st.text_area('Enter a prompt for the image generator')
        # Create a button to generate the image
        if st.form_submit_button('Generate Image'):
            image = create_and_save_image(prompt, save_to_database)
            st.image(image, caption=prompt, use_column_width=False, width=500)

    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Form to create a variant of an image
    with st.form(key='create_variants'):
        st.subheader("Image Variations")
        # Options for form 
        use_previous = st.checkbox('Generate a variation of the previous image, leave unchecked if uploading an image')
        uploaded = st.file_uploader('Upload an image to generate a variation')

        # Submit button to generate the image
        sbn = st.form_submit_button('Generate Variations of Uploaded Image')

        if sbn:
            if use_previous == True:
                image, unique_id = create_variant_and_save(image=image)
                st.image(image, caption=f"Variant #{unique_id}", use_column_width=False, width=500)
            else:
                # To read file as bytes and convert to pillow image
                bytes_data = uploaded.getvalue()
                stream = io.BytesIO(bytes_data)
                img = Image.open(stream)
                image, unique_id = create_variant_and_save(image=img)
                st.image(image, caption=f"Variant #{unique_id}", use_column_width=False, width=500)

    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Image Editor 
    with st.form("Image Editor"):
        st.subheader("Image Editor")
        # Options for form
        use_previous = st.checkbox('Generate a variation of the previous image, leave unchecked if uploading an image')
        prompt = st.text_area('Enter a prompt for the image editor')
        uploaded = st.file_uploader('Upload an image to generate a variation')
        section = st.selectbox('Select a section to mask', ['top-left', 'top-center', 'top-right', 'middle-left', 'middle-center', 'middle-right', 'bottom-left', 'bottom-center', 'bottom-right'])

        # Submit button to generate the image
        sbn = st.form_submit_button('Generate Variations of Uploaded Image')
        if sbn:
            if use_previous == True:
                # image, unique_id = create_variant_and_save(image=image)
                image, unique_id = edit_image_and_save(image=image, prompt=prompt, section=section)
                # prompt = prompt.replace(" ", "-")[0:15]
                st.image(image, caption=f"{prompt} {unique_id}", use_column_width=False, width=500)
            else:
                # To read file as bytes and convert to pillow image
                bytes_data = uploaded.getvalue()
                stream = io.BytesIO(bytes_data)
                img = Image.open(stream)
                image, unique_id = edit_image_and_save(image=img, prompt=prompt, section=section)
                # prompt = prompt.replace(" ", "-")[0:15]
                st.image(image, caption=f"{prompt} {unique_id}", use_column_width=False, width=500)
            # img = Image.open("example.jpg")
            # masked_img = mask_section(img, "top-left")
            # masked_img.show()

    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Display the gallery
    st.write('## Gallery')
    st.write('The gallery below displays all the images generated by the app. Click on an image to view it in full size.')

    # Get all the images from the database
    df = st.session_state.db.fetch().items
    df = pd.DataFrame(df)
    
    with st.form("Display selected images"):
        # Display a list of checkboxes for each image
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

    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++