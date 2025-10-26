# Streamlit - Concepts

**Pages:** 48

---

## Automate your tests with CI - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/app-testing/automate-tests

**Contents:**
- Automate your tests with CI
- GitHub Actions
- Streamlit App Action
  - Triggering the workflow
  - Setting up the test environment
  - Running the app tests
    - Tip
  - Linting your app code
    - Tip
  - Viewing results

One of the key benefits of app testing is that tests can be automated using Continuous Integration (CI). By running tests automatically during development, you can validate that changes to your app don't break existing functionality. You can verify app code as you commit, catch bugs early, and prevent accidental breaks before deployment.

There are many popular CI tools, including GitHub Actions, Jenkins, GitLab CI, Azure DevOps, and Circle CI. Streamlit app testing will integrate easily with any of them similar to any other Python tests.

Since many Streamlit apps (and all Community Cloud apps) are built in GitHub, this page uses examples from GitHub Actions. For more information about GitHub Actions, see:

Streamlit App Action provides an easy way to add automated testing to your app repository in GitHub. It also includes basic smoke testing for each page of your app without you writing any test code.

To install Streamlit App Action, add a workflow .yml file to your repository's .github/workflows/ folder. For example:

Let's take a look in more detail at what this action workflow is doing.

This workflow will be triggered and execute tests on pull requests targeting the main branch, as well as any new commits pushed to the main branch. Note that it will also execute the tests on subsequent commits to any open pull requests. See GitHub Actions: Triggering a workflow for more information and examples.

The workflow has a streamlit job that executes a series of steps. The job runs on a Docker container with the ubuntu-latest image.

Streamlit App Action does the following:

If your app doesn't include requirements.txt in the repository root directory, you will need to add a step to install dependencies with your chosen package manager before running Streamlit App Action.

The built-in smoke tests have the following behavior:

If you want to run Streamlit App Action without the smoke tests, you can set skip-smoke: true.

Linting is the automated checking of source code for programmatic and stylistic errors. This is done by using a lint tool (otherwise known as a linter). Linting is important to reduce errors and improve the overall quality of your code, especially for repositories with multiple developers or public repositories.

You can add automated linting with Ruff by passing ruff: true to Streamlit App Action.

You may want to add a pre-commit hook like ruff-pre-commit in your local development environment to fix linting errors before they get to CI.



*[Content truncated]*

---

## Define multipage apps with st.Page and st.navigation - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/multipage-apps/page-and-navigation

**Contents:**
- Define multipage apps with st.Page and st.navigation
- App structure
- Defining pages
- Customizing navigation
  - Adding section headers
  - Dynamically changing the available pages
  - Building a custom navigation menu
  - Still have questions?

st.Page and st.navigation are the preferred commands for defining multipage apps. With these commands, you have flexibility to organize your project files and customize your navigation menu. Simply initialize StreamlitPage objects with st.Page, then pass those StreamlitPage objects to st.navigation in your entrypoint file (i.e. the file you pass to streamlit run).

This page assumes you understand the Page terminology presented in the overview.

When using st.navigation, your entrypoint file acts like a page router. Each page is a script executed from your entrypoint file. You can define a page from a Python file or function. If you include elements or widgets in your entrypoint file, they become common elements between your pages. In this case, you can think of your entrypoint file like a picture frame around each of your pages.

You can only call st.navigation once per app run and you must call it from your entrypoint file. When a user selects a page in navigation (or is routed through a command like st.switch_page), st.navigation returns the selected page. You must manually execute that page with the .run() method. The following example is a two-page app where each page is defined by a Python file.

st.Page lets you define a page. The first and only required argument defines your page source, which can be a Python file or function. When using Python files, your pages may be in a subdirectory (or superdirectory). The path to your page file must always be relative to the entrypoint file. Once you create your page objects, pass them to st.navigation to register them as pages in your app.

If you don't define your page title or URL pathname, Streamlit will infer them from the file or function name as described in the multipage apps Overview. However, st.Page lets you configure them manually. Within st.Page, Streamlit uses title to set the page label and title. Additionaly, Streamlit uses icon to set the page icon and favicon. If you want to have a different page title and label, or different page icon and favicon, you can use st.set_page_config to change the page title and/or favicon. Just call st.set_page_config in your entrypoint file or in your page script. You can call st.set_page_config multiple times to additively configure your page. Use st.set_page_config in your entrypoint file to declare a default configuration, and call it within page scripts to override that default.

The following example uses st.set_page_config to set a page title and favicon 

*[Content truncated]*

---

## Streamlit's native app testing framework - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/app-testing

**Contents:**
- Streamlit's native app testing framework
  - Still have questions?

Streamlit app testing enables developers to build and run automated tests. Bring your favorite test automation software and enjoy simple syntax to simulate user input and inspect rendered output.

The provided class, AppTest, simulates a running app and provides methods to set up, manipulate, and inspect the app contents via API instead of a browser UI. AppTest provides similar functionality to browser automation tools like Selenium or Playwright, but with less overhead to write and execute tests. Use our testing framework with a tool like pytest to execute or automate your tests. A typical pattern is to build a suite of tests for an app to ensure consistent functionality as the app evolves. The tests run locally and/or in a CI environment like GitHub Actions.

Get started introduces you to the app testing framework and how to execute tests using pytest. Learn how to initialize and run simulated apps, including how to retrieve, manipulate, and inspect app elements.

Beyond the basics explains how to work with secrets and Session State within app tests, including how to test multipage apps.

Automate your tests with Continuous Integration (CI) to validate app changes over time.

Example puts together the concepts explained above. Check out an app with multiple tests in place.

Cheat sheet is a compact reference summarizing the available syntax.

Our forums are full of helpful information and Streamlit experts.

---

## Run your Streamlit app - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/architecture/run-your-app

**Contents:**
- Run your Streamlit app
- Use streamlit run
  - Pass arguments to your script
  - Pass a URL to streamlit run
- Run Streamlit as a Python module
  - Still have questions?

Working with Streamlit is simple. First you sprinkle a few Streamlit commands into a normal Python script, and then you run it. We list few ways to run your script, depending on your use case.

Once you've created your script, say your_script.py, the easiest way to run it is with streamlit run:

As soon as you run the script as shown above, a local Streamlit server will spin up and your app will open in a new tab in your default web browser.

When passing your script some custom arguments, they must be passed after two dashes. Otherwise the arguments get interpreted as arguments to Streamlit itself:

You can also pass a URL to streamlit run! This is great when your script is hosted remotely, such as a GitHub Gist. For example:

Another way of running Streamlit is to run it as a Python module. This is useful when configuring an IDE like PyCharm to work with Streamlit:

Our forums are full of helpful information and Streamlit experts.

---

## Managing secrets when deploying your app - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/concepts/secrets

**Contents:**
- Managing secrets when deploying your app
  - Still have questions?

If you are connecting to data sources or external services, you will likely be handling secret information like credentials or keys. Secret information should be stored and transmitted in a secure manner. When you deploy your app, ensure that you understand your platform's features and mechanisms for handling secrets so you can follow best practice.

Avoid saving secrets directly in your code and keep .gitignore updated to prevent accidentally committing a local secret to your repository. For helpful reminders, see Security reminders.

If you are using Streamlit Community Cloud, Secrets management allows you save environment variables and store secrets outside of your code. If you are using another platform designed for Streamlit, check if they have a built-in mechanism for working with secrets. In some cases, they may even support st.secrets or securely uploading your secrets.toml file.

For information about using st.connection with environment variables, see Global secrets, managing multiple apps and multiple data stores.

Our forums are full of helpful information and Streamlit experts.

---

## Limitations of custom components - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/custom-components/limitations

**Contents:**
- Limitations of custom components
- How do Streamlit Components differ from functionality provided in the base Streamlit package?
- What types of things aren't possible with Streamlit Components?
- My Component seems to be blinking/stuttering...how do I fix that?
  - Still have questions?

Because each Streamlit Component gets mounted into its own sandboxed iframe, this implies a few limitations on what is possible with Components:

Currently, no automatic debouncing of Component updates is performed within Streamlit. The Component creator themselves can decide to rate-limit the updates they send back to Streamlit.

Our forums are full of helpful information and Streamlit experts.

---

## Creating multipage apps using the `pages/` directory - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/multipage-apps/pages-directory

**Contents:**
- Creating multipage apps using the pages/ directory
- App structure
    - Important
  - How pages are sorted in the sidebar
    - Tip
- Notes and limitations
  - Still have questions?

The most customizable method for declaring multipage apps is using Page and navigation. However, Streamlit also provides a frictionless way to create multipage apps where pages are automatically recognized and shown in a navigation widget inside your app's sidebar. This method uses the pages/ directory.

This page assumes you understand the Page terminology presented in the overview.

When you use the pages/ directory, Streamlit identifies pages in your multipage app by directory structure and filenames. Your entrypoint file (the file you pass to streamlit run), is your app's homepage. When you have a pages/ directory next to your entrypoint file, Streamlit will identify each Python file within it as a page. The following example has three pages. your_homepage.py is the entrypoint file and homepage.

Run your multipage app just like you would for a single-page app. Pass your entrypoint file to streamlit run.

Only .py files in the pages/ directory will be identified as pages. Streamlit ignores all other files in the pages/ directory and its subdirectories. Streamlit also ignores Python files in subdirectories of pages/.

If you call st.navigation in your app (in any session), Streamlit will switch to using the newer, Page-and-navigation multipage structure. In this case, the pages/ directory will be ignored across all sessions. You will not be able to revert back to the pages/ directory unless you restart you app.

See the overview to understand how Streamlit assigns Automatic page labels and URLs based on the number, separator, identifier, and ".py" extension that constitute a filename.

