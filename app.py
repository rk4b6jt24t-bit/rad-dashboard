import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd

# Configuración de página
st.set_page_config(page_title="Abdominal Radiology Hub", layout="wide", page_icon="🩻")

if 'favorites' not in st.session_state:
    st.session_state.favorites = []

# --- DICCIONARIO DE REVISTAS (ENFOQUE ABDOMINAL) ---
JOURNALS = {
    "Abdominal Radiology (NY)": '"Abdom Radiol (NY)"[jour]',
    "Radiology": '"Radiology"[jour]',
    "RadioGraphics": '"RadioGraphics"[jour]',
    "AJR (Am J Roentgenol)": '"AJR Am J Roentgenol"[jour]',
    "European Radiology": '"Eur Radiol"[jour]',
    "Clinical Radiology (UK)": '"Clin Radiol"[jour]',
    "Canadian Assoc of Radiologists Journal": '"Can Assoc Radiol J"[jour]',
    "British Journal of Radiology": '"Br J Radiol"[jour]',
    "Radiología (Engl Ed)": '"Radiologia(Engl Ed)"[jour]'
}

@st.cache_data(ttl=3600)
def fetch_pubmed_articles(journal_query, max_results=20):
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": f"{journal_query} AND (hasabstract[text])",
        "retmode": "json",
        "retmax": max_results,
        "sort": "date"
    }
    try:
        response = requests.get(search_url, params=params).json()
        return response.get("esearchresult", {}).get("idlist", [])
    except Exception:
        return []

@st.cache_data(ttl=3600)
def get_article_details(id_list):
    if not id_list: return []
    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {"db": "pubmed", "id": ",".join(id_list), "retmode": "xml"}
    try:
        response = requests.get(fetch_url, params=params)
        root = ET.fromstring(response.content)
        articles = []
        for article in root.findall(".//PubmedArticle"):
            pmid = article.find(".//PMID").text
            title = article.find(".//ArticleTitle").text
            abstract_el = article.find(".//AbstractText")
            abstract = abstract_el.text if abstract_el is not None else "Resumen no disponible."
            
            doi = None
            for el in article.findall(".//ArticleId"):
                if el.attrib.get("IdType") == "doi": doi = el.text
            
            pub_date_el = article.find(".//JournalIssue/PubDate")
            year = pub_date_el.find("Year")
            month = pub_date_el.find("Month")
            date_str = f"{year.text if year is not None else ''} {month.text if month is not None else ''}".strip()
            
            articles.append({
                "pmid": pmid, "title": title, "abstract": abstract, 
                "doi": doi, "date": date_str if date_str else "N/A"
            })
        return articles
    except Exception:
        return []

def check_pdf_availability(doi, pmid):
    links = {"abstract": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "pdf": None}
    if doi:
        unpaywall_url = f"https://api.unpaywall.org/v2/{doi}?email=research@example.com"
        try:
            res = requests.get(unpaywall_url, timeout=3).json()
            if res.get("is_oa"):
                pdf_url = res.get("best_oa_location", {}).get("url_for_pdf")
                if pdf_url: links["pdf"] = pdf_url
        except Exception:
            pass
    return links

def add_to_favorites(article):
    if not any(fav['pmid'] == article['pmid'] for fav in st.session_state.favorites):
        st.session_state.favorites.append(article)

# --- INTERFAZ ---
st.title("🩻 Abdominal Radiology Monitor")

with st.sidebar:
    st.header("⚙️ Ajustes de Búsqueda")
    selected_journal_name = st.selectbox("Selecciona una revista:", list(JOURNALS.keys()))
    max_articles = st.slider("Artículos a cargar:", 10, 100, 30)
    
    st.markdown("---")
    st.subheader("🔍 Filtros de Abdomen")
    # Filtros 100% enfocados en diagnóstico abdominal, GI y hepatobiliar
    quick_filters = st.multiselect("Etiquetas rápidas:", 
                                   ["Hepatobiliary", "LI-RADS", "Pancreas", "Rectal MRI", "Crohn", "Prostate", "HCC", "Cholangiocarcinoma", "O-RADS"])
    search_keyword = st.text_input("...o busca texto libre (ej. 'fistula'):", "")
    
    st.markdown("---")
    st.subheader(f"⭐ Mis Favoritos ({len(st.session_state.favorites)})")
    
    if st.session_state.favorites:
        df_favs = pd.DataFrame(st.session_state.favorites)
        csv = df_favs[['date', 'title', 'pmid', 'doi']].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Exportar Favoritos (CSV)",
            data=csv,
            file_name='articulos_abdomen.csv',
            mime='text/csv',
        )
        
        for fav in st.session_state.favorites:
            st.caption(f"- [{fav['title'][:40]}...](https://pubmed.ncbi.nlm.nih.gov/{fav['pmid']}/)")
        
        if st.button("🗑️ Borrar favoritos"):
            st.session_state.favorites = []
            st.rerun()

journal_query = JOURNALS[selected_journal_name]

with st.spinner(f"Consultando PubMed para {selected_journal_name}..."):
    id_list = fetch_pubmed_articles(journal_query, max_results=max_articles)
    articles = get_article_details(id_list)

if not articles:
    st.warning("No se encontraron artículos o PubMed no responde.")
else:
    filtros_activos = quick_filters + ([search_keyword] if search_keyword else [])
    
    if filtros_activos:
        filtered_articles = []
        for art in articles:
            if any(f.lower() in art["title"].lower() or f.lower() in art["abstract"].lower() for f in filtros_activos):
                filtered_articles.append(art)
        articles = filtered_articles

    st.subheader(f"Resultados ({len(articles)})")
    st.write("---")

    for art in articles:
        col1, col2 = st.columns([0.8, 0.2])
        
        with col1:
            st.markdown(f"**{art['title']}**")
            st.caption(f"📅 {art['date']} | PMID: {art['pmid']}")
            
            with st.expander("Leer Resumen (Abstract)"):
                st.write(art['abstract'])
                
        with col2:
            st.button("⭐ Guardar", key=f"fav_{art['pmid']}", on_click=add_to_favorites, args=(art,), use_container_width=True)
            
            with st.spinner("PDF..."):
                links = check_pdf_availability(art['doi'], art['pmid'])
            
            if links["pdf"]:
                st.link_button("📥 PDF (Gratis)", links["pdf"], type="primary", use_container_width=True)
            else:
                st.link_button("🌐 PubMed", links["abstract"], type="secondary", use_container_width=True)
        
        st.write("---")
