"""
app.py  –  Dashboard de Gestão de OAEs (Obras de Arte Especiais)
Ferroviário · Manutenção & Confiabilidade Estrutural
"""

import datetime
import io
import numpy as np
import pandas as pd
import streamlit as st
from pathlib import Path
from streamlit_folium import st_folium

from data_loader      import build_master_df
from map_builder      import build_map, COND_HEX, SI_COLOR, RAAE_HEX, PAT_HEX, pat_hex_color
from report_generator import generate_report, COND_META

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
  /* ── Fundo e cor base do sidebar ──────────────────────────────────────── */
  section[data-testid="stSidebar"] { background:#1a2535; }
  section[data-testid="stSidebar"] * { color:#dce8f5 !important; }

  /* ── Label dos filtros: destaque sutil ───────────────────────────────── */
  section[data-testid="stSidebar"] label[data-testid="stWidgetLabel"] p {
    font-size: 11px !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
    color: #8faecf !important;
    margin-bottom: 2px !important;
  }

  /* ── Caixa de multiselect: fundo diferenciado, borda visível ─────────── */
  section[data-testid="stSidebar"] [data-baseweb="select"] > div:first-child {
    background: #253448 !important;
    border: 1px solid #3a546e !important;
    border-radius: 7px !important;
    min-height: 36px !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
  }
  section[data-testid="stSidebar"] [data-baseweb="select"]:focus-within > div:first-child {
    border-color: #4a90d9 !important;
    box-shadow: 0 0 0 2px rgba(74,144,217,0.18) !important;
  }

  /* ── Placeholder ("vazio = todos") ──────────────────────────────────── */
  section[data-testid="stSidebar"] [data-baseweb="select"] [data-baseweb="placeholder"] {
    color: #5c7a9a !important;
    font-style: italic !important;
    font-size: 12px !important;
  }

  /* ── Chips dos valores selecionados ──────────────────────────────────── */
  section[data-testid="stSidebar"] [data-baseweb="tag"] {
    background: #1e4d7b !important;
    border: 1px solid #2d6aad !important;
    border-radius: 5px !important;
    margin: 2px !important;
    padding: 1px 6px !important;
  }
  section[data-testid="stSidebar"] [data-baseweb="tag"] span {
    color: #c8dff5 !important;
    font-size: 11px !important;
  }
  section[data-testid="stSidebar"] [data-baseweb="tag"] button svg {
    fill: #7aabd4 !important;
  }

  /* ── Dropdown da lista suspensa ──────────────────────────────────────── */
  [data-baseweb="popover"] { background:#1a2535 !important; border:1px solid #3a546e !important; }
  [role="option"]:hover    { background:#253448 !important; }
  [role="option"][aria-selected="true"] { background:#1e4d7b !important; }

  /* ── Expanders do sidebar ────────────────────────────────────────────── */
  section[data-testid="stSidebar"] details {
    background: #1e2d40 !important;
    border: 1px solid #2e4360 !important;
    border-radius: 9px !important;
    margin-bottom: 8px !important;
    padding: 0 2px !important;
  }
  section[data-testid="stSidebar"] details summary {
    font-weight: 700 !important;
    font-size: 13px !important;
    padding: 8px 12px !important;
    border-radius: 9px !important;
  }
  section[data-testid="stSidebar"] details summary:hover {
    background: #253448 !important;
  }

  /* ── Separadores ─────────────────────────────────────────────────────── */
  section[data-testid="stSidebar"] hr {
    border-color: #2e4360 !important;
    margin: 6px 0 !important;
  }

  /* ── Checkboxes ──────────────────────────────────────────────────────── */
  section[data-testid="stSidebar"] [data-testid="stCheckbox"] label {
    font-size: 12px !important;
    font-weight: 500 !important;
  }

  /* ── Cards de KPI ────────────────────────────────────────────────────── */
  .metric-card {
    background:#1e2a38; border-radius:10px; padding:8px 12px;
    color:#ecf0f1; text-align:center;
  }
  .metric-card .value { font-size:1.5rem; font-weight:700; }
  .metric-card .label { font-size:.75rem; opacity:.8; margin-top:2px; }

  /* ── Alerta S.I. ─────────────────────────────────────────────────────── */
  .si-alert {
    background:#ffeaa7; border-left:5px solid #d63031;
    padding:10px 14px; border-radius:6px; margin-bottom:8px;
  }

  div[data-testid="stDataFrame"] { border-radius:8px; overflow:hidden; }
  div.block-container { padding-top:0.5rem !important; padding-bottom:0.5rem !important; }
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
    """Estilo de célula — paleta 0-5 fiel ao padrão de referência."""
    try:
        n = int(float(val))
        # Cores sólidas da paleta com texto contrastante
        styles = {
            0: ("background-color:#8E44AD;color:#fff;",),   # Emergencial → roxo
            1: ("background-color:#C0392B;color:#fff;",),   # Crítico     → vermelho
            2: ("background-color:#E67E22;color:#fff;",),   # Ruim        → laranja
            3: ("background-color:#F4D03F;color:#1a1a1a;",),# Regular     → amarelo
            4: ("background-color:#58D68D;color:#1a1a1a;",),# Bom         → verde claro
            5: ("background-color:#1E8449;color:#fff;",),   # Excelente   → verde escuro
        }
        base = styles.get(n, ("",))[0]
        return base + "font-weight:bold;text-align:center;"
    except (TypeError, ValueError):
        if str(val) == "S.I.":
            return "background-color:#7f0000;color:#fff;font-weight:bold;text-align:center;"
        return ""


def raae_color_row(val):
    colors = {"Baixo":"#d5f5e3","Médio":"#fef9e7","Alto":"#fdebd0",
              "Muito Alto":"#fadbd8","Extremo":"#e8daef"}
    return f"background-color:{colors.get(str(val).strip(),'')};"


def _render_pat_raae_chart(df: pd.DataFrame, pat_list: list) -> None:
    """
    Mini gráfico de barras horizontais empilhadas — frequência de cada
    patologia distribuída por zona RAAE. Renderizado na sidebar.
    """
    if not pat_list:
        return

    RAAE_ORDER = ["Extremo", "Muito Alto", "Alto", "Médio", "Baixo"]

    # Computa frequência patologia × RAAE
    rows = []
    for pat in pat_list:
        subset = df[df["patologia"].astype(str).str.strip() == pat]
        total  = len(subset)
        if total == 0:
            continue
        counts = {
            r: int((subset["raae"].astype(str).str.strip() == r).sum())
            for r in RAAE_ORDER
        }
        rows.append((pat, counts, total))

    if not rows:
        return

    rows.sort(key=lambda x: x[2], reverse=True)
    max_total = max(r[2] for r in rows)

    html_rows = ""
    for pat, counts, total in rows:
        pat_color  = pat_hex_color(pat)
        short_name = (pat[:17] + "…") if len(pat) > 17 else pat

        # Segmentos da barra proporcional ao total geral
        bar_width_pct = total / max_total * 100
        segments = "".join(
            f'<div style="width:{counts[r]/total*100:.1f}%;background:{RAAE_HEX[r]};"'
            f' title="{r}: {counts[r]}"></div>'
            for r in RAAE_ORDER if counts.get(r, 0) > 0
        )

        html_rows += f"""
        <div style="display:flex;align-items:center;gap:5px;margin:3px 0;">
          <div style="width:10px;height:10px;border-radius:50%;background:{pat_color};
                      flex-shrink:0;"></div>
          <div style="width:82px;font-size:9.5px;color:#bdc3c7;overflow:hidden;
                      white-space:nowrap;text-overflow:ellipsis;flex-shrink:0;"
               title="{pat}">{short_name}</div>
          <div style="flex:1;background:#1a2535;border-radius:3px;
                      height:11px;overflow:hidden;">
            <div style="display:flex;height:100%;width:{bar_width_pct:.1f}%;">
              {segments}
            </div>
          </div>
          <div style="width:22px;font-size:9.5px;color:#ecf0f1;
                      text-align:right;font-weight:700;flex-shrink:0;">{total}</div>
        </div>"""

    legend_dots = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:3px;margin:0 3px;">'
        f'<span style="width:8px;height:8px;border-radius:50%;background:{RAAE_HEX[r]};">'
        f'</span><span style="font-size:8.5px;color:#7f8c8d;">{r}</span></span>'
        for r in RAAE_ORDER
    )

    st.markdown(
        f'<div style="margin-top:10px;padding:8px 10px;background:#1a2535;'
        f'border-radius:7px;border-left:3px solid #4a6fa5;">'
        f'<div style="font-size:9.5px;font-weight:700;color:#7f8c8d;'
        f'text-transform:uppercase;letter-spacing:.5px;margin-bottom:7px;">'
        f'Frequência por Zona RAAE</div>'
        f'{html_rows}'
        f'<div style="margin-top:7px;display:flex;flex-wrap:wrap;gap:1px 2px;">'
        f'{legend_dots}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# CARREGAMENTO E CACHE DOS DADOS
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Carregando dados do Excel...")
def load_data(path: str) -> tuple:
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
    st.markdown("## 🏗️ Gestão à Vista de Pontes, Viadutos e Tuneis Ferroviários")
    st.info("👈 Faça o upload do arquivo Excel na barra lateral para iniciar.")
    st.stop()

try:
    df, qtd_rotineira_total, qtd_especial_total = load_data(excel_path)
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
    # ── Grupo 1: Estrutura & Geometria ────────────────────────────────────────
    with st.expander("🏗️ Estrutura & Geometria", expanded=True):
        _tip = "Vazio = exibe todos"

        tipos = sorted(df["tipo"].dropna().unique().tolist())
        sel_tipo = st.multiselect(
            f"Tipo de OAE  ({len(tipos)})", tipos,
            placeholder="Todos os tipos...", help=_tip,
        )

        caracteristicas = sorted(df["caracteristica"].dropna().unique().tolist())
        sel_caracteristica = st.multiselect(
            f"Característica  ({len(caracteristicas)})", caracteristicas,
            placeholder="Todas...", help=_tip,
        )

        estat_vals = sorted(df["estaticidade"].dropna().unique().tolist())
        sel_estat = st.multiselect(
            f"Estaticidade  ({len(estat_vals)})", estat_vals,
            placeholder="Todas...", help=_tip,
        )

        tab_vals = sorted(df["tabuleiro"].dropna().unique().tolist())
        sel_tab = st.multiselect(
            f"Tabuleiro  ({len(tab_vals)})", tab_vals,
            placeholder="Todos...", help=_tip,
        )

        _anos_validos = sorted(
            pd.to_numeric(df["ano"], errors="coerce").dropna().astype(int).unique().tolist()
        )
        sel_anos = st.multiselect(
            f"Ano de Construção  ({len(_anos_validos)})", _anos_validos,
            placeholder="Todos os anos...", help=_tip,
        )

    # ── Grupo 2: Condição & Ambiente ──────────────────────────────────────────
    with st.expander("⚠️ Condição & Ambiente", expanded=True):
        raae_vals = sorted(df["raae"].dropna().unique().tolist())
        sel_raae = st.multiselect(
            f"RAAE  ({len(raae_vals)})", raae_vals,
            placeholder="Todos os níveis...", help="Vazio = exibe todos",
        )

        show_raae = st.checkbox(
            "🟢 Exibir Zonas de Influência RAAE no Mapa",
            value=False,
            help="Ativa os círculos de influência RAAE e o painel resumo no mapa.",
        )

        todas_pat = sorted(set(
            p.strip()
            for p in df["patologia"].dropna().astype(str)
            if p.strip() and p.strip().lower() not in ("nan", "none", "")
        ))
        sel_pat = st.multiselect(
            f"Manifestação Patológica  ({len(todas_pat)})",
            todas_pat,
            placeholder="Todas as patologias...",
            help="Filtra quais tipos de patologia são exibidos nas zonas do mapa. Vazio = exibe todas.",
        )

        show_pat_zones = st.checkbox(
            "🔬 Exibir Zonas de Manifestação Patológica no Mapa",
            value=False,
            help=(
                "Ativa os círculos de área de patologia no mapa e exibe o painel "
                "resumo acima do painel RAAE. Se nenhuma patologia estiver "
                "selecionada, exibe todas."
            ),
        )

        # Gráfico de frequência patologia × RAAE (todas as patologias do filtro atual)
        _render_pat_raae_chart(df, todas_pat)

    with st.expander("🎨 Visualização", expanded=False):
        color_mode = st.radio(
            "Critério de cor dos marcadores",
            options=["condition", "raae"],
            format_func=lambda x: "Condição Geral (ABNT 9452)" if x == "condition" else "RAAE",
            index=0,
        )
        mostrar_si = st.checkbox("Destacar S.I. no topo da tabela", value=True)

# ---------------------------------------------------------------------------
# APLICAÇÃO DOS FILTROS
# ---------------------------------------------------------------------------

mask = pd.Series([True] * len(df), index=df.index)

if sel_tipo:
    mask &= df["tipo"].isin(sel_tipo)
if sel_caracteristica:
    mask &= df["caracteristica"].isin(sel_caracteristica)
if sel_raae:
    mask &= df["raae"].isin(sel_raae)
if sel_estat:
    mask &= df["estaticidade"].isin(sel_estat)
if sel_tab:
    mask &= df["tabuleiro"].isin(sel_tab)

if sel_anos:
    ano_col = pd.to_numeric(df["ano"], errors="coerce").astype("Int64")
    mask &= ano_col.isin(sel_anos)


# Patologia NÃO filtra df_filtered — controla apenas quais camadas de área
# são renderizadas no mapa via LayerControl (sel_pat → _add_pathology_area_layers).

df_filtered = df[mask].copy()

# ── Badge de status dos filtros no sidebar ────────────────────────────────────
_filtros_ativos = sum([
    bool(sel_tipo), bool(sel_caracteristica), bool(sel_raae),
    bool(sel_estat), bool(sel_tab), bool(sel_anos),
])
with st.sidebar:
    n_total    = len(df)
    n_filtrado = len(df_filtered)
    _pct = int(100 * n_filtrado / n_total) if n_total else 0
    if _filtros_ativos:
        _badge_bg  = "#1e4d7b"
        _badge_brd = "#2d6aad"
        _badge_msg = f"{_filtros_ativos} filtro(s) ativo(s)"
    else:
        _badge_bg  = "#1a3a1a"
        _badge_brd = "#2d7a2d"
        _badge_msg = "Sem filtros"
    st.markdown(
        f'<div style="background:{_badge_bg};border:1px solid {_badge_brd};'
        f'border-radius:8px;padding:7px 12px;margin:4px 0 8px;'
        f'font-family:Arial,sans-serif;">'
        f'<div style="font-size:10px;color:#8faecf;text-transform:uppercase;'
        f'letter-spacing:0.05em;margin-bottom:2px;">{_badge_msg}</div>'
        f'<div style="font-size:14px;font-weight:700;color:#dce8f5;">'
        f'{n_filtrado} <span style="font-weight:400;font-size:11px;color:#8faecf;">'
        f'de {n_total} OAEs  ({_pct}%)</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# CABEÇALHO E KPIs
# ---------------------------------------------------------------------------

SVG_BRIDGE = """
<svg width="75" height="48" viewBox="0 0 110 70" xmlns="http://www.w3.org/2000/svg">
  <!-- Rio -->
  <rect x="0" y="58" width="110" height="12" fill="#2980b9" rx="2" opacity="0.4"/>
  <!-- Arco principal -->
  <path d="M8,58 Q55,6 102,58" stroke="#2c3e50" stroke-width="4" fill="none" stroke-linecap="round"/>
  <!-- Tabuleiro -->
  <rect x="0" y="40" width="110" height="5" fill="#7f8c8d" rx="2"/>
  <!-- Tirantes verticais -->
  <line x1="28" y1="40" x2="24" y2="57" stroke="#95a5a6" stroke-width="2"/>
  <line x1="42" y1="40" x2="40" y2="52" stroke="#95a5a6" stroke-width="2"/>
  <line x1="55" y1="40" x2="55" y2="47" stroke="#95a5a6" stroke-width="2"/>
  <line x1="68" y1="40" x2="70" y2="52" stroke="#95a5a6" stroke-width="2"/>
  <line x1="82" y1="40" x2="86" y2="57" stroke="#95a5a6" stroke-width="2"/>
  <!-- Pilares -->
  <rect x="3"  y="40" width="7" height="20" fill="#2c3e50" rx="1"/>
  <rect x="100" y="40" width="7" height="20" fill="#2c3e50" rx="1"/>
  <!-- Trilhos -->
  <line x1="0" y1="39" x2="110" y2="39" stroke="#e74c3c" stroke-width="1.5" stroke-dasharray="6,4"/>
</svg>
"""

SVG_TUNNEL = """
<svg width="61" height="48" viewBox="0 0 90 70" xmlns="http://www.w3.org/2000/svg">
  <!-- Montanha -->
  <path d="M0,70 L0,28 Q45,2 90,28 L90,70 Z" fill="#7f8c8d"/>
  <!-- Sombra topo montanha -->
  <path d="M0,28 Q45,2 90,28 Q60,18 45,16 Q30,18 0,28 Z" fill="#636e72" opacity="0.4"/>
  <!-- Vegetação -->
  <ellipse cx="18" cy="24" rx="8" ry="6" fill="#27ae60"/>
  <ellipse cx="72" cy="24" rx="8" ry="6" fill="#27ae60"/>
  <ellipse cx="45" cy="13" rx="9" ry="7" fill="#2ecc71"/>
  <!-- Portal do túnel (abertura) -->
  <path d="M20,70 L20,40 Q45,20 70,40 L70,70 Z" fill="#1a1a2e"/>
  <!-- Borda do portal -->
  <path d="M20,40 Q45,20 70,40" stroke="#bdc3c7" stroke-width="3" fill="none"/>
  <rect x="20" y="40" width="2" height="30" fill="#bdc3c7"/>
  <rect x="68" y="40" width="2" height="30" fill="#bdc3c7"/>
  <!-- Via dentro do túnel -->
  <rect x="20" y="62" width="50" height="8" fill="#2d3436"/>
  <line x1="43" y1="63" x2="43" y2="70" stroke="#f1c40f" stroke-width="2" stroke-dasharray="3,3"/>
  <line x1="47" y1="63" x2="47" y2="70" stroke="#f1c40f" stroke-width="2" stroke-dasharray="3,3"/>
  <!-- Luz no fundo -->
  <ellipse cx="45" cy="45" rx="6" ry="4" fill="#f39c12" opacity="0.35"/>
  <ellipse cx="45" cy="45" rx="3" ry="2" fill="#fdcb6e" opacity="0.5"/>
</svg>
"""

st.markdown(f"""
<div style="
    display:flex; align-items:center; gap:14px;
    background:linear-gradient(135deg,#1e2a38 0%,#2c3e50 100%);
    border-radius:10px; padding:10px 18px; margin-bottom:4px;
    box-shadow:0 4px 16px rgba(0,0,0,.25);
">
  <!-- Ícone Ponte -->
  <div style="flex-shrink:0; opacity:.92;">{SVG_BRIDGE}</div>

  <!-- Texto central -->
  <div style="flex:1; text-align:center;">
    <div style="color:#ecf0f1; font-size:1.2rem; font-weight:700; line-height:1.2;
                font-family:'Segoe UI',Arial,sans-serif; letter-spacing:.3px;">
      Gestão à Vista de Pontes,<br>Viadutos e Tuneis Ferroviários
    </div>
    <div style="color:#95a5a6; font-size:.75rem; margin-top:2px; letter-spacing:.5px;">
      Inspeções em OAEs Ferroviárias
    </div>
  </div>

  <!-- Ícone Túnel -->
  <div style="flex-shrink:0; opacity:.92;">{SVG_TUNNEL}</div>
</div>
""", unsafe_allow_html=True)
st.markdown("<div style='margin:2px 0 4px;border-top:1px solid #2d3d4f;'></div>", unsafe_allow_html=True)

total      = len(df_filtered)
# Rotineira: OAEs com sem_inspecao == False
insp_rot_count = int((df_filtered["sem_inspecao"] == False).sum())
# Especial: OAEs com sem_especial == False (coluna vinda da aba Inspeção Especial)
insp_esp_count = int((df_filtered.get("sem_especial", pd.Series(True, index=df_filtered.index)) == False).sum())

# ── Linha 1: totalizadores ──────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(metric_card("Total de OAEs", total, "#3498db"), unsafe_allow_html=True)
with c2:
    st.markdown(metric_card("Total Inspecionadas", max(insp_rot_count, insp_esp_count), "#27ae60"), unsafe_allow_html=True)
with c3:
    st.markdown(metric_card("Inspeção Rotineira", insp_rot_count, "#8e44ad"), unsafe_allow_html=True)
with c4:
    color_esp = "#e67e22" if insp_esp_count > 0 else "#7f8c8d"
    color_esp = "#e67e22" if insp_esp_count > 0 else "#7f8c8d"
    st.markdown(metric_card("Inspeção Especial", insp_esp_count, color_esp), unsafe_allow_html=True)

st.markdown("<div style='margin:4px 0 2px;'><b style='color:#ecf0f1;font-size:.8rem;'>PARÂMETRO DE CONDIÇÃO GERAL DA OAE</b></div>", unsafe_allow_html=True)

# ── Linha 2: paleta de condição 0-5 ──────────────────────────────────────
# Cores fiéis à tabela de referência enviada pelo usuário
# (nivel, label, bg, txt)
CONDICOES = [
    (0, "Emergencial", "#8E44AD", "#ffffff"),  # roxo
    (1, "Crítico",     "#C0392B", "#ffffff"),  # vermelho puro
    (2, "Ruim",        "#E67E22", "#ffffff"),  # laranja
    (3, "Regular",     "#F4D03F", "#1a1a1a"),  # amarelo  → texto escuro
    (4, "Bom",         "#58D68D", "#1a1a1a"),  # verde claro → texto escuro
    (5, "Excelente",   "#1E8449", "#ffffff"),  # verde escuro
]

geral_numeric = pd.to_numeric(df_filtered["insp_geral"], errors="coerce")
cols_cond = st.columns(6)
for col, (nivel, label, bg, txt) in zip(cols_cond, CONDICOES):
    cnt = int((geral_numeric == nivel).sum())
    with col:
        st.markdown(f"""
        <div style="
            background:{bg}; border-radius:12px;
            padding:10px 6px 10px; text-align:center;
            box-shadow:0 4px 12px rgba(0,0,0,.28);
        ">
          <!-- Classificação com destaque -->
          <div style="font-size:.85rem; font-weight:900; color:{txt};
                      letter-spacing:.5px; text-transform:uppercase;
                      line-height:1.2;">{label}</div>
          <!-- Divisor -->
          <div style="border-top:1px solid {txt}; opacity:.35;
                      margin:5px auto; width:55%;"></div>
          <!-- Quantidade -->
          <div style="font-size:1.7rem; font-weight:900; color:{txt};
                      line-height:1;">{cnt}</div>
          <div style="font-size:.65rem; color:{txt}; opacity:.75;
                      margin-top:3px; letter-spacing:.4px;">OAEs</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<div style='margin:2px 0 4px;border-top:1px solid #2d3d4f;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# CARDS COMPACTOS: RAAE + CONDIÇÃO (substituem a coluna lateral)
# ---------------------------------------------------------------------------

RAAE_ORDER  = ["Extremo", "Muito Alto", "Alto", "Médio", "Baixo"]
raae_counts = df_filtered["raae"].value_counts()
geral_num   = pd.to_numeric(df_filtered["insp_geral"], errors="coerce")
COND_LABEL_MAP = {0:"Emergencial",1:"Crítico",2:"Ruim",3:"Regular",4:"Bom",5:"Excelente"}

st.markdown(
    '<div style="font-size:.8rem;font-weight:700;color:#95a5a6;letter-spacing:.8px;'
    'margin-bottom:4px;">PARÂMETRO DE RAAE</div>',
    unsafe_allow_html=True,
)
raae_cols = st.columns(5)
for col, raae_lbl in zip(raae_cols, RAAE_ORDER):
    cnt   = int(raae_counts.get(raae_lbl, 0))
    color = RAAE_HEX.get(raae_lbl, "#95a5a6")
    pct   = cnt / total * 100 if total else 0
    with col:
        st.markdown(f"""
        <div style="background:{color};border-radius:10px;padding:10px 8px;
                    text-align:center;box-shadow:0 3px 8px rgba(0,0,0,.22);">
          <div style="font-size:.72rem;font-weight:800;color:#fff;
                      text-transform:uppercase;letter-spacing:.4px;">{raae_lbl}</div>
          <div style="font-size:1.4rem;font-weight:900;color:#fff;line-height:1.1;
                      margin:3px 0;">{cnt}</div>
          <div style="font-size:.65rem;color:rgba(255,255,255,.75);">{pct:.0f}%</div>
        </div>""", unsafe_allow_html=True)

st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)

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
# INSIGHT CARDS (contexto do filtro atual — acima do mapa)
# ---------------------------------------------------------------------------

geral_num_filt = pd.to_numeric(df_filtered["insp_geral"], errors="coerce")
_critico_count = int(((geral_num_filt == 0) | (geral_num_filt == 1)).sum())
_ruim_count    = int((geral_num_filt == 2).sum())
_si_count      = int((df_filtered["sem_inspecao"] == True).sum())
_raae_alto     = int(df_filtered["raae"].isin(["Extremo", "Muito Alto"]).sum())

# Patologia mais frequente no filtro atual
_pat_counts = (
    df_filtered["patologia"]
    .dropna()
    .astype(str)
    .str.strip()
    .replace({"nan": None, "None": None, "": None})
    .dropna()
    .value_counts()
)
_top_pat = _pat_counts.index[0] if not _pat_counts.empty else "—"
_top_pat_cnt = int(_pat_counts.iloc[0]) if not _pat_counts.empty else 0

_ic1, _ic2, _ic3, _ic4 = st.columns(4)
_insights = [
    (_ic1, "⚡ Crítico / Emergencial",   _critico_count, "#C0392B"),
    (_ic2, "🟠 Ruim (Cond. 2)",          _ruim_count,    "#E67E22"),
    (_ic3, "🔴 RAAE Extremo/Muito Alto", _raae_alto,     "#8e44ad"),
    (_ic4, f"🔬 {_top_pat[:22]}",         _top_pat_cnt,   "#2980b9"),
]
for col, lbl, val, cor in _insights:
    with col:
        st.markdown(f"""
        <div style="background:#1e2a38;border-left:4px solid {cor};
                    border-radius:8px;padding:10px 14px;margin-bottom:4px;">
          <div style="font-size:.72rem;color:#95a5a6;font-weight:600;
                      text-transform:uppercase;letter-spacing:.5px;">{lbl}</div>
          <div style="font-size:1.9rem;font-weight:900;color:{cor};
                      line-height:1.1;">{val}</div>
          <div style="font-size:.65rem;color:#7f8c8d;">OAEs no filtro atual</div>
        </div>""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# MAPA INTERATIVO — tela cheia, LayerControl no canto superior direito
# ---------------------------------------------------------------------------

st.subheader("🗺️ Mapa de Distribuição das OAEs")

if df_filtered.dropna(subset=["latitude","longitude"]).empty:
    st.warning("Nenhuma OAE com coordenadas válidas para exibir no mapa.")
else:
    fmap = build_map(
        df_filtered,
        color_mode=color_mode,
        selected_pathologies=sel_pat if sel_pat else None,
        show_raae=show_raae,
        show_pat_zones=show_pat_zones,
    )
    st_folium(fmap, width=None, height=620, returned_objects=[])

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

df_display = df_display.copy()

# Corrige coluna Ano: converte timestamp/float para inteiro legível
df_display["ano"] = pd.to_numeric(df_display["ano"], errors="coerce")
df_display["ano"] = df_display["ano"].apply(
    lambda x: int(x) if pd.notna(x) and 1800 < x < 2100 else ""
)

def _fmt_cond(x):
    """Formata condição como inteiro ou mantém 'S.I.'."""
    s = str(x)
    if s in ("S.I.", "", "nan", "None"):
        return "S.I."
    try:
        return int(float(x))
    except (ValueError, TypeError):
        return s

# Formata condições e anos como inteiro
for col in ["insp_geral","insp_E","insp_D","insp_F","esp_geral","esp_E","esp_D","esp_F"]:
    if col in df_display.columns:
        df_display[col] = df_display[col].apply(_fmt_cond)

# Esp. Ano: garante formato "aaaa" sem decimais
if "esp_ano" in df_display.columns:
    df_display["esp_ano"] = pd.to_numeric(df_display["esp_ano"], errors="coerce").apply(
        lambda x: int(x) if pd.notna(x) and 1800 < x < 2100 else ("S.I." if pd.isna(x) else x)
    )

DISPLAY_COLS = {
    "nome":           "OAE",
    "tipo":           "Tipo",
    "caracteristica": "Característica",
    "estaticidade":   "Estaticidade",
    "ano":            "Ano Construção",
    "raae":           "RAAE",
    # Inspeção Rotineira
    "insp_ano":       "Rot. Ano",
    "insp_geral":     "Rot. Geral",
    "insp_E":         "Rot. E",
    "insp_D":         "Rot. D",
    "insp_F":         "Rot. F",
    "patologia":      "Rot. Manifestação Patológica",
    # Inspeção Especial
    "esp_ano":        "Esp. Ano",
    "esp_geral":      "Esp. Geral",
    "esp_E":          "Esp. E",
    "esp_D":          "Esp. D",
    "esp_F":          "Esp. F",
}

# Mantém apenas colunas existentes
avail_cols = {k: v for k, v in DISPLAY_COLS.items() if k in df_display.columns}
df_show = df_display[list(avail_cols.keys())].rename(columns=avail_cols)

# Estilo: cor de fundo nas condições de ambas inspeções + RAAE
rot_cond_cols = [c for c in ["Rot. Geral","Rot. E","Rot. D","Rot. F"] if c in df_show.columns]
esp_cond_cols = [c for c in ["Esp. Geral","Esp. E","Esp. D","Esp. F"] if c in df_show.columns]
cond_cols = rot_cond_cols + esp_cond_cols
styled = (
    df_show.style
    .map(color_condition, subset=cond_cols)
    .map(raae_color_row,  subset=["RAAE"] if "RAAE" in df_show.columns else [])
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
# RELATÓRIO TÉCNICO DE OBRAS
# ---------------------------------------------------------------------------

st.markdown("---")
st.subheader("📄 Relatório Técnico de Obras de Adequação")

with st.expander("🔧 Configurar e Gerar Relatório", expanded=False):

    st.markdown(
        "Selecione os **parâmetros de condição** que deseja tratar na obra. "
        "O relatório incluirá todas as OAEs do filtro atual que se enquadrem nos níveis escolhidos.",
        unsafe_allow_html=False,
    )

    # ── Seleção visual dos níveis de condição ─────────────────────────────────
    _cond_options = {
        0: ("0 – Emergencial", "#8E44AD"),
        1: ("1 – Crítico",     "#C0392B"),
        2: ("2 – Ruim",        "#E67E22"),
        3: ("3 – Regular",     "#F4D03F"),
        4: ("4 – Bom",         "#58D68D"),
        5: ("5 – Excelente",   "#1E8449"),
    }

    # Mostra badges coloridos dos níveis disponíveis nos dados filtrados
    _geral_filtrado = pd.to_numeric(df_filtered["insp_geral"], errors="coerce")
    _niveis_disponiveis = sorted(_geral_filtrado.dropna().astype(int).unique().tolist())

    badges_html = ""
    for n, (lbl, cor) in _cond_options.items():
        cnt_n = int((_geral_filtrado == n).sum())
        opacity = "1" if n in _niveis_disponiveis else "0.35"
        badges_html += (
            f'<span style="display:inline-flex;align-items:center;gap:5px;'
            f'background:{cor}22;border:2px solid {cor};border-radius:6px;'
            f'padding:4px 12px;margin:3px;opacity:{opacity};">'
            f'<b style="color:{cor};">{lbl}</b>'
            f'<span style="background:{cor};color:#fff;border-radius:3px;'
            f'padding:1px 6px;font-size:11px;font-weight:700;">{cnt_n}</span>'
            f'</span>'
        )
    st.markdown(
        f'<div style="margin:8px 0 14px;">{badges_html}</div>',
        unsafe_allow_html=True,
    )

    # ── Multiselect dos níveis ────────────────────────────────────────────────
    _cond_labels = [f"{n} – {COND_META[n]['label']}" for n in range(6)]
    _default_sel = [_cond_labels[n] for n in _niveis_disponiveis if n <= 2]  # 0,1,2 como padrão

    _sel_labels = st.multiselect(
        "Parâmetros de condição a incluir no relatório:",
        options=_cond_labels,
        default=_default_sel,
        help="Selecione um ou mais níveis de condição. Os dados seguem o filtro ativo no dashboard.",
    )
    _sel_levels = [int(lbl.split(" –")[0]) for lbl in _sel_labels]

    # ── Pré-visualização de quantas OAEs serão incluídas ─────────────────────
    if _sel_levels:
        _mask_rep = _geral_filtrado.isin(_sel_levels)
        _n_rep    = int(_mask_rep.sum())
        if _n_rep:
            st.info(
                f"✅ O relatório incluirá **{_n_rep} OAE(s)** — "
                f"ordenadas por prioridade (Condição × RAAE).",
                icon=None,
            )
        else:
            st.warning("Nenhuma OAE encontrada para os níveis selecionados no filtro atual.")

        col_gen, col_dl = st.columns([1, 2])

        with col_gen:
            if st.button("📋 Gerar Relatório", use_container_width=True, type="primary"):
                with st.spinner("Gerando relatório..."):
                    _report_bytes = generate_report(df_filtered, _sel_levels)
                st.session_state["_report_bytes"] = _report_bytes
                st.success("Relatório gerado com sucesso!")

        with col_dl:
            if "_report_bytes" in st.session_state:
                _fname = (
                    f"relatorio_oae_cond{'_'.join(str(l) for l in sorted(_sel_levels))}"
                    f"_{datetime.date.today().strftime('%Y%m%d')}.html"
                )
                st.download_button(
                    label="⬇️ Baixar Relatório HTML  (abrir no navegador → Ctrl+P → Salvar PDF)",
                    data=st.session_state["_report_bytes"],
                    file_name=_fname,
                    mime="text/html",
                    use_container_width=True,
                )
    else:
        st.info("Selecione pelo menos um parâmetro de condição para gerar o relatório.")

# ---------------------------------------------------------------------------
# RODAPÉ
# ---------------------------------------------------------------------------

st.markdown("---")
st.caption(
    "Dashboard OAE · Engenharia de Manutenção & Confiabilidade Estrutural · "
    "Desenvolvido com Streamlit + Folium · Dados: arquivo Excel interno."
)
