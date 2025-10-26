# Streamlit - Deployment

**Pages:** 43

---

## Login attempt to Streamlit Community Cloud fails with error 403 - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/deploy/login-attempt-to-streamlit-community-cloud-fails-with-error-403

**Contents:**
- Login attempt to Streamlit Community Cloud fails with error 403
- Problem
- Solution
  - Still have questions?

Streamlit Community Cloud has monitoring jobs to detect malicious users using the platform for crypto mining. These jobs sometimes result in false positives and a normal user starts getting error 403 against a login attempt.

Please contact Support by providing your GitHub username for help referring to this article.

Our forums are full of helpful information and Streamlit experts.

---

## Share your app - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/deploy/share-apps-with-viewers-outside-organization

**Contents:**
- Share your app
- Make your app public or private
  - Set privacy from your app settings
  - Set privacy from the share button
- Share your public app
  - Share your app on social media
    - Tip
  - Invite viewers by email
  - Copy your app's URL
  - Add a badge to your GitHub repository

Now that your app is deployed you can easily share it and collaborate on it. But first, let's take a moment and do a little joy dance for getting that app deployed! 🕺💃

Your app is now live at a fixed URL, so go wild and share it with whomever you want. Your app will inherit permissions from your GitHub repo, meaning that if your repo is private your app will be private and if your repo is public your app will be public. If you want to change that you can simply do so from the app settings menu.

You are only allowed one private app at a time. If you've deployed from a private repository, you will have to make that app public or delete it before you can deploy another app from a private repository. Only developers can change your app between public and private.

If you deployed your app from a public repository, your app will be public by default. If you deployed your app from a private repository, you will need to make the app public if you want to freely share it with the community at large.

Access your App settings and go to the "Sharing" section.

Set your app's privacy under "Who can view this app." Select "This app is public and searchable" to make your app public. Select "Only specific people can view this app" to make your app private.

From your app at <your-custom-subdomain>.streamlit.app, click "Share" in the upper-right corner.

Toggle your app between public and private by clicking "Make this app public."

Once your app is public, just give anyone your app's URL and they view it! Streamlit Community Cloud has several convenient shortcuts for sharing your app.

From your app at <your-custom-subdomain>.streamlit.app, click "Share" in the upper-right corner.

Click "Social" to access convenient social media share buttons.

Use the social media sharing buttons to post your app on our forum! We'd love to see what you make and perhaps feature your app as our app of the month. 💖

Whether your app is public or private, you can send an email invite to your app directly from Streamlit Community Cloud. This grants the viewer access to analytics for all your public apps and the ability to invite other viewers to your workspace. Developers and invited viewers are identified by their email in analytics instead of appearing anonymously (if they view any of your apps while signed in). Read more about viewers in App analytics.

From your app at <your-custom-subdomain>.streamlit.app, click "Share" in the upper-right corner.

Enter an email address and click "I

*[Content truncated]*

---

## Upgrade your app's Streamlit version on Streamlit Community Cloud - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/upgrade-streamlit

**Contents:**
- Upgrade your app's Streamlit version on Streamlit Community Cloud
- No dependency file
- With a dependency file
  - Still have questions?

Want to use a cool new Streamlit feature but your app on Streamlit Community Cloud is running an old version of the Streamlit library? If that's you, don't worry! Here's how to upgrade your app's Streamlit version, based on how you manage your app dependencies:

When there is no dependencies file in your repository, your app will use the lastest Streamlit version that existed when it was last rebooted. In this case, simply reboot your app and Community Cloud will install the latest version.

You may want to avoid getting into this situation if your app depends on a specific version of Streamlit. That is why we encourage you to use a dependency file and pin your desired version of Streamlit.

When your app includes a dependency file, reboot your app or change your dependency file as follows:

If Streamlit is not included in your dependency file, reboot the app as described above.

Note that we don't recommend having an incomplete dependency file since pip won't be able to include streamlit when resolving compatible versions of your dependencies.

If Streamlit is included in your dependency file, but the version is not pinned or capped, reboot the app as described above.

When Community Cloud reboots your app, it will re-resolve your dependency file. Your app will then have the latest version of all dependencies that are consistent with your dependency file.

If Streamlit is included in your dependency file, and the version is pinned (e.g., streamlit==1.37.0), update your dependency file.

When you commit a change to your dependency file in your repository, Community Cloud will detect the change and automatically resolve the new dependencies. This is how you add, remove, or change all Python dependencies in general. You don't need to manually reboot your app, but you can if you want to.

Our forums are full of helpful information and Streamlit experts.

---

## Rename or change your app's GitHub coordinates - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/rename-your-app

**Contents:**
- Rename or change your app's GitHub coordinates
- Delete, rename, redeploy
- Regain access when you've already made changes to your app's GitHub coordinates
  - Still have questions?

Streamlit Community Cloud identifies apps by their GitHub coordinates (owner, repository, branch, entrypoint file path). If you move or rename one of these coordinates without preparation, you will lose access to administer any associated app.

If you need to rename your repository, move your entrypoint file, or otherwise change a deployed app's GitHub coordinates, do the following:

If you have changed a repository so that Community Cloud can no longer find your app on GitHub, your app will be missing or shown as view-only. View-only means that you can't edit, reboot, delete, or view settings for your app. You can only access analytics.

You may be able to regain control as follows:

Revert the change you made to your app so that Community Cloud can see the owner, repository, branch, and entrypoint file it expects.

Sign out of Community Cloud and GitHub.

Sign back in to Community Cloud and GitHub.

If you have regained access, delete your app. Proceed with your original change, and redeploy your app.

If this does not restore access to your app, please contact Snowflake support for assistance. They can delete your disconnected apps so you can redeploy them. For the quickest help, please provide a complete list of your affected apps by URL.

Our forums are full of helpful information and Streamlit experts.

---

## App settings - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/app-settings

**Contents:**
- App settings
- Access your app settings
  - Access app settings from your workspace
  - Access app settings from your Cloud logs
- Change your app settings
  - View or change your app's URL
  - Update your app's share settings
  - View or update your secrets
  - Still have questions?

This page is about your app settings on Streamlit Community Cloud. From your app settings you can view or change your app's URL, manage public or private access to your app, and update your saved secrets for your apps.

If you access "Settings" from your app chrome in the upper-right corner of your running app, you can access features to control the appearance of your app while it's running.

You can get to your app's settings:

From your workspace at share.streamlit.io, click the overflow icon (more_vert) next to your app. Click "Settings."

From your app at <your-custom-subdomain>.streamlit.app, click "Manage app" in the lower-right corner.

Click the overflow menu icon (more_vert) and click "Settings."

To view or customize your app subdomain from the dashboard:

Access your app's settings as described above.

On the "General" tab in the "App settings" dialog, see your app's unique subdomain in the "App URL" field.

Optional: Enter a new, custom subdomain between 6 and 63 characters in length, and then click "Save."

