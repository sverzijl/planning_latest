# Streamlit - Knowledge Base

**Pages:** 22

---

## How do I upgrade to the latest version of Streamlit? - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/using-streamlit/how-upgrade-latest-version-streamlit

**Contents:**
- How do I upgrade to the latest version of Streamlit?
- Pipenv
- Conda
- Poetry
  - Still have questions?

We recommend upgrading to the latest official release of Streamlit so you have access to the newest, cutting-edge features. If you haven't installed Streamlit yet, please read our Installation guide. It helps you set up your virtual environment and walks you through installing Streamlit on Windows, macOS, and Linux. Regardless of which package management tool and OS you're using, we recommend running the commands on this page in a virtual environment.

If you've previously installed Streamlit and want to upgrade to the latest version, here's how to do it based on your dependency manager.

Streamlit's officially-supported environment manager for macOS and Linux is Pipenv.

Or if you want to use an easily-reproducible environment, replace pip with pipenvevery time you install or update a package:

Be sure to replace$ENVIRONMENT_NAME ☝️ with the name your conda environment!

In order to get the latest version of Streamlit with Poetry and verify you have the latest version, run:

Our forums are full of helpful information and Streamlit experts.

---

## What is serializable session state? - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/using-streamlit/serializable-session-state

**Contents:**
- What is serializable session state?
- Serializable Session State
  - Still have questions?

Serialization refers to the process of converting an object or data structure into a format that can be persisted and shared, and allowing you to recover the data’s original structure. Python’s built-in pickle module serializes Python objects to a byte stream ("pickling") and deserializes the stream into an object ("unpickling").

By default, Streamlit’s Session State allows you to persist any Python object for the duration of the session, irrespective of the object’s pickle-serializability. This property lets you store Python primitives such as integers, floating-point numbers, complex numbers and booleans, dataframes, and even lambdas returned by functions. However, some execution environments may require serializing all data in Session State, so it may be useful to detect incompatibility during development, or when the execution environment will stop supporting it in the future.

To that end, Streamlit provides a runner.enforceSerializableSessionState configuration option that, when set to true, only allows pickle-serializable objects in Session State. To enable the option, either create a global or project config file with the following or use it as a command-line flag:

By "pickle-serializable", we mean calling pickle.dumps(obj) should not raise a PicklingError exception. When the config option is enabled, adding unserializable data to session state should result in an exception. E.g.,

Our forums are full of helpful information and Streamlit experts.

---

## How to download a Pandas DataFrame as a CSV? - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/using-streamlit/how-download-pandas-dataframe-csv

**Contents:**
- How to download a Pandas DataFrame as a CSV?
- Example usage
  - Still have questions?

Use the st.download_button widget that is natively built into Streamlit. Check out a sample app demonstrating how you can use st.download_button to download common file formats.

Additional resources:

Our forums are full of helpful information and Streamlit experts.

---

## How can I make Streamlit watch for changes in other modules I'm importing in my app? - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/using-streamlit/streamlit-watch-changes-other-modules-importing-app

**Contents:**
- How can I make Streamlit watch for changes in other modules I'm importing in my app?
  - Still have questions?

By default, Streamlit only watches modules contained in the current directory of the main app module. You can track other modules by adding the parent directory of each module to the PYTHONPATH.

Our forums are full of helpful information and Streamlit experts.

---

## Where does st.file_uploader store uploaded files and when do they get deleted? - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/using-streamlit/where-file-uploader-store-when-deleted

**Contents:**
- Where does st.file_uploader store uploaded files and when do they get deleted?
  - Still have questions?

When you upload a file using st.file_uploader, the data are copied to the Streamlit backend via the browser, and contained in a BytesIO buffer in Python memory (i.e. RAM, not disk). The data will persist in RAM until the Streamlit app re-runs from top-to-bottom, which is on each widget interaction. If you need to save the data that was uploaded between runs, then you can cache it so that Streamlit persists it across re-runs.

As files are stored in memory, they get deleted immediately as soon as they’re not needed anymore.

This means Streamlit removes a file from memory when:

