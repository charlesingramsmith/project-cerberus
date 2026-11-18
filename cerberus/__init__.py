"""Project Cerberus: a life list for the dog breeds you spot."""
import time

# When this package was imported. app.py compares it with the cerberus/*.py files'
# modified times to spot a deploy that changed them (see drop_stale_cerberus_modules).
LOADED_AT = time.time()
