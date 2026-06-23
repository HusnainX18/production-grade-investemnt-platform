"""
Resilient API helper.
Configures requests.Session with exponential backoff retry mechanisms.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

def get_resilient_session(retries=5, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504)):
    """
    Build and return a requests.Session pre-configured with retries and exponential backoff.
    """
    session = requests.Session()
    
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        raise_on_status=False
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session
