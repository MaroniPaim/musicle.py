import streamlit as st  # Interface interativa
import requests           # Requisições HTTP
import spotipy            # Cliente Spotify API
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.exceptions import SpotifyException
from datetime import datetime

# ========== REMOVER ÍCONES DE LINK E MASCARAR INPUT ADMIN ==========
st.markdown("""
  <style>
    /* remove âncoras/link-icons de headers */
    h1 a, h2 a, h3 a, h4 a, h5 a, h6 a,
    a.anchor-link { display: none !important; }
    /* mascara o input do Admin sem usar type="password" */
    input[placeholder="Defina o artista..."] {
      -webkit-text-security: disc;
    }
  </style>
""", unsafe_allow_html=True)

# ========== CONFIGURAÇÃO DO SPOTIFY ==========
SPOTIPY_CLIENT_ID = "fb5a13371bb54f2e95951eab6ba3412a"
SPOTIPY_CLIENT_SECRET = "bd9af6218f31416698ea259416a88113"
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET
))

# ========== DEFAULTS DO MUSICBRAINZ ==========
DEFAULT_MB = {
    "pais": "Desconhecido",
    "ano_inicio": "Desconhecido",
    "album_inicio": "Desconhecido",
    "tipo": "Desconhecido",
    "genero_pessoa": "Desconhecido",
    "idade": "Desconhecido",
    "genero_musical": ["Desconhecido"]
}

# ========== UTILITÁRIAS ==========
def country_to_flag(code):
    return ''.join(chr(ord(c) + 127397) for c in code.upper()) if len(code)==2 else code

def get_color(fb):
    return {"🎯":"green","🟡":"#FFD700","⚪":"#555555"}.get(fb,"#555555")

def format_number(n):
    if n>=1_000_000_000: return f"{n/1_000_000_000:.1f}B"
    if n>=1_000_000:     return f"{n/1_000_000:.1f}M"
    if n>=1_000:         return f"{n/1_000:.1f}K"
    return str(n)

def styled_box(label, value, color, arrow=None):
    arrow_str = f" {arrow}" if arrow else ""
    return f"""
    <div style='background-color:{color};
                padding:8px;border-radius:12px;
                text-align:center;margin:6px;
                min-height:80px;'>
      <h6 style='margin:0;color:white;font-size:14px;'>{label}</h6>
      <h4 style='margin:0;color:white;font-size:20px;'>{value}{arrow_str}</h4>
    </div>"""

# ========== BUSCA SPOTIFY COM TRATAMENTO DE ERROS ==========
@st.cache_data(ttl=3600)
def buscar_spotify(nome):
    try:
        r = sp.search(q=nome, type='artist', limit=1)
    except SpotifyException:
        st.error("⚠️ Problema de comunicação com Spotify. Tente novamente em alguns minutos.")
        return None
    except Exception:
        st.error("⚠️ Erro inesperado ao consultar Spotify.")
        return None

    items = r.get('artists',{}).get('items',[])
    if not items:
        st.warning("😕 Artista não encontrado. Verifique a grafia e tente novamente.")
        return None

    a = items[0]
    return {
        "nome": a['name'],
        "seguidores": a['followers']['total'],
        "popularidade": a['popularity'],
        "imagem": a['images'][0]['url'] if a['images'] else None,
        "genero_musical": a['genres'] or ['Desconhecido']
    }

