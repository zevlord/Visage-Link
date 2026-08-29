# This file makes the server/ directory a proper Python package
# so uvicorn can import it as: uvicorn server:app

from .server import app

