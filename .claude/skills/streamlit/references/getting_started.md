# Streamlit - Getting Started

**Pages:** 26

---

## Get started with app testing - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/concepts/app-testing/get-started

**Contents:**
- Get started with app testing
- A simple testing example with pytest
  - How pytest is structured
  - Example project with app testing
  - Try out a simple test with pytest
  - Handling file paths and imports with pytest
- Fundamentals of app testing
  - How to initialize and run a simulated app
  - How to retrieve elements
    - Retrieve elements by index

This guide will cover a simple example of how tests are structured within a project and how to execute them with pytest. After seeing the big picture, keep reading to learn about the Fundamentals of app testing:

Streamlit's app testing framework is not tied to any particular testing tool, but we'll use pytest for our examples since it is one of the most common Python test frameworks. To try out the examples in this guide, be sure to install pytest into your Streamlit development environment before you begin:

This section explains how a simple test is structured and executed with pytest. For a comprehensive introduction to pytest, check out Real Python's guide to Effective Python testing with pytest.

pytest uses a naming convention for files and functions to execute tests conveniently. Name your test scripts of the form test_<name>.py or <name>_test.py. For example, you can use test_myapp.py or myapp_test.py. Within your test scripts, each test is written as a function. Each function is named to begin or end with test. We will prefix all our test scripts and test functions with test_ for our examples in this guide.

You can write as many tests (functions) within a single test script as you want. When calling pytest in a directory, all test_<name>.py files within it will be used for testing. This includes files within subdirectories. Each test_<something> function within those files will be executed as a test. You can place test files anywhere in your project directory, but it is common to collect tests into a designated tests/ directory. For other ways to structure and execute tests, check out How to invoke pytest in the pytest docs.

Consider the following project:

Let's take a quick look at what's in this app and test before we run it. The main app file (app.py) contains four elements when rendered: st.title, st.number_input, st.button, and st.markdown. The test script (test_app.py) includes a single test (the function named test_increment_and_add). We'll cover test syntax in more detail in the latter half of this guide, but here's a brief explanation of what this test does:

Assertions are the heart of tests. When the assertion is true, the test passes. When the assertion is false, the test fails. A test can have multiple assertions, but keeping tests tightly focused is good practice. When tests focus on a single behavior, it is easier to understand and respond to failure.

The test should execute successfully. Your terminal should show something lik

*[Content truncated]*

---

## Connect your GitHub account - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/get-started/connect-your-github-account

**Contents:**
- Connect your GitHub account
    - Important
- Prerequisites
- Add access to public repositories
- Optional: Add access to private repositories
- Organization access
  - Organizations you own
  - Organizations owned by others
  - Previous or pending authorization
    - Approved access

Connecting GitHub to your Streamlit Community Cloud account allows you to deploy apps directly from the files you store in your repositories. It also lets the system check for updates to those files and automatically update your apps. When you first connect your GitHub account to your Community Cloud account, you'll be able to deploy apps from your public repositories to Community Cloud. If you want to deploy from private repositories, you can give Community Cloud additional permissions to do so. For more information about these permissions, see GitHub OAuth scope.

In order to deploy an app, you must have admin permissions to its repository. If you don't have admin access, contact the repository's owner or fork the repository to create your own copy. For more help, see our community forum.

If you are a member of a GitHub organization, that organization is displayed at the bottom of each GitHub OAuth prompt. In this case, we recommend reading about Organization access at the end of this page before performing the steps to connect your GitHub account. You must be an organization's owner in GitHub to grant access to that organization.

From the drop down, click "Connect GitHub account."

Enter your GitHub credentials and follow GitHub's authentication prompts.

Click "Authorize streamlit."

This adds the "Streamlit" OAuth application to your GitHub account. This allows Community Cloud to work with your public repositories and create codespaces for you. In the next section, you can allow Community Cloud to access your private repositories, too. For more information about using and reviewing the OAuth applications on your account, see Using OAuth apps in GitHub's docs.

After your Community Cloud account has access to deploy from your public repositories, you can follow these additional steps to grant access to your private repositories.

To deploy apps from repositories owned by a GitHub organization, Community Cloud must have permission to access the organization's repositories. If you are a member of a GitHub organization when you connect your GitHub account, your OAuth prompts will include a section labeled "Organization access."

If you have already connected your GitHub account and need to add access to an organization, follow the steps in Manage your GitHub connection to disconnect your GitHub account and start over. Alternatively, if you are not the owner of an organization, you can ask the owner to create a Community Cloud account for themselves and 

*[Content truncated]*

---

## Use Streamlit Playground in your browser - Streamlit Docs

**URL:** https://docs.streamlit.io/get-started/installation/streamlit-playground

**Contents:**
- Use Streamlit Playground in your browser
    - Important
- Prerequisites
- Go to the Playground
- Create a Hello World app
- What's next?
  - Still have questions?

The fastest way to try out Streamlit is to try out our Playground! Streamlit Playground runs in your browser. Just visit the Playground, and a limited version of Streamlit loads as browser scripts.

Enjoy the following conveniences:

Although the Playground has everything you need to get started, it doesn't contain the full version of Streamlit. To access the full awesomeness of Streamlit, see Install Streamlit using command line or Install Streamlit using Anaconda Distribution.

Because the Playground runs Streamlit locally in your browser, you should visit the Playground from a personal computer, not a mobile device.

Go to streamlit.io/playground.

Wait for the playground to load.

Behind the scenes, the site installs a browser-based version of Python and Streamlit. This can take as little as a few seconds. The setup time can vary depending on your machine and internet connection. When Streamlit is done loading, an example app is displayed in the right panel.

Optional: To view different examples, above the editor, select them from the examples list.

From the "EXAMPLES" list, select "Blank."

On the left, update the contents of the code editor to contain the following code:

A second or two after typing or pasting the code into the editor, the right panel will display the updated app. The code editor saves your edits whenever you pause from typing. Therefore, if you pause between keystrokes as you type a new line of code, you may see an error on the right because Streamlit executed an incomplete line. If this happens, just keep typing to complete the line(s) you are writing. When you pause again at the end of the line, Streamlit reruns the app.

On the left, change st.write to st.title so the code editor has the following code:

A second after you stop typing, Streamlit reruns the app and updates the display on the right.

Keep making changes! Watch as your edits are automatically saved and the new result is displayed on the right.

Option 1: If you're already intrigued and ready to install Streamlit on your computer, see one of the options to Install Streamlit on your machine.

