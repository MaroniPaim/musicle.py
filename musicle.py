import streamlit as st
import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import random
from datetime import datetime

# ========== REMOVER ÍCONES DE ÂNCORA ==========
st.markdown(
    """<style>
    .stMarkdown h1 a, .stMarkdown h2 a, .stMarkdown h3 a, .stMarkdown h4 a, .stMarkdown h5 a, .stMarkdown h6 a {
        display: none;
    }
    </style>""",
    unsafe_allow_html=True
)

# ========== CONFIGURAÇÃO DO SPOTIFY ==========
SPOTIPY_CLIENT_ID = "fb5a13371bb54f2e95951eab6ba3412a"
SPOTIPY_CLIENT_SECRET = "bd9af6218f31416698ea259416a88113"

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET
))

# ========== UTILITÁRIAS ==========
def country_to_flag(code):
    return ''.join(chr(ord(char) + 127397) for char in code.upper()) if len(code) == 2 else code

def get_color(feedback):
    return {"🎯": "green", "🟡": "#FFD700", "⚪": "#555555"}.get(feedback, "#555555")

def format_number(n):
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    elif n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)

def styled_box(label, value, color, arrow=None):
    arrow_str = f" {arrow}" if arrow else ""
    return f"""
    <div style='background-color: {color}; padding: 6px; border-radius: 8px; text-align: center; margin: 3px; min-height: 65px;'>
        <h6 style='margin: 0; color: white; font-size: 11px;'>{label}</h6>
        <h4 style='margin: 0; color: white; font-size: 15px;'>{value}{arrow_str}</h4>
    </div>"""

# ========== BUSCAS ==========
@st.cache_data(ttl=3600)
def buscar_dados_artist_spotify(nome):
    try:
        resultado = sp.search(q=nome, type='artist', limit=1)
        artista = resultado['artists']['items'][0]
        return {
            "nome": artista['name'],
            "seguidores": artista['followers']['total'],
            "id_spotify": artista['id'],
            "popularidade": artista['popularity'],
            "imagem": artista['images'][0]['url'] if artista['images'] else None,
            "genero_musical": artista['genres'] or ['Desconhecido']
        }
    except:
        return None

@st.cache_data(ttl=3600)
def buscar_dados_artist_musicbrainz(nome):
    try:
        headers = {"User-Agent": "MusicleGame/1.0 (email@dominio.com)"}
        url = f"https://musicbrainz.org/ws/2/artist/?query=artist:{nome}&fmt=json&limit=1"
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
        if 'artists' not in data or not data['artists']:
            return None

        artista = data['artists'][0]
        mbid = artista['id']
        pais = artista.get('begin-area', {}).get('iso-3166-1-codes', [None])[0] or artista.get('country', 'Desconhecido')
        tipo = artista.get('type', 'Desconhecido')
        if tipo == "Group":
         genero_pessoa = "Grupo"
        else:
            genero_raw = artista.get("gender", "").lower()
            if genero_raw == "male":
                genero_pessoa = "Masculino"
            elif genero_raw == "female":
                genero_pessoa = "Feminino"
            elif genero_raw == "other":
                genero_pessoa = "Outro"
            else:
                genero_pessoa = "Desconhecido"


        nascimento_str = artista.get('life-span', {}).get('begin', None)
        idade = 'Desconhecido'
        if nascimento_str:
            try:
                nascimento = datetime.strptime(nascimento_str, '%Y-%m-%d') if '-' in nascimento_str else datetime.strptime(nascimento_str, '%Y')
                hoje = datetime.today()
                idade = hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))
            except:
                pass

        url_album = f"https://musicbrainz.org/ws/2/release-group?artist={mbid}&type=album&fmt=json&limit=100"
        albuns = requests.get(url_album, headers=headers).json().get('release-groups', [])
        albuns_validos = [(a['title'], a['first-release-date'][:4]) for a in albuns if 'first-release-date' in a and a['first-release-date'][:4].isdigit()]
        album_inicio, ano_inicio = (albuns_validos and min(albuns_validos, key=lambda x: int(x[1]))) or ("Desconhecido", "Desconhecido")

        return {
            "pais": pais,
            "ano_inicio": ano_inicio,
            "album_inicio": album_inicio,
            "tipo": tipo,
            "genero_pessoa": genero_pessoa,
            "idade": idade
        }
    except:
        return None

# ========== LÓGICA DE JOGO ==========

st.title("🎤 Musicle - Descubra o Artista do Dia")
modo = st.sidebar.selectbox("Modo:", ["Jogar", "Admin"])

if 'tentativas' not in st.session_state:
    st.session_state.tentativas = []

if modo == "Admin":
    nome = st.text_input("Defina o artista do dia:")
    if st.button("Definir"):
        s = buscar_dados_artist_spotify(nome)
        m = buscar_dados_artist_musicbrainz(nome)
        if s and m:
            st.session_state.artista_dia = {**s, **m}
            st.session_state.tentativas = []
            st.success(f"🎯 Artista definido: {s['nome']}")
        else:
            st.error("Não foi possível definir o artista.")