# ========== BUSCA MUSICBRAINZ ==========
@st.cache_data(ttl=3600)
def buscar_musicbrainz(nome):
    try:
        headers = {"User-Agent":"MusicleGame/1.0"}
        url = f"https://musicbrainz.org/ws/2/artist/?query=artist:{nome}&fmt=json&limit=1"
        r = requests.get(url, headers=headers); r.raise_for_status()
        items = r.json().get('artists') or []
        if not items: return None
        a = items[0]
        mbid = a['id']
        pais = (a.get('begin-area',{}).get('iso-3166-1-codes',[None])[0]
                or a.get('country') or DEFAULT_MB["pais"])
        tipo = a.get('type') or DEFAULT_MB["tipo"]
        genero_pessoa = ("Grupo" if tipo=="Group" else
                         {"male":"Masculino","female":"Feminino","other":"Outro"}
                         .get(a.get('gender','').lower(), DEFAULT_MB["genero_pessoa"]))
        nasc = a.get('life-span',{}).get('begin')
        idade = DEFAULT_MB["idade"]
        if nasc:
            fmt = '%Y-%m-%d' if '-' in nasc else '%Y'
            dt = datetime.strptime(nasc, fmt)
            now = datetime.today()
            idade = now.year - dt.year - ((now.month,now.day)<(dt.month,dt.day))
        url2 = f"https://musicbrainz.org/ws/2/release-group?artist={mbid}&type=album&fmt=json&limit=100"
        rg = requests.get(url2, headers=headers).json().get('release-groups',[])
        v = [(x['title'],x['first-release-date'][:4])
             for x in rg if x.get('first-release-date','')[:4].isdigit()]
        album_inicio, ano_inicio = (min(v,key=lambda x:int(x[1]))
                                    if v else (DEFAULT_MB["album_inicio"],DEFAULT_MB["ano_inicio"]))
        url3 = f"https://musicbrainz.org/ws/2/artist/{mbid}?inc=tags&fmt=json"
        tags = requests.get(url3, headers=headers).json().get('tags',[])
        generos = [t['name'] for t in sorted(tags, key=lambda x:x.get('count',0), reverse=True)[:3]]
        return {
            "pais": pais,
            "ano_inicio": ano_inicio,
            "album_inicio": album_inicio,
            "tipo": tipo,
            "genero_pessoa": genero_pessoa,
            "idade": idade,
            "genero_musical": generos or DEFAULT_MB["genero_musical"]
        }
    except:
        return None

# ========== SETUP ARTISTA FIXO ==========
ARTISTA_FIXO = "Adele"
if 'artista_dia' not in st.session_state:
    init = buscar_spotify(ARTISTA_FIXO)
    mbi  = buscar_musicbrainz(ARTISTA_FIXO) or DEFAULT_MB
    if init:
        st.session_state.artista_dia = {**init, **mbi}
        st.session_state.tentativas = []

# ========== UI PRINCIPAL ==========
st.title("🎤 Musicle - Descubra o Artista do Dia")
modo = st.sidebar.selectbox("Modo:", ["Admin","Jogar"])

# ------- ADMIN -------
if modo=="Admin":
    nome_masked = st.text_input(
        "Defina o artista do dia:",
        placeholder="Defina o artista...",
        key="admin_in"
    )
    if st.button("Definir"):
        s = buscar_spotify(nome_masked)
        if s:
            m = buscar_musicbrainz(nome_masked) or DEFAULT_MB
            st.session_state.artista_dia = {**s, **m}
            st.session_state.tentativas = []
            st.success("🎯 Artista definido com sucesso!")