Option 2: Otherwise, you can keep using the playground while you read about our Basic concepts and try out more commands in your app.

When you use the Streamlit Playground to work through the basic concepts, you can skip over any instructions to save your file or to select "Rerun on save." Streamlit Playground automatically saves your code when you pause from editing, as descr

*[Content truncated]*

---

## Additional Streamlit features - Streamlit Docs

**URL:** https://docs.streamlit.io/get-started/fundamentals/additional-features

**Contents:**
- Additional Streamlit features
- Theming
    - Note
    - Tip
- Pages
- Custom components
- Static file serving
- App testing
  - Still have questions?

So you've read all about Streamlit's Basic concepts and gotten a taste of caching and Session State in Advanced concepts. But what about the bells and whistles? Here's a quick look at some extra features to take your app to the next level.

Streamlit supports Light and Dark themes out of the box. Streamlit will first check if the user viewing an app has a Light or Dark mode preference set by their operating system and browser. If so, then that preference will be used. Otherwise, the Light theme is applied by default.

You can also change the active theme from "⋮" → "Settings".

Want to add your own theme to an app? The "Settings" menu has a theme editor accessible by clicking on "Edit active theme". You can use this editor to try out different colors and see your app update live.

When you're happy with your work, themes can be saved by setting config options in the [theme] config section. After you've defined a theme for your app, it will appear as "Custom Theme" in the theme selector and will be applied by default instead of the included Light and Dark themes.

More information about the options available when defining a theme can be found in the theme option documentation.

The theme editor menu is available only in local development. If you've deployed your app using Streamlit Community Cloud, the "Edit active theme" button will no longer be displayed in the "Settings" menu.

Another way to experiment with different theme colors is to turn on the "Run on save" option, edit your config.toml file, and watch as your app reruns with the new theme colors applied.

As apps grow large, it becomes useful to organize them into multiple pages. This makes the app easier to manage as a developer and easier to navigate as a user. Streamlit provides a powerful way to create multipage apps using st.Page and st.navigation. Just create your pages and connect them with navigation as follows:

Here's an example of a three-page app:

Now run streamlit run streamlit_app.py and view your shiny new multipage app! The navigation menu will automatically appear, allowing users to switch between pages.

Our documentation on Multipage apps teaches you how to add pages to your app, including how to define pages, structure and run multipage apps, and navigate between pages. Once you understand the basics, create your first multipage app!

If you can't find the right component within the Streamlit library, try out custom components to extend Streamlit's built-in functionality. Explo

*[Content truncated]*

---

## Get started with Streamlit Community Cloud - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/get-started

**Contents:**
- Get started with Streamlit Community Cloud
    - Quickstart
    - Trust and Security
  - Still have questions?

Welcome to Streamlit Community Cloud, where you can share your Streamlit apps with the world! Whether you've already created your first Streamlit app or you're just getting started, you're in the right place.

First things first, you need to create your Streamlit Community Cloud account to start deploying apps.

Create your account and deploy an example app as fast as possible. Jump right into coding with GitHub Codespaces.

Security first! If you want to read up on how we handle your data before you get started, we've got you covered.

If you're looking for help to build your first Streamlit app, read our Get started docs for the Streamlit library. If you want to fork an app and start with an example, check out our App gallery. Either way, it only takes a few minutes to create your first app.

If you're looking for more detailed instructions than the quickstart, try the following:

Create your account. See all the options and get complete explanations as you create your Streamlit Community Cloud account.

Connect your GitHub account. After your create your Community Cloud account, connect GitHub for source control.

Explore your workspace. Take a quick tour of your Community Cloud workspace. See where all the magic happens.

Deploy an app from a template. Use a template to get your own app up and running in minutes.

Fork and edit a public app. Start with a bang! Fork a public app and jump right into the code.

Our forums are full of helpful information and Streamlit experts.

---

## Install Streamlit - Streamlit Docs

**URL:** https://docs.streamlit.io/get-started/installation

**Contents:**
- Install Streamlit
    - Tip
- Summary for experienced Python developers
- Install Streamlit on your machine
  - Option 1: I like the command line
  - Option 2: I prefer a graphical interface
- Create an app in the cloud
  - Option 1: I want a free cloud environment
  - Option 2: I need something secure, controlled, and in the cloud
  - Still have questions?

There are multiple ways to set up your development environment and install Streamlit. Developing locally with Python installed on your own computer is the most common scenario.

Try a Streamlit Playground that runs in your browser — no installation required. (Note that this is not how Streamlit is meant to be used, because it has many downsides. That's why it's a playground!)

To set up your Python environment and test your installation, execute the following terminal commands:

Jump to our Basic concepts.

Install Streamlit on your own machine using tools like venv and pip.

Install Streamlit using the Anaconda Distribution graphical user interface. This is also the best approach if you're on Windows or don't have Python set up.

Use Streamlit Community Cloud with GitHub Codespaces so you don't have to go through the trouble of installing Python and setting up an environment.

Use Streamlit in Snowflake to code your apps in the cloud, right alongside your data with role-based access controls.

Our forums are full of helpful information and Streamlit experts.

---

## Install Streamlit using Anaconda Distribution - Streamlit Docs

**URL:** https://docs.streamlit.io/get-started/installation/anaconda-distribution

**Contents:**
- Install Streamlit using Anaconda Distribution
- Prerequisites
- Install Anaconda Distribution
- Create an environment using Anaconda Navigator
- Activate your environment
- Install Streamlit in your environment
- Create a Hello World app and run it
- What's next?
  - Still have questions?

This page walks you through installing Streamlit locally using Anaconda Distribution. At the end, you'll build a simple "Hello world" app and run it. You can read more about Getting started with Anaconda Distribution in Anaconda's docs. If you prefer to manage your Python environments via command line, check out how to Install Streamlit using command line.

Anaconda Distribution includes Python and basically everything you need to get started. The only thing left for you to choose is a code editor.

Our favorite editor is VS Code, which is also what we use in all our tutorials.

Knowledge about environment managers

Environment managers create virtual environments to isolate Python package installations between projects. For a detailed introduction to Python environments, check out Python Virtual Environments: A Primer.

But don't worry! In this guide we'll teach you how to install and use an environment manager (Anaconda).

Go to anaconda.com/download.

Install Anaconda Distribution for your OS.

Open Anaconda Navigator (the graphical interface included with Anaconda Distribution).