Our forums are full of helpful information and Streamlit experts.

---

## How can I make st.pydeck_chart use custom Mapbox styles? - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/using-streamlit/pydeck-chart-custom-mapbox-styles

**Contents:**
- How can I make st.pydeck_chart use custom Mapbox styles?
  - Still have questions?

If you are supplying a Mapbox token, but the resulting pydeck_chart doesn't show your custom Mapbox styles, please check that you are adding the Mapbox token to the Streamlit config.toml configuration file. Streamlit DOES NOT read Mapbox tokens from inside of a PyDeck specification (i.e. from inside of the Streamlit app). Please see this forum thread for more information.

Our forums are full of helpful information and Streamlit experts.

---

## What browsers does Streamlit support? - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/using-streamlit/supported-browsers

**Contents:**
- What browsers does Streamlit support?
    - Note
  - Still have questions?

The latest version of Streamlit is compatible with the two most recent versions of the following browsers:

You may not be able to use all the latest features of Streamlit with unsupported browsers or older versions of the above browsers. Streamlit will not provide bug fixes for unsupported browsers.

Our forums are full of helpful information and Streamlit experts.

---

## Widget updating for every second input when using session state - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/using-streamlit/widget-updating-session-state

**Contents:**
- Widget updating for every second input when using session state
- Overview
- Solution
- Relevant resources
  - Still have questions?

You are using session state to store page interactions in your app. When users interact with a widget in your app (e.g., click a button), you expect your app to update its widget states and reflect the new values. However, you notice that it doesn't. Instead, users have to interact with the widget twice (e.g., click a button twice) for the app to show the correct values. What do you do now? 🤔 Let's walk through the solution in the section below.

When using session state to update widgets or values in your script, you need to use the unique key you assigned to the widget, not the variable that you assigned your widget to. In the example code block below, the unique key assigned to the slider widget is slider, and the variable the widget is assigned to is slide_val.

Let's see this in an example. Say you want a user to click a button that resets a slider.

To have the slider's value update on the button click, you need to use a callback function with the on_click parameter of st.button:

Our forums are full of helpful information and Streamlit experts.

---

## How do I create an anchor link? - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/using-streamlit/create-anchor-link

**Contents:**
- How do I create an anchor link?
- Overview
- Solution
- Examples
  - Still have questions?

Have you wanted to create anchors so that users of your app can directly navigate to specific sections by specifying #anchor in the URL? If so, let's find out how.

Anchors are automatically added to header text.

For example, if you define a header text via the st.header() command as follows:

Then you can create a link to this header using:

Our forums are full of helpful information and Streamlit experts.

---

## How do you retrieve the filename of a file uploaded with st.file_uploader? - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/using-streamlit/retrieve-filename-uploaded

**Contents:**
- How do you retrieve the filename of a file uploaded with st.file_uploader?
  - Still have questions?

If you upload a single file (i.e. accept_multiple_files=False), the filename can be retrieved by using the .name attribute on the returned UploadedFile object:

If you upload multiple files (i.e. accept_multiple_files=True), the individual filenames can be retrieved by using the .name attribute on each UploadedFile object in the returned list:

Our forums are full of helpful information and Streamlit experts.

---

## Installing dependencies - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/dependencies

**Contents:**
- Installing dependencies
  - Still have questions?

Our forums are full of helpful information and Streamlit experts.

---

## How to download a file in Streamlit? - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/using-streamlit/how-download-file-streamlit

**Contents:**
- How to download a file in Streamlit?
- Example usage
  - Still have questions?

Use the st.download_button widget that is natively built into Streamlit. Check out a sample app demonstrating how you can use st.download_button to download common file formats.

Additional resources:

Our forums are full of helpful information and Streamlit experts.

---

## ModuleNotFoundError No module named - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/dependencies/module-not-found-error

**Contents:**
- ModuleNotFoundError: No module named
- Problem
- Solution
  - Still have questions?

You receive the error ModuleNotFoundError: No module named when you deploy an app on Streamlit Community Cloud.

