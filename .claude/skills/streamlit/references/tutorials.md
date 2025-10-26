# Streamlit - Tutorials

**Pages:** 47

---

## Use Microsoft Entra to authenticate users - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/authentication/microsoft

**Contents:**
- Use Microsoft Entra to authenticate users
- Prerequisites
- Summary
- Create a web application in Microsoft Entra ID
  - Register a new application
  - Gather your application's details
- Build the example
  - Configure your secrets
    - Important
  - Initialize your app

Microsoft Identity Platform is a service within Microsoft Entra that lets you build applications to authenticate users. Your applications can use personal, work, and school accounts managed by Microsoft.

This tutorial requires the following Python libraries:

You should have a clean working directory called your-repository.

You must have a Microsoft Azure account, which includes Microsoft Entra ID.

In this tutorial, you'll build an app that users can log in to with their personal Microsoft accounts. When they log in, they'll see a personalized greeting with their name and have the option to log out.

Here's a look at what you'll build:

.streamlit/secrets.toml

Within Microsoft Entra ID in Azure, you'll need to register a new application and generate a secret needed to configure your app. In this example, your application will only accept personal Microsoft accounts, but you can optionally accept work and school accounts or restrict the application to your personal tenant. Microsoft Entra also lets you connect other, external identity providers.

Go to Microsoft Azure, and sign in to Microsoft.

At the top of the page among the services, select "Microsoft Entra ID."

In the left navigation, select "Manage" → "App registrations."

At the top of the screen, select "New registration."

Fill in a name for your application.

The application name will be visible to your users within the authentication flow presented by Microsoft.

Under "Supported account types," select "Personal Microsoft accounts only."

Under "Redirect URI," select a "Web" platform, and enter your app's URL with the pathname oauth2callback.

For example, if you are developing locally, enter http://localhost:8501/oauth2callback. If you are using a different port, change 8501 to match your port.

At the bottom of the screen, select "Register."

Microsoft will redirect you to your new application, a resource within Azure.

To store your app information to use in later steps, open a text editor, or (even better) create a new item in a password locker.

Always handle your app secrets securely. Remember to label the values as you paste them so you don't mix them up.

Under "Essentials," copy the "Application (client) ID" into your text editor.

This is your client_id.

At the top of the page, select "Endpoints."

Copy the "OpenID Connect metadata document" into your text editor.

This is your server_metadata_url.

In the left navigation, select "Manage" → "Certificates & secrets."

Near the top,

*[Content truncated]*

---

## Connect Streamlit to PostgreSQL - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/databases/postgresql

**Contents:**
- Connect Streamlit to PostgreSQL
- Introduction
- Create a PostgreSQL database
    - Note
- Add username and password to your local app secrets
    - Important
- Copy your app secrets to the cloud
- Add dependencies to your requirements file
- Write your Streamlit app
  - Still have questions?

This guide explains how to securely access a remote PostgreSQL database from Streamlit Community Cloud. It uses st.connection and Streamlit's Secrets management. The below example code will only work on Streamlit version >= 1.28, when st.connection was added.

If you already have a database that you want to use, feel free to skip to the next step.

First, follow this tutorial to install PostgreSQL and create a database (note down the database name, username, and password!). Open the SQL Shell (psql) and enter the following two commands to create a table with some example values:

Your local Streamlit app will read secrets from a file .streamlit/secrets.toml in your app's root directory. Create this file if it doesn't exist yet and add the name, user, and password of your database as shown below:

When copying your app secrets to Streamlit Community Cloud, be sure to replace the values of host, port, database, username, and password with those of your remote PostgreSQL database!

Add this file to .gitignore and don't commit it to your GitHub repo!

As the secrets.toml file above is not committed to GitHub, you need to pass its content to your deployed app (on Streamlit Community Cloud) separately. Go to the app dashboard and in the app's dropdown menu, click on Edit Secrets. Copy the content of secrets.toml into the text area. More information is available at Secrets management.

Add the psycopg2-binary and SQLAlchemy packages to your requirements.txt file, preferably pinning its version (replace x.x.x with the version you want installed):

Copy the code below to your Streamlit app and run it. Make sure to adapt query to use the name of your table.

See st.connection above? This handles secrets retrieval, setup, query caching and retries. By default, query() results are cached without expiring. In this case, we set ttl="10m" to ensure the query result is cached for no longer than 10 minutes. You can also set ttl=0 to disable caching. Learn more in Caching.

If everything worked out (and you used the example table we created above), your app should look like this:

Our forums are full of helpful information and Streamlit experts.

---

## Build a basic LLM chat app - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/chat-and-llm-apps/build-conversational-apps

**Contents:**
- Build a basic LLM chat app
- Introduction
- Chat elements
  - st.chat_message
  - st.chat_input
- Build a bot that mirrors your input
- Build a simple chatbot GUI with streaming
- Build a ChatGPT-like app
  - Install dependencies
  - Add OpenAI API key to Streamlit secrets

The advent of large language models like GPT has revolutionized the ease of developing chat-based applications. Streamlit offers several Chat elements, enabling you to build Graphical User Interfaces (GUIs) for conversational agents or chatbots. Leveraging session state along with these elements allows you to construct anything from a basic chatbot to a more advanced, ChatGPT-like experience using purely Python code.

In this tutorial, we'll start by walking through Streamlit's chat elements, st.chat_message and st.chat_input. Then we'll proceed to construct three distinct applications, each showcasing an increasing level of complexity and functionality:

Here's a sneak peek of the LLM-powered chatbot GUI with streaming we'll build in this tutorial:

Play around with the above demo to get a feel for what we'll build in this tutorial. A few things to note:

Before we start building, let's take a closer look at the chat elements we'll use.

Streamlit offers several commands to help you build conversational apps. These chat elements are designed to be used in conjunction with each other, but you can also use them separately.

st.chat_message lets you insert a chat message container into the app so you can display messages from the user or the app. Chat containers can contain other Streamlit elements, including charts, tables, text, and more. st.chat_input lets you display a chat input widget so the user can type in a message.

For an overview of the API, check out this video tutorial by Chanin Nantasenamat (@dataprofessor), a Senior Developer Advocate at Streamlit.

st.chat_message lets you insert a multi-element chat message container into your app. The returned container can contain any Streamlit element, including charts, tables, text, and more. To add elements to the returned container, you can use with notation.

st.chat_message's first parameter is the name of the message author, which can be either "user" or "assistant" to enable preset styling and avatars, like in the demo above. You can also pass in a custom string to use as the author name. Currently, the name is not shown in the UI but is only set as an accessibility label. For accessibility reasons, you should not use an empty string.

Here's an minimal example of how to use st.chat_message to display a welcome message:

Notice the message is displayed with a default avatar and styling since we passed in "user" as the author name. You can also pass in "assistant" as the author name to use a differ

*[Content truncated]*

---

## Work with Streamlit elements - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/elements

**Contents:**
- Work with Streamlit elements
      - Annotate an Altair chart
      - Get row selections from dataframes
  - Still have questions?

Add annotations to an Altair chart.

Work with user row-selections in dataframes.

Our forums are full of helpful information and Streamlit experts.

---

## Connect Streamlit to a private Google Sheet - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/databases/private-gsheet

**Contents:**
- Connect Streamlit to a private Google Sheet
- Introduction
  - Prerequisites
- Create a Google Sheet
- Enable the Sheets API
- Create a service account & key file
    - Note
- Share the Google Sheet with the service account
- Add the key file to your local app secrets
    - Important

This guide explains how to securely access a private Google Sheet from Streamlit Community Cloud. It uses st.connection, Streamlit GSheetsConnection, and Streamlit's Secrets management.

If you are fine with enabling link sharing for your Google Sheet (i.e. everyone with the link can view it), the guide Connect Streamlit to a public Google Sheet shows a simpler method of doing this. If your Sheet contains sensitive information and you cannot enable link sharing, keep on reading.

This tutorial requires streamlit>=1.28 and st-gsheets-connection in your Python environment.

If you already have a Sheet that you want to use, you can skip to the next step.

Create a spreadsheet with this example data.

Programmatic access to Google Sheets is controlled through Google Cloud Platform. Create an account or sign in and head over to the APIs & Services dashboard (select or create a project if asked). As shown below, search for the Sheets API and enable it:

To use the Sheets API from Streamlit Community Cloud, you need a Google Cloud Platform service account (a special account type for programmatic data access). Go to the Service Accounts page and create an account with the Viewer permission (this will let the account access data but not change it):

The button "CREATE SERVICE ACCOUNT" is gray, you don't have the correct permissions. Ask the admin of your Google Cloud project for help.

After clicking "DONE", you should be back on the service accounts overview. First, note down the email address of the account you just created (important for next step!). Then, create a JSON key file for the new account and download it:

By default, the service account you just created cannot access your Google Sheet. To give it access, click on the "Share" button in the Google Sheet, add the email of the service account (noted down in step 2), and choose the correct permission (if you just want to read the data, "Viewer" is enough):

Your local Streamlit app will read secrets from a file .streamlit/secrets.toml in your app's root directory. Create this file if it doesn't exist yet and add the URL of your Google Sheet plus the content of the key file you downloaded to it as shown below:

Add this file to .gitignore and don't commit it to your GitHub repo!

Copy the code below to your Streamlit app and run it.

See st.connection above? This handles secrets retrieval, setup, query caching and retries. By default, .read() results are cached without expiring. You can pass optional parame

*[Content truncated]*

---

## Connect to data sources - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/databases

**Contents:**
- Connect Streamlit to data sources
      - AWS S3
      - BigQuery
      - Firestore (blog)
      - Google Cloud Storage
      - Microsoft SQL Server
      - MongoDB
      - MySQL
      - Neon
      - PostgreSQL

These step-by-step guides demonstrate how to connect Streamlit apps to various databases & APIs. They use Streamlit's Secrets management and caching to provide secure and fast data access.

Our forums are full of helpful information and Streamlit experts.

---

## Connect Streamlit to Google Cloud Storage - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/databases/gcs

**Contents:**
- Connect Streamlit to Google Cloud Storage
- Introduction
- Create a Google Cloud Storage bucket and add a file
    - Note
- Enable the Google Cloud Storage API
- Create a service account and key file
    - Note
- Add the key to your local app secrets
    - Important
- Copy your app secrets to the cloud

This guide explains how to securely access files on Google Cloud Storage from Streamlit Community Cloud. It uses Streamlit FilesConnection, the gcsfs library and Streamlit's Secrets management.

If you already have a bucket that you want to use, feel free to skip to the next step.

First, sign up for Google Cloud Platform or log in. Go to the Google Cloud Storage console and create a new bucket.

Navigate to the upload section of your new bucket:

And upload the following CSV file, which contains some example data:

The Google Cloud Storage API is enabled by default when you create a project through the Google Cloud Console or CLI. Feel free to skip to the next step.