You can decline signing in to Anaconda if prompted.

In the left menu, click "Environments."

At the bottom of your environments list, click "Create."

Enter "streamlitenv" for the name of your environment.

Click the green play icon (play_circle) next to your environment.

Click "Open Terminal."

A terminal will open with your environment activated. Your environment's name will appear in parentheses at the beginning of your terminal's prompt to show that it's activated.

In your terminal, type:

To validate your installation, enter:

If this doesn't work, use the long-form command:

The Streamlit Hello example app will automatically open in your browser. If it doesn't, open your browser and go to the localhost address indicated in your terminal, typically http://localhost:8501. Play around with the app!

Open VS Code with a new project.

Create a Python file named app.py in your project folder.

Copy the following code into app.py and save it.

Click your Python interpreter in the lower-right corner, then choose your streamlitenv environment from the drop-down.

Right-click app.py in your file navigation and click "Open in integrated terminal."

A terminal will open with your environment activated. Confirm this by looking for "(streamlitenv)" at the beginning of your next prompt. If it is not there, manually activate your environment with the command:

In your terminal, type:

*[Content truncated]*

---

## Deploy an app from a template - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/get-started/deploy-from-a-template

**Contents:**
- Deploy an app from a template
- Access the template picker
- Select a template
    - Note
    - Important
- View your app
    - Important
  - Still have questions?

Streamlit Community Cloud makes it easy to get started with several convenient templates. Just pick a template, and Community Cloud will fork it to your account and deploy it. Any edits you push to your new fork will immediately show up in your deployed app. Additionally, if you don't want to use a local development environment, Community Cloud makes it easy to create a GitHub codespace that's fully configured for Streamlit app development.

There are two ways to begin deploying a template: the "Create app" button and the template gallery at the bottom of your workspace.

The template picker shows a list of available templates on the left. A preview for the current, selected template shows on the right.

From the list of templates on the left, select "GDP dashboard."

Optional: For "Name of new GitHub repository," enter a name for your new, forked repository.

When you deploy a template, Community Cloud forks the template repository into your GitHub account. Community Cloud chooses a default name for this repository based on the selected template. If you have previously deployed the same template with its default name, Community Cloud will append an auto-incrementing number to the name.

Even if you have another user's or organization's workspace selected, Community Cloud will always deploy a template app from your personal workspace. That is, Community Cloud will always fork a template into your GitHub user account. If you want to deploy a template app from an organization, manually fork the template in GitHub, and deploy it from your fork in the associated workspace.

Optional: In the "App URL" field, choose a subdomain for your new app.

Every Community Cloud app is deployed to a subdomain on streamlit.app, but you can change your app's subdomain at any time. For more information, see App settings.

Optional: To edit the template in a GitHub codespace immediately, select the option to "Open GitHub Codespaces..."

You can create a codespace for your app at any time. To learn how to create a codespace after you've deployed an app, see Edit your app.

Optional: To change the version of Python, at the bottom of the screen, click "Advanced settings," select a Python version, and then click "Save."

After an app is deployed, you can't change the version of Python without deleting and redeploying the app.

At the bottom, click "Deploy."

If you didn't select the option to open GitHub Codespaces, you are redirected to your new app.

If you selected the option t

*[Content truncated]*

---

## Use Streamlit in Snowflake - Streamlit Docs

**URL:** https://docs.streamlit.io/get-started/installation/streamlit-in-snowflake

**Contents:**
- Use Streamlit in Snowflake to code in a secure environment
    - Note
- Prerequisites
- Create an account
- Optional: Create a warehouse
- Create a database
- Create a "Hello World" Streamlit app
    - Tip
- Return to your app
- What's next?

Snowflake is a single, global platform that powers the Data Cloud. If you want to use a secure platform with role-based access control, this is the option for you! This page walks you through creating a trial Snowflake account and building a "Hello world" app. Your trial account comes with an account credit so you can try out the service without entering any payment information.

For more information, see Limitations and unsupported features in the Snowflake documentation.

All you need is an email address! Everything else happens in your 30-day trial account.

Go to signup.snowflake.com. (This link will open in a new tab.)

Fill in your information, and click "CONTINUE."

Select "Standard" for your Snowflake edition and "Amazon Web Services" for your cloud provider.

Choose the region nearest you, accept the terms, and click "GET STARTED."

Answer a few questions to let us know more about yourself, or skip them.

A message will display: "You're now signed up!" Go to your email, and click on the activation link. (Within your link, note the subdomain. This is your Snowflake account identifier. https://<account_identifier>.snowflakecomputing.com)

Set your username and password. This will be an admin user account within your Snowflake account. Your Snowflake account can have multiple users within it.

If you are not signed in after setting your password, follow the instructions to enter your Snowflake account identifier, and then enter your username and password. If you've accidentally closed your browser, you can sign in at app.snowflake.com.

Congratulations! You have a trial Snowflake account.

The displayed interface is called Snowsight. Snowsight provides a web-based, graphical user interface for your Snowflake account. The default page is "Home," which provides popular quick actions to get started. You can access your "Projects" in the left navigation or at the bottom of your "Home" page. "Projects" include worksheets, notebooks, Streamlit apps, and dashboards. Check out the Snowflake docs for a quick tour.)

Warehouses provide compute resources for tasks and apps in your Snowflake account. Your trial account already has an XS warehouse which you can use. This is named "COMPUTE_WH." However, if you want to use more compute resources, you can create another warehouse.

In the lower-left corner under your name, confirm that your current role is "ACCOUNTADMIN." If it isn't, click your name, hover over "Switch Role," and select "ACCOUNTADMIN."

In the left

*[Content truncated]*

---

## Quickstart - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/get-started/quickstart?slug=deploy&slug=streamlit-community-cloud&slug=get-started

**Contents:**
- Quickstart
- Prerequisites
- Sign up for Streamlit Community Cloud
- Add access to your public repositories
- Optional: Add access to private repositories
- Create a new app from a template
- Edit your app in GitHub Codespaces
- Publish your changes
- Stop or delete your codespace
  - Still have questions?

This is a concise set of steps to create your Streamlit Community Cloud account, deploy a sample app, and start editing it with GitHub Codespaces. For other options and complete explanations, start with Create your account.

You will sign in to your GitHub account during this process. Community Cloud will use the email from your GitHub account to create your Community Cloud account. For other sign-in options, see Create your account.

