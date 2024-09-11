#!/bin/sh
waitress-serve --call 'quex_backend:create_app' --port 8000