If you do need to enable the API for programmatic access in your project, head over to the APIs & Services dashboard (select or create a project if asked). Search for the Cloud Storage API and enable it. The screenshot below has a blue "Manage" button and indicates the "API is enabled" which means no further action needs to be taken. This is very likely what you have since the API is enabled by default. However, if that is not what you see and you have an "Enable" button, you'll need to enable the API:

To use the Google Cloud Storage API from Streamlit, you need a Google Cloud Platform service account (a special type for programmatic data access). Go to the Service Accounts page and create an account with Viewer permission.

If the button CREATE SERVICE ACCOUNT is gray, you don't have the correct permissions. Ask the admin of your Google Cloud project for help.

After clicking DONE, you should be back on the service accounts overview. Create a JSON key file for the new account and download it:

Your local Streamlit app will read secrets from a file .streamlit/secrets.toml in your app's root directory. Create this file if it doesn't exist yet and add the access key to it as shown below:

Add this file to .gitignore and don't commit it to your GitHub repo!

As the secrets.toml file above is not committed to GitHub, you need to pass its content to your deployed app (on Streamlit Community Cloud) separately. Go to the app dashboard and in the app's dropdown menu, click on Edit Secrets. Copy the content of secrets.toml into the text area. More information is available at Secrets management.

Add the FilesConnection and gcsfs packages to your requirements.txt file, preferably pinning the versions (replace x.x.x with the version you want installed):

Copy the code below to your Streamlit app and ru

*[Content truncated]*

---

## Build LLM apps - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/chat-and-llm-apps

**Contents:**
- Build LLM apps
      - Build a basic chat app
      - Build an LLM app using LangChain
      - Get chat response feedback
      - Validate and edit chat responses
  - Still have questions?

Build a simple OpenAI chat app to get started with Streamlit's chat elements.

Build a chat app using the LangChain framework with OpenAI.

Buid a chat app and let users rate the responses. (thumb_up thumb_down)

Build a chat app with response validation. Let users correct or edit the responses.

Our forums are full of helpful information and Streamlit experts.

---

## Connect Streamlit to AWS S3 - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/databases/aws-s3

**Contents:**
- Connect Streamlit to AWS S3
- Introduction
- Create an S3 bucket and add a file
    - Note
- Create access keys
    - Tip
- Set up your AWS credentials locally
    - Important
- Copy your app secrets to the cloud
- Add FilesConnection and s3fs to your requirements file

This guide explains how to securely access files on AWS S3 from Streamlit Community Cloud. It uses Streamlit FilesConnection, the s3fs library and optionally Streamlit's Secrets management.

If you already have a bucket that you want to use, feel free to skip to the next step.

First, sign up for AWS or log in. Go to the S3 console and create a new bucket:

Navigate to the upload section of your new bucket:

And note down the "AWS Region" for later. In this example, it's us-east-1, but it may differ for you.

Next, upload the following CSV file, which contains some example data:

Go to the AWS console, create access keys as shown below and copy the "Access Key ID" and "Secret Access Key":

Access keys created as a root user have wide-ranging permissions. In order to make your AWS account more secure, you should consider creating an IAM account with restricted permissions and using its access keys. More information here.

Streamlit FilesConnection and s3fs will read and use your existing AWS credentials and configuration if available - such as from an ~/.aws/credentials file or environment variables.

If you don't already have this set up, or plan to host the app on Streamlit Community Cloud, you should specify the credentials from a file .streamlit/secrets.toml in your app's root directory or your home directory. Create this file if it doesn't exist yet and add to it the access key ID, access key secret, and the AWS default region you noted down earlier, as shown below:

Be sure to replace xxx above with the values you noted down earlier, and add this file to .gitignore so you don't commit it to your GitHub repo!

To host your app on Streamlit Community Cloud, you will need to pass your credentials to your deployed app via secrets. Go to the app dashboard and in the app's dropdown menu, click on Edit Secrets. Copy the content of secrets.toml above into the text area. More information is available at Secrets management.

Add the FilesConnection and s3fs packages to your requirements.txt file, preferably pinning the versions (replace x.x.x with the version you want installed):

Copy the code below to your Streamlit app and run it. Make sure to adapt the name of your bucket and file. Note that Streamlit automatically turns the access keys from your secrets file into environment variables, where s3fs searches for them by default.

See st.connection above? This handles secrets retrieval, setup, result caching and retries. By default, read() results are cached w

*[Content truncated]*

---

## Connect Streamlit to Neon - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/databases/neon

**Contents:**
- Connect Streamlit to Neon
- Introduction
  - Prerequisites
    - Note
- Create a Neon project
- Add the Neon connection string to your local app secrets
    - Important
- Write your Streamlit app
- Connecting to a Neon database from Community Cloud
  - Still have questions?

This guide explains how to securely access a Neon database from Streamlit. Neon is a fully managed serverless PostgreSQL database that separates storage and compute to offer features such as instant branching and automatic scaling.

The following packages must be installed in your Python environment:

You may use psycopg2 instead of psycopg2-binary. However, building Psycopg requires a few prerequisites (like a C compiler). To use psycopg2 on Community Cloud, you must include libpq-dev in a packages.txt file in the root of your repository. psycopg2-binary is a stand-alone package that is practical for testing and development.

You must have a Neon account.

You should have a basic understanding of st.connection and Secrets management.

If you already have a Neon project that you want to use, you can skip to the next step.

Log in to the Neon console and navigate to the Projects section.

If you see a prompt to enter your project name, skip to the next step. Otherwise, click the "New Project" button to create a new project.

Enter "Streamlit-Neon" for your project name, accept the othe default settings, and click "Create Project."

After Neon creates your project with a ready-to-use neondb database, you will be redirected to your project's Quickstart.

Click on "SQL Editor" from the left sidebar.

Replace the text in the input area with the following code and click "Run" to add sample data to your project.

Within your Neon project, click "Dashboard" in the left sidebar.

Within the "Connection Details" tile, locate your database connection string. It should look similar to this:

If you do not already have a .streamlit/secrets.toml file in your app's root directory, create an empty secrets file.

Copy your connection string and add it to your app's .streamlit/secrets.toml file as follows:

Add this file to .gitignore and don't commit it to your GitHub repo!

Copy the code below to your Streamlit app and save it.

The st.connection object above handles secrets retrieval, setup, query caching and retries.

By default, query() results are cached without expiring. Setting the ttl parameter to "10m" ensures the query result is cached for no longer than 10 minutes. You can also set ttl=0 to disable caching. Learn more in Caching.

Run your Streamlit app.

If everything worked out (and you used the example table we created above), your app should look like this:

This tutorial assumes a local Streamlit app, but you can also connect to a Neon database from apps ho

*[Content truncated]*

---

## Connect Streamlit to Supabase - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/databases/supabase

**Contents:**
- Connect Streamlit to Supabase
- Introduction
    - Note
- Sign in to Supabase and create a project
    - Important
- Create a Supabase database
  - Add Supabase Project URL and API key to your local app secrets
    - Important
- Copy your app secrets to the cloud
- Add st-supabase-connection to your requirements file

This guide explains how to securely access a Supabase instance from Streamlit Community Cloud. It uses st.connection, Streamlit Supabase Connector (a community-built connection developed by @SiddhantSadangi) and Streamlit's Secrets management. Supabase is the open source Firebase alternative and is based on PostgreSQL.

Community-built connections, such as the Streamlit Supabase Connector, extend and build on the st.connection interface and make it easier than ever to build Streamlit apps with a wide variety of data sources. These type of connections work exactly the same as the ones built into Streamlit and have access to all the same capabilities.

First, head over to Supabase and sign up for a free account using your GitHub.

Once you're signed in, you can create a project.

Your Supabase account

Your screen should look like this once your project has been created:

Make sure to note down your Project API Key and Project URL highlighted in the above screenshot. ☝️

You will need these to connect to your Supabase instance from Streamlit.

Now that you have a project, you can create a database and populate it with some sample data. To do so, click on the SQL editor button on the same project page, followed by the New query button in the SQL editor.

In the SQL editor, enter the following queries to create a database and a table with some example values:

Click Run to execute the queries. To verify that the queries were executed successfully, click on the Table Editor button on the left menu, followed by your newly created table mytable.

Write and run your queries

View your table in the Table Editor

With your Supabase database created, you can now connect to it from Streamlit!

Your local Streamlit app will read secrets from a file .streamlit/secrets.toml in your app's root directory. Create this file if it doesn't exist yet and add the SUPABASE_URL and SUPABASE_KEY here:

Replace xxxx above with your Project URL and API key from Step 1.

Add this file to .gitignore and don't commit it to your GitHub repo!

As the secrets.toml file above is not committed to GitHub, you need to pass its content to your deployed app (on Streamlit Community Cloud) separately. Go to the app dashboard and in the app's dropdown menu, click on Edit Secrets. Copy the content of secrets.toml into the text area. More information is available at Secrets management.

Add the st-supabase-connection community-built connection library to your requirements.txt file, preferably pinning

*[Content truncated]*

---

## Authenticate users and personalize your app - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/authentication

**Contents:**
- Authenticate users and personalize your app
      - Google Auth Platform
      - Microsoft Entra
  - Still have questions?

Streamlit supports user authentication with the OpenID Connect (OIDC) protocol. You can use any OIDC provider. Whether you want to create a social login or manage your enterprise users, Streamlit makes it simple to authenticate your users.

Google Auth Platform Google is one of the most popular identity providers for social logins. You can use the Google Auth Platform with any Google account, including personal and organization accounts.

Microsoft Entra Microsoft is popular for both social and business logins. You can include personal, school, or work accounts in your integration.

Our forums are full of helpful information and Streamlit experts.

---

## Create a fragment across multiple containers - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/execution-flow/create-a-multiple-container-fragment

**Contents:**
- Create a fragment across multiple containers
- Applied concepts
- Prerequisites
- Summary
- Build the example
  - Initialize your app
  - Frame out your app's containers
  - Define your fragments
  - Put the functions together together to create an app
  - Still have questions?

Streamlit lets you turn functions into fragments, which can rerun independently from the full script. If your fragment doesn't write to outside containers, Streamlit will clear and redraw all the fragment elements with each fragment rerun. However, if your fragment does write elements to outside containers, Streamlit will not clear those elements during a fragment rerun. Instead, those elements accumulate with each fragment rerun until the next full-script rerun. If you want a fragment to update multiple containers in your app, use st.empty() containers to prevent accumulating elements.

This tutorial requires the following version of Streamlit:

You should have a clean working directory called your-repository.

You should have a basic understanding of fragments and st.empty().

