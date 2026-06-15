"""
map_builder.py
Constrói o mapa Folium com marcadores coloridos e pop-ups para cada OAE.
"""

import heapq
import folium
import numpy as np
import pandas as pd
from geopy.distance import geodesic


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

# Paleta 0-5 idêntica à tabela de referência enviada pelo usuário
COND_HEX = {
    0: "#8E44AD",   # Emergencial  → roxo
    1: "#C0392B",   # Crítico      → vermelho
    2: "#E67E22",   # Ruim         → laranja
    3: "#F4D03F",   # Regular      → amarelo
    4: "#58D68D",   # Bom          → verde claro
    5: "#1E8449",   # Excelente    → verde escuro
}

COND_LABEL = {
    0: "Emergencial",
    1: "Crítico",
    2: "Ruim",
    3: "Regular",
    4: "Bom",
    5: "Excelente",
}

SI_COLOR   = "#7f0000"
DEF_CENTER = [-19.9, -43.9]

# Legenda para a camada de círculos RAAE
RAAE_HEAT_LEGEND = [
    ("#27ae60", "Baixo"),
    ("#f39c12", "Médio"),
    ("#e67e22", "Alto"),
    ("#e74c3c", "Muito Alto"),
    ("#8e44ad", "Extremo"),
]

# Paleta oficial de cores hexadecimais por tipo de manifestação patológica
# keyword_lower → cor hex
PAT_HEX: dict = {
    # Corrosão / oxidação / ferrugem → família vermelha
    "corros":     "#e74c3c",
    "oxidac":     "#c0392b",
    "ferrug":     "#c0392b",
    # Fissuras / trincas / rachaduras → laranja escuro
    "fissur":     "#e67e22",
    "trinca":     "#d35400",
    "rachad":     "#d35400",
    # Infiltração / umidade → azul
    "infiltr":    "#2980b9",
    "umidad":     "#3498db",
    # Recalque / deformação / deslocamento → roxo
    "recalqu":    "#7d3c98",
    "recalc":     "#7d3c98",
    "deform":     "#9b59b6",
    "deslocam":   "#9b59b6",
    # Vegetação → verde
    "vegetac":    "#27ae60",
    "vegeta":     "#27ae60",
    # Eflorescência → verde-azulado
    "eflorescen": "#1abc9c",
    "eflorescên": "#1abc9c",
    # Segregação / desagregação → cinza
    "segregac":   "#7f8c8d",
    "desagreg":   "#7f8c8d",
    # Armadura exposta / colapso → vermelho escuro / chumbo
    "armadura":   "#7f0000",
    "colapso":    "#2c3e50",
    # Guarda corpo / junta → âmbar
    "guarda":     "#f39c12",
    "junta":      "#e67e22",
    # Drenagem → teal
    "drena":      "#16a085",
}
_PAT_HEX_DEFAULT = "#95a5a6"


def pat_hex_color(pat_name: str) -> str:
    """Retorna a cor hexadecimal oficial para uma patologia pelo nome completo."""
    pat_lower = pat_name.lower()
    for keyword, color in PAT_HEX.items():
        if keyword in pat_lower:
            return color
    return _PAT_HEX_DEFAULT


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
        "#8E44AD": "purple",   # Emergencial
        "#C0392B": "red",      # Crítico
        "#E67E22": "orange",   # Ruim
        "#F4D03F": "orange",   # Regular (folium não tem amarelo, usa laranja)
        "#58D68D": "green",    # Bom
        "#1E8449": "darkgreen",# Excelente
        "#7f0000": "darkred",  # S.I.
        "#95a5a6": "gray",
        "#27ae60": "green",
        "#f39c12": "orange",
        "#8e44ad": "purple",
    }
    return mapping.get(hex_color, "gray")