This error occurs when you import a module on Streamlit Community Cloud that isn’t included in your requirements file. Any external Python dependencies that are not distributed with a standard Python installation should be included in your requirements file.

E.g. You will see ModuleNotFoundError: No module named 'sklearn' if you don’t include scikit-learn in your requirements file and import sklearn in your app.

Our forums are full of helpful information and Streamlit experts.

---

## Enabling camera or microphone access in your browser - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/using-streamlit/enable-camera

**Contents:**
- Enabling camera or microphone access in your browser
  - Still have questions?

Streamlit apps may include a widget to upload images from your camera or record sound with your microphone. To safeguard the users' privacy and security, browsers require users to explicitly allow access to their camera or microphone before those devices can be used.

To learn how to enable camera access, please check the documentation for your browser:

Our forums are full of helpful information and Streamlit experts.

---

## ImportError libGL.so.1 cannot open shared object file No such file or directory - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/dependencies/libgl

**Contents:**
- ImportError libGL.so.1 cannot open shared object file No such file or directory
- Problem
- Solution
  - Still have questions?

You receive the error ImportError libGL.so.1 cannot open shared object file No such file or directory when using OpenCV in your app deployed on Streamlit Community Cloud.

If you use OpenCV in your app, include opencv-python-headless in your requirements file on Streamlit Community Cloud in place of opencv_contrib_python and opencv-python.

If opencv-python is a required (non-optional) dependency of your app or a dependency of a library used in your app, the above solution is not applicable. Instead, you can use the following solution:

Create a packages.txt file in your repo with the following line to install the apt-get dependency libgl:

Our forums are full of helpful information and Streamlit experts.

---

## How to install a package not on PyPI/Conda but available on GitHub - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/dependencies/install-package-not-pypi-conda-available-github

**Contents:**
- How to install a package not on PyPI/Conda but available on GitHub
- Overview
- Specify the GitHub web URL
- Specify a Git branch name
- Specify a commit hash
- Specify a tag
- Limitations
  - Still have questions?

Are you trying to deploy your app to Streamlit Community Cloud, but don't know how to specify a Python dependency in your requirements file that is available on a public GitHub repo but not any package index like PyPI or Conda? If so, continue reading to find out how!

Let's suppose you want to install SomePackage and its Python dependencies from GitHub, a hosting service for the popular version control system (VCS) Git. And suppose SomePackage is found at the the following URL: https://github.com/SomePackage.git.

pip (via requirements.txt) supports installing from GitHub. This support requires a working executable to be available (for Git). It is used through a URL prefix: git+.

To install SomePackage, innclude the following in your requirements.txt file:

You can even specify a "git ref" such as branch name, a commit hash or a tag name, as shown in the examples below.

Install SomePackage by specifying a branch name such as main, master, develop, etc, in requirements.txt:

Install SomePackage by specifying a commit hash in requirements.txt:

Install SomePackage by specifying a tag in requirements.txt:

It is currently not possible to install private packages from private GitHub repos using the URI form:

where version is a tag, a branch, or a commit. And token is a personal access token with read only permissions. Streamlit Community Cloud only supports installing public packages from public GitHub repos.

Our forums are full of helpful information and Streamlit experts.

---

## ERROR No matching distribution found for - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/dependencies/no-matching-distribution

**Contents:**
- ERROR: No matching distribution found for
- Problem
- Solution
  - Still have questions?

You receive the error ERROR: No matching distribution found for when you deploy an app on Streamlit Community Cloud.

This error occurs when you deploy an app on Streamlit Community Cloud and have one or more of the following issues with your Python dependencies in your requirements file:

Our forums are full of helpful information and Streamlit experts.

---

## FAQ - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/using-streamlit

**Contents:**
- FAQ
  - Still have questions?

Here are some frequently asked questions about using Streamlit. If you feel something important is missing that everyone needs to know, please open an issue or submit a pull request and we'll be happy to review it!

Our forums are full of helpful information and Streamlit experts.

---

## Why does Streamlit restrict nested st.columns? - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/using-streamlit/why-streamlit-restrict-nested-columns

**Contents:**
- Why does Streamlit restrict nested st.columns?
  - Still have questions?