if modo == "Jogar":
    if 'artista_dia' not in st.session_state:
        st.info("Admin precisa definir o artista do dia.")
    else:
        if len(st.session_state.tentativas) < 3:
            nome = st.text_input("Digite o nome do artista:")
            if st.button("Enviar"):
                s = buscar_dados_artist_spotify(nome)
                m = buscar_dados_artist_musicbrainz(nome)
                if s and m:
                    tentativa = {**s, **m}
                    alvo = st.session_state.artista_dia
                    acertou = tentativa['nome'].lower() == alvo['nome'].lower()
                    fb = None
                    if not acertou:
                        fb = {
                            'seguidores': "🎯" if tentativa['seguidores'] == alvo['seguidores'] else "🟡" if abs(tentativa['seguidores'] - alvo['seguidores']) <= 1e6 else "⚪",
                            'popularidade': "🎯" if tentativa['popularidade'] == alvo['popularidade'] else "🟡" if abs(tentativa['popularidade'] - alvo['popularidade']) <= 5 else "⚪",
                            'genero_musical': "🎯" if set(tentativa['genero_musical']) == set(alvo['genero_musical']) else "🟡" if set(tentativa['genero_musical']) & set(alvo['genero_musical']) else "⚪",
                            'pais': "🎯" if tentativa['pais'] == alvo['pais'] else "⚪",
                            'ano_inicio': "🎯" if tentativa['ano_inicio'] == alvo['ano_inicio'] else "🟡" if abs(int(tentativa['ano_inicio']) - int(alvo['ano_inicio'])) <= 2 else "⚪",
                            'tipo': "🎯" if tentativa['tipo'] == alvo['tipo'] else "⚪",
                            'genero_pessoa': "🎯" if tentativa['genero_pessoa'] == alvo['genero_pessoa'] else "⚪"
                        }
                    st.session_state.tentativas.insert(0, (tentativa, fb, acertou))

        for i, (t, fb, acertou) in enumerate(st.session_state.tentativas):
            st.subheader(f"Tentativa {len(st.session_state.tentativas)-i}: {t['nome']}")
            if t['imagem']:
                st.image(t['imagem'], width=100)
            col1, col2, col3 = st.columns(3)
            if acertou:
                st.balloons()  # ANIMAÇÃO PARA ACERTO
                col1.markdown(styled_box("Debut", f"{t['ano_inicio']} ({t['album_inicio']})", "green"), unsafe_allow_html=True)
                col2.markdown(styled_box("Seguidores", format_number(t['seguidores']), "green", "🎯"), unsafe_allow_html=True)
                col3.markdown(styled_box("Popularidade", f"#{t['popularidade']}", "green", "🎯"), unsafe_allow_html=True)
                col4, col5, col6 = st.columns(3)
                col4.markdown(styled_box("Gênero Musical", ', '.join(t['genero_musical']), "green"), unsafe_allow_html=True)
                col5.markdown(styled_box("País", f"{country_to_flag(t['pais'])} {t['pais']}", "green"), unsafe_allow_html=True)
                col6.markdown(styled_box("Tipo", t['tipo'], "green"), unsafe_allow_html=True)
                st.success("🎉 Você acertou! Confira mais sobre o artista no Spotify:")
                spotify_url = f"https://open.spotify.com/artist/{t['id_spotify']}"
                st.markdown(f"[🔗 Ir para o perfil de {t['nome']} no Spotify]({spotify_url})", unsafe_allow_html=True)

            else:
                col1.markdown(styled_box("Debut", f"{t['ano_inicio']} ({t['album_inicio']})", get_color(fb['ano_inicio']), "↑" if t['ano_inicio'] < st.session_state.artista_dia['ano_inicio'] else "↓"), unsafe_allow_html=True)
                col2.markdown(styled_box("Seguidores", format_number(t['seguidores']), get_color(fb['seguidores']), "↑" if t['seguidores'] < st.session_state.artista_dia['seguidores'] else "↓"), unsafe_allow_html=True)
                col3.markdown(styled_box("Popularidade", f"#{t['popularidade']}", get_color(fb['popularidade']), "↑" if t['popularidade'] < st.session_state.artista_dia['popularidade'] else "↓"), unsafe_allow_html=True)
                col4, col5, col6 = st.columns(3)
                col4.markdown(styled_box("Gênero Musical", ', '.join(t['genero_musical']), get_color(fb['genero_musical'])), unsafe_allow_html=True)
                col5.markdown(styled_box("País", f"{country_to_flag(t['pais'])} {t['pais']}", get_color(fb['pais'])), unsafe_allow_html=True)
                col6.markdown(styled_box("Tipo", t['tipo'], get_color(fb['tipo'])), unsafe_allow_html=True)