def _build_popup(row: pd.Series) -> folium.Popup:
    """Constrói o HTML do pop-up com informações da OAE."""

    def _fmt(val, suffix=""):
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return "<em>N/D</em>"
        return f"{val}{suffix}"

    def _cond_badge(val):
        if str(val) in ("S.I.", "nan", "None", ""):
            return '<span style="background:#7f0000;color:#fff;padding:2px 8px;border-radius:4px;font-weight:bold;">S.I.</span>'
        try:
            n   = int(float(val))
            c   = COND_HEX.get(n, "#95a5a6")
            lbl = COND_LABEL.get(n, str(n))
            txt = "#1a1a1a" if n in (3, 4) else "#ffffff"
            return (f'<span style="background:{c};color:{txt};padding:2px 10px;'
                    f'border-radius:4px;font-weight:bold;">{n} – {lbl}</span>')
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

      <h4 style="margin:10px 0 4px;color:#e67e22;">Inspeção Rotineira</h4>
    """

    if row.get("sem_inspecao", True):
        html += """
      <div style="background:#ffeaa7;border-left:4px solid #d63031;padding:8px;border-radius:4px;">
        ⚠️ <strong>SEM INSPEÇÃO ROTINEIRA (2021–2025)</strong>
      </div>
        """
    else:
        html += f"""
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Ano</td>
            <td style="padding:2px 4px;font-weight:500;">{_fmt(row.get('insp_ano'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Geral</td>
            <td style="padding:2px 4px;">{_cond_badge(row.get('insp_geral'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Estrutural (E)</td>
            <td style="padding:2px 4px;">{_cond_badge(row.get('insp_E'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Durabilidade (D)</td>
            <td style="padding:2px 4px;">{_cond_badge(row.get('insp_D'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Funcional (F)</td>
            <td style="padding:2px 4px;">{_cond_badge(row.get('insp_F'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Obs.</td>
            <td style="padding:2px 4px;font-style:italic;">{_fmt(row.get('insp_obs'))}</td></tr>
      </table>
        """

    # ── Inspeção Especial ──────────────────────────────────────────────
    html += '<h4 style="margin:10px 0 4px;color:#8e44ad;">Inspeção Especial</h4>'
    if row.get("sem_especial", True):
        html += """
      <div style="background:#f0e6f6;border-left:4px solid #8e44ad;padding:8px;border-radius:4px;">
        — <em>Sem inspeção especial registrada</em>
      </div>
        """
    else:
        html += f"""
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Ano</td>
            <td style="padding:2px 4px;font-weight:500;">{_fmt(row.get('esp_ano'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Geral</td>
            <td style="padding:2px 4px;">{_cond_badge(row.get('esp_geral'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Estrutural (E)</td>
            <td style="padding:2px 4px;">{_cond_badge(row.get('esp_E'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Durabilidade (D)</td>
            <td style="padding:2px 4px;">{_cond_badge(row.get('esp_D'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Funcional (F)</td>
            <td style="padding:2px 4px;">{_cond_badge(row.get('esp_F'))}</td></tr>
        <tr><td style="color:#7f8c8d;padding:2px 4px;">Obs.</td>
            <td style="padding:2px 4px;font-style:italic;">{_fmt(row.get('esp_obs'))}</td></tr>
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


def _cond_badge_tt(prefix: str, val) -> str:
    """Badge colorido para tooltip: ex. 'G2' com fundo laranja."""
    s = str(val)
    if s in ("S.I.", "nan", "None", ""):
        return (f'<span style="background:#7f0000;color:#fff;padding:2px 6px;'
                f'border-radius:4px;font-weight:800;font-size:12px;">{prefix}S.I.</span>')
    try:
        n   = int(float(val))
        c   = COND_HEX.get(n, "#95a5a6")
        txt = "#1a1a1a" if n in (3, 4) else "#ffffff"
        return (f'<span style="background:{c};color:{txt};padding:2px 8px;'
                f'border-radius:4px;font-weight:800;font-size:12px;">{prefix}{n}</span>')
    except (TypeError, ValueError):
        return s


def _build_tooltip(row: pd.Series, nome: str, is_si: bool) -> str:
    """Tooltip HTML: nome → G/E/D/F badges → RAAE → Cidade."""
    g = _cond_badge_tt("G", row.get("insp_geral", "S.I."))
    e = _cond_badge_tt("E", row.get("insp_E",     "S.I."))
    d = _cond_badge_tt("D", row.get("insp_D",     "S.I."))
    f = _cond_badge_tt("F", row.get("insp_F",     "S.I."))

    raae_str   = str(row.get("raae", "")).strip()
    raae_color = RAAE_HEX.get(raae_str, "#95a5a6")
    raae_badge = (
        f'<span style="background:{raae_color};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-weight:700;font-size:12px;">{raae_str or "—"}</span>'
        if raae_str else "—"
    )

    cidade = str(row.get("cidade", "")).strip() or "—"

    alerta = ""
    if is_si:
        alerta = '<div style="color:#c0392b;font-weight:700;font-size:11px;margin-bottom:5px;">⚠ Sem Inspeção</div>'

    def _row_tt(label, badge):
        return (
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'gap:8px;padding:2px 0;">'
            f'<span style="font-size:11px;color:#7f8c8d;white-space:nowrap;">{label}</span>'
            f'{badge}'
            f'</div>'
        )

    return f"""
    <div style="font-family:Arial,sans-serif;padding:6px 4px;min-width:200px;">
      <div style="font-size:13px;font-weight:800;color:#2c3e50;
                  border-bottom:2px solid #3498db;padding-bottom:4px;margin-bottom:6px;">
        {nome}
      </div>
      {alerta}
      {_row_tt("Condição Geral",        g)}
      {_row_tt("Condição Estrutural",   e)}
      {_row_tt("Condição Durabilidade", d)}
      {_row_tt("Condição Funcional",    f)}
      {_row_tt("RAAE",                  raae_badge)}
      <div style="font-size:11px;color:#7f8c8d;margin-top:5px;border-top:1px solid #ecf0f1;padding-top:4px;">
        {cidade}
      </div>
    </div>
    """


def _nearest_radii(df: pd.DataFrame) -> dict:
    """
    Calcula raios de influência RAAE via Jacobi sobre a Árvore Geradora Mínima
    (MST) das posições únicas.

    Agrupamento por distância real (≤ 500 m) em vez de coordenada arredondada,
    evitando que pares quase co-localizados (ex.: OAE04/OAE05 a 300 m)
    criem raios minúsculos que impedem a tangência com vizinhos distantes.

    Usa apenas vizinhos MST no Jacobi → tangência ao longo de toda a cadeia
    ferroviária, com possíveis sobreposições leves em curvas da via.
    """
    valid = df.dropna(subset=["latitude", "longitude"]).reset_index(drop=True).copy()
    if valid.empty:
        return {}

    # ── Agrupamento por distância ≤ 500 m (union-find simples) ───────────────
    GROUP_THRESHOLD_M = 500
    n_pts = len(valid)
    gid = list(range(n_pts))

    def _root(i: int) -> int:
        while gid[i] != i:
            gid[i] = gid[gid[i]]
            i = gid[i]
        return i

    for i in range(n_pts):
        for j in range(i + 1, n_pts):
            d = geodesic(
                (float(valid.loc[i, "latitude"]), float(valid.loc[i, "longitude"])),
                (float(valid.loc[j, "latitude"]), float(valid.loc[j, "longitude"])),
            ).meters
            if d <= GROUP_THRESHOLD_M:
                ri, rj = _root(i), _root(j)
                if ri != rj:
                    gid[ri] = rj

    from collections import defaultdict
    by_group: dict[int, list[int]] = defaultdict(list)
    for i in range(n_pts):
        by_group[_root(i)].append(i)

    groups: list[tuple[list[str], float, float]] = []
    for indices in by_group.values():
        names = [valid.loc[i, "nome"] for i in indices]
        lat   = float(np.mean([valid.loc[i, "latitude"]  for i in indices]))
        lon   = float(np.mean([valid.loc[i, "longitude"] for i in indices]))
        groups.append((names, lat, lon))

    n = len(groups)
    if n == 1:
        return {name: 5_000 for name in groups[0][0]}

    # ── Distâncias geodésicas entre grupos únicos ────────────────────────────
    dists = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = geodesic(
                (groups[i][1], groups[i][2]),
                (groups[j][1], groups[j][2]),
            ).meters
            dists[i][j] = dists[j][i] = d

    # ── Árvore Geradora Mínima via Prim ──────────────────────────────────────
    in_mst   = [False] * n
    min_edge = [float("inf")] * n
    parent   = [-1] * n
    min_edge[0] = 0.0
    heap = [(0.0, 0)]
    mst_adj: list[list[int]] = [[] for _ in range(n)]

    while heap:
        d, u = heapq.heappop(heap)
        if in_mst[u]:
            continue
        in_mst[u] = True
        if parent[u] != -1:
            mst_adj[u].append(parent[u])
            mst_adj[parent[u]].append(u)
        for v in range(n):
            if not in_mst[v] and dists[u][v] < min_edge[v]:
                min_edge[v] = dists[u][v]
                parent[v] = u
                heapq.heappush(heap, (min_edge[v], v))

    # ── Jacobi sobre arestas MST: cresce até tangência na cadeia ─────────────
    radii = [
        min((dists[i][j] for j in mst_adj[i]), default=5_000) / 2.0
        for i in range(n)
    ]
    for _ in range(4 * n + 10):
        r_old     = list(radii)
        new_radii = list(radii)
        for i in range(n):
            if not mst_adj[i]:
                continue
            cap = min(dists[i][j] - r_old[j] for j in mst_adj[i])
            if cap > new_radii[i]:
                new_radii[i] = cap
        delta = max(abs(new_radii[i] - radii[i]) for i in range(n))
        radii = new_radii
        if delta < 1.0:
            break

    # 3 % de buffer para tangência visualmente perceptível; mínimo 800 m
    MIN_R  = 800
    BUFFER = 1.03

    result: dict = {}
    groups_out: list[tuple[float, float, list[str], float]] = []
    for i, (names, glat, glon) in enumerate(groups):
        r = max(radii[i] * BUFFER, MIN_R)
        for name in names:
            result[name] = r
        groups_out.append((glat, glon, names, r))   # centroide, nomes, raio

    # Detecta arestas MST com gap residual (para linha tracejada no mapa)
    gap_lines: list[tuple[float, float, float, float]] = []
    for i in range(n):
        for j in mst_adj[i]:
            if j < i:
                continue
            ri = max(radii[i] * BUFFER, MIN_R)
            rj = max(radii[j] * BUFFER, MIN_R)
            if dists[i][j] - ri - rj > 1_000:
                gap_lines.append((
                    groups[i][1], groups[i][2],
                    groups[j][1], groups[j][2],
                ))

    result["__groups__"]    = groups_out    # type: ignore[assignment]
    result["__gap_lines__"] = gap_lines     # type: ignore[assignment]
    return result


def _add_raae_circles(
    fg: folium.FeatureGroup,
    df: pd.DataFrame,
    radii: dict = None,
) -> None:
    """
    Adiciona ao FeatureGroup fg um folium.Circle por OAE.
    Se `radii` não for fornecido, calcula internamente via _nearest_radii.
    """
    if radii is None:
        radii = _nearest_radii(df)

    gap_lines:   list = radii.pop("__gap_lines__", [])
    groups_data: list = radii.pop("__groups__",    [])

    # Linhas tracejadas para trechos sem cobertura (desenhadas abaixo dos círculos)
    for lat1, lon1, lat2, lon2 in gap_lines:
        folium.PolyLine(
            locations=[[lat1, lon1], [lat2, lon2]],
            color="#7f8c8d",
            weight=2,
            opacity=0.6,
            dash_array="12 6",
            tooltip="Trecho ferroviário sem cobertura OAE",
        ).add_to(fg)

    if groups_data:
        # UM círculo por grupo no centroide → tangência exata garantida
        _RAAE_RISK = {"Baixo": 1, "Médio": 2, "Alto": 3, "Muito Alto": 4, "Extremo": 5}
        nome_to_row = {str(r.get("nome", "")).strip(): r for _, r in df.iterrows()}

        for glat, glon, names, radius in groups_data:
            # RAAE de maior risco no grupo
            raae_str = ""
            max_risk = -1
            for nm in names:
                raw = str(nome_to_row.get(nm, {}).get("raae", "")).strip()
                s   = "" if raw in ("nan", "None", "NaN") else raw
                if _RAAE_RISK.get(s, 0) > max_risk:
                    max_risk, raae_str = _RAAE_RISK.get(s, 0), s

            known  = raae_str in RAAE_HEX
            color  = RAAE_HEX.get(raae_str, "#7f8c8d")
            label  = ", ".join(sorted(names))
            folium.Circle(
                location=[glat, glon],
                radius=radius,
                color=color,
                weight=2,
                opacity=1.0,
                fill=True,
                fill_color=color,
                fill_opacity=0.10 if known else 0.04,
                dash_array=None if known else "8",
                tooltip=f"{label} · RAAE: {raae_str or 'N/D'} · R≈{radius/1000:.1f} km",
            ).add_to(fg)
    else:
        # Fallback: círculo individual por OAE (sem dados de grupos)
        for _, row in df.iterrows():
            lat = row.get("latitude")
            lon = row.get("longitude")
            if pd.isna(lat) or pd.isna(lon):
                continue
            nome     = str(row.get("nome", "")).strip()
            raae_raw = str(row.get("raae", "")).strip()
            raae_str = "" if raae_raw in ("nan", "None", "NaN") else raae_raw
            known    = raae_str in RAAE_HEX
            color    = RAAE_HEX.get(raae_str, "#7f8c8d")
            radius   = radii.get(nome, 5_000)
            folium.Circle(
                location=[float(lat), float(lon)],
                radius=radius,
                color=color,
                weight=2,
                opacity=1.0,
                fill=True,
                fill_color=color,
                fill_opacity=0.10 if known else 0.04,
                dash_array=None if known else "8",
                tooltip=f"{nome} · RAAE: {raae_str or 'N/D'} · R≈{radius/1000:.1f} km",
            ).add_to(fg)


def _build_raae_heat_legend(df: pd.DataFrame) -> str:
    """
    Painel RAAE — canto inferior esquerdo do mapa.
    Mesmo estilo e posição espelhada da legenda Condição Geral (canto inf. direito).
    """
    from collections import Counter
    raae_clean = (
        df["raae"].astype(str).str.strip()
        .replace({"nan": "", "None": "", "NaN": ""})
    )
    counts: Counter = Counter(raae_clean)
    total = sum(counts.values())

    # Mesmo estilo de linha usado em _build_legend (Condição Geral)
    rows_html = "".join(
        f'<div style="display:flex;align-items:center;gap:6px;margin:5px 0;">'
        f'<div style="width:13px;height:13px;border-radius:50%;background:{c};'
        f'flex-shrink:0;border:1px solid rgba(0,0,0,.15);"></div>'
        f'<span style="flex:1;">{lbl}</span>'
        f'<span style="background:#f0f0f0;border-radius:10px;padding:1px 7px;'
        f'font-weight:700;font-size:11px;min-width:22px;text-align:center;">'
        f'{counts.get(lbl, 0)}</span>'
        f'</div>'
        for c, lbl in RAAE_HEAT_LEGEND
    )
    return f"""
    <div style="
        position:fixed;bottom:40px;left:10px;z-index:1000;
        background:white;padding:12px 16px;border-radius:8px;
        box-shadow:0 2px 8px rgba(0,0,0,.3);font-family:Arial,sans-serif;font-size:12px;
    ">
      <b style="font-size:13px;">RAAE</b>
      <div style="font-size:10px;color:#7f8c8d;margin:2px 0 6px;">
        Total: {total} OAEs
      </div>
      {rows_html}
    </div>
    """


def _build_pat_summary_legend(df: pd.DataFrame, eff_pats: list) -> str:
    """
    Painel flutuante de resumo de manifestações patológicas.
    Posicionado acima do painel RAAE (bottom:245px;left:10px).
    Mostra cada patologia com contagem de OAEs afetados.
    """
    from collections import Counter

    pat_clean = df["patologia"].astype(str).str.strip()
    counts: Counter = Counter(pat_clean)
    # Filtra apenas as patologias efetivamente exibidas no mapa, ordena por frequência
    rows_data = sorted(
        [(p, counts.get(p, 0)) for p in eff_pats],
        key=lambda x: x[1],
        reverse=True,
    )
    total = sum(c for _, c in rows_data)
    MAX_VISIBLE = 8
    visible = rows_data[:MAX_VISIBLE]
    extra   = len(rows_data) - MAX_VISIBLE

    rows_html = "".join(
        f'<div style="display:flex;align-items:center;gap:6px;margin:4px 0;">'
        f'<div style="width:12px;height:12px;border-radius:50%;background:{pat_hex_color(p)};'
        f'flex-shrink:0;border:1px solid rgba(0,0,0,.15);"></div>'
        f'<span style="flex:1;font-size:11px;white-space:nowrap;overflow:hidden;'
        f'text-overflow:ellipsis;max-width:140px;" title="{p}">{p}</span>'
        f'<span style="background:#f0f0f0;border-radius:10px;padding:1px 6px;'
        f'font-weight:700;font-size:10px;min-width:20px;text-align:center;">'
        f'{cnt}</span>'
        f'</div>'
        for p, cnt in visible
    )
    extra_html = (
        f'<div style="font-size:10px;color:#7f8c8d;margin-top:4px;">'
        f'+ {extra} tipo(s) não exibidos</div>'
        if extra > 0 else ""
    )

    return f"""
    <div style="
        position:fixed;bottom:245px;left:10px;z-index:1001;
        background:white;padding:12px 16px;border-radius:8px;
        box-shadow:0 2px 8px rgba(0,0,0,.3);font-family:Arial,sans-serif;font-size:12px;
        max-width:240px;
    ">
      <b style="font-size:13px;">🔬 Manifestações Patológicas</b>
      <div style="font-size:10px;color:#7f8c8d;margin:2px 0 6px;">
        {len(eff_pats)} tipo(s) · {total} ocorrências
      </div>
      {rows_html}
      {extra_html}
    </div>
    """


def _add_pathology_area_layers(
    m: folium.Map,
    df: pd.DataFrame,
    selected_pats: list,
    radii: dict,
) -> None:
    """
    Adiciona círculos de área de patologia DIRETAMENTE no mapa (sem FeatureGroup).

    Sem FeatureGroup → não polui o LayerControl; visibilidade controlada
    exclusivamente pelo multiselect da sidebar.
    Raio = mesmo das zonas RAAE para cruzamento visual direto.
    """
    for pat in selected_pats:
        color  = pat_hex_color(pat)
        subset = df[df["patologia"].astype(str).str.strip() == pat]

        for _, row in subset.iterrows():
            lat = row.get("latitude")
            lon = row.get("longitude")
            if pd.isna(lat) or pd.isna(lon):
                continue

            nome     = str(row.get("nome", ""))
            raae     = str(row.get("raae", "")).strip()
            geral    = str(row.get("insp_geral", "S.I."))
            raae_col = RAAE_HEX.get(raae, "#95a5a6")
            radius   = radii.get(nome, 5_000)

            tooltip_html = (
                f'<div style="font-family:Arial,sans-serif;font-size:12px;'
                f'min-width:190px;padding:4px 2px;">'
                f'<b style="color:#2c3e50;font-size:13px;">{nome}</b><br>'
                f'<div style="display:flex;align-items:center;gap:5px;margin:4px 0 2px;">'
                f'<span style="display:inline-block;width:10px;height:10px;'
                f'border-radius:50%;background:{color};flex-shrink:0;"></span>'
                f'<span style="color:#7f8c8d;">Patologia:</span> '
                f'<b style="color:{color};">{pat}</b>'
                f'</div>'
                f'<div style="display:flex;align-items:center;gap:5px;">'
                f'<span style="color:#7f8c8d;">RAAE:</span>'
                f'<span style="background:{raae_col};color:#fff;padding:1px 7px;'
                f'border-radius:4px;font-size:11px;font-weight:700;">{raae or "—"}</span>'
                f'<span style="color:#7f8c8d;margin-left:6px;">G:</span>'
                f'<b>{geral}</b>'
                f'</div>'
                f'<div style="font-size:10px;color:#95a5a6;margin-top:3px;">'
                f'R ≈ {radius/1000:.1f} km</div>'
                f'</div>'
            )

            folium.Circle(
                location=[float(lat), float(lon)],
                radius=radius,
                color=color,
                weight=2,
                opacity=0.90,
                fill=True,
                fill_color=color,
                fill_opacity=0.28,
                tooltip=tooltip_html,
            ).add_to(m)


def build_map(
    df: pd.DataFrame,
    color_mode: str = "condition",
    selected_pathologies: list = None,
    show_raae: bool = False,
    show_pat_zones: bool = False,
) -> folium.Map:
    """
    Constrói o mapa com LayerControl discreto (collapsed=True, canto sup. direito).
    show_raae=True: ativa as Zonas RAAE e adiciona painel resumo (bottom-left).
    show_pat_zones=True: ativa círculos de patologia e painel resumo ACIMA do RAAE.
    """
    valid_coords = df.dropna(subset=["latitude", "longitude"])
    if valid_coords.empty:
        center = DEF_CENTER
        zoom   = 7
    else:
        center = [valid_coords["latitude"].mean(), valid_coords["longitude"].mean()]
        zoom   = 7

    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles="OpenStreetMap",
        control_scale=True,
    )
    folium.TileLayer("CartoDB positron", name="CartoDB Positron").add_to(m)
    folium.TileLayer("CartoDB dark_matter", name="Dark Matter").add_to(m)

    # Ajusta o zoom automaticamente para enquadrar todos os marcadores
    if not valid_coords.empty:
        lat_min = valid_coords["latitude"].min()
        lat_max = valid_coords["latitude"].max()
        lon_min = valid_coords["longitude"].min()
        lon_max = valid_coords["longitude"].max()
        m.fit_bounds([[lat_min, lon_min], [lat_max, lon_max]], padding=(30, 30))

    # ── Raios calculados uma vez, reutilizados por RAAE e Patologias ─────────
    radii = _nearest_radii(df)

    # ── CAMADA 1: Zonas RAAE — visibilidade e legenda controladas pelo sidebar ──
    fg_raa = folium.FeatureGroup(name="🟢 Zonas RAAE – Influência Ambiental", show=show_raae)
    _add_raae_circles(fg_raa, df, radii=radii)
    if show_raae:
        m.get_root().html.add_child(folium.Element(_build_raae_heat_legend(df)))
    fg_raa.add_to(m)

    # ── CAMADA 2: Marcadores de Condição (todos os OAEs) ──────────────────────
    fg_oae = folium.FeatureGroup(name="🔵 OAEs – Condição", show=True)

    for _, row in df.iterrows():
        lat = row.get("latitude")
        lon = row.get("longitude")
        if pd.isna(lat) or pd.isna(lon):
            continue

        is_si     = bool(row.get("sem_inspecao", False))
        hex_color = _marker_color(row, color_mode)
        popup     = _build_popup(row)
        nome      = str(row.get("nome", ""))
        tooltip   = _build_tooltip(row, nome, is_si)

        if is_si:
            icon_html = f"""
            <div style="text-align:center;min-width:52px;">
              <div style="background:#7f0000;color:#fff;border-radius:50%;
                          width:22px;height:22px;line-height:22px;font-size:13px;
                          margin:0 auto;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4);">
                ⚠
              </div>
              <div style="font-size:8.5px;font-weight:700;color:#7f0000;
                          margin-top:2px;white-space:nowrap;
                          text-shadow:0 0 3px #fff,-1px 0 #fff,1px 0 #fff;">
                {nome}
              </div>
            </div>"""
        else:
            txt_color   = "#1a1a1a" if hex_color in ("#F4D03F", "#58D68D") else "#ffffff"
            label_color = "#1a1a2e"
            icon_html = f"""
            <div style="text-align:center;min-width:52px;">
              <div style="background:{hex_color};color:{txt_color};
                          border-radius:50%;width:22px;height:22px;
                          line-height:22px;font-size:10px;font-weight:800;
                          margin:0 auto;border:2px solid #fff;
                          box-shadow:0 1px 5px rgba(0,0,0,.35);">
              </div>
              <div style="font-size:8.5px;font-weight:700;color:{label_color};
                          margin-top:2px;white-space:nowrap;
                          text-shadow:0 0 3px #fff,-1px 0 #fff,1px 0 #fff;">
                {nome}
              </div>
            </div>"""

        folium.Marker(
            location=[lat, lon],
            popup=popup,
            tooltip=tooltip,
            icon=folium.DivIcon(
                html=icon_html,
                icon_size=(60, 38),
                icon_anchor=(30, 11),
            ),
        ).add_to(fg_oae)

    fg_oae.add_to(m)

    # ── CAMADAS 3+: Áreas de patologia direto no mapa (sem FeatureGroup) ───────
    if show_pat_zones:
        all_pats = sorted(df["patologia"].dropna().astype(str).str.strip().unique().tolist())
        eff_pats = selected_pathologies if selected_pathologies else all_pats
        if eff_pats:
            _add_pathology_area_layers(m, df, eff_pats, radii)
            m.get_root().html.add_child(
                folium.Element(_build_pat_summary_legend(df, eff_pats))
            )

    # LayerControl discreto: apenas tiles + RAAE + OAEs — sem patologias
    folium.LayerControl(collapsed=True, position="topright").add_to(m)

    # Legenda de condição/RAAE
    legend_html = _build_legend(color_mode, df)
    m.get_root().html.add_child(folium.Element(legend_html))

    return m


def _build_legend(mode: str, df: pd.DataFrame = None) -> str:
    if mode == "raae":
        # RAAE: conta OAEs por nível
        items = []
        for lbl, c in RAAE_HEX.items():
            cnt = int((df["raae"].astype(str).str.strip() == lbl).sum()) if df is not None else 0
            items.append((c, lbl, cnt))
        title = "RAAE"
    else:
        # Condição Geral 0-5: sem numeração, sem S.I., com contagem
        geral_num = pd.to_numeric(df["insp_geral"], errors="coerce") if df is not None else None
        items = []
        for k in sorted(COND_HEX):
            cnt = int((geral_num == k).sum()) if geral_num is not None else 0
            items.append((COND_HEX[k], COND_LABEL[k], cnt))
        title = "Condição Geral"

    rows_html = "".join(
        f'<div style="display:flex;align-items:center;gap:6px;margin:5px 0;">'
        f'<div style="width:13px;height:13px;border-radius:50%;background:{c};'
        f'flex-shrink:0;border:1px solid rgba(0,0,0,.15);"></div>'
        f'<span style="flex:1;">{lbl}</span>'
        f'<span style="background:#f0f0f0;border-radius:10px;padding:1px 7px;'
        f'font-weight:700;font-size:11px;min-width:22px;text-align:center;">{cnt}</span>'
        f'</div>'
        for c, lbl, cnt in items
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