In this toy example, you'll build an app with six containers. Three containers will have orange cats. The other three containers will have black cats. You'll have three buttons in the sidebar: "Herd the black cats," "Herd the orange cats," and "Herd all the cats." Since herding cats is slow, you'll use fragments to help Streamlit run the associated processes efficiently. You'll create two fragments, one for the black cats and one for the orange cats. Since the buttons will be in the sidebar and the fragments will update containers in the main body, you'll use a trick with st.empty() to ensure you don't end up with too many cats in your app (if it's even possible to have too many cats). 😻

Here's a look at what you'll build:

In your_repository, create a file named app.py.

In a terminal, change directories to your_repository, and start your app:

Your app will be blank because you still need to add code.

In app.py, write the following:

You'll use time.sleep() to slow things down and see the fragments working.

Save your app.py file, and view your running app.

In your app, select "Always rerun", or press the "A" key.

Your preview will be blank but will automatically update as you save changes to app.py.

Add a title to your app and two rows of three containers.

Save your file to see your updated preview.

Define a helper function to draw two black cats.

This function represents "herding two cats" and uses time.sleep() to simulate a slower process. You will use this to draw two cats in one of your grid cards later on.

Define another helper function to draw two orange cats.

Optional: Test out your functions by calling each one within a grid card.

Save your app.py file to see 

*[Content truncated]*

---

## Trigger a full-script rerun from inside a fragment - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/execution-flow/trigger-a-full-script-rerun-from-a-fragment

**Contents:**
- Trigger a full-script rerun from inside a fragment
- Applied concepts
- Prerequisites
- Summary
- Build the example
  - Initialize your app
  - Build a function to create random sales data
  - Build a function to show daily sales data
  - Build a function to show monthly sales data
  - Put the functions together together to create an app

Streamlit lets you turn functions into fragments, which can rerun independently from the full script. When a user interacts with a widget inside a fragment, only the fragment reruns. Sometimes, you may want to trigger a full-script rerun from inside a fragment. To do this, call st.rerun inside the fragment.

This tutorial requires the following version of Streamlit:

You should have a clean working directory called your-repository.

You should have a basic understanding of fragments and st.rerun.

In this example, you'll build an app to display sales data. The app has two sets of elements that depend on a date selection. One set of elements displays information for the selected day. The other set of elements displays information for the associated month. If the user changes days within a month, Streamlit only needs to update the first set of elements. If the user selects a day in a different month, Streamlit needs to update all the elements.

You'll collect the day-specific elements into a fragment to avoid rerunning the full app when a user changes days within the same month. If you want to jump ahead to the fragment function definition, see Build a function to show daily sales data.

Here's a look at what you'll build:

Click here to see the example live on Community Cloud.

In your_repository, create a file named app.py.

In a terminal, change directories to your_repository, and start your app:

Your app will be blank because you still need to add code.

In app.py, write the following:

You'll be using these libraries as follows:

Save your app.py file, and view your running app.

In your app, select "Always rerun", or press the "A" key.

Your preview will be blank but will automatically update as you save changes to app.py.

To begin with, you'll define a function to randomly generate some sales data. It's okay to skip this section if you just want to copy the function.

Use an @st.cache_data decorator and start your function definition.

You don't need to keep re-randomizing the data, so the caching decorator will randomly generate the data once and save it in Streamlit's cache. As your app reruns, it will use the cached value instead of recomputing new data.

Define the list of product names and assign an average daily sales value to each.

For each product, use its average daily sales to randomly generate daily sales values for an entire year.

In the last line, data.index.date strips away the timestamp, so the index will show clean dates.

Return t

*[Content truncated]*

---

## Get dataframe row-selections from users (streamlit<1.35.0) - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/elements/dataframe-row-selections-old

**Contents:**
- Get dataframe row-selections from users (streamlit<1.35.0)
- Example
  - Still have questions?

Before dataframe selections were introduced in Streamlit version 1.35.0, st.dataframe and st.data_editor did not natively support passing user-selected rows to the Python backend. If you would like to work with row (or column)selections for dataframes, we recommend upgrading to streamlit>=1.35.0. For a newer tutorial, see Get dataframe row-selections from users.

However, if you need a workaround for an older version of Streamlit, you can effectively get row selections by adding an extra Checkbox column) to your dataframe using st.data_editor. Use this extra column to collect a user's selection(s).

In the following example, we define a function which accepts a dataframe and returns the rows selected by a user. Within the function, the dataframe is copied to prevent mutating it. We insert a temporary "Select" column into the copied dataframe before passing the copied data into st.data_editor. We have disabled editing for all other columns, but you can make them editable if desired. After filtering the dataframe and dropping the temporary column, our function returns the selected rows.

Our forums are full of helpful information and Streamlit experts.

---

## Build a basic LLM chat app - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/llms/build-conversational-apps

**Contents:**
- Build a basic LLM chat app
- Introduction
- Chat elements
  - st.chat_message
  - st.chat_input
- Build a bot that mirrors your input
- Build a simple chatbot GUI with streaming
- Build a ChatGPT-like app
  - Install dependencies
  - Add OpenAI API key to Streamlit secrets

The advent of large language models like GPT has revolutionized the ease of developing chat-based applications. Streamlit offers several Chat elements, enabling you to build Graphical User Interfaces (GUIs) for conversational agents or chatbots. Leveraging session state along with these elements allows you to construct anything from a basic chatbot to a more advanced, ChatGPT-like experience using purely Python code.

In this tutorial, we'll start by walking through Streamlit's chat elements, st.chat_message and st.chat_input. Then we'll proceed to construct three distinct applications, each showcasing an increasing level of complexity and functionality:

Here's a sneak peek of the LLM-powered chatbot GUI with streaming we'll build in this tutorial:

Play around with the above demo to get a feel for what we'll build in this tutorial. A few things to note:

Before we start building, let's take a closer look at the chat elements we'll use.

Streamlit offers several commands to help you build conversational apps. These chat elements are designed to be used in conjunction with each other, but you can also use them separately.

st.chat_message lets you insert a chat message container into the app so you can display messages from the user or the app. Chat containers can contain other Streamlit elements, including charts, tables, text, and more. st.chat_input lets you display a chat input widget so the user can type in a message.

For an overview of the API, check out this video tutorial by Chanin Nantasenamat (@dataprofessor), a Senior Developer Advocate at Streamlit.

st.chat_message lets you insert a multi-element chat message container into your app. The returned container can contain any Streamlit element, including charts, tables, text, and more. To add elements to the returned container, you can use with notation.

st.chat_message's first parameter is the name of the message author, which can be either "user" or "assistant" to enable preset styling and avatars, like in the demo above. You can also pass in a custom string to use as the author name. Currently, the name is not shown in the UI but is only set as an accessibility label. For accessibility reasons, you should not use an empty string.

Here's an minimal example of how to use st.chat_message to display a welcome message:

Notice the message is displayed with a default avatar and styling since we passed in "user" as the author name. You can also pass in "assistant" as the author name to use a differ

*[Content truncated]*

---

## Use externally hosted fonts and fallbacks to customize your font - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/configuration-and-theming/external-fonts

**Contents:**
- Use externally hosted fonts and fallbacks to customize your font
- Prerequisites
- Summary
- Collect your font CSS URLs
- Create your app configuration
- Build the example
  - Initialize your app
  - Display some text in your app
  - Still have questions?

Streamlit comes with Source Sans as the default font, but you can configure your app to use another font. This tutorial uses variable font files and is a walkthrough of Example 3 from Customize fonts in your Streamlit app. For an example that uses self-hosted variable font files, see Use variable font files to customize your font. For an example that uses self-hosted static font files, see Use static font files to customize your font.

This tutorial uses inline font definitions, which were introduced in Streamlit version 1.50.0. For an older workaround, see Use externally hosted fonts and fallbacks to customize your font (streamlit<1.50.0).

This tutorial requires the following version of Streamlit:

You should have a clean working directory called your-repository.

You should have a basic understanding of working with font files in web development. Otherwise, start by reading Customize fonts in your Streamlit app up to Example 3.

The following example uses Google-hosted instances of Nunito and Space Mono.

Here's a look at what you'll build:

.streamlit/config.toml:

To collect your URLs to use in later steps, open a text editor.

Remember to label the values as you paste them so you don't mix them up.

Search for or follow the link to Nunito, and select "Get font."

To get a link to a style sheet for your font files, in the upper-right corner, select the shopping bag (shopping_bag), and then select "code Get embed code."

On the right, in the first code block, copy the href URL from the third link, and paste it into your text editor.

By default, the "Embed Code" page loads with the "Web" tab and "<link>" radio option selected. The first code block is titled, "Embed code in the <head> of your html." The URL is a link to a style sheet and should look like the following text:

To remove Nunito from your list and get a clean URL for Space Mono, select the trash can (delete). Then, repeat the previous three steps for Space Mono.

The URL should look like the following text:

In your text editor, modify each URL by prepending its font family and a colon separator:

Because Space Mono has a space in its name, use single quotes around the font family. These will be inner quotes when the string is later copied into your configuration file.

In your_repository/, create a .streamlit/config.toml file:

To set your alternative fonts as the default font for your app, in .streamlit/config.toml, add the following text:

This sets Nunito as the default for all text in 

*[Content truncated]*

---

## Connect Streamlit to TigerGraph - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/databases/tigergraph

**Contents:**
- Connect Streamlit to TigerGraph
- Introduction
- Create a TigerGraph Cloud Database
- Add username and password to your local app secrets
    - Important
- Copy your app secrets to the cloud
- Add PyTigerGraph to your requirements file
- Write your Streamlit app
  - Still have questions?

This guide explains how to securely access a TigerGraph database from Streamlit Community Cloud. It uses the pyTigerGraph library and Streamlit's Secrets management.

First, follow the official tutorials to create a TigerGraph instance in TigerGraph Cloud, either as a blog or a video. Note your username, password, and subdomain.

For this tutorial, we will be using the COVID-19 starter kit. When setting up your solution, select the “COVID-19 Analysis" option.

Once it is started, ensure your data is downloaded and queries are installed.

Your local Streamlit app will read secrets from a file .streamlit/secrets.toml in your app’s root directory. Create this file if it doesn’t exist yet and add your TigerGraph Cloud instance username, password, graph name, and subdomain as shown below:

Add this file to .gitignore and don't commit it to your GitHub repo!

As the secrets.toml file above is not committed to GitHub, you need to pass its content to your deployed app (on Streamlit Community Cloud) separately. Go to the app dashboard and in the app's dropdown menu, click on Edit Secrets. Copy the content of secrets.toml into the text area. More information is available at Secrets management.

Add the pyTigerGraph package to your requirements.txt file, preferably pinning its version (replace x.x.x with the version you want installed):

Copy the code below to your Streamlit app and run it. Make sure to adapt the name of your graph and query.