The entrypoint file is always displayed first. The remaining pages are sorted as follows:

This table shows examples of filenames and their corresponding labels, sorted by the order in which they appear in the sidebar.

Emojis can be used to make your page names more fun! For example, a file named 🏠_Home.py will create a page titled "🏠 Home" in the sidebar. When adding emojis to filenames, it’s best practice to include a numbered prefix to make autocompletion in your terminal easier. Terminal-autocomplete can get confused by unicode (which is how emojis are represented).

Pages support run-on-save.

While your app is running, adding or deleting a page updates the sidebar navigation immediately.

st.set_page_config works at the page level.

Pages share the same Python modules globally:

Pages share the same st.session_state:

You now have a solid understanding of multipage

*[Content truncated]*

---

## Animate and update elements - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/design/animate

**Contents:**
- Animate and update elements
- st.empty containers
- The .add_rows() method
  - Still have questions?

Sometimes you display a chart or dataframe and want to modify it live as the app runs (for example, in a loop). Some elements have built-in methods to allow you to update them in-place without rerunning the app.

Updatable elements include the following:

st.empty can hold a single element. When you write any element to an st.empty container, Streamlit discards its previous content displays the new element. You can also st.empty containers by calling .empty() as a method. If you want to update a set of elements, use a plain container (st.container()) inside st.empty and write contents to the plain container. Rewrite the plain container and its contents as often as desired to update your app's display.

st.dataframe, st.table, and all chart functions can be mutated using the .add_rows() method on their output. In the following example, we use my_data_element = st.line_chart(df). You can try the example with st.table, st.dataframe, and most of the other simple charts by just swapping out st.line_chart. Note that st.dataframe only shows the first ten rows by default and enables scrolling for additional rows. This means adding rows is not as visually apparent as it is with st.table or the chart elements.

Our forums are full of helpful information and Streamlit experts.

---

## Working with widgets in multipage apps - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/multipage-apps/widgets

**Contents:**
- Working with widgets in multipage apps
- Option 1 (preferred): Execute your widget command in your entrypoint file
- Option 2: Save your widget values into a dummy key in Session State
- Option 3: Interrupt the widget clean-up process
  - Still have questions?

When you create a widget in a Streamlit app, Streamlit generates a widget ID and uses it to make your widget stateful. As your app reruns with user interaction, Streamlit keeps track of the widget's value by associating its value to its ID. In particular, a widget's ID depends on the page where it's created. If you define an identical widget on two different pages, then the widget will reset to its default value when you switch pages.

This guide explains three strategies to deal with the behavior if you'd like to have a widget remain stateful across all pages. If don't want a widget to appear on all pages, but you do want it to remain stateful when you navigate away from its page (and then back), Options 2 and 3 can be used. For detailed information about these strategies, see Understanding widget behavior.

When you define your multipage app with st.Page and st.navigation, your entrypoint file becomes a frame of common elements around your pages. When you execute a widget command in your entrypoint file, Streamlit associates the widget to your entrypoint file instead of a particular page. Since your entrypoint file is executed in every app rerun, any widget in your entrypoint file will remain stateful as your users switch between pages.

This method does not work if you define your app with the pages/ directory.

The following example includes a selectbox and slider in the sidebar that are rendered and stateful on all pages. The widgets each have an assigned key so you can access their values through Session State within a page.

If you want to navigate away from a widget and return to it while keeping its value, or if you want to use the same widget on multiple pages, use a separate key in st.session_state to save the value independently from the widget. In this example, a temporary key is used with a widget. The temporary key uses an underscore prefix. Hence, "_my_key" is used as the widget key, but the data is copied to "my_key" to preserve it between pages.

If this is functionalized to work with multiple widgets, it could look something like this:

When Streamlit gets to the end of an app run, it will delete the data for any widgets that were not rendered. This includes data for any widget not associated to the current page. However, if you re-save a key-value pair in an app run, Streamlit will not associate the key-value pair to any widget until you execute a widget command again with that key.

As a result, if you have the following code at the to

*[Content truncated]*

---

## Working with Streamlit's execution model - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/architecture

**Contents:**
- Working with Streamlit's execution model
      - Run your app
      - Streamlit's architecture
      - The app chrome
      - Caching
      - Session State
      - Forms
      - Widget behavior
  - Still have questions?

Understand how to start your Streamlit app.

Understand Streamlit's client-server architecture and related considerations.

Every Streamlit app has a few widgets in the top right to help you as you develop your app and help your users as they view your app. This is called the app chrome.

Make your app performant by caching results to avoid unecessary recomputation with each rerun.

Manage your app's statefulness with Session State.

Use forms to isolate user input and prevent unnecessary app reruns.

Understand how widgets work in detail.

Our forums are full of helpful information and Streamlit experts.

---

## Security reminders - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/connections/security-reminders

**Contents:**
- Security reminders
- Protect your secrets
  - Use environment variables
  - Keep .gitignore updated
- Pickle warning
  - Still have questions?

Never save usernames, passwords, or security keys directly in your code or commit them to your repository.

Avoid putting sensitve information in your code by using environment variables. Be sure to check out st.secrets. Research any platform you use to follow their security best practices. If you use Streamlit Community Cloud, Secrets management allows you save environment variables and store secrets outside of your code.

If you use any sensitive or private information during development, make sure that information is saved in separate files from your code. Ensure .gitignore is properly configured to prevent saving private information to your repository.

Streamlit's st.cache_data and st.session_state implicitly use the pickle module, which is known to be insecure. It is possible to construct malicious pickle data that will execute arbitrary code during unpickling. Never load data that could have come from an untrusted source in an unsafe mode or that could have been tampered with. Only load data you trust.

Our forums are full of helpful information and Streamlit experts.

---

## HTTPS support - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/configuration/https-support

**Contents:**
- HTTPS support
- Details on usage
    - Warning
- Example usage
  - Still have questions?

Many apps need to be accessed with SSL / TLS protocol or https://.

We recommend performing SSL termination in a reverse proxy or load balancer for self-hosted and production use cases, not directly in the app. Streamlit Community Cloud uses this approach, and every major cloud and app hosting platform should allow you to configure it and provide extensive documentation. You can find some of these platforms in our Deployment tutorials.

To terminate SSL in your Streamlit app, you must configure server.sslCertFile and server.sslKeyFile. Learn how to set config options in Configuration.

In a production environment, we recommend performing SSL termination by the load balancer or the reverse proxy, not using this option. The use of this option in Streamlit has not gone through extensive security audits or performance tests.

Our forums are full of helpful information and Streamlit experts.

---

## Understanding Streamlit's client-server architecture - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/architecture/architecture

**Contents:**
- Understanding Streamlit's client-server architecture
- Python backend (server)
- Browser frontend (client)
- Server-client impact on app design
- WebSockets and session management
  - Session affinity or stickiness
  - Still have questions?

Streamlit apps have a client-server structure. The Python backend of your app is the server. The frontend you view through a browser is the client. When you develop an app locally, your computer runs both the server and the client. If someone views your app across a local or global network, the server and client run on different machines. If you intend to share or deploy your app, it's important to understand this client-server structure to avoid common pitfalls.

When you execute the command streamlit run your_app.py, your computer uses Python to start up a Streamlit server. This server is the brains of your app and performs the computations for all users who view your app. Whether users view your app across a local network or the internet, the Streamlit server runs on the one machine where the app was initialized with streamlit run. The machine running your Streamlit server is also called a host.

When someone views your app through a browser, their device is a Streamlit client. When you view your app from the same computer where you are running or developing your app, then server and client are coincidentally running on the same machine. However, when users view your app across a local network or the internet, the client runs on a different machine from the server.

Keep in mind the following considerations when building your Streamlit app:

While most Streamlit app developers don’t need to interact directly with WebSockets, understanding their role is important for advanced deployments, custom components, or managing connections at scale.

Streamlit’s server is built on the Tornado web framework, which uses WebSockets to maintain a persistent, two-way communication channel between the client and server. This persistent connection allows the server to push real-time updates to the client and maintain session context for each user. Each browser tab or window creates its own WebSocket connection, resulting in a separate session within your app.

In large-scale or production deployments, load balancing and server replication are common. However, the way Streamlit handles sessions and local (server) files requires special consideration in these environments. When a client requests media (such as an image or audio file) via HTTP, there is no session context attached to that request. In deployments with multiple server replicas or load balancers, the HTTP request for the media file might be routed to a different server than the one handling the user’s WebSock

*[Content truncated]*

---

## Working with configuration options - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/configuration/options

**Contents:**
- Working with configuration options
    - Note
- Available options
- Telemetry
- Theming
- View all configuration options
  - Still have questions?

Streamlit provides four different ways to set configuration options. This list is in reverse order of precedence, i.e. command line flags take precedence over environment variables when the same configuration option is provided multiple times.

If you change theme settings in .streamlit/config.toml while the app is running, these changes will reflect immediately. If you change non-theme settings in .streamlit/config.toml while the app is running, the server needs to be restarted for changes to be reflected in the app.

In a global config file at ~/.streamlit/config.toml for macOS/Linux or %userprofile%/.streamlit/config.toml for Windows:

In a per-project config file at $CWD/.streamlit/config.toml, where $CWD is the folder you're running Streamlit from.

Through STREAMLIT_* environment variables, such as:

As flags on the command line when running streamlit run:

All available configuration options are documented in config.toml. These options may be declared in a TOML file, as environment variables, or as command line options.

When using environment variables to override config.toml, convert the variable (including its section header) to upper snake case and add a STREAMLIT_ prefix. For example, STREAMLIT_CLIENT_SHOW_ERROR_DETAILS is equivalent to the following in TOML:

