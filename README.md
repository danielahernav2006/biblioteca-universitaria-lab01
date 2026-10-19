instucciones
1. descarga el repo
2. abre lab1.sql en mysql y ejecútalo
3. abre cmd y ubicate en la carpeta
4. ejecuta estos comandosÑ

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

5. configura las variables

por defecto tiene db.py usa estos valores

DB_PORT		3306
DB_USER		root
DB_PASSWORD	(vacío)

puedes cambiarlos por línea de comandos o abriendo db.py en un editor de texto. sí o sí hay que cambiar DB_PASSWORD a el que esta en tu MySQL

en cmd: set DB_PASSWORD=contraseña

6. inicia la aplicación

python app.py

7. abre en el navegador http://127.0.0.1:5000
