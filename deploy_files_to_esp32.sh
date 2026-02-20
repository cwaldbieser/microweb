#! /bin/sh

# Copy assets
mpremote cp -r www/ :
mpremote cp -r templates/ :

# Copy python modules
mpremote cp ./xyt01.py :lib/xyt01.py
# TODO: Copy microdot files

# Clear out compiled templates
mpremote fs rm 'templates/index_tpl.py'
mpremote fs rm 'templates/settings_tpl.py'