Wait for GitHub to set up your codespace.

It can take several minutes to fully initialize your codespace. After the Visual Studio Code editor appears in your codespace, it can take several minutes to install Python and start the Streamlit server. When complete, a split screen view displays a code editor on the left and a running app on the right. The code editor opens two tabs by default: the repository's readme file and the app's entrypoint file.

Go to the app's entrypoint file (streamlit_app.py) in the left pane, and change line 3 by adding "Streamlit" inside st.title.

Files are automatically saved in your codespace with each edit.

A moment after typing a change, your app on the right side will display a rerun prompt. Click "Always rerun."

If the rerun prompt disappears before you click it, you can hover over the overflow menu icon (more_vert) to bring it back.

Optional: Continue to make edits and observe the changes within seconds.

To stage and commit all your changes, in the confirmation dialog, click "Yes." Your changes are committed locally in your codespace.

To push your commit to GitHub, in the source control sidebar on the left, click "cached 1 arrow_upward."

To push commits to "origin/main," in the confirmation dialog, click "OK."

Your changes are now saved to your GitHub repository. Community Cloud will immediately reflect the changes in your deployed app.

Optional: To see your updated, published app, return to the "My apps" section of your workspace at share.streamlit.io, and click on your app.

When you stop interacting with your codespace, GitHub will generally stop your codespace for you. However, the surest way to avoid undesired use of your capacity is to stop or delete your codespace when you are done.

If you want to return to your work later, click "Stop codespace." Otherwise, click "Delete."

Congratulations! You just deployed an app to Streamlit Community Cloud. 🎉 Return to your workspace at share.streamlit.io/ and deploy another Streamlit app.

Our forums are full of helpful information and S

*[Content truncated]*

---

## Fork and edit a public app - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/get-started/fork-and-edit-a-public-app

**Contents:**
- Fork and edit a public app
    - Warning
    - Important
  - Still have questions?

Community Cloud is all about learning, sharing, and exploring the world of Streamlit. For apps with public repositories, you can quickly fork copies to your GitHub account, deploy your own version, and jump into a codespace on GitHub to start editing and exploring Streamlit code.

From a forkable app, in the upper-right corner, click "Fork."

Optional: In the "App URL" field, choose a custom subdomain for your app.

Every Community Cloud app is deployed to a subdomain on streamlit.app, but you can change your app's subdomain at any time. For more information, see App settings.

The repository will be forked to your GitHub account. If you have already forked the repository, Community Cloud will use the existing fork. If your existing fork already has an associated codespace, the codespace will be reused.

Do not use this method in the following situations:

If you have an existing fork of this app and kept the original repository name, Community Cloud will use your existing fork. If you've previously deployed the app and opened a codespace, Community Cloud will open your existing codespace.

Wait for GitHub to set up your codespace.

It can take several minutes to fully initialize your codespace. After the Visual Studio Code editor appears in your codespace, it can take several minutes to install Python and start the Streamlit server. When complete, a split screen view displays a code editor on the left and a running app on the right. The code editor opens two tabs by default: the repository's readme file and the app's entrypoint file.

The app displayed in your codespace is not the same instance you deployed on Community Cloud. Your codespace is a self-contained development environment. When you make edits inside a codespace, those edits don't leave the codespace until you commit them to your repository. When you commit your changes to your repository, Community Cloud detects the changes and updates your deployed app. To learn more, see Edit your app.

Edit your newly forked app as desired. For more instructions on working with GitHub Codespaces, see Edit your app.

Our forums are full of helpful information and Streamlit experts.

---

## Basic concepts of Streamlit - Streamlit Docs

**URL:** https://docs.streamlit.io/get-started/fundamentals/main-concepts

**Contents:**
- Basic concepts of Streamlit
    - Note
    - Tip
- Development flow
    - Tip
- Data flow
- Display and style data
  - Use magic
  - Write a data frame
    - Note

Working with Streamlit is simple. First you sprinkle a few Streamlit commands into a normal Python script, then you run it with streamlit run:

As soon as you run the script as shown above, a local Streamlit server will spin up and your app will open in a new tab in your default web browser. The app is your canvas, where you'll draw charts, text, widgets, tables, and more.

What gets drawn in the app is up to you. For example st.text writes raw text to your app, and st.line_chart draws — you guessed it — a line chart. Refer to our API documentation to see all commands that are available to you.

When passing your script some custom arguments, they must be passed after two dashes. Otherwise the arguments get interpreted as arguments to Streamlit itself.

Another way of running Streamlit is to run it as a Python module. This can be useful when configuring an IDE like PyCharm to work with Streamlit:

You can also pass a URL to streamlit run! This is great when combined with GitHub Gists. For example:

Every time you want to update your app, save the source file. When you do that, Streamlit detects if there is a change and asks you whether you want to rerun your app. Choose "Always rerun" at the top-right of your screen to automatically update your app every time you change its source code.

This allows you to work in a fast interactive loop: you type some code, save it, try it out live, then type some more code, save it, try it out, and so on until you're happy with the results. This tight loop between coding and viewing results live is one of the ways Streamlit makes your life easier.

While developing a Streamlit app, it's recommended to lay out your editor and browser windows side by side, so the code and the app can be seen at the same time. Give it a try!

As of Streamlit version 1.10.0 and higher, Streamlit apps cannot be run from the root directory of Linux distributions. If you try to run a Streamlit app from the root directory, Streamlit will throw a FileNotFoundError: [Errno 2] No such file or directory error. For more information, see GitHub issue #5239.

If you are using Streamlit version 1.10.0 or higher, your main script should live in a directory other than the root directory. When using Docker, you can use the WORKDIR command to specify the directory where your main script lives. For an example of how to do this, read Create a Dockerfile.

Streamlit's architecture allows you to write apps the same way you write plain Python scripts. To unlock 

*[Content truncated]*

---

## Create your account - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/get-started/create-your-account

**Contents:**
- Create your account
- Sign up
    - Important
  - Option 1: Sign in using emailed codes
  - Option 2: Sign in using Google
  - Option 3: Sign in using GitHub
- Finish up
  - Still have questions?

Before you can start deploying apps for the world to see, you need to sign up for your Streamlit Community Cloud account.

Each Community Cloud account is associated with an email. Two accounts can't have the same email. When sharing a private app, you will assign viewing privileges by email. Additionally, two accounts can't have the same source control (GitHub account). If you try to create a second Community Cloud account with the same source control, Community Cloud will merge the accounts.