See st.cache_data above? Without it, Streamlit would run the query every time the app reruns (e.g. on a widget interaction). With st.cache_data, it only runs when the query changes or after 10 minutes (that's what ttl is for). Watch out: If your database updates more frequently, you should adapt ttl or remove caching so viewers always see the latest data. Learn more in Caching.

If everything worked out (and you used the example data we created above), your app should look like this:

Our forums are full of helpful information and Streamlit experts.

---

## Annotate an Altair chart - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/elements/annotate-an-altair-chart

**Contents:**
- Annotate an Altair chart
- Applied concepts
- Prerequisites
- Summary
- Build the example
  - Initialize your app
  - Build the data layer
  - Build the annotation layer
  - Combine the chart layers
- Next steps

Altair allows you to annotate your charts with text, images, and emojis. You can do this by overlaying two charts to create a layered chart.

This tutorial requires the following Python libraries:

This tutorial assumes you have a clean working directory called your-repository.

You should have a basic understanding of the Vega-Altair charting library.

In this example, you will create a time-series chart to track the evolution of stock prices. The chart will have two layers: a data layer and an annotation layer. Each layer is an altair.Chart object. You will combine the two charts with the + opterator to create a layered chart.

Within the data layer, you'll add a multi-line tooltip to show information about datapoints. To learn more about multi-line tooltips, see this example in Vega-Altair's documentation. You'll add another tooltip to the annotation layer.

Here's a look at what you'll build:

In your_repository, create a file named app.py.

In a terminal, change directories to your_repository, and start your app:

Your app will be blank because you still need to add code.

In app.py, write the following:

You'll be using these libraries as follows:

Save your app.py file, and view your running app.

In your app, select "Always rerun", or press the "A" key.

Your preview will be blank but will automatically update as you save changes to app.py.

You'll build an interactive time-series chart of the stock prices with a multi-line tooltip. The x-axis represents the date, and the y-axis represents the stock price.

Import data from vega_datasets.

The @st.cache_data decorator turns get_data() into a cahced function. Streamlit will only download the data once since the data will be saved in a cache. For more information about caching, see Caching overview.

Define a mouseover selection event in Altair.

This defines a mouseover selection for points. fields=["date"] allows Altair to identify other points with the same date. You will use this to create a vertical line highlight when a user hovers over a point.

Define a basic line chart to graph the five series in your data set.

Draw points on the lines and highlight them based on the mouseover selection.

Since the mouseover selection includes fields=["date"], Altair will draw circles on each series at the same date.

Draw a vertical rule at the location of the mouseover selection.

The opacity parameter ensures each vertical line is only visible when it's part of a mouseover selection. Each alt.Tooltip add

*[Content truncated]*

---

## Connect Streamlit to Microsoft SQL Server - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/databases/mssql

**Contents:**
- Connect Streamlit to Microsoft SQL Server
- Introduction
- Create an SQL Server database
    - Note
- Connect locally
    - Tip
  - Create a SQL Server database
  - Insert some data
  - Add username and password to your local app secrets
    - Important

This guide explains how to securely access a remote Microsoft SQL Server database from Streamlit Community Cloud. It uses the pyodbc library and Streamlit's Secrets management.

If you already have a remote database that you want to use, feel free to skip to the next step.

First, follow the Microsoft documentation to install SQL Server and the sqlcmd Utility. They have detailed installation guides on how to:

Once you have SQL Server installed, note down your SQL Server name, username, and password during setup.

If you are connecting locally, use sqlcmd to connect to your new local SQL Server instance.

In your terminal, run the following command:

As you are connecting locally, the SQL Server name is localhost, the username is SA, and the password is the one you provided during the SA account setup.

You should see a sqlcmd command prompt 1>, if successful.

If you run into a connection failure, review Microsoft's connection troubleshooting recommendations for your OS (Linux & Windows).

When connecting remotely, the SQL Server name is the machine name or IP address. You might also need to open the SQL Server TCP port (default 1433) on your firewall.

By now, you have SQL Server running and have connected to it with sqlcmd! 🥳 Let's put it to use by creating a database containing a table with some example values.

From the sqlcmd command prompt, run the following Transact-SQL command to create a test database mydb:

To execute the above command, type GO on a new line:

Next create a new table, mytable, in the mydb database with three columns and two rows.

Switch to the new mydb database:

Create a new table with the following schema:

Insert some data into the table:

Type GO to execute the above commands:

To end your sqlcmd session, type QUIT on a new line.

Your local Streamlit app will read secrets from a file .streamlit/secrets.toml in your app's root directory. Create this file if it doesn't exist yet and add the SQL Server name, database name, username, and password as shown below:

When copying your app secrets to Streamlit Community Cloud, be sure to replace the values of server, database, username, and password with those of your remote SQL Server!

And add this file to .gitignore and don't commit it to your GitHub repo.

As the secrets.toml file above is not committed to GitHub, you need to pass its content to your deployed app (on Streamlit Community Cloud) separately. Go to the app dashboard and in the app's dropdown menu, click on Edit Sec

*[Content truncated]*

---

## Deploy Streamlit using Kubernetes - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/tutorials/kubernetes

**Contents:**
- Deploy Streamlit using Kubernetes
- Introduction
- Prerequisites
  - Install Docker Engine
    - Tip
  - Install the gcloud CLI
- Create a Docker container
  - Create an entrypoint script
  - Create a Dockerfile
    - Important

So you have an amazing app and you want to start sharing it with other people, what do you do? You have a few options. First, where do you want to run your Streamlit app, and how do you want to access it?

Wherever you decide to deploy your app, you will first need to containerize it. This guide walks you through using Kubernetes to deploy your app. If you prefer Docker see Deploy Streamlit using Docker.

If you haven't already done so, install Docker on your server. Docker provides .deb and .rpm packages from many Linux distributions, including:

Verify that Docker Engine is installed correctly by running the hello-world Docker image:

Follow Docker's official post-installation steps for Linux to run Docker as a non-root user, so that you don't have to preface the docker command with sudo.

In this guide, we will orchestrate Docker containers with Kubernetes and host docker images on the Google Container Registry (GCR). As GCR is a Google-supported Docker registry, we need to register gcloud as the Docker credential helper.

Follow the official documentation to Install the gcloud CLI and initialize it.

We need to create a docker container which contains all the dependencies and the application code. Below you can see the entrypoint, i.e. the command run when the container starts, and the Dockerfile definition.

Create a run.sh script containing the following:

Docker builds images by reading the instructions from a Dockerfile. A Dockerfile is a text document that contains all the commands a user could call on the command line to assemble an image. Learn more in the Dockerfile reference. The docker build command builds an image from a Dockerfile. The docker run command first creates a container over the specified image, and then starts it using the specified command.

Here's an example Dockerfile that you can add to the root of your directory.

As mentioned in Development flow, for Streamlit version 1.10.0 and higher, Streamlit apps cannot be run from the root directory of Linux distributions. Your main script should live in a directory other than the root directory. If you try to run a Streamlit app from the root directory, Streamlit will throw a FileNotFoundError: [Errno 2] No such file or directory error. For more information, see GitHub issue #5239.

If you are using Streamlit version 1.10.0 or higher, you must set the WORKDIR to a directory other than the root directory. For example, you can set the WORKDIR to /home/appuser as shown in the example Do

*[Content truncated]*

---

## Build multipage apps - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/multipage

**Contents:**
- Build multipage apps
      - Create a dynamic navigation menu
  - Still have questions?

Create a dynamic, user-dependant navigation menu with st.navigation.

Our forums are full of helpful information and Streamlit experts.

---

## Deployment tutorials - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/tutorials

**Contents:**
- Deployment tutorials
      - Streamlit Community Cloud
      - Docker
      - Kubernetes
  - Still have questions?

This sections contains step-by-step guides on how to deploy Streamlit apps to various cloud platforms and services. We have deployment guides for:

While we work on official Streamlit deployment guides for other hosting providers, here are some user-submitted tutorials for different cloud services:

Our forums are full of helpful information and Streamlit experts.

---

## Connect Streamlit to Snowflake - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/databases/snowflake

**Contents:**
- Connect Streamlit to Snowflake
- Introduction
  - Prerequisites
    - Note
- Create a Snowflake database
    - Important
- Add connection parameters to your local app secrets
  - Option 1: Use .streamlit/secrets.toml
    - Important
    - Important

This guide explains how to securely access a Snowflake database from Streamlit. It uses st.connection, the Snowpark library, and Streamlit's Secrets management.

The following packages must be installed in your Python environment:

Use the correct version of Python required by snowflake-snowpark-python. For example, if you use snowflake-snowpark-python==1.23.0, you must use Python version >=3.8, <3.12.

You must have a Snowflake account. To create a trial account, see the tutorial in Get started.

You should have a basic understanding of st.connection and Secrets management.

If you already have a database that you want to use, you can skip to the next step.

Sign in to your Snowflake account at https://app.snowflake.com.

In the left navigation, select "Projects," and then select "Worksheets."

To create a new worksheet, in the upper-right corner, click the plus icon (add).

You can use a worksheet to quickly and conveniently execute SQL statements. This is a great way to learn about and experiment with SQL in a trial account.

Optional: To rename your worksheet, in the upper-left corner, hover over the tab with your worksheet name, and then click the overflow menu icon (more_vert). Select "Rename", enter a new worksheet name (e.g. "Scratchwork"), and then press "Enter".

To create a new database with a table, in your worksheet's SQL editor, type and execute the following SQL statements:

To execute the statements in a worksheet, select all the lines you want to execute by highlighting them with your mouse. Then, in the upper-right corner, click the play button (play_arrow). Alternatively, if you want to execute everything in a worksheet, click the down arrow (expand_more) next to the play button, and select "Run All".

If no lines are highlighted and you click the play button, only the line with your cursor will be executed.

Optional: To view your new database, above the left navigation, select "Databases." Click the down arrows (expand_more) to expand "PETS" → "PUBLIC" → "Tables" → "MYTABLE."

For your use in later steps, note down your role, warehouse, database, and schema. In the preceding screenshot, these are the following:

Because the SQL statements did not specify a schema, they defaulted to the "PUBLIC" schema within the new "PETS" database. The role and warehouse are trial-account defaults. You can see the role and warehouse used by your worksheet in the upper-right corner, to the left of the "Share" and play (play_arrow) buttons.

In Snowflak

*[Content truncated]*

---

## Use the Google Auth Platform to authenticate users - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/authentication/google

**Contents:**
- Use the Google Auth Platform to authenticate users
- Prerequisites
- Summary
- Create a web application in Google Cloud Console
  - Configure your consent screen
  - Configure your audience
  - Configure your client
  - Gather your application's details
- Build the example
  - Configure your secrets

Google is one of the most popular identity providers for social logins. You can use the Google Auth Platform with both private and organizational Google accounts. This tutorial configures authentication for anyone with a Google account. For more information, see Google's overview of the Google Auth Platform and OpenID Connect.

This tutorial requires the following Python libraries:

You should have a clean working directory called your-repository.

You must have a Google account and accept the terms of Google Cloud to use their authentication service.

You must have a project in Google Cloud within which to create your application. For more information about managing your projects in Google Cloud, see Creating and managing projects in Google's documentation.

In this tutorial, you'll build an app that users can log in to with their Google accounts. When they log in, they'll see a personalized greeting with their name and have the option to log out.

Here's a look at what you'll build:

.streamlit/secrets.toml

In this section, you'll complete three steps to create your web application in your project in Google Cloud Console:

The consent screen is what users see from Google within the authentication flow. The audience settings manage your application's status (Testing or Published). Creating a client for your web application generates the ID and secrets needed to configure your Streamlit app. To learn more about consent screens, audience, and clients, see Google's overview of the Google Auth Platform.

Go to the Google Auth Platform, and sign in to Google.

In the upper-left corner, select your project.

In the left navigation menu, select "Branding."

Fill in the required information for your application's consent screen.

This information controls what users see within the Google authentication flow. Your "App name" is displayed to users within Google's prompts. Google asks users to consent to sending their account information to your application. If you are developing locally and/or deploying on Streamlit Community Cloud, in "Authorized domain," use example.com. For more information about the available fields, see Setting up your OAuth consent screen.

At the bottom of the branding page, select "SAVE."

In the left navigation menu, select "Audience."

Below "OAuth user cap" → "Test users," select "ADD USERS."

Enter the email address for a personal Google account, and select "SAVE."

When you create a new application in the Google Auth Platform, its sta

*[Content truncated]*

---

## Use externally hosted fonts and fallbacks to customize your font (streamlit<1.50.0) - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/configuration-and-theming/external-fonts-old

**Contents:**
- Use externally hosted fonts and fallbacks to customize your font (streamlit<1.50.0)
    - Note
- Prerequisites
- Summary
- Collect your font file URLs
- Create your app configuration
- Build the example
  - Initialize your app
  - Display some text in your app
  - Still have questions?

A simpler method for using externally hosted fonts was introduced in Streamlit version 1.50.0. For a newer version of this tutorial, see Use externally hosted fonts and fallbacks to customize your font.

Streamlit comes with Source Sans as the default font, but you can configure your app to use another font. This tutorial uses variable font files and is a walkthrough of Example 3 from Customize fonts in your Streamlit app. For an example that uses self-hosted variable font files, see Use variable font files to customize your font. For an example that uses self-hosted static font files, see Use static font files to customize your font.

This tutorial requires the following version of Streamlit:

You should have a clean working directory called your-repository.

You should have a basic understanding of working with font files in web development. Otherwise, start by reading Customize fonts in your Streamlit app up to Example 3.

The following example uses a Google-hosted instances of Nunito and Space Mono. Nunito is defined in variable font files. However, because font style is not parameterized, Nunito requires two files to define the normal and italic styles separately. Space Mono is defined in static font files.

Here's a look at what you'll build:

.streamlit/config.toml:

Search for or follow the link to Nunito, and select "Get font."

Search for or follow the link to Space Mono, and select "Get font."

To get a link to a style sheet for your font files, in the upper-right corner, select the shopping bag (shopping_bag), and then select "code Get embed code."

On the right, in the first code block, copy the href URL from the third link, and paste it into a new tab.

By default, the "Embed Code" page loads with the "Web" tab and "<link>" radio option selected. The first code block is titled, "Embed code in the <head> of your html." The URL is a link to a style sheet and should look like the following text:

Go to your new tab and visit the URL.

This page is a style sheet. It is filled with font-face declarations that look like the following text:

Each font-face declaration starts with a comment to indication which character set is included in that declaration. For most English apps, only the /* latin */ declarations are needed.

To store the portion of the style sheet you'll need in later steps, copy the font-face declarations that are prefixed with the /* latin */ comment, and paste them into a text file.

In your_repository/, create a .streamlit/config

*[Content truncated]*

---

## Build an LLM app using LangChain - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/chat-and-llm-apps/llm-quickstart

**Contents:**
- Build an LLM app using LangChain
- OpenAI, LangChain, and Streamlit in 18 lines of code
- Objectives
- Prerequisites
- Setup coding environment
- Building the app
- Deploying the app
- Conclusion
  - Still have questions?

In this tutorial, you will build a Streamlit LLM app that can generate text from a user-provided prompt. This Python app will use the LangChain framework and Streamlit. Optionally, you can deploy your app to Streamlit Community Cloud when you're done.

This tutorial is adapted from a blog post by Chanin Nantesanamat: LangChain tutorial #1: Build an LLM-powered app in 18 lines of code.

Bonus: Deploy the app on Streamlit Community Cloud!

In your IDE (integrated coding environment), open the terminal and install the following two Python libraries:

Create a requirements.txt file located in the root of your working directory and save these dependencies. This is necessary for deploying the app to the Streamlit Community Cloud later.

The app is only 18 lines of code:

To start, create a new Python file and save it as streamlit_app.py in the root of your working directory.

Import the necessary Python libraries.

Create the app's title using st.title.

Add a text input box for the user to enter their OpenAI API key.

Define a function to authenticate to OpenAI API with the user's key, send a prompt, and get an AI-generated response. This function accepts the user's prompt as an argument and displays the AI-generated response in a blue box using st.info.

Finally, use st.form() to create a text box (st.text_area()) for user input. When the user clicks Submit, the generate-response() function is called with the user's input as an argument.

Remember to save your file!

Return to your computer's terminal to run the app.

To deploy the app to the Streamlit Cloud, follow these steps:

Create a GitHub repository for the app. Your repository should contain two files:

Go to Streamlit Community Cloud, click the New app button from your workspace, then specify the repository, branch, and main file path. Optionally, you can customize your app's URL by choosing a custom subdomain.

Click the Deploy! button.

Your app will now be deployed to Streamlit Community Cloud and can be accessed from around the world! 🌎

Congratulations on building an LLM-powered Streamlit app in 18 lines of code! 🥳 You can use this app to generate text from any prompt that you provide. The app is limited by the capabilities of the OpenAI LLM, but it can still be used to generate some creative and interesting text.

We hope you found this tutorial helpful! Check out more examples to see the power of Streamlit and LLM. 💖

Happy Streamlit-ing! 🎈

Our forums are full of helpful information and Stream

*[Content truncated]*

---

## Use variable font files to customize your font - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/configuration-and-theming/variable-fonts

**Contents:**
- Use variable font files to customize your font
- Prerequisites
- Summary
- Download and save your font files
- Create your app configuration
    - Tip
- Build the example
  - Initialize your app
  - Display some text in your app
  - Still have questions?

Streamlit comes with Source Sans as the default font, but you can configure your app to use another font. This tutorial uses variable font files and is a walkthrough of Example 1 from Customize fonts in your Streamlit app. For an example that uses static font files, see Use static font files to customize your font.

This tutorial requires the following version of Streamlit:

You should have a clean working directory called your-repository.

You should have a basic understanding of static file serving.

You should have a basic understanding of working with font files in web development. Otherwise, start by reading Customize fonts in your Streamlit app up to Example 1.

The following example uses static file serving to host Google's Noto Sans and Noto Sans Mono fonts and configures the app to use them. Both of these fonts are defined with variable font files that include a parameterized weight. However, because font style is not parameterized, Noto Sans requires two files to define the normal and italic styles separately. Noto Sans Mono does not include a separate file for its italic style. Per CSS rules, because no italic style is explicitly provided, it will be simulated by skewing the normal-style font.

Here's a look at what you'll build:

.streamlit/config.toml:

Search for or follow the link to Noto Sans, and select "Get font."

Search for or follow the link to Noto Sans Mono, and select "Get font."

To download your font files, in the upper-right corner, select the shopping bag (shopping_bag), and then select "download Download all."

In your downloads directory, unzip the downloaded file.

From the unzipped files, copy and save the TTF font files into a static/ directory in your_repository/.

Copy the following files:

Save those files in your repository:

In this example, the font files are NotoSans-Italic-VariableFont_wdth,wght.ttf and NotoSansMono-VariableFont_wdth,wght.ttf for Noto Sans italic and normal font, respectively. NotoSansMono-VariableFont_wdth,wght.ttf is the file for Noto Sans Mono.

In your_repository/, create a .streamlit/config.toml file:

To enable static file serving, in .streamlit/config.toml, add the following text:

This makes the files in your static/ directory publicly available through your app's URL at the relative path app/static/{filename}.

To define your alternative fonts, in .streamlit/config.toml, add the following text:

The [[theme.fontFaces]] table can be repeated to use multiple files to define a single font or t

*[Content truncated]*

---

## Use core features to work with Streamlit's execution model - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/execution-flow

**Contents:**
- Use core features to work with Streamlit's execution model
- Fragments
      - Trigger a full-script rerun from inside a fragment
      - Create a fragment across multiple containers
      - Start and stop a streaming fragment
  - Still have questions?

Call st.rerun from inside a fragment to trigger a full-script rerun when a condition is met.

Use a fragment to write to multiple containers across your app.

Use a fragment to live-stream data. Use a button to start and stop the live-streaming.

Our forums are full of helpful information and Streamlit experts.

---

## Deploy Streamlit using Docker - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/tutorials/docker

**Contents:**
- Deploy Streamlit using Docker
- Introduction
- Prerequisites
  - Install Docker Engine
    - Tip
  - Check network port accessibility
- Create a Dockerfile
  - Dockerfile walkthrough
    - Tip
    - Important

So you have an amazing app and you want to start sharing it with other people, what do you do? You have a few options. First, where do you want to run your Streamlit app, and how do you want to access it?

Wherever you decide to deploy your app, you will first need to containerize it. This guide walks you through using Docker to deploy your app. If you prefer Kubernetes see Deploy Streamlit using Kubernetes.

If you haven't already done so, install Docker on your server. Docker provides .deb and .rpm packages from many Linux distributions, including:

Verify that Docker Engine is installed correctly by running the hello-world Docker image:

Follow Docker's official post-installation steps for Linux to run Docker as a non-root user, so that you don't have to preface the docker command with sudo.

As you and your users are behind your corporate VPN, you need to make sure all of you can access a certain network port. Let's say port 8501, as it is the default port used by Streamlit. Contact your IT team and request access to port 8501 for you and your users.

Docker builds images by reading the instructions from a Dockerfile. A Dockerfile is a text document that contains all the commands a user could call on the command line to assemble an image. Learn more in the Dockerfile reference. The docker build command builds an image from a Dockerfile. The docker run command first creates a container over the specified image, and then starts it using the specified command.

Here's an example Dockerfile that you can add to the root of your directory. i.e. in /app/

Let’s walk through each line of the Dockerfile :

A Dockerfile must start with a FROM instruction. It sets the Base Image (think OS) for the container:

Docker has a number of official Docker base images based on various Linux distributions. They also have base images that come with language-specific modules such as Python. The python images come in many flavors, each designed for a specific use case. Here, we use the python:3.9-slim image which is a lightweight image that comes with the latest version of Python 3.9.

You can also use your own base image, provided the image you use contains a supported version of Python for Streamlit. There is no one-size-fits-all approach to using any specific base image, nor is there an official Streamlit-specific base image.

The WORKDIR instruction sets the working directory for any RUN, CMD, ENTRYPOINT, COPY and ADD instructions that follow it in the Dockerfile . Let’s 

*[Content truncated]*

---

## Start and stop a streaming fragment - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/execution-flow/start-and-stop-fragment-auto-reruns

**Contents:**
- Start and stop a streaming fragment
- Applied concepts
- Prerequisites
- Summary
- Build the example
  - Initialize your app
  - Build a function to generate random, recent data
  - Initialize Session State values for your app
  - Build a fragment function to stream data
  - Call and test out your fragment function

Streamlit lets you turn functions into fragments, which can rerun independently from the full script. Additionally, you can tell Streamlit to rerun a fragment at a set time interval. This is great for streaming data or monitoring processes. You may want the user to start and stop this live streaming. To do this, programmatically set the run_every parameter for your fragment.

This tutorial requires the following version of Streamlit:

You should have a clean working directory called your-repository.

You should have a basic understanding of fragments.

In this example, you'll build an app that streams two data series in a line chart. Your app will gather recent data on the first load of a session and statically display the line chart. Two buttons in the sidebar will allow users to start and stop data streaming to update the chart in real time. You'll use a fragment to manage the frequency and scope of the live updates.

Here's a look at what you'll build:

In your_repository, create a file named app.py.

In a terminal, change directories to your_repository, and start your app:

Your app will be blank because you still need to add code.

In app.py, write the following:

You'll be using these libraries as follows:

Save your app.py file, and view your running app.

In your app, select "Always rerun", or press the "A" key.

Your preview will be blank but will automatically update as you save changes to app.py.

To begin with, you'll define a function to randomly generate some data for two time series, which you'll call "A" and "B." It's okay to skip this section if you just want to copy the function.

Start your function definition.

You'll pass the timestamp of your most recent datapoint to your data-generating function. Your function will use this to only return new data.

Get the current time and adjust the last timestamp if it is over 60 seconds ago.

By updating the last timestamp, you'll ensure the function never returns more than 60 seconds of data.

Declare a new variable, sample_time, to define the time between datapoints. Calculate the timestamp of the first, new datapoint.

Create a datetime.datetime index and generate two data series of the same length.

Combine the data series with the index into a pandas.DataFrame and return the data.

Optional: Test out your function by calling it and displaying the data.

Save your app.py file to see the preview. Delete these two lines when finished.

Since you will dynamically change the run_every parameter o

*[Content truncated]*

---

## Get dataframe row-selections from users - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/elements/dataframe-row-selections

**Contents:**
- Get dataframe row-selections from users
- Applied concepts
- Prerequisites
- Summary
- Build the example
  - Initialize your app
  - Build a function to create random member data
  - Display your data with multi-row selections enabled
  - Display the selected data
  - Combine activity data for the selected rows

Streamlit offers two commands for rendering beautiful, interactive dataframes in your app. If you need users to edit data, add rows, or delete rows, use st.data_editor. If you don't want users to change the data in your dataframe, use st.dataframe. Users can sort and search through data rendered with st.dataframe. Additionally, you can activate selections to work with users' row and column selections.

This tutorial uses row selections, which were introduced in Streamlit version 1.35.0. For an older workaround using st.data_editor, see Get dataframe row-selections (streamlit<1.35.0).

This tutorial requires the following version of Streamlit:

You should have a clean working directory called your-repository.

You should have a basic understanding of caching and st.dataframe.

In this example, you'll build an app that displays a table of members and their activity for an imaginary organization. Within the table, a user can select one or more rows to create a filtered view. Your app will show a combined chart that compares the selected employees.

Here's a look at what you'll build:

In your_repository, create a file named app.py.

In a terminal, change directories to your_repository, and start your app:

Your app will be blank because you still need to add code.

In app.py, write the following:

You'll be using these libraries as follows:

Save your app.py file, and view your running app.

In your app, select "Always rerun", or press the "A" key.

Your preview will be blank but will automatically update as you save changes to app.py.

To begin with, you'll define a function to randomly generate some member data. It's okay to skip this section if you just want to copy the function.

Use an @st.cache_data decorator and start your function definition.

The @st.cache_data decorator turns get_profile_dataset() into a cached function. Streamlit saves the output of a cached function to reuse when the cached function is called again with the same inputs. This keeps your app performant when rerunning as part of Streamlit's execution model. For more information, see Caching.

The get_profile_dataset function has two parameters to configure the size of the data set and the seed for random generation. This example will use the default values (20 members in the set with a seed of 0). The function will return a pandas.DataFrame.

Initialize an empty list to store data.

Initialize the random generators.

Iterate through a range to generate new member data as a dictionary

*[Content truncated]*

---

## Connect Streamlit to a public Google Sheet - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/databases/public-gsheet

**Contents:**
- Connect Streamlit to a public Google Sheet
- Introduction
  - Prerequisites
- Create a Google Sheet and turn on link sharing
- Add the Sheets URL to your local app secrets
    - Important
- Write your Streamlit app
- Connecting to a Google Sheet from Community Cloud
  - Still have questions?

This guide explains how to securely access a public Google Sheet from Streamlit. It uses st.connection, Streamlit GSheetsConnection, and Streamlit's Secrets management.

This method requires you to enable link sharing for your Google Sheet. While the sharing link will not appear in your code (and actually acts as sort of a password!), someone with the link can get all the data in the Sheet. If you don't want this, follow the (more complicated) guide to Connect Streamlit to a private Google Sheet.

This tutorial requires streamlit>=1.28 and st-gsheets-connection in your Python environment.

If you already have a Sheet that you want to access, you can skip to the next step. See Google's documentation on how to share spreadsheets for more information.

Create a spreadsheet with this example data and create a share link. The link should have "Anyone with the link" set as a "Viewer."

Your local Streamlit app will read secrets from a file .streamlit/secrets.toml in your app's root directory. Create this file if it doesn't exist yet and add the share link of your Google Sheet to it as shown below:

Add this file to .gitignore and don't commit it to your GitHub repo!

Copy the code below to your Streamlit app and run it.

See st.connection above? This handles secrets retrieval, setup, query caching and retries. By default, .read() results are cached without expiring. You can pass optional parameters to .read() to customize your connection. For example, you can specify the name of a worksheet, cache expiration time, or pass-through parameters for pandas.read_csv like this:

In this case, we set ttl="10m" to ensure the query result is cached for no longer than 10 minutes. You can also set ttl=0 to disable caching. Learn more in Caching. We've declared optional parameters usecols=[0,1] and nrows=3 for pandas to use under the hood.

If everything worked out (and you used the example table we created above), your app should look like this:

This tutorial assumes a local Streamlit app, however you can also connect to Google Sheets from apps hosted in Community Cloud. The main additional steps are:

Our forums are full of helpful information and Streamlit experts.

---

## Customize your theme and configure your app - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/configuration-and-theming

**Contents:**
- Customize your theme and configure your app
      - Use external font files and fallbacks to customize your font
      - Use static font files to customize your font
      - Use variable font files to customize your font
  - Still have questions?

Make a new font available to your app. This tutorial uses externally hosted font files to define an alternative font and declares a built-in fallback.

Make a new font available to your app. This tutorial uses static font files to define an alternative font.

Make a new font available to your app. This tutorial uses variable font files to define an alternative font.

Our forums are full of helpful information and Streamlit experts.

---

## Connect Streamlit to MongoDB - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/databases/mongodb

**Contents:**
- Connect Streamlit to MongoDB
- Introduction
- Create a MongoDB Database
    - Note
- Add username and password to your local app secrets
    - Important
- Copy your app secrets to the cloud
- Add PyMongo to your requirements file
- Write your Streamlit app
  - Still have questions?

This guide explains how to securely access a remote MongoDB database from Streamlit Community Cloud. It uses the PyMongo library and Streamlit's Secrets management.

If you already have a database that you want to use, feel free to skip to the next step.

First, follow the official tutorials to install MongoDB, set up authentication (note down the username and password!), and connect to the MongoDB instance. Once you are connected, open the mongo shell and enter the following two commands to create a collection with some example values:

Your local Streamlit app will read secrets from a file .streamlit/secrets.toml in your app's root directory. Create this file if it doesn't exist yet and add the database information as shown below:

When copying your app secrets to Streamlit Community Cloud, be sure to replace the values of host, port, username, and password with those of your remote MongoDB database!

Add this file to .gitignore and don't commit it to your GitHub repo!

As the secrets.toml file above is not committed to GitHub, you need to pass its content to your deployed app (on Streamlit Community Cloud) separately. Go to the app dashboard and in the app's dropdown menu, click on Edit Secrets. Copy the content of secrets.toml into the text area. More information is available at Secrets management.

Add the PyMongo package to your requirements.txt file, preferably pinning its version (replace x.x.x with the version you want installed):

Copy the code below to your Streamlit app and run it. Make sure to adapt the name of your database and collection.

See st.cache_data above? Without it, Streamlit would run the query every time the app reruns (e.g. on a widget interaction). With st.cache_data, it only runs when the query changes or after 10 minutes (that's what ttl is for). Watch out: If your database updates more frequently, you should adapt ttl or remove caching so viewers always see the latest data. Learn more in Caching.

If everything worked out (and you used the example data we created above), your app should look like this:

Our forums are full of helpful information and Streamlit experts.

---

## Create a dynamic navigation menu - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/multipage/dynamic-navigation

**Contents:**
- Create a dynamic navigation menu
- Applied concepts
- Prerequisites
- Summary
- Build the example
  - Initialize your app
  - Add your page and image files
  - Initialize global values
  - Define your user authentication pages
  - Define all your pages

st.navigation makes it easy to build dynamic navigation menus. You can change the set of pages passed to st.navigation with each rerun, which changes the navigation menu to match. This is a convenient feature for creating custom, role-based navigation menus.

This tutorial uses st.navigation and st.Page, which were introduced in Streamlit version 1.36.0. For an older workaround using the pages/ directory and st.page_link, see Build a custom navigation menu with st.page_link.

This tutorial requires the following version of Streamlit:

You should have a clean working directory called your-repository.

You should have a basic understanding of st.navigation and st.Page.

In this example, we'll build a dynamic navigation menu for a multipage app that depends on the current user's role. You'll abstract away the use of username and credentials to simplify the example. Instead, you'll use a selectbox to let users choose a role and log in.

The entrypoint file, streamlit_app.py will handle user authentication. The other pages will be stubs representing account management (settings.py) and specific pages associated to three roles: Requester, Responder, and Admin. Requesters can access the account and request pages. Responders can access the account and respond pages. Admins can access all pages.

Here's a look at what we'll build:

In your_repository, create a file named streamlit_app.py.

In a terminal, change directories to your_repository, and start your app:

Your app will be blank because you still need to add code.

In streamlit_app.py, write the following:

Save your streamlit_app.py file, and view your running app.

In your app, select "Always rerun", or press the "A" key.

Your preview will be blank but will automatically update as you save changes to streamlit_app.py.

In your_repositoy, create a file named settings.py.

In settings.py add the following stub.

In later steps, you'll create an authentication method that saves the current user's role to st.session_state.role. Since you'll be blocking access to this page until a user is logged in, you don't need to initialize the "role" key in Session State for this page.

Create similar stubs by changing the value of st.header for the following six pages:

For example, admin/admin_1.py should be the following:

Create an images subdirectory in your-repository and add the following two files:

You now have all the files needed to build your app.

Return to streamlit_app.py and initialize "role" in Session St

*[Content truncated]*

---

## Collect user feedback about LLM responses - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/chat-and-llm-apps/chat-response-feedback

**Contents:**
- Collect user feedback about LLM responses
- Applied concepts
- Prerequisites
- Summary
- Build the example
  - Initialize your app
  - Build a function to simulate a chat response stream
  - Initialize and render your chat history
  - Add chat input
  - Optional: Change the feedback behavior

A common task in a chat app is to collect user feedback about an LLM's responses. Streamlit includes st.feedback to conveniently collect user sentiment by displaying a group of selectable sentiment icons.

This tutorial uses Streamlit's chat commands and st.feedback to build a simple chat app that collects user feedback about each response.

This tutorial requires the following version of Streamlit:

You should have a clean working directory called your-repository.

You should have a basic understanding of Session State.

In this example, you'll build a chat interface. To avoid API calls, the chat app will echo the user's prompt within a fixed response. Each chat response will be followed by a feedback widget where the user can vote "thumb up" or "thumb down." In the following code, a user can't change their feedback after it's given. If you want to let users change their rating, see the optional instructions at the end of this tutorial.

Here's a look at what you'll build:

In your_repository, create a file named app.py.

In a terminal, change directories to your_repository, and start your app:

Your app will be blank because you still need to add code.

In app.py, write the following:

You'll use time to build a simulated chat response stream.

Save your app.py file, and view your running app.

In your app, select "Always rerun", or press the "A" key.

Your preview will be blank but will automatically update as you save changes to app.py.

To begin, you'll define a function to stream a fixed chat response. You can skip this section if you just want to copy the function.

Define a function which accepts a prompt and formulates a response:

Loop through the characters and yield each one at 0.02-second intervals:

You now have a complete generator function to simulate a chat stream object.

To make your chat app stateful, you'll save the conversation history into Session State as a list of messages. Each message is a dictionary of message attributes. The dictionary keys include the following:

Initialize the chat history in Session State:

Iterate through the messages in your chat history and render their contents in chat message containers:

In a later step, you'll need a unique key for each assistant message. You can use the index of the message in your chat history to create a unique key. Therefore, use enumerate() to get an index along with each message dictionary.

For each assistant message, check whether feedback has been saved:

If no feedback is sa

*[Content truncated]*

---

## Connect Streamlit to TiDB - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/databases/tidb

**Contents:**
- Connect Streamlit to TiDB
- Introduction
- Sign in to TiDB Cloud and create a cluster
    - Important
- Create a TiDB database
    - Note
- Add username and password to your local app secrets
    - Important
- Copy your app secrets to the cloud
- Add dependencies to your requirements file

This guide explains how to securely access a remote TiDB database from Streamlit Community Cloud. It uses st.connection and Streamlit's Secrets management. The below example code will only work on Streamlit version >= 1.28, when st.connection was added.

TiDB is an open-source, MySQL-compatible database that supports Hybrid Transactional and Analytical Processing (HTAP) workloads. TiDB introducs a built-in vector search to the SQL database family, enabling support for your AI applications without requiring a new database or additional technical stacks. TiDB Cloud is a fully managed cloud database service that simplifies the deployment and management of TiDB databases for developers.

First, head over to TiDB Cloud and sign up for a free account, using either Google, GitHub, Microsoft or E-mail:

Once you've signed in, you will already have a TiDB cluster:

You can create more clusters if you want to. Click the cluster name to enter cluster overview page:

Then click Connect to easily get the connection arguments to access the cluster. On the popup, click Generate Password to set the password.

Make sure to note down the password. It won't be available on TiDB Cloud after this step.

If you already have a database that you want to use, feel free to skip to the next step.

Once your TiDB cluster is up and running, connect to it with the mysql client(or with SQL Editor tab on the console) and enter the following commands to create a database and a table with some example values:

Your local Streamlit app will read secrets from a file .streamlit/secrets.toml in your app's root directory. Learn more about Streamlit secrets management here. Create this file if it doesn't exist yet and add host, username and password of your TiDB cluster as shown below:

When copying your app secrets to Streamlit Community Cloud, be sure to replace the values of host, username and password with those of your remote TiDB cluster!

Add this file to .gitignore and don't commit it to your GitHub repo!

As the secrets.toml file above is not committed to GitHub, you need to pass its content to your deployed app (on Streamlit Community Cloud) separately. Go to the app dashboard and in the app's dropdown menu, click on Edit Secrets. Copy the content of secrets.toml into the text area. More information is available at Secrets management.

Add the mysqlclient and SQLAlchemy packages to your requirements.txt file, preferably pinning its version (replace x.x.x with the version you want insta

*[Content truncated]*

---

## Build a custom navigation menu with `st.page_link` - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/multipage/st.page_link-nav

**Contents:**
- Build a custom navigation menu with st.page_link
- Prerequisites
- Summary
- Build the example
  - Hide the default sidebar navigation
  - Create a menu function
    - Tip
  - Create the main file of your app
  - Add other pages to your app
  - Still have questions?

Streamlit lets you build custom navigation menus and elements with st.page_link. Introduced in Streamlit version 1.31.0, st.page_link can link to other pages in your multipage app or to external sites. When linked to another page in your app, st.page_link will show a highlight effect to indicate the current page. When combined with the client.showSidebarNavigation configuration option, you can build sleek, dynamic navigation in your app.

Create a new working directory in your development environment. We'll call this directory your-repository.

In this example, we'll build a dynamic navigation menu for a multipage app that depends on the current user's role. We've abstracted away the use of username and creditials to simplify the example. Instead, we'll use a selectbox on the main page of the app to switch between roles. Session State will carry this selection between pages. The app will have a main page (app.py) which serves as the abstracted log-in page. There will be three additional pages which will be hidden or accessible, depending on the current role. The file structure will be as follows:

Here's a look at what we'll build:

When creating a custom navigation menu, you need to hide the default sidebar navigation using client.showSidebarNavigation. Add the following .streamlit/config.toml file to your working directory:

You can write different menu logic for different pages or you can create a single menu function to call on multiple pages. In this example, we'll use the same menu logic on all pages, including a redirect to the main page when a user isn't logged in. We'll build a few helper functions to do this.

We'll call menu() on the main page and call menu_with_redirect() on the other pages. st.session_state.role will store the current selected role. If this value does not exist or is set to None, then the user is not logged in. Otherwise, it will hold the user's role as a string: "user", "admin", or "super-admin".

Add the following menu.py file to your working directory. (We'll describe the functions in more detail below.)

Let's take a closer look at authenticated_menu(). When this function is called, st.session_state.role exists and has a value other than None.

The first two pages in the navigation menu are available to all users. Since we know a user is logged in when this function is called, we'll use the label "Switch accounts" for the main page. (If you don't use the label parameter, the page name will be derived from the file name lik

*[Content truncated]*

---

## Tutorials - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials

**Contents:**
- Tutorials
      - Add user authentication
      - Chat apps and LLMs
      - Configuration and theming
      - Connect to data sources
      - Work with Streamlit's core elements
      - Use core features to work with Streamlit's execution model
      - Create multipage apps
  - Still have questions?

Our tutorials include step-by-step examples of building different types of apps in Streamlit.

Add user authentication with Streamlit's built-in support for OpenID Connect.

Work with LLMs and create chat apps.

Customize the appearance of your app.

Connect to popular datasources.

Work with core elements like dataframes and charts.

Build simple apps and walk through examples to learn about Streamlit's core features and execution model.

Create multipage apps, navigation, and flows.

When you're done developing your app, see our deployment tutorials, too!

Our forums are full of helpful information and Streamlit experts.

---

## Connect Streamlit to Google BigQuery - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/databases/bigquery

**Contents:**
- Connect Streamlit to Google BigQuery
- Introduction
- Create a BigQuery database
    - Note
- Enable the BigQuery API
- Create a service account & key file
    - Note
- Add the key file to your local app secrets
    - Important
- Copy your app secrets to the cloud

This guide explains how to securely access a BigQuery database from Streamlit Community Cloud. It uses the google-cloud-bigquery library and Streamlit's Secrets management.

If you already have a database that you want to use, feel free to skip to the next step.

For this example, we will use one of the sample datasets from BigQuery (namely the shakespeare table). If you want to create a new dataset instead, follow Google's quickstart guide.

Programmatic access to BigQuery is controlled through Google Cloud Platform. Create an account or sign in and head over to the APIs & Services dashboard (select or create a project if asked). As shown below, search for the BigQuery API and enable it:

To use the BigQuery API from Streamlit Community Cloud, you need a Google Cloud Platform service account (a special account type for programmatic data access). Go to the Service Accounts page and create an account with the Viewer permission (this will let the account access data but not change it):

If the button CREATE SERVICE ACCOUNT is gray, you don't have the correct permissions. Ask the admin of your Google Cloud project for help.

After clicking DONE, you should be back on the service accounts overview. Create a JSON key file for the new account and download it:

Your local Streamlit app will read secrets from a file .streamlit/secrets.toml in your app's root directory. Create this file if it doesn't exist yet and add the content of the key file you just downloaded to it as shown below:

Add this file to .gitignore and don't commit it to your GitHub repo!

As the secrets.toml file above is not committed to GitHub, you need to pass its content to your deployed app (on Streamlit Community Cloud) separately. Go to the app dashboard and in the app's dropdown menu, click on Edit Secrets. Copy the content of secrets.toml into the text area. More information is available at Secrets management.

Add the google-cloud-bigquery package to your requirements.txt file, preferably pinning its version (replace x.x.x with the version want installed):

Copy the code below to your Streamlit app and run it. Make sure to adapt the query if you don't use the sample table.

See st.cache_data above? Without it, Streamlit would run the query every time the app reruns (e.g. on a widget interaction). With st.cache_data, it only runs when the query changes or after 10 minutes (that's what ttl is for). Watch out: If your database updates more frequently, you should adapt ttl or remove caching 

*[Content truncated]*

---

## Build an LLM app using LangChain - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/llms/llm-quickstart

**Contents:**
- Build an LLM app using LangChain
- OpenAI, LangChain, and Streamlit in 18 lines of code
- Objectives
- Prerequisites
- Setup coding environment
- Building the app
- Deploying the app
- Conclusion
  - Still have questions?

In this tutorial, you will build a Streamlit LLM app that can generate text from a user-provided prompt. This Python app will use the LangChain framework and Streamlit. Optionally, you can deploy your app to Streamlit Community Cloud when you're done.

This tutorial is adapted from a blog post by Chanin Nantesanamat: LangChain tutorial #1: Build an LLM-powered app in 18 lines of code.

Bonus: Deploy the app on Streamlit Community Cloud!

In your IDE (integrated coding environment), open the terminal and install the following two Python libraries:

Create a requirements.txt file located in the root of your working directory and save these dependencies. This is necessary for deploying the app to the Streamlit Community Cloud later.

The app is only 18 lines of code:

To start, create a new Python file and save it as streamlit_app.py in the root of your working directory.

Import the necessary Python libraries.

Create the app's title using st.title.

Add a text input box for the user to enter their OpenAI API key.

Define a function to authenticate to OpenAI API with the user's key, send a prompt, and get an AI-generated response. This function accepts the user's prompt as an argument and displays the AI-generated response in a blue box using st.info.

Finally, use st.form() to create a text box (st.text_area()) for user input. When the user clicks Submit, the generate-response() function is called with the user's input as an argument.

Remember to save your file!

Return to your computer's terminal to run the app.

To deploy the app to the Streamlit Cloud, follow these steps:

Create a GitHub repository for the app. Your repository should contain two files:

Go to Streamlit Community Cloud, click the New app button from your workspace, then specify the repository, branch, and main file path. Optionally, you can customize your app's URL by choosing a custom subdomain.

Click the Deploy! button.

Your app will now be deployed to Streamlit Community Cloud and can be accessed from around the world! 🌎

Congratulations on building an LLM-powered Streamlit app in 18 lines of code! 🥳 You can use this app to generate text from any prompt that you provide. The app is limited by the capabilities of the OpenAI LLM, but it can still be used to generate some creative and interesting text.

We hope you found this tutorial helpful! Check out more examples to see the power of Streamlit and LLM. 💖

Happy Streamlit-ing! 🎈

Our forums are full of helpful information and Stream

*[Content truncated]*

---

## Use static font files to customize your font - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/configuration-and-theming/static-fonts

**Contents:**
- Use static font files to customize your font
- Prerequisites
- Summary
- Download and save your font files
- Create your app configuration
    - Tip
- Build the example
  - Initialize your app
  - Display some text in your app
  - Still have questions?

Streamlit comes with Source Sans as the default font, but you can configure your app to use another font. This tutorial uses static font files and is a walkthrough of Example 2 from Customize fonts in your Streamlit app. For an example that uses variable font files, see Use variable font files to customize your font.

This tutorial requires the following version of Streamlit:

You should have a clean working directory called your-repository.

You should have a basic understanding of static file serving.

You should have a basic understanding of working with font files in web development. Otherwise, start by reading Customize fonts in your Streamlit app up to Example 2.

The following example uses Tuffy font. The font has four static font files which cover the four following weight-style pairs:

Here's a look at what you'll build:

.streamlit/config.toml:

Search for or follow the link to Tuffy, and select "Get font."

To download your font files, in the upper-right corner, select the shopping bag (shopping_bag), and then select "download Download all."

In your downloads directory, unzip the downloaded file.

From the unzipped files, copy and save the TTF font files into a static/ directory in your_repository/.

Copy the following files:

Save those files in your repository:

In your_repository/, create a .streamlit/config.toml file:

To enable static file serving, in .streamlit/config.toml, add the following text:

This makes the files in your static/ directory publicly available through your app's URL at the relative path app/static/{filename}.

To define your alternative fonts, in .streamlit/config.toml, add the following text:

The [[theme.fontFaces]] table can be repeated to use multiple files to define a single font or to define multiple fonts. In this example, the definitions make "tuffy" available to other font configuration options.

For convenience, avoid spaces in your font family names. When you declare the default font, you can also declare fallback fonts. If you avoid spaces in your font family names, you don't need inner quotes.

To set your alternative fonts as the default font for your app, in .streamlit/config.toml, add the following text:

This sets Tuffy as the default for all text in your app except inline code and code blocks.

To verify that your font is loaded correctly, create a simple app.

In your_repository, create a file named streamlit_app.py.

In a terminal, change directories to your_repository, and start your app:

Your app

*[Content truncated]*

---

## Connect Streamlit to MySQL - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/databases/mysql

**Contents:**
- Connect Streamlit to MySQL
- Introduction
- Create a MySQL database
    - Note
- Add username and password to your local app secrets
    - Important
- Copy your app secrets to the cloud
- Add dependencies to your requirements file
- Write your Streamlit app
  - Still have questions?

This guide explains how to securely access a remote MySQL database from Streamlit Community Cloud. It uses st.connection and Streamlit's Secrets management. The below example code will only work on Streamlit version >= 1.28, when st.connection was added.

If you already have a database that you want to use, feel free to skip to the next step.

First, follow this tutorial to install MySQL and start the MySQL server (note down the username and password!). Once your MySQL server is up and running, connect to it with the mysql client and enter the following commands to create a database and a table with some example values:

Your local Streamlit app will read secrets from a file .streamlit/secrets.toml in your app's root directory. Learn more about Streamlit secrets management here. Create this file if it doesn't exist yet and add the database name, user, and password of your MySQL server as shown below:

If you use query when defining your connection, you must use streamlit>=1.35.0.

When copying your app secrets to Streamlit Community Cloud, be sure to replace the values of host, port, database, username, and password with those of your remote MySQL database!

Add this file to .gitignore and don't commit it to your GitHub repo!

As the secrets.toml file above is not committed to GitHub, you need to pass its content to your deployed app (on Streamlit Community Cloud) separately. Go to the app dashboard and in the app's dropdown menu, click on Edit Secrets. Copy the content of secrets.toml into the text area. More information is available at Secrets management.

Add the mysqlclient and SQLAlchemy packages to your requirements.txt file, preferably pinning its version (replace x.x.x with the version you want installed):

Copy the code below to your Streamlit app and run it. Make sure to adapt query to use the name of your table.

See st.connection above? This handles secrets retrieval, setup, query caching and retries. By default, query() results are cached without expiring. In this case, we set ttl=600 to ensure the query result is cached for no longer than 10 minutes. You can also set ttl=0 to disable caching. Learn more in Caching.

If everything worked out (and you used the example table we created above), your app should look like this:

Our forums are full of helpful information and Streamlit experts.

---

## Deployment tutorials - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/deploy/deploy-streamlit-heroku-aws-google-cloud

**Contents:**
- Deployment tutorials
      - Streamlit Community Cloud
      - Docker
      - Kubernetes
  - Still have questions?

This sections contains step-by-step guides on how to deploy Streamlit apps to various cloud platforms and services. We have deployment guides for:

While we work on official Streamlit deployment guides for other hosting providers, here are some user-submitted tutorials for different cloud services:

Our forums are full of helpful information and Streamlit experts.

---

## Connect Streamlit to Tableau - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/databases/tableau

**Contents:**
- Connect Streamlit to Tableau
- Introduction
- Create a Tableau site
    - Note
- Create personal access tokens
    - Note
- Add token to your local app secrets
    - Important
- Copy your app secrets to the cloud
- Add tableauserverclient to your requirements file

This guide explains how to securely access data on Tableau from Streamlit Community Cloud. It uses the tableauserverclient library and Streamlit's Secrets management.

If you already have a database that you want to use, feel free to skip to the next step.

For simplicity, we are using the cloud version of Tableau here but this guide works equally well for self-hosted deployments. First, sign up for Tableau Online or log in. Create a workbook or run one of the example workbooks under "Dashboard Starters".

While the Tableau API allows authentication via username and password, you should use personal access tokens for a production app.

Go to your Tableau Online homepage, create an access token and note down the token name and secret.

Personal access tokens will expire if not used after 15 consecutive days.

Your local Streamlit app will read secrets from a file .streamlit/secrets.toml in your app's root directory. Create this file if it doesn't exist yet and add your token, the site name you created during setup, and the URL of your Tableau server like below:

Add this file to .gitignore and don't commit it to your GitHub repo!

As the secrets.toml file above is not committed to GitHub, you need to pass its content to your deployed app (on Streamlit Community Cloud) separately. Go to the app dashboard and in the app's dropdown menu, click on Edit Secrets. Copy the content of secrets.toml into the text area. More information is available at Secrets management.

Add the tableauserverclient package to your requirements.txt file, preferably pinning its version (replace x.x.x with the version you want installed):

Copy the code below to your Streamlit app and run it. Note that this code just shows a few options of data you can get – explore the tableauserverclient library to find more!

See st.cache_data above? Without it, Streamlit would run the query every time the app reruns (e.g. on a widget interaction). With st.cache_data, it only runs when the query changes or after 10 minutes (that's what ttl is for). Watch out: If your database updates more frequently, you should adapt ttl or remove caching so viewers always see the latest data. Learn more in Caching.

If everything worked out, your app should look like this (can differ based on your workbooks):

Our forums are full of helpful information and Streamlit experts.

---

## Validate and edit chat responses - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/tutorials/chat-and-llm-apps/validate-and-edit-chat-responses

**Contents:**
- Validate and edit chat responses
- Applied concepts
- Prerequisites
- Summary
- Build the example
  - Initialize your app
  - Build a function to simulate a chat response stream
  - Create a validation function
  - Create a helper function to highlight text
  - Initialize and display your chat history

As you train LLM models, you may want users to correct or improve chat responses. With Streamlit, you can build a chat app that lets users improve chat responses.

This tutorial uses Streamlit's chat commands to build a simple chat app that lets users modify chat responses to improve them.

This tutorial requires the following version of Streamlit:

You should have a clean working directory called your-repository.

You should have a basic understanding of Session State.

In this example, you'll build a chat interface. To avoid API calls, the app will include a generator function to simulate a chat stream object. When the simulated chat assistant responds, a function validates the response and highlights possible "errors" for the user to review. The user must accept, correct, or rewrite the response before proceeding.

Here's a look at what you'll build:

In your_repository, create a file named app.py.

In a terminal, change directories to your_repository, and start your app:

Your app will be blank because you still need to add code.

In app.py, write the following:

You'll use lorem, random, and time to build a simulated chat response stream.

Save your app.py file, and view your running app.

In your app, select "Always rerun", or press the "A" key.

Your preview will be blank but will automatically update as you save changes to app.py.

To begin, you'll define a function to stream a random chat response. The simulated chat stream will use lorem to generate three to nine random sentences. You can skip this section if you just want to copy the function.

Define a function for your simulated chat stream:

For this example, the chat stream does not have any arguments. The streamed response will be random and independent of the user's prompt.

Create a loop that executes three to nine times:

Within the loop, yield a random sentence from lorem with a space at the end:

To create a streaming effect, add a small delay with time.sleep(0.2) between yields:

You now have a complete generator function to simulate a chat stream object.

The app will validate the streamed responses to assist users in identifying possible errors. To validate a response, you'll first create a list of its sentences. Any sentence with fewer than six words will be marked as a potential error. This is an arbitrary standard for the sake of illustration.

Define a function that accepts a string response and breaks it into sentences:

Use list comprehension to clean the list of sentences. Fo

*[Content truncated]*

---
