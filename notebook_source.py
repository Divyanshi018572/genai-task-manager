# %% [markdown]
# # AI-Powered Personal Task Manager
#
# ## 1. Problem understanding and proposed approach
#
# ## 2. Tech stack and justification
#
# ## 3. Python implementation
#
# ## 4. Sample inputs and outputs
#
# ## 5. Testing of core functionality and error handling
#
# ## 6. Limitations and possible improvements

# %%
import json
import os
import re
import sqlite3
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None
