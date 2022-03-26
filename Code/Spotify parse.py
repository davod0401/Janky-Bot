import requests
from bs4 import BeautifulSoup

#print(requests.get('https://open.spotify.com/track/10oKSzRcwbZsog2uq2gb4b?si=666ebd0409e044b4').content)


def spotify_parse(search:str):
    '''Funcion que comprueba si la busqueda realizada es un enlace de spotify,
       si lo es extrae el titulo de la cancion y lo retorna,
       de lo contrario retorna la misma busqueda'''
       
    if search.startswith('https://open.spotify.com'):
        URL = search
        page = requests.get(URL)
        soup = BeautifulSoup(page.content, "html.parser")
        #print(soup.find('title'))
        title = soup.title.get_text().split('|')
        title_s = title[0]
        return title_s
    else:
        return search


search = input("Link de spotify\n")
print(spotify_parse(search))