Community Cloud allows you to sign in using one of the three following methods:

Even when you sign in through GitHub, the authentication flow returns your email address to Community Cloud. Changing the email on your GitHub account can affect your Community Cloud account if you sign in through GitHub.

Go to share.streamlit.io.

Click "Continue to sign-in."

Continue with one of the three options listed below.

Click "Continue with GitHub."

Enter your GitHub credentials, and follow GitHub's authentication prompts.

This adds the "Streamlit Community Cloud" OAuth application to your GitHub account. This application is only used to pass your email when you sign in to Community Cloud. On the next page, you'll perform additional steps to allow Community Cloud to access your repositories. For more information about using and reviewing the OAuth applications on your account, see Using OAuth apps in GitHub's docs.

Fill in your information, and click "Continue" at the bottom.

The "Primary email" field is prefilled with the email you used to sign in. If you change this email in the account setup form, it will only impact marketing emails; it will not reflect on your new account. To change the email associated with your account after it's created, see Update your email address.

Congratulations on creating your Streamlit Community Cloud account! A warning icon (warning) next to "Workspaces" in the upper-left corner is expected; this indicates that your account is not yet connected to GitHub. Even if you created your account by signing in through GitHub, your account does not yet have permission to access your repositories. Continue to the next page to connect your GitHub account.

Our forums are full of helpful information and Streamlit experts.

---

## Explore your workspace - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/get-started/explore-your-workspace

**Contents:**
- Explore your workspace
- Workspaces
  - Switching workspaces
  - Invite other developers to your workspace
    - Note
- My apps
  - Deploying apps
- My profile
- Explore
  - Still have questions?

If you just created your account and connected your GitHub account, congrats! You are now signed in and ready to go. If you are joining someone else's workspace you may already see some apps.

Each GitHub account and organization is associated with a workspace in Community Cloud. When you sign in to Community Cloud for the first time, you will land in your personal workspace associated with your GitHub user account. The upper-left corner of Community Cloud shows your current workspace.

To switch between workspaces, click the workspace name in the upper-left corner and select a new workspace.

Other workspaces are available to you as follows:

Inviting other developers is simple: Just give them write access to your GitHub repository so that you can code together. When they sign in to share.streamlit.io, they'll have access to your workspace.

Streamlit Community Cloud inherits developer permissions from GitHub. When others sign in to Community Cloud, they will automatically see the workspaces they share with you. From there you can all deploy, manage, and share apps together.

When a user is added to a repository on GitHub, it will take at most 15 minutes before they can deploy or manage the app on Community Cloud. If a user is removed from a repository on GitHub, it will take at most 15 minutes before their permission to manage the app from that repository is revoked.

And remember, whenever anyone on the team updates the code on GitHub, the app will automatically update for you!

The "My apps" section of your workspace is your base of operations to deploy and manage your apps. When you deploy an app, it is added to this section of your workspace.

If you already have an app saved to a GitHub repo, you can deploy it directly. Otherwise, Community Cloud provides templates you can use. When you deploy from a template, Community Cloud will fork a project into your GitHub account and deploy from the new fork. This is a convenient way to get started if you haven't already created a Streamlit app.

To get started, just click "Create app" in the upper-right corner. To learn more, see Deploy your app and Deploy from a template.

The "My profile" section of your workspace lets you customize a personal portfolio of Streamlit apps to share with the world. Curate and feature your Streamlit apps to show off your work.

For inspiration, check out the "Explore" section. This is a gallery of Streamlit apps created by the Streamlit community. Check out popular and trendin

*[Content truncated]*

---

## Create an app - Streamlit Docs

**URL:** https://docs.streamlit.io/get-started/tutorials/create-an-app

**Contents:**
- Create an app
    - Tip
- Create your first app
    - Tip
- Fetch some data
- Effortless caching
  - How's it work?
    - Tip
- Inspect the raw data
- Draw a histogram

If you've made it this far, chances are you've installed Streamlit and run through the basics in Basic concepts and Advanced concepts. If not, now is a good time to take a look.

The easiest way to learn how to use Streamlit is to try things out yourself. As you read through this guide, test each method. As long as your app is running, every time you add a new element to your script and save, Streamlit's UI will ask if you'd like to rerun the app and view the changes. This allows you to work in a fast interactive loop: you write some code, save it, review the output, write some more, and so on, until you're happy with the results. The goal is to use Streamlit to create an interactive app for your data or model and along the way to use Streamlit to review, debug, perfect, and share your code.

In this guide, you're going to use Streamlit's core features to create an interactive app; exploring a public Uber dataset for pickups and drop-offs in New York City. When you're finished, you'll know how to fetch and cache data, draw charts, plot information on a map, and use interactive widgets, like a slider, to filter results.

If you'd like to skip ahead and see everything at once, the complete script is available below.

Streamlit is more than just a way to make data apps, it’s also a community of creators that share their apps and ideas and help each other make their work better. Please come join us on the community forum. We love to hear your questions, ideas, and help you work through your bugs — stop by today!

The first step is to create a new Python script. Let's call it uber_pickups.py.

Open uber_pickups.py in your favorite IDE or text editor, then add these lines:

Every good app has a title, so let's add one:

Now it's time to run Streamlit from the command line:

Running a Streamlit app is no different than any other Python script. Whenever you need to view the app, you can use this command.

Did you know you can also pass a URL to streamlit run? This is great when combined with GitHub Gists. For example:

As usual, the app should automatically open in a new tab in your browser.

Now that you have an app, the next thing you'll need to do is fetch the Uber dataset for pickups and drop-offs in New York City.

Let's start by writing a function to load the data. Add this code to your script:

You'll notice that load_data is a plain old function that downloads some data, puts it in a Pandas dataframe, and converts the date column from text to datetime. The

*[Content truncated]*

---

## Streamlit Trust and Security - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/get-started/trust-and-security

**Contents:**
- Streamlit trust and security
- Product security
  - Authentication
  - Permissions
- Network and application security
  - Data hosting
  - Data deletion
  - Virtual private cloud
  - Encryption
  - Permissions and authentication

Streamlit is a framework that turns Python scripts into interactive apps, giving data scientists the ability to quickly create data and model-based apps for the entire company.

A simple Streamlit app is:

