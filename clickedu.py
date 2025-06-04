import os
import requests
from bs4 import BeautifulSoup
import getpass

# URLs base
BASE_URL = "https://dominiquesbcn.clickedu.eu"
LOGIN_URL = f"{BASE_URL}/user.php?action=doLogin"
ALBUMS_URL_TEMPLATE = f"{BASE_URL}/students/albums_fotos.php?accio=llistar&pag={{}}&lloc=fotos"

# Carpeta para guardar las fotos
DOWNLOAD_FOLDER = "fotos_descargadas"

def obtener_credenciales():
    username = input("Usuario en clickedu: ")
    password = getpass.getpass("Introduce tu contraseña: ")
    return username, password

def iniciar_sesion(username, password):
    """Inicia sesión en el sitio web y devuelve la sesión autenticada."""
    session = requests.Session()
    payload = {
        'username': username,
        'password': password,
    }
    response = session.post(LOGIN_URL, data=payload)

    if response.status_code == 200 and "Iniciar sessió" not in response.text:
        print("[+] Inicio de sesión exitoso")
        return session
    else:
        print("[-] Error al iniciar sesión")
        exit()

def obtener_todas_paginas(session):
    """Itera dinámicamente por todas las páginas de álbumes hasta que no existan más (menos de 6 álbumes)."""
    paginas = []
    page_number = 1
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
    albumes = []
    contenedores_albumes = soup.find_all('div', class_='foto_albums_llistat_2')
    for contenedor in contenedores_albumes:
        enlace = contenedor.find('a', href=True)
        nombre_div = contenedor.find('div', class_='Gran negreta')
        if enlace and nombre_div:
            enlace_album = BASE_URL + "/students/" + enlace['href']
            nombre_album = nombre_div.get_text(strip=True).split("(")[0].strip().replace("\n", " ").replace("\r", "").replace("/", "-")
            albumes.append((enlace_album, nombre_album))

    return albumes

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

def descargar_fotos(session, fotos, album_nombre):
    """Descarga las fotos desde las URLs obtenidas."""
    album_path = os.path.join(DOWNLOAD_FOLDER, album_nombre)
    if not os.path.exists(album_path):
        os.makedirs(album_path)

    for i, foto_url in enumerate(fotos, 1):
        try:
            response = session.get(foto_url, stream=True, timeout=10)
            if response.status_code == 200:
                filename = os.path.join(album_path, f"foto_{i}.jpg")
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                print(f"[+] Foto descargada: {filename}")
            else:
                print(f"[-] Error al descargar: {foto_url}")
        except Exception as e:
            print(f"[-] No se pudo descargar la foto {foto_url}: {e}")

def main():
    username, password = obtener_credenciales()
    session = iniciar_sesion(username, password)

    # Obtener todas las páginas de álbumes
    paginas = obtener_todas_paginas(session)
    print(f"[+] Se encontraron {len(paginas)} páginas de álbumes.")

    # Recopilar todos los álbumes de todas las páginas
    todos_los_albumes = []
    for pagina_url in paginas:
        albumes = obtener_enlaces_albumes_y_nombres(session, pagina_url)
        todos_los_albumes.extend(albumes)

    print(f"[+] Se encontraron {len(todos_los_albumes)} álbumes en total.")

    # Descargar fotos de cada álbum
    for album_url, nombre_album in todos_los_albumes:
        print(f"[+] Procesando álbum: {nombre_album}")
        fotos = obtener_fotos_album(session, album_url)
        print(f"    Se encontraron {len(fotos)} fotos en el álbum '{nombre_album}'.")
        descargar_fotos(session, fotos, nombre_album)

if __name__ == "__main__":
    main()


