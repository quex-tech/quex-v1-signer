#!/bin/sh
waitress-serve --host 127.0.0.1 --port 8000 --call 'quex_backend:create_app'
