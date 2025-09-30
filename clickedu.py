import os
import requests
from bs4 import BeautifulSoup
import getpass
import json
import re
import datetime
from exif import Image as eImage

# URLs base
BASE_URL = f"https://DOMAIN.clickedu.eu"
# Carpeta para guardar las fotos
DOWNLOAD_FOLDER = "fotos_descarregades"

WANTED_ALBUMS = open("albums.txt").read().split("\n")
NOW = datetime.datetime.now()

dmy = "[0-3][0-9][0-1][0-9]20[0-2][0-9]"
dmy2 = "[0-3][0-9]-[0-1][0-9]-20[0-2][0-9]"
ymd = '20[0-2][0-9][0-1][0-9][0-3][0-9]'
ymd2 = '20[0-2][0-9]-[0-1][0-9]-[0-3][0-9]'

def obtener_credenciales():
    try:
        credentials = json.load(open("credentials.json"))
        username = credentials["user"]
        password = credentials["password"]
        domain = credentials["domain"]
    except:
        print("Credencials no trobats, cal introduir-los ara:")
        domain = input("Domini clickedu (nom de l'escola):")
        username = input("Usuari clickedu: ")
        password = getpass.getpass("Contrasenya: ")
    return username, password, domain

def inicia_sessió():
    """Inicia sesión en el sitio web y devuelve la sesión autenticada."""
    global BASE_URL
    username, password, domain = obtener_credenciales()
    BASE_URL = f"https://{domain}.clickedu.eu"
    session = requests.Session()
    payload = {
        'username': username,
        'password': password,
    }
    LOGIN_URL = f"{BASE_URL}/user.php?action=doLogin"
    response = session.post(LOGIN_URL, data=payload)

    if response.status_code == 200 and "Iniciar sessió" not in response.text:
        print("[+] Sessió iniciada")
        return session
    else:
        print("[-] Error en iniciar sessió")
        exit()

def obtener_todas_paginas(session):
    """Itera dinámicamente por todas las páginas de álbumes hasta que no existan más (menos de 6 álbumes)."""
    paginas = []
    page_number = 1
    ALBUMS_URL_TEMPLATE = f"{BASE_URL}/students/albums_fotos.php?accio=llistar&pag={{}}&lloc=fotos"
    while True:
        url_pagina = ALBUMS_URL_TEMPLATE.format(page_number)
        response = session.get(url_pagina)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Buscar contenedores de álbumes en la página actual
        contenedores_albumes = soup.find_all('div', class_='foto_albums_llistat_2')
        if len(contenedores_albumes) > 0:
            paginas.append(url_pagina)
            print(f"[+] Página {page_number} detectada con {len(contenedores_albumes)} álbumes.")
            if len(contenedores_albumes) < 6:  # Menos de 6 álbumes, probablemente sea la última página
                print("[+] Última página detectada.")
                break
            page_number += 1
        else:
            print("[+] No se encontraron más páginas.")
            break

    return paginas

def obtener_enlaces_albumes_y_nombres(session, url):
    """Obtiene los enlaces de todos los álbumes y sus nombres en una página específica."""
    response = session.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Buscar enlaces de álbumes
    albums = {}
    contenedores_albumes = soup.find_all('div', class_='foto_albums_llistat_2')
    for contenedor in contenedores_albumes:
        enlace = contenedor.find('a', href=True)
        nombre_div = contenedor.find('div', class_='Gran negreta')
        if enlace and nombre_div:
            enlace_album = BASE_URL + "/students/" + enlace['href']
            nombre_album = nombre_div.get_text(strip=True).split("(")[0].strip().replace("\n", " ").replace("\r", "").replace("/", "-")
            albums[nombre_album] = enlace_album

    return albums