When you streamlit run my_app.py, you start a web server that runs the interactive application on your local computer at http://localhost:8501. This is great for local development. When you want to share with your colleagues, Streamlit Community Cloud enables you to deploy and run these applications in the cloud. Streamlit Community Cloud handles the details of containerization and provides you an interface for easily managing your deployed apps.

This document provides an overview of the security safeguards we've implemented to protect you and your data. Security, however, is a shared responsibility and you are ultimately responsible for making appropriate use of Streamlit and the Streamlit Community Cloud, including implementation of appropriate user-configurable security safeguards and best practices.

You must authenticate through GitHub to deploy or administer an app. Authentication through Google or single-use emailed links are required to view a private app when you don't have push or admin permissions on the associated GitHub repository. The single-use emailed links are valid for 15 minutes once requested.

Streamlit Community Cloud inherits the permissions you have assigned in GitHub. Users with write access to a GitHub repository for a given app will be able to make changes in the Streamlit administrative console. However, only users with admin access to a repository are able to deploy and delete apps.

Our physical infrastructure is hosted and managed within secure data centers maintained by infrastructure-as-a-service cloud providers. Streamlit leverages many of these platforms' built-in security, privacy, and redundancy features. Our cloud providers continually monitor their data centers for risk and undergo assessments to ensure compliance with industry standards.

Community Cloud users have the option to delete any apps they’ve deployed as well as their entire account.

When a user deletes their application from the admin console, we delete their source code, including any files copied from their GitHub repository or created within our system from the running app. However, we keep a record representing the application in our database. This record contains the coordinates of the application: the GitHub organization or user, the GitHub repos

*[Content truncated]*

---

## Advanced concepts of Streamlit - Streamlit Docs

**URL:** https://docs.streamlit.io/get-started/fundamentals/advanced-concepts

**Contents:**
- Advanced concepts of Streamlit
- Caching
- Session State
  - What is a session?
  - Examples of using Session State
- Connections
  - Still have questions?

Now that you know how a Streamlit app runs and handles data, let's talk about being efficient. Caching allows you to save the output of a function so you can skip over it on rerun. Session State lets you save information for each user that is preserved between reruns. This not only allows you to avoid unecessary recalculation, but also allows you to create dynamic pages and handle progressive processes.

Caching allows your app to stay performant even when loading data from the web, manipulating large datasets, or performing expensive computations.

The basic idea behind caching is to store the results of expensive function calls and return the cached result when the same inputs occur again. This avoids repeated execution of a function with the same input values.

To cache a function in Streamlit, you need to apply a caching decorator to it. You have two choices:

In the above example, long_running_function is decorated with @st.cache_data. As a result, Streamlit notes the following:

Before running the code within long_running_function, Streamlit checks its cache for a previously saved result. If it finds a cached result for the given function and input values, it will return that cached result and not rerun function's code. Otherwise, Streamlit executes the function, saves the result in its cache, and proceeds with the script run. During development, the cache updates automatically as the function code changes, ensuring that the latest changes are reflected in the cache.

Streamlit's two caching decorators and their use cases.

For more information about the Streamlit caching decorators, their configuration parameters, and their limitations, see Caching.

Session State provides a dictionary-like interface where you can save information that is preserved between script reruns. Use st.session_state with key or attribute notation to store and recall values. For example, st.session_state["my_key"] or st.session_state.my_key. Remember that widgets handle their statefulness all by themselves, so you won't always need to use Session State!

A session is a single instance of viewing an app. If you view an app from two different tabs in your browser, each tab will have its own session. So each viewer of an app will have a Session State tied to their specific view. Streamlit maintains this session as the user interacts with the app. If the user refreshes their browser page or reloads the URL to the app, their Session State resets and they begin again with a new se

*[Content truncated]*

---

## Create a multipage app - Streamlit Docs

**URL:** https://docs.streamlit.io/get-started/tutorials/create-a-multipage-app

**Contents:**
- Create a multipage app
- Motivation
- Convert an existing app into a multipage app
- Create the entrypoint file
- Create multiple pages
- Run the multipage app
- Next steps
  - Still have questions?

In Additional features, we introduced multipage apps, including how to define pages, structure and run multipage apps, and navigate between pages in the user interface. You can read more details in our guide to Multipage apps

In this guide, let’s put our understanding of multipage apps to use by converting the previous version of our streamlit hello app to a multipage app!

Before Streamlit 1.10.0, the streamlit hello command was a large single-page app. As there was no support for multiple pages, we resorted to splitting the app's content using st.selectbox in the sidebar to choose what content to run. The content is comprised of three demos for plotting, mapping, and dataframes.

Here's what the code and single-page app looked like:

Notice how large the file is! Each app “page" is written as a function, and the selectbox is used to pick which page to display. As our app grows, maintaining the code requires a lot of additional overhead. Moreover, we’re limited by the st.selectbox UI to choose which “page" to run, we cannot customize individual page titles with st.set_page_config, and we’re unable to navigate between pages using URLs.

Now that we've identified the limitations of a single-page app, what can we do about it? Armed with our knowledge from the previous section, we can convert the existing app to be a multipage app, of course! At a high level, we need to perform the following steps:

Now, let’s walk through each step of the process and view the corresponding changes in code.

We rename our entrypoint file to Hello.py , so that the title in the sidebar is capitalized and only the code for the intro page is included. Additionally, we’re able to customize the page title and favicon — as it appears in the browser tab with st.set_page_config. We can do so for each of our pages too!

Notice how the sidebar does not contain page labels as we haven’t created any pages yet.

A few things to remember here:

Check out how we do all this below! For each new page, we create a new file inside the pages folder, and add the appropriate demo code into it.

With our additional pages created, we can now put it all together in the final step below.

To run your newly converted multipage app, run:

That’s it! The Hello.py script now corresponds to the main page of your app, and other scripts that Streamlit finds in the pages folder will also be present in the new page selector that appears in the sidebar.

Congratulations! 🎉 If you've read this far, chances are y

*[Content truncated]*

---

## Quickstart - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/get-started/quickstart

**Contents:**
- Quickstart
- Prerequisites
- Sign up for Streamlit Community Cloud
- Add access to your public repositories
- Optional: Add access to private repositories
- Create a new app from a template
- Edit your app in GitHub Codespaces
- Publish your changes
- Stop or delete your codespace
  - Still have questions?

This is a concise set of steps to create your Streamlit Community Cloud account, deploy a sample app, and start editing it with GitHub Codespaces. For other options and complete explanations, start with Create your account.