If a custom subdomain is not available (e.g. because it's already taken or contains restricted words), you'll see an error message. Change your subdomain as indicated.

Learn how to Share your app.

Access your app's settings as described above.

On the "Secrets" tab in the "App settings" dialog, see your app's secrets in the "Secrets" field.

Optional: Add, edit, or delete your secrets, and then click "Save."

Learn more about Secrets management for your Community Cloud app.

Our forums are full of helpful information and Streamlit experts.

---

## Prep and deploy your app on Community Cloud - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app

**Contents:**
- Prep and deploy your app on Community Cloud
    - Note
- Summary
- Ready, set, go!
  - Still have questions?

Streamlit Community Cloud lets you deploy your apps in just one click, and most apps will be deployed in only a few minutes. If you don't have an app ready to deploy, you can fork or clone one from our App gallery—you can find apps for machine learning, data visualization, data exploration, A/B testing, and more. You can also Deploy an app from a template. After you've deployed your app, check out how you can Edit your app with GitHub Codespaces.

If you want to deploy your app on a different cloud service, see our Deployment tutorials.

The pages that follow explain how to organize your app and provide complete information for Community Cloud to run it correctly.

When your app has everything it needs, deploying is easy. Just go to your workspace and click "Create app" in the upper-right corner. Follow the prompts to fill in your app's information, and then click "Deploy."

File organization. Learn how Community Cloud initializes your app and interprets paths. Learn where to put your configuration files.

App dependencies. Learn how to install dependencies and other Python libraries into your deployment environment.

Secrets management. Learn about the interface Community Cloud provides to securely upload your secrets.toml data.

Deploy your app Put it all together to deploy your app for the whole world to see.

Our forums are full of helpful information and Streamlit experts.

---

## How do I increase the upload limit of st.file_uploader on Streamlit Community Cloud? - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/deploy/increase-file-uploader-limit-streamlit-cloud

**Contents:**
- How do I increase the upload limit of st.file_uploader on Streamlit Community Cloud?
- Overview
- Solution
- Relevant resources
  - Still have questions?

By default, files uploaded using st.file_uploader() are limited to 200MB. You can configure this using the server.maxUploadSize config option.

Streamlit provides four different ways to set configuration options:

Which of the four options should you choose for an app deployed to Streamlit Community Cloud? 🤔

When deploying your app to Streamlit Community Cloud, you should use option 1. Namely, set the maxUploadSize config option in a global config file (.streamlit/config.toml) uploaded to your app's GitHub repo. 🎈

For example, to increase the upload limit to 400MB, upload a .streamlit/config.toml file containing the following lines to your app's GitHub repo:

Our forums are full of helpful information and Streamlit experts.

---

## Does Streamlit support the WSGI Protocol? (aka Can I deploy Streamlit with gunicorn?) - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/deploy/does-streamlit-support-wsgi-protocol

**Contents:**
- Does Streamlit support the WSGI Protocol? (aka Can I deploy Streamlit with gunicorn?)
- Problem
- Solution
  - Still have questions?

You're not sure whether your Streamlit app can be deployed with gunicorn.

Streamlit does not support the WSGI protocol at this time, so deploying Streamlit with (for example) gunicorn is not currently possible. Check out this forum thread regarding deploying Streamlit in a gunicorn-like manner to see how other users have accomplished this.

Our forums are full of helpful information and Streamlit experts.

---

## User authentication and information - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/deploy/authentication-without-sso

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

## Edit your app - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/edit-your-app

**Contents:**
- Edit your app
- Edit your app with GitHub Codespaces
  - Create a codespace for your deployed app
  - Optional: Publish your changes
  - Stop or delete your codespace
  - Still have questions?

You can edit your app from any development environment of your choice. Streamlit Community Cloud will monitor your repository and automatically copy any file changes you commit. You will immediately see commits reflected in your deployed app for most changes (such as edits to your app's Python files).

Community Cloud also makes it easy to skip the work of setting up a development environment. With a few simple clicks, you can configure a development environment using GitHub Codespaces.

Spin up a cloud-based development environment for your deployed app in minutes. You can run your app within your codespace to enjoy experimenting in a safe, sandboxed environment. When you are done editing your code, you can commit your changes to your repo or just leave them in your codespace to return to later.

From your workspace at share.streamlit.io, click the overflow icon (more_vert) next to your app. Click "Edit with Codespaces."

Community Cloud will add a .devcontainer/devcontainer.json file to your repository. If you already have a file of the same name in your repository, it will not be changed. If you want your repository to receive the instance created by Community Cloud, delete or rename your existing devcontainer configuration.

Wait for GitHub to set up your codespace.

It can take several minutes to fully initialize your codespace. After the Visual Studio Code editor appears in your codespace, it can take several minutes to install Python and start the Streamlit server. When complete, a split screen view displays a code editor on the left and a running app on the right. The code editor opens two tabs by default: the repository's readme file and the app's entrypoint file.

Optional: For more room to work, open the app preview in another tab.

If you have multiple monitors and want a little more room to work, open your app preview in another tab instead of using the Simple Browser within Visual Studio Code. Just copy the URL from the Simple Browser into another tab, and then close the Simple Browser. Now you have more room to edit your code. The remaining steps on this page will continue to display the split-screen view in Visual Studio Code.

Make a change to your app.

When you make changes to your app, the file is automatically saved within your codespace. Your edits do not affect your repository or deployed app until you commit those changes, which is explained in a later step. The app preview shown on the right is local to your codespace.

In order to

*[Content truncated]*

---

## Delete your account - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-account/delete-your-account

**Contents:**
- Delete your account
    - Warning
- How to delete your account
  - Still have questions?

Deleting your Streamlit Community Cloud account is just as easy as creating it. When you delete your account, your information, account, and all your hosted apps are deleted as well. Read more about data deletion in Streamlit trust and security.

Deleting your account is permanent and cannot be undone. Make sure you really want to delete your account and all hosted apps before proceeding. Any app you've deployed will be deleted, regardless of the workspace it was deployed from.

Follow these steps to delete your account:

Sign in to Streamlit Community Cloud at share.streamlit.io and access your Workspace settings.

From the "Linked accounts" section, click "Delete account."

In the confirmation dialog, follow the prompt and click "Delete account forever."

All your information and apps will be permanently deleted.

It's that simple! If you have any questions or run into issues deleting your account, please reach out to us on our forum. We're happy to help! 🎈

Our forums are full of helpful information and Streamlit experts.

---

## Deployment Issues - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/deploy

**Contents:**
- Deployment-related questions and errors
  - Still have questions?

Our forums are full of helpful information and Streamlit experts.

---

## Reboot your app - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/reboot-your-app

**Contents:**
- Reboot your app
  - Reboot your app from your workspace
  - Reboot your app from your Cloud logs
  - Still have questions?

If you need to clear your app's memory or force a fresh build after modifying a file that Streamlit Community Cloud doesn't monitor, you may need to reboot your app. This will interrupt any user who may currently be using your app and may take a few minutes for your app to redeploy. Anyone visiting your app will see "Your app is in the oven" during a reboot.

Rebooting your app on Community Cloud is easy! You can reboot your app:

From your workspace at share.streamlit.io, click the overflow icon (more_vert) next to your app. Click "Reboot."

A confirmation will display. Click "Reboot."

From your app at <your-custom-subdomain>.streamlit.app, click "Manage app" in the lower-right corner.

Click the overflow menu icon (more_vert) and click "Reboot app."

A confirmation will display. Click "Reboot."

Our forums are full of helpful information and Streamlit experts.

---

## SEO and search indexability - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app/indexability

**Contents:**
- SEO and search indexability
- Get the most out of app indexability
  - Make sure your app is public
  - Choose a custom subdomain early
  - Choose a descriptive app title
  - Customize your app's meta description
- What does my indexed app look like?
- What if I don't want my app to be indexed?
  - Still have questions?

When you deploy a public app to Streamlit Community Cloud, it is automatically indexed by search engines like Google and Bing on a weekly basis. 🎈 This means that anyone can find your app by searching for its custom subdomain (e.g. "traingenerator.streamlit.app") or by searching for the app's title.

Here are some tips to help you get the most out of app indexability:

All public apps hosted on Community Cloud are indexed by search engines. If your app is private, it will not be indexed by search engines. To make your private app public, read Share your app.

Community Cloud automatically generates a subdomain for your app if you do not choose one. However, you can change your subdomain at any time! Custom subdomains modify your app URLs to reflect your app content, personal branding, or whatever you’d like. To learn how to change your app's subdomain, see View or change your app's URL.

By choosing a custom subdomain, you can use it to help people find your app. For example, if you're deploying an app that generates training data, you might choose a subdomain like traingenerator.streamlit.app. This makes it easy for people to find your app by searching for "training generator" or "train generator streamlit app."

We recommend choosing a custom subdomain when you deploy your app. This ensures that your app is indexed by search engines using your custom subdomain, rather than the automatically generated one. If you choose a custom subdomain later, your app may be indexed multiple times—once using the default subdomain and once using your custom subdomain. In this case, your old URL will result in a 404 error which can confuse users who are searching for your app.

The meta title of your app is the text that appears in search engine results. It is also the text that appears in the browser tab when your app is open. By default, the meta title of your app is the same as the title of your app. However, you can customize the meta title of your app by setting the st.set_page_config parameter page_title to a custom string. For example:

This will change the meta title of your app to "Traingenerator." This makes it easier for people to find your app by searching for "Traingenerator" or "train generator streamlit app":

Google search results for "train generator streamlit app"

Meta descriptions are the short descriptions that appear in search engine results. Search engines use the meta description to help users understand what your app is about.

From our observati

*[Content truncated]*

---

## Streamlit Community Cloud - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud

**Contents:**
- Welcome to Streamlit Community Cloud
  - Still have questions?

With Streamlit Community Cloud, you can create, deploy, and manage your Streamlit apps — all for free. Share your apps with the world and build a customized profile page to display your work. Your Community Cloud account connects directly to your GitHub repositories (public or private). Most apps will launch in only a few minutes. Community Cloud handles all of the containerization, so deploying is easy. Bring your own code, or start from one of our popular templates. Rapidly prototype, explore, and update apps by simply changing your code in GitHub. Most changes appear immediately!

Want to avoid the work of setting up a local development environment? Community Cloud can help you quickly configure a codespace to develop in the cloud. Start coding or editing a Streamlit app with just a few clicks. See Edit your app.

Go to our Community Cloud quickstart to speed-run through creating your account, deploying an example app, and editing it using GitHub Codespaces. If you haven't built your first Streamlit app yet, see Get started with Streamlit.

Get started. Learn about Streamlit Community Cloud accounts and how to create one.

Deploy your app. A step-by-step guide on how to get your app deployed.

Manage your app. Access logs, reboot apps, set favorites, and more. Jump into a GitHub codespace to edit your app in the cloud.

Share your app. Share or embed your app.

Manage your account. Update your email, manage connections, or delete your account.

Our forums are full of helpful information and Streamlit experts.

---

## Huh. This is isn't supposed to happen message after trying to log in - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/deploy/huh-this-isnt-supposed-to-happen-message-after-trying-to-log-in

**Contents:**
- Huh. This is isn't supposed to happen message after trying to log in
- Problem
- Solution
  - Still have questions?

This article helps to resolve the login issue caused by email mismatching between the GitHub and the Streamlit Community Cloud.

You see the following message after signing in to your Streamlit Community Cloud account:

This message usually indicates that our system has linked your GitHub username with an email address other than the email address you're currently logged in with.

No worries – all you have to do is:

Our forums are full of helpful information and Streamlit experts.

---

## Share your app - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app

**Contents:**
- Share your app
- Make your app public or private
  - Set privacy from your app settings
  - Set privacy from the share button
- Share your public app
  - Share your app on social media
    - Tip
  - Invite viewers by email
  - Copy your app's URL
  - Add a badge to your GitHub repository

Now that your app is deployed you can easily share it and collaborate on it. But first, let's take a moment and do a little joy dance for getting that app deployed! 🕺💃

Your app is now live at a fixed URL, so go wild and share it with whomever you want. Your app will inherit permissions from your GitHub repo, meaning that if your repo is private your app will be private and if your repo is public your app will be public. If you want to change that you can simply do so from the app settings menu.

You are only allowed one private app at a time. If you've deployed from a private repository, you will have to make that app public or delete it before you can deploy another app from a private repository. Only developers can change your app between public and private.

If you deployed your app from a public repository, your app will be public by default. If you deployed your app from a private repository, you will need to make the app public if you want to freely share it with the community at large.

Access your App settings and go to the "Sharing" section.

Set your app's privacy under "Who can view this app." Select "This app is public and searchable" to make your app public. Select "Only specific people can view this app" to make your app private.

From your app at <your-custom-subdomain>.streamlit.app, click "Share" in the upper-right corner.

Toggle your app between public and private by clicking "Make this app public."

Once your app is public, just give anyone your app's URL and they view it! Streamlit Community Cloud has several convenient shortcuts for sharing your app.

From your app at <your-custom-subdomain>.streamlit.app, click "Share" in the upper-right corner.

Click "Social" to access convenient social media share buttons.

Use the social media sharing buttons to post your app on our forum! We'd love to see what you make and perhaps feature your app as our app of the month. 💖

Whether your app is public or private, you can send an email invite to your app directly from Streamlit Community Cloud. This grants the viewer access to analytics for all your public apps and the ability to invite other viewers to your workspace. Developers and invited viewers are identified by their email in analytics instead of appearing anonymously (if they view any of your apps while signed in). Read more about viewers in App analytics.

From your app at <your-custom-subdomain>.streamlit.app, click "Share" in the upper-right corner.

Enter an email address and click "I

*[Content truncated]*

---

## Share previews - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app/share-previews

**Contents:**
- Share previews
    - Note
- Titles
- Descriptions
- Preview images
  - Switching your app from public to private
  - Still have questions?

Social media sites generate a card with a title, preview image, and description when you share a link. This feature is called a "share preview." In the same way, when you share a link to a public Streamlit app on social media, a share preview is also generated. Here's an example of a share preview for a public Streamlit app posted on Twitter:

Share preview for a public Streamlit app

Share previews are generated only for public apps deployed on Streamlit Community Cloud.

The title is the text that appears at the top of the share preview. The text also appears in the browser tab when you visit the app. You should set the title to something that will make sense to your app's audience and describe what the app does. It is best practice to keep the title concise, ideally under 60 characters.

There are two ways to set the title of a share preview:

Set the page_title parameter in st.set_page_config() to your desired title. E.g.:

If you don't set the page_title parameter, the title of the share preview will be the name of your app's GitHub repository. For example, the default title for an app hosted on GitHub at github.com/jrieke/traingenerator will be "traingenerator".

The description is the text that appears below the title in the share preview. The description should summarize what the app does and ideally should be under 100 characters.

Streamlit pulls the description from the README in the app's GitHub repository. If there is no README, the description will default to:

This app was built in Streamlit! Check it out and visit https://streamlit.io for more awesome community apps. 🎈

Default share preview when a description is missing

If you want your share previews to look great and want users to share your app and click on your links, you should write a good description in the README of your app’s GitHub repository.

Streamlit Community Cloud takes a screenshot of your app once a day and uses it as the preview image, unlike titles and descriptions which are pulled directly from your app's code or GitHub repository. This screenshot may take up to 24 hours to update.

If you initially made your app public and later decided to make it private, we will stop generating share previews for the app. However, it may take up to 24 hours for the share previews to stop appearing.

Our forums are full of helpful information and Streamlit experts.

---

## How do I deploy Streamlit on a domain so it appears to run on a regular port (i.e. port 80)? - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/deploy/deploy-streamlit-domain-port-80

**Contents:**
- How do I deploy Streamlit on a domain so it appears to run on a regular port (i.e. port 80)?
- Problem
- Solution
  - Still have questions?

You want to deploy a Streamlit app on a domain so it appears to run on port 80.

You should use a reverse proxy to forward requests from a webserver like Apache or Nginx to the port where your Streamlit app is running. You can accomplish this in several different ways. The simplest way is to forward all requests sent to your domain so that your Streamlit app appears as the content of your website.

Another approach is to configure your webserver to forward requests to designated subfolders (e.g. http://awesomestuff.net/streamlitapp) to different Streamlit apps on the same domain, as in this example config for Nginx submitted by a Streamlit community member.

Our forums are full of helpful information and Streamlit experts.

---

## Workspace settings - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-account/workspace-settings

**Contents:**
- Workspace settings
- Access your workspace settings
- Linked accounts
- Limits
- Support
  - Still have questions?

From your workspace settings you can Manage your account, see your App resources and limits and access support resources.

Sign in to share.streamlit.io.

In the upper-left corner, click on your workspace name.

In the drop-down menu, click "Settings."

The "Linked accounts" section shows your current email identity and source control account. To learn more, see Manage your account.

The "Limits" section shows your current resources and limits. To learn more, see App resources and limits.

The "Support" section provides a convenient list of useful resources so you know where to go for help.

Our forums are full of helpful information and Streamlit experts.

---

## Argh. This app has gone over its resource limits - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/deploy/resource-limits

**Contents:**
- Argh. This app has gone over its resource limits
  - Still have questions?

Sorry! It means you've hit the resource limits of your Streamlit Community Cloud account.

There are a few things you can change in your app to make it less resource-hungry:

Check out our blog post on "Common app problems: Resource limits" for more in-depth tips prevent your app from hitting the resource limits of the Streamlit Community Cloud.

We offer free resource increases only to support nonprofits or educational organizations on a case-by-case basis. If you are a nonprofit or educational organization, please complete this form and we will review your submission as soon as possible.

Once the increase is completed, you will receive an email from the Streamlit marketing team with a confirmation that the increase has been applied.

Our forums are full of helpful information and Streamlit experts.

---

## Upgrade your app's Python version on Community Cloud - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/upgrade-python

**Contents:**
- Upgrade your app's Python version on Community Cloud
  - Still have questions?

Dependencies within Python can be upgraded in place by simply changing your environment configuration file (typically requirements.txt). However, Python itself can't be changed after deployment.

When you deploy an app, you can select the version of Python through the "Advanced settings" dialog. After you have deployed an app, you must delete it and redeploy it to change the version of Python it uses.

Take note of your app's settings:

When you delete an app, its custom subdomain is immediately available for reuse.

In a few minutes, Community Cloud will redirect you to your redployed app.

Our forums are full of helpful information and Streamlit experts.

---

## Status and limitations - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/status

**Contents:**
- Status and limitations of Community Cloud
- Community Cloud Status
- GitHub OAuth scope
  - Developer permissions
- Repository file structure
- Linux environments
- Python environments
- Configuration
- IP addresses
    - Warning

You can view the current status of Community Cloud at streamlitstatus.com.

To deploy your app, Streamlit requires access to your app's source code in GitHub and the ability to manage the public keys associated with your repositories. The default GitHub OAuth scopes are sufficient to work with apps in public GitHub repositories. However, to access your private repositories, we create a read-only GitHub Deploy Key and then access your repo using an SSH key. When we create this key, GitHub notifies repo admins of the creation as a security measure.

Streamlit requires the additional repo OAuth scope from GitHub to work with your private repos and manage deploy keys. We recognize that the repo scope provides Streamlit with extra permissions that we do not really need and which, as people who prize security, we'd rather not even be granted. This was the permission model available from GitHub when Community Cloud was created. However, we are working on adopting the new GitHub permission model to reduce uneeded permissions.

Because of the OAuth limitations noted above, a developer must have administrative permissions to a repository to deploy apps from it.

You can deploy multiple apps from your repository, and your entrypoint file(s) may be anywhere in your directory structure. However, Community Cloud initializes all apps from the root of your repository, even if the entrypoint file is in a subdirectory. This has the following consequences:

Community Cloud is built on Debian Linux.

The following configuration options are set within Community Cloud and will override any contrary setting in your config.toml file:

If you need to whitelist IP addresses for a connection, Community Cloud is currently served from the following IP addresses:

These IP addresses may change at any time without notice.

Our forums are full of helpful information and Streamlit experts.

---

## Invoking a Python subprocess in a deployed Streamlit app - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/deploy/invoking-python-subprocess-deployed-streamlit-app

**Contents:**
- Invoking a Python subprocess in a deployed Streamlit app
- Problem
- Solution
  - Relevant links
  - Still have questions?

Let's suppose you want to invoke a subprocess to run a Python script script.py in your deployed Streamlit app streamlit_app.py. For example, the machine learning library Ludwig is run using a command-line interface, or maybe you want to run a bash script or similar type of process from Python.

You have tried the following, but run into dependency issues for script.py, even though you have specified your Python dependencies in a requirements file:

When you run the above code block, you will get the version of Python that is on the system path—not necessarily the Python executable installed in the virtual environment that the Streamlit code is running under.

The solution is to detect the Python executable directly with sys.executable:

This ensures that script.py is running under the same Python executable as your Streamlit code—where your Python dependencies are installed.

Our forums are full of helpful information and Streamlit experts.

---

## Sign in & sign out - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-account/sign-in-sign-out

**Contents:**
- Sign in & sign out
- Sign in with Google
- Sign in with GitHub
    - Important
- Sign in with Email
- Sign out of your account
  - Still have questions?

After you've created your account, you can sign in to share.streamlit.io as described by the following options.

If your account is already linked to GitHub, you may be immediately prompted to sign in with GitHub.

When you sign in with GitHub, Community Cloud will look for an account that uses the same email you have on your GitHub account. If such an account doesn't exist, Community Cloud will look for an account that uses your GitHub account for source control. In this latter instance, Community Cloud will update the email on your Community Cloud account to match the email on your GitHub account.

If your account is already linked to GitHub, you may be immediately prompted to sign in with GitHub.

From your workspace, click on your workspace name in the upper-left corner. Click "Sign out."

Our forums are full of helpful information and Streamlit experts.

---

## Manage your GitHub connection - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-account/manage-your-github-connection

**Contents:**
- Manage your GitHub connection
- Add access to an organization
  - Revoke and reauthorize
  - Granting previously denied access
- Rename your GitHub account or repositories
  - Still have questions?

If you have created an account but not yet connected GitHub, see Connect your GitHub account.

If you have already connected your GitHub account but still need to allow Streamlit Community Cloud to access private repositories, see Optional: Add access to private repositories.

If you are in an organization, you can grant or request access to that organization when you connect your GitHub account. For more information, see Organization access.

If your GitHub account is already connected, you can remove permissions in your GitHub settings and force Streamlit to reprompt for GitHub authorization the next time you sign in to Community Cloud.

From your workspace, click on your workspace name in the upper-right corner. To sign out of Community Cloud, click "Sign out."

Go to your GitHub application settings at github.com/settings/applications.

Find the "Streamlit" application, and click on the three dots (more_horiz) to open the overflow menu.

If you have ever signed in to Community Cloud using GitHub, you will also see the "Streamlit Community Cloud" application in your GitHub account. The "Streamlit" application manages repository access. The "Streamlit Community Cloud" application is only for managing your identity (email) on Community Cloud. You only need to revoke access to the "Streamlit" application.

Click "I understand, revoke access."

If an organization owner has restricted Streamlit's access or restricted all OAuth applications, they may need to directly modify their permissions in GitHub. If an organization has restricted Streamlit's access, a red X (close) will appear next to the organization when you are prompted to authorize with your GitHub account.

See GitHub's documentation on OAuth apps and organizations.

Community Cloud identifies apps by their GitHub coordinates (owner, repository, branch, entrypoint file path). If you rename your account or repository from which you've deployed an app, you will lose access to administer the app. To learn more, see Rename your app in GitHub.

Our forums are full of helpful information and Streamlit experts.

---

## App dependencies for your Community Cloud app - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies

**Contents:**
- App dependencies for your Community Cloud app
    - Note
- Add Python dependencies
    - Important
    - Tip
  - Other Python package managers
    - Warning
- apt-get dependencies
  - Still have questions?

The main reason that apps fail to build properly is because Streamlit Community Cloud can't find your dependencies! There are two kinds of dependencies your app might have: Python dependencies and external dependencies. Python dependencies are other Python packages (just like Streamlit!) that you import into your script. External dependencies are less common, but they include any other software your script needs to function properly. Because Community Cloud runs on Linux, these will be Linux dependencies installed with apt-get outside the Python environment.

For your dependencies to be installed correctly, make sure you:

Python requirements files should be placed either in the root of your repository or in the same directory as your app's entrypoint file.

With each import statement in your script, you are bringing in a Python dependency. You need to tell Community Cloud how to install those dependencies through a Python package manager. We recommend using a requirements.txt file, which is based on pip.

You should not include built-in Python libraries like math, random, or distutils in your requirements.txt file. These are a part of Python and aren't installed separately. Also, Community Cloud has streamlit installed by default. You don't strictly need to include streamlit unless you want to pin or restrict the version. If you deploy an app without a requirements.txt file, your app will run in an environment with just streamlit (and its dependencies) installed.

The version of Python you use is important! Built-in libraries change between versions of Python and other libraries may have specific version requirements, too. Whenever Streamlit supports a new version of Python, Community Cloud quickly follows to default to that new version of Python. Always develop your app in the same version of Python you will use to deploy it. For more information about setting the version of Python when you deploy your app, see Optional: Configure secrets and Python version.

If you have a script like the following, no extra dependencies would be needed since pandas and numpy are installed as direct dependencies of streamlit. Similarly, math and random are built into Python.

However, a valid requirements.txt file would be:

Alternatively, if you needed to specify certain versions, another valid example would be:

In the above example, streamlit is pinned to version 1.24.1, pandas must be strictly greater than version 2.0, and numpy must be at-or-below version 1.25.1. Ea

*[Content truncated]*

---

## Secrets management for your Community Cloud app - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management

**Contents:**
- Secrets management for your Community Cloud app
- Introduction
- How to use secrets management
  - Prerequisites
  - Advanced settings
  - Edit your app's secrets
  - Still have questions?

If you are connecting to data sources, you will likely need to handle credentials or secrets. Storing unencrypted secrets in a git repository is a bad practice. If your application needs access to sensitive credentials, the recommended solution is to store those credentials in a file that is not committed to the repository and to pass them as environment variables.

Community Cloud lets you save your secrets within your app's settings. When developing locally, you can use st.secrets in your code to read secrets from a .streamlit/secrets.toml file. However, this secrets.toml file should never be committed to your repository. Instead, when you deploy your app, you can paste the contents of your secrets.toml file into the "Advanced settings" dialog. You can update your secrets at any time through your app's settings in your workspace.

While deploying your app, you can access "Advanced settings" to set your secrets. After your app is deployed, you can view or update your secrets through the app's settings. The deployment workflow is fully described on the next page, but the "Advanced settings" dialog looks like this:

Simply copy and paste the contents of your local secrets.toml file into the "Secrets" field within the dialog. After you click "Save" to commit the changes, that's it!

If you need to add or edit your secrets for an app that is already deployed, you can access secrets through your App settings. See View or update your secrets.

Our forums are full of helpful information and Streamlit experts.

---

## Deploy your app on Community Cloud - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy

**Contents:**
- Deploy your app on Community Cloud
- Select your repository and entrypoint file
- Optional: Configure secrets and Python version
    - Note
- Watch your app launch
    - Note
- View your app
  - Unique subdomains
  - Custom subdomains
  - Still have questions?

After you've organized your files and added your dependencies as described on the previous pages, you're ready to deploy your app to Community Cloud!

From your workspace at share.streamlit.io, in the upper-right corner, click "Create app."

When asked "Do you already have an app?" click "Yup, I have an app."

Fill in your repository, branch, and file path. Alternatively, to paste a link directly to your_app.py on GitHub, click "Paste GitHub URL."

Optional: In the "App URL" field, choose a subdomain for your new app.

Every Community Cloud app is deployed to a subdomain on streamlit.app, but you can change your app's subdomain at any time. For more information, see App settings. In the following example, Community Cloud will deploy an app to https://red-balloon.streamlit.app/.

Although Community Cloud attempts to suggest available repositories and files, these suggestions are not always complete. If the desired information is not listed for any field, enter it manually.

Streamlit Community Cloud supports all released versions of Python that are still receiving security updates. Streamlit Community Cloud defaults to version 3.12. You can select a version of your choice from the "Python version" dropdown in the "Advanced settings" modal. If an app is running a version of Python that becomes unsupported, it will be forcibly upgraded to the oldest supported version of Python and may break.

Click "Advanced settings."

Select your desired version of Python.

To define environment variables and secrets, in the "Secrets" field, paste the contents of your secrets.toml file.

For more information, see Community Cloud secrets management.

Your app is now being deployed, and you can watch while it launches. Most apps are deployed within a few minutes, but if your app has a lot of dependencies, it may take longer. After the initial deployment, changes to your code should be reflected immediately in your app. Changes to your dependencies will be processed immediately, but may take a few minutes to install.

The Streamlit Community Cloud logs on the right-hand side of your app are only viewable to users with write access to your repository. These logs help you debug any issues with the app. Learn more about Streamlit Community Cloud logs.

That's it—you're done! Your app now has a unique URL that you can share with others. Read more about how to Share your app with viewers.

If the "Custom subdomain (optional)" field is blank when you deploy your app, a URL is assign

*[Content truncated]*

---

## App analytics - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/app-analytics

**Contents:**
- App analytics
- Access your app analytics
  - Access app analytics from your workspace
  - Access app analytics from your Cloud logs
- App viewers
    - Important
  - Still have questions?

Streamlit Community Cloud allows you to see the viewership of each of your apps. Specifically, you can see:

You can get to your app's analytics:

From your workspace at share.streamlit.io, click the overflow icon (more_vert) next to your app. Click "Analytics."

From your app at <your-custom-subdomain>.streamlit.app, click "Manage app" in the lower-right corner.

Click the overflow menu icon (more_vert) and click "Analytics."

For public apps, we anonymize all viewers outside your workspace to protect their privacy and display anonymous viewers as random pseudonyms. You'll still be able to see the identities of fellow members in your workspace, including any viewers you've invited (once they've accepted).

When you invite a viewer to an app, they gain access to analytics as well. Additionally, if someone is invited as a viewer to any app in your workspace, they can see analytics for all public apps in your workspace and invite additional viewers themselves. A viewer in your workspace may see the emails of developers and other viewers in your workspace through analytics.

Meanwhile, for private apps where you control who has access, you will be able to see the specific users who recently viewed your apps.

Additionally, you may occasionally see anonymous users in a private app. Rest assured, these anonymous users do have authorized view access granted by you or your workspace members.

Common reasons why users show up anonymously are:

See Streamlit's general Privacy Notice.

Our forums are full of helpful information and Streamlit experts.

---

## Sign in & sign out - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/deploy/sign-in-without-sso

**Contents:**
- Sign in & sign out
- Sign in with Google
- Sign in with GitHub
    - Important
- Sign in with Email
- Sign out of your account
  - Still have questions?

After you've created your account, you can sign in to share.streamlit.io as described by the following options.

If your account is already linked to GitHub, you may be immediately prompted to sign in with GitHub.

When you sign in with GitHub, Community Cloud will look for an account that uses the same email you have on your GitHub account. If such an account doesn't exist, Community Cloud will look for an account that uses your GitHub account for source control. In this latter instance, Community Cloud will update the email on your Community Cloud account to match the email on your GitHub account.

If your account is already linked to GitHub, you may be immediately prompted to sign in with GitHub.

From your workspace, click on your workspace name in the upper-left corner. Click "Sign out."

Our forums are full of helpful information and Streamlit experts.

---

## How to submit a support case for Streamlit Community Cloud - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/deploy/how-to-submit-a-support-case-for-streamlit-community-cloud

**Contents:**
- How to submit a support case for Streamlit Community Cloud
    - Note
  - Still have questions?

This article describes the steps to submit a support request to Snowflake for Streamlit Community Cloud.

For Snowflake customers, a support case can be submitted via the support portal on Snowsight.

You should receive a confirmation email with the case number. A Snowflake Support engineer will follow up directly with the next steps to resolve your case. All communication will be through email.

Our forums are full of helpful information and Streamlit experts.

---

## File organization for your Community Cloud app - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization

**Contents:**
- File organization for your Community Cloud app
- Basic example
    - Tip
- Use an entrypoint file in a subdirectory
    - Tip
- Multiple apps in one repository
  - Still have questions?

Streamlit Community Cloud copies all the files in your repository and executes streamlit run from its root directory. Because Community Cloud is creating a new Python environment to run your app, you need to include a declaration of any App dependencies in addition to any Configuration options.

You can have multiple apps in your repository, and their entrypoint files can be anywhere in your repository. However, you can only have one configuration file. This page explains how to correctly organize your app, configuration, and dependency files. The following examples assume you are using requirements.txt to declare your dependencies because it is the most common. As explained on the next page, Community Cloud supports other formats for configuring your Python environment.

In the following example, the entrypoint file (your_app.py) is in the root of the project directory alongside a requirements.txt file to declare the app's dependencies.

If you are including custom configuration, your config file must be located at .streamlit/config.toml within your repository.

Additionally, any files that need to be locally available to your app should be included in your repository.

If you have really big or binary data that you change frequently, and git is running slowly, you might want to check out Git Large File Store (LFS) as a better way to store large files in GitHub. You don't need to make any changes to your app to start using it. If your GitHub repository uses LFS, it will just work with Streamlit Community Cloud.

When your entrypoint file is in a subdirectory, the configuration file must stay at the root. However, your dependency file may be either at the root or next to your entrypoint file.

Your dependency file can be at the root of your repository while your entrypoint file is in a subdirectory.

Alternatively, your dependency file can be in the same subdirectory as your entrypoint file.

Although most Streamlit commands interpret paths relative to the entrypoint file, some commands interpret paths relative to the working directory. On Community Cloud, the working directory is always the root of your repository. Therefore, when developing and testing your app locally, execute streamlit run from the root of your repository. This ensures that paths are interpreted consistently between your local environment and Community Cloud.

In the previous example, this would look something like this:

Remember to always use forward-slash path separators in your pat

*[Content truncated]*

---

## Manage your app - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app

**Contents:**
- Manage your app
- Manage your app from your workspace
  - Sort your apps
  - App overflow menus
- Manage your app directly from your app
  - Cloud logs
  - App chrome
- Manage your app in GitHub
  - Update your app
  - Add or remove dependencies

You can manage your deployed app from your workspace at share.streamlit.io or directly from <your-custom-subdomain>.streamlit.app. You can view, deploy, delete, reboot, or favorite an app.

Streamlit Community Cloud is organized into workspaces, which automatically group your apps according to their repository's owner in GitHub. Your workspace is indicated in the upper-left corner. For more information, see Switching workspaces.

To deploy or manage any app, always switch to the workspace matching the repository's owner first.

If you have many apps in your workspace, you can pin apps to the top by marking them as favorite (star). For more information, see Favorite your app.

Each app has a menu accessible from the overflow icon (more_vert) to the right.

If you have view-only access to an app, all options in the app's menu will be disabled except analytics.

You can manage your deployed app directly from the app itself! Just make sure you are signed in to Community Cloud, and then visit your app.

From your app at <your-custom-subdomain>.streamlit.app, click "Manage app" in the lower-right corner.

Once you've clicked on "Manage app", you will be able to view your app's logs. This is your primary place to troubleshoot any issues with your app.

You can access more developer options by clicking the overflow icon (more_vert) at the bottom of your Cloud logs. To conveniently download your logs, click "Download log."

Other options accessible from Cloud logs are:

From your app at <your-custom-subdomain>.streamlit.app, you can always access the app chrome just like you can when developing locally. The option to deploy your app is removed, but you can still clear your cache from here.

Your GitHub repository is the source for your app, so that means that any time you push an update to your repository you'll see it reflected in the app in almost real time. Try it out!

Streamlit also smartly detects whether you touched your dependencies, in which case it will automatically do a full redeploy for you—which will take a little more time. But since most updates don't involve dependency changes, you should usually see your app update in real time.

To add or remove dependencies at any point, just update requirements.txt (Python dependenciess) or packages.txt (Linux dependencies), and commit the changes to your repository on GitHub. Community Cloud detects the change in your dependencies and automatically triggers (re)installation.

It is best practice to pin your St

*[Content truncated]*

---

## Manage your account - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-account

**Contents:**
- Manage your account
- Access your workspace settings
  - Still have questions?

You can Update your email or completely Delete your account through Workspace settings.

Your Streamlit Community Cloud account is identified by your email. When you sign in to Community Cloud, regardless of which method you use, you are providing Community Cloud with your email address. In particular, when you sign in to Community Cloud using GitHub, you are using the primary email on your GitHub account. You can view your email identity and source-control identity from your workspace settings, under "Linked accounts."

Our forums are full of helpful information and Streamlit experts.

---

## Delete your app - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/delete-your-app

**Contents:**
- Delete your app
  - Delete your app from your workspace
  - Delete your app from your Cloud logs
  - Still have questions?

If you need to delete your app, it's simple and easy. There are several cases where you may need to delete your app:

If you delete your app and intend to immediately redploy it, your custom subdomain should be immediately available for reuse. Read more about data deletion in Streamlit trust and security.

You can delete your app:

From your workspace at share.streamlit.io, click the overflow icon (more_vert) next to your app. Click "Delete."

A confirmation will display. Enter the required confirmation string and click "Delete."

From your app at <your-custom-subdomain>.streamlit.app, click "Manage app" in the lower-right corner.

Click the overflow menu icon (more_vert) and click "Delete app."

A confirmation will display. Enter the required confirmation string and click "Delete."

Our forums are full of helpful information and Streamlit experts.

---

## Streamlit in Snowflake - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/snowflake

**Contents:**
- Deploy Streamlit apps in Snowflake
    - Streamlit in Snowflake Quickstart
    - Examples
    - Get started with Snowflake
    - Note
  - Still have questions?

Host your apps alongside your data in a single, global platform. Snowflake provides industry-leading features that ensure the highest levels of security for your account, users, data, and apps. If you're looking for an enterprise hosting solution, try Snowflake!

Create a free trial account and deploy an app with Streamlit in Snowflake.

Explore a wide variety of example apps in Snowflake Labs' snowflake-demo-streamlit repository.

Learn more in Snowflake's documentation.

There are three ways to host Streamlit apps in Snowflake:

Streamlit in Snowflake. Run your Streamlit app as a native object in Snowflake. Enjoy an in-browser editor and minimal work to configure your environment. Share your app with other users in your Snowflake account through role-based access control (RBAC). This is a great way to deploy apps internally for your business. Check out Snowflake docs!

Snowflake Native Apps. Package your app with data and share it with other Snowflake accounts. This is a great way to share apps and their underlying data with other organizations who use Snowflake. Check out Snowflake docs!

Snowpark Container Services. Deploy your app in a container that's optimized to run in Snowflake. This is the most flexible option, where you can use any library and assign a public URL to your app. Manage your allowed viewers through your Snowflake account. Check out Snowflake docs!

Using Snowpark Container Services to deploy a Streamlit app requires a compute pool, which is not available in a trial account at this time.

Our forums are full of helpful information and Streamlit experts.

---

## Update your email - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-account/update-your-email

**Contents:**
- Update your email
- Option 1: Create a new account and merge it
- Option 2: Use your GitHub account
    - Important
  - Still have questions?

To update your email on Streamlit Community Cloud, you have two options: You can create a new account and merge your existing account into it, or you can use your GitHub account to update your email.

Two Community Cloud accounts can't have the same GitHub account for source control. When you connect a GitHub account to a new Community Cloud account for source control, Community Cloud will automatically merge any existing account with the same source control.

Therefore, you can create a new account with the desired email and connect the same GitHub account to merge them together.

Your old and new accounts are now merged, and you have effectively changed your email address.

Alternatively, you can change the email on your GitHub account and then sign in to Community Cloud with GitHub.

Go to GitHub, and set your primary email address to your new email.

If you are currently signed in to Community Cloud, sign out.

Sign in to Community Cloud using GitHub.

If you are redirected to your workspace and you see your existing apps, you're done! Your email has been changed. To confirm your current email and GitHub account, click on your workspace name in the upper-left corner, and look at the bottom of the drop-down menu.

If you are redirected to an empty workspace and you see "Workspaces warning" in the upper-left corner, proceed to Connect your GitHub account. This can happen if you previously created an account with your new email but didn't connect a GitHub account to it.

If you have multiple GitHub accounts, be careful. To avoid unexpected behavior, either use unique emails on each GitHub account or avoid signing in to Community Cloud using GitHub.

Our forums are full of helpful information and Streamlit experts.

---

## How can I deploy multiple Streamlit apps on different subdomains? - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/deploy/deploy-multiple-streamlit-apps-different-subdomains

**Contents:**
- How can I deploy multiple Streamlit apps on different subdomains?
- Problem
- Solution
  - Still have questions?

You want to deploy multiple Streamlit apps on different subdomains.

Like running your Streamlit app on more common ports such as 80, subdomains are handled by a web server like Apache or Nginx:

Set up a web server on a machine with a public IP address, then use a DNS server to point all desired subdomains to your webserver's IP address

Configure your web server to route requests for each subdomain to the different ports that your Streamlit apps are running on

For example, let’s say you had two Streamlit apps called Calvin and Hobbes. App Calvin is running on port 8501. You set up app Hobbes to run on port 8502. Your webserver would then be set up to "listen" for requests on subdomains calvin.somedomain.com and hobbes.subdomain.com, and route requests to port 8501 and 8502, respectively.

Check out these two tutorials for Apache2 and Nginx that deal with setting up a webserver to redirect subdomains to different ports:

Our forums are full of helpful information and Streamlit experts.

---

## Favorite your app - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/favorite-your-app

**Contents:**
- Favorite your app
    - Note
- Favoriting and unfavoriting your app
  - Favorite your app from your workspace
  - Favorite your app from your app toolbar
  - Still have questions?

Streamlit Community Cloud supports a "favorite" feature that lets you quickly access your apps from your workspace. Favorited apps appear at the top of their workspace with a yellow star (star) beside them. You can favorite and unfavorite apps in any workspace to which you have access as a developer or invited viewer.

Favorites are specific to your account. Other members of your workspace cannot see which apps you have favorited.

You can favorite your app:

From your workspace at share.streamlit.io, hover over your app.

If your app is not yet favorited, a star outline (star_border) will appear on hover.

Click on the star (star_border/star) next to your app name to toggle its favorited status.

From your app at <your-custom-subdomain>.streamlit.app, click the star (star_border/star) in the upper-right corner to toggle your app's favorited status.

Our forums are full of helpful information and Streamlit experts.

---

## Embed your app - Streamlit Docs

**URL:** https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app/embed-your-app

**Contents:**
- Embed your app
- Embedding with iframes
    - Important
- Embedding with oEmbed
  - Example
    - Tip
  - Key Sites for oEmbed
  - iframe versus oEmbed
- Embed options
  - Build an embed link

Embedding Streamlit Community Cloud apps enriches your content by integrating interactive, data-driven applications directly within your pages. Whether you're writing a blog post, a technical document, or sharing resources on platforms like Medium, Notion, or even StackOverflow, embedding Streamlit apps adds a dynamic component to your content. This allows your audience to interact with your ideas, rather than merely reading about them or looking at screenshots.

Streamlit Community Cloud supports both iframe and oEmbed methods for embedding public apps. This flexibility enables you to share your apps across a wide array of platforms, broadening your app's visibility and impact. In this guide, we'll cover how to use both methods effectively to share your Streamlit apps with the world.

Streamlit Community Cloud supports embedding public apps using the subdomain scheme. To embed a public app, add the query parameter /?embed=true to the end of the *.streamlit.app URL.

For example, say you want to embed the 30DaysOfStreamlit app. The URL to include in your iframe is: https://30days.streamlit.app/?embed=true:

There will be no official support for embedding private apps.

In addition to allowing you to embed apps via iframes, the ?embed=true query parameter also does the following:

For granular control over the embedding behavior, Streamlit allows you to specify one or more instances of the ?embed_options query parameter (e.g. to show the toolbar, open the app in dark theme, etc). Click here for a full list of Embed options.

Streamlit's oEmbed support allows for a simpler embedding experience. You can directly drop a Streamlit app's URL into a Medium, Ghost, or Notion page (or any of more than 700 content providers that supports oEmbed or embed.ly). The embedded app will automatically appear! This helps Streamlit Community Cloud apps seamlessly integrate into these platforms, improving the visibility and accessibility of your apps.

When creating content in a Notion page, Medium article, or Ghost blog, you only need to paste the app's URL and hit "Enter." The app will then render automatically at that spot in your content. You can use your undecorated app URL without the ?embed=true query parameter.

Here's an example of @chrieke's Prettymapp app embedded in a Medium article:

Ensure the platform hosting the embedded Streamlit app supports oEmbed or embed.ly.

oEmbed should work out of the box for several platforms including but not limited to:

Please chec

*[Content truncated]*

---

## App is not loading when running remotely - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/deploy/remote-start

**Contents:**
- App is not loading when running remotely
  - Symptom #1: The app never loads
  - Symptom #2: The app says "Please wait..." or shows skeleton elements forever
  - Symptom #3: Unable to upload files when running in multiple replicas
  - Still have questions?

Below are a few common errors that occur when users spin up their own solution to host a Streamlit app remotely.

To learn about a deceptively simple way to host Streamlit apps that avoids all the issues below, check out Streamlit Community Cloud.

When you enter the app's URL in a browser and all you see is a blank page, a "Page not found" error, a "Connection refused" error, or anything like that, first check that Streamlit is actually running on the remote server. On a Linux server you can SSH into it and then run:

If you see Streamlit running, the most likely culprit is the Streamlit port not being exposed. The fix depends on your exact setup. Below are three example fixes:

Try port 80: Some hosts expose port 80 by default. To set Streamlit to use that port, start Streamlit with the --server.port option:

AWS EC2 server: First, click on your instance in the AWS Console. Then scroll down and click on Security Groups → Inbound → Edit. Next, add a Custom TCP rule that allows the Port Range 8501 with Source 0.0.0.0/0.

Other types of server: Check the firewall settings.

If that still doesn't solve the problem, try running a simple HTTP server instead of Streamlit, and seeing if that works correctly. If it does, then you know the problem lies somewhere in your Streamlit app or configuration (in which case you should ask for help in our forums!) If not, then it's definitely unrelated to Streamlit.

How to start a simple HTTP server:

This symptom appears differently starting from version 1.29.0. For earlier versions of Streamlit, a loading app shows a blue box in the center of the page with a "Please wait..." message. Starting from version 1.29.0, a loading app shows skeleton elements. If this loading screen does not go away, the underlying cause is likely one of the following:

To diagnose the issue, first make sure you are not using port 3000. If in doubt, try port 80 as described above.

Next, try temporarily disabling CORS protection by running Streamlit with the --server.enableCORS flag set to false:

If this fixes your issue, you should re-enable CORS protection and then set browser.serverAddress to the URL of your Streamlit app.

If the issue persists, try disabling websocket compression by running Streamlit with the --server.enableWebsocketCompression flag set to false

If this fixes your issue, your server setup is likely stripping the Sec-WebSocket-Extensions HTTP header that is used to negotiate Websocket compression.

Compression is not requir

*[Content truncated]*

---

## Upgrade your app's Streamlit version on Streamlit Community Cloud - Streamlit Docs

**URL:** https://docs.streamlit.io/knowledge-base/deploy/upgrade-streamlit-version-on-streamlit-cloud

**Contents:**
- Upgrade your app's Streamlit version on Streamlit Community Cloud
- No dependency file
- With a dependency file
  - Still have questions?

Want to use a cool new Streamlit feature but your app on Streamlit Community Cloud is running an old version of the Streamlit library? If that's you, don't worry! Here's how to upgrade your app's Streamlit version, based on how you manage your app dependencies:

When there is no dependencies file in your repository, your app will use the lastest Streamlit version that existed when it was last rebooted. In this case, simply reboot your app and Community Cloud will install the latest version.

You may want to avoid getting into this situation if your app depends on a specific version of Streamlit. That is why we encourage you to use a dependency file and pin your desired version of Streamlit.

When your app includes a dependency file, reboot your app or change your dependency file as follows:

If Streamlit is not included in your dependency file, reboot the app as described above.

Note that we don't recommend having an incomplete dependency file since pip won't be able to include streamlit when resolving compatible versions of your dependencies.

If Streamlit is included in your dependency file, but the version is not pinned or capped, reboot the app as described above.

When Community Cloud reboots your app, it will re-resolve your dependency file. Your app will then have the latest version of all dependencies that are consistent with your dependency file.

If Streamlit is included in your dependency file, and the version is pinned (e.g., streamlit==1.37.0), update your dependency file.

When you commit a change to your dependency file in your repository, Community Cloud will detect the change and automatically resolve the new dependencies. This is how you add, remove, or change all Python dependencies in general. You don't need to manually reboot your app, but you can if you want to.

Our forums are full of helpful information and Streamlit experts.

---
