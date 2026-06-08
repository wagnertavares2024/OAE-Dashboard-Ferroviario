"""
map_builder.py
Constrói o mapa Folium com marcadores coloridos e pop-ups para cada OAE.
"""

import folium
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# PALETAS DE CORES
# ---------------------------------------------------------------------------

RAAE_HEX = {
    "Baixo":      "#27ae60",
    "Médio":      "#f39c12",
    "Alto":       "#e67e22",
    "Muito Alto": "#e74c3c",
    "Extremo":    "#8e44ad",
}

COND_HEX = {
    1: "#27ae60",
    2: "#2980b9",
    3: "#f39c12",
    4: "#e67e22",
    5: "#e74c3c",
}

SI_COLOR   = "#7f0000"   # vermelho escuro → Sem Inspeção
SI_ICON    = "exclamation-triangle"
DEF_CENTER = [-19.9, -43.9]   # Minas Gerais / Espírito Santo (região aproximada)


def _marker_color(row: pd.Series, mode: str) -> str:
    """
    Retorna a cor hexadecimal do marcador.
    mode: 'raae' → cor pelo RAAE | 'condition' → cor pela condição geral
    """
    if row.get("sem_inspecao", True) and mode == "condition":
        return SI_COLOR

    if mode == "raae":
        return RAAE_HEX.get(str(row.get("raae", "")).strip(), "#95a5a6")

    # mode == "condition"
    geral = row.get("insp_geral")
    try:
        g = int(float(geral))
        return COND_HEX.get(g, "#95a5a6")
    except (TypeError, ValueError):
        return SI_COLOR


def _folium_color_name(hex_color: str) -> str:
    """
    Folium aceita nomes de cores (não hex) para CircleMarker fill — usamos
    'red', 'orange', etc. Para marcadores de ícone usamos 'white' sempre e
    controlamos pelo css inline no popup.
    """
    mapping = {
        "#27ae60": "green",
        "#2980b9": "blue",
        "#f39c12": "orange",
        "#e67e22": "orange",
        "#e74c3c": "red",
        "#8e44ad": "purple",
        "#7f0000": "darkred",
        "#95a5a6": "gray",
    }
    return mapping.get(hex_color, "gray")


def _build_popup(row: pd.Series) -> folium.Popup:
    """Constrói o HTML do pop-up com informações da OAE."""

    def _fmt(val, suffix=""):
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return "<em>N/D</em>"
        return f"{val}{suffix}"

    def _cond_badge(val):
        if str(val) == "S.I.":
            return '<span style="background:#7f0000;color:#fff;padding:2px 6px;border-radius:4px;font-weight:bold;">S.I.</span>'
        try:
            n = int(float(val))
            colors = {1:"#27ae60",2:"#2980b9",3:"#f39c12",4:"#e67e22",5:"#e74c3c"}
            c = colors.get(n, "#95a5a6")
            return f'<span style="background:{c};color:#fff;padding:2px 6px;border-radius:4px;font-weight:bold;">{n}</span>'
        except (TypeError, ValueError):
            return str(val)

    raae_color = RAAE_HEX.get(str(row.get("raae","")).strip(), "#95a5a6")

    html = f"""
    <div style="font-family:Arial,sans-serif;min-width:280px;max-width:340px;font-size:13px;">
      <h3 style="margin:0 0 8px;color:#2c3e50;border-bottom:2px solid #3498db;padding-bottom:4px;">
        {row.get('nome','—')}
      </h3>

      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Tipo</td>
            <td style="padding:2px 4px;font-weight:500;">{_fmt(row.get('tipo'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Característica</td>
            <td style="padding:2px 4px;">{_fmt(row.get('caracteristica'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Cidade</td>
            <td style="padding:2px 4px;">{_fmt(row.get('cidade'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Ano de Construção</td>
            <td style="padding:2px 4px;">{_fmt(row.get('ano'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">RAAE</td>
            <td style="padding:2px 4px;">
              <span style="background:{raae_color};color:#fff;padding:2px 8px;border-radius:4px;font-weight:bold;">
                {_fmt(row.get('raae'))}
              </span>
            </td></tr>
      </table>

      <h4 style="margin:10px 0 4px;color:#2980b9;">Características Geométricas</h4>
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Qtd. de Vãos</td>
            <td style="padding:2px 4px;">{_fmt(row.get('qtd_vaos'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Maior Vão</td>
            <td style="padding:2px 4px;">{_fmt(row.get('comp_maior_vao'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Alt. Pilar/Encontro</td>
            <td style="padding:2px 4px;">{_fmt(row.get('altura_pilar'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Estaticidade</td>
            <td style="padding:2px 4px;">{_fmt(row.get('estaticidade'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Tabuleiro</td>
            <td style="padding:2px 4px;">{_fmt(row.get('tabuleiro'))}</td></tr>
      </table>

      <h4 style="margin:10px 0 4px;color:#e67e22;">Última Inspeção Rotineira</h4>
    """

    if row.get("sem_inspecao", True):
        html += """
      <div style="background:#ffeaa7;border-left:4px solid #d63031;padding:8px;border-radius:4px;">
        ⚠️ <strong>SEM INSPEÇÃO REGISTRADA (2021–2025)</strong>
      </div>
        """
    else:
        html += f"""
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Ano da Inspeção</td>
            <td style="padding:2px 4px;font-weight:500;">{_fmt(row.get('insp_ano'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Condição Geral</td>
            <td style="padding:2px 4px;">{_cond_badge(row.get('insp_geral'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Estrutural (E)</td>
            <td style="padding:2px 4px;">{_cond_badge(row.get('insp_E'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Durabilidade (D)</td>
            <td style="padding:2px 4px;">{_cond_badge(row.get('insp_D'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Funcional (F)</td>
            <td style="padding:2px 4px;">{_cond_badge(row.get('insp_F'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Observação</td>
            <td style="padding:2px 4px;font-style:italic;">{_fmt(row.get('insp_obs'))}</td></tr>
      </table>
        """

    pat = str(row.get("patologia", "")).strip()
    if pat and pat not in ("", "nan", "None"):
        html += f"""
      <h4 style="margin:10px 0 4px;color:#8e44ad;">Manifestação Patológica</h4>
      <div style="background:#f8f9fa;padding:6px 8px;border-radius:4px;border-left:3px solid #8e44ad;">
        {pat}
      </div>
        """

    html += "</div>"
    return folium.Popup(html, max_width=360)