You will sign in to your GitHub account during this process. Community Cloud will use the email from your GitHub account to create your Community Cloud account. For other sign-in options, see Create your account.

Wait for GitHub to set up your codespace.

It can take several minutes to fully initialize your codespace. After the Visual Studio Code editor appears in your codespace, it can take several minutes to install Python and start the Streamlit server. When complete, a split screen view displays a code editor on the left and a running app on the right. The code editor opens two tabs by default: the repository's readme file and the app's entrypoint file.

Go to the app's entrypoint file (streamlit_app.py) in the left pane, and change line 3 by adding "Streamlit" inside st.title.

Files are automatically saved in your codespace with each edit.

A moment after typing a change, your app on the right side will display a rerun prompt. Click "Always rerun."

If the rerun prompt disappears before you click it, you can hover over the overflow menu icon (more_vert) to bring it back.

Optional: Continue to make edits and observe the changes within seconds.

To stage and commit all your changes, in the confirmation dialog, click "Yes." Your changes are committed locally in your codespace.

To push your commit to GitHub, in the source control sidebar on the left, click "cached 1 arrow_upward."

To push commits to "origin/main," in the confirmation dialog, click "OK."

Your changes are now saved to your GitHub repository. Community Cloud will immediately reflect the changes in your deployed app.

Optional: To see your updated, published app, return to the "My apps" section of your workspace at share.streamlit.io, and click on your app.

When you stop interacting with your codespace, GitHub will generally stop your codespace for you. However, the surest way to avoid undesired use of your capacity is to stop or delete your codespace when you are done.

If you want to return to your work later, click "Stop codespace." Otherwise, click "Delete."

Congratulations! You just deployed an app to Streamlit Community Cloud. 🎉 Return to your workspace at share.streamlit.io/ and deploy another Streamlit app.

Our forums are full of helpful information and S

*[Content truncated]*

---

## Fundamental concepts - Streamlit Docs

**URL:** https://docs.streamlit.io/get-started/fundamentals

**Contents:**
- Fundamental concepts
  - Still have questions?

Are you new to Streamlit and want the grand tour? If so, you're in the right place!

Basic concepts. Learn the fundamental concepts of Streamlit. How is a Streamlit app structured? How does it run? How does it magically get your data on a webpage?

Advanced concepts. After you understand the rerun logic of Streamlit, learn how to make efficient and dynamic apps with caching and Session State. Get introduced to handling database connections.

Additional features. Learn about Streamlit's additional features. You don't need to know these concepts for your first app, but check it out to know what's available.

Our forums are full of helpful information and Streamlit experts.

---

## Use Streamlit in Snowflake - Streamlit Docs

**URL:** https://docs.streamlit.io/get-started/installation/streamlit-in-snowflake?slug=deploy&slug=snowflake

**Contents:**
- Use Streamlit in Snowflake to code in a secure environment
    - Note
- Prerequisites
- Create an account
- Optional: Create a warehouse
- Create a database
- Create a "Hello World" Streamlit app
    - Tip
- Return to your app
- What's next?

Snowflake is a single, global platform that powers the Data Cloud. If you want to use a secure platform with role-based access control, this is the option for you! This page walks you through creating a trial Snowflake account and building a "Hello world" app. Your trial account comes with an account credit so you can try out the service without entering any payment information.

For more information, see Limitations and unsupported features in the Snowflake documentation.

All you need is an email address! Everything else happens in your 30-day trial account.

Go to signup.snowflake.com. (This link will open in a new tab.)

Fill in your information, and click "CONTINUE."

Select "Standard" for your Snowflake edition and "Amazon Web Services" for your cloud provider.

Choose the region nearest you, accept the terms, and click "GET STARTED."

Answer a few questions to let us know more about yourself, or skip them.

A message will display: "You're now signed up!" Go to your email, and click on the activation link. (Within your link, note the subdomain. This is your Snowflake account identifier. https://<account_identifier>.snowflakecomputing.com)

Set your username and password. This will be an admin user account within your Snowflake account. Your Snowflake account can have multiple users within it.

If you are not signed in after setting your password, follow the instructions to enter your Snowflake account identifier, and then enter your username and password. If you've accidentally closed your browser, you can sign in at app.snowflake.com.

Congratulations! You have a trial Snowflake account.

The displayed interface is called Snowsight. Snowsight provides a web-based, graphical user interface for your Snowflake account. The default page is "Home," which provides popular quick actions to get started. You can access your "Projects" in the left navigation or at the bottom of your "Home" page. "Projects" include worksheets, notebooks, Streamlit apps, and dashboards. Check out the Snowflake docs for a quick tour.)

Warehouses provide compute resources for tasks and apps in your Snowflake account. Your trial account already has an XS warehouse which you can use. This is named "COMPUTE_WH." However, if you want to use more compute resources, you can create another warehouse.

In the lower-left corner under your name, confirm that your current role is "ACCOUNTADMIN." If it isn't, click your name, hover over "Switch Role," and select "ACCOUNTADMIN."

In the left

*[Content truncated]*

---

## First steps building Streamlit apps - Streamlit Docs

**URL:** https://docs.streamlit.io/get-started/tutorials

**Contents:**
- First steps building Streamlit apps
  - Still have questions?

If you've just read through our Basic concepts and want to get your hands on Streamlit. Check out these tutorials. Make sure you have installed Streamlit so you can execute the code yourself.

Create an app uses the concepts learned in Fundamentals along with caching to walk through making your first app.

Create a multipage app walks through the easy steps to add pages to your app.

Our forums are full of helpful information and Streamlit experts.

---

## Install Streamlit using command line - Streamlit Docs

**URL:** https://docs.streamlit.io/get-started/installation/command-line

**Contents:**
- Install Streamlit using command line
- Prerequisites
- Create an environment using venv
- Activate your environment
- Install Streamlit in your environment
- Create a "Hello World" app and run it
- What's next?
  - Still have questions?

This page will walk you through creating an environment with venv and installing Streamlit with pip. These are our recommended tools, but if you are familiar with others you can use your favorite ones too. At the end, you'll build a simple "Hello world" app and run it. If you prefer to have a graphical interface to manage your Python environments, check out how to Install Streamlit using Anaconda Distribution.

As with any programming tool, in order to install Streamlit you first need to make sure your computer is properly set up. More specifically, you’ll need:

We support version 3.9 to 3.13.

A Python environment manager (recommended)

Environment managers create virtual environments to isolate Python package installations between projects.