def obtener_fotos_album(session, album_url):
    """Obtiene las URLs de las fotos de un álbum."""
    response = session.get(album_url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Buscar todas las fotos grandes dentro del álbum
    fotos = []
    galeria = soup.find('ul', class_='image-gallery')  # Buscar el contenedor de la galería
    if galeria:
        enlaces = galeria.find_all('a', href=True)  # Buscar todos los enlaces <a> en la galería
        for enlace in enlaces:
            foto_url = enlace['href']
            if foto_url.startswith("http") and "/grans/" in foto_url:  # Solo incluir fotos grandes
                fotos.append(foto_url)

    if not fotos:
        print(f"    [-] No se encontraron fotos en el álbum: {album_url}")

    return fotos

def update_exif_date(fn):
    with open(fn, 'rb') as image_file:
        img = eImage(image_file)
    try:
        date = img.datetime
    except:
        date = None
    if date and not date.startswith("0000"):
        date = datetime.datetime.strptime(date, '%Y:%m:%d %H:%M:%S')
        year = date.year
        month = date.month
        day = date.day
        return (date.year, date.month, date.day)
    else:
        year = month = day = None
        bn = os.path.basename(fn)
        m = re.search(dmy, bn)
        if m:
            g = m.group(0)
            month = g[2:4]
            year = g[4:8]
            day = g[0:2]
        else:
            m = re.search(ymd, bn)
        if m and not year:
            g = m.group(0)
            day = g[6:8]
            year = g[0:4]
            month = g[4:6]
        else:
            m = re.search(dmy2, bn)
        if m and not year:
           day, month, year = m.group(0).split("-")
        else:
           m = re.search(ymd2, bn)
        if m and not year:
           year, month, day = m.group(0).split("-")
        else:
           pass #more m
    if month and int(month) > 12:
        if day and int(day) < 13:
            month, day = day, month
        else:
            year = month = day = None
    if not year:
        year = str(NOW.year)
        month = str(NOW.month).zfill(2)
        day = str(NOW.day).zfill(2)
    print(f"Updating EXIF data for {fn} to {year}:{month}:{day}")
    img.datetime = '{}:{}:{} 00:00:00'.format(year, month, day)
    with open(fn, 'wb') as image_file:
        image_file.write(img.get_file())
    return (year, month, day)

def descargar_fotos(session, fotos, folder):
    """Descarga las fotos desde las URLs obtenidas."""
    album_path = os.path.join(DOWNLOAD_FOLDER, folder)
    if not os.path.exists(album_path):
        os.makedirs(album_path)

    for foto_url in fotos:
        filename = os.path.join(album_path, os.path.basename(foto_url))
        if os.path.exists(filename):
            print(f"    Foto prèviament descarregada {os.path.basename(foto_url)}")
            update_exif_date(filename)
            continue
        try:
            response = session.get(foto_url, stream=True, timeout=10)
            if response.status_code == 200:
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                update_exif_date(filename)
                print(f"[+] Foto descarregada: {filename}", end="\r")
            else:
                print(f"[-] Error en descarregar: {foto_url}")
        except Exception as e:
            print(f"[-] No es pot descarregar la foto {foto_url}: {e}")

def llista_àlbums(sessió=None):
    if sessió is None:
        sessió = inicia_sessió()
    # Obtener todas las páginas de álbumes
    paginas = obtener_todas_paginas(sessió)
    print(f"[+]  {len(paginas)} pàgines d'àlbums trobades.")
    # Recopilar todos los álbumes de todas las páginas
    àlbums_totals = {}
    for pagina_url in paginas:
        albums = obtener_enlaces_albumes_y_nombres(session, pagina_url)
        àlbums_totals.update(albums)
    print(f"[+] S'han trobat {len(àlbums_totals)} àlbums en total.")
    return àlbums_totals

if __name__ == "__main__":
    session = inicia_sessió()

    àlbums = llista_àlbums(session)
    #".*I3.*"xui
    for nom, aurl in àlbums.items():
        if nom not in WANTED_ALBUMS: continue
        print(f"[+] Processant àlbum: {nom}")
        fotos = obtener_fotos_album(session, aurl)
        print(f"     {len(fotos)} fotos trobades.")
        descargar_fotos(session, fotos, nom)

    # Descargar fotos de cada álbum
    # for album_url, nombre_album in todos_los_albumes:
    #     print(f"[+] Procesando álbum: {nombre_album}")
    #     fotos = obtener_fotos_album(session, album_url)
    #     print(f"    Se encontraron {len(fotos)} fotos en el álbum '{nombre_album}'.")
    #     descargar_fotos(session, fotos, nombre_album)