def build_map(df: pd.DataFrame, color_mode: str = "condition") -> folium.Map:
    """
    Constrói o mapa Folium.

    Parameters
    ----------
    df : DataFrame consolidado (merge fixed + inspection)
    color_mode : 'condition' | 'raae'
    """
    # Centro do mapa: média das coordenadas válidas
    valid_coords = df.dropna(subset=["latitude", "longitude"])
    if valid_coords.empty:
        center = DEF_CENTER
        zoom   = 7
    else:
        center = [valid_coords["latitude"].mean(), valid_coords["longitude"].mean()]
        zoom   = 8

    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles="CartoDB positron",
        control_scale=True,
    )

    # Adiciona camadas de tile alternativas
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)
    folium.TileLayer("CartoDB dark_matter", name="Dark Matter").add_to(m)

    # Grupo para OAEs normais e grupo para S.I.
    group_normal = folium.FeatureGroup(name="OAEs Inspecionadas", show=True)
    group_si     = folium.FeatureGroup(name="OAEs Sem Inspeção ⚠️", show=True)

    for _, row in df.iterrows():
        lat = row.get("latitude")
        lon = row.get("longitude")
        if pd.isna(lat) or pd.isna(lon):
            continue

        hex_color   = _marker_color(row, color_mode)
        folium_color = _folium_color_name(hex_color)
        popup        = _build_popup(row)
        nome         = str(row.get("nome", ""))
        tooltip      = (
            f"<b>{nome}</b><br>"
            f"{row.get('cidade','')}<br>"
            f"RAAE: {row.get('raae','')}"
        )

        is_si = bool(row.get("sem_inspecao", False))

        if is_si:
            # Marcador pulsante via CSS para S.I.
            icon = folium.Icon(color="darkred", icon="exclamation-sign", prefix="glyphicon")
            marker = folium.Marker(
                location=[lat, lon],
                popup=popup,
                tooltip=tooltip,
                icon=icon,
            )
            marker.add_to(group_si)
        else:
            marker = folium.CircleMarker(
                location=[lat, lon],
                radius=9,
                color="#ffffff",
                weight=1.5,
                fill=True,
                fill_color=hex_color,
                fill_opacity=0.85,
                popup=popup,
                tooltip=tooltip,
            )
            marker.add_to(group_normal)

    group_normal.add_to(m)
    group_si.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)

    # Legenda customizada
    legend_html = _build_legend(color_mode)
    m.get_root().html.add_child(folium.Element(legend_html))

    return m


def _build_legend(mode: str) -> str:
    if mode == "raae":
        items = [(c, lbl) for lbl, c in RAAE_HEX.items()]
        title = "RAAE"
    else:
        items = [(COND_HEX[k], f"Condição {k}") for k in sorted(COND_HEX)]
        items.append((SI_COLOR, "Sem Inspeção"))
        title = "Condição Geral"

    rows_html = "".join(
        f'<div style="display:flex;align-items:center;gap:6px;margin:4px 0;">'
        f'<div style="width:14px;height:14px;border-radius:50%;background:{c};flex-shrink:0;"></div>'
        f'<span>{lbl}</span></div>'
        for c, lbl in items
    )

    return f"""
    <div style="
        position:fixed;bottom:40px;right:10px;z-index:1000;
        background:white;padding:12px 16px;border-radius:8px;
        box-shadow:0 2px 8px rgba(0,0,0,.3);font-family:Arial,sans-serif;font-size:12px;
    ">
      <b style="font-size:13px;">{title}</b>
      {rows_html}
    </div>
    """