# ------- JOGAR -------
else:
    if 'artista_dia' not in st.session_state:
        st.info("Admin precisa definir o artista do dia.")
        st.stop()

    if 'tentativas' not in st.session_state:
        st.session_state.tentativas = []

    # input de palpite
    if len(st.session_state.tentativas)<7:
        palpite = st.text_input("Digite o nome do artista:", key="play_in")
        if st.button("Enviar", key="play_btn"):
            s = buscar_spotify(palpite)
            if s:
                m = buscar_musicbrainz(palpite) or DEFAULT_MB
                t = {**s, **m}
                alvo = st.session_state.artista_dia
                acertou = (t['nome'].lower()==alvo['nome'].lower())

                # feedback e arrows
                arrows, fb = {}, {}
                seg_t,seg_a = t["seguidores"],alvo["seguidores"]
                arrows["seguidores"]="↑" if seg_t<seg_a else "↓" if seg_t>seg_a else "→"
                fb["seguidores"]="🎯" if seg_t==seg_a else "🟡" if abs(seg_t-seg_a)<=1e6 else "⚪"
                pop_t,pop_a = t["popularidade"],alvo["popularidade"]
                arrows["popularidade"]="↑" if pop_t<pop_a else "↓" if pop_t>pop_a else "→"
                fb["popularidade"]="🎯" if pop_t==pop_a else "🟡" if abs(pop_t-pop_a)<=5 else "⚪"
                try:
                    ano_t,ano_a=int(t["ano_inicio"]),int(alvo["ano_inicio"])
                    arrows["ano_inicio"]="↑" if ano_t<ano_a else "↓" if ano_t>ano_a else "→"
                    fb["ano_inicio"]="🎯" if ano_t==ano_a else "🟡" if abs(ano_t-ano_a)<=2 else "⚪"
                except:
                    arrows["ano_inicio"],fb["ano_inicio"]="","⚪"
                fb["genero_musical"]="🎯" if set(t["genero_musical"])==set(alvo["genero_musical"]) else "🟡" if set(t["genero_musical"])&set(alvo["genero_musical"]) else "⚪"
                fb["pais"]="🎯" if t.get("pais")==alvo.get("pais") else "⚪"
                fb["tipo"]="🎯" if t.get("tipo")==alvo.get("tipo") else "⚪"
                fb["genero_pessoa"]="🎯" if t.get("genero_pessoa")==alvo.get("genero_pessoa") else "⚪"

                st.session_state.tentativas.insert(0,(t,fb,arrows,acertou))
        def styled_box(label, value, color, arrow=None):
            arrow_str = f" {arrow}" if arrow else ""
            return f"""
            <div style='
                background-color: {color};
                width: 100%;
                height: 120px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                padding: 8px;
                border-radius: 12px;
                margin: 6px;
                overflow: hidden;
            '>
            <h6 style='
                margin: 0;
                color: white;
                font-size: 14px;
                white-space: nowrap;
                text-overflow: ellipsis;
                overflow: hidden;
            '>{label}</h6>
            <h4 style='
                margin: 4px 0 0 0;
                color: white;
                font-size: 20px;
                line-height: 1.2;
                white-space: normal;
                word-wrap: break-word;
                text-align: center;
            '>{value}{arrow_str}</h4>
            </div>"""


    # exibe tentativas
    for t,fb,arrows,acertou in st.session_state.tentativas:
        # imagem + nome
        img_col,name_col = st.columns([1,3])
        if t.get("imagem"):
            img_html = f"<img src='{t['imagem']}' style='width:100px;height:100px;border-radius:50%;'>" 
            img_col.markdown(img_html, unsafe_allow_html=True)
        name_col.markdown(f"<h2 style='margin:0;font-size:2rem;color:white;'>{t['nome']}</h2>",
                          unsafe_allow_html=True)

        # linha 1: seguidores, popularidade, gênero musical
        c1,c2,c3 = st.columns(3)
        c1.markdown(styled_box("Seguidores", format_number(t["seguidores"]),
                               get_color(fb["seguidores"]), arrows["seguidores"]),
                    unsafe_allow_html=True)
        c2.markdown(styled_box("Popularidade", t["popularidade"],
                               get_color(fb["popularidade"]), arrows["popularidade"]),
                    unsafe_allow_html=True)
        c3.markdown(styled_box("Gênero Musical", ", ".join(t["genero_musical"]),
                               get_color(fb["genero_musical"])),
                    unsafe_allow_html=True)

        # linha 2: país, ano início, tipo, gênero pessoa
        d1,d2,d3,d4 = st.columns(4)
        flag = country_to_flag(t.get("pais","Desconhecido"))
# span com font-size grande
        flag_html = f"<span style='font-size:64px; line-height:1;'>{flag}</span>"

        d1.markdown(
            styled_box("País", flag_html, get_color(fb["pais"]), None),
            unsafe_allow_html=True
        )
        d2.markdown(styled_box("Ano Início", t.get("ano_inicio","Desconhecido"),
                               get_color(fb["ano_inicio"]), arrows["ano_inicio"]),
                    unsafe_allow_html=True)
        d3.markdown(styled_box("Tipo", t.get("tipo","Desconhecido"),
                               get_color(fb["tipo"])),
                    unsafe_allow_html=True)
        d4.markdown(styled_box("Gênero Pessoa", t.get("genero_pessoa","Desconhecido"),
                               get_color(fb["genero_pessoa"])),
                    unsafe_allow_html=True)

        if acertou:
            st.success("🎉 Acertou!")
            if st.session_state.artista_dia.get("imagem"):
                st.image(st.session_state.artista_dia["imagem"], width=180)
            break
