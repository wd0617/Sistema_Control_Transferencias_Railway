"""
Archivo WSGI para PythonAnywhere
Este archivo le dice a PythonAnywhere cómo ejecutar tu aplicación Flask.
"""

import sys
import os

# Agrega la ruta del proyecto al path de Python
path = '/home/wd0617/Sistema_Control_Transferencias'
if path not in sys.path:
    sys.path.append(path)

# Importa la aplicación desde tu script principal
from run import app as application  # Ajusta según cómo hayas definido tu app

# Activa la configuración para producción
os.environ['FLASK_ENV'] = 'production'

# La configuración para la base de datos MySQL ya está activada en config.py
# No es necesario configurarla aquí
