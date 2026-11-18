# Helpdesk Tollocan

Sistema web de tickets de soporte técnico hecho con Django 5 y PostgreSQL. Los usuarios reportan incidencias y el equipo de soporte las atiende, con seguimiento y avisos por correo. Está pensado para correr en un servidor propio dentro de la red local.

## Requisitos

Instala estos tres programas:

- Python 3.12 o superior: https://www.python.org/downloads/ (en Windows marca "Add python.exe to PATH")
- PostgreSQL 14 o superior: https://www.postgresql.org/download/ (anota la contraseña del usuario postgres y deja el puerto 5432)
- Git: https://git-scm.com/downloads

En Linux (Debian o Ubuntu):

```bash
sudo apt install python3 python3-venv python3-pip postgresql libpq-dev git
```

## Instalación

### 1. Descargar el proyecto

```bash
git clone https://github.com/JulioCesarSanchez6843/HelpdesATO.git
cd HelpdesATO
```

### 2. Entorno virtual y dependencias

Windows (PowerShell):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements/dev.txt
```

Si PowerShell bloquea la activación, ejecuta una vez: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

Linux o macOS:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements/dev.txt
```

### 3. Crear la base de datos

En pgAdmin: clic derecho en Databases, Create, Database, nombre `helpdesk_db`.

O por terminal en Linux:

```bash
sudo -u postgres psql -c "CREATE DATABASE helpdesk_db;"
```

### 4. Configurar el archivo .env

Copia la plantilla:

```bash
cp .env.example .env
```

En Windows: `copy .env.example .env`

Edita `.env` y completa estos valores:

```env
SECRET_KEY=pega-una-clave-larga-y-aleatoria
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=helpdesk_db
DB_USER=postgres
DB_PASSWORD=la-contraseña-de-postgres
DB_HOST=localhost
DB_PORT=5432
SITE_URL=http://localhost:8000
```

Para generar la SECRET_KEY:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### 5. Preparar la base de datos

```bash
python manage.py migrate
python manage.py createcachetable
python manage.py createsuperuser
```

El último comando pide correo, nombre y contraseña del administrador.

### 6. Iniciar

```bash
python manage.py runserver
```

Abre http://localhost:8000 e inicia sesión con el administrador.

## Primeros pasos

Entra como administrador y da de alta, en este orden: sucursales, catálogos (áreas, categorías y puestos) y usuarios.

## Correos (opcional)

Sin configuración, los correos solo se imprimen en la consola del servidor y no se envían. Para enviarlos, agrega al `.env` (con Gmail necesitas una contraseña de aplicación de Google):

```env
EMAIL_HOST_USER=tu-cuenta@gmail.com
EMAIL_HOST_PASSWORD=tu-contraseña-de-aplicación
DEFAULT_FROM_EMAIL=Helpdesk Tollocan <tu-cuenta@gmail.com>
```

Para otro servidor SMTP, agrega también `EMAIL_HOST` y `EMAIL_PORT`.

Prueba el envío con:

```bash
python manage.py probar_correo tucorreo@gmail.com
```

## Dejarlo en el servidor

Si otras computadoras de la red lo van a usar:

1. En el `.env` agrega la IP del servidor, por ejemplo:

```env
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.50
SITE_URL=http://192.168.1.50:8000
```

`SITE_URL` es la dirección que aparece en los enlaces de los correos.

2. Abre el puerto 8000 en el firewall.

3. Deja corriendo estos dos procesos, cada uno en su terminal con el entorno virtual activo:

```bash
python manage.py runserver 0.0.0.0:8000
python manage.py ejecutar_tareas
```

El segundo envía la cola de correos y hace el cierre automático de tickets. Si no está corriendo, los correos no salen.

4. Para que arranquen solos al encender el servidor, usa el Programador de tareas (Windows) o servicios de systemd (Linux), uno por cada comando.

## Hecho por Juls.