Starting in version 1.46.0, Streamlit removed explicit limits on nesting columns, expanders, popovers, and chat message containers. To follow best design practices and maintain a good appearance on all screen sizes, don't overuse nested layouts.

From version 1.18.0 to 1.45.0, Streamlit allows nesting st.columns inside other st.columns with the following restrictions:

These restrictions were in place to make Streamlit apps look good on all device sizes. Nesting columns multiple times often leads to a bad UI. You might be able to make it look good on one screen size but as soon as a user on a different screen views the app, they will have a bad experience. Some columns will be tiny, others will be way too long, and complex layouts will look out of place. Streamlit tries its best to automatically resize elements to look good across devices, without any help from the developer. But for complex layouts with multiple levels of nesting, this is not possible.

Our forums are full of helpful information and Streamlit experts.

---

## Sanity checks - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/using-streamlit/sanity-checks

**Contents:**
- Sanity checks
- Check #0: Are you using a Streamlit-supported version of Python?
- Check #1: Is Streamlit running?
- Check #2: Is this an already-fixed Streamlit bug?
- Check #3: Are you running the correct Streamlit binary?
- Check #4: Is your browser caching your app too aggressively?
- Check #5: Is this a Streamlit regression?
- Check #6 [Windows]: Is Python added to your PATH?
- Check #7 [Windows]: Do you need Build Tools for Visual Studio installed?
  - Still have questions?

If you're having problems running your Streamlit app, here are a few things to try out.

Streamlit will maintain backwards-compatibility with earlier Python versions as practical, guaranteeing compatibility with at least the last three minor versions of Python 3.

As new versions of Python are released, we will try to be compatible with the new version as soon as possible, though frequently we are at the mercy of other Python packages to support these new versions as well.

Streamlit currently supports versions 3.9, 3.10, 3.11, 3.12, and 3.13 of Python.

On a Mac or Linux machine, type this on the terminal:

If you don't see streamlit run in the output (or streamlit hello, if that's the command you ran) then the Streamlit server is not running. So re-run your command and see if the bug goes away.

We try to fix bugs quickly, so many times a problem will go away when you upgrade Streamlit. So the first thing to try when having an issue is upgrading to the latest version of Streamlit:

...and then verify that the version number printed corresponds to the version number displayed on PyPI.

Try reproducing the issue now. If not fixed, keep reading on.

Let's check whether your Python environment is set up correctly. Edit the Streamlit script where you're experiencing your issue, comment everything out, and add these lines instead:

...then call streamlit run on your script and make sure it says the same version as above. If not the same version, check out these instructions for some sure-fire ways to set up your environment.

There are two easy ways to check this:

Load your app in a browser then press Ctrl-Shift-R or ⌘-Shift-R to do a hard refresh (Chrome/Firefox).

As a test, run Streamlit on another port. This way the browser starts the page with a brand new cache. For that, pass the --server.port argument to Streamlit on the command line:

If you've upgraded to the latest version of Streamlit and things aren't working, you can downgrade at any time using this command:

...where 1.0.0 is the version you'd like to downgrade to. See Release notes for a complete list of Streamlit versions.

When installed by downloading from python.org, Python is not automatically added to the Windows system PATH. Because of this, you may get error messages like the following:

To resolve this issue, add Python to the Windows system PATH.

After adding Python to your Windows PATH, you should then be able to follow the instructions in our Get Started section.

Streamlit include

*[Content truncated]*

---

## How to remove "· Streamlit" from the app title? - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/using-streamlit/remove-streamlit-app-title

**Contents:**
- How to remove "· Streamlit" from the app title?
  - Still have questions?

Using st.set_page_config to assign the page title will not append "· Streamlit" to that title. E.g.:

Our forums are full of helpful information and Streamlit experts.

---

## How to insert elements out of order? - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/using-streamlit/insert-elements-out-of-order

**Contents:**
- How to insert elements out of order?
  - Still have questions?

You can use the st.empty method as a placeholder, to "save" a slot in your app that you can use later.

Our forums are full of helpful information and Streamlit experts.

---
