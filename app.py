"""
app.py  –  Dashboard de Gestão de OAEs (Obras de Arte Especiais)
Ferroviário · Manutenção & Confiabilidade Estrutural
"""

import io
import numpy as np
import pandas as pd
import streamlit as st
from pathlib import Path
from streamlit_folium import st_folium

from data_loader import build_master_df, RAAE_HEX, CONDITION_COLORS
from map_builder  import build_map, COND_HEX, SI_COLOR

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Dashboard OAE – Gestão Estrutural",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS global para ajustes visuais
st.markdown("""
<style>
  section[data-testid="stSidebar"] { background:#1e2a38; }
  section[data-testid="stSidebar"] * { color:#ecf0f1 !important; }
  .metric-card {
    background:#1e2a38; border-radius:10px; padding:16px 20px;
    color:#ecf0f1; text-align:center;
  }
  .metric-card .value { font-size:2rem; font-weight:700; }
  .metric-card .label { font-size:.8rem; opacity:.8; margin-top:4px; }
  .si-alert {
    background:#ffeaa7; border-left:5px solid #d63031;
    padding:10px 14px; border-radius:6px; margin-bottom:8px;
  }
  div[data-testid="stDataFrame"] { border-radius:8px; overflow:hidden; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# FUNÇÕES AUXILIARES DE UI
# ---------------------------------------------------------------------------

def metric_card(label: str, value, color: str = "#3498db") -> str:
    return f"""
    <div class="metric-card" style="border-top:4px solid {color};">
      <div class="value" style="color:{color};">{value}</div>
      <div class="label">{label}</div>
    </div>
    """


def color_condition(val):
    """Estilo de célula para condições numéricas no dataframe."""
    try:
        n = int(float(val))
        colors = {1:"#d5f5e3",2:"#d6eaf8",3:"#fef9e7",4:"#fdebd0",5:"#fadbd8"}
        return f"background-color:{colors.get(n,'')};font-weight:bold;"
    except (TypeError, ValueError):
        if str(val) == "S.I.":
            return "background-color:#fadbd8;color:#922b21;font-weight:bold;"
        return ""


def raae_color_row(val):
    colors = {"Baixo":"#d5f5e3","Médio":"#fef9e7","Alto":"#fdebd0",
              "Muito Alto":"#fadbd8","Extremo":"#e8daef"}
    return f"background-color:{colors.get(str(val).strip(),'')};"


# ---------------------------------------------------------------------------
# CARREGAMENTO E CACHE DOS DADOS
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Carregando dados do Excel...")
def load_data(path: str) -> pd.DataFrame:
    return build_master_df(path)


# ---------------------------------------------------------------------------
# SIDEBAR – UPLOAD E FILTROS
# ---------------------------------------------------------------------------

with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Emblem_of_Brazil.svg/120px-Emblem_of_Brazil.svg.png", width=60)
    st.title("OAE · Gestão Estrutural")
    st.markdown("---")

    uploaded = st.file_uploader(
        "📂 Carregar arquivo Excel (.xlsx)",
        type=["xlsx"],
        help="Selecione o arquivo com as abas 'Dados Fixos' e 'Inspeção Rotineira'.",
    )
    st.markdown("---")

    if uploaded:
        tmp_path = Path("tmp_oae_data.xlsx")
        tmp_path.write_bytes(uploaded.read())
        excel_path = str(tmp_path)
        st.success(f"Arquivo: **{uploaded.name}**")
    else:
        # Tenta encontrar um Excel na pasta do projeto
        candidates = sorted(Path(".").glob("*.xlsx")) + sorted(Path("..").glob("*.xlsx"))
        if candidates:
            excel_path = str(candidates[0])
            st.info(f"Usando: **{candidates[0].name}**")
        else:
            excel_path = None

# ---------------------------------------------------------------------------
# CARREGAMENTO DOS DADOS
# ---------------------------------------------------------------------------

if not excel_path:
    st.markdown("## 🏗️ Dashboard de Gestão de OAEs")
    st.info("👈 Faça o upload do arquivo Excel na barra lateral para iniciar.")
    st.stop()

try:
    df = load_data(excel_path)
except Exception as e:
    st.error(f"Erro ao carregar o arquivo: {e}")
    st.exception(e)
    st.stop()

if df.empty:
    st.warning("Nenhum dado encontrado no arquivo.")
    st.stop()

# ---------------------------------------------------------------------------
# SIDEBAR – FILTROS (só aparecem depois que os dados carregam)
# ---------------------------------------------------------------------------

with st.sidebar:
    st.subheader("🔍 Filtros")

    # Tipo de OAE
    tipos = sorted(df["tipo"].dropna().unique().tolist())
    sel_tipo = st.multiselect("Tipo de OAE", tipos, default=tipos)

    # Cidade
    cidades = sorted(df["cidade"].dropna().unique().tolist())
    sel_cidade = st.multiselect("Cidade", cidades, default=cidades)

    # RAAE
    raae_vals = sorted(df["raae"].dropna().unique().tolist())
    sel_raae = st.multiselect("RAAE", raae_vals, default=raae_vals)

    # Estaticidade
    estat_vals = sorted(df["estaticidade"].dropna().unique().tolist())
    sel_estat = st.multiselect("Estaticidade", estat_vals, default=estat_vals)

    # Tabuleiro
    tab_vals = sorted(df["tabuleiro"].dropna().unique().tolist())
    sel_tab = st.multiselect("Tabuleiro", tab_vals, default=tab_vals)

    # Ano de construção
    ano_min = int(df["ano"].dropna().min()) if not df["ano"].dropna().empty else 1900
    ano_max = int(df["ano"].dropna().max()) if not df["ano"].dropna().empty else 2025
    sel_ano = st.slider("Ano de Construção", ano_min, ano_max, (ano_min, ano_max))

    # Manifestação Patológica (multiselect baseado em palavras-chave)
    todas_pat = set()
    for p in df["patologia"].dropna():
        for token in str(p).split():
            if len(token) > 3:
                todas_pat.add(token.capitalize())
    sel_pat = st.multiselect("Manifestação Patológica", sorted(todas_pat))

    st.markdown("---")
    st.markdown("**Coloração do Mapa**")
    color_mode = st.radio(
        "Critério de cor dos marcadores",
        options=["condition", "raae"],
        format_func=lambda x: "Condição Geral" if x == "condition" else "RAAE",
        index=0,
    )

    mostrar_si = st.checkbox("Destacar S.I. no topo da tabela", value=True)

# ---------------------------------------------------------------------------
# APLICAÇÃO DOS FILTROS
# ---------------------------------------------------------------------------

mask = pd.Series([True] * len(df), index=df.index)

if sel_tipo:
    mask &= df["tipo"].isin(sel_tipo)
if sel_cidade:
    mask &= df["cidade"].isin(sel_cidade)
if sel_raae:
    mask &= df["raae"].isin(sel_raae)
if sel_estat:
    mask &= df["estaticidade"].isin(sel_estat)
if sel_tab:
    mask &= df["tabuleiro"].isin(sel_tab)

ano_col = pd.to_numeric(df["ano"], errors="coerce")
mask &= (ano_col >= sel_ano[0]) & (ano_col <= sel_ano[1])

if sel_pat:
    pat_mask = pd.Series([False] * len(df), index=df.index)
    for kw in sel_pat:
        pat_mask |= df["patologia"].str.contains(kw, case=False, na=False)
    mask &= pat_mask

df_filtered = df[mask].copy()

# ---------------------------------------------------------------------------
# CABEÇALHO E KPIs
# ---------------------------------------------------------------------------

st.markdown("## 🏗️ Dashboard de Gestão de OAEs – Ferroviário")
st.caption("Inspeção Rotineira · Confiabilidade Estrutural · VALEC / EFVM")
st.markdown("---")

total       = len(df_filtered)
si_count    = int(df_filtered["sem_inspecao"].sum())
raae_alto   = int(df_filtered["raae"].isin(["Alto","Muito Alto","Extremo"]).sum())
cond_critica = int(
    pd.to_numeric(df_filtered["insp_geral"], errors="coerce")
    .apply(lambda x: x >= 4 if not np.isnan(x) else False)
    .sum()
)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(metric_card("Total de OAEs", total, "#3498db"), unsafe_allow_html=True)
with c2:
    color = "#e74c3c" if si_count > 0 else "#27ae60"
    st.markdown(metric_card("Sem Inspeção (S.I.)", si_count, color), unsafe_allow_html=True)
with c3:
    color = "#e67e22" if raae_alto > 0 else "#27ae60"
    st.markdown(metric_card("RAAE Alto / Muito Alto / Extremo", raae_alto, color), unsafe_allow_html=True)
with c4:
    color = "#e74c3c" if cond_critica > 0 else "#27ae60"
    st.markdown(metric_card("Condição Crítica (≥ 4)", cond_critica, color), unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# ALERTAS DE S.I.
# ---------------------------------------------------------------------------

si_rows = df_filtered[df_filtered["sem_inspecao"] == True]
if not si_rows.empty:
    with st.expander(f"⚠️ {len(si_rows)} OAE(s) SEM INSPEÇÃO REGISTRADA — clique para ver", expanded=False):
        for _, r in si_rows.iterrows():
            st.markdown(
                f'<div class="si-alert">🚨 <b>{r["nome"]}</b> — '
                f'{r.get("tipo","")} | {r.get("cidade","")} | '
                f'RAAE: <b>{r.get("raae","")}</b></div>',
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------------------
# MAPA INTERATIVO
# ---------------------------------------------------------------------------

st.subheader("🗺️ Mapa de Distribuição das OAEs")

col_map, col_info = st.columns([3, 1])

with col_map:
    if df_filtered.dropna(subset=["latitude","longitude"]).empty:
        st.warning("Nenhuma OAE com coordenadas válidas para exibir no mapa.")
    else:
        fmap = build_map(df_filtered, color_mode=color_mode)
        st_folium(fmap, width=None, height=520, returned_objects=[])

with col_info:
    st.markdown("### Distribuição RAAE")
    raae_counts = df_filtered["raae"].value_counts()
    for raae, cnt in raae_counts.items():
        color = RAAE_HEX.get(str(raae).strip(), "#95a5a6")
        pct   = cnt / total * 100 if total else 0
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;margin:6px 0;">'
            f'<div style="width:12px;height:12px;border-radius:50%;background:{color};flex-shrink:0;"></div>'
            f'<span style="flex:1;">{raae}</span>'
            f'<b>{cnt}</b><span style="color:#7f8c8d;font-size:.85rem;"> ({pct:.0f}%)</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("### Distribuição Condição")
    if not df_filtered["insp_geral"].isna().all():
        cond_counts = df_filtered["insp_geral"].astype(str).value_counts().sort_index()
        for cond, cnt in cond_counts.items():
            try:
                c = COND_HEX.get(int(float(cond)), SI_COLOR)
            except (ValueError, TypeError):
                c = SI_COLOR
            pct = cnt / total * 100 if total else 0
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:8px;margin:6px 0;">'
                f'<div style="width:12px;height:12px;border-radius:50%;background:{c};flex-shrink:0;"></div>'
                f'<span style="flex:1;">Nível {cond}</span>'
                f'<b>{cnt}</b><span style="color:#7f8c8d;font-size:.85rem;"> ({pct:.0f}%)</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

st.markdown("---")

# ---------------------------------------------------------------------------
# TABELA DE DADOS CONSOLIDADOS
# ---------------------------------------------------------------------------

st.subheader("📋 Tabela Consolidada de OAEs")

# Reordena: S.I. primeiro se opção marcada
if mostrar_si:
    df_display = pd.concat([
        df_filtered[df_filtered["sem_inspecao"] == True],
        df_filtered[df_filtered["sem_inspecao"] == False],
    ])
else:
    df_display = df_filtered.copy()

DISPLAY_COLS = {
    "nome":          "OAE",
    "tipo":          "Tipo",
    "caracteristica":"Característica",
    "cidade":        "Cidade",
    "raae":          "RAAE",
    "ano":           "Ano",
    "estaticidade":  "Estaticidade",
    "tabuleiro":     "Tabuleiro",
    "insp_ano":      "Ano Insp.",
    "insp_geral":    "Cond. Geral",
    "insp_E":        "E",
    "insp_D":        "D",
    "insp_F":        "F",
    "patologia":     "Manifestação",
    "insp_obs":      "Observação",
}

# Mantém apenas colunas existentes
avail_cols = {k: v for k, v in DISPLAY_COLS.items() if k in df_display.columns}
df_show = df_display[list(avail_cols.keys())].rename(columns=avail_cols)

# Aplica estilos
styled = (
    df_show.style
    .applymap(color_condition, subset=[c for c in ["Cond. Geral","E","D","F"] if c in df_show.columns])
    .applymap(raae_color_row,  subset=["RAAE"] if "RAAE" in df_show.columns else [])
    .set_properties(**{"font-size": "12px"})
)

st.dataframe(styled, use_container_width=True, height=420)

# Botão de exportação
csv_bytes = df_show.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
st.download_button(
    label="⬇️ Exportar tabela para CSV",
    data=csv_bytes,
    file_name="oae_dados_consolidados.csv",
    mime="text/csv",
)

# ---------------------------------------------------------------------------
# RODAPÉ
# ---------------------------------------------------------------------------

st.markdown("---")
st.caption(
    "Dashboard OAE · Engenharia de Manutenção & Confiabilidade Estrutural · "
    "Desenvolvido com Streamlit + Folium · Dados: arquivo Excel interno."
)
