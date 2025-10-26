# Streamlit - Api

**Pages:** 187

---

## config.toml - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/configuration/config.toml

**Contents:**
- config.toml
  - File location
  - File format
    - Example
  - Available configuration options
    - Global
    - Logger
    - Client
    - Runner
    - Server

config.toml is an optional file you can define for your working directory or global development environment. When config.toml is defined both globally and in your working directory, Streamlit combines the configuration options and gives precedence to the working-directory configuration. Additionally, you can use environment variables and command-line options to override additional configuration options. For more information, see Configuration options.

To define your configuration locally or per-project, add .streamlit/config.toml to your working directory. Your working directory is wherever you call streamlit run. If you haven't previously created the .streamlit directory, you will need to add it.

To define your configuration globally, you must first locate your global .streamlit directory. Streamlit adds this hidden directory to your OS user profile during installation. For MacOS/Linux, this will be ~/.streamlit/config.toml. For Windows, this will be %userprofile%/.streamlit/config.toml.

config.toml is a TOML file.

Below are all the sections and options you can have in your .streamlit/config.toml file. To see all configurations, use the following command in your terminal or CLI:

Our forums are full of helpful information and Streamlit experts.

---

## st.set_page_config - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/configuration/st.set_page_config

**Contents:**
- st.set_page_config
    - Example
  - Still have questions?

Configure the default settings of the page.

This command can be called multiple times in a script run to dynamically change the page configuration. The calls are additive, with each successive call overriding only the parameters that are specified.

st.set_page_config(page_title=None, page_icon=None, layout=None, initial_sidebar_state=None, menu_items=None)

page_title (str or None)

The page title, shown in the browser tab. If this is None (default), the page title is inherited from the previous call of st.set_page_config. If this is None and no previous call exists, the page title is inferred from the page source.

If a page source is a Python file, its inferred title is derived from the filename. If a page source is a callable object, its inferred title is derived from the callable's name.

page_icon (Anything supported by st.image (except list), str, or None)

The page favicon. If page_icon is None (default), the page icon is inherited from the previous call of st.set_page_config. If this is None and no previous call exists, the favicon is a monochrome Streamlit logo.

In addition to the types supported by st.image (except list), the following strings are valid:

A single-character emoji. For example, you can set page_icon="🦈".

An emoji short code. For example, you can set page_icon=":shark:". For a list of all supported codes, see https://share.streamlit.io/streamlit/emoji-shortcodes.

The string literal, "random". You can set page_icon="random" to set a random emoji from the supported list above.

An icon from the Material Symbols library (rounded style) in the format ":material/icon_name:" where "icon_name" is the name of the icon in snake case.

For example, page_icon=":material/thumb_up:" will display the Thumb Up icon. Find additional icons in the Material Symbols font library.

Colors are not supported for Material icons. When you use a Material icon for favicon, it will be black, regardless of browser theme.

layout ("centered", "wide", or None)

How the page content should be laid out. If this is None (default), the page layout is inherited from the previous call of st.set_page_config. If this is None and no previous call exists, the page layout is "centered".

"centered" constrains the elements into a centered column of fixed width. "wide" uses the entire screen.

initial_sidebar_state ("auto", "expanded", "collapsed", or None)

How the sidebar should start out. If this is None (default), the sidebar state is inherited from the previous cal

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.set_page_config(
    page_title="Ex-stream-ly Cool App",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://www.extremelycoolapp.com/help',
        'Report a bug': "https://www.extremelycoolapp.com/bug",
        'About': "# This is a header. This is an *extremely* cool app!"
    }
)
```

---

## st.caption - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/text/st.caption

**Contents:**
- st.caption
    - Examples
  - Still have questions?

Display text in small font.

This should be used for captions, asides, footnotes, sidenotes, and other explanatory text.

st.caption(body, unsafe_allow_html=False, *, help=None, width="stretch")

The text to display as GitHub-flavored Markdown. Syntax information can be found at: https://github.github.com/gfm.

See the body parameter of st.markdown for additional, supported Markdown directives.

unsafe_allow_html (bool)

Whether to render HTML within body. If this is False (default), any HTML tags found in body will be escaped and therefore treated as raw text. If this is True, any HTML expressions within body will be rendered.

Adding custom HTML to your app impacts safety, styling, and maintainability.

If you only want to insert HTML or CSS without Markdown text, we recommend using st.html instead.

A tooltip that gets displayed next to the caption. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

width ("stretch", "content", or int)

The width of the caption element. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.caption("This is a string that explains something above.")
st.caption("A caption with _italics_ :blue[colors] and emojis :sunglasses:")
```

---

## 2024 release notes - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/quick-reference/release-notes/2024

**Contents:**
- 2024 release notes
- Version 1.41.0
- Version 1.40.0
- Version 1.39.0
- Version 1.38.0
- Version 1.37.0
- Version 1.36.0
- Version 1.35.0
- Version 1.34.0
- Version 1.33.0

This page contains release notes for Streamlit versions released in 2024. For the latest version of Streamlit, see Release notes.

Release date: December 10, 2024

Release date: November 6, 2024

Release date: October 1, 2024

Release date: August 27, 2024

Release date: July 25, 2024

Release date: June 20, 2024

Release date: May 23, 2024

Release date: May 2, 2024

Release date: April 4, 2024

Release date: March 7, 2024

Release date: February 1, 2024

Release date: January 11, 2024

Our forums are full of helpful information and Streamlit experts.

---

## st.popover - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/layout/st.popover

**Contents:**
- st.popover
    - Examples
  - Still have questions?

Insert a popover container.

Inserts a multi-element container as a popover. It consists of a button-like element and a container that opens when the button is clicked.

Opening and closing the popover will not trigger a rerun. Interacting with widgets inside of an open popover will rerun the app while keeping the popover open. Clicking outside of the popover will close it.

To add elements to the returned container, you can use the "with" notation (preferred) or just call methods directly on the returned object. See examples below.

To follow best design practices, don't nest popovers.

st.popover(label, *, help=None, icon=None, disabled=False, use_container_width=None, width="content")

The label of the button that opens the popover container. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

A tooltip that gets displayed when the popover button is hovered over. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

An optional emoji or icon to display next to the button label. If icon is None (default), no icon is displayed. If icon is a string, the following options are valid:

A single-character emoji. For example, you can set icon="🚨" or icon="🔥". Emoji short codes are not supported.

An icon from the Material Symbols library (rounded style) in the format ":material/icon_name:" where "icon_name" is the name of the icon in snake case.

For example, icon=":material/thumb_up:" will display the Thumb Up icon. Find additional icons in the Material Symbols font library.

An optional boolean that disables the popover button if set to True. The default is False.

use_container_width (bool)

use_container_width is deprecated and will be removed in a future release. For use_container_width=True, use width="stretch". For use_container_width=False, use width="content".

Whether to expand the button's width to fill its parent container. If use_container_width is False (defaul

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

with st.popover("Open popover"):
    st.markdown("Hello World 👋")
    name = st.text_input("What's your name?")

st.write("Your name:", name)
```

Example 2 (unknown):
```unknown
import streamlit as st

popover = st.popover("Filter items")
red = popover.checkbox("Show red items.", True)
blue = popover.checkbox("Show blue items.", True)

if red:
    st.write(":red[This is a red item.]")
if blue:
    st.write(":blue[This is a blue item.]")
```

---

## Authentication and user info - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/user

**Contents:**
- Authentication and user info
    - Log in a user
    - Log out a user
    - User info
  - Still have questions?

Streamlit provides native support for user authentication so you can personalize your apps. You can also directly read headers and cookies.

st.login() starts an authentication flow with an identity provider.

st.logout() removes a user's identity information.

st.user returns information about a logged-in user.

Our forums are full of helpful information and Streamlit experts.

---

## Chart elements - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/charts

**Contents:**
- Chart elements
- Simple chart elements
    - Simple area charts
    - Simple bar charts
    - Simple line charts
    - Simple scatter charts
    - Scatterplots on maps
- Advanced chart elements
    - Matplotlib
    - Altair

Streamlit supports several different charting libraries, and our goal is to continually add support for more. Right now, the most basic library in our arsenal is Matplotlib. Then there are also interactive charting libraries like Vega Lite (2D charts) and deck.gl (maps and 3D charts). And finally we also provide a few chart types that are "native" to Streamlit, like st.line_chart and st.area_chart.

Display an area chart.

Display a line chart.

Display a line chart.

Display a map with points on it.

Display a matplotlib.pyplot figure.

Display a chart using the Altair library.

Display a chart using the Vega-Lite library.

Display an interactive Plotly chart.

Display an interactive Bokeh chart.

Display a chart using the PyDeck library.

Display a graph using the dagre-d3 library.

Third-party components

These are featured components created by our lovely community. For more examples and inspiration, check out our Components Gallery and Streamlit Extras!

Integrate Lottie animations inside your Streamlit app. Created by @andfanilo.

Make Plotly charts interactive!. Created by @null-jones.

A library with useful Streamlit extras. Created by @arnaudmiribel.

A deceptively simple plotting library for Streamlit. Created by @tvst.

High dimensional Interactive Plotting. Created by @facebookresearch.

High dimensional Interactive Plotting. Created by @andfanilo.

Streamlit Component for rendering Folium maps. Created by @randyzwitch.

spaCy building blocks and visualizers for Streamlit apps. Created by @explosion.

A Streamlit Graph Vis, based on react-grah-vis. Created by @ChrisDelClea.

Integrate Lottie animations inside your Streamlit app. Created by @andfanilo.

Make Plotly charts interactive!. Created by @null-jones.

A library with useful Streamlit extras. Created by @arnaudmiribel.

A deceptively simple plotting library for Streamlit. Created by @tvst.

High dimensional Interactive Plotting. Created by @facebookresearch.

High dimensional Interactive Plotting. Created by @andfanilo.

Streamlit Component for rendering Folium maps. Created by @randyzwitch.

spaCy building blocks and visualizers for Streamlit apps. Created by @explosion.

A Streamlit Graph Vis, based on react-grah-vis. Created by @ChrisDelClea.

Integrate Lottie animations inside your Streamlit app. Created by @andfanilo.

Make Plotly charts interactive!. Created by @null-jones.

A library with useful Streamlit extras. Created by @arnaudmiribel.

Our forums are full of helpful informatio

*[Content truncated]*

---

## st.error - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/status/st.error

**Contents:**
- st.error
    - Example
  - Still have questions?

Display error message.

st.error(body, *, icon=None, width="stretch")

The text to display as GitHub-flavored Markdown. Syntax information can be found at: https://github.github.com/gfm.

See the body parameter of st.markdown for additional, supported Markdown directives.

An optional emoji or icon to display next to the alert. If icon is None (default), no icon is displayed. If icon is a string, the following options are valid:

A single-character emoji. For example, you can set icon="🚨" or icon="🔥". Emoji short codes are not supported.

An icon from the Material Symbols library (rounded style) in the format ":material/icon_name:" where "icon_name" is the name of the icon in snake case.

For example, icon=":material/thumb_up:" will display the Thumb Up icon. Find additional icons in the Material Symbols font library.

width ("stretch" or int)

The width of the alert element. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.error('This is an error', icon="🚨")
```

---

## st.help - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/text/st.help

**Contents:**
- st.help
    - Example
  - Still have questions?

Display help and other information for a given object.

Depending on the type of object that is passed in, this displays the object's name, type, value, signature, docstring, and member variables, methods — as well as the values/docstring of members and methods.

st.help(obj=, *, width="stretch")

The object whose information should be displayed. If left unspecified, this call will display help for Streamlit itself.

width ("stretch" or int)

The width of the help element. This can be one of the following:

Don't remember how to initialize a dataframe? Try this:

Want to quickly check what data type is output by a certain function? Try:

Want to quickly inspect an object? No sweat:

And if you're using Magic, you can get help for functions, classes, and modules without even typing st.help:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st
import pandas

st.help(pandas.DataFrame)
```

Example 2 (unknown):
```unknown
import streamlit as st

x = my_poorly_documented_function()
st.help(x)
```

Example 3 (python):
```python
class Dog:
  '''A typical dog.'''

  def __init__(self, breed, color):
    self.breed = breed
    self.color = color

  def bark(self):
    return 'Woof!'


fido = Dog("poodle", "white")

st.help(fido)
```

Example 4 (unknown):
```unknown
import streamlit as st
import pandas

# Get help for Pandas read_csv:
pandas.read_csv

# Get help for Streamlit itself:
st
```

---

## streamlit docs - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/cli/docs

**Contents:**
- $ streamlit docs
  - Syntax
  - Still have questions?

Open the Streamlit docs in your default browser.

Our forums are full of helpful information and Streamlit experts.

---

## st.connections.BaseConnection - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/connections/st.connections.baseconnection

**Contents:**
    - Tip
- st.connections.BaseConnection
- BaseConnection.reset
    - Example
  - Still have questions?

This page only contains information on the st.connections.BaseConnection class. For a deeper dive into creating and managing data connections within Streamlit apps, read Connecting to data.

The abstract base class that all Streamlit Connections must inherit from.

This base class provides connection authors with a standardized way to hook into the st.connection() factory function: connection authors are required to provide an implementation for the abstract method _connect in their subclasses.

Additionally, it also provides a few methods/properties designed to make implementation of connections more convenient. See the docstrings for each of the methods of this class for more information

While providing an implementation of _connect is technically all that's required to define a valid connection, connections should also provide the user with context-specific ways of interacting with the underlying connection object. For example, the first-party SQLConnection provides a query() method for reads and a session property for more complex operations.

st.connections.BaseConnection(connection_name, **kwargs)

Reset this connection so that it gets reinitialized the next time it's used.

Reset this connection so that it gets reinitialized the next time it's used.

This method can be useful when a connection has become stale, an auth token has expired, or in similar scenarios where a broken connection might be fixed by reinitializing it. Note that some connection methods may already use reset() in their error handling code.

BaseConnection.reset()

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

conn = st.connection("my_conn")

# Reset the connection before using it if it isn't healthy
# Note: is_healthy() isn't a real method and is just shown for example here.
if not conn.is_healthy():
    conn.reset()

# Do stuff with conn...
```

---

## st.column_config - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config

**Contents:**
- Column configuration
    - Column
    - Text column
    - Number column
    - Checkbox column
    - Selectbox column
    - Multiselect column
    - Datetime column
    - Date column
    - Time column

When working with data in Streamlit, the st.column_config class is a powerful tool for configuring data display and interaction. Specifically designed for the column_config parameter in st.dataframe and st.data_editor, it provides a suite of methods to tailor your columns to various data types - from simple text and numbers to lists, URLs, images, and more.

Whether it's translating temporal data into user-friendly formats or utilizing charts and progress bars for clearer data visualization, column configuration not only provides the user with an enriched data viewing experience but also ensures that you're equipped with the tools to present and interact with your data, just the way you want it.

Configure a generic column.

Configure a text column.

Configure a number column.

Configure a checkbox column.

Configure a selectbox column.

Configure a multiselect column.

Configure a datetime column.

Configure a date column.

Configure a time column.

Configure a JSON column.

Configure a list column.

Configure a link column.

Configure an image column.

Configure an area chart column.

Configure a line chart column.

Configure a bar chart column.

Configure a progress column.

Our forums are full of helpful information and Streamlit experts.

---

## st.cache_data - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data

**Contents:**
    - Tip
- st.cache_data
    - Example
    - Warning
- st.cache_data.clear
    - Example
- CachedFunc.clear
    - Example
- Using Streamlit commands in cached functions
  - Static elements

This page only contains information on the st.cache_data API. For a deeper dive into caching and how to use it, check out Caching.

Decorator to cache functions that return data (e.g. dataframe transforms, database queries, ML inference).

Cached objects are stored in "pickled" form, which means that the return value of a cached function must be pickleable. Each caller of the cached function gets its own copy of the cached data.

You can clear a function's cache with func.clear() or clear the entire cache with st.cache_data.clear().

A function's arguments must be hashable to cache it. If you have an unhashable argument (like a database connection) or an argument you want to exclude from caching, use an underscore prefix in the argument name. In this case, Streamlit will return a cached value when all other arguments match a previous function call. Alternatively, you can declare custom hashing functions with hash_funcs.

Cached values are available to all users of your app. If you need to save results that should only be accessible within a session, use Session State instead. Within each user session, an @st.cache_data-decorated function returns a copy of the cached return value (if the value is already cached). To cache shared global resources (singletons), use st.cache_resource instead. To learn more about caching, see Caching overview.

Caching async functions is not supported. To upvote this feature, see GitHub issue #8308.

st.cache_data(func=None, *, ttl, max_entries, show_spinner, show_time=False, persist, hash_funcs=None)

The function to cache. Streamlit hashes the function's source code.

ttl (float, timedelta, str, or None)

The maximum time to keep an entry in the cache. Can be one of:

Note that ttl will be ignored if persist="disk" or persist=True.

max_entries (int or None)

The maximum number of entries to keep in the cache, or None for an unbounded cache. When a new entry is added to a full cache, the oldest cached entry will be removed. Defaults to None.

show_spinner (bool or str)

Enable the spinner. Default is True to show a spinner when there is a "cache miss" and the cached data is being created. If string, value of show_spinner param will be used for spinner text.

Whether to show the elapsed time next to the spinner text. If this is False (default), no time is displayed. If this is True, elapsed time is displayed with a precision of 0.1 seconds. The time format is not configurable.

persist ("disk", bool, or None)

Optional locatio

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import streamlit as st

@st.cache_data
def fetch_and_clean_data(url):
    # Fetch data from URL here, and then clean it up.
    return data

d1 = fetch_and_clean_data(DATA_URL_1)
# Actually executes the function, since this is the first time it was
# encountered.

d2 = fetch_and_clean_data(DATA_URL_1)
# Does not execute the function. Instead, returns its previously computed
# value. This means that now the data in d1 is the same as in d2.

d3 = fetch_and_clean_data(DATA_URL_2)
# This is a different URL, so the function executes.
```

Example 2 (python):
```python
import streamlit as st

@st.cache_data(persist="disk")
def fetch_and_clean_data(url):
    # Fetch data from URL here, and then clean it up.
    return data
```

Example 3 (python):
```python
import streamlit as st

@st.cache_data
def fetch_and_clean_data(_db_connection, num_rows):
    # Fetch data from _db_connection here, and then clean it up.
    return data

connection = make_database_connection()
d1 = fetch_and_clean_data(connection, num_rows=10)
# Actually executes the function, since this is the first time it was
# encountered.

another_connection = make_database_connection()
d2 = fetch_and_clean_data(another_connection, num_rows=10)
# Does not execute the function. Instead, returns its previously computed
# value - even though the _database_connection parameter was differen
...
```

Example 4 (python):
```python
import streamlit as st

@st.cache_data
def fetch_and_clean_data(_db_connection, num_rows):
    # Fetch data from _db_connection here, and then clean it up.
    return data

fetch_and_clean_data.clear(_db_connection, 50)
# Clear the cached entry for the arguments provided.

fetch_and_clean_data.clear()
# Clear all cached entries for this function.
```

---

## st.badge - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/text/st.badge

**Contents:**
- st.badge
    - Examples
  - Still have questions?

Display a colored badge with an icon and label.

This is a thin wrapper around the color-badge Markdown directive. The following are equivalent:

You can insert badges everywhere Streamlit supports Markdown by using the color-badge Markdown directive. See st.markdown for more information.

st.badge(label, *, icon=None, color="blue", width="content")

The label to display in the badge. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code.

See the body parameter of st.markdown for additional, supported Markdown directives. Because this command escapes square brackets ([ ]) in this parameter, any directive requiring square brackets is not supported.

An optional emoji or icon to display next to the badge label. If icon is None (default), no icon is displayed. If icon is a string, the following options are valid:

A single-character emoji. For example, you can set icon="🚨" or icon="🔥". Emoji short codes are not supported.

An icon from the Material Symbols library (rounded style) in the format ":material/icon_name:" where "icon_name" is the name of the icon in snake case.

For example, icon=":material/thumb_up:" will display the Thumb Up icon. Find additional icons in the Material Symbols font library.

The color to use for the badge. This defaults to "blue".

This can be one of the following supported colors: red, orange, yellow, blue, green, violet, gray/grey, or primary. If you use "primary", Streamlit will use the default primary accent color unless you set the theme.primaryColor configuration option.

width ("content", "stretch", or int)

The width of the badge element. This can be one of the following:

Create standalone badges with st.badge (with or without icons). If you want to have multiple, side-by-side badges, you can use the Markdown directive in st.markdown.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.badge("New")
st.badge("Success", icon=":material/check:", color="green")

st.markdown(
    ":violet-badge[:material/star: Favorite] :orange-badge[⚠️ Needs review] :gray-badge[Deprecated]"
)
```

---

## st.pyplot - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/charts/st.pyplot

**Contents:**
- st.pyplot
    - Example
    - Warning
  - Still have questions?

Display a matplotlib.pyplot figure.

You must install matplotlib>=3.0.0 to use this command. You can install all charting dependencies (except Bokeh) as an extra with Streamlit:

st.pyplot(fig=None, clear_figure=None, *, width="stretch", use_container_width=None, **kwargs)

fig (Matplotlib Figure)

The Matplotlib Figure object to render. See https://matplotlib.org/stable/gallery/index.html for examples.

When this argument isn't specified, this function will render the global Matplotlib figure object. However, this feature is deprecated and will be removed in a later version.

If True, the figure will be cleared after being rendered. If False, the figure will not be cleared after being rendered. If left unspecified, we pick a default based on the value of fig.

width ("stretch", "content", or int)

The width of the chart element. This can be one of the following:

use_container_width (bool)

use_container_width is deprecated and will be removed in a future release. For use_container_width=True, use width="stretch". For use_container_width=False, use width="content".

Whether to override the figure's native width with the width of the parent container. If use_container_width is True (default), Streamlit sets the width of the figure to match the width of the parent container. If use_container_width is False, Streamlit sets the width of the chart to fit its contents according to the plotting library, up to the width of the parent container.

Arguments to pass to Matplotlib's savefig function.

Matplotlib supports several types of "backends". If you're getting an error using Matplotlib with Streamlit, try setting your backend to "TkAgg":

For more information, see https://matplotlib.org/faq/usage_faq.html.

Matplotlib doesn't work well with threads. So if you're using Matplotlib you should wrap your code with locks. This Matplotlib bug is more prominent when you deploy and share your apps because you're more likely to get concurrent users then. The following example uses Rlock from the threading module.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
pip install streamlit[charts]
```

Example 2 (python):
```python
import matplotlib.pyplot as plt
import streamlit as st
from numpy.random import default_rng as rng

arr = rng(0).normal(1, 1, size=100)
fig, ax = plt.subplots()
ax.hist(arr, bins=20)

st.pyplot(fig)
```

Example 3 (unknown):
```unknown
echo "backend: TkAgg" >> ~/.matplotlib/matplotlibrc
```

---

## API Reference - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference

**Contents:**
- API reference
- Display almost anything
  - Write and magic
    - st.write
    - st.write_stream
    - Magic
  - Text elements
    - Markdown
    - Title
    - Header

Streamlit makes it easy for you to visualize, mutate, and share data. The API reference is organized by activity type, like displaying data or optimizing performance. Each section includes methods associated with the activity type, including examples.

Browse our API below and click to learn more about any of our available commands! 🎈

Write arguments to the app.

Write generators or streams to the app with a typewriter effect.

Any time Streamlit sees either a variable or literal value on its own line, it automatically writes that to your app using st.write

Display string formatted as Markdown.

Display text in title formatting.

Display text in header formatting.

Display text in subheader formatting.

Display a small, colored badge.

Display text in small font.

Display a code block with optional syntax highlighting.

Display some code in the app, then execute it. Useful for tutorials.

Display mathematical expressions formatted as LaTeX.

Write fixed-width and preformatted text.

Display a horizontal rule.

Display object’s doc string, nicely formatted.

Renders HTML strings to your app.

Third-party components

These are featured components created by our lovely community. For more examples and inspiration, check out our Components Gallery and Streamlit Extras!

Add tags to your Streamlit apps. Created by @gagan3012.

Apply text mining on a dataframe. Created by @JohnSnowLabs.

A library with useful Streamlit extras. Created by @arnaudmiribel.

Display annotated text in Streamlit apps. Created by @tvst.

Provides a sketching canvas using Fabric.js. Created by @andfanilo.

Add tags to your Streamlit apps. Created by @gagan3012.

Apply text mining on a dataframe. Created by @JohnSnowLabs.

A library with useful Streamlit extras. Created by @arnaudmiribel.

Display annotated text in Streamlit apps. Created by @tvst.

Provides a sketching canvas using Fabric.js. Created by @andfanilo.

Add tags to your Streamlit apps. Created by @gagan3012.

Apply text mining on a dataframe. Created by @JohnSnowLabs.

A library with useful Streamlit extras. Created by @arnaudmiribel.

Display a dataframe as an interactive table.

Display a data editor widget.

Configure the display and editing behavior of dataframes and data editors.

Display a static table.

Display a metric in big bold font, with an optional indicator of how the metric changed.

Display object or string as a pretty-printed JSON string.

Third-party components

These are featured components created by o

*[Content truncated]*

---

## st.pills - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.pills

**Contents:**
- st.pills
    - Examples
  - Still have questions?

Display a pills widget.

A pills widget is similar to a st.selectbox or st.multiselect where the options are displayed as pill-buttons instead of a drop-down list.

st.pills(label, options, *, selection_mode="single", default=None, format_func=None, key=None, help=None, on_change=None, args=None, kwargs=None, disabled=False, label_visibility="visible", width="content")

A short label explaining to the user what this widget is for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

For accessibility reasons, you should never set an empty label, but you can hide it with label_visibility if needed. In the future, we may disallow empty labels by raising an exception.

options (Iterable of V)

Labels for the select options in an Iterable. This can be a list, set, or anything supported by st.dataframe. If options is dataframe-like, the first column will be used. Each label will be cast to str internally by default and can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

selection_mode ("single" or "multi")

The selection mode for the widget. If this is "single" (default), only one option can be selected. If this is "multi", multiple options can be selected.

default (Iterable of V, V, or None)

The value of the widget when it first renders. If the selection_mode is multi, this can be a list of values, a single value, or None. If the selection_mode is "single", this can be a single value or None.

format_func (function)

Function to modify the display of the options. It receives the raw option as an argument and should output the label to be shown for that option. This has no impact on the return value of the command. The output can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. Multiple widgets of the same ty

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

options = ["North", "East", "South", "West"]
selection = st.pills("Directions", options, selection_mode="multi")
st.markdown(f"Your selected options: {selection}.")
```

Example 2 (unknown):
```unknown
import streamlit as st

option_map = {
    0: ":material/add:",
    1: ":material/zoom_in:",
    2: ":material/zoom_out:",
    3: ":material/zoom_out_map:",
}
selection = st.pills(
    "Tool",
    options=option_map.keys(),
    format_func=lambda option: option_map[option],
    selection_mode="single",
)
st.write(
    "Your selected option: "
    f"{None if selection is None else option_map[selection]}"
)
```

---

## st.camera_input - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.camera_input

**Contents:**
- st.camera_input
    - Examples
    - Important
- Image processing examples
  - Pillow (PIL) and NumPy
  - OpenCV (cv2)
  - TensorFlow
  - Torchvision
  - PyTorch
  - Still have questions?

Display a widget that returns pictures from the user's webcam.

st.camera_input(label, key=None, help=None, on_change=None, args=None, kwargs=None, *, disabled=False, label_visibility="visible", width="stretch")

A short label explaining to the user what this widget is used for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

For accessibility reasons, you should never set an empty label, but you can hide it with label_visibility if needed. In the future, we may disallow empty labels by raising an exception.

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

A tooltip that gets displayed next to the widget label. Streamlit only displays the tooltip when label_visibility="visible". If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

An optional callback invoked when this camera_input's value changes.

An optional list or tuple of args to pass to the callback.

An optional dict of kwargs to pass to the callback.

An optional boolean that disables the camera input if set to True. Default is False.

label_visibility ("visible", "hidden", or "collapsed")

The visibility of the label. The default is "visible". If this is "hidden", Streamlit displays an empty spacer instead of the label, which can help keep the widget aligned with other widgets. If this is "collapsed", Streamlit displays no label or spacer.

width ("stretch" or int)

The width of the camera input widget. This can be one of the following:

(None or UploadedFile)

The UploadedFile class is a subclass of BytesIO, and therefore is "file-like". This means you can pass an instance of it anywhere a file is expected.

To read the image file buffer as bytes, you can use getvalue() on the UploadedFile object.

st.camera_input returns an object of the UploadedFile class, which

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

enable = st.checkbox("Enable camera")
picture = st.camera_input("Take a picture", disabled=not enable)

if picture:
    st.image(picture)
```

---

## st.feedback - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.feedback

**Contents:**
- st.feedback
    - Examples
  - Still have questions?

Display a feedback widget.

A feedback widget is an icon-based button group available in three styles, as described in options. It is commonly used in chat and AI apps to allow users to rate responses.

st.feedback(options="thumbs", *, key=None, disabled=False, on_change=None, args=None, kwargs=None, width="content")

options ("thumbs", "faces", or "stars")

The feedback options displayed to the user. options can be one of the following:

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

An optional boolean that disables the feedback widget if set to True. The default is False.

An optional callback invoked when this feedback widget's value changes.

An optional list or tuple of args to pass to the callback.

An optional dict of kwargs to pass to the callback.

width ("content", "stretch", or int)

The width of the feedback widget. This can be one of the following:

An integer indicating the user's selection, where 0 is the lowest feedback. Higher values indicate more positive feedback. If no option was selected, the widget returns None.

Display a feedback widget with stars, and show the selected sentiment:

Display a feedback widget with thumbs, and show the selected sentiment:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

sentiment_mapping = ["one", "two", "three", "four", "five"]
selected = st.feedback("stars")
if selected is not None:
    st.markdown(f"You selected {sentiment_mapping[selected]} star(s).")
```

Example 2 (unknown):
```unknown
import streamlit as st

sentiment_mapping = [":material/thumb_down:", ":material/thumb_up:"]
selected = st.feedback("thumbs")
if selected is not None:
    st.markdown(f"You selected: {sentiment_mapping[selected]}")
```

---

## st.column_config.CheckboxColumn - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.checkboxcolumn

**Contents:**
- st.column_config.CheckboxColumn
    - Examples
  - Still have questions?

Configure a checkbox column in st.dataframe or st.data_editor.

This is the default column type for boolean values. This command needs to be used in the column_config parameter of st.dataframe or st.data_editor. When used with st.data_editor, editing will be enabled with a checkbox widget.

st.column_config.CheckboxColumn(label=None, *, width=None, help=None, disabled=None, required=None, pinned=None, default=None)

The label shown at the top of the column. If this is None (default), the column name is used.

width ("small", "medium", "large", int, or None)

The display width of the column. If this is None (default), the column will be sized to fit the cell contents. Otherwise, this can be one of the following:

If the total width of all columns is less than the width of the dataframe, the remaining space will be distributed evenly among all columns.

A tooltip that gets displayed when hovering over the column label. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

disabled (bool or None)

Whether editing should be disabled for this column. If this is None (default), Streamlit will enable editing wherever possible.

If a column has mixed types, it may become uneditable regardless of disabled.

required (bool or None)

Whether edited cells in the column need to have a value. If this is False (default), the user can submit empty values for this column. If this is True, an edited cell in this column can only be submitted if its value is not None, and a new row will only be submitted after the user fills in this column.

pinned (bool or None)

Whether the column is pinned. A pinned column will stay visible on the left side no matter where the user scrolls. If this is None (default), Streamlit will decide: index columns are pinned, and data columns are not pinned.

default (bool or None)

Specifies the default value in this column when a new row is added by the user. This defaults to None.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "widgets": ["st.selectbox", "st.number_input", "st.text_area", "st.button"],
        "favorite": [True, False, False, True],
    }
)

st.data_editor(
    data_df,
    column_config={
        "favorite": st.column_config.CheckboxColumn(
            "Your favorite?",
            help="Select your **favorite** widgets",
            default=False,
        )
    },
    disabled=["widgets"],
    hide_index=True,
)
```

---

## st.latex - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/text/st.latex

**Contents:**
- st.latex
    - Example
  - Still have questions?

Display mathematical expressions formatted as LaTeX.

Supported LaTeX functions are listed at https://katex.org/docs/supported.html.

st.latex(body, *, help=None, width="stretch")

body (str or SymPy expression)

The string or SymPy expression to display as LaTeX. If str, it's a good idea to use raw Python strings since LaTeX uses backslashes a lot.

A tooltip that gets displayed next to the LaTeX expression. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

width ("stretch", "content", or int)

The width of the LaTeX element. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.latex(r'''
    a + ar + a r^2 + a r^3 + \cdots + a r^{n-1} =
    \sum_{k=0}^{n-1} ar^k =
    a \left(\frac{1-r^{n}}{1-r}\right)
    ''')
```

---

## st.file_uploader - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.file_uploader

**Contents:**
- st.file_uploader
    - Examples
  - Still have questions?

Display a file uploader widget.

By default, uploaded files are limited to 200 MB each. You can configure this using the server.maxUploadSize config option. For more information on how to set config options, see config.toml.

st.file_uploader(label, type=None, accept_multiple_files=False, key=None, help=None, on_change=None, args=None, kwargs=None, *, disabled=False, label_visibility="visible", width="stretch")

A short label explaining to the user what this file uploader is for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

For accessibility reasons, you should never set an empty label, but you can hide it with label_visibility if needed. In the future, we may disallow empty labels by raising an exception.

type (str, list of str, or None)

The allowed file extension(s) for uploaded files. This can be one of the following types:

This is a best-effort check, but doesn't provide a security guarantee against users uploading files of other types or type extensions. The correct handling of uploaded files is part of the app developer's responsibility.

accept_multiple_files (bool or "directory")

Whether to accept more than one file in a submission. This can be one of the following values:

When this is True or "directory", the return value will be a list and a user can additively select files if they click the browse button on the widget multiple times.

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

A tooltip that gets displayed next to the widget label. Streamlit only displays the tooltip when label_visibility="visible". If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

An optional callback invoked when this file_uploader's value changes.

An optional list or tuple of args to pass to the callback.

An optional dict of k

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import streamlit as st
import pandas as pd
from io import StringIO

uploaded_file = st.file_uploader("Choose a file")
if uploaded_file is not None:
    # To read file as bytes:
    bytes_data = uploaded_file.getvalue()
    st.write(bytes_data)

    # To convert to a string based IO:
    stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
    st.write(stringio)

    # To read file as string:
    string_data = stringio.read()
    st.write(string_data)

    # Can be used wherever a "file-like" object is accepted:
    dataframe = pd.read_csv(uploaded_file)
    st.write(dataframe)
```

Example 2 (unknown):
```unknown
import pandas as pd
import streamlit as st

uploaded_files = st.file_uploader(
    "Upload data", accept_multiple_files=True, type="csv"
)
for uploaded_file in uploaded_files:
    df = pd.read_csv(uploaded_file)
    st.write(df)
```

Example 3 (unknown):
```unknown
import streamlit as st

uploaded_files = st.file_uploader(
    "Upload images", accept_multiple_files="directory", type=["jpg", "png"]
)
for uploaded_file in uploaded_files:
    st.image(uploaded_file)
```

---

## streamlit run - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/cli/run

**Contents:**
- $ streamlit run
  - Syntax
  - Arguments
  - Options
  - Script arguments
  - Examples
  - Still have questions?

This command starts your Streamlit app.

<entrypoint file>: The path to your entrypoint file for your Streamlit app. In a multipage app with st.navigation, your entrypoint file acts as a router between your pages. Otherwise, your entrypoint file is your app's homepage.

Configuration options are passed in the form of --<section>.<option>=<value>. For example, if you want to set the primary color of your app to blue, you could use one of the three equivalent options:

For a complete list of configuration options, see config.toml in the API reference. For examples, see below.

If you need to pass arguments directly to your script, you can pass them as positional arguments. If you use sys.argv to read your arguments, sys.arfgv returns a list of all arugments and does not include any configuration options. Python interprets all arguments as strings.

If your app is in your working directory, run it as follows:

If your app is in a subdirectory, run it as follows:

If your app is saved in a public GitHub repo or gist, run it as follows:

If you need to set one or more configuration options, run it as follows:

If you need to pass an argument to your script, run it as follows:

Within your script, the following statement will be true:

Our forums are full of helpful information and Streamlit experts.

---

## st.color_picker - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.color_picker

**Contents:**
- st.color_picker
    - Example
  - Still have questions?

Display a color picker widget.

st.color_picker(label, value=None, key=None, help=None, on_change=None, args=None, kwargs=None, *, disabled=False, label_visibility="visible", width="content")

A short label explaining to the user what this input is for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

For accessibility reasons, you should never set an empty label, but you can hide it with label_visibility if needed. In the future, we may disallow empty labels by raising an exception.

The hex value of this widget when it first renders. If None, defaults to black.

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

A tooltip that gets displayed next to the widget label. Streamlit only displays the tooltip when label_visibility="visible". If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

An optional callback invoked when this color_picker's value changes.

An optional list or tuple of args to pass to the callback.

An optional dict of kwargs to pass to the callback.

An optional boolean that disables the color picker if set to True. The default is False.

label_visibility ("visible", "hidden", or "collapsed")

The visibility of the label. The default is "visible". If this is "hidden", Streamlit displays an empty spacer instead of the label, which can help keep the widget aligned with other widgets. If this is "collapsed", Streamlit displays no label or spacer.

width ("content", "stretch", or int)

The width of the color picker widget. This can be one of the following:

The selected color as a hex string.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

color = st.color_picker("Pick A Color", "#00f900")
st.write("The current color is", color)
```

---

## st.data_editor - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.data_editor

**Contents:**
    - Tip
- st.data_editor
    - Examples
  - Configuring columns
  - Still have questions?

This page only contains information on the st.data_editor API. For an overview of working with dataframes and to learn more about the data editor's capabilities and limitations, read Dataframes.

Display a data editor widget.

The data editor widget allows you to edit dataframes and many other data structures in a table-like UI.

st.data_editor(data, *, width="stretch", height="auto", use_container_width=None, hide_index=None, column_order=None, column_config=None, num_rows="fixed", disabled=False, key=None, on_change=None, args=None, kwargs=None, row_height=None)

data (Anything supported by st.dataframe)

The data to edit in the data editor.

width ("stretch", "content", or int)

The width of the data editor. This can be one of the following:

height (int or "auto")

The height of the data editor. This can be one of the following:

Vertical scrolling within the data editor is enabled when the height does not accommodate all rows.

use_container_width (bool)

use_container_width is deprecated and will be removed in a future release. For use_container_width=True, use width="stretch".

Whether to override width with the width of the parent container. If this is True (default), Streamlit sets the width of the data editor to match the width of the parent container. If this is False, Streamlit sets the data editor's width according to width.

hide_index (bool or None)

Whether to hide the index column(s). If hide_index is None (default), the visibility of index columns is automatically determined based on the data.

column_order (Iterable[str] or None)

The ordered list of columns to display. If this is None (default), Streamlit displays all columns in the order inherited from the underlying data structure. If this is a list, the indicated columns will display in the order they appear within the list. Columns may be omitted or repeated within the list.

For example, column_order=("col2", "col1") will display "col2" first, followed by "col1", and will hide all other non-index columns.

column_order does not accept positional column indices and can't move the index column(s).

column_config (dict or None)

Configuration to customize how columns are displayed. If this is None (default), columns are styled based on the underlying data type of each column.

Column configuration can modify column names, visibility, type, width, format, editing properties like min/max, and more. If this is a dictionary, the keys are column names (strings) and/or positional column ind

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import pandas as pd
import streamlit as st

df = pd.DataFrame(
    [
        {"command": "st.selectbox", "rating": 4, "is_widget": True},
        {"command": "st.balloons", "rating": 5, "is_widget": False},
        {"command": "st.time_input", "rating": 3, "is_widget": True},
    ]
)
edited_df = st.data_editor(df)

favorite_command = edited_df.loc[edited_df["rating"].idxmax()]["command"]
st.markdown(f"Your favorite command is **{favorite_command}** 🎈")
```

Example 2 (unknown):
```unknown
import streamlit as st
import pandas as pd

df = pd.DataFrame(
    [
        {"command": "st.selectbox", "rating": 4, "is_widget": True},
        {"command": "st.balloons", "rating": 5, "is_widget": False},
        {"command": "st.time_input", "rating": 3, "is_widget": True},
    ]
)
edited_df = st.data_editor(df, num_rows="dynamic")

favorite_command = edited_df.loc[edited_df["rating"].idxmax()]["command"]
st.markdown(f"Your favorite command is **{favorite_command}** 🎈")
```

Example 3 (unknown):
```unknown
import pandas as pd
import streamlit as st

df = pd.DataFrame(
    [
        {"command": "st.selectbox", "rating": 4, "is_widget": True},
        {"command": "st.balloons", "rating": 5, "is_widget": False},
        {"command": "st.time_input", "rating": 3, "is_widget": True},
    ]
)
edited_df = st.data_editor(
    df,
    column_config={
        "command": "Streamlit Command",
        "rating": st.column_config.NumberColumn(
            "Your rating",
            help="How much do you like this command (1-5)?",
            min_value=1,
            max_value=5,
            step=1,
            
...
```

---

## st.metric - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.metric

**Contents:**
- st.metric
    - Examples
  - Still have questions?

Display a metric in big bold font, with an optional indicator of how the metric changed.

Tip: If you want to display a large number, it may be a good idea to shorten it using packages like millify or numerize. E.g. 1234 can be displayed as 1.2k using st.metric("Short number", millify(1234)).

st.metric(label, value, delta=None, delta_color="normal", *, help=None, label_visibility="visible", border=False, width="stretch", height="content", chart_data=None, chart_type="line")

The header or title for the metric. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

value (int, float, decimal.Decimal, str, or None)

Value of the metric. None is rendered as a long dash.

delta (int, float, decimal.Decimal, str, or None)

Indicator of how the metric changed, rendered with an arrow below the metric. If delta is negative (int/float) or starts with a minus sign (str), the arrow points down and the text is red; else the arrow points up and the text is green. If None (default), no delta indicator is shown.

delta_color ("normal", "inverse", or "off")

If "normal" (default), the delta indicator is shown as described above. If "inverse", it is red when positive and green when negative. This is useful when a negative change is considered good, e.g. if cost decreased. If "off", delta is shown in gray regardless of its value.

A tooltip that gets displayed next to the metric label. Streamlit only displays the tooltip when label_visibility="visible". If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

label_visibility ("visible", "hidden", or "collapsed")

The visibility of the label. The default is "visible". If this is "hidden", Streamlit displays an empty spacer instead of the label, which can help keep the widget aligned with other widgets. If this is "collapsed", Streamlit displays no label or spacer.

Whether to show a border around the metric container. If this is False (defaul

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.metric(label="Temperature", value="70 °F", delta="1.2 °F")
```

Example 2 (unknown):
```unknown
import streamlit as st

col1, col2, col3 = st.columns(3)
col1.metric("Temperature", "70 °F", "1.2 °F")
col2.metric("Wind", "9 mph", "-8%")
col3.metric("Humidity", "86%", "4%")
```

Example 3 (unknown):
```unknown
import streamlit as st

st.metric(label="Gas price", value=4, delta=-0.5, delta_color="inverse")

st.metric(
    label="Active developers",
    value=123,
    delta=123,
    delta_color="off",
)
```

Example 4 (unknown):
```unknown
import streamlit as st

a, b = st.columns(2)
c, d = st.columns(2)

a.metric("Temperature", "30°F", "-9°F", border=True)
b.metric("Wind", "4 mph", "2 mph", border=True)

c.metric("Humidity", "77%", "5%", border=True)
d.metric("Pressure", "30.34 inHg", "-2 inHg", border=True)
```

---

## st.image - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/media/st.image

**Contents:**
- st.image
    - Example
  - Still have questions?

Display an image or list of images.

st.image(image, caption=None, width="content", use_column_width=None, clamp=False, channels="RGB", output_format="auto", *, use_container_width=None)

image (numpy.ndarray, BytesIO, str, Path, or list of these)

The image to display. This can be one of the following:

caption (str or list of str)

Image caption(s). If this is None (default), no caption is displayed. If image is a list of multiple images, caption must be a list of captions (one caption for each image) or None.

Captions can optionally contain GitHub-flavored Markdown. Syntax information can be found at: https://github.github.com/gfm.

See the body parameter of st.markdown for additional, supported Markdown directives.

width ("content", "stretch", or int)

The width of the image element. This can be one of the following:

When using an SVG image without a default width, use "stretch" or an integer.

use_column_width ("auto", "always", "never", or bool)

use_column_width is deprecated and will be removed in a future release. Please use the width parameter instead.

If "auto", set the image's width to its natural size, but do not exceed the width of the column. If "always" or True, set the image's width to the column width. If "never" or False, set the image's width to its natural size. Note: if set, use_column_width takes precedence over the width parameter.

Whether to clamp image pixel values to a valid range (0-255 per channel). This is only used for byte array images; the parameter is ignored for image URLs and files. If this is False (default) and an image has an out-of-range value, a RuntimeError will be raised.

channels ("RGB" or "BGR")

The color format when image is an nd.array. This is ignored for other image types. If this is "RGB" (default), image[:, :, 0] is the red channel, image[:, :, 1] is the green channel, and image[:, :, 2] is the blue channel. For images coming from libraries like OpenCV, you should set this to "BGR" instead.

output_format ("JPEG", "PNG", or "auto")

The output format to use when transferring the image data. If this is "auto" (default), Streamlit identifies the compression type based on the type and format of the image. Photos should use the "JPEG" format for lossy compression while diagrams should use the "PNG" format for lossless compression.

use_container_width (bool)

use_container_width is deprecated and will be removed in a future release. For use_container_width=True, use width="stretch". For use_container_wi

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st
st.image("sunrise.jpg", caption="Sunrise by the mountains")
```

---

## st.tabs - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/layout/st.tabs?utm_source=streamlit

**Contents:**
- st.tabs
    - Examples
  - Still have questions?

Insert containers separated into tabs.

Inserts a number of multi-element containers as tabs. Tabs are a navigational element that allows users to easily move between groups of related content.

To add elements to the returned containers, you can use the with notation (preferred) or just call methods directly on the returned object. See the examples below.

All content within every tab is computed and sent to the frontend, regardless of which tab is selected. Tabs do not currently support conditional rendering. If you have a slow-loading tab, consider using a widget like st.segmented_control to conditionally render content instead.

st.tabs(tabs, *, width="stretch", default=None)

Creates a tab for each string in the list. The first tab is selected by default. The string is used as the name of the tab and can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

width ("stretch" or int)

The width of the tab container. This can be one of the following:

default (str or None)

The default tab to select. If this is None (default), the first tab is selected. If this is a string, it must be one of the tab labels. If two tabs have the same label as default, the first one is selected.

A list of container objects.

Example 1: Use context management

You can use with notation to insert any element into a tab:

Example 2: Call methods directly

You can call methods directly on the returned objects:

Example 3: Set the default tab and style the tab labels

Use the default parameter to set the default tab. You can also use Markdown in the tab labels.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

tab1, tab2, tab3 = st.tabs(["Cat", "Dog", "Owl"])

with tab1:
    st.header("A cat")
    st.image("https://static.streamlit.io/examples/cat.jpg", width=200)
with tab2:
    st.header("A dog")
    st.image("https://static.streamlit.io/examples/dog.jpg", width=200)
with tab3:
    st.header("An owl")
    st.image("https://static.streamlit.io/examples/owl.jpg", width=200)
```

Example 2 (python):
```python
import streamlit as st
from numpy.random import default_rng as rng

df = rng(0).standard_normal((10, 1))

tab1, tab2 = st.tabs(["📈 Chart", "🗃 Data"])

tab1.subheader("A tab with a chart")
tab1.line_chart(df)

tab2.subheader("A tab with the data")
tab2.write(df)
```

Example 3 (unknown):
```unknown
import streamlit as st

tab1, tab2, tab3 = st.tabs(
    [":cat: Cat", ":dog: Dog", ":rainbow[Owl]"], default=":rainbow[Owl]"
)

with tab1:
    st.header("A cat")
    st.image("https://static.streamlit.io/examples/cat.jpg", width=200)
with tab2:
    st.header("A dog")
    st.image("https://static.streamlit.io/examples/dog.jpg", width=200)
with tab3:
    st.header("An owl")
    st.image("https://static.streamlit.io/examples/owl.jpg", width=200)
```

---

## streamlit cache - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/cli/cache

**Contents:**
- $ streamlit cache clear
  - Syntax
  - Still have questions?

Clear persisted files from the on-disk Streamlit cache, if present.

Our forums are full of helpful information and Streamlit experts.

---

## st.rerun - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/execution-flow/st.rerun

**Contents:**
- st.rerun
  - Caveats for st.rerun
  - A simple example in three variations
        - Using st.rerun to update an earlier header
        - Using a callback to update an earlier header
        - Using containers to update an earlier header
  - Still have questions?

Rerun the script immediately.

When st.rerun() is called, Streamlit halts the current script run and executes no further statements. Streamlit immediately queues the script to rerun.

When using st.rerun in a fragment, you can scope the rerun to the fragment. However, if a fragment is running as part of a full-app rerun, a fragment-scoped rerun is not allowed.

st.rerun(*, scope="app")

scope ("app" or "fragment")

Specifies what part of the app should rerun. If scope is "app" (default), the full app reruns. If scope is "fragment", Streamlit only reruns the fragment from which this command is called.

Setting scope="fragment" is only valid inside a fragment during a fragment rerun. If st.rerun(scope="fragment") is called during a full-app rerun or outside of a fragment, Streamlit will raise a StreamlitAPIException.

st.rerun is one of the tools to control the logic of your app. While it is great for prototyping, there can be adverse side effects:

In many cases where st.rerun works, callbacks may be a cleaner alternative. Containers may also be helpful.

Our forums are full of helpful information and Streamlit experts.

---

## st.code - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/text/st.code

**Contents:**
- st.code
    - Examples
  - Still have questions?

Display a code block with optional syntax highlighting.

st.code(body, language="python", *, line_numbers=False, wrap_lines=False, height="content", width="stretch")

The string to display as code or monospace text.

language (str or None)

The language that the code is written in, for syntax highlighting. This defaults to "python". If this is None, the code will be plain, monospace text.

For a list of available language values, see react-syntax-highlighter on GitHub.

An optional boolean indicating whether to show line numbers to the left of the code block. This defaults to False.

An optional boolean indicating whether to wrap lines. This defaults to False.

height ("content", "stretch", or int)

The height of the code block element. This can be one of the following:

Use scrolling containers sparingly. If you use scrolling containers, avoid heights that exceed 500 pixels. Otherwise, the scroll surface of the container might cover the majority of the screen on mobile devices, which makes it hard to scroll the rest of the app.

width ("stretch", "content", or int)

The width of the code block element. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (python):
```python
import streamlit as st

code = '''def hello():
    print("Hello, Streamlit!")'''
st.code(code, language="python")
```

Example 2 (unknown):
```unknown
import streamlit as st
code = '''Is it a crown or boat?
                        ii
                      iiiiii
WWw                 .iiiiiiii.                ...:
 WWWWWWw          .iiiiiiiiiiii.         ........
  WWWWWWWWWWw    iiiiiiiiiiiiiiii    ...........
   WWWWWWWWWWWWWWwiiiiiiiiiiiiiiiii............
    WWWWWWWWWWWWWWWWWWwiiiiiiiiiiiiii.........
     WWWWWWWWWWWWWWWWWWWWWWwiiiiiiiiii.......
      WWWWWWWWWWWWWWWWWWWWWWWWWWwiiiiiii....
       WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWwiiii.
          -MMMWWWWWWWWWWWWWWWWWWWWWWMMM-
'''
st.code(code, language=None)
```

---

## st.experimental_rerun - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/execution-flow/st.experimental_rerun

**Contents:**
- st.experimental_rerun
    - Warning
  - Still have questions?

This method did not exist in version 1.50.0 of Streamlit.

Our forums are full of helpful information and Streamlit experts.

---

## st.container - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/layout/st.container

**Contents:**
- st.container
    - Examples
  - Still have questions?

Insert a multi-element container.

Inserts an invisible container into your app that can be used to hold multiple elements. This allows you to, for example, insert multiple elements into your app out of order.

To add elements to the returned container, you can use the with notation (preferred) or just call commands directly on the returned object. See examples below.

st.container(*, border=None, key=None, width="stretch", height="content", horizontal=False, horizontal_alignment="left", vertical_alignment="top", gap="small")

border (bool or None)

Whether to show a border around the container. If None (default), a border is shown if the container is set to a fixed height and not shown otherwise.

An optional string to give this container a stable identity.

Additionally, if key is provided, it will be used as CSS class name prefixed with st-key-.

width ("stretch" or int)

The width of the container. This can be one of the following:

height ("content", "stretch", or int)

The height of the container. This can be one of the following:

Use scrolling containers sparingly. If you use scrolling containers, avoid heights that exceed 500 pixels. Otherwise, the scroll surface of the container might cover the majority of the screen on mobile devices, which makes it hard to scroll the rest of the app.

Whether to use horizontal flexbox layout. If this is False (default), the container's elements are laid out vertically. If this is True, the container's elements are laid out horizontally and will overflow to the next line if they don't fit within the container's width.

horizontal_alignment ("left", "center", "right", or "distribute")

The horizontal alignment of the elements inside the container. This can be one of the following:

"left" (default): Elements are aligned to the left side of the container.

"center": Elements are horizontally centered inside the container.

"right": Elements are aligned to the right side of the container.

"distribute": Elements are distributed evenly in the container. This increases the horizontal gap between elements to fill the width of the container. A standalone element is aligned to the left.

When horizontal is False, "distribute" aligns the elements the same as "left".

vertical_alignment ("top", "center", "bottom", or "distribute")

The vertical alignment of the elements inside the container. This can be one of the following:

"top" (default): Elements are aligned to the top of the container.

"center": Elements are vertic

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

with st.container():
    st.write("This is inside the container")

    # You can call any Streamlit command, including custom components:
    st.bar_chart(np.random.randn(50, 3))

st.write("This is outside the container")
```

Example 2 (unknown):
```unknown
import streamlit as st

container = st.container(border=True)
container.write("This is inside the container")
st.write("This is outside the container")

container.write("This is inside too")
```

Example 3 (unknown):
```unknown
import streamlit as st

row1 = st.columns(3)
row2 = st.columns(3)

for col in row1 + row2:
    tile = col.container(height=120)
    tile.title(":balloon:")
```

Example 4 (unknown):
```unknown
import streamlit as st

long_text = "Lorem ipsum. " * 1000

with st.container(height=300):
    st.markdown(long_text)
```

---

## st.column_config.JsonColumn - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.jsoncolumn

**Contents:**
- st.column_config.JsonColumn
    - Examples
  - Still have questions?

Configure a JSON column in st.dataframe or st.data_editor.

Cells need to contain JSON strings or JSON-compatible objects. JSON columns are not editable at the moment. This command needs to be used in the column_config parameter of st.dataframe or st.data_editor.

st.column_config.JsonColumn(label=None, *, width=None, help=None, pinned=None)

The label shown at the top of the column. If this is None (default), the column name is used.

width ("small", "medium", "large", int, or None)

The display width of the column. If this is None (default), the column will be sized to fit the cell contents. Otherwise, this can be one of the following:

If the total width of all columns is less than the width of the dataframe, the remaining space will be distributed evenly among all columns.

A tooltip that gets displayed when hovering over the column label. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

pinned (bool or None)

Whether the column is pinned. A pinned column will stay visible on the left side no matter where the user scrolls. If this is None (default), Streamlit will decide: index columns are pinned, and data columns are not pinned.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "json": [
            {"foo": "bar", "bar": "baz"},
            {"foo": "baz", "bar": "qux"},
            {"foo": "qux", "bar": "foo"},
            None,
        ],
    }
)

st.dataframe(
    data_df,
    column_config={
        "json": st.column_config.JsonColumn(
            "JSON Data",
            help="JSON strings or objects",
            width="large",
        ),
    },
    hide_index=True,
)
```

---

## streamlit config show - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/cli/config

**Contents:**
- $ streamlit config show
  - Syntax
  - Still have questions?

Print all the available configuration options, including their descriptions, default values, and current values. For more information about configuration options, see config.toml.

Our forums are full of helpful information and Streamlit experts.

---

## st.select_slider - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.select_slider

**Contents:**
- st.select_slider
    - Examples
  - Featured videos
  - Still have questions?

Display a slider widget to select items from a list.

This also allows you to render a range slider by passing a two-element tuple or list as the value.

The difference between st.select_slider and st.slider is that select_slider accepts any datatype and takes an iterable set of options, while st.slider only accepts numerical or date/time data and takes a range as input.

st.select_slider(label, options=(), value=None, format_func=special_internal_function, key=None, help=None, on_change=None, args=None, kwargs=None, *, disabled=False, label_visibility="visible", width="stretch")

A short label explaining to the user what this slider is for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

For accessibility reasons, you should never set an empty label, but you can hide it with label_visibility if needed. In the future, we may disallow empty labels by raising an exception.

Labels for the select options in an Iterable. This can be a list, set, or anything supported by st.dataframe. If options is dataframe-like, the first column will be used. Each label will be cast to str internally by default.

value (a supported type or a tuple/list of supported types or None)

The value of the slider when it first renders. If a tuple/list of two values is passed here, then a range slider with those lower and upper bounds is rendered. For example, if set to (1, 10) the slider will have a selectable range between 1 and 10. Defaults to first option.

format_func (function)

Function to modify the display of the labels from the options. argument. It receives the option as an argument and its output will be cast to str.

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

A tooltip that gets displayed next to the widget label. Streamlit only displays the tooltip when label_visibility="visible". If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-fl

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

color = st.select_slider(
    "Select a color of the rainbow",
    options=[
        "red",
        "orange",
        "yellow",
        "green",
        "blue",
        "indigo",
        "violet",
    ],
)
st.write("My favorite color is", color)
```

Example 2 (unknown):
```unknown
import streamlit as st

start_color, end_color = st.select_slider(
    "Select a range of color wavelength",
    options=[
        "red",
        "orange",
        "yellow",
        "green",
        "blue",
        "indigo",
        "violet",
    ],
    value=("red", "blue"),
)
st.write("You selected wavelengths between", start_color, "and", end_color)
```

---

## st.info - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/status/st.info

**Contents:**
- st.info
    - Example
  - Still have questions?

Display an informational message.

st.info(body, *, icon=None, width="stretch")

The text to display as GitHub-flavored Markdown. Syntax information can be found at: https://github.github.com/gfm.

See the body parameter of st.markdown for additional, supported Markdown directives.

An optional emoji or icon to display next to the alert. If icon is None (default), no icon is displayed. If icon is a string, the following options are valid:

A single-character emoji. For example, you can set icon="🚨" or icon="🔥". Emoji short codes are not supported.

An icon from the Material Symbols library (rounded style) in the format ":material/icon_name:" where "icon_name" is the name of the icon in snake case.

For example, icon=":material/thumb_up:" will display the Thumb Up icon. Find additional icons in the Material Symbols font library.

width ("stretch" or int)

The width of the info element. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.info('This is a purely informational message', icon="ℹ️")
```

---

## st.help - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/utilities/st.help

**Contents:**
- st.help
    - Example
  - Still have questions?

Display help and other information for a given object.

Depending on the type of object that is passed in, this displays the object's name, type, value, signature, docstring, and member variables, methods — as well as the values/docstring of members and methods.

st.help(obj=, *, width="stretch")

The object whose information should be displayed. If left unspecified, this call will display help for Streamlit itself.

width ("stretch" or int)

The width of the help element. This can be one of the following:

Don't remember how to initialize a dataframe? Try this:

Want to quickly check what data type is output by a certain function? Try:

Want to quickly inspect an object? No sweat:

And if you're using Magic, you can get help for functions, classes, and modules without even typing st.help:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st
import pandas

st.help(pandas.DataFrame)
```

Example 2 (unknown):
```unknown
import streamlit as st

x = my_poorly_documented_function()
st.help(x)
```

Example 3 (python):
```python
class Dog:
  '''A typical dog.'''

  def __init__(self, breed, color):
    self.breed = breed
    self.color = color

  def bark(self):
    return 'Woof!'


fido = Dog("poodle", "white")

st.help(fido)
```

Example 4 (unknown):
```unknown
import streamlit as st
import pandas

# Get help for Pandas read_csv:
pandas.read_csv

# Get help for Streamlit itself:
st
```

---

## st.html - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/utilities/st.html

**Contents:**
- st.html
    - Example
  - Still have questions?

Insert HTML into your app.

Adding custom HTML to your app impacts safety, styling, and maintainability. We sanitize HTML with DOMPurify, but inserting HTML remains a developer risk. Passing untrusted code to st.html or dynamically loading external code can increase the risk of vulnerabilities in your app.

st.html content is not iframed. Executing JavaScript is not supported at this time.

st.html(body, *, width="stretch")

The HTML code to insert. This can be one of the following:

If the resulting HTML content is empty, Streamlit will raise an error.

If body is a path to a CSS file, Streamlit will wrap the CSS content in <style> tags automatically. When the resulting HTML content only contains style tags, Streamlit will send the content to the event container instead of the main container to avoid taking up space in the app.

width ("stretch", "content", or int)

The width of the HTML element. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.html(
    "<p><span style='text-decoration: line-through double red;'>Oops</span>!</p>"
)
```

---

## 2025 release notes - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/quick-reference/release-notes/2025

**Contents:**
- 2025 release notes
- Version 1.50.0
- Version 1.49.0
- Version 1.48.0
- Version 1.47.0
- Version 1.46.0
- Version 1.45.0
- Version 1.44.0
- Version 1.43.0
- Version 1.42.0

This page contains release notes for Streamlit versions released in 2025. For the latest version of Streamlit, see Release notes.

Release date: September 23, 2025

Release date: August 26, 2025

Release date: August 5, 2025

Release date: July 16, 2025

Release date: June 18, 2025

Release date: April 29, 2025

Release date: March 25, 2025

Release date: March 4, 2025

Release date: February 4, 2025

Our forums are full of helpful information and Streamlit experts.

---

## st.progress - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/status/st.progress

**Contents:**
- st.progress
    - Example
  - Still have questions?

Display a progress bar.

st.progress(value, text=None, width="stretch")

0 <= value <= 100 for int

0.0 <= value <= 1.0 for float

A message to display above the progress bar. The text can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

width ("stretch" or int)

The width of the progress element. This can be one of the following:

Here is an example of a progress bar increasing over time and disappearing when it reaches completion:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st
import time

progress_text = "Operation in progress. Please wait."
my_bar = st.progress(0, text=progress_text)

for percent_complete in range(100):
    time.sleep(0.01)
    my_bar.progress(percent_complete + 1, text=progress_text)
time.sleep(1)
my_bar.empty()

st.button("Rerun")
```

---

## st.altair_chart - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/charts/st.altair_chart

**Contents:**
- st.altair_chart
    - Example
- Chart selections
  - VegaLiteState
    - Examples
- element.add_rows
    - Example
- Theming
  - Still have questions?

Display a chart using the Vega-Altair library.

Vega-Altair is a declarative statistical visualization library for Python, based on Vega and Vega-Lite.

st.altair_chart(altair_chart, *, use_container_width=None, theme="streamlit", key=None, on_select="ignore", selection_mode=None)

altair_chart (altair.Chart)

The Altair chart object to display. See https://altair-viz.github.io/gallery/ for examples of graph descriptions.

use_container_width (bool or None)

Whether to override the chart's native width with the width of the parent container. This can be one of the following:

theme ("streamlit" or None)

The theme of the chart. If theme is "streamlit" (default), Streamlit uses its own design default. If theme is None, Streamlit falls back to the default behavior of the library.

The "streamlit" theme can be partially customized through the configuration options theme.chartCategoricalColors and theme.chartSequentialColors. Font configuration options are also applied.

An optional string to use for giving this element a stable identity. If key is None (default), this element's identity will be determined based on the values of the other parameters.

Additionally, if selections are activated and key is provided, Streamlit will register the key in Session State to store the selection state. The selection state is read-only.

on_select ("ignore", "rerun", or callable)

How the figure should respond to user selection events. This controls whether or not the figure behaves like an input widget. on_select can be one of the following:

To use selection events, the object passed to altair_chart must include selection parameters. To learn about defining interactions in Altair and how to declare selection-type parameters, see Interactive Charts in Altair's documentation.

selection_mode (str or Iterable of str)

The selection parameters Streamlit should use. If selection_mode is None (default), Streamlit will use all selection parameters defined in the chart's Altair spec.

When Streamlit uses a selection parameter, selections from that parameter will trigger a rerun and be included in the selection state. When Streamlit does not use a selection parameter, selections from that parameter will not trigger a rerun and not be included in the selection state.

Selection parameters are identified by their name property.

If on_select is "ignore" (default), this command returns an internal placeholder for the chart element that can be used with the .add_rows() method. Otherw

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import altair as alt
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(rng(0).standard_normal((60, 3)), columns=["a", "b", "c"])

chart = (
    alt.Chart(df)
    .mark_circle()
    .encode(x="a", y="b", size="c", color="c", tooltip=["a", "b", "c"])
)

st.altair_chart(chart)
```

Example 2 (python):
```python
import altair as alt
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(rng(0).standard_normal((20, 3)), columns=["a", "b", "c"])

point_selector = alt.selection_point("point_selection")
interval_selector = alt.selection_interval("interval_selection")
chart = (
    alt.Chart(df)
    .mark_circle()
    .encode(
        x="a",
        y="b",
        size="c",
        color="c",
        tooltip=["a", "b", "c"],
        fillOpacity=alt.condition(point_selector, alt.value(1), alt.value(0.3)),
    )
    .add_params(point_selector, interval_selec
...
```

Example 3 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(rng(0).standard_normal((20, 3)), columns=["a", "b", "c"])

spec = {
    "mark": {"type": "circle", "tooltip": True},
    "params": [
        {"name": "interval_selection", "select": "interval"},
        {"name": "point_selection", "select": "point"},
    ],
    "encoding": {
        "x": {"field": "a", "type": "quantitative"},
        "y": {"field": "b", "type": "quantitative"},
        "size": {"field": "c", "type": "quantitative"},
        "color": {"field": "c", "type": "quantitative"},
...
```

Example 4 (python):
```python
import time
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df1 = pd.DataFrame(
    rng(0).standard_normal(size=(50, 20)), columns=("col %d" % i for i in range(20))
)

df2 = pd.DataFrame(
    rng(1).standard_normal(size=(50, 20)), columns=("col %d" % i for i in range(20))
)

my_table = st.table(df1)
time.sleep(1)
my_table.add_rows(df2)
```

---

## st.download_button - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.download_button

**Contents:**
- st.download_button
    - Examples
  - Still have questions?

Display a download button widget.

This is useful when you would like to provide a way for your users to download a file directly from your app.

Note that the data to be downloaded is stored in-memory while the user is connected, so it's a good idea to keep file sizes under a couple hundred megabytes to conserve memory.

If you want to prevent your app from rerunning when a user clicks the download button, wrap the download button in a fragment.

st.download_button(label, data, file_name=None, mime=None, key=None, help=None, on_click="rerun", args=None, kwargs=None, *, type="secondary", icon=None, disabled=False, use_container_width=None, width="content")

A short label explaining to the user what this button is for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

data (str, bytes, or file)

The contents of the file to be downloaded.

To prevent unncecessary recomputation, use caching when converting your data for download. For more information, see the Example 1 below.

An optional string to use as the name of the file to be downloaded, such as "my_file.csv". If not specified, the name will be automatically generated.

The MIME type of the data. If this is None (default), Streamlit sets the MIME type depending on the value of data as follows:

For more information about MIME types, see https://www.iana.org/assignments/media-types/media-types.xhtml.

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

A tooltip that gets displayed when the button is hovered over. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

on_click (callable, "rerun", "ignore", or None)

How the button should respond to user interaction. This controls whether or not the button triggers a rerun and if a callback function is called. This can be one of th

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import streamlit as st
import pandas as pd
import numpy as np

@st.cache_data
def get_data():
    df = pd.DataFrame(
        np.random.randn(50, 20), columns=("col %d" % i for i in range(20))
    )
    return df

@st.cache_data
def convert_for_download(df):
    return df.to_csv().encode("utf-8")

df = get_data()
csv = convert_for_download(df)

st.download_button(
    label="Download CSV",
    data=csv,
    file_name="data.csv",
    mime="text/csv",
    icon=":material/download:",
)
```

Example 2 (unknown):
```unknown
import streamlit as st

message = st.text_area("Message", value="Lorem ipsum.\nStreamlit is cool.")

if st.button("Prepare download"):
    st.download_button(
        label="Download text",
        data=message,
        file_name="message.txt",
        on_click="ignore",
        type="primary",
        icon=":material/download:",
    )
```

Example 3 (unknown):
```unknown
import streamlit as st

with open("flower.png", "rb") as file:
    st.download_button(
        label="Download image",
        data=file,
        file_name="flower.png",
        mime="image/png",
    )
```

---

## streamlit version - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/cli/version

**Contents:**
- $ streamlit version
  - Syntax
  - Still have questions?

Print Streamlit's version number. This command is equivalent to executing streamlit --version.

Our forums are full of helpful information and Streamlit experts.

---

## st.markdown - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/text/st.markdown

**Contents:**
- st.markdown
    - Examples
  - Still have questions?

Display string formatted as Markdown.

st.markdown(body, unsafe_allow_html=False, *, help=None, width="stretch")

The text to display as GitHub-flavored Markdown. Syntax information can be found at: https://github.github.com/gfm. If anything other than a string is passed, it will be converted into a string behind the scenes using str(body).

unsafe_allow_html (bool)

Whether to render HTML within body. If this is False (default), any HTML tags found in body will be escaped and therefore treated as raw text. If this is True, any HTML expressions within body will be rendered.

Adding custom HTML to your app impacts safety, styling, and maintainability.

If you only want to insert HTML or CSS without Markdown text, we recommend using st.html instead.

A tooltip that gets displayed next to the Markdown. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

width ("stretch", "content", or int)

The width of the Markdown element. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.markdown("*Streamlit* is **really** ***cool***.")
st.markdown('''
    :red[Streamlit] :orange[can] :green[write] :blue[text] :violet[in]
    :gray[pretty] :rainbow[colors] and :blue-background[highlight] text.''')
st.markdown("Here's a bouquet &mdash;\
            :tulip::cherry_blossom::rose::hibiscus::sunflower::blossom:")

multi = '''If you end a line with two spaces,
a soft return is used for the next line.

Two (or more) newline characters in a row will result in a hard return.
'''
st.markdown(multi)
```

---

## st.area_chart - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/charts/st.area_chart

**Contents:**
- st.area_chart
    - Examples
- element.add_rows
    - Example
  - Still have questions?

Display an area chart.

This is syntax-sugar around st.altair_chart. The main difference is this command uses the data's own column and indices to figure out the chart's Altair spec. As a result this is easier to use for many "just plot this" scenarios, while being less customizable.

st.area_chart(data=None, *, x=None, y=None, x_label=None, y_label=None, color=None, stack=None, width=None, height=None, use_container_width=True)

data (Anything supported by st.dataframe)

Column name or key associated to the x-axis data. If x is None (default), Streamlit uses the data index for the x-axis values.

y (str, Sequence of str, or None)

Column name(s) or key(s) associated to the y-axis data. If this is None (default), Streamlit draws the data of all remaining columns as data series. If this is a Sequence of strings, Streamlit draws several series on the same chart by melting your wide-format table into a long-format table behind the scenes.

x_label (str or None)

The label for the x-axis. If this is None (default), Streamlit will use the column name specified in x if available, or else no label will be displayed.

y_label (str or None)

The label for the y-axis. If this is None (default), Streamlit will use the column name(s) specified in y if available, or else no label will be displayed.

color (str, tuple, Sequence of str, Sequence of tuple, or None)

The color to use for different series in this chart.

For an area chart with just 1 series, this can be:

For an area chart with multiple series, where the dataframe is in long format (that is, y is None or just one column), this can be:

None, to use the default colors.

The name of a column in the dataset. Data points will be grouped into series of the same color based on the value of this column. In addition, if the values in this column match one of the color formats above (hex string or color tuple), then that color will be used.

For example: if the dataset has 1000 rows, but this column only contains the values "adult", "child", and "baby", then those 1000 datapoints will be grouped into three series whose colors will be automatically selected from the default palette.

But, if for the same 1000-row dataset, this column contained the values "#ffaa00", "#f0f", "#0000ff", then then those 1000 datapoints would still be grouped into 3 series, but their colors would be "#ffaa00", "#f0f", "#0000ff" this time around.

For an area chart with multiple series, where the dataframe is in wide format (that is, y is 

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(rng(0).standard_normal((20, 3)), columns=["a", "b", "c"])

st.area_chart(df)
```

Example 2 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(
    {
        "col1": list(range(20)) * 3,
        "col2": rng(0).standard_normal(60),
        "col3": ["a"] * 20 + ["b"] * 20 + ["c"] * 20,
    }
)

st.area_chart(df, x="col1", y="col2", color="col3")
```

Example 3 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(
    {
        "col1": list(range(20)),
        "col2": rng(0).standard_normal(20),
        "col3": rng(1).standard_normal(20),
    }
)

st.area_chart(
    df,
    x="col1",
    y=["col2", "col3"],
    color=["#FF000080", "#0000FF80"],
)
```

Example 4 (python):
```python
import streamlit as st
from vega_datasets import data

df = data.unemployment_across_industries()

st.area_chart(df, x="date", y="count", color="series", stack="center")
```

---

## st.button - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.button

**Contents:**
- st.button
    - Examples
  - Advanced functionality
  - Featured videos
  - Still have questions?

Display a button widget.

st.button(label, key=None, help=None, on_click=None, args=None, kwargs=None, *, type="secondary", icon=None, disabled=False, use_container_width=None, width="content")

A short label explaining to the user what this button is for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

A tooltip that gets displayed when the button is hovered over. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

An optional callback invoked when this button is clicked.

An optional list or tuple of args to pass to the callback.

An optional dict of kwargs to pass to the callback.

type ("primary", "secondary", or "tertiary")

An optional string that specifies the button type. This can be one of the following:

An optional emoji or icon to display next to the button label. If icon is None (default), no icon is displayed. If icon is a string, the following options are valid:

A single-character emoji. For example, you can set icon="🚨" or icon="🔥". Emoji short codes are not supported.

An icon from the Material Symbols library (rounded style) in the format ":material/icon_name:" where "icon_name" is the name of the icon in snake case.

For example, icon=":material/thumb_up:" will display the Thumb Up icon. Find additional icons in the Material Symbols font library.

An optional boolean that disables the button if set to True. The default is False.

use_container_width (bool)

use_container_width is deprecated and will be removed in a future release. For use_container_width=True, use width="stretch". For use_container_width=False, use width="content".

Whether to expand the button's width to fill its parent container. If use_container_width is False (default), Streamlit sizes 

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.button("Reset", type="primary")
if st.button("Say hello"):
    st.write("Why hello there")
else:
    st.write("Goodbye")

if st.button("Aloha", type="tertiary"):
    st.write("Ciao")
```

Example 2 (unknown):
```unknown
import streamlit as st

left, middle, right = st.columns(3)
if left.button("Plain button", width="stretch"):
    left.markdown("You clicked the plain button.")
if middle.button("Emoji button", icon="😃", width="stretch"):
    middle.markdown("You clicked the emoji button.")
if right.button("Material button", icon=":material/mood:", width="stretch"):
    right.markdown("You clicked the Material button.")
```

---

## st.testing.v1.AppTest - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest

**Contents:**
- The AppTest class
- st.testing.v1.AppTest
- Initialize a simulated app using AppTest
- AppTest.from_file
- AppTest.from_string
- AppTest.from_function
- Run an AppTest script
- AppTest.run
- AppTest.switch_page
- Get AppTest script elements

A simulated Streamlit app to check the correctness of displayed elements and outputs.

An instance of AppTest simulates a running Streamlit app. This class provides methods to set up, manipulate, and inspect the app contents via API instead of a browser UI. It can be used to write automated tests of an app in various scenarios. These can then be run using a tool like pytest.

AppTest can be initialized by one of three class methods:

Once initialized, Session State and widget values can be updated and the script can be run. Unlike an actual live-running Streamlit app, you need to call AppTest.run() explicitly to re-run the app after changing a widget value. Switching pages also requires an explicit, follow-up call to AppTest.run().

AppTest enables developers to build tests on their app as-is, in the familiar python test format, without major refactoring or abstracting out logic to be tested separately from the UI. Tests can run quickly with very low overhead. A typical pattern is to build a suite of tests for an app that ensure consistent functionality as the app evolves, and run the tests locally and/or in a CI environment like Github Actions.

AppTest only supports testing a single page of an app per instance. For multipage apps, each page will need to be tested separately. AppTest is not yet compatible with multipage apps using st.navigation and st.Page.

st.testing.v1.AppTest(script_path, *, default_timeout, args=None, kwargs=None)

Get elements or widgets of the specified type.

Run the script from the current state.

switch_page(page_path)

Switch to another page of the app.

secrets (dict[str, Any])

Dictionary of secrets to be used the simulated app. Use dict-like syntax to set secret values for the simulated app.

session_state (SafeSessionState)

Session State for the simulated app. SafeSessionState object supports read and write operations as usual for Streamlit apps.

query_params (dict[str, Any])

Dictionary of query parameters to be used by the simluated app. Use dict-like syntax to set query_params values for the simulated app.

Sequence of all st.button and st.form_submit_button widgets.

Sequence of all st.feedback widgets.

Sequence of all st.caption elements.

Sequence of all st.chat_input widgets.

Sequence of all st.chat_message elements.

Sequence of all st.checkbox widgets.

Sequence of all st.code elements.

Sequence of all st.color_picker widgets.

Sequence of all columns within st.columns elements.

Sequence of all st.dataframe e

*[Content truncated]*

---

## st.column_config.MultiselectColumn - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.multiselectcolumn

**Contents:**
- st.column_config.MultiselectColumn
    - Examples
  - Still have questions?

Configure a multiselect column in st.dataframe or st.data_editor.

This command needs to be used in the column_config parameter of st.dataframe or st.data_editor. When used with st.data_editor, users can select options from a dropdown menu. You can configure the column to allow freely typed options, too.

You can also use this column type to display colored labels in a read-only st.dataframe.

Editing for non-string or mixed type lists can cause issues with Arrow serialization. We recommend that you disable editing for these columns or convert all list values to strings.

st.column_config.MultiselectColumn(label=None, *, width=None, help=None, disabled=None, required=None, default=None, options=None, accept_new_options=None, color=None, format_func=None)

The label shown at the top of the column. If None (default), the column name is used.

width ("small", "medium", "large", or None)

The display width of the column. If this is None (default), the column will be sized to fit the cell contents. Otherwise, this can be one of the following:

If the total width of all columns is less than the width of the dataframe, the remaining space will be distributed evenly among all columns.

A tooltip that gets displayed when hovering over the column label. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

disabled (bool or None)

Whether editing should be disabled for this column. Defaults to False.

required (bool or None)

Whether edited cells in the column need to have a value. If True, an edited cell can only be submitted if it has a value other than None. Defaults to False.

default (Iterable of str or None)

Specifies the default value in this column when a new row is added by the user.

options (Iterable of str or None)

The options that can be selected during editing.

accept_new_options (bool or None)

Whether the user can add selections that aren't included in options. If this is False (default), the user can only select from the items in options. If this is True, the user can enter new items that don't exist in options.

When a user enters and selects a new item, it is included in the returned cell list value as a string. The new item is not added to the options drop-down menu.

color (str, Iterable of str, or None)

The color to use for different options. This can be:

None (default): The options are displayed wi

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "category": [
            ["exploration", "visualization"],
            ["llm", "visualization"],
            ["exploration"],
        ],
    }
)

st.data_editor(
    data_df,
    column_config={
        "category": st.column_config.MultiselectColumn(
            "App Categories",
            help="The categories of the app",
            options=[
                "exploration",
                "visualization",
                "llm",
            ],
            color=["#ffa421", "#803df5", "#00c0f2"],
            f
...
```

Example 2 (unknown):
```unknown
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "category": [
            ["exploration", "visualization"],
            ["llm", "visualization"],
            ["exploration"],
        ],
    }
)

st.dataframe(
    data_df,
    column_config={
        "category": st.column_config.MultiselectColumn(
            "App Categories",
            options=["exploration", "visualization", "llm"],
            color="primary",
            format_func=lambda x: x.capitalize(),
        ),
    },
)
```

---

## st.connections.ExperimentalBaseConnection - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/connections/st.connections.experimentalbaseconnection

**Contents:**
    - Important
    - Tip
- st.connections.ExperimentalBaseConnection
    - Deprecation notice
- st.connections.ExperimentalBaseConnection.reset
    - Warning
  - Still have questions?

This is an experimental feature. Experimental features and their APIs may change or be removed at any time. To learn more, click here.

This page only contains information on the st.connections.ExperimentalBaseConnection class. For a deeper dive into creating and managing data connections within Streamlit apps, read Connecting to data.

st.connections.ExperimentalBaseConnection was deprecated in version 1.28.0. Use st.connections.BaseConnection instead.

The abstract base class that all Streamlit Connections must inherit from.

This base class provides connection authors with a standardized way to hook into the st.connection() factory function: connection authors are required to provide an implementation for the abstract method _connect in their subclasses.

Additionally, it also provides a few methods/properties designed to make implementation of connections more convenient. See the docstrings for each of the methods of this class for more information

While providing an implementation of _connect is technically all that's required to define a valid connection, connections should also provide the user with context-specific ways of interacting with the underlying connection object. For example, the first-party SQLConnection provides a query() method for reads and a session property for more complex operations.

st.connections.ExperimentalBaseConnection(connection_name, **kwargs)

Reset this connection so that it gets reinitialized the next time it's used.

This method did not exist in version 1.50.0 of Streamlit.

Our forums are full of helpful information and Streamlit experts.

---

## st.chat_input - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/chat/st.chat_input

**Contents:**
    - Tip
- st.chat_input
    - Examples
  - Still have questions?

Read the Build a basic LLM chat app tutorial to learn how to use st.chat_message and st.chat_input to build chat-based apps.

Display a chat input widget.

st.chat_input(placeholder="Your message", *, key=None, max_chars=None, accept_file=False, file_type=None, disabled=False, on_submit=None, args=None, kwargs=None, width="stretch")

A placeholder text shown when the chat input is empty. This defaults to "Your message". For accessibility reasons, you should not use an empty string.

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

max_chars (int or None)

The maximum number of characters that can be entered. If this is None (default), there will be no maximum.

accept_file (bool, "multiple", or "directory")

Whether the chat input should accept files. This can be one of the following values:

By default, uploaded files are limited to 200 MB each. You can configure this using the server.maxUploadSize config option. For more information on how to set config options, see config.toml.

file_type (str, Sequence[str], or None)

The allowed file extension(s) for uploaded files. This can be one of the following types:

This is a best-effort check, but doesn't provide a security guarantee against users uploading files of other types or type extensions. The correct handling of uploaded files is part of the app developer's responsibility.

Whether the chat input should be disabled. This defaults to False.

An optional callback invoked when the chat input's value is submitted.

An optional list or tuple of args to pass to the callback.

An optional dict of kwargs to pass to the callback.

width ("stretch" or int)

The width of the chat input widget. This can be one of the following:

(None, str, or dict-like)

The user's submission. This is one of the following types:

When the widget is configured to accept files and the user submits something in the last rerun, you can access the user's submission with key or attribute notation from the dict-like object. This is shown in Example 3 below.

The text attribute holds a string, which is the user's message. This is an empty string if the user only submitted one or more files.

The files attribute holds a list of UploadedFile objects. The list is empty if the user only submitted a message. Unlike st.file_uploader, this attribute always returns a list, even when the widget is configur

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

prompt = st.chat_input("Say something")
if prompt:
    st.write(f"User has sent the following prompt: {prompt}")
```

Example 2 (unknown):
```unknown
import streamlit as st

with st.sidebar:
    messages = st.container(height=300)
    if prompt := st.chat_input("Say something"):
        messages.chat_message("user").write(prompt)
        messages.chat_message("assistant").write(f"Echo: {prompt}")
```

Example 3 (unknown):
```unknown
import streamlit as st

prompt = st.chat_input(
    "Say something and/or attach an image",
    accept_file=True,
    file_type=["jpg", "jpeg", "png"],
)
if prompt and prompt.text:
    st.markdown(prompt.text)
if prompt and prompt["files"]:
    st.image(prompt["files"][0])
```

Example 4 (unknown):
```unknown
import streamlit as st

if st.button("Set Value"):
    st.session_state.chat_input = "Hello, world!"
st.chat_input(key="chat_input")
st.write("Chat input value:", st.session_state.chat_input)
```

---

## st.write_stream - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/write-magic/st.write_stream

**Contents:**
- st.write_stream
    - Example
    - Tip
  - Still have questions?

Stream a generator, iterable, or stream-like sequence to the app.

st.write_stream iterates through the given sequences and writes all chunks to the app. String chunks will be written using a typewriter effect. Other data types will be written using st.write.

st.write_stream(stream)

stream (Callable, Generator, Iterable, OpenAI Stream, or LangChain Stream)

The generator or iterable to stream.

If you pass an async generator, Streamlit will internally convert it to a sync generator. If the generator depends on a cached object with async references, this can raise an error.

To use additional LLM libraries, you can create a wrapper to manually define a generator function and include custom output parsing.

The full response. If the streamed output only contains text, this is a string. Otherwise, this is a list of all the streamed objects. The return value is fully compatible as input for st.write.

You can pass an OpenAI stream as shown in our tutorial, Build a basic LLM chat app. Alternatively, you can pass a generic generator function as input:

If your stream object is not compatible with st.write_stream, define a wrapper around your stream object to create a compatible generator function.

For an example, see how we use Replicate with Snowflake Arctic in this code.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (python):
```python
import time
import numpy as np
import pandas as pd
import streamlit as st

_LOREM_IPSUM = """
Lorem ipsum dolor sit amet, **consectetur adipiscing** elit, sed do eiusmod tempor
incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis
nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
"""


def stream_data():
    for word in _LOREM_IPSUM.split(" "):
        yield word + " "
        time.sleep(0.02)

    yield pd.DataFrame(
        np.random.randn(5, 10),
        columns=["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"],
    )

    for word in _LOREM
...
```

---

## 2019 release notes - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/quick-reference/release-notes/2019

**Contents:**
- 2019 release notes
- Version 0.52.0
- Version 0.51.0
- Version 0.50.1
- Version 0.49.0
- Version 0.48.0
- Version 0.47.0
- Version 0.46.0
- Version 0.45.0
- Version 0.44.0

This page contains release notes for Streamlit versions released in 2019. For the latest version of Streamlit, see Release notes.

Release date: December 20, 2019

📤 Preview release of the file uploader widget. To try it out just call st.file_uploader!

Note that as a preview release things may change in the near future. Looking forward to hearing input from the community before we stabilize the API!

👋 Support for emoji codes in st.write and st.markdown! Try it out with st.write("Hello :wave:").

Release date: November 30, 2019

Release date: November 10, 2019

Release date: October 23, 2019

Release date: October 12, 2019

Release date: October 1, 2019

Release date: September 19, 2019

Release date: August 28, 2019

Release date: July 28, 2019

Release date: July 9, 2019

Release date: July 1, 2019

Release date: June 24, 2019

Release date: June 10, 2019

Why is this so much faster?

Now, Streamlit keeps a single Python session running until you kill the server. This means that Streamlit can re-run your code without kicking off a new process; imported libraries are cached to memory. An added bonus is that st.cache now caches to memory instead of to disk.

What happens if I run Streamlit the old way?

If you run $ python your_script.py the script will execute from top to bottom, but won't produce a Streamlit app.

What are the limitations of the new architecture?

What else do I need to know?

The strings we print to the command line when liveSave is on have been cleaned up. You may need to adjust any RegEx that depends on those.

A number of config options have been renamed:

What if something breaks?

If the new Streamlit isn't working, please let us know by Slack or email. You can downgrade at any time with these commands:

Thank you for staying with us on this journey! This version of Streamlit lays the foundation for interactive widgets, a new feature of Streamlit we're really excited to share with you in the next few months.

Release date: May 03, 2019

Release date: April 26, 2019

Our forums are full of helpful information and Streamlit experts.

---

## st.query_params - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/caching-and-state/st.query_params

**Contents:**
- st.query_params
  - Repeated keys
  - Limitation
- st.query_params.clear
- st.query_params.from_dict
    - Example
- st.query_params.get_all
- st.query_params.to_dict
  - Still have questions?

st.query_params provides a dictionary-like interface to access query parameters in your app's URL and is available as of Streamlit 1.30.0. It behaves similarly to st.session_state with the notable exception that keys may be repeated in an app's URL. Handling of repeated keys requires special consideration as explained below.

st.query_params can be used with both key and attribute notation. For example, st.query_params.my_key and st.query_params["my_key"]. All keys and values will be set and returned as strings. When you write to st.query_params, key-value pair prefixed with ? is added to the end of your app's URL. Each additional pair is prefixed with & instead of ?. Query parameters are cleared when navigating between pages in a multipage app.

For example, consider the following URL:

The parameters in the URL above will be accessible in st.query_params as:

This means you can use those parameters in your app like this:

When a key is repeated in your app's URL (?a=1&a=2&a=3), dict-like methods will return only the last value. In this example, st.query_params["a"] returns "3". To get all keys as a list, use the .get_all() method shown below. To set the value of a repeated key, assign the values as a list. For example, st.query_params.a = ["1", "2", "3"] produces the repeated key given at the beginning of this paragraph.

st.query_params can't get or set embedding settings as described in Embed your app. st.query_params.embed and st.query_params.embed_options will raise an AttributeError or StreamlitAPIException when trying to get or set their values, respectively.

Clear all query parameters from the URL of the app.

st.query_params.clear()

Set all of the query parameters from a dictionary or dictionary-like object.

This method primarily exists for advanced users who want to control multiple query parameters in a single update. To set individual query parameters, use key or attribute notation instead.

This method inherits limitations from st.query_params and can't be used to set embedding options as described in Embed your app.

To handle repeated keys, the value in a key-value pair should be a list.

.from_dict() is not a direct inverse of .to_dict() if you are working with repeated keys. A true inverse operation is {key: st.query_params.get_all(key) for key in st.query_params}.

st.query_params.from_dict(params)

A dictionary used to replace the current query parameters.

Get a list of all query parameter values associated to a given key.

When a k

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.query_params.from_dict({"foo": "bar", "baz": [1, "two"]})
```

---

## st.time_input - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.time_input

**Contents:**
- st.time_input
    - Example
  - Still have questions?

Display a time input widget.

st.time_input(label, value="now", key=None, help=None, on_change=None, args=None, kwargs=None, *, disabled=False, label_visibility="visible", step=0:15:00, width="stretch")

A short label explaining to the user what this time input is for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

For accessibility reasons, you should never set an empty label, but you can hide it with label_visibility if needed. In the future, we may disallow empty labels by raising an exception.

value ("now", datetime.time, datetime.datetime, str, or None)

The value of this widget when it first renders. This can be one of the following:

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

A tooltip that gets displayed next to the widget label. Streamlit only displays the tooltip when label_visibility="visible". If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

An optional callback invoked when this time_input's value changes.

An optional list or tuple of args to pass to the callback.

An optional dict of kwargs to pass to the callback.

An optional boolean that disables the time input if set to True. The default is False.

label_visibility ("visible", "hidden", or "collapsed")

The visibility of the label. The default is "visible". If this is "hidden", Streamlit displays an empty spacer instead of the label, which can help keep the widget aligned with other widgets. If this is "collapsed", Streamlit displays no label or spacer.

step (int or timedelta)

The stepping interval in seconds. Defaults to 900, i.e. 15 minutes. You can also pass a datetime.timedelta object.

width ("stretch" or int)

The width of the time input widget. This can be one of the following:

(datetime.time or None)

The current value of the time inp

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import datetime
import streamlit as st

t = st.time_input("Set an alarm for", datetime.time(8, 45))
st.write("Alarm is set for", t)
```

Example 2 (unknown):
```unknown
import datetime
import streamlit as st

t = st.time_input("Set an alarm for", value=None)
st.write("Alarm is set for", t)
```

---

## streamlit hello - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/cli/hello

**Contents:**
- $ streamlit hello
  - Syntax
  - Options
  - Example
    - Example 1: Run the Hello app with default settings
    - Example 2: Run the Hello app with a custom config option value
  - Still have questions?

Run the Hello app, an example Streamlit app included with the Streamlit library.

The hello command accepts configuration options (just like the run command does). Configuration options are passed in the form of --<section>.<option>=<value>. For example, if you want to set the primary color of your app to blue, you could use one of the three equivalent options:

For a complete list of configuration options, see config.toml in the API reference. For examples, see below.

To verify that Streamlit is installed correctly, this command runs an example app included in the Streamlit library. From any directory, execute the following:

Streamlit will start the Hello app and open it in your default browser. The source for the Hello app can be viewed in GitHub.

To run the Hello app with a blue accent color, from any directory, execute the following:

Our forums are full of helpful information and Streamlit experts.

---

## Release notes - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/quick-reference/release-notes

**Contents:**
- Release notes
- Upgrade Streamlit
    - Tip
- Version 1.50.0 (latest)
- Older versions of Streamlit
  - Still have questions?

This page lists highlights, bug fixes, and known issues for the latest release of Streamlit. If you're looking for information about nightly releases or experimental features, see Pre-release features.

To upgrade to the latest version of Streamlit, run:

Release date: September 23, 2025

Our forums are full of helpful information and Streamlit experts.

---

## st.html - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/text/st.html

**Contents:**
- st.html
    - Example
  - Still have questions?

Insert HTML into your app.

Adding custom HTML to your app impacts safety, styling, and maintainability. We sanitize HTML with DOMPurify, but inserting HTML remains a developer risk. Passing untrusted code to st.html or dynamically loading external code can increase the risk of vulnerabilities in your app.

st.html content is not iframed. Executing JavaScript is not supported at this time.

st.html(body, *, width="stretch")

The HTML code to insert. This can be one of the following:

If the resulting HTML content is empty, Streamlit will raise an error.

If body is a path to a CSS file, Streamlit will wrap the CSS content in <style> tags automatically. When the resulting HTML content only contains style tags, Streamlit will send the content to the event container instead of the main container to avoid taking up space in the app.

width ("stretch", "content", or int)

The width of the HTML element. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.html(
    "<p><span style='text-decoration: line-through double red;'>Oops</span>!</p>"
)
```

---

## st.cache_resource - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/caching-and-state/st.experimental_singleton

**Contents:**
    - Tip
- st.cache_resource
    - Example
- st.cache_resource.clear
    - Example
- CachedFunc.clear
    - Example
- Using Streamlit commands in cached functions
  - Static elements
  - Input widgets

This page only contains information on the st.cache_resource API. For a deeper dive into caching and how to use it, check out Caching.

Decorator to cache functions that return global resources (e.g. database connections, ML models).

Cached objects are shared across all users, sessions, and reruns. They must be thread-safe because they can be accessed from multiple threads concurrently. If thread safety is an issue, consider using st.session_state to store resources per session instead.

You can clear a function's cache with func.clear() or clear the entire cache with st.cache_resource.clear().

A function's arguments must be hashable to cache it. If you have an unhashable argument (like a database connection) or an argument you want to exclude from caching, use an underscore prefix in the argument name. In this case, Streamlit will return a cached value when all other arguments match a previous function call. Alternatively, you can declare custom hashing functions with hash_funcs.

Cached values are available to all users of your app. If you need to save results that should only be accessible within a session, use Session State instead. Within each user session, an @st.cache_resource-decorated function returns the cached instance of the return value (if the value is already cached). Therefore, objects cached by st.cache_resource act like singletons and can mutate. To cache data and return copies, use st.cache_data instead. To learn more about caching, see Caching overview.

Async objects are not officially supported in Streamlit. Caching async objects or objects that reference async objects may have unintended consequences. For example, Streamlit may close event loops in its normal operation and make the cached object raise an Event loop closed error.

To upvote official asyncio support, see GitHub issue #8488. To upvote support for caching async functions, see GitHub issue #8308.

st.cache_resource(func, *, ttl, max_entries, show_spinner, show_time=False, validate, hash_funcs=None)

The function that creates the cached resource. Streamlit hashes the function's source code.

ttl (float, timedelta, str, or None)

The maximum time to keep an entry in the cache. Can be one of:

max_entries (int or None)

The maximum number of entries to keep in the cache, or None for an unbounded cache. When a new entry is added to a full cache, the oldest cached entry will be removed. Defaults to None.

show_spinner (bool or str)

Enable the spinner. Default is True to sho

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import streamlit as st

@st.cache_resource
def get_database_session(url):
    # Create a database session object that points to the URL.
    return session

s1 = get_database_session(SESSION_URL_1)
# Actually executes the function, since this is the first time it was
# encountered.

s2 = get_database_session(SESSION_URL_1)
# Does not execute the function. Instead, returns its previously computed
# value. This means that now the connection object in s1 is the same as in s2.

s3 = get_database_session(SESSION_URL_2)
# This is a different URL, so the function executes.
```

Example 2 (python):
```python
import streamlit as st

@st.cache_resource
def get_database_session(_sessionmaker, url):
    # Create a database connection object that points to the URL.
    return connection

s1 = get_database_session(create_sessionmaker(), DATA_URL_1)
# Actually executes the function, since this is the first time it was
# encountered.

s2 = get_database_session(create_sessionmaker(), DATA_URL_1)
# Does not execute the function. Instead, returns its previously computed
# value - even though the _sessionmaker parameter was different
# in both calls.
```

Example 3 (python):
```python
import streamlit as st

@st.cache_resource
def get_database_session(_sessionmaker, url):
    # Create a database connection object that points to the URL.
    return connection

fetch_and_clean_data.clear(_sessionmaker, "https://streamlit.io/")
# Clear the cached entry for the arguments provided.

get_database_session.clear()
# Clear all cached entries for this function.
```

Example 4 (python):
```python
import streamlit as st
from pydantic import BaseModel

class Person(BaseModel):
    name: str

@st.cache_resource(hash_funcs={Person: str})
def get_person_name(person: Person):
    return person.name
```

---

## st.form_submit_button - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/execution-flow/st.form_submit_button

**Contents:**
- st.form_submit_button
  - Still have questions?

Display a form submit button.

When this button is clicked, all widget values inside the form will be sent from the user's browser to your Streamlit server in a batch.

Every form must have at least one st.form_submit_button. An st.form_submit_button cannot exist outside of a form.

For more information about forms, check out our docs.

st.form_submit_button(label="Submit", help=None, on_click=None, args=None, kwargs=None, *, key=None, type="secondary", icon=None, disabled=False, use_container_width=None, width="content")

A short label explaining to the user what this button is for. This defaults to "Submit". The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

A tooltip that gets displayed when the button is hovered over. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

An optional callback invoked when this button is clicked.

An optional list or tuple of args to pass to the callback.

An optional dict of kwargs to pass to the callback.

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

type ("primary", "secondary", or "tertiary")

An optional string that specifies the button type. This can be one of the following:

An optional emoji or icon to display next to the button label. If icon is None (default), no icon is displayed. If icon is a string, the following options are valid:

A single-character emoji. For example, you can set icon="🚨" or icon="🔥". Emoji short codes are not supported.

An icon from the Material Symbols library (rounded style) in the format ":material/icon_name:" where "icon_name" is the name of the icon in snake case.

For example, icon=":material/thumb_up:" will display the Thumb Up icon. Find additional icons in the Material Symbols font library.

Whether to disable the button. If this is False (default

*[Content truncated]*

---

## st.sidebar - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/layout/st.sidebar

**Contents:**
- st.sidebar
- Add widgets to sidebar
    - Tip
    - Important
  - Still have questions?

Not only can you add interactivity to your app with widgets, you can organize them into a sidebar. Elements can be passed to st.sidebar using object notation and with notation.

The following two snippets are equivalent:

Each element that's passed to st.sidebar is pinned to the left, allowing users to focus on the content in your app.

The sidebar is resizable! Drag and drop the right border of the sidebar to resize it! ↔️

Here's an example of how you'd add a selectbox and a radio button to your sidebar:

The only elements that aren't supported using object notation are st.echo, st.spinner, and st.toast. To use these elements, you must use with notation.

Here's an example of how you'd add st.echo and st.spinner to your sidebar:

Our forums are full of helpful information and Streamlit experts.

---

## 2023 release notes - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/quick-reference/release-notes/2023

**Contents:**
- 2023 release notes
- Version 1.29.0
- Version 1.28.0
- Version 1.27.0
- Version 1.26.0
- Version 1.25.0
- Version 1.24.0
- Version 1.23.0
- Version 1.22.0
- Version 1.21.0

This page contains release notes for Streamlit versions released in 2023. For the latest version of Streamlit, see Release notes.

Release date: November 30, 2023

Release date: October 26, 2023

Release date: September 21, 2023

Release date: August 24, 2023

Release date: July 20, 2023

Release date: June 27, 2023

Release date: June 1, 2023

Release date: April 27, 2023

Release date: April 6, 2023

Release date: March 09, 2023

Release date: February 23, 2023

Release date: February 09, 2023

Release date: January 12, 2023

Our forums are full of helpful information and Streamlit experts.

---

## st.title - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/text/st.title

**Contents:**
- st.title
    - Examples
  - Still have questions?

Display text in title formatting.

Each document should have a single st.title(), although this is not enforced.

st.title(body, anchor=None, *, help=None, width="stretch")

The text to display as GitHub-flavored Markdown. Syntax information can be found at: https://github.github.com/gfm.

See the body parameter of st.markdown for additional, supported Markdown directives.

anchor (str or False)

The anchor name of the header that can be accessed with #anchor in the URL. If omitted, it generates an anchor using the body. If False, the anchor is not shown in the UI.

A tooltip that gets displayed next to the title. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

width ("stretch", "content", or int)

The width of the title element. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.title("This is a title")
st.title("_Streamlit_ is :blue[cool] :sunglasses:")
```

---

## st.experimental_connection - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/connections/st.experimental_connection

**Contents:**
    - Important
    - Tip
- st.experimental_connection
    - Warning
  - Still have questions?

This is an experimental feature. Experimental features and their APIs may change or be removed at any time. To learn more, click here.

This page only contains the st.experimental_connection API. For a deeper dive into creating and managing data connections within Streamlit apps, read Connecting to data.

This method did not exist in version 1.50.0 of Streamlit.

For a comprehensive overview of this feature, check out this video tutorial by Joshua Carroll, Streamlit's Product Manager for Developer Experience. You'll learn about the feature's utility in creating and managing data connections within your apps by using real-world examples.

Our forums are full of helpful information and Streamlit experts.

---

## st.column_config.AreaChartColumn - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.areachartcolumn?utm_source=streamlit

**Contents:**
- st.column_config.AreaChartColumn
    - Examples
  - Still have questions?

Configure an area chart column in st.dataframe or st.data_editor.

Cells need to contain a list of numbers. Chart columns are not editable at the moment. This command needs to be used in the column_config parameter of st.dataframe or st.data_editor.

st.column_config.AreaChartColumn(label=None, *, width=None, help=None, pinned=None, y_min=None, y_max=None, color=None)

The label shown at the top of the column. If this is None (default), the column name is used.

width ("small", "medium", "large", int, or None)

The display width of the column. If this is None (default), the column will be sized to fit the cell contents. Otherwise, this can be one of the following:

If the total width of all columns is less than the width of the dataframe, the remaining space will be distributed evenly among all columns.

A tooltip that gets displayed when hovering over the column label. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

pinned (bool or None)

Whether the column is pinned. A pinned column will stay visible on the left side no matter where the user scrolls. If this is None (default), Streamlit will decide: index columns are pinned, and data columns are not pinned.

y_min (int, float, or None)

The minimum value on the y-axis for all cells in the column. If this is None (default), every cell will use the minimum of its data.

y_max (int, float, or None)

The maximum value on the y-axis for all cells in the column. If this is None (default), every cell will use the maximum of its data.

color ("auto", "auto-inverse", str, or None)

The color to use for the chart. This can be one of the following:

The basic color palette can be configured in the theme settings.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "sales": [
            [0, 4, 26, 80, 100, 40],
            [80, 20, 80, 35, 40, 100],
            [10, 20, 80, 80, 70, 0],
            [10, 100, 20, 100, 30, 100],
        ],
    }
)

st.data_editor(
    data_df,
    column_config={
        "sales": st.column_config.AreaChartColumn(
            "Sales (last 6 months)",
            width="medium",
            help="The sales volume in the last 6 months",
            y_min=0,
            y_max=100,
         ),
    },
    hide_index=True,
)
```

---

## st.plotly_chart - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/charts/st.plotly_chart

**Contents:**
- st.plotly_chart
    - Examples
- Chart selections
  - PlotlyState
    - Example
  - PlotlySelectionState
    - Example
- Theming
  - Still have questions?

Display an interactive Plotly chart.

Plotly is a charting library for Python. The arguments to this function closely follow the ones for Plotly's plot() function.

To show Plotly charts in Streamlit, call st.plotly_chart wherever you would call Plotly's py.plot or py.iplot.

You must install plotly>=4.0.0 to use this command. Your app's performance may be enhanced by installing orjson as well. You can install all charting dependencies (except Bokeh) as an extra with Streamlit:

st.plotly_chart(figure_or_data, use_container_width=True, *, theme="streamlit", key=None, on_select="ignore", selection_mode=('points', 'box', 'lasso'), config=None, **kwargs)

figure_or_data (plotly.graph_objs.Figure, plotly.graph_objs.Data, or dict/list of plotly.graph_objs.Figure/Data)

The Plotly Figure or Data object to render. See https://plot.ly/python/ for examples of graph descriptions.

If your chart contains more than 1000 data points, Plotly will use a WebGL renderer to display the chart. Different browsers have different limits on the number of WebGL contexts per page. If you have multiple WebGL contexts on a page, you may need to switch to SVG rendering mode. You can do this by setting render_mode="svg" within the figure. For example, the following code defines a Plotly Express line chart that will render in SVG mode when passed to st.plotly_chart: px.line(df, x="x", y="y", render_mode="svg").

use_container_width (bool)

Whether to override the figure's native width with the width of the parent container. If use_container_width is True (default), Streamlit sets the width of the figure to match the width of the parent container. If use_container_width is False, Streamlit sets the width of the chart to fit its contents according to the plotting library, up to the width of the parent container.

theme ("streamlit" or None)

The theme of the chart. If theme is "streamlit" (default), Streamlit uses its own design default. If theme is None, Streamlit falls back to the default behavior of the library.

The "streamlit" theme can be partially customized through the configuration options theme.chartCategoricalColors and theme.chartSequentialColors. Font configuration options are also applied.

An optional string to use for giving this element a stable identity. If key is None (default), this element's identity will be determined based on the values of the other parameters.

Additionally, if selections are activated and key is provided, Streamlit will register the key in Sessio

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
pip install streamlit[charts]
```

Example 2 (python):
```python
import plotly.figure_factory as ff
import streamlit as st
from numpy.random import default_rng as rng

hist_data = [
    rng(0).standard_normal(200) - 2,
    rng(1).standard_normal(200),
    rng(2).standard_normal(200) + 2,
]
group_labels = ["Group 1", "Group 2", "Group 3"]

fig = ff.create_distplot(
    hist_data, group_labels, bin_size=[0.1, 0.25, 0.5]
)

st.plotly_chart(fig)
```

Example 3 (unknown):
```unknown
import plotly.graph_objects as go
import streamlit as st

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=[1, 2, 3, 4, 5],
        y=[1, 3, 2, 5, 4]
    )
)

st.plotly_chart(fig, config = {'scrollZoom': False})
```

Example 4 (unknown):
```unknown
import plotly.express as px
import streamlit as st

df = px.data.iris()
fig = px.scatter(df, x="sepal_width", y="sepal_length")

event = st.plotly_chart(fig, key="iris", on_select="rerun")

event
```

---

## st.dataframe - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.dataframe

**Contents:**
    - Tip
- st.dataframe
    - Examples
- Dataframe selections
  - DataframeState
  - DataframeSelectionState
    - Example
- element.add_rows
    - Example
- Interactivity

Learn more in our Dataframes guide and check out our tutorial, Get dataframe row-selections from users.

Display a dataframe as an interactive table.

This command works with a wide variety of collection-like and dataframe-like object types.

st.dataframe(data=None, width="stretch", height="auto", *, use_container_width=None, hide_index=None, column_order=None, column_config=None, key=None, on_select="ignore", selection_mode="multi-row", row_height=None)

data (dataframe-like, collection-like, or None)

Dataframe-like objects include dataframe and series objects from popular libraries like Dask, Modin, Numpy, pandas, Polars, PyArrow, Snowpark, Xarray, and more. You can use database cursors and clients that comply with the Python Database API Specification v2.0 (PEP 249). Additionally, you can use anything that supports the Python dataframe interchange protocol.

For example, you can use the following:

If a data type is not recognized, Streamlit will convert the object to a pandas.DataFrame or pyarrow.Table using a .to_pandas() or .to_arrow() method, respectively, if available.

If data is a pandas.Styler, it will be used to style its underlying pandas.DataFrame. Streamlit supports custom cell values, colors, and font weights. It does not support some of the more exotic styling options, like bar charts, hovering, and captions. For these styling options, use column configuration instead. Text and number formatting from column_config always takes precedence over text and number formatting from pandas.Styler.

Collection-like objects include all Python-native Collection types, such as dict, list, and set.

If data is None, Streamlit renders an empty table.

width ("stretch", "content", or int)

The width of the dataframe element. This can be one of the following:

height (int or "auto")

The height of the dataframe element. This can be one of the following:

Vertical scrolling within the dataframe element is enabled when the height does not accommodate all rows.

use_container_width (bool)

use_container_width is deprecated and will be removed in a future release. For use_container_width=True, use width="stretch".

Whether to override width with the width of the parent container. If this is True (default), Streamlit sets the width of the dataframe to match the width of the parent container. If this is False, Streamlit sets the dataframe's width according to width.

hide_index (bool or None)

Whether to hide the index column(s). If hide_index is None (default)

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(
    rng(0).standard_normal((50, 20)), columns=("col %d" % i for i in range(20))
)

st.dataframe(df)
```

Example 2 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(
    rng(0).standard_normal((10, 20)), columns=("col %d" % i for i in range(20))
)

st.dataframe(df.style.highlight_max(axis=0))
```

Example 3 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(
    {
        "name": ["Roadmap", "Extras", "Issues"],
        "url": [
            "https://roadmap.streamlit.app",
            "https://extras.streamlit.app",
            "https://issues.streamlit.app",
        ],
        "stars": rng(0).integers(0, 1000, size=3),
        "views_history": rng(0).integers(0, 5000, size=(3, 30)).tolist(),
    }
)

st.dataframe(
    df,
    column_config={
        "name": "App name",
        "stars": st.column_config.NumberColumn(
            "Github Stars
...
```

Example 4 (python):
```python
from datetime import datetime, date
import numpy as np
import pandas as pd
import streamlit as st

@st.cache_data
def load_data():
    year = datetime.now().year
    df = pd.DataFrame(
        {
            "Date": [date(year, month, 1) for month in range(1, 4)],
            "Total": np.random.randint(1000, 5000, size=3),
        }
    )
    df.set_index("Date", inplace=True)
    return df

df = load_data()
config = {
    "_index": st.column_config.DateColumn("Month", format="MMM YYYY"),
    "Total": st.column_config.NumberColumn("Total ($)"),
}

st.dataframe(df, column_config=config)
```

---

## Pre-release features - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/quick-reference/prerelease

**Contents:**
- Pre-release features
- Experimental Features
    - Warning
  - The lifecycle of an experimental feature
- Nightly releases
    - Warning
  - Still have questions?

At Streamlit, we like to move quick while keeping things stable. In our latest effort to move even faster without sacrificing stability, we're offering our bold and fearless users two ways to try out Streamlit's bleeding-edge features:

Less stable Streamlit features have one naming convention: st.experimental_. This distinction is a prefix we attach to our command names to make sure their status is clear to everyone.

Here's a quick rundown of what you get from each naming convention:

Features with the experimental_ naming convention are things that we're still working on or trying to understand. If these features are successful, at some point they'll become part of Streamlit core. If unsuccessful, these features are removed without much notice. While in experimental, a feature's API and behaviors may not be stable, and it's possible they could change in ways that aren't backward-compatible.

Experimental features and their APIs may change or be removed at any time.

In addition to experimental features, we offer another way to try out Streamlit's newest features: nightly releases.

At the end of each day (at night 🌛), our bots run automated tests against the latest Streamlit code and, if everything looks good, it publishes them as the streamlit-nightly package. This means the nightly build includes all our latest features, bug fixes, and other enhancements on the same day they land on our codebase.

How does this differ from official releases?

Official Streamlit releases go not only through both automated tests but also rigorous manual testing, while nightly releases only have automated tests. It's important to keep in mind that new features introduced in nightly releases often lack polish. In our official releases, we always make double-sure all new features are ready for prime time.

How do I use the nightly release?

All you need to do is install the streamlit-nightly package:

You should never have both streamlit and streamlit-nightly installed in the same environment!

Why should I use the nightly release?

Because you can't wait for official releases, and you want to help us find bugs early!

Why shouldn't I use the nightly release?

While our automated tests have high coverage, there's still a significant likelihood that there will be some bugs in the nightly code.

Can I choose which nightly release I want to install?

If you'd like to use a specific version, you can find the version number in our Release history. Specify the desired version us

*[Content truncated]*

---

## st.pydeck_chart - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/charts/st.pydeck_chart

**Contents:**
- st.pydeck_chart
    - Example
- Chart selections
  - PydeckState
  - PydeckSelectionState
    - Examples
  - Still have questions?

Draw a chart using the PyDeck library.

This supports 3D maps, point clouds, and more! More info about PyDeck at https://deckgl.readthedocs.io/en/latest/.

These docs are also quite useful:

When using this command, a service called Carto provides the map tiles to render map content. If you're using advanced PyDeck features you may need to obtain an API key from Carto first. You can do that as pydeck.Deck(api_keys={"carto": YOUR_KEY}) or by setting the CARTO_API_KEY environment variable. See PyDeck's documentation for more information.

Another common provider for map tiles is Mapbox. If you prefer to use that, you'll need to create an account at https://mapbox.com and specify your Mapbox key when creating the pydeck.Deck object. You can do that as pydeck.Deck(api_keys={"mapbox": YOUR_KEY}) or by setting the MAPBOX_API_KEY environment variable.

Carto and Mapbox are third-party products and Streamlit accepts no responsibility or liability of any kind for Carto or Mapbox, or for any content or information made available by Carto or Mapbox. The use of Carto or Mapbox is governed by their respective Terms of Use.

Pydeck uses two WebGL contexts per chart, and different browsers have different limits on the number of WebGL contexts per page. If you exceed this limit, the oldest contexts will be dropped to make room for the new ones. To avoid this limitation in most browsers, don't display more than eight Pydeck charts on a single page.

st.pydeck_chart(pydeck_obj=None, *, use_container_width=True, width=None, height=None, selection_mode="single-object", on_select="ignore", key=None)

pydeck_obj (pydeck.Deck or None)

Object specifying the PyDeck chart to draw.

use_container_width (bool)

Whether to override the figure's native width with the width of the parent container. If use_container_width is True (default), Streamlit sets the width of the figure to match the width of the parent container. If use_container_width is False, Streamlit sets the width of the chart to fit its contents according to the plotting library, up to the width of the parent container.

Desired width of the chart expressed in pixels. If width is None (default), Streamlit sets the width of the chart to fit its contents according to the plotting library, up to the width of the parent container. If width is greater than the width of the parent container, Streamlit sets the chart width to match the width of the parent container.

To use width, you must set use_container_width=False.

Desire

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import pandas as pd
import pydeck as pdk
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(
    rng(0).standard_normal((1000, 2)) / [50, 50] + [37.76, -122.4],
    columns=["lat", "lon"],
)

st.pydeck_chart(
    pdk.Deck(
        map_style=None,  # Use Streamlit theme to pick map style
        initial_view_state=pdk.ViewState(
            latitude=37.76,
            longitude=-122.4,
            zoom=11,
            pitch=50,
        ),
        layers=[
            pdk.Layer(
                "HexagonLayer",
                data=df,
                get_positi
...
```

Example 2 (unknown):
```unknown
import streamlit as st
import pydeck
import pandas as pd

capitals = pd.read_csv(
    "capitals.csv",
    header=0,
    names=[
        "Capital",
        "State",
        "Abbreviation",
        "Latitude",
        "Longitude",
        "Population",
    ],
)
capitals["size"] = capitals.Population / 10

point_layer = pydeck.Layer(
    "ScatterplotLayer",
    data=capitals,
    id="capital-cities",
    get_position=["Longitude", "Latitude"],
    get_color="[255, 75, 75]",
    pickable=True,
    auto_highlight=True,
    get_radius="size",
)

view_state = pydeck.ViewState(
    latitude=40, longit
...
```

Example 3 (unknown):
```unknown
{
  "indices":{
    "capital-cities":[
      2
    ]
  },
  "objects":{
    "capital-cities":[
      {
        "Abbreviation":" AZ"
        "Capital":"Phoenix"
        "Latitude":33.448457
        "Longitude":-112.073844
        "Population":1650070
        "State":" Arizona"
        "size":165007.0
      }
    ]
  }
}
```

---

## Session State - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state

**Contents:**
- Session State
  - Initialize values in Session State
  - Reads and updates
  - Delete items
  - Session State and Widget State association
  - Use Callbacks to update Session State
  - Forms and Callbacks
  - Serializable Session State
    - Warning
  - Caveats and limitations

Session State is a way to share variables between reruns, for each user session. In addition to the ability to store and persist state, Streamlit also exposes the ability to manipulate state using Callbacks. Session state also persists across apps inside a multipage app.

Check out this Session State basics tutorial video by Streamlit Developer Advocate Dr. Marisa Smith to get started:

The Session State API follows a field-based API, which is very similar to Python dictionaries:

Read the value of an item in Session State and display it by passing to st.write :

Update an item in Session State by assigning it a value:

Curious about what is in Session State? Use st.write or magic:

Streamlit throws a handy exception if an uninitialized variable is accessed:

Delete items in Session State using the syntax to delete items in any Python dictionary:

Session State can also be cleared by going to Settings → Clear Cache, followed by Rerunning the app.

Every widget with a key is automatically added to Session State:

A callback is a python function which gets called when an input widget changes.

Order of execution: When updating Session state in response to events, a callback function gets executed first, and then the app is executed from top to bottom.

Callbacks can be used with widgets using the parameters on_change (or on_click), args, and kwargs:

Widgets which support the on_change event:

Widgets which support the on_click event:

To add a callback, define a callback function above the widget declaration and pass it to the widget via the on_change (or on_click ) parameter.

Widgets inside a form can have their values be accessed and set via the Session State API. st.form_submit_button can have a callback associated with it. The callback gets executed upon clicking on the submit button. For example:

Serialization refers to the process of converting an object or data structure into a format that can be persisted and shared, and allowing you to recover the data’s original structure. Python’s built-in pickle module serializes Python objects to a byte stream ("pickling") and deserializes the stream into an object ("unpickling").

By default, Streamlit’s Session State allows you to persist any Python object for the duration of the session, irrespective of the object’s pickle-serializability. This property lets you store Python primitives such as integers, floating-point numbers, complex numbers and booleans, dataframes, and even lambdas returned by functions

*[Content truncated]*

---

## Data elements - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data

**Contents:**
- Data elements
    - Dataframes
    - Data editor
    - Column configuration
    - Static tables
    - Metrics
    - Dicts and JSON
    - Image Coordinates
    - Plotly Events
    - Streamlit Extras

When you're working with data, it is extremely valuable to visualize that data quickly, interactively, and from multiple different angles. That's what Streamlit is actually built and optimized for.

You can display data via charts, and you can display it in raw form. These are the Streamlit commands you can use to display and interact with raw data.

Display a dataframe as an interactive table.

Display a data editor widget.

Configure the display and editing behavior of dataframes and data editors.

Display a static table.

Display a metric in big bold font, with an optional indicator of how the metric changed.

Display object or string as a pretty-printed JSON string.

Third-party components

These are featured components created by our lovely community. For more examples and inspiration, check out our Components Gallery and Streamlit Extras!

Get the coordinates of clicks on an image. Created by @blackary.

Make Plotly charts interactive!. Created by @null-jones.

A library with useful Streamlit extras. Created by @arnaudmiribel.

Implementation of Ag-Grid component for Streamlit. Created by @PablocFonseca.

Streamlit Component for rendering Folium maps. Created by @randyzwitch.

Pandas profiling component for Streamlit. Created by @okld.

Get the coordinates of clicks on an image. Created by @blackary.

Make Plotly charts interactive!. Created by @null-jones.

A library with useful Streamlit extras. Created by @arnaudmiribel.

Implementation of Ag-Grid component for Streamlit. Created by @PablocFonseca.

Streamlit Component for rendering Folium maps. Created by @randyzwitch.

Pandas profiling component for Streamlit. Created by @okld.

Get the coordinates of clicks on an image. Created by @blackary.

Make Plotly charts interactive!. Created by @null-jones.

A library with useful Streamlit extras. Created by @arnaudmiribel.

Our forums are full of helpful information and Streamlit experts.

---

## st.connection - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/connections/st.connection

**Contents:**
    - Tip
- st.connection
    - Examples
  - Still have questions?

This page only contains the st.connection API. For a deeper dive into creating and managing data connections within Streamlit apps, read Connecting to data.

Create a new connection to a data store or API, or return an existing one.

Configuration options, credentials, and secrets for connections are combined from the following sources:

The connection returned from st.connection is internally cached with st.cache_resource and is therefore shared between sessions.

st.connection(name, type=None, max_entries=None, ttl=None, **kwargs)

The connection name used for secrets lookup in secrets.toml. Streamlit uses secrets under [connections.<name>] for the connection. type will be inferred if name is one of the following: "snowflake", "snowpark", or "sql".

type (str, connection class, or None)

The type of connection to create. This can be one of the following:

max_entries (int or None)

The maximum number of connections to keep in the cache. If this is None (default), the cache is unbounded. Otherwise, when a new entry is added to a full cache, the oldest cached entry is removed.

ttl (float, timedelta, or None)

The maximum number of seconds to keep results in the cache. If this is None (default), cached results do not expire with time.

Connection-specific keyword arguments that are passed to the connection's ._connect() method. **kwargs are typically combined with (and take precedence over) key-value pairs in secrets.toml. To learn more, see the specific connection's documentation.

(Subclass of BaseConnection)

An initialized connection object of the specified type.

Example 1: Inferred connection type

The easiest way to create a first-party (SQL, Snowflake, or Snowpark) connection is to use their default names and define corresponding sections in your secrets.toml file. The following example creates a "sql"-type connection.

.streamlit/secrets.toml:

Example 2: Named connections

Creating a connection with a custom name requires you to explicitly specify the type. If type is not passed as a keyword argument, it must be set in the appropriate section of secrets.toml. The following example creates two "sql"-type connections, each with their own custom name. The first defines type in the st.connection command; the second defines type in secrets.toml.

.streamlit/secrets.toml:

Example 3: Using a path to the connection class

Passing the full module path to the connection class can be useful, especially when working with a custom connection. Although this i

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
[connections.sql]
dialect = "xxx"
host = "xxx"
username = "xxx"
password = "xxx"
```

Example 2 (unknown):
```unknown
import streamlit as st
conn = st.connection("sql")
```

Example 3 (unknown):
```unknown
[connections.first_connection]
dialect = "xxx"
host = "xxx"
username = "xxx"
password = "xxx"

[connections.second_connection]
type = "sql"
dialect = "yyy"
host = "yyy"
username = "yyy"
password = "yyy"
```

Example 4 (unknown):
```unknown
import streamlit as st
conn1 = st.connection("first_connection", type="sql")
conn2 = st.connection("second_connection")
```

---

## Configuration - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/configuration

**Contents:**
- Configuration
    - Configuration file
    - Get config option
    - Set config option
    - Set page title, favicon, and more
  - Still have questions?

Configures the default settings for your app.

Retrieve a single configuration option.

Set a single configuration option. (This is very limited.)

Configures the default settings of the page.

Our forums are full of helpful information and Streamlit experts.

---

## st.login - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/user/st.login

**Contents:**
    - Tip
- st.login
    - Examples
  - Still have questions?

Learn more in User authentication and information.

Initiate the login flow for the given provider.

This command redirects the user to an OpenID Connect (OIDC) provider. After the user authenticates their identity, they are redirected back to the home page of your app. Streamlit stores a cookie with the user's identity information in the user's browser . You can access the identity information through st.user. Call st.logout() to remove the cookie and start a new session.

You can use any OIDC provider, including Google, Microsoft, Okta, and more. You must configure the provider through secrets management. Although OIDC is an extension of OAuth 2.0, you can't use generic OAuth providers. Streamlit parses the user's identity token and surfaces its attributes in st.user. If the provider returns an access token, that token is ignored. Therefore, this command will not allow your app to act on behalf of a user in a secure system.

For all providers, there are two shared settings, redirect_uri and cookie_secret, which you must specify in an [auth] dictionary in secrets.toml. Other settings must be defined as described in the provider parameter.

In addition to the shared settings, the following settings are required:

For a complete list of OIDC parameters, see OpenID Connect Core and your provider's documentation. By default, Streamlit sets scope="openid profile email" and prompt="select_account". You can change these and other OIDC parameters by passing a dictionary of settings to client_kwargs. state and nonce, which are used for security, are handled automatically and don't need to be specified. For more information, see Example 4.

You must install Authlib>=1.3.2 to use this command. You can install it as an extra with Streamlit:

Your authentication configuration is dependent on your host location. When you deploy your app, remember to update your redirect_uri within your app and your provider.

All URLs declared in the settings must be absolute (i.e., begin with http:// or https://).

Streamlit automatically enables CORS and XSRF protection when you configure authentication in secrets.toml. This takes precedence over configuration options in config.toml.

If a user is logged into your app and opens a new tab in the same browser, they will automatically be logged in to the new session with the same account.

If a user closes your app without logging out, the identity cookie will expire after 30 days.

For security reasons, authentication is not supported 

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
pip install streamlit[auth]
```

Example 2 (unknown):
```unknown
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "xxx"
client_id = "xxx"
client_secret = "xxx"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"  # fmt: skip
```

Example 3 (unknown):
```unknown
import streamlit as st

if not st.user.is_logged_in:
    if st.button("Log in"):
        st.login()
else:
    if st.button("Log out"):
        st.logout()
    st.write(f"Hello, {st.user.name}!")
```

Example 4 (unknown):
```unknown
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "xxx"

[auth.microsoft]
client_id = "xxx"
client_secret = "xxx"
server_metadata_url = "https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration"
```

---

## st.columns - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/layout/st.columns

**Contents:**
- st.columns
    - Examples
  - Still have questions?

Insert containers laid out as side-by-side columns.

Inserts a number of multi-element containers laid out side-by-side and returns a list of container objects.

To add elements to the returned containers, you can use the with notation (preferred) or just call methods directly on the returned object. See examples below.

To follow best design practices and maintain a good appearance on all screen sizes, don't nest columns more than once.

st.columns(spec, *, gap="small", vertical_alignment="top", border=False, width="stretch")

spec (int or Iterable of numbers)

Controls the number and width of columns to insert. Can be one of:

gap ("small", "medium", "large", or None)

The size of the gap between the columns. This can be one of the following:

The rem unit is relative to the theme.baseFontSize configuration option.

vertical_alignment ("top", "center", or "bottom")

The vertical alignment of the content inside the columns. The default is "top".

Whether to show a border around the column containers. If this is False (default), no border is shown. If this is True, a border is shown around each column.

width (int or "stretch")

The desired width of the columns expressed in pixels. If this is "stretch" (default), Streamlit sets the width of the columns to match the width of the parent container. Otherwise, this must be an integer. If the specified width is greater than the width of the parent container, Streamlit sets the width of the columns to match the width of the parent container.

A list of container objects.

Example 1: Use context management

You can use the with statement to insert any element into a column:

Example 2: Use commands as container methods

You can just call methods directly on the returned objects:

Example 3: Align widgets

Use vertical_alignment="bottom" to align widgets.

Example 4: Use vertical alignment to create grids

Adjust vertical alignment to customize your grid layouts.

Example 5: Add borders

Add borders to your columns instead of nested containers for consistent heights.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

col1, col2, col3 = st.columns(3)

with col1:
    st.header("A cat")
    st.image("https://static.streamlit.io/examples/cat.jpg")

with col2:
    st.header("A dog")
    st.image("https://static.streamlit.io/examples/dog.jpg")

with col3:
    st.header("An owl")
    st.image("https://static.streamlit.io/examples/owl.jpg")
```

Example 2 (python):
```python
import streamlit as st
from numpy.random import default_rng as rng

df = rng(0).standard_normal((10, 1))
col1, col2 = st.columns([3, 1])

col1.subheader("A wide column with a chart")
col1.line_chart(df)

col2.subheader("A narrow column with the data")
col2.write(df)
```

Example 3 (unknown):
```unknown
import streamlit as st

left, middle, right = st.columns(3, vertical_alignment="bottom")

left.text_input("Write something")
middle.button("Click me", use_container_width=True)
right.checkbox("Check me")
```

Example 4 (unknown):
```unknown
import streamlit as st

vertical_alignment = st.selectbox(
    "Vertical alignment", ["top", "center", "bottom"], index=2
)

left, middle, right = st.columns(3, vertical_alignment=vertical_alignment)
left.image("https://static.streamlit.io/examples/cat.jpg")
middle.image("https://static.streamlit.io/examples/dog.jpg")
right.image("https://static.streamlit.io/examples/owl.jpg")
```

---

## st.column_config.DatetimeColumn - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.datetimecolumn

**Contents:**
- st.column_config.DatetimeColumn
    - Examples
  - Still have questions?

Configure a datetime column in st.dataframe or st.data_editor.

This is the default column type for datetime values. This command needs to be used in the column_config parameter of st.dataframe or st.data_editor. When used with st.data_editor, editing will be enabled with a datetime picker widget.

st.column_config.DatetimeColumn(label=None, *, width=None, help=None, disabled=None, required=None, pinned=None, default=None, format=None, min_value=None, max_value=None, step=None, timezone=None)

The label shown at the top of the column. If this is None (default), the column name is used.

width ("small", "medium", "large", int, or None)

The display width of the column. If this is None (default), the column will be sized to fit the cell contents. Otherwise, this can be one of the following:

If the total width of all columns is less than the width of the dataframe, the remaining space will be distributed evenly among all columns.

A tooltip that gets displayed when hovering over the column label. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

disabled (bool or None)

Whether editing should be disabled for this column. If this is None (default), Streamlit will enable editing wherever possible.

If a column has mixed types, it may become uneditable regardless of disabled.

required (bool or None)

Whether edited cells in the column need to have a value. If this is False (default), the user can submit empty values for this column. If this is True, an edited cell in this column can only be submitted if its value is not None, and a new row will only be submitted after the user fills in this column.

pinned (bool or None)

Whether the column is pinned. A pinned column will stay visible on the left side no matter where the user scrolls. If this is None (default), Streamlit will decide: index columns are pinned, and data columns are not pinned.

default (datetime.datetime or None)

Specifies the default value in this column when a new row is added by the user. This defaults to None.

format (str, "localized", "distance", "calendar", "iso8601", or None)

A format string controlling how datetimes are displayed. This can be one of the following values:

Formatting from column_config always takes precedence over formatting from pandas.Styler. The formatting does not impact the return value when used in st.data_editor.

min

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
from datetime import datetime
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "appointment": [
            datetime(2024, 2, 5, 12, 30),
            datetime(2023, 11, 10, 18, 0),
            datetime(2024, 3, 11, 20, 10),
            datetime(2023, 9, 12, 3, 0),
        ]
    }
)

st.data_editor(
    data_df,
    column_config={
        "appointment": st.column_config.DatetimeColumn(
            "Appointment",
            min_value=datetime(2023, 6, 1),
            max_value=datetime(2025, 1, 1),
            format="D MMM YYYY, h:mm a",
            step=60,
 
...
```

---

## st.header - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/text/st.header

**Contents:**
- st.header
    - Examples
  - Still have questions?

Display text in header formatting.

st.header(body, anchor=None, *, help=None, divider=False, width="stretch")

The text to display as GitHub-flavored Markdown. Syntax information can be found at: https://github.github.com/gfm.

See the body parameter of st.markdown for additional, supported Markdown directives.

anchor (str or False)

The anchor name of the header that can be accessed with #anchor in the URL. If omitted, it generates an anchor using the body. If False, the anchor is not shown in the UI.

A tooltip that gets displayed next to the header. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

divider (bool, "blue", "green", "orange", "red", "violet", "yellow", "gray"/"grey", or "rainbow")

Shows a colored divider below the header. If this is True, successive headers will cycle through divider colors, except gray and rainbow. That is, the first header will have a blue line, the second header will have a green line, and so on. If this is a string, the color can be set to one of the following: blue, green, orange, red, violet, yellow, gray/grey, or rainbow.

width ("stretch", "content", or int)

The width of the header element. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.header("_Streamlit_ is :blue[cool] :sunglasses:")
st.header("This is a header with a divider", divider="gray")
st.header("These headers have rotating dividers", divider=True)
st.header("One", divider=True)
st.header("Two", divider=True)
st.header("Three", divider=True)
st.header("Four", divider=True)
```

---

## st.empty - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/layout/st.empty

**Contents:**
- st.empty
    - Examples
  - Still have questions?

Insert a single-element container.

Inserts a container into your app that can be used to hold a single element. This allows you to, for example, remove elements at any point, or replace several elements at once (using a child multi-element container).

To insert/replace/clear an element on the returned container, you can use with notation or just call methods directly on the returned object. See examples below.

Inside a with st.empty(): block, each displayed element will replace the previous one.

You can use an st.empty to replace multiple elements in succession. Use st.container inside st.empty to display (and later replace) a group of elements.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st
import time

with st.empty():
    for seconds in range(10):
        st.write(f"⏳ {seconds} seconds have passed")
        time.sleep(1)
    st.write(":material/check: 10 seconds over!")
st.button("Rerun")
```

Example 2 (unknown):
```unknown
import streamlit as st
import time

st.button("Start over")

placeholder = st.empty()
placeholder.markdown("Hello")
time.sleep(1)

placeholder.progress(0, "Wait for it...")
time.sleep(1)
placeholder.progress(50, "Wait for it...")
time.sleep(1)
placeholder.progress(100, "Wait for it...")
time.sleep(1)

with placeholder.container():
    st.line_chart({"data": [1, 5, 2, 6]})
    time.sleep(1)
    st.markdown("3...")
    time.sleep(1)
    st.markdown("2...")
    time.sleep(1)
    st.markdown("1...")
    time.sleep(1)

placeholder.markdown("Poof!")
time.sleep(1)

placeholder.empty()
```

---

## st.expander - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/layout/st.expander

**Contents:**
- st.expander
    - Examples
  - Still have questions?

Insert a multi-element container that can be expanded/collapsed.

Inserts a container into your app that can be used to hold multiple elements and can be expanded or collapsed by the user. When collapsed, all that is visible is the provided label.

To add elements to the returned container, you can use the with notation (preferred) or just call methods directly on the returned object. See examples below.

All content within the expander is computed and sent to the frontend, even if the expander is closed.

To follow best design practices and maintain a good appearance on all screen sizes, don't nest expanders.

st.expander(label, expanded=False, *, icon=None, width="stretch")

A string to use as the header for the expander. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

If True, initializes the expander in "expanded" state. Defaults to False (collapsed).

An optional emoji or icon to display next to the expander label. If icon is None (default), no icon is displayed. If icon is a string, the following options are valid:

A single-character emoji. For example, you can set icon="🚨" or icon="🔥". Emoji short codes are not supported.

An icon from the Material Symbols library (rounded style) in the format ":material/icon_name:" where "icon_name" is the name of the icon in snake case.

For example, icon=":material/thumb_up:" will display the Thumb Up icon. Find additional icons in the Material Symbols font library.

width ("stretch" or int)

The width of the expander container. This can be one of the following:

You can use the with notation to insert any element into an expander

Or you can just call methods directly on the returned objects:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.bar_chart({"data": [1, 5, 2, 6, 2, 1]})

with st.expander("See explanation"):
    st.write('''
        The chart above shows some numbers I picked for you.
        I rolled actual dice for these, so they're *guaranteed* to
        be random.
    ''')
    st.image("https://static.streamlit.io/examples/dice.jpg")
```

Example 2 (unknown):
```unknown
import streamlit as st

st.bar_chart({"data": [1, 5, 2, 6, 2, 1]})

expander = st.expander("See explanation")
expander.write('''
    The chart above shows some numbers I picked for you.
    I rolled actual dice for these, so they're *guaranteed* to
    be random.
''')
expander.image("https://static.streamlit.io/examples/dice.jpg")
```

---

## Quick reference - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/quick-reference

**Contents:**
- Quick reference
      - Cheatsheet
      - Release notes
      - Pre-release features
      - Roadmap
  - Still have questions?

A dense list of Streamlit commands with example syntax.

See how Streamlit has changed with each new version.

Understand how we introduce new features and how you can get your hands on them sooner!

Get a sneak peek at what we have scheduled for the next year.

Our forums are full of helpful information and Streamlit experts.

---

## Streamlit API cheat sheet - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/quick-reference/cheat-sheet

**Contents:**
- Streamlit API cheat sheet
    - Install & Import
    - Pre-release features
    - Command line
    - Magic commands
    - Display text
    - Display data
    - Display media
    - Display charts
    - Add elements to sidebar

This is a summary of the docs for the latest version of Streamlit, v1.50.0.

Learn more about experimental features

To use Bokeh, see our custom component streamlit-bokeh.

Learn how to Build a basic LLM chat app

Our forums are full of helpful information and Streamlit experts.

---

## Media elements - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/media

**Contents:**
- Media elements
    - Image
    - Logo
    - PDF
    - Audio
    - Video
    - Streamlit Cropper
    - Image Coordinates
    - Streamlit Lottie
    - Streamlit Webrtc

It's easy to embed images, videos, and audio files directly into your Streamlit apps.

Display an image or list of images.

Display a logo in the upper-left corner of your app and its sidebar.

Display an audio player.

Display a video player.

Third-party components

These are featured components created by our lovely community. For more examples and inspiration, check out our Components Gallery and Streamlit Extras!

A simple image cropper for Streamlit. Created by @turner-anderson.

Get the coordinates of clicks on an image. Created by @blackary.

Integrate Lottie animations inside your Streamlit app. Created by @andfanilo.

Handling and transmitting real-time video/audio streams with Streamlit. Created by @whitphx.

Provides a sketching canvas using Fabric.js. Created by @andfanilo.

Compare images with a slider using JuxtaposeJS. Created by @fcakyon.

A simple image cropper for Streamlit. Created by @turner-anderson.

Get the coordinates of clicks on an image. Created by @blackary.

Integrate Lottie animations inside your Streamlit app. Created by @andfanilo.

Handling and transmitting real-time video/audio streams with Streamlit. Created by @whitphx.

Provides a sketching canvas using Fabric.js. Created by @andfanilo.

Compare images with a slider using JuxtaposeJS. Created by @fcakyon.

A simple image cropper for Streamlit. Created by @turner-anderson.

Get the coordinates of clicks on an image. Created by @blackary.

Integrate Lottie animations inside your Streamlit app. Created by @andfanilo.

Our forums are full of helpful information and Streamlit experts.

---

## Execution flow - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/execution-flow

**Contents:**
- Execution flow
- Change execution
    - Modal dialog
    - Fragments
    - Rerun script
    - Stop execution
- Group multiple widgets
    - Forms
    - Form submit button
    - Autorefresh

By default, Streamlit apps execute the script entirely, but we allow some functionality to handle control flow in your applications.

Insert a modal dialog that can rerun independently from the rest of the script.

Define a fragment to rerun independently from the rest of the script.

Rerun the script immediately.

Stops execution immediately.

By default, Streamlit reruns your script everytime a user interacts with your app. However, sometimes it's a better user experience to wait until a group of related widgets is filled before actually rerunning the script. That's what st.form is for!

Create a form that batches elements together with a “Submit" button.

Display a form submit button.

Third-party components

These are featured components created by our lovely community. For more examples and inspiration, check out our Components Gallery and Streamlit Extras!

Force a refresh without tying up a script. Created by @kmcgrady.

Auto-generate Streamlit UI from Pydantic Models and Dataclasses. Created by @lukasmasuch.

An experimental version of Streamlit Multi-Page Apps. Created by @blackary.

Our forums are full of helpful information and Streamlit experts.

---

## st.column_config.AreaChartColumn - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.areachartcolumn

**Contents:**
- st.column_config.AreaChartColumn
    - Examples
  - Still have questions?

Configure an area chart column in st.dataframe or st.data_editor.

Cells need to contain a list of numbers. Chart columns are not editable at the moment. This command needs to be used in the column_config parameter of st.dataframe or st.data_editor.

st.column_config.AreaChartColumn(label=None, *, width=None, help=None, pinned=None, y_min=None, y_max=None, color=None)

The label shown at the top of the column. If this is None (default), the column name is used.

width ("small", "medium", "large", int, or None)

The display width of the column. If this is None (default), the column will be sized to fit the cell contents. Otherwise, this can be one of the following:

If the total width of all columns is less than the width of the dataframe, the remaining space will be distributed evenly among all columns.

A tooltip that gets displayed when hovering over the column label. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

pinned (bool or None)

Whether the column is pinned. A pinned column will stay visible on the left side no matter where the user scrolls. If this is None (default), Streamlit will decide: index columns are pinned, and data columns are not pinned.

y_min (int, float, or None)

The minimum value on the y-axis for all cells in the column. If this is None (default), every cell will use the minimum of its data.

y_max (int, float, or None)

The maximum value on the y-axis for all cells in the column. If this is None (default), every cell will use the maximum of its data.

color ("auto", "auto-inverse", str, or None)

The color to use for the chart. This can be one of the following:

The basic color palette can be configured in the theme settings.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "sales": [
            [0, 4, 26, 80, 100, 40],
            [80, 20, 80, 35, 40, 100],
            [10, 20, 80, 80, 70, 0],
            [10, 100, 20, 100, 30, 100],
        ],
    }
)

st.data_editor(
    data_df,
    column_config={
        "sales": st.column_config.AreaChartColumn(
            "Sales (last 6 months)",
            width="medium",
            help="The sales volume in the last 6 months",
            y_min=0,
            y_max=100,
         ),
    },
    hide_index=True,
)
```

---

## st.context - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/caching-and-state/st.context

**Contents:**
- st.context
- context.cookies
    - Examples
- context.headers
    - Examples
- context.ip_address
    - Example
- context.is_embedded
    - Example
- context.locale

An interface to access user session context.

st.context provides a read-only interface to access headers and cookies for the current user session.

Each property (st.context.headers and st.context.cookies) returns a dictionary of named values.

A read-only, dict-like object containing cookies sent in the initial request.

A read-only, dict-like object containing headers sent in the initial request.

The read-only IP address of the user's connection.

Whether the app is embedded.

The read-only locale of the user's browser.

A read-only, dictionary-like object containing theme information.

The read-only timezone of the user's browser.

The read-only timezone offset of the user's browser.

The read-only URL of the app in the user's browser.

A read-only, dict-like object containing cookies sent in the initial request.

Example 1: Access all available cookies

Show a dictionary of cookies:

Example 2: Access a specific cookie

Show the value of a specific cookie:

A read-only, dict-like object containing headers sent in the initial request.

Keys are case-insensitive and may be repeated. When keys are repeated, dict-like methods will only return the last instance of each key. Use .get_all(key="your_repeated_key") to see all values if the same header is set multiple times.

Example 1: Access all available headers

Show a dictionary of headers (with only the last instance of any repeated key):

Example 2: Access a specific header

Show the value of a specific header (or the last instance if it's repeated):

Show of list of all headers for a given key:

The read-only IP address of the user's connection.

This should not be used for security measures because it can easily be spoofed. When a user accesses the app through localhost, the IP address is None. Otherwise, the IP address is determined from the remote_ip attribute of the Tornado request object and may be an IPv4 or IPv6 address.

Check if the user has an IPv4 or IPv6 address:

Whether the app is embedded.

This property returns a boolean value indicating whether the app is running in an embedded context. This is determined by the presence of embed=true as a query parameter in the URL. This is the only way to determine if the app is currently configured for embedding because embedding settings are not accessible through st.query_params or st.context.url.

Conditionally show content when the app is running in an embedded context:

The read-only locale of the user's browser.

st.context.locale returns the 

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.context.cookies
```

Example 2 (unknown):
```unknown
import streamlit as st

st.context.cookies["_ga"]
```

Example 3 (unknown):
```unknown
import streamlit as st

st.context.headers
```

Example 4 (unknown):
```unknown
import streamlit as st

st.context.headers["host"]
```

---

## st.slider - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.slider

**Contents:**
- st.slider
    - Examples
  - Featured videos
  - Still have questions?

Display a slider widget.

This supports int, float, date, time, and datetime types.

This also allows you to render a range slider by passing a two-element tuple or list as the value.

The difference between st.slider and st.select_slider is that slider only accepts numerical or date/time data and takes a range as input, while select_slider accepts any datatype and takes an iterable set of options.

Integer values exceeding +/- (1<<53) - 1 cannot be accurately stored or returned by the widget due to serialization constraints between the Python server and JavaScript client. You must handle such numbers as floats, leading to a loss in precision.

st.slider(label, min_value=None, max_value=None, value=None, step=None, format=None, key=None, help=None, on_change=None, args=None, kwargs=None, *, disabled=False, label_visibility="visible", width="stretch")

A short label explaining to the user what this slider is for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

For accessibility reasons, you should never set an empty label, but you can hide it with label_visibility if needed. In the future, we may disallow empty labels by raising an exception.

min_value (a supported type or None)

The minimum permitted value. If this is None (default), the minimum value depends on the type as follows:

max_value (a supported type or None)

The maximum permitted value. If this is None (default), the maximum value depends on the type as follows:

value (a supported type or a tuple/list of supported types or None)

The value of the slider when it first renders. If a tuple/list of two values is passed here, then a range slider with those lower and upper bounds is rendered. For example, if set to (1, 10) the slider will have a selectable range between 1 and 10. This defaults to min_value. If the type is not otherwise specified in any of the numeric parameters, the widget will have an integer value.

step (int, float, timedelta, or None)

The stepping interval. Defaults to 1 if the value is an int, 0.01 if a float, timedelta(days

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

age = st.slider("How old are you?", 0, 130, 25)
st.write("I'm ", age, "years old")
```

Example 2 (unknown):
```unknown
import streamlit as st

values = st.slider("Select a range of values", 0.0, 100.0, (25.0, 75.0))
st.write("Values:", values)
```

Example 3 (python):
```python
import streamlit as st
from datetime import time

appointment = st.slider(
    "Schedule your appointment:", value=(time(11, 30), time(12, 45))
)
st.write("You're scheduled for:", appointment)
```

Example 4 (python):
```python
import streamlit as st
from datetime import datetime

start_time = st.slider(
    "When do you start?",
    value=datetime(2020, 1, 1, 9, 30),
    format="MM/DD/YY - hh:mm",
)
st.write("Start time:", start_time)
```

---

## st.audio - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/media/st.audio

**Contents:**
- st.audio
    - Examples
  - Still have questions?

Display an audio player.

st.audio(data, format="audio/wav", start_time=0, *, sample_rate=None, end_time=None, loop=False, autoplay=False, width="stretch")

data (str, Path, bytes, BytesIO, numpy.ndarray, or file)

The audio to play. This can be one of the following:

If data is a NumPy array, it must either be a 1D array of the waveform or a 2D array of shape (C, S) where C is the number of channels and S is the number of samples. See the default channel order at http://msdn.microsoft.com/en-us/library/windows/hardware/dn653308(v=vs.85).aspx

The MIME type for the audio file. This defaults to "audio/wav". For more information about MIME types, see https://www.iana.org/assignments/media-types/media-types.xhtml.

start_time (int, float, timedelta, str, or None)

The time from which the element should start playing. This can be one of the following:

sample_rate (int or None)

The sample rate of the audio data in samples per second. This is only required if data is a NumPy array.

end_time (int, float, timedelta, str, or None)

The time at which the element should stop playing. This can be one of the following:

Whether the audio should loop playback.

Whether the audio file should start playing automatically. This is False by default. Browsers will not autoplay audio files if the user has not interacted with the page by clicking somewhere.

width ("stretch" or int)

The width of the audio player element. This can be one of the following:

To display an audio player for a local file, specify the file's string path and format.

You can also pass bytes or numpy.ndarray objects to st.audio.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.audio("cat-purr.mp3", format="audio/mpeg", loop=True)
```

Example 2 (unknown):
```unknown
import streamlit as st
import numpy as np

audio_file = open("myaudio.ogg", "rb")
audio_bytes = audio_file.read()

st.audio(audio_bytes, format="audio/ogg")

sample_rate = 44100  # 44100 samples per second
seconds = 2  # Note duration of 2 seconds
frequency_la = 440  # Our played note will be 440 Hz
# Generate array with seconds*sample_rate steps, ranging between 0 and seconds
t = np.linspace(0, seconds, seconds * sample_rate, False)
# Generate a 440 Hz sine wave
note_la = np.sin(frequency_la * t * 2 * np.pi)

st.audio(note_la, sample_rate=sample_rate)
```

---

## st.set_option - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/configuration/st.set_option

**Contents:**
- st.set_option
    - Example
  - Still have questions?

Set a configuration option.

Currently, only client configuration options can be set within the script itself:

Calling st.set_option with any other option will raise a StreamlitAPIException. When changing a configuration option in a running app, you may need to trigger a rerun after changing the option to see the effects.

Run streamlit config show in a terminal to see all available options.

st.set_option(key, value)

The config option key of the form "section.optionName". To see all available options, run streamlit config show in a terminal.

The new value to assign to this config option.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.set_option("client.showErrorDetails", True)
```

---

## st.components.v1.html - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/custom-components/st.components.v1.html

**Contents:**
- st.components.v1.html
    - Example
  - Still have questions?

Display an HTML string in an iframe.

To use this function, import it from the streamlit.components.v1 module.

If you want to insert HTML text into your app without an iframe, try st.html instead.

Using st.components.v1.html directly (instead of importing its module) is deprecated and will be disallowed in a later version.

st.components.v1.html(html, width=None, height=None, scrolling=False, *, tab_index=None)

The HTML string to embed in the iframe.

The width of the iframe in CSS pixels. By default, this is the app's default element width.

The height of the frame in CSS pixels. By default, this is 150.

Whether to allow scrolling in the iframe. If this False (default), Streamlit crops any content larger than the iframe and does not show a scrollbar. If this is True, Streamlit shows a scrollbar when the content is larger than the iframe.

tab_index (int or None)

Specifies how and if the iframe is sequentially focusable. Users typically use the Tab key for sequential focus navigation.

This can be one of the following values:

For more information, see the tabindex documentation on MDN.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit.components.v1 as components

components.html(
    "<p><span style='text-decoration: line-through double red;'>Oops</span>!</p>"
)
```

---

## st.selectbox - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.selectbox

**Contents:**
- st.selectbox
    - Examples
  - Still have questions?

Display a select widget.

st.selectbox(label, options, index=0, format_func=special_internal_function, key=None, help=None, on_change=None, args=None, kwargs=None, *, placeholder=None, disabled=False, label_visibility="visible", accept_new_options=False, width="stretch")

A short label explaining to the user what this select widget is for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

For accessibility reasons, you should never set an empty label, but you can hide it with label_visibility if needed. In the future, we may disallow empty labels by raising an exception.

Labels for the select options in an Iterable. This can be a list, set, or anything supported by st.dataframe. If options is dataframe-like, the first column will be used. Each label will be cast to str internally by default.

The index of the preselected option on first render. If None, will initialize empty and return None until the user selects an option. Defaults to 0 (the first option).

format_func (function)

Function to modify the display of the options. It receives the raw option as an argument and should output the label to be shown for that option. This has no impact on the return value of the command.

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

A tooltip that gets displayed next to the widget label. Streamlit only displays the tooltip when label_visibility="visible". If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

An optional callback invoked when this selectbox's value changes.

An optional list or tuple of args to pass to the callback.

An optional dict of kwargs to pass to the callback.

placeholder (str or None)

A string to display when no options are selected. If this is None (default), the widget displays placeholder text based on 

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

option = st.selectbox(
    "How would you like to be contacted?",
    ("Email", "Home phone", "Mobile phone"),
)

st.write("You selected:", option)
```

Example 2 (unknown):
```unknown
import streamlit as st

option = st.selectbox(
    "How would you like to be contacted?",
    ("Email", "Home phone", "Mobile phone"),
    index=None,
    placeholder="Select contact method...",
)

st.write("You selected:", option)
```

Example 3 (unknown):
```unknown
import streamlit as st

option = st.selectbox(
    "Default email",
    ["foo@example.com", "bar@example.com", "baz@example.com"],
    index=None,
    placeholder="Select a saved email or enter a new one",
    accept_new_options=True,
)

st.write("You selected:", option)
```

---

## st.components.v1.iframe - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/custom-components/st.components.v1.iframe

**Contents:**
- st.components.v1.iframe
    - Example
  - Still have questions?

Load a remote URL in an iframe.

To use this function, import it from the streamlit.components.v1 module.

Using st.components.v1.iframe directly (instead of importing its module) is deprecated and will be disallowed in a later version.

st.components.v1.iframe(src, width=None, height=None, scrolling=False, *, tab_index=None)

The URL of the page to embed.

The width of the iframe in CSS pixels. By default, this is the app's default element width.

The height of the frame in CSS pixels. By default, this is 150.

Whether to allow scrolling in the iframe. If this False (default), Streamlit crops any content larger than the iframe and does not show a scrollbar. If this is True, Streamlit shows a scrollbar when the content is larger than the iframe.

tab_index (int or None)

Specifies how and if the iframe is sequentially focusable. Users typically use the Tab key for sequential focus navigation.

This can be one of the following values:

For more information, see the tabindex documentation on MDN.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit.components.v1 as components

components.iframe("https://example.com", height=500)
```

---

## st.toggle - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.toggle

**Contents:**
- st.toggle
    - Example
  - Still have questions?

Display a toggle widget.

st.toggle(label, value=False, key=None, help=None, on_change=None, args=None, kwargs=None, *, disabled=False, label_visibility="visible", width="content")

A short label explaining to the user what this toggle is for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

For accessibility reasons, you should never set an empty label, but you can hide it with label_visibility if needed. In the future, we may disallow empty labels by raising an exception.

Preselect the toggle when it first renders. This will be cast to bool internally.

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

A tooltip that gets displayed next to the widget label. Streamlit only displays the tooltip when label_visibility="visible". If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

An optional callback invoked when this toggle's value changes.

An optional list or tuple of args to pass to the callback.

An optional dict of kwargs to pass to the callback.

An optional boolean that disables the toggle if set to True. The default is False.

label_visibility ("visible", "hidden", or "collapsed")

The visibility of the label. The default is "visible". If this is "hidden", Streamlit displays an empty spacer instead of the label, which can help keep the widget aligned with other widgets. If this is "collapsed", Streamlit displays no label or spacer.

width ("content", "stretch", or int)

The width of the toggle widget. This can be one of the following:

Whether or not the toggle is checked.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

on = st.toggle("Activate feature")

if on:
    st.write("Feature activated!")
```

---

## st.balloons - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/status/st.balloons

**Contents:**
- st.balloons
    - Example
  - Still have questions?

Draw celebratory balloons.

...then watch your app and get ready for a celebration!

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.balloons()
```

---

## st.snow - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/status/st.snow

**Contents:**
- st.snow
    - Example
  - Still have questions?

Draw celebratory snowfall.

...then watch your app and get ready for a cool celebration!

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.snow()
```

---

## st.navigation - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/navigation/st.navigation

**Contents:**
- st.navigation
    - Examples
  - Still have questions?

Configure the available pages in a multipage app.

Call st.navigation in your entrypoint file to define the available pages for your app. st.navigation returns the current page, which can be executed using .run() method.

When using st.navigation, your entrypoint file (the file passed to streamlit run) acts like a router or frame of common elements around each of your pages. Streamlit executes the entrypoint file with every app rerun. To execute the current page, you must call the .run() method on the StreamlitPage object returned by st.navigation.

The set of available pages can be updated with each rerun for dynamic navigation. By default, st.navigation displays the available pages in the sidebar if there is more than one page. This behavior can be changed using the position keyword argument.

As soon as any session of your app executes the st.navigation command, your app will ignore the pages/ directory (across all sessions).

st.navigation(pages, *, position="sidebar", expanded=False)

pages (Sequence[page-like], Mapping[str, Sequence[page-like]])

The available pages for the app.

To create a navigation menu with no sections or page groupings, pages must be a list of page-like objects. Page-like objects are anything that can be passed to st.Page or a StreamlitPage object returned by st.Page.

To create labeled sections or page groupings within the navigation menu, pages must be a dictionary. Each key is the label of a section and each value is the list of page-like objects for that section. If you use position="top", each grouping will be a collapsible item in the navigation menu. For top navigation, if you use an empty string as a section header, the pages in that section will be displayed at the beginning of the menu before the collapsible sections.

When you use a string or path as a page-like object, they are internally passed to st.Page and converted to StreamlitPage objects. In this case, the page will have the default title, icon, and path inferred from its path or filename. To customize these attributes for your page, initialize your page with st.Page.

position ("sidebar", "top", or "hidden")

The position of the navigation menu. If this is "sidebar" (default), the navigation widget appears at the top of the sidebar. If this is "top", the navigation appears in the top header of the app. If this is "hidden", the navigation widget is not displayed.

If there is only one page in pages, the navigation will be hidden for any value of position.

Wh

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.title("Page 1")
```

Example 2 (python):
```python
import streamlit as st

def page_2():
    st.title("Page 2")

pg = st.navigation(["page_1.py", page_2])
pg.run()
```

Example 3 (unknown):
```unknown
your_repository/
├── create_account.py
├── learn.py
├── manage_account.py
├── streamlit_app.py
└── trial.py
```

Example 4 (unknown):
```unknown
import streamlit as st

pages = {
    "Your account": [
        st.Page("create_account.py", title="Create your account"),
        st.Page("manage_account.py", title="Manage your account"),
    ],
    "Resources": [
        st.Page("learn.py", title="Learn about us"),
        st.Page("trial.py", title="Try it out"),
    ],
}

pg = st.navigation(pages)
pg.run()
```

---

## st.radio - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.radio

**Contents:**
- st.radio
    - Example
  - Featured videos
  - Still have questions?

Display a radio button widget.

st.radio(label, options, index=0, format_func=special_internal_function, key=None, help=None, on_change=None, args=None, kwargs=None, *, disabled=False, horizontal=False, captions=None, label_visibility="visible", width="content")

A short label explaining to the user what this radio group is for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

For accessibility reasons, you should never set an empty label, but you can hide it with label_visibility if needed. In the future, we may disallow empty labels by raising an exception.

Labels for the select options in an Iterable. This can be a list, set, or anything supported by st.dataframe. If options is dataframe-like, the first column will be used. Each label will be cast to str internally by default.

Labels can include markdown as described in the label parameter and will be cast to str internally by default.

The index of the preselected option on first render. If None, will initialize empty and return None until the user selects an option. Defaults to 0 (the first option).

format_func (function)

Function to modify the display of radio options. It receives the raw option as an argument and should output the label to be shown for that option. This has no impact on the return value of the radio.

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

A tooltip that gets displayed next to the widget label. Streamlit only displays the tooltip when label_visibility="visible". If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

An optional callback invoked when this radio's value changes.

An optional list or tuple of args to pass to the callback.

An optional dict of kwargs to pass to the callback.

An optional boolean that disables the radio button if

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

genre = st.radio(
    "What's your favorite movie genre",
    [":rainbow[Comedy]", "***Drama***", "Documentary :movie_camera:"],
    captions=[
        "Laugh out loud.",
        "Get the popcorn.",
        "Never stop learning.",
    ],
)

if genre == ":rainbow[Comedy]":
    st.write("You selected comedy.")
else:
    st.write("You didn't select comedy.")
```

Example 2 (unknown):
```unknown
import streamlit as st

genre = st.radio(
    "What's your favorite movie genre",
    [":rainbow[Comedy]", "***Drama***", "Documentary :movie_camera:"],
    index=None,
)

st.write("You selected:", genre)
```

---

## st.exception - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/status/st.exception

**Contents:**
- st.exception
    - Example
  - Still have questions?

Display an exception.

When accessing the app through localhost, in the lower-right corner of the exception, Streamlit displays links to Google and ChatGPT that are prefilled with the contents of the exception message.

st.exception(exception, width="stretch")

exception (Exception)

The exception to display.

width ("stretch" or int)

The width of the exception element. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

e = RuntimeError("This is an exception of type RuntimeError")
st.exception(e)
```

---

## st.fragment - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment

**Contents:**
- st.fragment
    - Examples
  - Still have questions?

Decorator to turn a function into a fragment which can rerun independently of the full app.

When a user interacts with an input widget created inside a fragment, Streamlit only reruns the fragment instead of the full app. If run_every is set, Streamlit will also rerun the fragment at the specified interval while the session is active, even if the user is not interacting with your app.

To trigger an app rerun from inside a fragment, call st.rerun() directly. To trigger a fragment rerun from within itself, call st.rerun(scope="fragment"). Any values from the fragment that need to be accessed from the wider app should generally be stored in Session State.

When Streamlit element commands are called directly in a fragment, the elements are cleared and redrawn on each fragment rerun, just like all elements are redrawn on each app rerun. The rest of the app is persisted during a fragment rerun. When a fragment renders elements into externally created containers, the elements will not be cleared with each fragment rerun. Instead, elements will accumulate in those containers with each fragment rerun, until the next app rerun.

Calling st.sidebar in a fragment is not supported. To write elements to the sidebar with a fragment, call your fragment function inside a with st.sidebar context manager.

Fragment code can interact with Session State, imported modules, and other Streamlit elements created outside the fragment. Note that these interactions are additive across multiple fragment reruns. You are responsible for handling any side effects of that behavior.

st.fragment(func=None, *, run_every=None)

The function to turn into a fragment.

run_every (int, float, timedelta, str, or None)

The time interval between automatic fragment reruns. This can be one of the following:

If run_every is None, the fragment will only rerun from user-triggered events.

The following example demonstrates basic usage of @st.fragment. As an analogy, "inflating balloons" is a slow process that happens outside of the fragment. "Releasing balloons" is a quick process that happens inside of the fragment.

This next example demonstrates how elements both inside and outside of a fragement update with each app or fragment rerun. In this app, clicking "Rerun full app" will increment both counters and update all values displayed in the app. In contrast, clicking "Rerun fragment" will only increment the counter within the fragment. In this case, the st.write command inside the fragment will u

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import streamlit as st
import time

@st.fragment
def release_the_balloons():
    st.button("Release the balloons", help="Fragment rerun")
    st.balloons()

with st.spinner("Inflating balloons..."):
    time.sleep(5)
release_the_balloons()
st.button("Inflate more balloons", help="Full rerun")
```

Example 2 (python):
```python
import streamlit as st

if "app_runs" not in st.session_state:
    st.session_state.app_runs = 0
    st.session_state.fragment_runs = 0

@st.fragment
def my_fragment():
    st.session_state.fragment_runs += 1
    st.button("Rerun fragment")
    st.write(f"Fragment says it ran {st.session_state.fragment_runs} times.")

st.session_state.app_runs += 1
my_fragment()
st.button("Rerun full app")
st.write(f"Full app says it ran {st.session_state.app_runs} times.")
st.write(f"Full app sees that fragment ran {st.session_state.fragment_runs} times.")
```

Example 3 (python):
```python
import streamlit as st

if "clicks" not in st.session_state:
    st.session_state.clicks = 0

@st.fragment
def count_to_five():
    if st.button("Plus one!"):
        st.session_state.clicks += 1
        if st.session_state.clicks % 5 == 0:
            st.rerun()
    return

count_to_five()
st.header(f"Multiples of five clicks: {st.session_state.clicks // 5}")

if st.button("Check click count"):
    st.toast(f"## Total clicks: {st.session_state.clicks}")
```

---

## st.spinner - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/status/st.spinner

**Contents:**
- st.spinner
    - Example
  - Still have questions?

Display a loading spinner while executing a block of code.

st.spinner(text="In progress...", *, show_time=False, width="content")

The text to display next to the spinner. This defaults to "In progress...".

The text can optionally contain GitHub-flavored Markdown. Syntax information can be found at: https://github.github.com/gfm.

See the body parameter of st.markdown for additional, supported Markdown directives.

Whether to show the elapsed time next to the spinner text. If this is False (default), no time is displayed. If this is True, elapsed time is displayed with a precision of 0.1 seconds. The time format is not configurable.

width ("content", "stretch", or int)

The width of the spinner element. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st
import time

with st.spinner("Wait for it...", show_time=True):
    time.sleep(5)
st.success("Done!")
st.button("Rerun")
```

---

## st.column_config.ImageColumn - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.imagecolumn

**Contents:**
- st.column_config.ImageColumn
    - Examples
  - Still have questions?

Configure an image column in st.dataframe or st.data_editor.

The cell values need to be one of:

Image columns are not editable at the moment. This command needs to be used in the column_config parameter of st.dataframe or st.data_editor.

st.column_config.ImageColumn(label=None, *, width=None, help=None, pinned=None)

The label shown at the top of the column. If this is None (default), the column name is used.

width ("small", "medium", "large", int, or None)

The display width of the column. If this is None (default), the column will be sized to fit the cell contents. Otherwise, this can be one of the following:

If the total width of all columns is less than the width of the dataframe, the remaining space will be distributed evenly among all columns.

A tooltip that gets displayed when hovering over the column label. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

pinned (bool or None)

Whether the column is pinned. A pinned column will stay visible on the left side no matter where the user scrolls. If this is None (default), Streamlit will decide: index columns are pinned, and data columns are not pinned.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "apps": [
            "https://storage.googleapis.com/s4a-prod-share-preview/default/st_app_screenshot_image/5435b8cb-6c6c-490b-9608-799b543655d3/Home_Page.png",
            "https://storage.googleapis.com/s4a-prod-share-preview/default/st_app_screenshot_image/ef9a7627-13f2-47e5-8f65-3f69bb38a5c2/Home_Page.png",
            "https://storage.googleapis.com/s4a-prod-share-preview/default/st_app_screenshot_image/31b99099-8eae-4ff8-aa89-042895ed3843/Home_Page.png",
            "https://storage.googleapis.com/s4a-prod
...
```

---

## streamlit help - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/cli/help

**Contents:**
- $ streamlit help
  - Syntax
  - Still have questions?

Print the available commands for the Streamlit CLI tool. This command is equivalent to executing streamlit --help.

Our forums are full of helpful information and Streamlit experts.

---

## Command-line options - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/cli

**Contents:**
- Command-line interface
- Available commands
  - Run your app
  - Still have questions?

When you install Streamlit, a command-line (CLI) tool gets installed as well. The purpose of this tool is to run Streamlit apps, change Streamlit configuration options, and help you diagnose and fix issues.

The most important command is streamlit run, which is summarized for convenience here:

At any time, in your terminal, you can stop the server with Ctrl+C.

Our forums are full of helpful information and Streamlit experts.

---

## st.bar_chart - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/charts/st.bar_chart?utm_source=streamlit

**Contents:**
- st.bar_chart
    - Examples
- element.add_rows
    - Example
  - Still have questions?

This is syntax-sugar around st.altair_chart. The main difference is this command uses the data's own column and indices to figure out the chart's Altair spec. As a result this is easier to use for many "just plot this" scenarios, while being less customizable.

st.bar_chart(data=None, *, x=None, y=None, x_label=None, y_label=None, color=None, horizontal=False, sort=True, stack=None, width=None, height=None, use_container_width=True)

data (Anything supported by st.dataframe)

Column name or key associated to the x-axis data. If x is None (default), Streamlit uses the data index for the x-axis values.

y (str, Sequence of str, or None)

Column name(s) or key(s) associated to the y-axis data. If this is None (default), Streamlit draws the data of all remaining columns as data series. If this is a Sequence of strings, Streamlit draws several series on the same chart by melting your wide-format table into a long-format table behind the scenes.

x_label (str or None)

The label for the x-axis. If this is None (default), Streamlit will use the column name specified in x if available, or else no label will be displayed.

y_label (str or None)

The label for the y-axis. If this is None (default), Streamlit will use the column name(s) specified in y if available, or else no label will be displayed.

color (str, tuple, Sequence of str, Sequence of tuple, or None)

The color to use for different series in this chart.

For a bar chart with just one series, this can be:

For a bar chart with multiple series, where the dataframe is in long format (that is, y is None or just one column), this can be:

None, to use the default colors.

The name of a column in the dataset. Data points will be grouped into series of the same color based on the value of this column. In addition, if the values in this column match one of the color formats above (hex string or color tuple), then that color will be used.

For example: if the dataset has 1000 rows, but this column only contains the values "adult", "child", and "baby", then those 1000 datapoints will be grouped into three series whose colors will be automatically selected from the default palette.

But, if for the same 1000-row dataset, this column contained the values "#ffaa00", "#f0f", "#0000ff", then then those 1000 datapoints would still be grouped into 3 series, but their colors would be "#ffaa00", "#f0f", "#0000ff" this time around.

For a bar chart with multiple series, where the dataframe is in wide format (that is, y is 

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(rng(0).standard_normal((20, 3)), columns=["a", "b", "c"])

st.bar_chart(df)
```

Example 2 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(
    {
        "col1": list(range(20)) * 3,
        "col2": rng(0).standard_normal(60),
        "col3": ["a"] * 20 + ["b"] * 20 + ["c"] * 20,
    }
)

st.bar_chart(df, x="col1", y="col2", color="col3")
```

Example 3 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(
    {
        "col1": list(range(20)),
        "col2": rng(0).standard_normal(20),
        "col3": rng(1).standard_normal(20),
    }
)

st.bar_chart(
    df,
    x="col1",
    y=["col2", "col3"],
    color=["#FF0000", "#0000FF"],
)
```

Example 4 (python):
```python
import streamlit as st
from vega_datasets import data

source = data.barley()

st.bar_chart(source, x="variety", y="yield", color="site", horizontal=True)
```

---

## st.graphviz_chart - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/charts/st.graphviz_chart

**Contents:**
- st.graphviz_chart
    - Example
  - Still have questions?

Display a graph using the dagre-d3 library.

You must install graphviz>=0.19.0 to use this command. You can install all charting dependencies (except Bokeh) as an extra with Streamlit:

st.graphviz_chart(figure_or_dot, use_container_width=None, *, width="content", height="content")

figure_or_dot (graphviz.dot.Graph, graphviz.dot.Digraph, graphviz.sources.Source, str)

The Graphlib graph object or dot string to display

use_container_width (bool)

use_container_width is deprecated and will be removed in a future release. For use_container_width=True, use width="stretch". For use_container_width=False, use width="content".

Whether to override the figure's native width with the width of the parent container. If use_container_width is False (default), Streamlit sets the width of the chart to fit its contents according to the plotting library, up to the width of the parent container. If use_container_width is True, Streamlit sets the width of the figure to match the width of the parent container.

width ("content", "stretch", or int)

The width of the chart element. This can be one of the following:

height ("content", "stretch", or int)

The height of the chart element. This can be one of the following:

Or you can render the chart from the graph using GraphViz's Dot language:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
pip install streamlit[charts]
```

Example 2 (unknown):
```unknown
import streamlit as st
import graphviz

# Create a graphlib graph object
graph = graphviz.Digraph()
graph.edge("run", "intr")
graph.edge("intr", "runbl")
graph.edge("runbl", "run")
graph.edge("run", "kernel")
graph.edge("kernel", "zombie")
graph.edge("kernel", "sleep")
graph.edge("kernel", "runmem")
graph.edge("sleep", "swap")
graph.edge("swap", "runswap")
graph.edge("runswap", "new")
graph.edge("runswap", "runmem")
graph.edge("new", "runmem")
graph.edge("sleep", "runmem")

st.graphviz_chart(graph)
```

Example 3 (unknown):
```unknown
st.graphviz_chart('''
    digraph {
        run -> intr
        intr -> runbl
        runbl -> run
        run -> kernel
        kernel -> zombie
        kernel -> sleep
        kernel -> runmem
        sleep -> swap
        swap -> runswap
        runswap -> new
        runswap -> runmem
        new -> runmem
        sleep -> runmem
    }
''')
```

---

## Layouts and Containers - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/layout

**Contents:**
- Layouts and Containers
- Complex layouts
    - Columns
    - Container
    - Modal dialog
    - Empty
    - Expander
    - Popover
    - Sidebar
    - Tabs

Streamlit provides several options for controlling how different elements are laid out on the screen.

Insert containers laid out as side-by-side columns.

Insert a multi-element container.

Insert a modal dialog that can rerun independently from the rest of the script.

Insert a single-element container.

Insert a multi-element container that can be expanded/collapsed.

Insert a multi-element popover container that can be opened/closed.

Display items in a sidebar.

Insert containers separated into tabs.

Third-party components

These are featured components created by our lovely community. For more examples and inspiration, check out our Components Gallery and Streamlit Extras!

Create a draggable and resizable dashboard in Streamlit. Created by @okls.

Auto-generate Streamlit UI from Pydantic Models and Dataclasses. Created by @lukasmasuch.

An experimental version of Streamlit Multi-Page Apps. Created by @blackary.

Our forums are full of helpful information and Streamlit experts.

---

## st.video - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/media/st.video

**Contents:**
- st.video
    - Example
  - Still have questions?

Display a video player.

st.video(data, format="video/mp4", start_time=0, *, subtitles=None, end_time=None, loop=False, autoplay=False, muted=False, width="stretch")

data (str, Path, bytes, io.BytesIO, numpy.ndarray, or file)

The video to play. This can be one of the following:

The MIME type for the video file. This defaults to "video/mp4". For more information about MIME types, see https://www.iana.org/assignments/media-types/media-types.xhtml.

start_time (int, float, timedelta, str, or None)

The time from which the element should start playing. This can be one of the following:

subtitles (str, bytes, Path, io.BytesIO, or dict)

Optional subtitle data for the video, supporting several input types:

When provided, subtitles are displayed by default. For multiple tracks, the first one is displayed by default. If you don't want any subtitles displayed by default, use an empty string for the value in a dictrionary's first pair: {"None": "", "English": "path/to/english.vtt"}

Not supported for YouTube videos.

end_time (int, float, timedelta, str, or None)

The time at which the element should stop playing. This can be one of the following:

Whether the video should loop playback.

Whether the video should start playing automatically. This is False by default. Browsers will not autoplay unmuted videos if the user has not interacted with the page by clicking somewhere. To enable autoplay without user interaction, you must also set muted=True.

Whether the video should play with the audio silenced. This is False by default. Use this in conjunction with autoplay=True to enable autoplay without user interaction.

width ("stretch" or int)

The width of the video player element. This can be one of the following:

When you include subtitles, they will be turned on by default. A viewer can turn off the subtitles (or captions) from the browser's default video control menu, usually located in the lower-right corner of the video.

Here is a simple VTT file (subtitles.vtt):

If the above VTT file lives in the same directory as your app, you can add subtitles like so:

See additional examples of supported subtitle input types in our video subtitles feature demo.

Some videos may not display if they are encoded using MP4V (which is an export option in OpenCV), as this codec is not widely supported by browsers. Converting your video to H.264 will allow the video to be displayed in Streamlit. See this StackOverflow post or this Streamlit forum post for more information.

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

video_file = open("myvideo.mp4", "rb")
video_bytes = video_file.read()

st.video(video_bytes)
```

Example 2 (unknown):
```unknown
WEBVTT

0:00:01.000 --> 0:00:02.000
Look!

0:00:03.000 --> 0:00:05.000
Look at the pretty stars!
```

Example 3 (unknown):
```unknown
import streamlit as st

VIDEO_URL = "https://example.com/not-youtube.mp4"
st.video(VIDEO_URL, subtitles="subtitles.vtt")
```

---

## st.column_config.NumberColumn - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.numbercolumn

**Contents:**
- st.column_config.NumberColumn
    - Examples
  - Still have questions?

Configure a number column in st.dataframe or st.data_editor.

This is the default column type for integer and float values. This command needs to be used in the column_config parameter of st.dataframe or st.data_editor. When used with st.data_editor, editing will be enabled with a numeric input widget.

st.column_config.NumberColumn(label=None, *, width=None, help=None, disabled=None, required=None, pinned=None, default=None, format=None, min_value=None, max_value=None, step=None)

The label shown at the top of the column. If this is None (default), the column name is used.

width ("small", "medium", "large", int, or None)

The display width of the column. If this is None (default), the column will be sized to fit the cell contents. Otherwise, this can be one of the following:

If the total width of all columns is less than the width of the dataframe, the remaining space will be distributed evenly among all columns.

A tooltip that gets displayed when hovering over the column label. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

disabled (bool or None)

Whether editing should be disabled for this column. If this is None (default), Streamlit will enable editing wherever possible.

If a column has mixed types, it may become uneditable regardless of disabled.

required (bool or None)

Whether edited cells in the column need to have a value. If this is False (default), the user can submit empty values for this column. If this is True, an edited cell in this column can only be submitted if its value is not None, and a new row will only be submitted after the user fills in this column.

pinned (bool or None)

Whether the column is pinned. A pinned column will stay visible on the left side no matter where the user scrolls. If this is None (default), Streamlit will decide: index columns are pinned, and data columns are not pinned.

default (int, float, or None)

Specifies the default value in this column when a new row is added by the user. This defaults to None.

format (str, "plain", "localized", "percent", "dollar", "euro", "yen", "accounting", "compact", "scientific", "engineering", or None)

A format string controlling how numbers are displayed. This can be one of the following values:

Formatting from column_config always takes precedence over formatting from pandas.Styler. The formatting does not impact the re

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "price": [20, 950, 250, 500],
    }
)

st.data_editor(
    data_df,
    column_config={
        "price": st.column_config.NumberColumn(
            "Price (in USD)",
            help="The price of the product in USD",
            min_value=0,
            max_value=1000,
            step=1,
            format="$%d",
        )
    },
    hide_index=True,
)
```

---

## st.column_config.ProgressColumn - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.progresscolumn

**Contents:**
- st.column_config.ProgressColumn
    - Examples
  - Still have questions?

Configure a progress column in st.dataframe or st.data_editor.

Cells need to contain a number. Progress columns are not editable at the moment. This command needs to be used in the column_config parameter of st.dataframe or st.data_editor.

st.column_config.ProgressColumn(label=None, *, width=None, help=None, pinned=None, format=None, min_value=None, max_value=None, step=None)

The label shown at the top of the column. If this is None (default), the column name is used.

width ("small", "medium", "large", int, or None)

The display width of the column. If this is None (default), the column will be sized to fit the cell contents. Otherwise, this can be one of the following:

If the total width of all columns is less than the width of the dataframe, the remaining space will be distributed evenly among all columns.

A tooltip that gets displayed when hovering over the column label. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

format (str, "plain", "localized", "percent", "dollar", "euro", "yen", "accounting", "compact", "scientific", "engineering", or None)

A format string controlling how the numbers are displayed. This can be one of the following values:

Number formatting from column_config always takes precedence over number formatting from pandas.Styler. The number formatting does not impact the return value when used in st.data_editor.

pinned (bool or None)

Whether the column is pinned. A pinned column will stay visible on the left side no matter where the user scrolls. If this is None (default), Streamlit will decide: index columns are pinned, and data columns are not pinned.

min_value (int, float, or None)

The minimum value of the progress bar. If this is None (default), the minimum will be 0.

max_value (int, float, or None)

The maximum value of the progress bar. If this is None (default), the maximum will be 100 for integer values and 1.0 for float values.

step (int, float, or None)

The precision of numbers. If this is None (default), integer columns will have a step of 1 and float columns will have a step of 0.01. Setting step for float columns will ensure a consistent number of digits after the decimal are displayed.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "sales": [200, 550, 1000, 80],
    }
)

st.data_editor(
    data_df,
    column_config={
        "sales": st.column_config.ProgressColumn(
            "Sales volume",
            help="The sales volume in USD",
            format="$%f",
            min_value=0,
            max_value=1000,
        ),
    },
    hide_index=True,
)
```

---

## Navigation and pages - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/navigation

**Contents:**
- Navigation and pages
    - Navigation
    - Page
    - Page link
    - Switch page
  - Still have questions?

Configure the available pages in a multipage app.

Define a page in a multipage app.

Display a link to another page in a multipage app.

Programmatically navigates to a specified page.

Our forums are full of helpful information and Streamlit experts.

---

## st.pdf - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/media/st.pdf

**Contents:**
- st.pdf
    - Example
  - Still have questions?

Display a PDF viewer.

You must install streamlit-pdf to use this command. You can install it as an extra with Streamlit:

st.pdf(data, *, height=500, key=None)

data (str, Path, BytesIO, or bytes)

The PDF file to show. This can be one of the following:

height (int or "stretch")

The height of the PDF viewer. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
pip install streamlit[pdf]
```

Example 2 (unknown):
```unknown
st.pdf("https://example.com/sample.pdf")
st.pdf("https://example.com/sample.pdf", height=600)
```

---

## App testing - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/app-testing

**Contents:**
- App testing
- The AppTest class
  - st.testing.v1.AppTest
  - AppTest.from_file
  - AppTest.from_string
  - AppTest.from_function
- Testing-element classes
    - Block
    - Element
    - Button

Streamlit app testing framework enables developers to build and run headless tests that execute their app code directly, simulate user input, and inspect rendered outputs for correctness.

The provided class, AppTest, simulates a running app and provides methods to set up, manipulate, and inspect the app contents via API instead of a browser UI. It can be used to write automated tests of an app in various scenarios. These can then be run using a tool like pytest. A typical pattern is to build a suite of tests for an app that ensure consistent functionality as the app evolves, and run the tests locally and/or in a CI environment like Github Actions.

st.testing.v1.AppTest simulates a running Streamlit app for testing.

st.testing.v1.AppTest.from_file initializes a simulated app from a file.

st.testing.v1.AppTest.from_string initializes a simulated app from a string.

st.testing.v1.AppTest.from_function initializes a simulated app from a function.

A representation of container elements, including:

The base class for representation of all elements, including:

A representation of st.button and st.form_submit_button.

A representation of st.chat_input.

A representation of st.checkbox.

A representation of st.color_picker.

A representation of st.date_input.

A representation of st.multiselect.

A representation of st.number_input.

A representation of st.radio.

A representation of st.select_slider.

A representation of st.selectbox.

A representation of st.slider.

A representation of st.text_area.

A representation of st.text_input.

A representation of st.time_input.

A representation of st.toggle.

Our forums are full of helpful information and Streamlit experts.

---

## st.cache_data - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/caching-and-state/st.experimental_memo

**Contents:**
    - Tip
- st.cache_data
    - Example
    - Warning
- st.cache_data.clear
    - Example
- CachedFunc.clear
    - Example
- Using Streamlit commands in cached functions
  - Static elements

This page only contains information on the st.cache_data API. For a deeper dive into caching and how to use it, check out Caching.

Decorator to cache functions that return data (e.g. dataframe transforms, database queries, ML inference).

Cached objects are stored in "pickled" form, which means that the return value of a cached function must be pickleable. Each caller of the cached function gets its own copy of the cached data.

You can clear a function's cache with func.clear() or clear the entire cache with st.cache_data.clear().

A function's arguments must be hashable to cache it. If you have an unhashable argument (like a database connection) or an argument you want to exclude from caching, use an underscore prefix in the argument name. In this case, Streamlit will return a cached value when all other arguments match a previous function call. Alternatively, you can declare custom hashing functions with hash_funcs.

Cached values are available to all users of your app. If you need to save results that should only be accessible within a session, use Session State instead. Within each user session, an @st.cache_data-decorated function returns a copy of the cached return value (if the value is already cached). To cache shared global resources (singletons), use st.cache_resource instead. To learn more about caching, see Caching overview.

Caching async functions is not supported. To upvote this feature, see GitHub issue #8308.

st.cache_data(func=None, *, ttl, max_entries, show_spinner, show_time=False, persist, hash_funcs=None)

The function to cache. Streamlit hashes the function's source code.

ttl (float, timedelta, str, or None)

The maximum time to keep an entry in the cache. Can be one of:

Note that ttl will be ignored if persist="disk" or persist=True.

max_entries (int or None)

The maximum number of entries to keep in the cache, or None for an unbounded cache. When a new entry is added to a full cache, the oldest cached entry will be removed. Defaults to None.

show_spinner (bool or str)

Enable the spinner. Default is True to show a spinner when there is a "cache miss" and the cached data is being created. If string, value of show_spinner param will be used for spinner text.

Whether to show the elapsed time next to the spinner text. If this is False (default), no time is displayed. If this is True, elapsed time is displayed with a precision of 0.1 seconds. The time format is not configurable.

persist ("disk", bool, or None)

Optional locatio

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import streamlit as st

@st.cache_data
def fetch_and_clean_data(url):
    # Fetch data from URL here, and then clean it up.
    return data

d1 = fetch_and_clean_data(DATA_URL_1)
# Actually executes the function, since this is the first time it was
# encountered.

d2 = fetch_and_clean_data(DATA_URL_1)
# Does not execute the function. Instead, returns its previously computed
# value. This means that now the data in d1 is the same as in d2.

d3 = fetch_and_clean_data(DATA_URL_2)
# This is a different URL, so the function executes.
```

Example 2 (python):
```python
import streamlit as st

@st.cache_data(persist="disk")
def fetch_and_clean_data(url):
    # Fetch data from URL here, and then clean it up.
    return data
```

Example 3 (python):
```python
import streamlit as st

@st.cache_data
def fetch_and_clean_data(_db_connection, num_rows):
    # Fetch data from _db_connection here, and then clean it up.
    return data

connection = make_database_connection()
d1 = fetch_and_clean_data(connection, num_rows=10)
# Actually executes the function, since this is the first time it was
# encountered.

another_connection = make_database_connection()
d2 = fetch_and_clean_data(another_connection, num_rows=10)
# Does not execute the function. Instead, returns its previously computed
# value - even though the _database_connection parameter was differen
...
```

Example 4 (python):
```python
import streamlit as st

@st.cache_data
def fetch_and_clean_data(_db_connection, num_rows):
    # Fetch data from _db_connection here, and then clean it up.
    return data

fetch_and_clean_data.clear(_db_connection, 50)
# Clear the cached entry for the arguments provided.

fetch_and_clean_data.clear()
# Clear all cached entries for this function.
```

---

## st.checkbox - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.checkbox

**Contents:**
- st.checkbox
    - Example
  - Featured videos
  - Still have questions?

Display a checkbox widget.

st.checkbox(label, value=False, key=None, help=None, on_change=None, args=None, kwargs=None, *, disabled=False, label_visibility="visible", width="content")

A short label explaining to the user what this checkbox is for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

For accessibility reasons, you should never set an empty label, but you can hide it with label_visibility if needed. In the future, we may disallow empty labels by raising an exception.

Preselect the checkbox when it first renders. This will be cast to bool internally.

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

A tooltip that gets displayed next to the widget label. Streamlit only displays the tooltip when label_visibility="visible". If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

An optional callback invoked when this checkbox's value changes.

An optional list or tuple of args to pass to the callback.

An optional dict of kwargs to pass to the callback.

An optional boolean that disables the checkbox if set to True. The default is False.

label_visibility ("visible", "hidden", or "collapsed")

The visibility of the label. The default is "visible". If this is "hidden", Streamlit displays an empty spacer instead of the label, which can help keep the widget aligned with other widgets. If this is "collapsed", Streamlit displays no label or spacer.

width ("content", "stretch", or int)

The width of the checkbox widget. This can be one of the following:

Whether or not the checkbox is checked.

Check out our video on how to use one of Streamlit's core functions, the checkbox! ☑

In the video below, we'll take it a step further and learn how to combine a button, checkbox and radio button!

Our forums are full of helpful info

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

agree = st.checkbox("I agree")

if agree:
    st.write("Great!")
```

---

## Text elements - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/text

**Contents:**
- Text elements
- Headings and body text
    - Markdown
    - Title
    - Header
    - Subheader
- Formatted text
    - Badge
    - Caption
    - Code block

Streamlit apps usually start with a call to st.title to set the app's title. After that, there are 2 heading levels you can use: st.header and st.subheader.

Pure text is entered with st.text, and Markdown with st.markdown.

We also offer a "swiss-army knife" command called st.write, which accepts multiple arguments, and multiple data types. And as described above, you can also use magic commands in place of st.write.

Display string formatted as Markdown.

Display text in title formatting.

Display text in header formatting.

Display text in subheader formatting.

Display a small, colored badge.

Display text in small font.

Display a code block with optional syntax highlighting.

Display some code on the app, then execute it. Useful for tutorials.

Write fixed-width and preformatted text.

Display mathematical expressions formatted as LaTeX.

Display a horizontal rule.

Display object’s doc string, nicely formatted.

Renders HTML strings to your app.

Third-party components

These are featured components created by our lovely community. For more examples and inspiration, check out our Components Gallery and Streamlit Extras!

Add tags to your Streamlit apps. Created by @gagan3012.

Apply text mining on a dataframe. Created by @JohnSnowLabs.

A library with useful Streamlit extras. Created by @arnaudmiribel.

Display annotated text in Streamlit apps. Created by @tvst.

Provides a sketching canvas using Fabric.js. Created by @andfanilo.

Add tags to your Streamlit apps. Created by @gagan3012.

Apply text mining on a dataframe. Created by @JohnSnowLabs.

A library with useful Streamlit extras. Created by @arnaudmiribel.

Display annotated text in Streamlit apps. Created by @tvst.

Provides a sketching canvas using Fabric.js. Created by @andfanilo.

Add tags to your Streamlit apps. Created by @gagan3012.

Apply text mining on a dataframe. Created by @JohnSnowLabs.

A library with useful Streamlit extras. Created by @arnaudmiribel.

Our forums are full of helpful information and Streamlit experts.

---

## st.column_config.Column - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.column

**Contents:**
- st.column_config.Column
    - Examples
  - Still have questions?

Configure a generic column in st.dataframe or st.data_editor.

The type of the column will be automatically inferred from the data type. This command needs to be used in the column_config parameter of st.dataframe or st.data_editor.

To change the type of the column and enable type-specific configuration options, use one of the column types in the st.column_config namespace, e.g. st.column_config.NumberColumn.

st.column_config.Column(label=None, *, width=None, help=None, disabled=None, required=None, pinned=None)

The label shown at the top of the column. If this is None (default), the column name is used.

width ("small", "medium", "large", int, or None)

The display width of the column. If this is None (default), the column will be sized to fit the cell contents. Otherwise, this can be one of the following:

If the total width of all columns is less than the width of the dataframe, the remaining space will be distributed evenly among all columns.

A tooltip that gets displayed when hovering over the column label. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

disabled (bool or None)

Whether editing should be disabled for this column. If this is None (default), Streamlit will enable editing wherever possible.

If a column has mixed types, it may become uneditable regardless of disabled.

required (bool or None)

Whether edited cells in the column need to have a value. If this is False (default), the user can submit empty values for this column. If this is True, an edited cell in this column can only be submitted if its value is not None, and a new row will only be submitted after the user fills in this column.

pinned (bool or None)

Whether the column is pinned. A pinned column will stay visible on the left side no matter where the user scrolls. If this is None (default), Streamlit will decide: index columns are pinned, and data columns are not pinned.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "widgets": ["st.selectbox", "st.number_input", "st.text_area", "st.button"],
    }
)

st.data_editor(
    data_df,
    column_config={
        "widgets": st.column_config.Column(
            "Streamlit Widgets",
            help="Streamlit **widget** commands 🎈",
            width="medium",
            required=True,
        )
    },
    hide_index=True,
    num_rows="dynamic",
)
```

---

## st.context - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/utilities/st.context

**Contents:**
- st.context
- context.cookies
    - Examples
- context.headers
    - Examples
- context.ip_address
    - Example
- context.is_embedded
    - Example
- context.locale

An interface to access user session context.

st.context provides a read-only interface to access headers and cookies for the current user session.

Each property (st.context.headers and st.context.cookies) returns a dictionary of named values.

A read-only, dict-like object containing cookies sent in the initial request.

A read-only, dict-like object containing headers sent in the initial request.

The read-only IP address of the user's connection.

Whether the app is embedded.

The read-only locale of the user's browser.

A read-only, dictionary-like object containing theme information.

The read-only timezone of the user's browser.

The read-only timezone offset of the user's browser.

The read-only URL of the app in the user's browser.

A read-only, dict-like object containing cookies sent in the initial request.

Example 1: Access all available cookies

Show a dictionary of cookies:

Example 2: Access a specific cookie

Show the value of a specific cookie:

A read-only, dict-like object containing headers sent in the initial request.

Keys are case-insensitive and may be repeated. When keys are repeated, dict-like methods will only return the last instance of each key. Use .get_all(key="your_repeated_key") to see all values if the same header is set multiple times.

Example 1: Access all available headers

Show a dictionary of headers (with only the last instance of any repeated key):

Example 2: Access a specific header

Show the value of a specific header (or the last instance if it's repeated):

Show of list of all headers for a given key:

The read-only IP address of the user's connection.

This should not be used for security measures because it can easily be spoofed. When a user accesses the app through localhost, the IP address is None. Otherwise, the IP address is determined from the remote_ip attribute of the Tornado request object and may be an IPv4 or IPv6 address.

Check if the user has an IPv4 or IPv6 address:

Whether the app is embedded.

This property returns a boolean value indicating whether the app is running in an embedded context. This is determined by the presence of embed=true as a query parameter in the URL. This is the only way to determine if the app is currently configured for embedding because embedding settings are not accessible through st.query_params or st.context.url.

Conditionally show content when the app is running in an embedded context:

The read-only locale of the user's browser.

st.context.locale returns the 

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.context.cookies
```

Example 2 (unknown):
```unknown
import streamlit as st

st.context.cookies["_ga"]
```

Example 3 (unknown):
```unknown
import streamlit as st

st.context.headers
```

Example 4 (unknown):
```unknown
import streamlit as st

st.context.headers["host"]
```

---

## Testing element classes - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/app-testing/testing-element-classes

**Contents:**
- Testing element classes
- st.testing.v1.element_tree.Block
- st.testing.v1.element_tree.Element
- st.testing.v1.element_tree.Button
- st.testing.v1.element_tree.ChatInput
- st.testing.v1.element_tree.Checkbox
- st.testing.v1.element_tree.ColorPicker
- st.testing.v1.element_tree.DateInput
- st.testing.v1.element_tree.Multiselect
- st.testing.v1.element_tree.NumberInput

The Block class has the same methods and attributes as AppTest. A Block instance represents a container of elements just as AppTest represents the entire app. For example, Block.button will produce a WidgetList of Button in the same manner as AppTest.button.

ChatMessage, Column, and Tab all inherit from Block. For all container classes, parameters of the original element can be obtained as properties. For example, ChatMessage.avatar and Tab.label.

Element base class for testing.

This class's methods and attributes are universal for all elements implemented in testing. For example, Caption, Code, Text, and Title inherit from Element. All widget classes also inherit from Element, but have additional methods specific to each widget type. See the AppTest class for the full list of supported elements.

For all element classes, parameters of the original element can be obtained as properties. For example, Button.label, Caption.help, and Toast.icon.

st.testing.v1.element_tree.Element(proto, root)

Run the AppTest script which contains the element.

The value or contents of the element.

A representation of st.button and st.form_submit_button.

st.testing.v1.element_tree.Button(proto, root)

Set the value of the button to True.

Run the AppTest script which contains the element.

Set the value of the button.

The value of the button. (bool)

A representation of st.chat_input.

st.testing.v1.element_tree.ChatInput(proto, root)

Run the AppTest script which contains the element.

Set the value of the widget.

The value of the widget. (str)

A representation of st.checkbox.

st.testing.v1.element_tree.Checkbox(proto, root)

Set the value of the widget to True.

Run the AppTest script which contains the element.

Set the value of the widget.

Set the value of the widget to False.

The value of the widget. (bool)

A representation of st.color_picker.

st.testing.v1.element_tree.ColorPicker(proto, root)

Set the value of the widget as a hex string. May omit the "#" prefix.

Run the AppTest script which contains the element.

Set the value of the widget as a hex string.

The currently selected value as a hex string. (str)

A representation of st.date_input.

st.testing.v1.element_tree.DateInput(proto, root)

Run the AppTest script which contains the element.

Set the value of the widget.

The value of the widget. (date or Tuple of date)

A representation of st.multiselect.

st.testing.v1.element_tree.Multiselect(proto, root)

Run the AppTest script which contains the

*[Content truncated]*

---

## st.bar_chart - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/charts/st.bar_chart

**Contents:**
- st.bar_chart
    - Examples
- element.add_rows
    - Example
  - Still have questions?

This is syntax-sugar around st.altair_chart. The main difference is this command uses the data's own column and indices to figure out the chart's Altair spec. As a result this is easier to use for many "just plot this" scenarios, while being less customizable.

st.bar_chart(data=None, *, x=None, y=None, x_label=None, y_label=None, color=None, horizontal=False, sort=True, stack=None, width=None, height=None, use_container_width=True)

data (Anything supported by st.dataframe)

Column name or key associated to the x-axis data. If x is None (default), Streamlit uses the data index for the x-axis values.

y (str, Sequence of str, or None)

Column name(s) or key(s) associated to the y-axis data. If this is None (default), Streamlit draws the data of all remaining columns as data series. If this is a Sequence of strings, Streamlit draws several series on the same chart by melting your wide-format table into a long-format table behind the scenes.

x_label (str or None)

The label for the x-axis. If this is None (default), Streamlit will use the column name specified in x if available, or else no label will be displayed.

y_label (str or None)

The label for the y-axis. If this is None (default), Streamlit will use the column name(s) specified in y if available, or else no label will be displayed.

color (str, tuple, Sequence of str, Sequence of tuple, or None)

The color to use for different series in this chart.

For a bar chart with just one series, this can be:

For a bar chart with multiple series, where the dataframe is in long format (that is, y is None or just one column), this can be:

None, to use the default colors.

The name of a column in the dataset. Data points will be grouped into series of the same color based on the value of this column. In addition, if the values in this column match one of the color formats above (hex string or color tuple), then that color will be used.

For example: if the dataset has 1000 rows, but this column only contains the values "adult", "child", and "baby", then those 1000 datapoints will be grouped into three series whose colors will be automatically selected from the default palette.

But, if for the same 1000-row dataset, this column contained the values "#ffaa00", "#f0f", "#0000ff", then then those 1000 datapoints would still be grouped into 3 series, but their colors would be "#ffaa00", "#f0f", "#0000ff" this time around.

For a bar chart with multiple series, where the dataframe is in wide format (that is, y is 

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(rng(0).standard_normal((20, 3)), columns=["a", "b", "c"])

st.bar_chart(df)
```

Example 2 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(
    {
        "col1": list(range(20)) * 3,
        "col2": rng(0).standard_normal(60),
        "col3": ["a"] * 20 + ["b"] * 20 + ["c"] * 20,
    }
)

st.bar_chart(df, x="col1", y="col2", color="col3")
```

Example 3 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(
    {
        "col1": list(range(20)),
        "col2": rng(0).standard_normal(20),
        "col3": rng(1).standard_normal(20),
    }
)

st.bar_chart(
    df,
    x="col1",
    y=["col2", "col3"],
    color=["#FF0000", "#0000FF"],
)
```

Example 4 (python):
```python
import streamlit as st
from vega_datasets import data

source = data.barley()

st.bar_chart(source, x="variety", y="yield", color="site", horizontal=True)
```

---

## st.page_link - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.page_link

**Contents:**
    - Tip
- st.page_link
    - Example
  - Still have questions?

Check out our tutorial to learn about building custom, dynamic menus with st.page_link.

Display a link to another page in a multipage app or to an external page.

If another page in a multipage app is specified, clicking st.page_link stops the current page execution and runs the specified page as if the user clicked on it in the sidebar navigation.

If an external page is specified, clicking st.page_link opens a new tab to the specified page. The current script run will continue if not complete.

st.page_link(page, *, label=None, icon=None, help=None, disabled=False, use_container_width=None, width="content")

page (str, Path, or StreamlitPage)

The file path (relative to the main script) or a StreamlitPage indicating the page to switch to. Alternatively, this can be the URL to an external page (must start with "http://" or "https://").

The label for the page link. Labels are required for external pages. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

An optional emoji or icon to display next to the button label. If icon is None (default), the icon is inferred from the StreamlitPage object or no icon is displayed. If icon is a string, the following options are valid:

A single-character emoji. For example, you can set icon="🚨" or icon="🔥". Emoji short codes are not supported.

An icon from the Material Symbols library (rounded style) in the format ":material/icon_name:" where "icon_name" is the name of the icon in snake case.

For example, icon=":material/thumb_up:" will display the Thumb Up icon. Find additional icons in the Material Symbols font library.

A tooltip that gets displayed when the link is hovered over. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

An optional boolean that disables the page link if set to True. The default is False.

use_container_width (bool)

use_container_width is deprecated and will be removed in a future release. For use

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
your-repository/
├── pages/
│   ├── page_1.py
│   └── page_2.py
└── your_app.py
```

Example 2 (unknown):
```unknown
import streamlit as st

st.page_link("your_app.py", label="Home", icon="🏠")
st.page_link("pages/page_1.py", label="Page 1", icon="1️⃣")
st.page_link("pages/page_2.py", label="Page 2", icon="2️⃣", disabled=True)
st.page_link("http://www.google.com", label="Google", icon="🌎")
```

---

## st.echo - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/text/st.echo

**Contents:**
- st.echo
    - Example
  - Display code
    - Note
  - Still have questions?

Use in a with block to draw some code on the app, then execute it.

st.echo(code_location="above")

code_location ("above" or "below")

Whether to show the echoed code before or after the results of the executed code block.

Sometimes you want your Streamlit app to contain both your usual Streamlit graphic elements and the code that generated those elements. That's where st.echo() comes in.

Ok so let's say you have the following file, and you want to make its app a little bit more self-explanatory by making that middle section visible in the Streamlit app:

The file above creates a Streamlit app containing the words "Hi there, John", and then "Done!".

Now let's use st.echo() to make that middle section of the code visible in the app:

You can have multiple st.echo() blocks in the same file. Use it as often as you wish!

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

with st.echo():
    st.write('This code will be printed')
```

---

## st.experimental_data_editor - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.experimental_data_editor

**Contents:**
- st.experimental_data_editor
    - Warning
  - Still have questions?

This method did not exist in version 1.50.0 of Streamlit.

Our forums are full of helpful information and Streamlit experts.

---

## st.link_button - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.link_button

**Contents:**
- st.link_button
    - Example
  - Still have questions?

Display a link button element.

When clicked, a new tab will be opened to the specified URL. This will create a new session for the user if directed within the app.

st.link_button(label, url, *, help=None, type="secondary", icon=None, disabled=False, use_container_width=None, width="content")

A short label explaining to the user what this button is for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

The url to be opened on user click

A tooltip that gets displayed when the button is hovered over. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

type ("primary", "secondary", or "tertiary")

An optional string that specifies the button type. This can be one of the following:

An optional emoji or icon to display next to the button label. If icon is None (default), no icon is displayed. If icon is a string, the following options are valid:

A single-character emoji. For example, you can set icon="🚨" or icon="🔥". Emoji short codes are not supported.

An icon from the Material Symbols library (rounded style) in the format ":material/icon_name:" where "icon_name" is the name of the icon in snake case.

For example, icon=":material/thumb_up:" will display the Thumb Up icon. Find additional icons in the Material Symbols font library.

An optional boolean that disables the link button if set to True. The default is False.

use_container_width (bool)

use_container_width is deprecated and will be removed in a future release. For use_container_width=True, use width="stretch". For use_container_width=False, use width="content".

Whether to expand the button's width to fill its parent container. If use_container_width is False (default), Streamlit sizes the button to fit its contents. If use_container_width is True, the width of the button matches its parent container.

In both cases, if the contents of the button are wider than the parent container, the contents will li

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.link_button("Go to gallery", "https://streamlit.io/gallery")
```

---

## st.number_input - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.number_input

**Contents:**
- st.number_input
    - Example
  - Still have questions?

Display a numeric input widget.

Integer values exceeding +/- (1<<53) - 1 cannot be accurately stored or returned by the widget due to serialization constraints between the Python server and JavaScript client. You must handle such numbers as floats, leading to a loss in precision.

st.number_input(label, min_value=None, max_value=None, value="min", step=None, format=None, key=None, help=None, on_change=None, args=None, kwargs=None, *, placeholder=None, disabled=False, label_visibility="visible", icon=None, width="stretch")

A short label explaining to the user what this input is for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

For accessibility reasons, you should never set an empty label, but you can hide it with label_visibility if needed. In the future, we may disallow empty labels by raising an exception.

min_value (int, float, or None)

The minimum permitted value. If this is None (default), there will be no minimum for float values and a minimum of - (1<<53) + 1 for integer values.

max_value (int, float, or None)

The maximum permitted value. If this is None (default), there will be no maximum for float values and a maximum of (1<<53) - 1 for integer values.

value (int, float, "min" or None)

The value of this widget when it first renders. If this is "min" (default), the initial value is min_value unless min_value is None. If min_value is None, the widget initializes with a value of 0.0 or 0.

If value is None, the widget will initialize with no value and return None until the user provides input.

step (int, float, or None)

The stepping interval. Defaults to 1 if the value is an int, 0.01 otherwise. If the value is not specified, the format parameter will be used.

A printf-style format string controlling how the interface should display numbers. The output must be purely numeric. This does not impact the return value of the widget. For more information about the formatting specification, see sprintf.js.

For example, format="%0.1f" adjusts the displayed decimal precision to only show one di

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

number = st.number_input("Insert a number")
st.write("The current number is ", number)
```

Example 2 (unknown):
```unknown
import streamlit as st

number = st.number_input(
    "Insert a number", value=None, placeholder="Type a number..."
)
st.write("The current number is ", number)
```

---

## st.column_config.BarChartColumn - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.barchartcolumn

**Contents:**
- st.column_config.BarChartColumn
    - Examples
  - Still have questions?

Configure a bar chart column in st.dataframe or st.data_editor.

Cells need to contain a list of numbers. Chart columns are not editable at the moment. This command needs to be used in the column_config parameter of st.dataframe or st.data_editor.

st.column_config.BarChartColumn(label=None, *, width=None, help=None, pinned=None, y_min=None, y_max=None, color=None)

The label shown at the top of the column. If this is None (default), the column name is used.

width ("small", "medium", "large", int, or None)

The display width of the column. If this is None (default), the column will be sized to fit the cell contents. Otherwise, this can be one of the following:

If the total width of all columns is less than the width of the dataframe, the remaining space will be distributed evenly among all columns.

A tooltip that gets displayed when hovering over the column label. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

pinned (bool or None)

Whether the column is pinned. A pinned column will stay visible on the left side no matter where the user scrolls. If this is None (default), Streamlit will decide: index columns are pinned, and data columns are not pinned.

y_min (int, float, or None)

The minimum value on the y-axis for all cells in the column. If this is None (default), every cell will use the minimum of its data.

y_max (int, float, or None)

The maximum value on the y-axis for all cells in the column. If this is None (default), every cell will use the maximum of its data.

color ("auto", "auto-inverse", str, or None)

The color to use for the chart. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "sales": [
            [0, 4, 26, 80, 100, 40],
            [80, 20, 80, 35, 40, 100],
            [10, 20, 80, 80, 70, 0],
            [10, 100, 20, 100, 30, 100],
        ],
    }
)

st.data_editor(
    data_df,
    column_config={
        "sales": st.column_config.BarChartColumn(
            "Sales (last 6 months)",
            help="The sales volume in the last 6 months",
            y_min=0,
            y_max=100,
        ),
    },
    hide_index=True,
)
```

---

## st.write and magic commands - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/write-magic

**Contents:**
- st.write and magic commands
    - st.write
    - st.write_stream
    - Magic
  - Still have questions?

Streamlit has two easy ways to display information into your app, which should typically be the first thing you try: st.write and magic.

Write arguments to the app.

Write generators or streams to the app with a typewriter effect.

Any time Streamlit sees either a variable or literal value on its own line, it automatically writes that to your app using st.write

Our forums are full of helpful information and Streamlit experts.

---

## st.multiselect - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.multiselect

**Contents:**
- st.multiselect
    - Examples
  - Still have questions?

Display a multiselect widget.

The multiselect widget starts as empty.

st.multiselect(label, options, default=None, format_func=special_internal_function, key=None, help=None, on_change=None, args=None, kwargs=None, *, max_selections=None, placeholder=None, disabled=False, label_visibility="visible", accept_new_options=False, width="stretch")

A short label explaining to the user what this select widget is for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

For accessibility reasons, you should never set an empty label, but you can hide it with label_visibility if needed. In the future, we may disallow empty labels by raising an exception.

Labels for the select options in an Iterable. This can be a list, set, or anything supported by st.dataframe. If options is dataframe-like, the first column will be used. Each label will be cast to str internally by default.

default (Iterable of V, V, or None)

List of default values. Can also be a single value.

format_func (function)

Function to modify the display of the options. It receives the raw option as an argument and should output the label to be shown for that option. This has no impact on the return value of the command.

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

A tooltip that gets displayed next to the widget label. Streamlit only displays the tooltip when label_visibility="visible". If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

An optional callback invoked when this widget's value changes.

An optional list or tuple of args to pass to the callback.

An optional dict of kwargs to pass to the callback.

The max selections that can be selected at a time.

placeholder (str or None)

A string to display when no options are selected. If this is None (default), th

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

options = st.multiselect(
    "What are your favorite colors?",
    ["Green", "Yellow", "Red", "Blue"],
    default=["Yellow", "Red"],
)

st.write("You selected:", options)
```

Example 2 (unknown):
```unknown
import streamlit as st

options = st.multiselect(
    "What are your favorite cat names?",
    ["Jellybeans", "Fish Biscuit", "Madam President"],
    max_selections=5,
    accept_new_options=True,
)

st.write("You selected:", options)
```

---

## st.secrets - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/connections/st.secrets

**Contents:**
- st.secrets
  - secrets.toml
  - Configure secrets locations
    - Example
  - Still have questions?

st.secrets provides a dictionary-like interface to access secrets stored in a secrets.toml file. It behaves similarly to st.session_state. st.secrets can be used with both key and attribute notation. For example, st.secrets.your_key and st.secrets["your_key"] refer to the same value. For more information about using st.secrets, see Secrets management.

By default, secrets can be saved globally or per-project. When both types of secrets are saved, Streamlit will combine the saved values but give precedence to per-project secrets if there are duplicate keys. For information on how to format and locate your secrets.toml file for your development environment, see secrets.toml.

You can configure where Streamlit searches for secrets through the configuration option, secrets.files. With this option, you can list additional secrets locations and change the order of precedence. You can specify other TOML files or include Kubernetes style secret files.

In your Streamlit app, the following values would be true:

Our forums are full of helpful information and Streamlit experts.

---

## st.status - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/status/st.status

**Contents:**
- st.status
    - Examples
- StatusContainer.update
  - Still have questions?

Insert a status container to display output from long-running tasks.

Inserts a container into your app that is typically used to show the status and details of a process or task. The container can hold multiple elements and can be expanded or collapsed by the user similar to st.expander. When collapsed, all that is visible is the status icon and label.

The label, state, and expanded state can all be updated by calling .update() on the returned object. To add elements to the returned container, you can use with notation (preferred) or just call methods directly on the returned object.

By default, st.status() initializes in the "running" state. When called using with notation, it automatically updates to the "complete" state at the end of the "with" block. See examples below for more details.

All content within the status container is computed and sent to the frontend, even if the status container is closed.

To follow best design practices and maintain a good appearance on all screen sizes, don't nest status containers.

st.status(label, *, expanded=False, state="running", width="stretch")

The initial label of the status container. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

If True, initializes the status container in "expanded" state. Defaults to False (collapsed).

state ("running", "complete", or "error")

The initial state of the status container which determines which icon is shown:

width ("stretch" or int)

The width of the status container. This can be one of the following:

A mutable status container that can hold multiple elements. The label, state, and expanded state can be updated after creation via .update().

You can use the with notation to insert any element into an status container:

You can also use .update() on the container to change the label, state, or expanded state:

Update the status container.

Only specified arguments are updated. Container contents and unspecified arguments remain unchanged.

StatusContainer.update(*, label=None, expanded=None, state=None)

A new label 

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import time
import streamlit as st

with st.status("Downloading data..."):
    st.write("Searching for data...")
    time.sleep(2)
    st.write("Found URL.")
    time.sleep(1)
    st.write("Downloading data...")
    time.sleep(1)

st.button("Rerun")
```

Example 2 (unknown):
```unknown
import time
import streamlit as st

with st.status("Downloading data...", expanded=True) as status:
    st.write("Searching for data...")
    time.sleep(2)
    st.write("Found URL.")
    time.sleep(1)
    st.write("Downloading data...")
    time.sleep(1)
    status.update(
        label="Download complete!", state="complete", expanded=False
    )

st.button("Rerun")
```

---

## st.date_input - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.date_input

**Contents:**
- st.date_input
    - Examples
  - Still have questions?

Display a date input widget.

The date input widget can be configured to accept a single date or a date range. The first day of the week is determined from the user's locale in their browser.

st.date_input(label, value="today", min_value=None, max_value=None, key=None, help=None, on_change=None, args=None, kwargs=None, *, format="YYYY/MM/DD", disabled=False, label_visibility="visible", width="stretch")

A short label explaining to the user what this date input is for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

For accessibility reasons, you should never set an empty label, but you can hide it with label_visibility if needed. In the future, we may disallow empty labels by raising an exception.

value ("today", datetime.date, datetime.datetime, str, list/tuple of these, or None)

The value of this widget when it first renders. This can be one of the following:

min_value ("today", datetime.date, datetime.datetime, str, or None)

The minimum selectable date. This can be any of the date types accepted by value, except list or tuple.

If this is None (default), the minimum selectable date is ten years before the initial value. If the initial value is an interval, the minimum selectable date is ten years before the start date of the interval. If no initial value is set, the minimum selectable date is ten years before today.

max_value ("today", datetime.date, datetime.datetime, str, or None)

The maximum selectable date. This can be any of the date types accepted by value, except list or tuple.

If this is None (default), the maximum selectable date is ten years after the initial value. If the initial value is an interval, the maximum selectable date is ten years after the end date of the interval. If no initial value is set, the maximum selectable date is ten years after today.

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

A tooltip that gets displayed next to t

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import datetime
import streamlit as st

d = st.date_input("When's your birthday", datetime.date(2019, 7, 6))
st.write("Your birthday is:", d)
```

Example 2 (unknown):
```unknown
import datetime
import streamlit as st

today = datetime.datetime.now()
next_year = today.year + 1
jan_1 = datetime.date(next_year, 1, 1)
dec_31 = datetime.date(next_year, 12, 31)

d = st.date_input(
    "Select your vacation for next year",
    (jan_1, datetime.date(next_year, 1, 7)),
    jan_1,
    dec_31,
    format="MM.DD.YYYY",
)
d
```

Example 3 (unknown):
```unknown
import datetime
import streamlit as st

d = st.date_input("When's your birthday", value=None)
st.write("Your birthday is:", d)
```

---

## st.column_config.TimeColumn - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.timecolumn

**Contents:**
- st.column_config.TimeColumn
    - Examples
  - Still have questions?

Configure a time column in st.dataframe or st.data_editor.

This is the default column type for time values. This command needs to be used in the column_config parameter of st.dataframe or st.data_editor. When used with st.data_editor, editing will be enabled with a time picker widget.

st.column_config.TimeColumn(label=None, *, width=None, help=None, disabled=None, required=None, pinned=None, default=None, format=None, min_value=None, max_value=None, step=None)

The label shown at the top of the column. If this is None (default), the column name is used.

width ("small", "medium", "large", int, or None)

The display width of the column. If this is None (default), the column will be sized to fit the cell contents. Otherwise, this can be one of the following:

If the total width of all columns is less than the width of the dataframe, the remaining space will be distributed evenly among all columns.

A tooltip that gets displayed when hovering over the column label. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

disabled (bool or None)

Whether editing should be disabled for this column. If this is None (default), Streamlit will enable editing wherever possible.

If a column has mixed types, it may become uneditable regardless of disabled.

required (bool or None)

Whether edited cells in the column need to have a value. If this is False (default), the user can submit empty values for this column. If this is True, an edited cell in this column can only be submitted if its value is not None, and a new row will only be submitted after the user fills in this column.

pinned (bool or None)

Whether the column is pinned. A pinned column will stay visible on the left side no matter where the user scrolls. If this is None (default), Streamlit will decide: index columns are pinned, and data columns are not pinned.

default (datetime.time or None)

Specifies the default value in this column when a new row is added by the user. This defaults to None.

format (str, "localized", "iso8601", or None)

A format string controlling how times are displayed. This can be one of the following values:

Formatting from column_config always takes precedence over formatting from pandas.Styler. The formatting does not impact the return value when used in st.data_editor.

min_value (datetime.time or None)

The minimum time that can be en

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
from datetime import time
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "appointment": [
            time(12, 30),
            time(18, 0),
            time(9, 10),
            time(16, 25),
        ]
    }
)

st.data_editor(
    data_df,
    column_config={
        "appointment": st.column_config.TimeColumn(
            "Appointment",
            min_value=time(8, 0, 0),
            max_value=time(19, 0, 0),
            format="hh:mm a",
            step=60,
        ),
    },
    hide_index=True,
)
```

---

## st.cache_data - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache

**Contents:**
    - Tip
- st.cache_data
    - Example
    - Warning
- st.cache_data.clear
    - Example
- CachedFunc.clear
    - Example
- Using Streamlit commands in cached functions
  - Static elements

This page only contains information on the st.cache_data API. For a deeper dive into caching and how to use it, check out Caching.

Decorator to cache functions that return data (e.g. dataframe transforms, database queries, ML inference).

Cached objects are stored in "pickled" form, which means that the return value of a cached function must be pickleable. Each caller of the cached function gets its own copy of the cached data.

You can clear a function's cache with func.clear() or clear the entire cache with st.cache_data.clear().

A function's arguments must be hashable to cache it. If you have an unhashable argument (like a database connection) or an argument you want to exclude from caching, use an underscore prefix in the argument name. In this case, Streamlit will return a cached value when all other arguments match a previous function call. Alternatively, you can declare custom hashing functions with hash_funcs.

Cached values are available to all users of your app. If you need to save results that should only be accessible within a session, use Session State instead. Within each user session, an @st.cache_data-decorated function returns a copy of the cached return value (if the value is already cached). To cache shared global resources (singletons), use st.cache_resource instead. To learn more about caching, see Caching overview.

Caching async functions is not supported. To upvote this feature, see GitHub issue #8308.

st.cache_data(func=None, *, ttl, max_entries, show_spinner, show_time=False, persist, hash_funcs=None)

The function to cache. Streamlit hashes the function's source code.

ttl (float, timedelta, str, or None)

The maximum time to keep an entry in the cache. Can be one of:

Note that ttl will be ignored if persist="disk" or persist=True.

max_entries (int or None)

The maximum number of entries to keep in the cache, or None for an unbounded cache. When a new entry is added to a full cache, the oldest cached entry will be removed. Defaults to None.

show_spinner (bool or str)

Enable the spinner. Default is True to show a spinner when there is a "cache miss" and the cached data is being created. If string, value of show_spinner param will be used for spinner text.

Whether to show the elapsed time next to the spinner text. If this is False (default), no time is displayed. If this is True, elapsed time is displayed with a precision of 0.1 seconds. The time format is not configurable.

persist ("disk", bool, or None)

Optional locatio

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import streamlit as st

@st.cache_data
def fetch_and_clean_data(url):
    # Fetch data from URL here, and then clean it up.
    return data

d1 = fetch_and_clean_data(DATA_URL_1)
# Actually executes the function, since this is the first time it was
# encountered.

d2 = fetch_and_clean_data(DATA_URL_1)
# Does not execute the function. Instead, returns its previously computed
# value. This means that now the data in d1 is the same as in d2.

d3 = fetch_and_clean_data(DATA_URL_2)
# This is a different URL, so the function executes.
```

Example 2 (python):
```python
import streamlit as st

@st.cache_data(persist="disk")
def fetch_and_clean_data(url):
    # Fetch data from URL here, and then clean it up.
    return data
```

Example 3 (python):
```python
import streamlit as st

@st.cache_data
def fetch_and_clean_data(_db_connection, num_rows):
    # Fetch data from _db_connection here, and then clean it up.
    return data

connection = make_database_connection()
d1 = fetch_and_clean_data(connection, num_rows=10)
# Actually executes the function, since this is the first time it was
# encountered.

another_connection = make_database_connection()
d2 = fetch_and_clean_data(another_connection, num_rows=10)
# Does not execute the function. Instead, returns its previously computed
# value - even though the _database_connection parameter was differen
...
```

Example 4 (python):
```python
import streamlit as st

@st.cache_data
def fetch_and_clean_data(_db_connection, num_rows):
    # Fetch data from _db_connection here, and then clean it up.
    return data

fetch_and_clean_data.clear(_db_connection, 50)
# Clear the cached entry for the arguments provided.

fetch_and_clean_data.clear()
# Clear all cached entries for this function.
```

---

## st.cache_resource - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_resource

**Contents:**
    - Tip
- st.cache_resource
    - Example
- st.cache_resource.clear
    - Example
- CachedFunc.clear
    - Example
- Using Streamlit commands in cached functions
  - Static elements
  - Input widgets

This page only contains information on the st.cache_resource API. For a deeper dive into caching and how to use it, check out Caching.

Decorator to cache functions that return global resources (e.g. database connections, ML models).

Cached objects are shared across all users, sessions, and reruns. They must be thread-safe because they can be accessed from multiple threads concurrently. If thread safety is an issue, consider using st.session_state to store resources per session instead.

You can clear a function's cache with func.clear() or clear the entire cache with st.cache_resource.clear().

A function's arguments must be hashable to cache it. If you have an unhashable argument (like a database connection) or an argument you want to exclude from caching, use an underscore prefix in the argument name. In this case, Streamlit will return a cached value when all other arguments match a previous function call. Alternatively, you can declare custom hashing functions with hash_funcs.

Cached values are available to all users of your app. If you need to save results that should only be accessible within a session, use Session State instead. Within each user session, an @st.cache_resource-decorated function returns the cached instance of the return value (if the value is already cached). Therefore, objects cached by st.cache_resource act like singletons and can mutate. To cache data and return copies, use st.cache_data instead. To learn more about caching, see Caching overview.

Async objects are not officially supported in Streamlit. Caching async objects or objects that reference async objects may have unintended consequences. For example, Streamlit may close event loops in its normal operation and make the cached object raise an Event loop closed error.

To upvote official asyncio support, see GitHub issue #8488. To upvote support for caching async functions, see GitHub issue #8308.

st.cache_resource(func, *, ttl, max_entries, show_spinner, show_time=False, validate, hash_funcs=None)

The function that creates the cached resource. Streamlit hashes the function's source code.

ttl (float, timedelta, str, or None)

The maximum time to keep an entry in the cache. Can be one of:

max_entries (int or None)

The maximum number of entries to keep in the cache, or None for an unbounded cache. When a new entry is added to a full cache, the oldest cached entry will be removed. Defaults to None.

show_spinner (bool or str)

Enable the spinner. Default is True to sho

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import streamlit as st

@st.cache_resource
def get_database_session(url):
    # Create a database session object that points to the URL.
    return session

s1 = get_database_session(SESSION_URL_1)
# Actually executes the function, since this is the first time it was
# encountered.

s2 = get_database_session(SESSION_URL_1)
# Does not execute the function. Instead, returns its previously computed
# value. This means that now the connection object in s1 is the same as in s2.

s3 = get_database_session(SESSION_URL_2)
# This is a different URL, so the function executes.
```

Example 2 (python):
```python
import streamlit as st

@st.cache_resource
def get_database_session(_sessionmaker, url):
    # Create a database connection object that points to the URL.
    return connection

s1 = get_database_session(create_sessionmaker(), DATA_URL_1)
# Actually executes the function, since this is the first time it was
# encountered.

s2 = get_database_session(create_sessionmaker(), DATA_URL_1)
# Does not execute the function. Instead, returns its previously computed
# value - even though the _sessionmaker parameter was different
# in both calls.
```

Example 3 (python):
```python
import streamlit as st

@st.cache_resource
def get_database_session(_sessionmaker, url):
    # Create a database connection object that points to the URL.
    return connection

fetch_and_clean_data.clear(_sessionmaker, "https://streamlit.io/")
# Clear the cached entry for the arguments provided.

get_database_session.clear()
# Clear all cached entries for this function.
```

Example 4 (python):
```python
import streamlit as st
from pydantic import BaseModel

class Person(BaseModel):
    name: str

@st.cache_resource(hash_funcs={Person: str})
def get_person_name(person: Person):
    return person.name
```

---

## st.vega_lite_chart - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/charts/st.vega_lite_chart

**Contents:**
- st.vega_lite_chart
    - Example
- Chart selections
  - VegaLiteState
    - Examples
- element.add_rows
    - Example
- Theming
  - Still have questions?

Display a chart using the Vega-Lite library.

Vega-Lite is a high-level grammar for defining interactive graphics.

st.vega_lite_chart(data=None, spec=None, *, use_container_width=None, theme="streamlit", key=None, on_select="ignore", selection_mode=None, **kwargs)

data (Anything supported by st.dataframe)

Either the data to be plotted or a Vega-Lite spec containing the data (which more closely follows the Vega-Lite API).

The Vega-Lite spec for the chart. If spec is None (default), Streamlit uses the spec passed in data. You cannot pass a spec to both data and spec. See https://vega.github.io/vega-lite/docs/ for more info.

use_container_width (bool or None)

Whether to override the chart's native width with the width of the parent container. This can be one of the following:

theme ("streamlit" or None)

The theme of the chart. If theme is "streamlit" (default), Streamlit uses its own design default. If theme is None, Streamlit falls back to the default behavior of the library.

The "streamlit" theme can be partially customized through the configuration options theme.chartCategoricalColors and theme.chartSequentialColors. Font configuration options are also applied.

An optional string to use for giving this element a stable identity. If key is None (default), this element's identity will be determined based on the values of the other parameters.

Additionally, if selections are activated and key is provided, Streamlit will register the key in Session State to store the selection state. The selection state is read-only.

on_select ("ignore", "rerun", or callable)

How the figure should respond to user selection events. This controls whether or not the figure behaves like an input widget. on_select can be one of the following:

To use selection events, the Vega-Lite spec defined in data or spec must include selection parameters from the charting library. To learn about defining interactions in Vega-Lite, see Dynamic Behaviors with Parameters in Vega-Lite's documentation.

selection_mode (str or Iterable of str)

The selection parameters Streamlit should use. If selection_mode is None (default), Streamlit will use all selection parameters defined in the chart's Vega-Lite spec.

When Streamlit uses a selection parameter, selections from that parameter will trigger a rerun and be included in the selection state. When Streamlit does not use a selection parameter, selections from that parameter will not trigger a rerun and not be included in the selection st

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(rng(0).standard_normal((60, 3)), columns=["a", "b", "c"])

st.vega_lite_chart(
    df,
    {
        "mark": {"type": "circle", "tooltip": True},
        "encoding": {
            "x": {"field": "a", "type": "quantitative"},
            "y": {"field": "b", "type": "quantitative"},
            "size": {"field": "c", "type": "quantitative"},
            "color": {"field": "c", "type": "quantitative"},
        },
    },
)
```

Example 2 (python):
```python
import altair as alt
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(rng(0).standard_normal((20, 3)), columns=["a", "b", "c"])

point_selector = alt.selection_point("point_selection")
interval_selector = alt.selection_interval("interval_selection")
chart = (
    alt.Chart(df)
    .mark_circle()
    .encode(
        x="a",
        y="b",
        size="c",
        color="c",
        tooltip=["a", "b", "c"],
        fillOpacity=alt.condition(point_selector, alt.value(1), alt.value(0.3)),
    )
    .add_params(point_selector, interval_selec
...
```

Example 3 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(rng(0).standard_normal((20, 3)), columns=["a", "b", "c"])

spec = {
    "mark": {"type": "circle", "tooltip": True},
    "params": [
        {"name": "interval_selection", "select": "interval"},
        {"name": "point_selection", "select": "point"},
    ],
    "encoding": {
        "x": {"field": "a", "type": "quantitative"},
        "y": {"field": "b", "type": "quantitative"},
        "size": {"field": "c", "type": "quantitative"},
        "color": {"field": "c", "type": "quantitative"},
...
```

Example 4 (python):
```python
import time
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df1 = pd.DataFrame(
    rng(0).standard_normal(size=(50, 20)), columns=("col %d" % i for i in range(20))
)

df2 = pd.DataFrame(
    rng(1).standard_normal(size=(50, 20)), columns=("col %d" % i for i in range(20))
)

my_table = st.table(df1)
time.sleep(1)
my_table.add_rows(df2)
```

---

## st.segmented_control - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.segmented_control

**Contents:**
- st.segmented_control
    - Examples
  - Still have questions?

Display a segmented control widget.

A segmented control widget is a linear set of segments where each of the passed options functions like a toggle button.

st.segmented_control(label, options, *, selection_mode="single", default=None, format_func=None, key=None, help=None, on_change=None, args=None, kwargs=None, disabled=False, label_visibility="visible", width="content")

A short label explaining to the user what this widget is for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

For accessibility reasons, you should never set an empty label, but you can hide it with label_visibility if needed. In the future, we may disallow empty labels by raising an exception.

options (Iterable of V)

Labels for the select options in an Iterable. This can be a list, set, or anything supported by st.dataframe. If options is dataframe-like, the first column will be used. Each label will be cast to str internally by default and can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

selection_mode ("single" or "multi")

The selection mode for the widget. If this is "single" (default), only one option can be selected. If this is "multi", multiple options can be selected.

default (Iterable of V, V, or None)

The value of the widget when it first renders. If the selection_mode is multi, this can be a list of values, a single value, or None. If the selection_mode is "single", this can be a single value or None.

format_func (function)

Function to modify the display of the options. It receives the raw option as an argument and should output the label to be shown for that option. This has no impact on the return value of the command. The output can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. Multiple widgets of the sa

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

options = ["North", "East", "South", "West"]
selection = st.segmented_control(
    "Directions", options, selection_mode="multi"
)
st.markdown(f"Your selected options: {selection}.")
```

Example 2 (unknown):
```unknown
import streamlit as st

option_map = {
    0: ":material/add:",
    1: ":material/zoom_in:",
    2: ":material/zoom_out:",
    3: ":material/zoom_out_map:",
}
selection = st.segmented_control(
    "Tool",
    options=option_map.keys(),
    format_func=lambda option: option_map[option],
    selection_mode="single",
)
st.write(
    "Your selected option: "
    f"{None if selection is None else option_map[selection]}"
)
```

---

## st.text_input - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.text_input

**Contents:**
- st.text_input
    - Example
  - Still have questions?

Display a single-line text input widget.

st.text_input(label, value="", max_chars=None, key=None, type="default", help=None, autocomplete=None, on_change=None, args=None, kwargs=None, *, placeholder=None, disabled=False, label_visibility="visible", icon=None, width="stretch")

A short label explaining to the user what this input is for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

For accessibility reasons, you should never set an empty label, but you can hide it with label_visibility if needed. In the future, we may disallow empty labels by raising an exception.

value (object or None)

The text value of this widget when it first renders. This will be cast to str internally. If None, will initialize empty and return None until the user provides input. Defaults to empty string.

max_chars (int or None)

Max number of characters allowed in text input.

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

type ("default" or "password")

The type of the text input. This can be either "default" (for a regular text input), or "password" (for a text input that masks the user's typed value). Defaults to "default".

A tooltip that gets displayed next to the widget label. Streamlit only displays the tooltip when label_visibility="visible". If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

An optional value that will be passed to the <input> element's autocomplete property. If unspecified, this value will be set to "new-password" for "password" inputs, and the empty string for "default" inputs. For more details, see https://developer.mozilla.org/en-US/docs/Web/HTML/Attributes/autocomplete

An optional callback invoked when this text input's value changes.

An optional list or tuple of args to pass to the callback.

An optional dict 

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

title = st.text_input("Movie title", "Life of Brian")
st.write("The current movie title is", title)
```

---

## Caching and state - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/caching-and-state

**Contents:**
- Caching and state
- Caching
    - Cache data
    - Cache resource
- Browser and server state
    - Context
    - Session State
    - Query parameters
- Deprecated commands
    - Get query parameters

Optimize performance and add statefulness to your app!

Streamlit provides powerful cache primitives for data and global resources. They allow your app to stay performant even when loading data from the web, manipulating large datasets, or performing expensive computations.

Function decorator to cache functions that return data (e.g. dataframe transforms, database queries, ML inference).

Function decorator to cache functions that return global resources (e.g. database connections, ML models).

Streamlit re-executes your script with each user interaction. Widgets have built-in statefulness between reruns, but Session State lets you do more!

st.context provides a read-only interface to access cookies, headers, locale, and other browser-session information.

Save data between reruns and across pages.

Get, set, or clear the query parameters that are shown in the browser's URL bar.

Get query parameters that are shown in the browser's URL bar.

Set query parameters that are shown in the browser's URL bar.

Our forums are full of helpful information and Streamlit experts.

---

## st.write - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/write-magic/st.write

**Contents:**
- st.write
    - Examples
  - Featured video
  - Still have questions?

Displays arguments in the app.

This is the Swiss Army knife of Streamlit commands: it does different things depending on what you throw at it. Unlike other Streamlit commands, st.write() has some unique properties:

st.write(*args, unsafe_allow_html=False)

One or many objects to display in the app.

unsafe_allow_html (bool)

Whether to render HTML within *args. This only applies to strings or objects falling back on _repr_html_(). If this is False (default), any HTML tags found in body will be escaped and therefore treated as raw text. If this is True, any HTML expressions within body will be rendered.

Adding custom HTML to your app impacts safety, styling, and maintainability.

If you only want to insert HTML or CSS without Markdown text, we recommend using st.html instead.

Its basic use case is to draw Markdown-formatted text, whenever the input is a string:

As mentioned earlier, st.write() also accepts other data formats, such as numbers, data frames, styled data frames, and assorted objects:

Finally, you can pass in multiple arguments to do things like:

Oh, one more thing: st.write accepts chart objects too! For example:

Learn what the st.write and magic commands are and how to use them.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.write("Hello, *World!* :sunglasses:")
```

Example 2 (unknown):
```unknown
import streamlit as st
import pandas as pd

st.write(1234)
st.write(
    pd.DataFrame(
        {
            "first column": [1, 2, 3, 4],
            "second column": [10, 20, 30, 40],
        }
    )
)
```

Example 3 (unknown):
```unknown
import streamlit as st

st.write("1 + 1 = ", 2)
st.write("Below is a DataFrame:", data_frame, "Above is a dataframe.")
```

Example 4 (python):
```python
import altair as alt
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(rng(0).standard_normal((200, 3)), columns=["a", "b", "c"])
chart = (
    alt.Chart(df)
    .mark_circle()
    .encode(x="a", y="b", size="c", color="c", tooltip=["a", "b", "c"])
)

st.write(chart)
```

---

## st.bokeh_chart - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/charts/st.bokeh_chart

**Contents:**
- st.bokeh_chart
    - Deprecation notice
    - Example
  - Still have questions?

st.bokeh_chart was deprecated in version 1.49.0. Use the streamlit-bokeh custom component instead.

Display an interactive Bokeh chart.

Bokeh is a charting library for Python. The arguments to this function closely follow the ones for Bokeh's show function. You can find more about Bokeh at https://bokeh.pydata.org.

To show Bokeh charts in Streamlit, call st.bokeh_chart wherever you would call Bokeh's show.

You must install bokeh==2.4.3 and numpy<2 to use this command, which is deprecated and will be removed in a future version.

For more current updates, use the streamlit-bokeh custom component instead.

st.bokeh_chart(figure, use_container_width=True)

figure (bokeh.plotting.figure.Figure)

A Bokeh figure to plot.

use_container_width (bool)

Whether to override the figure's native width with the width of the parent container. If use_container_width is True (default), Streamlit sets the width of the figure to match the width of the parent container. If use_container_width is False, Streamlit sets the width of the chart to fit its contents according to the plotting library, up to the width of the parent container.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (python):
```python
import streamlit as st
from bokeh.plotting import figure

x = [1, 2, 3, 4, 5]
y = [6, 7, 2, 4, 5]

p = figure(title="simple line example", x_axis_label="x", y_axis_label="y")
p.line(x, y, legend_label="Trend", line_width=2)

st.bokeh_chart(p)
```

---

## st.audio_input - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.audio_input?utm_source=streamlit

**Contents:**
- st.audio_input
    - Examples
  - Still have questions?

Display a widget that returns an audio recording from the user's microphone.

st.audio_input(label, *, sample_rate=16000, key=None, help=None, on_change=None, args=None, kwargs=None, disabled=False, label_visibility="visible", width="stretch")

A short label explaining to the user what this widget is used for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

For accessibility reasons, you should never set an empty label, but you can hide it with label_visibility if needed. In the future, we may disallow empty labels by raising an exception.

sample_rate (int or None)

The target sample rate for the audio recording in Hz. This defaults to 16000 Hz, which is optimal for speech recognition.

The following sample rates are supported: 8000, 11025, 16000, 22050, 24000, 32000, 44100, or 48000. If this is None, the widget uses the browser's default sample rate (typically 44100 or 48000 Hz).

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

A tooltip that gets displayed next to the widget label. Streamlit only displays the tooltip when label_visibility="visible". If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

An optional callback invoked when this audio input's value changes.

An optional list or tuple of args to pass to the callback.

An optional dict of kwargs to pass to the callback.

An optional boolean that disables the audio input if set to True. Default is False.

label_visibility ("visible", "hidden", or "collapsed")

The visibility of the label. The default is "visible". If this is "hidden", Streamlit displays an empty spacer instead of the label, which can help keep the widget aligned with other widgets. If this is "collapsed", Streamlit displays no label or spacer.

width ("stretch" or int)

The width of the audio inpu

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

audio_value = st.audio_input("Record a voice message")

if audio_value:
    st.audio(audio_value)
```

Example 2 (unknown):
```unknown
import streamlit as st

audio_value = st.audio_input("Record high quality audio", sample_rate=48000)

if audio_value:
    st.audio(audio_value)
```

---

## st.chat_message - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/chat/st.chat_message

**Contents:**
    - Tip
- st.chat_message
    - Examples
  - Still have questions?

Read the Build a basic LLM chat app tutorial to learn how to use st.chat_message and st.chat_input to build chat-based apps.

Insert a chat message container.

To add elements to the returned container, you can use with notation (preferred) or just call methods directly on the returned object. See the examples below.

To follow best design practices and maintain a good appearance on all screen sizes, don't nest chat message containers.

st.chat_message(name, *, avatar=None, width="stretch")

name ("user", "assistant", "ai", "human", or str)

The name of the message author. Can be "human"/"user" or "ai"/"assistant" to enable preset styling and avatars.

Currently, the name is not shown in the UI but is only set as an accessibility label. For accessibility reasons, you should not use an empty string.

avatar (Anything supported by st.image (except list), str, or None)

The avatar shown next to the message.

If avatar is None (default), the icon will be determined from name as follows:

In addition to the types supported by st.image (except list), the following strings are valid:

A single-character emoji. For example, you can set avatar="🧑‍💻" or avatar="🦖". Emoji short codes are not supported.

An icon from the Material Symbols library (rounded style) in the format ":material/icon_name:" where "icon_name" is the name of the icon in snake case.

For example, icon=":material/thumb_up:" will display the Thumb Up icon. Find additional icons in the Material Symbols font library.

width ("stretch", "content", or int)

The width of the chat message container. This can be one of the following:

A single container that can hold multiple elements.

You can use with notation to insert any element into an expander

Or you can just call methods directly in the returned objects:

For an overview of the st.chat_message and st.chat_input API, check out this video tutorial by Chanin Nantasenamat (@dataprofessor), a Senior Developer Advocate at Streamlit.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st
import numpy as np

with st.chat_message("user"):
    st.write("Hello 👋")
    st.line_chart(np.random.randn(30, 3))
```

Example 2 (unknown):
```unknown
import streamlit as st
import numpy as np

message = st.chat_message("assistant")
message.write("Hello human")
message.bar_chart(np.random.randn(30, 3))
```

---

## st.table - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.table

**Contents:**
    - Tip
- st.table
    - Examples
- element.add_rows
    - Example
  - Still have questions?

Static tables with st.table are the most basic way to display dataframes. For the majority of cases, we recommend using st.dataframe to display interactive dataframes, and st.data_editor to let users edit dataframes.

Display a static table.

While st.dataframe is geared towards large datasets and interactive data exploration, st.table is useful for displaying small, styled tables without sorting or scrolling. For example, st.table may be the preferred way to display a confusion matrix or leaderboard. Additionally, st.table supports Markdown.

st.table(data=None, *, border=True)

data (Anything supported by st.dataframe)

All cells including the index and column headers can optionally contain GitHub-flavored Markdown. Syntax information can be found at: https://github.github.com/gfm.

See the body parameter of st.markdown for additional, supported Markdown directives.

border (bool or "horizontal")

Whether to show borders around the table and between cells. This can be one of the following:

Example 1: Display a confusion matrix as a static table

Example 2: Display a product leaderboard with Markdown and horizontal borders

Concatenate a dataframe to the bottom of the current one.

element.add_rows(data=None, **kwargs)

data (pandas.DataFrame, pandas.Styler, pyarrow.Table, numpy.ndarray, pyspark.sql.DataFrame, snowflake.snowpark.dataframe.DataFrame, Iterable, dict, or None)

Table to concat. Optional.

**kwargs (pandas.DataFrame, numpy.ndarray, Iterable, dict, or None)

The named dataset to concat. Optional. You can only pass in 1 dataset (including the one in the data parameter).

You can do the same thing with plots. For example, if you want to add more data to a line chart:

And for plots whose datasets are named, you can pass the data with a keyword argument where the key is the name:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import pandas as pd
import streamlit as st

confusion_matrix = pd.DataFrame(
    {
        "Predicted Cat": [85, 3, 2, 1],
        "Predicted Dog": [2, 78, 4, 0],
        "Predicted Bird": [1, 5, 72, 3],
        "Predicted Fish": [0, 2, 1, 89],
    },
    index=["Actual Cat", "Actual Dog", "Actual Bird", "Actual Fish"],
)
st.table(confusion_matrix)
```

Example 2 (unknown):
```unknown
import streamlit as st

product_data = {
    "Product": [
        ":material/devices: Widget Pro",
        ":material/smart_toy: Smart Device",
        ":material/inventory: Premium Kit",
    ],
    "Category": [":blue[Electronics]", ":green[IoT]", ":violet[Bundle]"],
    "Stock": ["🟢 Full", "🟡 Low", "🔴 Empty"],
    "Units sold": [1247, 892, 654],
    "Revenue": [125000, 89000, 98000],
}
st.table(product_data, border="horizontal")
```

Example 3 (python):
```python
import time
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df1 = pd.DataFrame(
    rng(0).standard_normal(size=(50, 20)), columns=("col %d" % i for i in range(20))
)

df2 = pd.DataFrame(
    rng(1).standard_normal(size=(50, 20)), columns=("col %d" % i for i in range(20))
)

my_table = st.table(df1)
time.sleep(1)
my_table.add_rows(df2)
```

Example 4 (unknown):
```unknown
# Assuming df1 and df2 from the example above still exist...
my_chart = st.line_chart(df1)
time.sleep(1)
my_chart.add_rows(df2)
```

---

## st.experimental_set_query_params - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/caching-and-state/st.experimental_set_query_params

**Contents:**
- st.experimental_set_query_params
    - Deprecation notice
    - Example
  - Still have questions?

st.experimental_set_query_params was deprecated in version 1.30.0. Use st.query_params instead.

Set the query parameters that are shown in the browser's URL bar.

Query param embed cannot be set using this method.

st.experimental_set_query_params(**query_params)

**query_params (dict)

The query parameters to set, as key-value pairs.

To point the user's web browser to something like "http://localhost:8501/?show_map=True&selected=asia&selected=america", you would do the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.experimental_set_query_params(
    show_map=True,
    selected=["asia", "america"],
)
```

---

## st.column_config.TextColumn - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.textcolumn

**Contents:**
- st.column_config.TextColumn
    - Examples
  - Still have questions?

Configure a text column in st.dataframe or st.data_editor.

This is the default column type for string values. This command needs to be used in the column_config parameter of st.dataframe or st.data_editor. When used with st.data_editor, editing will be enabled with a text input widget.

st.column_config.TextColumn(label=None, *, width=None, help=None, disabled=None, required=None, pinned=None, default=None, max_chars=None, validate=None)

The label shown at the top of the column. If this is None (default), the column name is used.

width ("small", "medium", "large", int, or None)

The display width of the column. If this is None (default), the column will be sized to fit the cell contents. Otherwise, this can be one of the following:

If the total width of all columns is less than the width of the dataframe, the remaining space will be distributed evenly among all columns.

A tooltip that gets displayed when hovering over the column label. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

disabled (bool or None)

Whether editing should be disabled for this column. If this is None (default), Streamlit will enable editing wherever possible.

If a column has mixed types, it may become uneditable regardless of disabled.

required (bool or None)

Whether edited cells in the column need to have a value. If this is False (default), the user can submit empty values for this column. If this is True, an edited cell in this column can only be submitted if its value is not None, and a new row will only be submitted after the user fills in this column.

pinned (bool or None)

Whether the column is pinned. A pinned column will stay visible on the left side no matter where the user scrolls. If this is None (default), Streamlit will decide: index columns are pinned, and data columns are not pinned.

default (str or None)

Specifies the default value in this column when a new row is added by the user. This defaults to None.

max_chars (int or None)

The maximum number of characters that can be entered. If this is None (default), there will be no maximum.

validate (str or None)

A JS-flavored regular expression (e.g. "^[a-z]+$") that edited values are validated against. If the user input is invalid, it will not be submitted.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "widgets": ["st.selectbox", "st.number_input", "st.text_area", "st.button"],
    }
)

st.data_editor(
    data_df,
    column_config={
        "widgets": st.column_config.TextColumn(
            "Widgets",
            help="Streamlit **widget** commands 🎈",
            default="st.",
            max_chars=50,
            validate=r"^st\.[a-z_]+$",
        )
    },
    hide_index=True,
)
```

---

## Connections and databases - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/connections

**Contents:**
- Connections and databases
- Setup your connection
    - Create a connection
- Built-in connections
    - SnowflakeConnection
    - SQLConnection
- Third-party connections
    - Connection base class
- Secrets
    - Secrets singleton

Connect to a data source or API

A connection to Snowflake.

A connection to a SQL database using SQLAlchemy.

Build your own connection with BaseConnection.

Access secrets from a local TOML file.

Save your secrets in a per-project or per-profile TOML file.

A connection to Snowflake.

Our forums are full of helpful information and Streamlit experts.

---

## st.logo - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/media/st.logo

**Contents:**
- st.logo
    - Examples
  - Still have questions?

Renders a logo in the upper-left corner of your app and its sidebar.

If st.logo is called multiple times within a page, Streamlit will render the image passed in the last call. For the most consistent results, call st.logo early in your page script and choose an image that works well in both light and dark mode. Avoid empty margins around your image.

If your logo does not work well for both light and dark mode, consider setting the theme and hiding the settings menu from users with the configuration option client.toolbarMode="minimal".

st.logo(image, *, size="medium", link=None, icon_image=None)

image (Anything supported by st.image (except list))

The image to display in the upper-left corner of your app and its sidebar. This can be any of the types supported by st.image except a list. If icon_image is also provided, then Streamlit will only display image in the sidebar.

Streamlit scales the image to a max height set by size and a max width to fit within the sidebar.

size ("small", "medium", or "large")

The size of the image displayed in the upper-left corner of the app and its sidebar. The possible values are as follows:

The external URL to open when a user clicks on the logo. The URL must start with "http://" or "https://". If link is None (default), the logo will not include a hyperlink.

icon_image (Anything supported by st.image (except list) or None)

An optional, typically smaller image to replace image in the upper-left corner when the sidebar is closed. This can be any of the types supported by st.image except a list. If icon_image is None (default), Streamlit will always display image in the upper-left corner, regardless of whether the sidebar is open or closed. Otherwise, Streamlit will render icon_image in the upper-left corner of the app when the sidebar is closed.

Streamlit scales the image to a max height set by size and a max width to fit within the sidebar. If the sidebar is closed, the max width is retained from when it was last open.

For best results, pass a wide or horizontal image to image and a square image to icon_image. Or, pass a square image to image and leave icon_image=None.

A common design practice is to use a wider logo in the sidebar, and a smaller, icon-styled logo in your app's main body.

Try switching logos around in the following example:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.logo(
    LOGO_URL_LARGE,
    link="https://streamlit.io/gallery",
    icon_image=LOGO_URL_SMALL,
)
```

Example 2 (unknown):
```unknown
import streamlit as st

HORIZONTAL_RED = "images/horizontal_red.png"
ICON_RED = "images/icon_red.png"
HORIZONTAL_BLUE = "images/horizontal_blue.png"
ICON_BLUE = "images/icon_blue.png"

options = [HORIZONTAL_RED, ICON_RED, HORIZONTAL_BLUE, ICON_BLUE]
sidebar_logo = st.selectbox("Sidebar logo", options, 0)
main_body_logo = st.selectbox("Main body logo", options, 1)

st.logo(sidebar_logo, icon_image=main_body_logo)
st.sidebar.markdown("Hi!")
```

---

## 2020 release notes - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/quick-reference/release-notes/2020

**Contents:**
- 2020 release notes
- Version 0.73.0
- Version 0.72.0
- Version 0.71.0
- Version 0.70.0
- Version 0.69.0
- Version 0.68.0
- Version 0.67.0
- Version 0.66.0
- Version 0.65.0

This page contains release notes for Streamlit versions released in 2020. For the latest version of Streamlit, see Release notes.

Release date: December 17, 2020

Release date: December 2, 2020

Release date: November 11, 2020

Release date: October 28, 2020

Release date: October 15, 2020

Release date: October 8, 2020

Release date: September 16, 2020

Release date: September 1, 2020

Release date: August 12, 2020

Release date: July 23, 2020

Release date: July 13, 2020

Release date: June 21, 2020

Release date: June 2, 2020

Release date: May 18, 2020

Release date: May 05, 2020

Release date: April 22, 2020

Release date: March 26, 2020

Release date: February 15, 2020

Release date: February 4, 2020

Release date: January 29, 2020

Release date: January 14, 2020

🗺️ Support for all DeckGL features! Just use Pydeck instead of st.deck_gl_chart. To do that, simply pass a PyDeck object to st.pydeck_chart, st.write, or magic.

Note that as a preview release things may change in the near future. Looking forward to hearing input from the community before we stabilize the API!

The goals is for this to replace st.deck_gl_chart, since it is does everything the old API did and much more!

🆕 Better handling of Streamlit upgrades while developing. We now auto-reload the browser tab if the app it is displaying uses a newer version of Streamlit than the one the tab is running.

👑 New favicon, with our new logo!

Updated how we calculate the default width and height of all chart types. We now leave chart sizing up to your charting library itself, so please refer to the library's documentation.

As a result, the width and height arguments have been deprecated from most chart commands, and use_container_width has been introduced everywhere to allow you to make charts fill as much horizontal space as possible (this used to be the default).

Our forums are full of helpful information and Streamlit experts.

---

## st.column_config.MultiselectColumn - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.multiselectcolumn?utm_source=streamlit

**Contents:**
- st.column_config.MultiselectColumn
    - Examples
  - Still have questions?

Configure a multiselect column in st.dataframe or st.data_editor.

This command needs to be used in the column_config parameter of st.dataframe or st.data_editor. When used with st.data_editor, users can select options from a dropdown menu. You can configure the column to allow freely typed options, too.

You can also use this column type to display colored labels in a read-only st.dataframe.

Editing for non-string or mixed type lists can cause issues with Arrow serialization. We recommend that you disable editing for these columns or convert all list values to strings.

st.column_config.MultiselectColumn(label=None, *, width=None, help=None, disabled=None, required=None, default=None, options=None, accept_new_options=None, color=None, format_func=None)

The label shown at the top of the column. If None (default), the column name is used.

width ("small", "medium", "large", or None)

The display width of the column. If this is None (default), the column will be sized to fit the cell contents. Otherwise, this can be one of the following:

If the total width of all columns is less than the width of the dataframe, the remaining space will be distributed evenly among all columns.

A tooltip that gets displayed when hovering over the column label. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

disabled (bool or None)

Whether editing should be disabled for this column. Defaults to False.

required (bool or None)

Whether edited cells in the column need to have a value. If True, an edited cell can only be submitted if it has a value other than None. Defaults to False.

default (Iterable of str or None)

Specifies the default value in this column when a new row is added by the user.

options (Iterable of str or None)

The options that can be selected during editing.

accept_new_options (bool or None)

Whether the user can add selections that aren't included in options. If this is False (default), the user can only select from the items in options. If this is True, the user can enter new items that don't exist in options.

When a user enters and selects a new item, it is included in the returned cell list value as a string. The new item is not added to the options drop-down menu.

color (str, Iterable of str, or None)

The color to use for different options. This can be:

None (default): The options are displayed wi

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "category": [
            ["exploration", "visualization"],
            ["llm", "visualization"],
            ["exploration"],
        ],
    }
)

st.data_editor(
    data_df,
    column_config={
        "category": st.column_config.MultiselectColumn(
            "App Categories",
            help="The categories of the app",
            options=[
                "exploration",
                "visualization",
                "llm",
            ],
            color=["#ffa421", "#803df5", "#00c0f2"],
            f
...
```

Example 2 (unknown):
```unknown
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "category": [
            ["exploration", "visualization"],
            ["llm", "visualization"],
            ["exploration"],
        ],
    }
)

st.dataframe(
    data_df,
    column_config={
        "category": st.column_config.MultiselectColumn(
            "App Categories",
            options=["exploration", "visualization", "llm"],
            color="primary",
            format_func=lambda x: x.capitalize(),
        ),
    },
)
```

---

## st.column_config.ListColumn - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.listcolumn

**Contents:**
- st.column_config.ListColumn
    - Examples
  - Still have questions?

Configure a list column in st.dataframe or st.data_editor.

This is the default column type for list-like values. This command needs to be used in the column_config parameter of st.dataframe or st.data_editor. When used with st.data_editor, users can freely type in new options and remove existing ones.

Editing for non-string or mixed type lists can cause issues with Arrow serialization. We recommend that you disable editing for these columns or convert all list values to strings.

st.column_config.ListColumn(label=None, *, width=None, help=None, pinned=None, disabled=None, required=None, default=None)

The label shown at the top of the column. If this is None (default), the column name is used.

width ("small", "medium", "large", int, or None)

The display width of the column. If this is None (default), the column will be sized to fit the cell contents. Otherwise, this can be one of the following:

If the total width of all columns is less than the width of the dataframe, the remaining space will be distributed evenly among all columns.

A tooltip that gets displayed when hovering over the column label. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

pinned (bool or None)

Whether the column is pinned. A pinned column will stay visible on the left side no matter where the user scrolls. If this is None (default), Streamlit will decide: index columns are pinned, and data columns are not pinned.

disabled (bool or None)

Whether editing should be disabled for this column. If this is None (default), Streamlit will enable editing wherever possible.

If a column has mixed types, it may become uneditable regardless of disabled.

required (bool or None)

Whether edited cells in the column need to have a value. If this is False (default), the user can submit empty values for this column. If this is True, an edited cell in this column can only be submitted if its value is not None, and a new row will only be submitted after the user fills in this column.

default (Iterable of str or None)

Specifies the default value in this column when a new row is added by the user. This defaults to None.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "sales": [
            [0, 4, 26, 80, 100, 40],
            [80, 20, 80, 35, 40, 100],
            [10, 20, 80, 80, 70, 0],
            [10, 100, 20, 100, 30, 100],
        ],
    }
)

st.data_editor(
    data_df,
    column_config={
        "sales": st.column_config.ListColumn(
            "Sales (last 6 months)",
            help="The sales volume in the last 6 months",
            width="medium",
        ),
    },
    hide_index=True,
)
```

---

## 2022 release notes - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/quick-reference/release-notes/2022

**Contents:**
- 2022 release notes
- Version 1.16.0
- Version 1.15.0
- Version 1.14.0
- Version 1.13.0
- Version 1.12.0
- Version 1.11.0
- Version 1.10.0
- Version 1.9.0
- Version 1.8.0

This page contains release notes for Streamlit versions released in 2022. For the latest version of Streamlit, see Release notes.

Release date: December 14, 2022

Release date: November 17, 2022

Release date: October 27, 2022

Release date: September 22, 2022

Release date: August 11, 2022

Release date: July 14, 2022

Release date: June 2, 2022

Release date: May 4, 2022

Release date: March 24, 2022

Release date: March 3, 2022

Release date: Feb 24, 2022

Release date: Jan 27, 2022

Release date: Jan 13, 2022

Our forums are full of helpful information and Streamlit experts.

---

## st.column_config.DateColumn - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.datecolumn

**Contents:**
- st.column_config.DateColumn
    - Examples
  - Still have questions?

Configure a date column in st.dataframe or st.data_editor.

This is the default column type for date values. This command needs to be used in the column_config parameter of st.dataframe or st.data_editor. When used with st.data_editor, editing will be enabled with a date picker widget.

st.column_config.DateColumn(label=None, *, width=None, help=None, disabled=None, required=None, pinned=None, default=None, format=None, min_value=None, max_value=None, step=None)

The label shown at the top of the column. If this is None (default), the column name is used.

width ("small", "medium", "large", int, or None)

The display width of the column. If this is None (default), the column will be sized to fit the cell contents. Otherwise, this can be one of the following:

If the total width of all columns is less than the width of the dataframe, the remaining space will be distributed evenly among all columns.

A tooltip that gets displayed when hovering over the column label. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

disabled (bool or None)

Whether editing should be disabled for this column. If this is None (default), Streamlit will enable editing wherever possible.

If a column has mixed types, it may become uneditable regardless of disabled.

required (bool or None)

Whether edited cells in the column need to have a value. If this is False (default), the user can submit empty values for this column. If this is True, an edited cell in this column can only be submitted if its value is not None, and a new row will only be submitted after the user fills in this column.

pinned (bool or None)

Whether the column is pinned. A pinned column will stay visible on the left side no matter where the user scrolls. If this is None (default), Streamlit will decide: index columns are pinned, and data columns are not pinned.

default (datetime.date or None)

Specifies the default value in this column when a new row is added by the user. This defaults to None.

format (str, "localized", "distance", "iso8601", or None)

A format string controlling how dates are displayed. This can be one of the following values:

Formatting from column_config always takes precedence over formatting from pandas.Styler. The formatting does not impact the return value when used in st.data_editor.

min_value (datetime.date or None)

The minimum date th

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
from datetime import date
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "birthday": [
            date(1980, 1, 1),
            date(1990, 5, 3),
            date(1974, 5, 19),
            date(2001, 8, 17),
        ]
    }
)

st.data_editor(
    data_df,
    column_config={
        "birthday": st.column_config.DateColumn(
            "Birthday",
            min_value=date(1900, 1, 1),
            max_value=date(2005, 1, 1),
            format="DD.MM.YYYY",
            step=1,
        ),
    },
    hide_index=True,
)
```

---

## st.divider - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/text/st.divider

**Contents:**
- st.divider
    - Example
  - Still have questions?

Display a horizontal rule.

You can achieve the same effect with st.write("---") or even just "---" in your script (via magic).

st.divider(*, width="stretch")

width ("stretch" or int)

The width of the divider element. This can be one of the following:

Here's what it looks like in action when you have multiple elements in the app:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.divider()
```

---

## st.success - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/status/st.success

**Contents:**
- st.success
    - Example
  - Still have questions?

Display a success message.

st.success(body, *, icon=None, width="stretch")

The text to display as GitHub-flavored Markdown. Syntax information can be found at: https://github.github.com/gfm.

See the body parameter of st.markdown for additional, supported Markdown directives.

An optional emoji or icon to display next to the alert. If icon is None (default), no icon is displayed. If icon is a string, the following options are valid:

A single-character emoji. For example, you can set icon="🚨" or icon="🔥". Emoji short codes are not supported.

An icon from the Material Symbols library (rounded style) in the format ":material/icon_name:" where "icon_name" is the name of the icon in snake case.

For example, icon=":material/thumb_up:" will display the Thumb Up icon. Find additional icons in the Material Symbols font library.

width ("stretch" or int)

The width of the success element. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.success('This is a success message!', icon="✅")
```

---

## st.connections.SQLConnection - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/connections/st.connections.sqlconnection

**Contents:**
    - Tip
- st.connections.SQLConnection
    - Examples
- SQLConnection.connect
- SQLConnection.query
    - Example
- SQLConnection.reset
    - Example
- SQLConnection.driver
- SQLConnection.engine

This page only contains the st.connections.SQLConnection class. For a deeper dive into creating and managing data connections within Streamlit apps, read Connecting to data.

A connection to a SQL database using a SQLAlchemy Engine.

Initialize this connection object using st.connection("sql") or st.connection("<name>", type="sql"). Connection parameters for a SQLConnection can be specified using secrets.toml and/or **kwargs. Possible connection parameters include:

If url exists as a connection parameter, Streamlit will pass it to sqlalchemy.engine.make_url(). Otherwise, Streamlit requires (at a minimum) dialect, username, and host. Streamlit will use dialect and driver (if defined) to derive drivername, then pass the relevant connection parameters to sqlalchemy.engine.URL.create().

In addition to the default keyword arguments for sqlalchemy.create_engine(), your dialect may accept additional keyword arguments. For example, if you use dialect="snowflake" with Snowflake SQLAlchemy, you can pass a value for private_key to use key-pair authentication. If you use dialect="bigquery" with Google BigQuery, you can pass a value for location.

SQLConnection provides the .query() convenience method, which can be used to run simple, read-only queries with both caching and simple error handling/retries. More complex database interactions can be performed by using the .session property to receive a regular SQLAlchemy Session.

SQLAlchemy must be installed in your environment to use this connection. You must also install your driver, such as pyodbc or psycopg2.

st.connections.SQLConnection(connection_name, **kwargs)

Call .connect() on the underlying SQLAlchemy Engine, returning a new connection object.

query(sql, *, show_spinner="Running `sql.query(...)`.", ttl=None, index_col=None, chunksize=None, params=None, **kwargs)

Run a read-only query.

Reset this connection so that it gets reinitialized the next time it's used.

The name of the driver used by the underlying SQLAlchemy Engine.

The underlying SQLAlchemy Engine.

Return a SQLAlchemy Session.

Example 1: Configuration with URL

You can configure your SQL connection using Streamlit's Secrets management. The following example specifies a SQL connection URL.

.streamlit/secrets.toml:

Example 2: Configuration with dialect, host, and username

If you do not specify url, you must at least specify dialect, host, and username instead. The following example also includes password.

.streamlit/secrets.toml:

Example 

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
[connections.sql]
url = "xxx+xxx://xxx:xxx@xxx:xxx/xxx"
```

Example 2 (unknown):
```unknown
import streamlit as st

conn = st.connection("sql")
df = conn.query("SELECT * FROM pet_owners")
st.dataframe(df)
```

Example 3 (unknown):
```unknown
[connections.sql]
dialect = "xxx"
host = "xxx"
username = "xxx"
password = "xxx"
```

Example 4 (unknown):
```unknown
import streamlit as st

conn = st.connection("sql")
df = conn.query("SELECT * FROM pet_owners")
st.dataframe(df)
```

---

## st.user - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/user/st.user

**Contents:**
- st.user
    - Examples
  - Community Cloud
- st.user.to_dict
  - Still have questions?

A read-only, dict-like object for accessing information about the current user.

st.user is dependent on the host platform running your Streamlit app. If your host platform has not configured the object, st.user will behave as it does in a locally running app.

When authentication is configured in secrets.toml, Streamlit will parse the OpenID Connect (OIDC) identity token and copy the attributes to st.user. Check your provider's documentation for their available attributes (known as claims).

When authentication is not configured, st.user has no attributes.

You can access values via key or attribute notation. For example, use st.user["email"] or st.user.email to access the email attribute.

Identity tokens include an issuance and expiration time. Streamlit does not implicitly check these. If you want to automatically expire a user's authentication, check these values manually and programmatically log out your user (st.logout()) when needed.

Get user info as a dictionary.

Whether a user is logged in. For a locally running app, this attribute is only available when authentication (st.login()) is configured in secrets.toml. Otherwise, it does not exist.

Example 1: Google's identity token

If you configure a basic Google OIDC connection as shown in Example 1 of st.login(), the following data is available in st.user. Streamlit adds the is_logged_in attribute. Additional attributes may be available depending on the configuration of the user's Google account. For more information about Google's identity tokens, see Obtain user information from the ID token in Google's docs.

Displayed data when a user is logged in:

Example 2: Microsoft's identity token

If you configure a basic Microsoft OIDC connection as shown in Example 2 of st.login(), the following data is available in st.user. For more information about Microsoft's identity tokens, see ID token claims reference in Microsoft's docs.

Displayed data when a user is logged in:

Starting from Streamlit version 1.42.0, you can't use st.user to retrieve a user's Community Cloud account email. To access user information, you must set up an identity provider and configure authentication ([auth]) in your app's secrets. Remember to update your identity provider's configuration and your app's secrets to allow your new domain. A list of IP addresses used by Community Cloud is available if needed. An authentication-configured app counts as your single allowed private app.

Get user info as a dictionary.

This method

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

if st.user.is_logged_in:
    st.write(st.user)
```

Example 2 (unknown):
```unknown
{
    "is_logged_in":true
    "iss":"https://accounts.google.com"
    "azp":"{client_id}.apps.googleusercontent.com"
    "aud":"{client_id}.apps.googleusercontent.com"
    "sub":"{unique_user_id}"
    "email":"{user}@gmail.com"
    "email_verified":true
    "at_hash":"{access_token_hash}"
    "nonce":"{nonce_string}"
    "name":"{full_name}"
    "picture":"https://lh3.googleusercontent.com/a/{content_path}"
    "given_name":"{given_name}"
    "family_name":"{family_name}"
    "iat":{issued_time}
    "exp":{expiration_time}
}
```

Example 3 (unknown):
```unknown
import streamlit as st

if st.user.is_logged_in:
    st.write(st.user)
```

Example 4 (unknown):
```unknown
{
    "is_logged_in":true
    "ver":"2.0"
    "iss":"https://login.microsoftonline.com/{tenant_id}/v2.0"
    "sub":"{application_user_id}"
    "aud":"{application_id}"
    "exp":{expiration_time}
    "iat":{issued_time}
    "nbf":{start_time}
    "name":"{full_name}"
    "preferred_username":"{username}"
    "oid":"{user_GUID}"
    "email":"{email}"
    "tid":"{tenant_id}"
    "nonce":"{nonce_string}"
    "aio":"{opaque_string}"
}
```

---

## Magic - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/write-magic/magic

**Contents:**
- Magic
  - How Magic works
    - Important
  - Featured video
  - Still have questions?

Magic commands are a feature in Streamlit that allows you to write almost anything (markdown, data, charts) without having to type an explicit command at all. Just put the thing you want to show on its own line of code, and it will appear in your app. Here's an example:

Any time Streamlit sees either a variable or literal value on its own line, it automatically writes that to your app using st.write (which you'll learn about later).

Also, magic is smart enough to ignore docstrings. That is, it ignores the strings at the top of files and functions.

If you prefer to call Streamlit commands more explicitly, you can always turn magic off in your ~/.streamlit/config.toml with the following setting:

Right now, Magic only works in the main Python app file, not in imported files. See GitHub issue #288 for a discussion of the issues.

Learn what the st.write and magic commands are and how to use them.

Our forums are full of helpful information and Streamlit experts.

---

## Display progress and status - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/status

**Contents:**
- Display progress and status
- Animated status elements
    - Progress bar
    - Spinner
    - Status container
    - Toast
    - Balloons
    - Snowflakes
- Simple callout messages
    - Success box

Streamlit provides a few methods that allow you to add animation to your apps. These animations include progress bars, status messages (like warnings), and celebratory balloons.

Display a progress bar.

Temporarily displays a message while executing a block of code.

Display output of long-running tasks in a container.

Briefly displays a toast message in the bottom-right corner.

Display celebratory balloons!

Display celebratory snowflakes!

Display a success message.

Display an informational message.

Display warning message.

Display error message.

Display an exception.

Third-party components

These are featured components created by our lovely community. For more examples and inspiration, check out our Components Gallery and Streamlit Extras!

The simplest way to handle a progress bar in streamlit app. Created by @Wirg.

A custom notification box with the ability to close it out. Created by @Socvest.

A library with useful Streamlit extras. Created by @arnaudmiribel.

Our forums are full of helpful information and Streamlit experts.

---

## st.column_config.SelectboxColumn - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.selectboxcolumn

**Contents:**
- st.column_config.SelectboxColumn
    - Examples
  - Still have questions?

Configure a selectbox column in st.dataframe or st.data_editor.

This is the default column type for Pandas categorical values. This command needs to be used in the column_config parameter of st.dataframe or st.data_editor. When used with st.data_editor, editing will be enabled with a selectbox widget.

st.column_config.SelectboxColumn(label=None, *, width=None, help=None, disabled=None, required=None, pinned=None, default=None, options=None, format_func=None)

The label shown at the top of the column. If this is None (default), the column name is used.

width ("small", "medium", "large", int, or None)

The display width of the column. If this is None (default), the column will be sized to fit the cell contents. Otherwise, this can be one of the following:

If the total width of all columns is less than the width of the dataframe, the remaining space will be distributed evenly among all columns.

A tooltip that gets displayed when hovering over the column label. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

disabled (bool or None)

Whether editing should be disabled for this column. If this is None (default), Streamlit will enable editing wherever possible.

If a column has mixed types, it may become uneditable regardless of disabled.

required (bool or None)

Whether edited cells in the column need to have a value. If this is False (default), the user can submit empty values for this column. If this is True, an edited cell in this column can only be submitted if its value is not None, and a new row will only be submitted after the user fills in this column.

pinned (bool or None)

Whether the column is pinned. A pinned column will stay visible on the left side no matter where the user scrolls. If this is None (default), Streamlit will decide: index columns are pinned, and data columns are not pinned.

default (str, int, float, bool, or None)

Specifies the default value in this column when a new row is added by the user. This defaults to None.

options (Iterable[str, int, float, bool] or None)

The options that can be selected during editing. If this is None (default), the options will be inferred from the underlying dataframe column if its dtype is "category". For more information, see Pandas docs).

format_func (function or None)

Function to modify the display of the options. It receives the raw option d

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "category": [
            "📊 Data Exploration",
            "📈 Data Visualization",
            "🤖 LLM",
            "📊 Data Exploration",
        ],
    }
)

st.data_editor(
    data_df,
    column_config={
        "category": st.column_config.SelectboxColumn(
            "App Category",
            help="The category of the app",
            width="medium",
            options=[
                "📊 Data Exploration",
                "📈 Data Visualization",
                "🤖 LLM",
            ],
            requ
...
```

---

## st.scatter_chart - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/charts/st.scatter_chart

**Contents:**
- st.scatter_chart
    - Examples
- element.add_rows
    - Example
  - Still have questions?

Display a scatterplot chart.

This is syntax-sugar around st.altair_chart. The main difference is this command uses the data's own column and indices to figure out the chart's Altair spec. As a result this is easier to use for many "just plot this" scenarios, while being less customizable.

st.scatter_chart(data=None, *, x=None, y=None, x_label=None, y_label=None, color=None, size=None, width=None, height=None, use_container_width=True)

data (Anything supported by st.dataframe)

Column name or key associated to the x-axis data. If x is None (default), Streamlit uses the data index for the x-axis values.

y (str, Sequence of str, or None)

Column name(s) or key(s) associated to the y-axis data. If this is None (default), Streamlit draws the data of all remaining columns as data series. If this is a Sequence of strings, Streamlit draws several series on the same chart by melting your wide-format table into a long-format table behind the scenes.

x_label (str or None)

The label for the x-axis. If this is None (default), Streamlit will use the column name specified in x if available, or else no label will be displayed.

y_label (str or None)

The label for the y-axis. If this is None (default), Streamlit will use the column name(s) specified in y if available, or else no label will be displayed.

color (str, tuple, Sequence of str, Sequence of tuple, or None)

The color of the circles representing each datapoint.

None, to use the default color.

A hex string like "#ffaa00" or "#ffaa0088".

An RGB or RGBA tuple with the red, green, blue, and alpha components specified as ints from 0 to 255 or floats from 0.0 to 1.0.

The name of a column in the dataset where the color of that datapoint will come from.

If the values in this column are in one of the color formats above (hex string or color tuple), then that color will be used.

Otherwise, the color will be automatically picked from the default palette.

For example: if the dataset has 1000 rows, but this column only contains the values "adult", "child", and "baby", then those 1000 datapoints be shown using three colors from the default palette.

But if this column only contains floats or ints, then those 1000 datapoints will be shown using a colors from a continuous color gradient.

Finally, if this column only contains the values "#ffaa00", "#f0f", "#0000ff", then then each of those 1000 datapoints will be assigned "#ffaa00", "#f0f", or "#0000ff" as appropriate.

If the dataframe is in wide format (that is, 

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(rng(0).standard_normal((20, 3)), columns=["a", "b", "c"])

st.scatter_chart(df)
```

Example 2 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(
    rng(0).standard_normal((20, 3)), columns=["col1", "col2", "col3"]
)
df["col4"] = rng(0).choice(["a", "b", "c"], 20)

st.scatter_chart(
    df,
    x="col1",
    y="col2",
    color="col4",
    size="col3",
)
```

Example 3 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(
    rng(0).standard_normal((20, 4)),
    columns=["col1", "col2", "col3", "col4"],
)

st.scatter_chart(
    df,
    x="col1",
    y=["col2", "col3"],
    size="col4",
    color=["#FF0000", "#0000FF"],
)
```

Example 4 (python):
```python
import time
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df1 = pd.DataFrame(
    rng(0).standard_normal(size=(50, 20)), columns=("col %d" % i for i in range(20))
)

df2 = pd.DataFrame(
    rng(1).standard_normal(size=(50, 20)), columns=("col %d" % i for i in range(20))
)

my_table = st.table(df1)
time.sleep(1)
my_table.add_rows(df2)
```

---

## st.text - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/text/st.text

**Contents:**
- st.text
    - Example
  - Still have questions?

Write text without Markdown or HTML parsing.

For monospace text, use st.code.

st.text(body, *, help=None, width="content")

The string to display.

A tooltip that gets displayed next to the text. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

width ("content", "stretch", or int)

The width of the text element. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.text("This is text\n[and more text](that's not a Markdown link).")
```

---

## st.connections.SnowparkConnection - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/connections/st.connections.snowparkconnection

**Contents:**
    - Tip
- st.connections.SnowparkConnection
    - Deprecation notice
- SnowparkConnection.query
    - Example
- SnowparkConnection.reset
    - Example
- SnowparkConnection.safe_session
    - Example
- SnowparkConnection.session

This page only contains the st.connections.SnowparkConnection class. For a deeper dive into creating and managing data connections within Streamlit apps, read Connecting to data.

st.connections.SnowParkConnection was deprecated in version 1.28.0. Use st.connections.SnowflakeConnection instead.

A connection to Snowpark using snowflake.snowpark.session.Session. Initialize using

st.connection("<name>", type="snowpark").

In addition to providing access to the Snowpark Session, SnowparkConnection supports direct SQL querying using query("...") and thread safe access using with conn.safe_session():. See methods below for more information. SnowparkConnections should always be created using st.connection(), not initialized directly.

We don't expect this iteration of SnowparkConnection to be able to scale well in apps with many concurrent users due to the lock contention that will occur over the single underlying Session object under high load.

st.connections.SnowparkConnection(connection_name, **kwargs)

Run a read-only SQL query.

Reset this connection so that it gets reinitialized the next time it's used.

Grab the underlying Snowpark session in a thread-safe manner.

Access the underlying Snowpark session.

Run a read-only SQL query.

This method implements both query result caching (with caching behavior identical to that of using @st.cache_data) as well as simple error handling/retries.

Queries that are run without a specified ttl are cached indefinitely.

SnowparkConnection.query(sql, ttl=None)

The read-only SQL query to execute.

ttl (float, int, timedelta or None)

The maximum number of seconds to keep results in the cache, or None if cached results should not expire. The default is None.

The result of running the query, formatted as a pandas DataFrame.

Reset this connection so that it gets reinitialized the next time it's used.

This method can be useful when a connection has become stale, an auth token has expired, or in similar scenarios where a broken connection might be fixed by reinitializing it. Note that some connection methods may already use reset() in their error handling code.

SnowparkConnection.reset()

Grab the underlying Snowpark session in a thread-safe manner.

As operations on a Snowpark session are not thread safe, we need to take care when using a session in the context of a Streamlit app where each script run occurs in its own thread. Using the contextmanager pattern to do this ensures that access on this connection's underl

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

conn = st.connection("snowpark")
df = conn.query("SELECT * FROM pet_owners")
st.dataframe(df)
```

Example 2 (unknown):
```unknown
import streamlit as st

conn = st.connection("my_conn")

# Reset the connection before using it if it isn't healthy
# Note: is_healthy() isn't a real method and is just shown for example here.
if not conn.is_healthy():
    conn.reset()

# Do stuff with conn...
```

Example 3 (unknown):
```unknown
import streamlit as st

conn = st.connection("snowpark")
with conn.safe_session() as session:
    df = session.table("mytable").limit(10).to_pandas()

st.dataframe(df)
```

Example 4 (unknown):
```unknown
import streamlit as st

session = st.connection("snowpark").session
df = session.table("mytable").limit(10).to_pandas()
st.dataframe(df)
```

---

## Chat elements - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/chat

**Contents:**
- Chat elements
    - Chat input
    - Chat message
    - Status container
    - st.write_stream
  - Still have questions?

Streamlit provides a few commands to help you build conversational apps. These chat elements are designed to be used in conjunction with each other, but you can also use them separately.

st.chat_message lets you insert a chat message container into the app so you can display messages from the user or the app. Chat containers can contain other Streamlit elements, including charts, tables, text, and more. st.chat_input lets you display a chat input widget so the user can type in a message. Remember to check out st.status to display output from long-running processes and external API calls.

Display a chat input widget.

Insert a chat message container.

Display output of long-running tasks in a container.

Write generators or streams to the app with a typewriter effect.

Our forums are full of helpful information and Streamlit experts.

---

## streamlit init - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/cli/init

**Contents:**
- $ streamlit init
  - Syntax
  - Arguments
  - Examples
    - Example 1: Create project files the current working directory
    - Example 2: Create project files in another directory
  - Still have questions?

This command creates the files for a new Streamlit app.

<directory> (Optional): The directory location of the new project. If no directory is provided, the current working directory will be used.

In your current working directory (CWD), execute the following:

Streamlit creates the following files:

In your terminal, Streamlit prompts, ❓ Run the app now? [Y/n]. Enter Y for yes.

This is equivalent to executing streamlit run streamlit_app.py from your current working directory.

Begin editing your streamlit_app.py file and save your changes.

In your current working directory (CWD), execute the following:

Streamlit creates the following files:

In your terminal, Streamlit prompts, ❓ Run the app now? [Y/n]. Enter Y for yes.

This is equivalent to executing streamlit run project/streamlit_app.py from your current working directory.

Begin editing your streamlit_app.py file and save your changes.

Our forums are full of helpful information and Streamlit experts.

---

## st.dialog - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/execution-flow/st.dialog

**Contents:**
- st.dialog
    - Examples
  - Still have questions?

Function decorator to create a modal dialog.

A function decorated with @st.dialog becomes a dialog function. When you call a dialog function, Streamlit inserts a modal dialog into your app. Streamlit element commands called within the dialog function render inside the modal dialog.

The dialog function can accept arguments that can be passed when it is called. Any values from the dialog that need to be accessed from the wider app should generally be stored in Session State.

If a dialog is dismissible, a user can dismiss it by clicking outside of it, clicking the "X" in its upper-right corner, or pressing ESC on their keyboard. You can configure whether this triggers a rerun of the app by setting the on_dismiss parameter.

If a dialog is not dismissible, it must be closed programmatically by calling st.rerun() inside the dialog function. This is useful when you want to ensure that the dialog is always closed programmatically, such as when the dialog contains a form that must be submitted before closing.

st.dialog inherits behavior from st.fragment. When a user interacts with an input widget created inside a dialog function, Streamlit only reruns the dialog function instead of the full script.

Calling st.sidebar in a dialog function is not supported.

Dialog code can interact with Session State, imported modules, and other Streamlit elements created outside the dialog. Note that these interactions are additive across multiple dialog reruns. You are responsible for handling any side effects of that behavior.

Only one dialog function may be called in a script run, which means that only one dialog can be open at any given time.

st.dialog(title, *, width="small", dismissible=True, on_dismiss="ignore")

The title to display at the top of the modal dialog. It cannot be empty.

The title can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

width ("small", "medium", "large")

The width of the modal dialog. This can be one of the following:

Whether the modal dialog can be dismissed by the user. If this is True (default), the

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import streamlit as st

@st.dialog("Cast your vote")
def vote(item):
    st.write(f"Why is {item} your favorite?")
    reason = st.text_input("Because...")
    if st.button("Submit"):
        st.session_state.vote = {"item": item, "reason": reason}
        st.rerun()

if "vote" not in st.session_state:
    st.write("Vote for your favorite")
    if st.button("A"):
        vote("A")
    if st.button("B"):
        vote("B")
else:
    f"You voted for {st.session_state.vote['item']} because {st.session_state.vote['reason']}"
```

---

## st.column_config.LinkColumn - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.linkcolumn

**Contents:**
- st.column_config.LinkColumn
    - Examples
  - Still have questions?

Configure a link column in st.dataframe or st.data_editor.

The cell values need to be string and will be shown as clickable links. This command needs to be used in the column_config parameter of st.dataframe or st.data_editor. When used with st.data_editor, editing will be enabled with a text input widget.

st.column_config.LinkColumn(label=None, *, width=None, help=None, disabled=None, required=None, pinned=None, default=None, max_chars=None, validate=None, display_text=None)

The label shown at the top of the column. If this is None (default), the column name is used.

width ("small", "medium", "large", int, or None)

The display width of the column. If this is None (default), the column will be sized to fit the cell contents. Otherwise, this can be one of the following:

If the total width of all columns is less than the width of the dataframe, the remaining space will be distributed evenly among all columns.

A tooltip that gets displayed when hovering over the column label. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

disabled (bool or None)

Whether editing should be disabled for this column. If this is None (default), Streamlit will enable editing wherever possible.

If a column has mixed types, it may become uneditable regardless of disabled.

required (bool or None)

Whether edited cells in the column need to have a value. If this is False (default), the user can submit empty values for this column. If this is True, an edited cell in this column can only be submitted if its value is not None, and a new row will only be submitted after the user fills in this column.

pinned (bool or None)

Whether the column is pinned. A pinned column will stay visible on the left side no matter where the user scrolls. If this is None (default), Streamlit will decide: index columns are pinned, and data columns are not pinned.

default (str or None)

Specifies the default value in this column when a new row is added by the user. This defaults to None.

max_chars (int or None)

The maximum number of characters that can be entered. If this is None (default), there will be no maximum.

validate (str or None)

A JS-flavored regular expression (e.g. "^https://.+$") that edited values are validated against. If the user input is invalid, it will not be submitted.

display_text (str or None)

The text that is displayed in t

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "apps": [
            "https://roadmap.streamlit.app",
            "https://extras.streamlit.app",
            "https://issues.streamlit.app",
            "https://30days.streamlit.app",
        ],
        "creator": [
            "https://github.com/streamlit",
            "https://github.com/arnaudmiribel",
            "https://github.com/streamlit",
            "https://github.com/streamlit",
        ],
    }
)

st.data_editor(
    data_df,
    column_config={
        "apps": st.column_config.LinkColumn(
     
...
```

---

## st.experimental_get_query_params - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/caching-and-state/st.experimental_get_query_params

**Contents:**
- st.experimental_get_query_params
    - Deprecation notice
    - Example
  - Still have questions?

st.experimental_get_query_params was deprecated in version 1.30.0. Use st.query_params instead.

Return the query parameters that is currently showing in the browser's URL bar.

st.experimental_get_query_params()

The current query parameters as a dict. "Query parameters" are the part of the URL that comes after the first "?".

Let's say the user's web browser is at http://localhost:8501/?show_map=True&selected=asia&selected=america. Then, you can get the query parameters using the following:

Note that the values in the returned dict are always lists. This is because we internally use Python's urllib.parse.parse_qs(), which behaves this way. And this behavior makes sense when you consider that every item in a query string is potentially a 1-element array.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.experimental_get_query_params()
{"show_map": ["True"], "selected": ["asia", "america"]}
```

---

## st.stop - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/execution-flow/st.stop

**Contents:**
- st.stop
    - Example
  - Still have questions?

Stops execution immediately.

Streamlit will not run any statements after st.stop(). We recommend rendering a message to explain why the script has stopped.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

name = st.text_input("Name")
if not name:
  st.warning('Please input a name.')
  st.stop()
st.success("Thank you for inputting a name.")
```

---

## st.logout - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/user/st.logout

**Contents:**
    - Tip
- st.logout
    - Example
  - Still have questions?

Learn more in User authentication and information.

Logout the current user.

This command removes the user's information from st.user, deletes their identity cookie, and redirects them back to your app's home page. This creates a new session.

If the user has multiple sessions open in the same browser, st.user will not be cleared in any other session. st.user only reads from the identity cookie at the start of a session. After a session is running, you must call st.login() or st.logout() within that session to update st.user.

This does not log the user out of their underlying account from the identity provider.

.streamlit/secrets.toml:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "xxx"
client_id = "xxx"
client_secret = "xxx"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"  # fmt: skip
```

Example 2 (unknown):
```unknown
import streamlit as st

if not st.user.is_logged_in:
    if st.button("Log in"):
        st.login()
else:
    if st.button("Log out"):
        st.logout()
    st.write(f"Hello, {st.user.name}!")
```

---

## secrets.toml - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/connections/secrets.toml

**Contents:**
- secrets.toml
  - File location
  - File format
    - Example
  - Still have questions?

secrets.toml is an optional file you can define for your working directory or global development environment. When secrets.toml is defined both globally and in your working directory, Streamlit combines the secrets and gives precendence to the working-directory secrets. For more information, see Secrets management.

To define your secrets locally or per-project, add .streamlit/secrets.toml to your working directory. Your working directory is wherever you call streamlit run. If you haven't previously created the .streamlit directory, you will need to add it.

To define your configuration globally, you must first locate your global .streamlit directory. Streamlit adds this hidden directory to your OS user profile during installation. For MacOS/Linux, this will be ~/.streamlit/secrets.toml. For Windows, this will be %userprofile%/.streamlit/secrets.toml.

Optionally, you can change where Streamlit searches for secrets through the configuration option, secrets.files.

secrets.toml is a TOML file.

In your Streamlit app, the following values would be true:

Our forums are full of helpful information and Streamlit experts.

---

## st.connections.SnowflakeConnection - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/connections/st.connections.snowflakeconnection

**Contents:**
    - Tip
- st.connections.SnowflakeConnection
    - Examples
- SnowflakeConnection.cursor
    - Example
- SnowflakeConnection.query
    - Example
- SnowflakeConnection.raw_connection
    - Example
- SnowflakeConnection.reset

This page only contains the st.connections.SnowflakeConnection class. For a deeper dive into creating and managing data connections within Streamlit apps, see Connect Streamlit to Snowflake and Connecting to data.

A connection to Snowflake using the Snowflake Connector for Python.

Initialize this connection object using st.connection("snowflake") or st.connection("<name>", type="snowflake"). Connection parameters for a SnowflakeConnection can be specified using secrets.toml and/or **kwargs. Connection parameters are passed to snowflake.connector.connect().

When an app is running in Streamlit in Snowflake, st.connection("snowflake") connects automatically using the app owner's role without further configuration. **kwargs will be ignored in this case. Use secrets.toml and **kwargs to configure your connection for local development.

SnowflakeConnection includes several convenience methods. For example, you can directly execute a SQL query with .query() or access the underlying Snowflake Connector object with .raw_connection.

snowflake-snowpark-python must be installed in your environment to use this connection. You can install it as an extra with Streamlit:

Account identifiers must be of the form <orgname>-<account_name> where <orgname> is the name of your Snowflake organization and <account_name> is the unique name of your account within your organization. This is dash-separated, not dot-separated like when used in SQL queries. For more information, see Account identifiers.

st.connections.SnowflakeConnection(connection_name, **kwargs)

Create a new cursor object from this connection.

query(sql, *, ttl=None, show_spinner="Running `snowflake.query(...)`.", params=None, **kwargs)

Run a read-only SQL query.

Reset this connection so that it gets reinitialized the next time it's used.

Create a new Snowpark session from this connection.

write_pandas(df, table_name, database=None, schema=None, chunk_size=None, **kwargs)

Write a pandas.DataFrame to a table in a Snowflake database.

Access the underlying connection object from the Snowflake Connector for Python.

Example 1: Configuration with Streamlit secrets

You can configure your Snowflake connection using Streamlit's Secrets management. For example, if you have MFA enabled on your account, you can connect using key-pair authentication.

.streamlit/secrets.toml:

Example 2: Configuration with keyword arguments and external authentication

You can configure your Snowflake connection with keyword argume

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
pip install streamlit[snowflake]
```

Example 2 (unknown):
```unknown
[connections.snowflake]
account = "xxx-xxx"
user = "xxx"
private_key_file = "/xxx/xxx/xxx.p8"
role = "xxx"
warehouse = "xxx"
database = "xxx"
schema = "xxx"
```

Example 3 (unknown):
```unknown
import streamlit as st
conn = st.connection("snowflake")
df = conn.query("SELECT * FROM my_table")
```

Example 4 (unknown):
```unknown
import streamlit as st
conn = st.connection(
    "",
    type="snowflake",
    account="xxx-xxx",
    user="xxx",
    authenticator="externalbrowser",
)
df = conn.query("SELECT * FROM my_table")
```

---

## 2021 release notes - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/quick-reference/release-notes/2021

**Contents:**
- 2021 release notes
- Version 1.3.0
- Version 1.2.0
- Version 1.1.0
- Version 1.0.0
- Version 0.89.0
- Version 0.88.0
- Version 0.87.0
- Version 0.86.0
- Version 0.85.0

This page contains release notes for Streamlit versions released in 2021. For the latest version of Streamlit, see Release notes.

Release date: Dec 16, 2021

Release date: Nov 11, 2021

Release date: Oct 21, 2021

Release date: Oct 5, 2021

Release date: Sep 22, 2021

Release date: Sep 2, 2021

Release date: Aug 19, 2021

Release date: Aug 5, 2021

Release date: Jul 22, 2021

Release date: Jul 1, 2021

Release date: Jun 17, 2021

Release date: May 13, 2021

Release date: Apr 29, 2021

Release date: Apr 8, 2021

Release date: Mar 18, 2021

Release date: Mar 4, 2021

Release date: Feb 23, 2021

Release date: February 4, 2021

Release date: January 21, 2021

Release date: January 6, 2021

Our forums are full of helpful information and Streamlit experts.

---

## st.components.v1.declare_component - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/custom-components/st.components.v1.declare_component

**Contents:**
- st.components.v1.declare_component
  - Still have questions?

Create a custom component and register it if there is a ScriptRunContext.

The component is not registered when there is no ScriptRunContext. This can happen when a CustomComponent is executed as standalone command (e.g. for testing).

To use this function, import it from the streamlit.components.v1 module.

Using st.components.v1.declare_component directly (instead of importing its module) is deprecated and will be disallowed in a later version.

st.components.v1.declare_component(name, path=None, url=None)

A short, descriptive name for the component, like "slider".

path (str, Path, or None)

The path to serve the component's frontend files from. The path should be absolute. If path is None (default), Streamlit will serve the component from the location in url. Either path or url must be specified. If both are specified, then url will take precedence.

The URL that the component is served from. If url is None (default), Streamlit will serve the component from the location in path. Either path or url must be specified. If both are specified, then url will take precedence.

A CustomComponent that can be called like a function. Calling the component will create a new instance of the component in the Streamlit app.

Our forums are full of helpful information and Streamlit experts.

---

## st.toast - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/status/st.toast

**Contents:**
- st.toast
    - Examples
  - Still have questions?

Display a short message, known as a notification "toast".

The toast appears in the app's top-right corner and disappears after four seconds.

st.toast is not compatible with Streamlit's caching and cannot be called within a cached function.

st.toast(body, *, icon=None, duration="short")

The string to display as GitHub-flavored Markdown. Syntax information can be found at: https://github.github.com/gfm.

See the body parameter of st.markdown for additional, supported Markdown directives.

An optional emoji or icon to display next to the alert. If icon is None (default), no icon is displayed. If icon is a string, the following options are valid:

A single-character emoji. For example, you can set icon="🚨" or icon="🔥". Emoji short codes are not supported.

An icon from the Material Symbols library (rounded style) in the format ":material/icon_name:" where "icon_name" is the name of the icon in snake case.

For example, icon=":material/thumb_up:" will display the Thumb Up icon. Find additional icons in the Material Symbols font library.

duration ("short", "long", "infinite", or int)

The time to display the toast message. This can be one of the following:

Example 1: Show a toast message

Example 2: Show multiple toasts

When multiple toasts are generated, they will stack. Hovering over a toast will stop it from disappearing. When hovering ends, the toast will disappear after time specified in duration.

Example 3: Update a toast message

Toast messages can also be updated. Assign st.toast(my_message) to a variable and use the .toast() method to update it. If a toast has already disappeared or been dismissed, the update will not be seen.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.toast("Your edited image was saved!", icon="😍")
```

Example 2 (unknown):
```unknown
import time
import streamlit as st

if st.button("Three cheers"):
    st.toast("Hip!")
    time.sleep(0.5)
    st.toast("Hip!")
    time.sleep(0.5)
    st.toast("Hooray!", icon="🎉")
```

Example 3 (python):
```python
import time
import streamlit as st

def cook_breakfast():
    msg = st.toast("Gathering ingredients...")
    time.sleep(1)
    msg.toast("Cooking...")
    time.sleep(1)
    msg.toast("Ready!", icon="🥞")

if st.button("Cook breakfast"):
    cook_breakfast()
```

---

## st.warning - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/status/st.warning

**Contents:**
- st.warning
    - Example
  - Still have questions?

Display warning message.

st.warning(body, *, icon=None, width="stretch")

The text to display as GitHub-flavored Markdown. Syntax information can be found at: https://github.github.com/gfm.

See the body parameter of st.markdown for additional, supported Markdown directives.

An optional emoji or icon to display next to the alert. If icon is None (default), no icon is displayed. If icon is a string, the following options are valid:

A single-character emoji. For example, you can set icon="🚨" or icon="🔥". Emoji short codes are not supported.

An icon from the Material Symbols library (rounded style) in the format ":material/icon_name:" where "icon_name" is the name of the icon in snake case.

For example, icon=":material/thumb_up:" will display the Thumb Up icon. Find additional icons in the Material Symbols font library.

width ("stretch" or int)

The width of the warning element. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.warning('This is a warning', icon="⚠️")
```

---

## st.Page - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/navigation/st.page

**Contents:**
- st.Page
    - Example
- StreamlitPage
- StreamlitPage.run
  - Still have questions?

Configure a page for st.navigation in a multipage app.

Call st.Page to initialize a StreamlitPage object, and pass it to st.navigation to declare a page in your app.

When a user navigates to a page, st.navigation returns the selected StreamlitPage object. Call .run() on the returned StreamlitPage object to execute the page. You can only run the page returned by st.navigation, and you can only run it once per app rerun.

A page can be defined by a Python file or Callable.

st.Page(page, *, title=None, icon=None, url_path=None, default=False)

page (str, Path, or callable)

The page source as a Callable or path to a Python file. If the page source is defined by a Python file, the path can be a string or pathlib.Path object. Paths can be absolute or relative to the entrypoint file. If the page source is defined by a Callable, the Callable can't accept arguments.

The title of the page. If this is None (default), the page title (in the browser tab) and label (in the navigation menu) will be inferred from the filename or callable name in page. For more information, see Overview of multipage apps.

An optional emoji or icon to display next to the page title and label. If icon is None (default), no icon is displayed next to the page label in the navigation menu, and a Streamlit icon is displayed next to the title (in the browser tab). If icon is a string, the following options are valid:

or icon="🔥". Emoji short codes are not supported.

format ":material/icon_name:" where "icon_name" is the name of the icon in snake case.

For example, icon=":material/thumb_up:" will display the Thumb Up icon. Find additional icons in the Material Symbols font library.

url_path (str or None)

The page's URL pathname, which is the path relative to the app's root URL. If this is None (default), the URL pathname will be inferred from the filename or callable name in page. For more information, see Overview of multipage apps.

The default page will have a pathname of "", indicating the root URL of the app. If you set default=True, url_path is ignored. url_path can't include forward slashes; paths can't include subdirectories.

Whether this page is the default page to be shown when the app is loaded. If default is False (default), the page will have a nonempty URL pathname. However, if no default page is passed to st.navigation and this is the first page, this page will become the default page. If default is True, then the page will have an empty pathname and url_path will be ign

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import streamlit as st

def page2():
    st.title("Second page")

pg = st.navigation([
    st.Page("page1.py", title="First page", icon="🔥"),
    st.Page(page2, title="Second page", icon=":material/favorite:"),
])
pg.run()
```

---

## st.subheader - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/text/st.subheader

**Contents:**
- st.subheader
    - Examples
  - Still have questions?

Display text in subheader formatting.

st.subheader(body, anchor=None, *, help=None, divider=False, width="stretch")

The text to display as GitHub-flavored Markdown. Syntax information can be found at: https://github.github.com/gfm.

See the body parameter of st.markdown for additional, supported Markdown directives.

anchor (str or False)

The anchor name of the header that can be accessed with #anchor in the URL. If omitted, it generates an anchor using the body. If False, the anchor is not shown in the UI.

A tooltip that gets displayed next to the subheader. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

divider (bool, "blue", "green", "orange", "red", "violet", "yellow", "gray"/"grey", or "rainbow")

Shows a colored divider below the header. If this is True, successive headers will cycle through divider colors, except gray and rainbow. That is, the first header will have a blue line, the second header will have a green line, and so on. If this is a string, the color can be set to one of the following: blue, green, orange, red, violet, yellow, gray/grey, or rainbow.

width ("stretch", "content", or int)

The width of the subheader element. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.subheader("_Streamlit_ is :blue[cool] :sunglasses:")
st.subheader("This is a subheader with a divider", divider="gray")
st.subheader("These subheaders have rotating dividers", divider=True)
st.subheader("One", divider=True)
st.subheader("Two", divider=True)
st.subheader("Three", divider=True)
st.subheader("Four", divider=True)
```

---

## st.json - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.json

**Contents:**
- st.json
    - Example
  - Still have questions?

Display an object or string as a pretty-printed, interactive JSON string.

st.json(body, *, expanded=True, width="stretch")

The object to print as JSON. All referenced objects should be serializable to JSON as well. If object is a string, we assume it contains serialized JSON.

expanded (bool or int)

The initial expansion state of the JSON element. This can be one of the following:

Regardless of the initial expansion state, users can collapse or expand any key-value pair to show or hide any part of the object.

width ("stretch" or int)

The width of the JSON element. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

st.json(
    {
        "foo": "bar",
        "stuff": [
            "stuff 1",
            "stuff 2",
            "stuff 3",
        ],
        "level1": {"level2": {"level3": {"a": "b"}}},
    },
    expanded=2,
)
```

---

## st.tabs - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/layout/st.tabs

**Contents:**
- st.tabs
    - Examples
  - Still have questions?

Insert containers separated into tabs.

Inserts a number of multi-element containers as tabs. Tabs are a navigational element that allows users to easily move between groups of related content.

To add elements to the returned containers, you can use the with notation (preferred) or just call methods directly on the returned object. See the examples below.

All content within every tab is computed and sent to the frontend, regardless of which tab is selected. Tabs do not currently support conditional rendering. If you have a slow-loading tab, consider using a widget like st.segmented_control to conditionally render content instead.

st.tabs(tabs, *, width="stretch", default=None)

Creates a tab for each string in the list. The first tab is selected by default. The string is used as the name of the tab and can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

width ("stretch" or int)

The width of the tab container. This can be one of the following:

default (str or None)

The default tab to select. If this is None (default), the first tab is selected. If this is a string, it must be one of the tab labels. If two tabs have the same label as default, the first one is selected.

A list of container objects.

Example 1: Use context management

You can use with notation to insert any element into a tab:

Example 2: Call methods directly

You can call methods directly on the returned objects:

Example 3: Set the default tab and style the tab labels

Use the default parameter to set the default tab. You can also use Markdown in the tab labels.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

tab1, tab2, tab3 = st.tabs(["Cat", "Dog", "Owl"])

with tab1:
    st.header("A cat")
    st.image("https://static.streamlit.io/examples/cat.jpg", width=200)
with tab2:
    st.header("A dog")
    st.image("https://static.streamlit.io/examples/dog.jpg", width=200)
with tab3:
    st.header("An owl")
    st.image("https://static.streamlit.io/examples/owl.jpg", width=200)
```

Example 2 (python):
```python
import streamlit as st
from numpy.random import default_rng as rng

df = rng(0).standard_normal((10, 1))

tab1, tab2 = st.tabs(["📈 Chart", "🗃 Data"])

tab1.subheader("A tab with a chart")
tab1.line_chart(df)

tab2.subheader("A tab with the data")
tab2.write(df)
```

Example 3 (unknown):
```unknown
import streamlit as st

tab1, tab2, tab3 = st.tabs(
    [":cat: Cat", ":dog: Dog", ":rainbow[Owl]"], default=":rainbow[Owl]"
)

with tab1:
    st.header("A cat")
    st.image("https://static.streamlit.io/examples/cat.jpg", width=200)
with tab2:
    st.header("A dog")
    st.image("https://static.streamlit.io/examples/dog.jpg", width=200)
with tab3:
    st.header("An owl")
    st.image("https://static.streamlit.io/examples/owl.jpg", width=200)
```

---

## Custom components - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/custom-components

**Contents:**
- Custom components
    - Declare a component
    - HTML
    - iframe
  - Still have questions?

Create and register a custom component.

Display an HTML string in an iframe.

Load a remote URL in an iframe.

Our forums are full of helpful information and Streamlit experts.

---

## Input widgets - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets

**Contents:**
- Input widgets
- Button elements
    - Button
    - Download button
    - Form button
    - Link button
    - Page link
- Selection elements
    - Checkbox
    - Color picker

With widgets, Streamlit allows you to bake interactivity directly into your apps with buttons, sliders, text inputs, and more.

Display a button widget.

Display a download button widget.

Display a form submit button. For use with st.form.

Display a link button.

Display a link to another page in a multipage app.

Display a checkbox widget.

Display a color picker widget.

Display a rating or sentiment button group.

Display a multiselect widget. The multiselect widget starts as empty.

Display a pill-button selection widget.

Display a radio button widget.

Display a segmented-button selection widget.

Display a slider widget to select items from a list.

Display a select widget.

Display a toggle widget.

Display a numeric input widget.

Display a slider widget.

Display a date input widget.

Display a time input widget.

Display a single-line text input widget.

Display a multi-line text input widget.

Display a chat input widget.

Display a widget that allows users to record with their microphone.

Display a data editor widget.

Display a file uploader widget.

Display a widget that allows users to upload images directly from a camera.

Third-party components

These are featured components created by our lovely community. For more examples and inspiration, check out our Components Gallery and Streamlit Extras!

Streamlit Component for a Chatbot UI. Created by @AI-Yash.

Select a single item from a list of options in a menu. Created by @victoryhb.

A library with useful Streamlit extras. Created by @arnaudmiribel.

Create a draggable and resizable dashboard in Streamlit. Created by @okls.

Add tags to your Streamlit apps. Created by @gagan3012.

The simplest way to handle a progress bar in streamlit app. Created by @Wirg.

Display a Timeline in Streamlit apps using TimelineJS. Created by @innerdoc.

Alternative for st.camera_input which returns the webcam images live. Created by @blackary.

Ace editor component for Streamlit. Created by @okld.

Streamlit Component for a Chatbot UI. Created by @AI-Yash.

Select a single item from a list of options in a menu. Created by @victoryhb.

A library with useful Streamlit extras. Created by @arnaudmiribel.

Create a draggable and resizable dashboard in Streamlit. Created by @okls.

Add tags to your Streamlit apps. Created by @gagan3012.

The simplest way to handle a progress bar in streamlit app. Created by @Wirg.

Display a Timeline in Streamlit apps using TimelineJS. Created by @innerdoc.

Alternative for st.

*[Content truncated]*

---

## st.column_config.LineChartColumn - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.linechartcolumn

**Contents:**
- st.column_config.LineChartColumn
    - Examples
  - Still have questions?

Configure a line chart column in st.dataframe or st.data_editor.

Cells need to contain a list of numbers. Chart columns are not editable at the moment. This command needs to be used in the column_config parameter of st.dataframe or st.data_editor.

st.column_config.LineChartColumn(label=None, *, width=None, help=None, pinned=None, y_min=None, y_max=None, color=None)

The label shown at the top of the column. If this is None (default), the column name is used.

width ("small", "medium", "large", int, or None)

The display width of the column. If this is None (default), the column will be sized to fit the cell contents. Otherwise, this can be one of the following:

If the total width of all columns is less than the width of the dataframe, the remaining space will be distributed evenly among all columns.

A tooltip that gets displayed when hovering over the column label. If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

pinned (bool or None)

Whether the column is pinned. A pinned column will stay visible on the left side no matter where the user scrolls. If this is None (default), Streamlit will decide: index columns are pinned, and data columns are not pinned.

y_min (int, float, or None)

The minimum value on the y-axis for all cells in the column. If this is None (default), every cell will use the minimum of its data.

y_max (int, float, or None)

The maximum value on the y-axis for all cells in the column. If this is None (default), every cell will use the maximum of its data.

color ("auto", "auto-inverse", str, or None)

The color to use for the chart. This can be one of the following:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import pandas as pd
import streamlit as st

data_df = pd.DataFrame(
    {
        "sales": [
            [0, 4, 26, 80, 100, 40],
            [80, 20, 80, 35, 40, 100],
            [10, 20, 80, 80, 70, 0],
            [10, 100, 20, 100, 30, 100],
        ],
    }
)

st.data_editor(
    data_df,
    column_config={
        "sales": st.column_config.LineChartColumn(
            "Sales (last 6 months)",
            width="medium",
            help="The sales volume in the last 6 months",
            y_min=0,
            y_max=100,
         ),
    },
    hide_index=True,
)
```

---

## st.form - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/execution-flow/st.form

**Contents:**
    - Tip
- st.form
    - Examples
  - Still have questions?

This page only contains information on the st.forms API. For a deeper dive into creating and using forms within Streamlit apps, read our guide on Using forms.

Create a form that batches elements together with a "Submit" button.

A form is a container that visually groups other elements and widgets together, and contains a Submit button. When the form's Submit button is pressed, all widget values inside the form will be sent to Streamlit in a batch.

To add elements to a form object, you can use with notation (preferred) or just call methods directly on the form. See examples below.

Forms have a few constraints:

st.form(key, clear_on_submit=False, *, enter_to_submit=True, border=True, width="stretch", height="content")

A string that identifies the form. Each form must have its own key. (This key is not displayed to the user in the interface.)

clear_on_submit (bool)

If True, all widgets inside the form will be reset to their default values after the user presses the Submit button. Defaults to False. (Note that Custom Components are unaffected by this flag, and will not be reset to their defaults on form submission.)

enter_to_submit (bool)

Whether to submit the form when a user presses Enter while interacting with a widget inside the form.

If this is True (default), pressing Enter while interacting with a form widget is equivalent to clicking the first st.form_submit_button in the form.

If this is False, the user must click an st.form_submit_button to submit the form.

If the first st.form_submit_button in the form is disabled, the form will override submission behavior with enter_to_submit=False.

Whether to show a border around the form. Defaults to True.

Not showing a border can be confusing to viewers since interacting with a widget in the form will do nothing. You should only remove the border if there's another border (e.g. because of an expander) or the form is small (e.g. just a text input and a submit button).

width ("stretch", "content", or int)

The width of the form container. This can be one of the following:

height ("content", "stretch", or int)

The height of the form container. This can be one of the following:

Use scrolling containers sparingly. If you use scrolling containers, avoid heights that exceed 500 pixels. Otherwise, the scroll surface of the container might cover the majority of the screen on mobile devices, which makes it hard to scroll the rest of the app.

Inserting elements using with notation:

Inserting elements 

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

with st.form("my_form"):
    st.write("Inside the form")
    slider_val = st.slider("Form slider")
    checkbox_val = st.checkbox("Form checkbox")

    # Every form must have a submit button.
    submitted = st.form_submit_button("Submit")
    if submitted:
        st.write("slider", slider_val, "checkbox", checkbox_val)
st.write("Outside the form")
```

Example 2 (unknown):
```unknown
import streamlit as st

form = st.form("my_form")
form.slider("Inside the form")
st.slider("Outside the form")

# Now add a submit button to the form:
form.form_submit_button("Submit")
```

---

## st.get_option - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/configuration/st.get_option

**Contents:**
- st.get_option
    - Example
  - Still have questions?

Return the current value of a given Streamlit configuration option.

Run streamlit config show in a terminal to see all available options.

The config option key of the form "section.optionName". To see all available options, run streamlit config show in a terminal.

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

color = st.get_option("theme.primaryColor")
```

---

## st.line_chart - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/charts/st.line_chart

**Contents:**
- st.line_chart
    - Examples
- element.add_rows
    - Example
  - Still have questions?

Display a line chart.

This is syntax-sugar around st.altair_chart. The main difference is this command uses the data's own column and indices to figure out the chart's Altair spec. As a result this is easier to use for many "just plot this" scenarios, while being less customizable.

st.line_chart(data=None, *, x=None, y=None, x_label=None, y_label=None, color=None, width="stretch", height="content", use_container_width=None)

data (Anything supported by st.dataframe)

Column name or key associated to the x-axis data. If x is None (default), Streamlit uses the data index for the x-axis values.

y (str, Sequence of str, or None)

Column name(s) or key(s) associated to the y-axis data. If this is None (default), Streamlit draws the data of all remaining columns as data series. If this is a Sequence of strings, Streamlit draws several series on the same chart by melting your wide-format table into a long-format table behind the scenes.

x_label (str or None)

The label for the x-axis. If this is None (default), Streamlit will use the column name specified in x if available, or else no label will be displayed.

y_label (str or None)

The label for the y-axis. If this is None (default), Streamlit will use the column name(s) specified in y if available, or else no label will be displayed.

color (str, tuple, Sequence of str, Sequence of tuple, or None)

The color to use for different lines in this chart.

For a line chart with just one line, this can be:

For a line chart with multiple lines, where the dataframe is in long format (that is, y is None or just one column), this can be:

None, to use the default colors.

The name of a column in the dataset. Data points will be grouped into lines of the same color based on the value of this column. In addition, if the values in this column match one of the color formats above (hex string or color tuple), then that color will be used.

For example: if the dataset has 1000 rows, but this column only contains the values "adult", "child", and "baby", then those 1000 datapoints will be grouped into three lines whose colors will be automatically selected from the default palette.

But, if for the same 1000-row dataset, this column contained the values "#ffaa00", "#f0f", "#0000ff", then then those 1000 datapoints would still be grouped into three lines, but their colors would be "#ffaa00", "#f0f", "#0000ff" this time around.

For a line chart with multiple lines, where the dataframe is in wide format (that is, y is a Sequen

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(rng(0).standard_normal((20, 3)), columns=["a", "b", "c"])

st.line_chart(df)
```

Example 2 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(
    {
        "col1": list(range(20)) * 3,
        "col2": rng(0).standard_normal(60),
        "col3": ["a"] * 20 + ["b"] * 20 + ["c"] * 20,
    }
)

st.line_chart(df, x="col1", y="col2", color="col3")
```

Example 3 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(rng(0).standard_normal((20, 3)), columns=["a", "b", "c"])

st.line_chart(
    df,
    x="a",
    y=["b", "c"],
    color=["#FF0000", "#0000FF"],
)
```

Example 4 (python):
```python
import time
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df1 = pd.DataFrame(
    rng(0).standard_normal(size=(50, 20)), columns=("col %d" % i for i in range(20))
)

df2 = pd.DataFrame(
    rng(1).standard_normal(size=(50, 20)), columns=("col %d" % i for i in range(20))
)

my_table = st.table(df1)
time.sleep(1)
my_table.add_rows(df2)
```

---

## st.map - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/charts/st.map

**Contents:**
- st.map
    - Examples
- element.add_rows
    - Example
  - Still have questions?

Display a map with a scatterplot overlaid onto it.

This is a wrapper around st.pydeck_chart to quickly create scatterplot charts on top of a map, with auto-centering and auto-zoom.

When using this command, a service called Carto provides the map tiles to render map content. If you're using advanced PyDeck features you may need to obtain an API key from Carto first. You can do that as pydeck.Deck(api_keys={"carto": YOUR_KEY}) or by setting the CARTO_API_KEY environment variable. See PyDeck's documentation for more information.

Another common provider for map tiles is Mapbox. If you prefer to use that, you'll need to create an account at https://mapbox.com and specify your Mapbox key when creating the pydeck.Deck object. You can do that as pydeck.Deck(api_keys={"mapbox": YOUR_KEY}) or by setting the MAPBOX_API_KEY environment variable.

Carto and Mapbox are third-party products and Streamlit accepts no responsibility or liability of any kind for Carto or Mapbox, or for any content or information made available by Carto or Mapbox. The use of Carto or Mapbox is governed by their respective Terms of Use.

st.map(data=None, *, latitude=None, longitude=None, color=None, size=None, zoom=None, use_container_width=True, width=None, height=None)

data (Anything supported by st.dataframe)

The data to be plotted.

latitude (str or None)

The name of the column containing the latitude coordinates of the datapoints in the chart.

If None, the latitude data will come from any column named 'lat', 'latitude', 'LAT', or 'LATITUDE'.

longitude (str or None)

The name of the column containing the longitude coordinates of the datapoints in the chart.

If None, the longitude data will come from any column named 'lon', 'longitude', 'LON', or 'LONGITUDE'.

color (str or tuple or None)

The color of the circles representing each datapoint.

size (str or float or None)

The size of the circles representing each point, in meters.

Zoom level as specified in https://wiki.openstreetmap.org/wiki/Zoom_levels.

use_container_width (bool)

Whether to override the map's native width with the width of the parent container. If use_container_width is True (default), Streamlit sets the width of the map to match the width of the parent container. If use_container_width is False, Streamlit sets the width of the chart to fit its contents according to the plotting library, up to the width of the parent container.

Desired width of the chart expressed in pixels. If width is None (default), Strea

*[Content truncated]*

**Examples:**

Example 1 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(
    rng(0).standard_normal((1000, 2)) / [50, 50] + [37.76, -122.4],
    columns=["lat", "lon"],
)

st.map(df)
```

Example 2 (unknown):
```unknown
st.map(df, size=20, color="#0044ff")
```

Example 3 (python):
```python
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df = pd.DataFrame(
    {
        "col1": rng(0).standard_normal(1000) / 50 + 37.76,
        "col2": rng(1).standard_normal(1000) / 50 + -122.4,
        "col3": rng(2).standard_normal(1000) * 100,
        "col4": rng(3).standard_normal((1000, 4)).tolist(),
    }
)

st.map(df, latitude="col1", longitude="col2", size="col3", color="col4")
```

Example 4 (python):
```python
import time
import pandas as pd
import streamlit as st
from numpy.random import default_rng as rng

df1 = pd.DataFrame(
    rng(0).standard_normal(size=(50, 20)), columns=("col %d" % i for i in range(20))
)

df2 = pd.DataFrame(
    rng(1).standard_normal(size=(50, 20)), columns=("col %d" % i for i in range(20))
)

my_table = st.table(df1)
time.sleep(1)
my_table.add_rows(df2)
```

---

## st.text_area - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.text_area

**Contents:**
- st.text_area
    - Example
  - Still have questions?

Display a multi-line text input widget.

st.text_area(label, value="", height=None, max_chars=None, key=None, help=None, on_change=None, args=None, kwargs=None, *, placeholder=None, disabled=False, label_visibility="visible", width="stretch")

A short label explaining to the user what this input is for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

For accessibility reasons, you should never set an empty label, but you can hide it with label_visibility if needed. In the future, we may disallow empty labels by raising an exception.

value (object or None)

The text value of this widget when it first renders. This will be cast to str internally. If None, will initialize empty and return None until the user provides input. Defaults to empty string.

height ("content", "stretch", int, or None)

The height of the text area widget. This can be one of the following:

The widget's height can't be smaller than the height of two lines. When label_visibility="collapsed", the minimum height is 68 pixels. Otherwise, the minimum height is 98 pixels.

max_chars (int or None)

Maximum number of characters allowed in text area.

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

A tooltip that gets displayed next to the widget label. Streamlit only displays the tooltip when label_visibility="visible". If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

An optional callback invoked when this text_area's value changes.

An optional list or tuple of args to pass to the callback.

An optional dict of kwargs to pass to the callback.

placeholder (str or None)

An optional string displayed when the text area is empty. If None, no text is displayed.

An optional boolean that disables the text area if set to True. The default is False.

label_visibi

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

txt = st.text_area(
    "Text to analyze",
    "It was the best of times, it was the worst of times, it was the age of "
    "wisdom, it was the age of foolishness, it was the epoch of belief, it "
    "was the epoch of incredulity, it was the season of Light, it was the "
    "season of Darkness, it was the spring of hope, it was the winter of "
    "despair, (...)",
)

st.write(f"You wrote {len(txt)} characters.")
```

---

## st.switch_page - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/navigation/st.switch_page

**Contents:**
- st.switch_page
    - Example
  - Still have questions?

Programmatically switch the current page in a multipage app.

When st.switch_page is called, the current page execution stops and the specified page runs as if the user clicked on it in the sidebar navigation. The specified page must be recognized by Streamlit's multipage architecture (your main Python file or a Python file in a pages/ folder). Arbitrary Python scripts cannot be passed to st.switch_page.

page (str, Path, or st.Page)

The file path (relative to the main script) or an st.Page indicating the page to switch to.

Consider the following example given this file structure:

Our forums are full of helpful information and Streamlit experts.

**Examples:**

Example 1 (unknown):
```unknown
your-repository/
├── pages/
│   ├── page_1.py
│   └── page_2.py
└── your_app.py
```

Example 2 (unknown):
```unknown
import streamlit as st

if st.button("Home"):
    st.switch_page("your_app.py")
if st.button("Page 1"):
    st.switch_page("pages/page_1.py")
if st.button("Page 2"):
    st.switch_page("pages/page_2.py")
```

---

## st.audio_input - Streamlit Docs

**URL:** https://docs.streamlit.io/develop/api-reference/widgets/st.audio_input

**Contents:**
- st.audio_input
    - Examples
  - Still have questions?

Display a widget that returns an audio recording from the user's microphone.

st.audio_input(label, *, sample_rate=16000, key=None, help=None, on_change=None, args=None, kwargs=None, disabled=False, label_visibility="visible", width="stretch")

A short label explaining to the user what this widget is used for. The label can optionally contain GitHub-flavored Markdown of the following types: Bold, Italics, Strikethroughs, Inline Code, Links, and Images. Images display like icons, with a max height equal to the font height.

Unsupported Markdown elements are unwrapped so only their children (text contents) render. Display unsupported elements as literal characters by backslash-escaping them. E.g., "1\. Not an ordered list".

See the body parameter of st.markdown for additional, supported Markdown directives.

For accessibility reasons, you should never set an empty label, but you can hide it with label_visibility if needed. In the future, we may disallow empty labels by raising an exception.

sample_rate (int or None)

The target sample rate for the audio recording in Hz. This defaults to 16000 Hz, which is optimal for speech recognition.

The following sample rates are supported: 8000, 11025, 16000, 22050, 24000, 32000, 44100, or 48000. If this is None, the widget uses the browser's default sample rate (typically 44100 or 48000 Hz).

An optional string or integer to use as the unique key for the widget. If this is omitted, a key will be generated for the widget based on its content. No two widgets may have the same key.

A tooltip that gets displayed next to the widget label. Streamlit only displays the tooltip when label_visibility="visible". If this is None (default), no tooltip is displayed.

The tooltip can optionally contain GitHub-flavored Markdown, including the Markdown directives described in the body parameter of st.markdown.

An optional callback invoked when this audio input's value changes.

An optional list or tuple of args to pass to the callback.

An optional dict of kwargs to pass to the callback.

An optional boolean that disables the audio input if set to True. Default is False.

label_visibility ("visible", "hidden", or "collapsed")

The visibility of the label. The default is "visible". If this is "hidden", Streamlit displays an empty spacer instead of the label, which can help keep the widget aligned with other widgets. If this is "collapsed", Streamlit displays no label or spacer.

width ("stretch" or int)

The width of the audio inpu

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
import streamlit as st

audio_value = st.audio_input("Record a voice message")

if audio_value:
    st.audio(audio_value)
```

Example 2 (unknown):
```unknown
import streamlit as st

audio_value = st.audio_input("Record high quality audio", sample_rate=48000)

if audio_value:
    st.audio(audio_value)
```

---