We recommend using virtual environments because installing or upgrading a Python package may cause unintentional effects on another package. For a detailed introduction to Python environments, check out Python Virtual Environments: A Primer.

For this guide, we'll be using venv, which comes with Python.

A Python package manager

Package managers handle installing each of your Python packages, including Streamlit.

For this guide, we'll be using pip, which comes with Python.

Only on MacOS: Xcode command line tools

Download Xcode command line tools using these instructions in order to let the package manager install some of Streamlit's dependencies.

Our favorite editor is VS Code, which is also what we use in all our tutorials.

Open a terminal and navigate to your project folder.

In your terminal, type:

A folder named ".venv" will appear in your project. This directory is where your virtual environment and its dependencies are installed.

In your terminal, activate your environment with one of the following commands, depending on your operating system.

Once activated, you will see your environment name in parentheses before your prompt. "(.venv)"

In the terminal with your environment activated, type:

Test that the installation worked by launching the Streamlit Hello example app:

If this doesn't work, use the long-form command:

Streamlit's Hello app should appear in a new tab in your web browser!

Close your terminal when you are done.

Once activated, you will see your environment's name in parentheses at the beginning of your terminal prompt. "(.venv)"

Run your Streamlit app.

If this doesn't work, use the long-form command:

To stop the Streamlit server, press Ctrl+C in the terminal.

When you're done u

*[Content truncated]*

---

## Streamlit Trust and Security - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/get-started/trust-and-security?slug=deploy&slug=streamlit-community-cloud&slug=get-started

**Contents:**
- Streamlit trust and security
- Product security
  - Authentication
  - Permissions
- Network and application security
  - Data hosting
  - Data deletion
  - Virtual private cloud
  - Encryption
  - Permissions and authentication

Streamlit is a framework that turns Python scripts into interactive apps, giving data scientists the ability to quickly create data and model-based apps for the entire company.

A simple Streamlit app is:

When you streamlit run my_app.py, you start a web server that runs the interactive application on your local computer at http://localhost:8501. This is great for local development. When you want to share with your colleagues, Streamlit Community Cloud enables you to deploy and run these applications in the cloud. Streamlit Community Cloud handles the details of containerization and provides you an interface for easily managing your deployed apps.

This document provides an overview of the security safeguards we've implemented to protect you and your data. Security, however, is a shared responsibility and you are ultimately responsible for making appropriate use of Streamlit and the Streamlit Community Cloud, including implementation of appropriate user-configurable security safeguards and best practices.

You must authenticate through GitHub to deploy or administer an app. Authentication through Google or single-use emailed links are required to view a private app when you don't have push or admin permissions on the associated GitHub repository. The single-use emailed links are valid for 15 minutes once requested.

Streamlit Community Cloud inherits the permissions you have assigned in GitHub. Users with write access to a GitHub repository for a given app will be able to make changes in the Streamlit administrative console. However, only users with admin access to a repository are able to deploy and delete apps.

Our physical infrastructure is hosted and managed within secure data centers maintained by infrastructure-as-a-service cloud providers. Streamlit leverages many of these platforms' built-in security, privacy, and redundancy features. Our cloud providers continually monitor their data centers for risk and undergo assessments to ensure compliance with industry standards.

Community Cloud users have the option to delete any apps they’ve deployed as well as their entire account.

When a user deletes their application from the admin console, we delete their source code, including any files copied from their GitHub repository or created within our system from the running app. However, we keep a record representing the application in our database. This record contains the coordinates of the application: the GitHub organization or user, the GitHub repos

*[Content truncated]*

---

## Use Community Cloud to develop with GitHub Codespaces - Streamlit Docs

**URL:** https://docs.streamlit.io/get-started/installation/community-cloud

**Contents:**
- Use Community Cloud to develop with GitHub Codespaces
- Prerequisites
- Sign up for Streamlit Community Cloud
- Add access to your public repositories
- Optional: Add access to private repositories
- Create a new app from a template
- Edit your app in GitHub Codespaces
- Publish your changes
- Learn Streamlit fundamentals
- Stop or delete your codespace

To use GitHub Codespaces for Streamlit development, you need a properly configured devcontainer.json file to set up the environment. Fortunately, Streamlit Community Cloud is here to help! Although Community Cloud is primarily used to deploy and share apps with the rest of the world, we've built in some handy features to make it easy to use GitHub Codespaces. This guide explains how to create a Community Cloud account and use an automated workflow to get you into a GitHub codespace and live-editing a Streamlit app. All this happens right in your browser, no installation required.

If you already created a Community Cloud account and connected GitHub, jump ahead to Create a new app from a template.

Wait for GitHub to set up your codespace.

It can take several minutes to fully initialize your codespace. After you see the Visual Studio Code editor in your codespace, it can take several minutes to install Python and start the Streamlit server. When complete, you will see a split screen view with a code editor on the left and a running app on the right. The code editor opens two tabs by default: the repository's readme file and the app's entrypoint file.

Go to the app's entrypoint file (streamlit_app.py) in the left pane, and change line 3 by adding "Streamlit" inside st.title.

Files are automatically saved in your codespace with each edit.

A moment after typing a change, your app on the right side will display a rerun prompt. Click "Always rerun."

If the rerun prompt disappears before you click it, you can hover over the overflow menu icon (more_vert) to bring it back.

Optional: Continue to make edits and observe the changes within seconds.

In the confirmation dialog, click "Yes" to stage and commit all your changes. Your changes are committed locally in your codespace.

In the source control sidebar on the left, click "cached 1 arrow_upward" to push your commit to GitHub.

In the confirmation dialog, click "OK" to push commits to "origin/main."

Your changes are now saved to your GitHub repository. Community Cloud will immediately reflect the changes in your deployed app.

Optional: To see your updated, published app, return to the "My apps" section of your workspace at share.streamlit.io, and click on your app.

If you haven't learned Streamlit's basic concepts yet, this is a great time to go to Fundamentals. Use your codespace to walk through and try basic Streamlit commands. When finished, come back here to learn how to clean up your codespace.

Wh

*[Content truncated]*

---

## App model summary - Streamlit Docs

**URL:** https://docs.streamlit.io/get-started/fundamentals/summary

**Contents:**
- App model summary
  - Still have questions?

Now that you know a little more about all the individual pieces, let's close the loop and review how it works together:

Our forums are full of helpful information and Streamlit experts.

---