When using command line options to override config.toml and environment variables, use the same case as you would in the TOML file and include the section header as a period-separated prefix. For example, the command line option --server.enableStaticServing true is equivalent to the following:

As mentioned during the installation process, Streamlit collects usage statistics. You can find out more by reading our Privacy Notice, but the high-level summary is that although we collect telemetry data we cannot see and do not store information contained in Streamlit apps.

If you'd like to opt out of usage statistics, add the following to your config file:

You can change the base colors of your app using the [theme] section of the configuration system. To learn more, see Theming.

As described in Command-line options, you can view all available configuration options using:

Our forums are full of helpful information and Streamlit experts.

---

## App testing cheat sheet - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/app-testing/cheat-sheet

**Contents:**
- App testing cheat sheet
- Text elements
- Input widgets
- Data elements
- Layouts and containers
- Chat elements
- Status elements
- Limitations
  - Still have questions?

As of Streamlit 1.28, the following Streamlit features are not natively supported by AppTest. However, workarounds are possible for many of them by inspecting the underlying proto directly using AppTest.get(). We plan to regularly add support for missing elements until all features are supported.

Our forums are full of helpful information and Streamlit experts.

---

## Using forms - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/architecture/forms

**Contents:**
- Using forms
- Example
- User interaction
- Widget values
- Forms are containers
- Processing form submissions
  - Execute the process after the form
  - Use a callback with session state
    - Important
  - Use st.rerun

When you don't want to rerun your script with each input made by a user, st.form is here to help! Forms make it easy to batch user input into a single rerun. This guide to using forms provides examples and explains how users interact with forms.

In the following example, a user can set multiple parameters to update the map. As the user changes the parameters, the script will not rerun and the map will not update. When the user submits the form with the button labeled "Update map", the script reruns and the map updates.

If at any time the user clicks "Generate new points" which is outside of the form, the script will rerun. If the user has any unsubmitted changes within the form, these will not be sent with the rerun. All changes made to a form will only be sent to the Python backend when the form itself is submitted.

If a widget is not in a form, that widget will trigger a script rerun whenever a user changes its value. For widgets with keyed input (st.number_input, st.text_input, st.text_area), a new value triggers a rerun when the user clicks or tabs out of the widget. A user can also submit a change by pressing Enter while their cursor is active in the widget.

On the other hand if a widget is inside of a form, the script will not rerun when a user clicks or tabs out of that widget. For widgets inside a form, the script will rerun when the form is submitted and all widgets within the form will send their updated values to the Python backend.

A user can submit a form using Enter on their keyboard if their cursor active in a widget that accepts keyed input. Within st.number_input and st.text_input a user presses Enter to submit the form. Within st.text_area a user presses Ctrl+Enter/⌘+Enter to submit the form.

Before a form is submitted, all widgets within that form will have default values, just like widgets outside of a form have default values.

When st.form is called, a container is created on the frontend. You can write to that container like you do with other container elements. That is, you can use Python's with statement as shown in the example above, or you can assign the form container to a variable and call methods on it directly. Additionally, you can place st.form_submit_button anywhere in the form container.

The purpose of a form is to override the default behavior of Streamlit which reruns a script as soon as the user makes a change. For widgets outside of a form, the logical flow is:

For widgets inside a form, any changes made by a 

*[Content truncated]*

---

## Connecting to data - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/connections/connecting-to-data

**Contents:**
- Connecting to data
- Basic usage
  - A simple starting point - using a local SQLite database
    - Note
    - Step 1: Install prerequisite library - SQLAlchemy
    - Step 2: Set a database URL in your Streamlit secrets.toml file
    - Step 3: Use the connection in your app
- Advanced topics
  - Global secrets, managing multiple apps and multiple data stores
  - Advanced SQLConnection configuration

Most Streamlit apps need some kind of data or API access to be useful - either retrieving data to view or saving the results of some user action. This data or API is often part of some remote service, database, or other data source.

Anything you can do with Python, including data connections, will generally work in Streamlit. Streamlit's tutorials are a great starting place for many data sources. However:

Streamlit provides st.connection() to more easily connect your Streamlit apps to data and APIs with just a few lines of code. This page provides a basic example of using the feature and then focuses on advanced usage.

For a comprehensive overview of this feature, check out this video tutorial by Joshua Carroll, Streamlit's Product Manager for Developer Experience. You'll learn about the feature's utility in creating and managing data connections within your apps by using real-world examples.

For basic startup and usage examples, read up on the relevant data source tutorial. Streamlit has built-in connections to SQL dialects and Snowflake. We also maintain installable connections for Cloud File Storage and Google Sheets.

If you are just starting, the best way to learn is to pick a data source you can access and get a minimal example working from one of the pages above 👆. Here, we will provide an ultra-minimal usage example for using a SQLite database. From there, the rest of this page will focus on advanced usage.

A local SQLite database could be useful for your app's semi-persistent data storage.

Community Cloud apps do not guarantee the persistence of local file storage, so the platform may delete data stored using this technique at any time.

To see the example below running live, check out the interactive demo below:

All SQLConnections in Streamlit use SQLAlchemy. For most other SQL dialects, you also need to install the driver. But the SQLite driver ships with python3, so it isn't necessary.

Create a directory and file .streamlit/secrets.toml in the same directory your app will run from. Add the following to the file.

The following app creates a connection to the database, uses it to create a table and insert some data, then queries the data back and displays it in a data frame.

In this example, we didn't set a ttl= value on the call to conn.query(), meaning Streamlit caches the result indefinitely as long as the app server runs.

Now, on to more advanced topics! 🚀

Streamlit supports a global secrets file specified in the user's home direc

*[Content truncated]*

---

## Components - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/custom-components

**Contents:**
- Custom Components
- How to use a Component
- Making your own Component
      - Video tutorial, part 1
      - Video tutorial, part 2
  - Still have questions?

Components are third-party Python modules that extend what's possible with Streamlit.

Components are super easy to use:

Start by finding the Component you'd like to use. Two great resources for this are:

Install the Component using your favorite Python package manager. This step and all following steps are described in your component's instructions.

For example, to use the fantastic AgGrid Component, you first install it with:

In your Python code, import the Component as described in its instructions. For AgGrid, this step is:

...now you're ready to use it! For AgGrid, that's:

If you're interested in making your own component, check out the following resources:

Alternatively, if you prefer to learn using videos, our engineer Tim Conkling has put together some amazing tutorials:

Our forums are full of helpful information and Streamlit experts.

---

## Publish a Component - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/custom-components/publish

**Contents:**
- Publish a Component
- Publish to PyPI
    - Note
  - Prepare your Component
  - Build a Python wheel
  - Upload your wheel to PyPI
- Promote your Component!
  - Still have questions?

Publishing your Streamlit Component to PyPI makes it easily accessible to Python users around the world. This step is completely optional, so if you won’t be releasing your component publicly, you can skip this section!

For static Streamlit Components, publishing a Python package to PyPI follows the same steps as the core PyPI packaging instructions. A static Component likely contains only Python code, so once you have your setup.py file correct and generate your distribution files, you're ready to upload to PyPI.

Bi-directional Streamlit Components at minimum include both Python and JavaScript code, and as such, need a bit more preparation before they can be published on PyPI. The remainder of this page focuses on the bi-directional Component preparation process.

A bi-directional Streamlit Component varies slightly from a pure Python library in that it must contain pre-compiled frontend code. This is how base Streamlit works as well; when you pip install streamlit, you are getting a Python library where the HTML and frontend code contained within it have been compiled into static assets.

The component-template GitHub repo provides the folder structure necessary for PyPI publishing. But before you can publish, you'll need to do a bit of housekeeping:

Give your Component a name, if you haven't already

Edit MANIFEST.in, change the path for recursive-include from package/frontend/build * to <component name>/frontend/build *

Edit setup.py, adding your component's name and other relevant info

Create a release build of your frontend code. This will add a new directory, frontend/build/, with your compiled frontend in it:

Pass the build folder's path as the path parameter to declare_component. (If you're using the template Python file, you can set _RELEASE = True at the top of the file):

Once you've changed the default my_component references, compiled the HTML and JavaScript code and set your new component name in components.declare_component(), you're ready to build a Python wheel:

Make sure you have the latest versions of setuptools, wheel, and twine

Create a wheel from the source code:

With your wheel created, the final step is to upload to PyPI. The instructions here highlight how to upload to Test PyPI, so that you can learn the mechanics of the process without worrying about messing anything up. Uploading to PyPI follows the same basic procedure.

Create an account on Test PyPI if you don't already have one

Visit https://test.pypi.org/account/

*[Content truncated]*

---

## Beyond the basics of app testing - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/app-testing/beyond-the-basics

**Contents:**
- Beyond the basics of app testing
- Using secrets with app testing
  - Example: declaring secrets in a test
- Working with Session State in app testing
  - Example: testing a multipage app
  - Still have questions?

Now that you're comfortable with executing a basic test for a Streamlit app let's cover the mutable attributes of AppTest:

You can read and update values using dict-like syntax for all three attributes. For .secrets and .query_params, you can use key notation but not attribute notation. For example, the .secrets attribute for AppTest accepts at.secrets["my_key"] but not at.secrets.my_key. This differs from how you can use the associated command in the main library. On the other hand, .session_state allows both key notation and attribute notation.

For these attributes, the typical pattern is to declare any values before executing the app's first run. Values can be inspected at any time in a test. There are a few extra considerations for secrets and Session State, which we'll cover now.

Be careful not to include secrets directly in your tests. Consider this simple project with pytest executed in the project's root directory:

In the above scenario, your simulated app will have access to your secrets.toml file. However, since you don't want to commit your secrets to your repository, you may need to write tests where you securely pull your secrets into memory or use dummy secrets.

Within a test, declare each secret after initializing your AppTest instance but before the first run. (A missing secret may result in an app that doesn't run!) For example, consider the following secrets file and corresponding test initialization to assign the same secrets manually:

Testing file with equivalent secrets:

Generally, you want to avoid typing your secrets directly into your test. If you don't need your real secrets for your test, you can declare dummy secrets as in the example above. If your app uses secrets to connect to an external service like a database or API, consider mocking that service in your app tests. If you need to use the real secrets and actually connect, you should use an API to pass them securely and anonymously. If you are automating your tests with GitHub actions, check out their Security guide.

The .session_state attribute for AppTest lets you read and update Session State values using key notation (at.session_state["my_key"]) and attribute notation (at.session_state.my_key). By manually declaring values in Session State, you can directly jump to a specific state instead of simulating many steps to get there. Additionally, the testing framework does not provide native support for multipage apps. An instance of AppTest can only test one page. Yo

*[Content truncated]*

---

## Colors and borders - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/configuration/theming-customize-colors-and-borders?utm_source=streamlit

**Contents:**
- Customize colors and borders in your Streamlit app
- Color values
    - Tip
- Default Streamlit colors
- Color and border configuration options
  - Basic color palette
  - primaryColor
    - Tip
    - Example 1: Primary color
  - backgroundColor, secondaryBackgroundColor, codeBackgroundColor, and dataframeHeaderBackgroundColor

For all configuration options that accept a color, you can specify the value with one of the following strings:

Although you can specify an alpha value for your colors, this isn't necessary for most options. Streamlit adjusts the alpha value of colors to ensure contextually appropriate shading between background and foreground.

Streamlit comes with two preconfigured themes: light and dark. If you don't specify any theme configuration options, Streamlit will attempt to use the preconfigured theme that best matches each user's browser settings. These themes feature a red primary color in addition to a basic color palette (red, orange, yellow, green, blue, violet, and gray/grey) for elements like colored Markdown text.

Most theme configuration options can be set for your whole app, but you can override some with a different value for the sidebar. For example, your app's primary color (primaryColor) is used to highlight interactive elements and show focus. If you set theme.primaryColor, this will change the primary color for your whole app. However, if you set theme.sidebar.primaryColor, this will override theme.primaryColor in the sidebar, allowing you to use two different primary colors.

The following two configuration options can only be applied to the whole app:

The following configuration options can be set separately for the sidebar by using the [theme.sidebar] table instead of the [theme] table in config.toml:

For brevity, on the rest of this page, theming configuration options will not include the theme. or theme.sidebar. prefix.

Various elements in Streamlit use or let you choose from a predefined palette of colors: red, orange, yellow, green, blue, violet, and gray/grey. These are some of the elements that use this basic color palette:

For each color in the palette, you can define a base color, background color, and text color. If you only define a base color, Streamlit adjusts lightness/darkness and opacity to automatically provide a corresponding background and text color. However, you can manually define each of them, too. These are the color palette options:

primaryColor defines the accent color most often used throughout your Streamlit app. The following features and effects use your primary color:

When your primary color is used as a background, Streamlit changes the text color to white. For example, this happens for type="primary" buttons and for selected items in st.multiselect.

For legibility, always choose a primary color that is

*[Content truncated]*

---

## Development concepts - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts

**Contents:**
- Development concepts
      - Streamlit's architecture and execution model
      - Multipage apps
      - App design considerations
      - Connections and secrets
      - Creating custom components
      - Configuration and theming
      - App testing
  - Still have questions?

This section gives you background on how different parts of Streamlit work.

Streamlit's execution model makes it easy to turn your scripts into beautiful, interactive web apps.

Streamlit provides an automated way to build multipage apps through directory structure.

Bring together Streamlit's architecture and execution model to design your app. Work with Streamlit commands to render dynamic and interactic content for your users.

Custom components extend Streamlit's functionality.

Streamlit provides a variety options to customize and configure your app.

Streamlit app testing enables developers to build and run automated tests. Bring your favorite test automation software and enjoy simple syntax to simulate user input and inspect rendered output.

Our forums are full of helpful information and Streamlit experts.

---

## Overview of multipage apps - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/multipage-apps/overview

**Contents:**
- Overview of multipage apps
- st.Page and st.navigation
- pages/ directory
- Page terminology
- Automatic page labels and URLs
  - Parts of filenames and callables
  - How Streamlit converts filenames into labels and titles
  - How Streamlit converts filenames into URL pathnames
- Navigating between pages
    - Important

Streamlit provides two built-in mechanisms for creating multipage apps. The simplest method is to use a pages/ directory. However, the preferred and more customizable method is to use st.navigation.

If you want maximum flexibility in defining your multipage app, we recommend using st.Page and st.navigation. With st.Page you can declare any Python file or Callable as a page in your app. Furthermore, you can define common elements for your pages in your entrypoint file (the file you pass to streamlit run). With these methods, your entrypoint file becomes like a picture frame shared by all your pages.

You must include st.navigation in your entrypoint file to configure your app's navigation menu. This is also how your entrypoint file serves as the router between your pages.

If you're looking for a quick and simple solution, just place a pages/ directory next to your entrypoint file. For every Python file in your pages/ directory, Streamlit will create an additional page for your app. Streamlit determines the page labels and URLs from the file name and automatically populates a navigation menu at the top of your app's sidebar.

Streamlit determines the page order in navigation from the filenames. You can use numerical prefixes in the filenames to adjust page order. For more information, see How pages are sorted in the sidebar. If you want to customize your navigation menu with this option, you can deactivate the default navigation through configuration (client.showSidebarNavigation = false). Then, you can use st.page_link to manually contruct a custom navigation menu. With st.page_link, you can change the page label and icon in your navigation menu, but you can't change the URLs of your pages.

A page has four identifying pieces as follows:

Additionly, a page can have two icons as follows:

Typically, the page icon and favicon are the same, but it's possible make them different.

1. Page label, 2.Page titles, 3. Page URL pathname, 4.Page favicon, 5. Page icon

If you use st.Page without declaring the page title or URL pathname, Streamlit falls back on automatically determining the page label, title, and URL pathname in the same manner as when you use a pages/ directory with the default navigation menu. This section describes this naming convention which is shared between the two approaches to multipage apps.

Filenames are composed of four different parts as follows (in order):

For callables, the function name is the identifier, including any leading or tr

*[Content truncated]*

---

## Widget behavior - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/architecture/widget-behavior

**Contents:**
- Understanding widget behavior
- Anatomy of a widget
  - Widgets are session dependent
  - Widgets return simple Python data types
  - Keys help distinguish widgets and access their values
    - Streamlit can't understand two identical widgets on the same page
    - Use keys to distinguish otherwise identical widgets
- Order of operations
    - Note
  - Using callback functions with forms

Widgets (like st.button, st.selectbox, and st.text_input) are at the heart of Streamlit apps. They are the interactive elements of Streamlit that pass information from your users into your Python code. Widgets are magical and often work how you want, but they can have surprising behavior in some situations. Understanding the different parts of a widget and the precise order in which events occur helps you achieve your desired results.

This guide covers advanced concepts about widgets. Generally, it begins with simpler concepts and increases in complexity. For most beginning users, these details won't be important to know right away. When you want to dynamically change widgets or preserve widget information between pages, these concepts will be important to understand. We recommend having a basic understanding of Session State before reading this guide.

The last two points (widget identity and widget deletion) are the most relevant when dynamically changing widgets or working with multi-page applications. This is covered in detail later in this guide: Statefulness of widgets and Widget life cycle.

There are four parts to keep in mind when using widgets:

Widget states are dependent on a particular session (browser connection). The actions of one user do not affect the widgets of any other user. Furthermore, if a user opens up multiple tabs to access an app, each tab will be a unique session. Changing a widget in one tab will not affect the same widget in another tab.

The value of a widget as seen through st.session_state and returned by the widget function are of simple Python types. For example, st.button returns a boolean value and will have the same boolean value saved in st.session_state if using a key. The first time a widget function is called (before a user interacts with it), it will return its default value. (e.g. st.selectbox returns the first option by default.) Default values are configurable for all widgets with a few special exceptions like st.button and st.file_uploader.

Widget keys serve two purposes:

Whenever possible, Streamlit updates widgets incrementally on the frontend instead of rebuilding them with each rerun. This means Streamlit assigns an ID to each widget from the arguments passed to the widget function. A widget's ID is based on parameters such as label, min or max value, default value, placeholder text, help text, and key. The page where the widget appears also factors into a widget's ID. If you have two widgets of the sa

*[Content truncated]*

---

## Working with connections, secrets, and user authentication - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/connections

**Contents:**
- Working with connections, secrets, and user authentication
      - Connecting to data
      - Secrets managements
      - Authentication and user information
      - Security reminders
  - Still have questions?

Connect your app to remote data or a third-party API.

Set up your development environement and design your app to handle secrets securely.

Use an OpenID Connect provider to authenticate users and personalize your app.

Check out a few reminders to follow best practices and avoid security mistakes.

Our forums are full of helpful information and Streamlit experts.

---

## Threading in Streamlit - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/design/multithreading

**Contents:**
- Multithreading in Streamlit
- Prerequisites
- When to use multithreading
- Threads created by Streamlit
- streamlit.errors.NoSessionContext
- Creating custom threads
  - Option 1: Do not use Streamlit commands within a custom thread
  - Option 2: Expose ScriptRunContext to the thread
    - Warning
  - Still have questions?

Multithreading is a type of concurrency, which improves the efficiency of computer programs. It's a way for processors to multitask. Streamlit uses threads within its architecture, which can make it difficult for app developers to include their own multithreaded processes. Streamlit does not officially support multithreading in app code, but this guide provides information on how it can be accomplished.

Multithreading is just one type of concurrency. Multiprocessing and coroutines are other forms of concurrency. You need to understand how your code is bottlenecked to choose the correct kind of concurrency.

Multiprocessing is inherently parallel, meaning that resources are split and multiple tasks are performed simultaneously. Therefore, multiprocessing is helpful with compute-bound operations. In contrast, multithreading and coroutines are not inherently parallel and instead allow resource switching. This makes them good choices when your code is stuck waiting for something, like an IO operation. AsyncIO uses coroutines and may be preferable with very slow IO operations. Threading may be preferable with faster IO operations. For a helpful guide to using AsyncIO with Streamlit, see this Medium article by Sehmi-Conscious Thoughts.

Don't forget that Streamlit has fragments and caching, too! Use caching to avoid unnecessarily repeating computations or IO operations. Use fragments to isolate a bit of code you want to update separately from the rest of the app. You can set fragments to rerun at a specified interval, so they can be used to stream updates to a chart or table.

Streamlit creates two types of threads in Python:

When a user connects to your app, this creates a new session and runs a script thread to initialize the app for that user. As the script thread runs, it renders elements in the user's browser tab and reports state back to the server. When the user interacts with the app, another script thread runs, re-rendering the elements in the browser tab and updating state on the server.

This is a simplifed illustration to show how Streamlit works:

Many Streamlit commands, including st.session_state, expect to be called from a script thread. When Streamlit is running as expected, such commands use the ScriptRunContext attached to the script thread to ensure they work within the intended session and update the correct user's view. When those Streamlit commands can't find any ScriptRunContext, they raise a streamlit.errors.NoSessionContext exception.

*[Content truncated]*

---

## Working with fragments - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/architecture/fragments

**Contents:**
- Working with fragments
- Use cases for fragments
- Defining and calling a fragment
  - Fragment execution flow
- Fragment return values and interacting with the rest of your app
- Automate fragment reruns
- Compare fragments to other Streamlit features
  - Fragments vs forms
  - Fragments vs callbacks
  - Fragments vs custom components

Reruns are a central part of every Streamlit app. When users interact with widgets, your script reruns from top to bottom, and your app's frontend is updated. Streamlit provides several features to help you develop your app within this execution model. Streamlit version 1.37.0 introduced fragments to allow rerunning a portion of your code instead of your full script. As your app grows larger and more complex, these fragment reruns help your app be efficient and performant. Fragments give you finer, easy-to-understand control over your app's execution flow.

Before you read about fragments, we recommend having a basic understanding of caching, Session State, and forms.

Fragments are versatile and applicable to a wide variety of circumstances. Here are just a few, common scenarios where fragments are useful:

Streamlit provides a decorator (st.fragment) to turn any function into a fragment function. When you call a fragment function that contains a widget function, a user triggers a fragment rerun instead of a full rerun when they interact with that fragment's widget. During a fragment rerun, only your fragment function is re-executed. Anything within the main body of your fragment is updated on the frontend, while the rest of your app remains the same. We'll describe fragments written across multiple containers later on.

Here is a basic example of defining and calling a fragment function. Just like with caching, remember to call your function after defining it.

If you want the main body of your fragment to appear in the sidebar or another container, call your fragment function inside a context manager.

Consider the following code with the explanation and diagram below.

When a user interacts with an input widget inside a fragment, only the fragment reruns instead of the full script. When a user interacts with an input widget outside a fragment, the full script reruns as usual.

If you run the code above, the full script will run top to bottom on your app's initial load. If you flip the toggle button in your running app, the first fragment (toggle_and_text()) will rerun, redrawing the toggle and text area while leaving everything else unchanged. If you click the checkbox, the second fragment (filter_and_file()) will rerun and consequently redraw the checkbox and file uploader. Everything else remains unchanged. Finally, if you click the update button, the full script will rerun, and Streamlit will redraw everything.

Streamlit ignores fragment return val

*[Content truncated]*

---

## Using custom Python classes in your Streamlit app - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/design/custom-classes

**Contents:**
- Using custom Python classes in your Streamlit app
- Patterns to define your custom classes
  - Pattern 1: Define your class in a separate module
    - Example: Move your class definition
  - Pattern 2: Force your class to compare internal values
    - Example: Define __eq__
  - Pattern 3: Store your class as serialized data
    - Example: Save your class instance as a string
  - Pattern 4: Use caching to preserve your class
- Understanding how Python defines and compares classes

If you are building a complex Streamlit app or working with existing code, you may have custom Python classes defined in your script. Common examples include the following:

Because Streamlit reruns your script after every user interaction, custom classes may be redefined multiple times within the same Streamlit session. This may result in unwanted effects, especially with class and instance comparisons. Read on to understand this common pitfall and how to avoid it.

We begin by covering some general-purpose patterns you can use for different types of custom classes, and follow with a few more technical details explaining why this matters. Finally, we go into more detail about Using Enum classes specifically, and describe a configuration option which can make them more convenient.

This is the recommended, general solution. If possible, move class definitions into their own module file and import them into your app script. As long as you are not editing the files that define your app, Streamlit will not re-import those classes with each rerun. Therefore, if a class is defined in an external file and imported into your script, the class will not be redefined during the session, unless you are actively editing your app.

Try running the following Streamlit app where MyClass is defined within the page's script. isinstance() will return True on the first script run then return False on each rerun thereafter.

If you move the class definition out of app.py into another file, you can make isinstance() consistently return True. Consider the following file structure:

Streamlit only reloads code in imported modules when it detects the code has changed. Thus, if you are actively editing your app code, you may need to start a new session or restart your Streamlit server to avoid an undesirable class redefinition.

For classes that store data (like dataclasses), you may be more interested in comparing the internally stored values rather than the class itself. If you define a custom __eq__ method, you can force comparisons to be made on the internally stored values.

Try running the following Streamlit app and observe how the comparison is True on the first run then False on every rerun thereafter.

Since MyDataclass gets redefined with each rerun, the instance stored in Session State will not be equal to any instance defined in a later script run. You can fix this by forcing a comparison of internal values as follows:

The default Python __eq__ implementation for a r

*[Content truncated]*

---

## App testing example - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/app-testing/examples

**Contents:**
- App testing example
- Testing a login page
  - Project summary
    - Login page behavior
    - Login page project structure
    - Login page Python file
    - Login page test file
  - Automating your tests
  - Still have questions?

Let's consider a login page. In this example, secrets.toml is not present. We'll manually declare dummy secrets directly in the tests. To avoid timing attacks, the login script uses hmac to compare a user's password to the secret value as a security best practice.

Before diving into the app's code, let's think about what this page is supposed to do. Whether you use test-driven development or you write unit tests after your code, it's a good idea to think about the functionality that needs to be tested. The login page should behave as follows:

The user's status mentioned in the page's specifications are encoded in st.session_state.status. This value is initialized at the beginning of the script as "unverified" and is updated through a callback when the password prompt receives a new entry.

These tests closely follow the app's specifications above. In each test, a dummy secret is set before running the app and proceeding with further simulations and checks.

See how Session State was modified in the last test? Instead of fully simulating a user logging in, the test jumps straight to a logged-in state by setting at.session_state["status"] = "verified". After running the app, the test proceeds to simulate the user logging out.

If myproject/ was pushed to GitHub as a repository, you could add GitHub Actions test automation with Streamlit App Action. This is as simple as adding a workflow file at myproject/.github/workflows/:

Our forums are full of helpful information and Streamlit experts.

---

## User authentication and information - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/connections/authentication

**Contents:**
- User authentication and information
- OpenID Connect
- st.login(), st.user, and st.logout()
- User cookies and logging out
- Setting up an identity provider
- Configure your OIDC connection in Streamlit
- A simple example
- Using multiple OIDC providers
- Passing keywords to your identity provider
    - Note

Personalizing your app for your users is a great way to make your app more engaging.

User authentication and personalization unlocks a plethora of use cases for developers, including controls for admins, a personalized stock ticker, or a chatbot app with a saved history between sessions.

Before reading this guide, you should have a basic understanding of secrets management.

Streamlit supports user authentication with OpenID Connect (OIDC), which is an authentication protocol built on top of OAuth 2.0. OIDC supports authentication, but not authorization: that is, OIDC connections tell you who a user is (authentication), but don't give you the authority to impersonate them (authorization). If you need to connect with a generic OAuth 2.0 provider or have your app to act on behalf of a user, consider using or creating a custom component.

Some popular OIDC providers are:

There are three commands involved with user authentication:

Streamlit checks for the identity cookie at the beginning of each new session. If a user logs in to your app in one tab and then opens a new tab, they will automatically be logged in to your app in the new tab. When you call st.logout() in a user session, Streamlit removes the identity cookie and starts a new session. This logs the user out from the current session. However, if they were logged in to other sessions already, they will remain logged in within those sessions. The information in st.user is updated at the beginning of a session (which is why st.login() and st.logout() both start new sessions after saving or deleting the identity cookie).

If a user closes your app without logging out, the identity cookie will expire after 30 days. This expiration time is not configurable and is not tied to any expiration time that may be returned in your user's identity token. If you need to prevent persistent authentication in your app, check the expiration information returned by the identity provider in st.user and manually call st.logout() when needed.

Streamlit does not modify or delete any cookies saved directly by your identity provider. For example, if you use Google as your identity provider and a user logs in to your app with Google, they will remain logged in to their Google account after they log out of your app with st.logout().

In order to use an identity provider, you must first configure your identity provider through an admin account. This typically involves setting up a client or application within the identity pro

*[Content truncated]*

---

## Theming - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/configuration/theming

**Contents:**
- Theming overview
- Example themes
- Working with theme configuration during development
  - Still have questions?

In this guide, we provide an overview of theming and visual customization of Streamlit apps. Streamlit themes are defined using configuration options, which are most commonly defined in a .streamlit/config.toml file. For more information about setting configuration options, see Working with configuration options. For a complete list of configuration options and definitions, see the API reference for config.toml.

The following options can be set in the [theme] table of config.toml and can't be set separately in the [theme.sidebar] table:

The following options can be configured separately for the main body of your app and the sidebar:

The following light theme is inspired by Anthropic.

The following dark theme is inspired by Spotify.

Most theme configuration options can be updated while an app is running. This makes it easy to iterate on your custom theme. If you change your app's primary color, save your config.toml file, and rerun your app, you will immediately see the new color. However, some configuration options (like [[theme.fontFace]]) require you to restart the Streamlit server to reflect the updates. If in doubt, when updating your app's configuration, stop the Streamlit server in your terminal and restart your app with the streamlit run command.

Our forums are full of helpful information and Streamlit experts.

---

## Button behavior and examples - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/design/buttons

**Contents:**
- Button behavior and examples
- Summary
- When to use if st.button()
- Common logic with buttons
  - Show a temporary message with a button
  - Stateful button
  - Toggle button
  - Buttons to continue or control stages of a process
  - Buttons to modify st.session_state
    - A slight problem

Buttons created with st.button do not retain state. They return True on the script rerun resulting from their click and immediately return to False on the next script rerun. If a displayed element is nested inside if st.button('Click me'):, the element will be visible when the button is clicked and disappear as soon as the user takes their next action. This is because the script reruns and the button return value becomes False.

In this guide, we will illustrate the use of buttons and explain common misconceptions. Read on to see a variety of examples that expand on st.button using st.session_state. Anti-patterns are included at the end. Go ahead and pull up your favorite code editor so you can streamlit run the examples as you read. Check out Streamlit's Basic concepts if you haven't run your own Streamlit scripts yet.

When code is conditioned on a button's value, it will execute once in response to the button being clicked and not again (until the button is clicked again).

Good to nest inside buttons:

Bad to nest inside buttons:

* This can be appropriate when disposable results are desired. If you have a "Validate" button, that could be a process conditioned directly on a button. It could be used to create an alert to say 'Valid' or 'Invalid' with no need to keep that info.

If you want to give the user a quick button to check if an entry is valid, but not keep that check displayed as the user continues.

In this example, a user can click a button to check if their animal string is in the animal_shelter list. When the user clicks "Check availability" they will see "We have that animal!" or "We don't have that animal." If they change the animal in st.text_input, the script reruns and the message disappears until they click "Check availability" again.

Note: The above example uses magic to render the message on the frontend.

If you want a clicked button to continue to be True, create a value in st.session_state and use the button to set that value to True in a callback.

If you want a button to work like a toggle switch, consider using st.checkbox. Otherwise, you can use a button with a callback function to reverse a boolean value saved in st.session_state.

In this example, we use st.button to toggle another widget on and off. By displaying st.slider conditionally on a value in st.session_state, the user can interact with the slider without it disappearing.

Alternatively, you can use the value in st.session_state on the slider's disabled parameter.


*[Content truncated]*

---

## Static file serving - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/configuration/serving-static-files

**Contents:**
- Static file serving
- Details on usage
- Example usage
  - Still have questions?

Streamlit apps can host and serve small, static media files to support media embedding use cases that won't work with the normal media elements.

To enable this feature, set enableStaticServing = true under [server] in your config file, or environment variable STREAMLIT_SERVER_ENABLE_STATIC_SERVING=true.

Media stored in the folder ./static/ relative to the running app file is served at path app/static/[filename], such as http://localhost:8501/app/static/cat.png.

Additional resources:

Our forums are full of helpful information and Streamlit experts.

---

## Caching overview - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/architecture/caching

**Contents:**
- Caching overview
- Minimal example
- Basic usage
  - st.cache_data
    - Usage
    - Behavior
    - Warning
    - Examples
    - Tip
  - st.cache_resource

Streamlit runs your script from top to bottom at every user interaction or code change. This execution model makes development super easy. But it comes with two major challenges:

But don't worry! Streamlit lets you tackle both issues with its built-in caching mechanism. Caching stores the results of slow function calls, so they only need to run once. This makes your app much faster and helps with persisting objects across reruns. Cached values are available to all users of your app. If you need to save results that should only be accessible within a session, use Session State instead.

To cache a function in Streamlit, you must decorate it with one of two decorators (st.cache_data or st.cache_resource):

In this example, decorating long_running_function with @st.cache_data tells Streamlit that whenever the function is called, it checks two things:

If this is the first time Streamlit sees these parameter values and function code, it runs the function and stores the return value in a cache. The next time the function is called with the same parameters and code (e.g., when a user interacts with the app), Streamlit will skip executing the function altogether and return the cached value instead. During development, the cache updates automatically as the function code changes, ensuring that the latest changes are reflected in the cache.

As mentioned, there are two caching decorators:

Streamlit's two caching decorators and their use cases.

st.cache_data is your go-to command for all functions that return data – whether DataFrames, NumPy arrays, str, int, float, or other serializable types. It's the right command for almost all use cases! Within each user session, an @st.cache_data-decorated function returns a copy of the cached return value (if the value is already cached).

Let's look at an example of using st.cache_data. Suppose your app loads the Uber ride-sharing dataset – a CSV file of 50 MB – from the internet into a DataFrame:

Running the load_data function takes 2 to 30 seconds, depending on your internet connection. (Tip: if you are on a slow connection, use this 5 MB dataset instead). Without caching, the download is rerun each time the app is loaded or with user interaction. Try it yourself by clicking the button we added! Not a great experience… 😕

Now let's add the @st.cache_data decorator on load_data:

Run the app again. You'll notice that the slow download only happens on the first run. Every subsequent rerun should be almost instant! 💨

How

*[Content truncated]*

---

## Multipage apps - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/multipage-apps

**Contents:**
- Multipage apps
      - Overview of multipage apps
      - Define multipage apps with st.Page and st.navigation
      - Creating multipage apps using the pages/ directory
      - Working with widgets in multipage apps
  - Still have questions?

Streamlit provides multiple ways to define multipage apps. Understand the terminology and basic comparison between methods.

Learn about the preferred method for defining multipage apps. st.Page and st.navigation give you flexibility to organize your project directory and label your pages as you please.

Define your multipage apps through directory structure. Place additional Python files in a pages/ directory alongside your entrypoint file and pages are automatically shown in a navigation widget inside your app's sidebar.

Understand how widget identity is tied to pages. Learn strategies to get the behavior you want out of widgets.

Our forums are full of helpful information and Streamlit experts.

---

## Add statefulness to apps - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/architecture/session-state

**Contents:**
- Add statefulness to apps
- What is State?
- Build a Counter
  - Initialization
  - Reads and updates
  - Example 1: Add Session State
  - Example 2: Session State and Callbacks
  - Example 3: Use args and kwargs in Callbacks
  - Example 4: Forms and Callbacks
- Advanced concepts

We define access to a Streamlit app in a browser tab as a session. For each browser tab that connects to the Streamlit server, a new session is created. Streamlit reruns your script from top to bottom every time you interact with your app. Each reruns takes place in a blank slate: no variables are shared between runs.

Session State is a way to share variables between reruns, for each user session. In addition to the ability to store and persist state, Streamlit also exposes the ability to manipulate state using Callbacks. Session state also persists across pages inside a multipage app.

In this guide, we will illustrate the usage of Session State and Callbacks as we build a stateful Counter app.

For details on the Session State and Callbacks API, please refer to our Session State API Reference Guide.

Also, check out this Session State basics tutorial video by Streamlit Developer Advocate Dr. Marisa Smith to get started:

Let's call our script counter.py. It initializes a count variable and has a button to increment the value stored in the count variable:

No matter how many times we press the Increment button in the above app, the count remains at 1. Let's understand why:

As we'll see later, we can avoid this issue by storing count as a Session State variable. By doing so, we're indicating to Streamlit that it should maintain the value stored inside a Session State variable across app reruns.

Let's learn more about the API to use Session State.

The Session State API follows a field-based API, which is very similar to Python dictionaries:

Read the value of an item in Session State by passing the item to st.write :

Update an item in Session State by assigning it a value:

Streamlit throws an exception if an uninitialized variable is accessed:

Let's now take a look at a few examples that illustrate how to add Session State to our Counter app.

Now that we've got a hang of the Session State API, let's update our Counter app to use Session State:

As you can see in the above example, pressing the Increment button updates the count each time.

Now that we've built a basic Counter app using Session State, let's move on to something a little more complex. The next example uses Callbacks with Session State.

Callbacks: A callback is a Python function which gets called when an input widget changes. Callbacks can be used with widgets using the parameters on_change (or on_click), args, and kwargs. The full Callbacks API can be found in our Session State API R

*[Content truncated]*

---

## App design concepts and considerations - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/design

**Contents:**
- App design concepts and considerations
      - Animate and update elements
      - Button behavior and examples
      - Dataframes
      - Using custom Python classes in your Streamlit app
      - Multithreading
      - Working with timezones
  - Still have questions?

Understand how to create dynamic, animated content or update elements without rerunning your app.

Understand how buttons work with explanations and examples to avoid common mistakes.

Dataframes are a great way to display and edit data in a tabular format. Understand the UI and options available in Streamlit.

Understand the impact of defining your own Python classes within Streamlit's rerun model.

Understand how to use multithreading within Streamlit apps.

Understand how to localize time to your users.

Our forums are full of helpful information and Streamlit experts.

---

## The app chrome - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/architecture/app-chrome

**Contents:**
- The app chrome
- Menu options
  - Rerun
  - Settings
    - Theme settings
  - Print
  - Record a screencast
  - About
- Developer options
  - Clear cache

Your Streamlit app has a few widgets in the top right to help you as you develop. These widgets also help your viewers as they use your app. We call this things “the app chrome”. The chrome includes a status area, toolbar, and app menu.

Your app menu is configurable. By default, you can access developer options from the app menu when viewing an app locally or on Streamlit Community Cloud while logged into an account with administrative access. While viewing an app, click the icon in the upper-right corner to access the menu.

The menu is split into two sections. The upper section contains options available to all viewers and the lower section contains options for developers. Read more about customizing this menu at the end of this page.

You can manually trigger a rerun of your app by clicking "Rerun" from the app menu. This rerun will not reset your session. Your widget states and values stored in st.session_state will be preserved. As a shortcut, without opening the app menu, you can rerun your app by pressing "R" on your keyboard (if you aren't currently focused on an input element).

With the "Settings" option, you can control the appearance of your app while it is running. If viewing the app locally, you can set how your app responds to changes in your source code. See more about development flow in Basic concepts. You can also force your app to appear in wide mode, even if not set within the script using st.set_page_config.

After clicking "Settings" from the app menu, you can choose between "Light", "Dark", or "Use system setting" for the app's base theme. Click "Edit active theme" to modify the theme, color-by-color.

Click "Print" or use keyboard shortcuts (⌘+P or Ctrl+P) to open a print dialog. This option uses your browser's built-in print-to-pdf function. To modify the appearance of your print, you can do the following:

You can easily make screen recordings right from your app! Screen recording is supported in the latest versions of Chrome, Edge, and Firefox. Ensure your browser is up-to-date for compatibility. Depending on your current settings, you may need to grant permission to your browser to record your screen or to use your microphone if recording a voiceover.

The whole process looks like this:

You can conveniently check what version of Streamlit is running from the "About" option. Developers also have the option to customize the message shown here using st.set_page_config.

By default, developer options only show when viewing an app

*[Content truncated]*

---

## Deployment concepts - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/concepts

**Contents:**
- Deployment concepts
  - Still have questions?

Learn the fundamental concepts of app deployment. There are three main processes involved in deploying apps.

If you're using Streamlit Community Cloud, we'll do most of the work for you!

Dependencies. Understand the basics of configuring your deployment environment.

Secrets. Understand the basics of secret management.

Our forums are full of helpful information and Streamlit experts.

---

## Customize fonts - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/configuration/theming-customize-fonts

**Contents:**
- Customize fonts in your Streamlit app
- Default Streamlit fonts
- Externally hosted fonts
    - Important
- Hosting alternative fonts
    - Important
    - Note
  - Example 1: Define an alternative font with variable font files
  - Example 2: Define an alternative font with static font files
- Font fallbacks

Streamlit lets you change and customize the fonts in your app. You can load font files from a public URL or host them with your app using static file serving.

Streamlit comes with Source Sans, Source Serif, and Source Code fonts. These font files are included with the Streamlit library so clients don't download them from a third party. By default, Streamlit uses Source Sans for all text except inline code and code blocks, which use Source Code instead.

To use these default faults, you can set each of the following configuration options to "sans-serif" (Source Sans), "serif" (Source Serif), or "monospace" (Source Code) in config.toml:

You can set the base font weight and size in the [theme] table in config.toml. These can't be configured separately in the sidebar.

The following configuration options can be set separately for the sidebar by using the [theme.sidebar] table instead of the [theme] table in config.toml:

When fonts are not declared in [theme.sidebar], Streamlit will inherit each option from [theme] before defaulting to less specific options. For example, if theme.sidebar.headingFont is not set, Streamlit uses (in order of precedence) theme.headingFont, theme.sidebar.font, or theme.font instead.

In the following config.toml example, Streamlit uses Source Serif in the main body of the app and Source Sans in the sidebar.

If you use a font service like Google Fonts or Adobe Fonts, you can use those fonts directly by encoding their font family (name) and CSS URL into a single string of the form {font_name}:{css_url}. If your font family includes a space, use inner quotes on the font family. In the following config.toml example, Streamlit uses Nunito font for all text except code, which is Space Mono instead. Space Mono has inner quotes because it has a space.

If you configure your app to include any third-party integrations, including externally hosted fonts, your app may transmit user data (for example, IP addresses) to external servers. As the app developer, you are solely responsible for notifying your users about these third-party integrations, providing access to relevant privacy policies, and ensuring compliance with all applicable data protection laws and regulations.

If you have font files that you want to host with your app, you must declare the font in config.toml under [[theme.fontFaces]]. For multiple alternative fonts, declare multiple [[theme.fontFaces]] tables in your configuration file. You can self-host your font by using Str

*[Content truncated]*

---

## Colors and borders - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/configuration/theming-customize-colors-and-borders

**Contents:**
- Customize colors and borders in your Streamlit app
- Color values
    - Tip
- Default Streamlit colors
- Color and border configuration options
  - Basic color palette
  - primaryColor
    - Tip
    - Example 1: Primary color
  - backgroundColor, secondaryBackgroundColor, codeBackgroundColor, and dataframeHeaderBackgroundColor

For all configuration options that accept a color, you can specify the value with one of the following strings:

Although you can specify an alpha value for your colors, this isn't necessary for most options. Streamlit adjusts the alpha value of colors to ensure contextually appropriate shading between background and foreground.

Streamlit comes with two preconfigured themes: light and dark. If you don't specify any theme configuration options, Streamlit will attempt to use the preconfigured theme that best matches each user's browser settings. These themes feature a red primary color in addition to a basic color palette (red, orange, yellow, green, blue, violet, and gray/grey) for elements like colored Markdown text.

Most theme configuration options can be set for your whole app, but you can override some with a different value for the sidebar. For example, your app's primary color (primaryColor) is used to highlight interactive elements and show focus. If you set theme.primaryColor, this will change the primary color for your whole app. However, if you set theme.sidebar.primaryColor, this will override theme.primaryColor in the sidebar, allowing you to use two different primary colors.

The following two configuration options can only be applied to the whole app:

The following configuration options can be set separately for the sidebar by using the [theme.sidebar] table instead of the [theme] table in config.toml:

For brevity, on the rest of this page, theming configuration options will not include the theme. or theme.sidebar. prefix.

Various elements in Streamlit use or let you choose from a predefined palette of colors: red, orange, yellow, green, blue, violet, and gray/grey. These are some of the elements that use this basic color palette:

For each color in the palette, you can define a base color, background color, and text color. If you only define a base color, Streamlit adjusts lightness/darkness and opacity to automatically provide a corresponding background and text color. However, you can manually define each of them, too. These are the color palette options:

primaryColor defines the accent color most often used throughout your Streamlit app. The following features and effects use your primary color:

When your primary color is used as a background, Streamlit changes the text color to white. For example, this happens for type="primary" buttons and for selected items in st.multiselect.

For legibility, always choose a primary color that is

*[Content truncated]*

---

## Create a Component - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/custom-components/create

**Contents:**
- Create a Component
    - Note
- Part 1: Setup and Architecture
- Part 2: Make a Slider Widget
  - Still have questions?

If you are only interested in using Streamlit Components, then you can skip this section and head over to the Streamlit Components Gallery to find and install components created by the community!

Developers can write JavaScript and HTML "components" that can be rendered in Streamlit apps. Streamlit Components can receive data from, and also send data to, Streamlit Python scripts.

Streamlit Components let you expand the functionality provided in the base Streamlit package. Use Streamlit Components to create the needed functionality for your use-case, then wrap it up in a Python package and share with the broader Streamlit community!

With Streamlit Components you can add new features to your app in the following ways:

Check out these Streamlit Components tutorial videos by Streamlit engineer Tim Conkling to get started:

Our forums are full of helpful information and Streamlit experts.

---

## Secrets management - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/connections/secrets-management

**Contents:**
- Secrets management
    - Note
- How to use secrets management
  - Develop locally and set up secrets
    - Important
  - Use secrets in your app
    - Tip
  - Error handling
  - Use secrets on Streamlit Community Cloud
  - Still have questions?

Storing unencrypted secrets in a git repository is a bad practice. For applications that require access to sensitive credentials, the recommended solution is to store those credentials outside the repository - such as using a credentials file not committed to the repository or passing them as environment variables.

Streamlit provides native file-based secrets management to easily store and securely access your secrets in your Streamlit app.

Existing secrets management tools, such as dotenv files, AWS credentials files, Google Cloud Secret Manager, or Hashicorp Vault, will work fine in Streamlit. We just add native secrets management for times when it's useful.

Streamlit provides two ways to set up secrets locally using TOML format:

In a global secrets file at ~/.streamlit/secrets.toml for macOS/Linux or %userprofile%/.streamlit/secrets.toml for Windows:

If you use the global secrets file, you don't have to duplicate secrets across several project-level files if multiple Streamlit apps share the same secrets.

In a per-project secrets file at $CWD/.streamlit/secrets.toml, where $CWD is the folder you're running Streamlit from. If both a global secrets file and a per-project secrets file exist, secrets in the per-project file overwrite those defined in the global file.

Add this file to your .gitignore so you don't commit your secrets!

Access your secrets by querying the st.secrets dict, or as environment variables. For example, if you enter the secrets from the section above, the code below shows you how to access them within your Streamlit app.

You can access st.secrets via attribute notation (e.g. st.secrets.key), in addition to key notation (e.g. st.secrets["key"]) — like st.session_state.

You can even compactly use TOML sections to pass multiple secrets as a single attribute. Consider the following secrets:

Rather than passing each secret as attributes in a function, you can more compactly pass the section to achieve the same result. See the notional code below, which uses the secrets above:

Here are some common errors you might encounter when using secrets management.

If a .streamlit/secrets.toml is created while the app is running, the server needs to be restarted for changes to be reflected in the app.

If you try accessing a secret, but no secrets.toml file exists, Streamlit will raise a FileNotFoundError exception:

If you try accessing a secret that doesn't exist, Streamlit will raise a KeyError exception:

When you deploy your app to S

*[Content truncated]*

---

## Intro to custom components - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/custom-components/intro

**Contents:**
- Intro to custom components
- Create a static component
  - Render an HTML string
  - Render an iframe URL
- Create a bi-directional component
  - Development Environment Setup
  - Frontend
    - Note
    - React
    - TypeScript-only

The first step in developing a Streamlit Component is deciding whether to create a static component (i.e. rendered once, controlled by Python) or to create a bi-directional component that can communicate from Python to JavaScript and back.

If your goal in creating a Streamlit Component is solely to display HTML code or render a chart from a Python visualization library, Streamlit provides two methods that greatly simplify the process: components.html() and components.iframe().

If you are unsure whether you need bi-directional communication, start here first!

While st.text, st.markdown and st.write make it easy to write text to a Streamlit app, sometimes you'd rather implement a custom piece of HTML. Similarly, while Streamlit natively supports many charting libraries, you may want to implement a specific HTML/JavaScript template for a new charting library. components.html works by giving you the ability to embed an iframe inside of a Streamlit app that contains your desired output.

components.iframe is similar in features to components.html, with the difference being that components.iframe takes a URL as its input. This is used for situations where you want to include an entire page within a Streamlit app.

A bi-directional Streamlit Component has two parts:

To make the process of creating bi-directional Streamlit Components easier, we've created a React template and a TypeScript-only template in the Streamlit Component-template GitHub repo. We also provide some example Components in the same repo.

To build a Streamlit Component, you need the following installed in your development environment:

Clone the component-template GitHub repo, then decide whether you want to use the React.js ("template") or plain TypeScript ("template-reactless") template.

Initialize and build the component template frontend from the terminal:

From a separate terminal, run the Streamlit app (Python) that declares and uses the component:

After running the steps above, you should see a Streamlit app in your browser that looks like this:

The example app from the template shows how bi-directional communication is implemented. The Streamlit Component displays a button (Python → JavaScript), and the end-user can click the button. Each time the button is clicked, the JavaScript front-end increments the counter value and passes it back to Python (JavaScript → Python), which is then displayed by Streamlit (Python → JavaScript).

Because each Streamlit Component is its own webpag

*[Content truncated]*

---

## Managing dependencies when deploying your app - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/concepts/dependencies

**Contents:**
- Managing dependencies when deploying your app
- Install Python and other software
- Install Python packages
  - pip and requirements.txt
    - Tip
  - Still have questions?

Before you began developing your app, you set up and configured your development environment by installing Python and Streamlit. When you deploy your app, you need to set up and configure your deployment environment in the same way. When you deploy your app to a cloud service, your app's Python server will be running on a remote machine. This remote machine will not have access all the files and programs on your personal computer.

All Streamlit apps have at least two dependencies: Python and Streamlit. Your app may have additional dependencies in the form of Python packages or software that must be installed to properly execute your script. If you are using a service like Streamlit Community Cloud which is designed for Streamlit apps, we'll take care of Python and Streamlit for you!

If you are using Streamlit Community Cloud, Python is already installed. You can just pick the version in the deployment dialog. If you need to install Python yourself or you have other non-Python software to install, follow your platform's instructions to install additional software. You will commonly use a package management tool to do this. For example, Streamlit Community Cloud uses Advanced Package Tool (apt) for Debian-based Linux systems. For more information about installing non-Python depencies on Streamlit Community Cloud, see apt-get dependencies.

Once you have Python installed in your deployment environment, you'll need to install all the necessary Python packages, including Streamlit! With each import of an installed package, you add a Python dependency to your script. You need to install those dependencies in your deployment environment through a Python package manager.

If you are using Streamlit Community Cloud, you'll have the latest version of Streamlit and all of its dependencies installed by default. So, if you're making a simple app and don't need additional dependencies, you won't have to do anything at all!

Since pip comes by default with Python, the most common way to configure your Python environment is with a requirements.txt file. Each line of a requirements.txt file is a package to pip install. You should not include built-in Python libraries like math, random, or distutils in your requirements.txt file. These are a part of Python and aren't installed separately.

Since dependencies may rely on a specific version of Python, always be aware of the Python version used in your development environment, and select the same version for your deployment 

*[Content truncated]*

---

## Working with timezones - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/design/timezone-handling

**Contents:**
- Working with timezones
- How Streamlit handles timezones
  - datetime instance without a timezone (naive)
  - datetime instance with a timezone
    - Note
  - Still have questions?

In general, working with timezones can be tricky. Your Streamlit app users are not necessarily in the same timezone as the server running your app. It is especially true of public apps, where anyone in the world (in any timezone) can access your app. As such, it is crucial to understand how Streamlit handles timezones, so you can avoid unexpected behavior when displaying datetime information.

Streamlit always shows datetime information on the frontend with the same information as its corresponding datetime instance in the backend. I.e., date or time information does not automatically adjust to the users' timezone. We distinguish between the following two cases:

When you provide a datetime instance without specifying a timezone, the frontend shows the datetime instance without timezone information. For example (this also applies to other widgets like st.dataframe):

Users of the above app always see the output as 2020-01-10 10:30:00.

When you provide a datetime instance and specify a timezone, the frontend shows the datetime instance in that same timezone. For example (this also applies to other widgets like st.dataframe):

Users of the above app always see the output as 2020-01-10 10:30:00-05:00.

In both cases, neither the date nor time information automatically adjusts to the users' timezone on the frontend. What users see is identical to the corresponding datetime instance in the backend. It is currently not possible to automatically adjust the date or time information to the timezone of the users viewing the app.

The legacy version of the st.dataframe has issues with timezones. We do not plan to roll out additional fixes or enhancements for the legacy dataframe. If you need stable timezone support, please consider switching to the arrow serialization by changing the config setting, config.dataFrameSerialization = "arrow".

Our forums are full of helpful information and Streamlit experts.

---

## Dataframes - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/design/dataframes

**Contents:**
- Dataframes
- Display dataframes with st.dataframe
- st.dataframe UI features
- Edit data with st.data_editor
- st.data_editor UI features
  - Add and delete rows
  - Copy and paste support
    - Note
    - Tip
  - Access edited data

Dataframes are a great way to display and edit data in a tabular format. Working with Pandas DataFrames and other tabular data structures is key to data science workflows. If developers and data scientists want to display this data in Streamlit, they have multiple options: st.dataframe and st.data_editor. If you want to solely display data in a table-like UI, st.dataframe is the way to go. If you want to interactively edit data, use st.data_editor. We explore the use cases and advantages of each option in the following sections.

Streamlit can display dataframes in a table-like UI via st.dataframe :

st.dataframe provides additional functionality by using glide-data-grid under the hood:

Try out all the UI features using the embedded app from the prior section.

In addition to Pandas DataFrames, st.dataframe also supports other common Python types, e.g., list, dict, or numpy array. It also supports Snowpark and PySpark DataFrames, which allow you to lazily evaluate and pull data from databases. This can be useful for working with large datasets.

Streamlit supports editable dataframes via the st.data_editor command. Check out its API in st.data_editor. It shows the dataframe in a table, similar to st.dataframe. But in contrast to st.dataframe, this table isn't static! The user can click on cells and edit them. The edited data is then returned on the Python side. Here's an example:

Try it out by double-clicking on any cell. You'll notice you can edit all cell values. Try editing the values in the rating column and observe how the text output at the bottom changes:

st.data_editor also supports a few additional things:

With st.data_editor, viewers can add or delete rows via the table UI. This mode can be activated by setting the num_rows parameter to "dynamic":

The data editor supports pasting in tabular data from Google Sheets, Excel, Notion, and many other similar tools. You can also copy-paste data between st.data_editor instances. This functionality, powered by the Clipboard API, can be a huge time saver for users who need to work with data across multiple platforms. To try it out:

Every cell of the pasted data will be evaluated individually and inserted into the cells if the data is compatible with the column type. For example, pasting in non-numerical text data into a number column will be ignored.

If you embed your apps with iframes, you'll need to allow the iframe to access the clipboard if you want to use the copy-paste functionality. To do so,

*[Content truncated]*

---

## Configure and customize your app - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/configuration

**Contents:**
- Configure and customize your app
      - Configuration options
      - HTTPS support
      - Static file serving
- Theming
      - Theming
      - Customize colors and borders
      - Customize fonts
  - Still have questions?

Understand the types of options available to you through Streamlit configuration.

Understand how to configure SSL and TLS for your Streamlit app.

Understand how to host files alongside your app to make them accessible by URL. Use this if you want to point to files with raw HTML.

Understand how you can use theming configuration options to customize the appearance of your app.

Understand the configuration options for customizing your app's color scheme.

Understand the configuration options for customizing your app's font.

Our forums are full of helpful information and Streamlit experts.

---
