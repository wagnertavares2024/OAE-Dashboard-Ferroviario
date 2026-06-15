"""
report_generator.py
Gerador de Relatório Técnico de Obras de Adequação de OAEs Ferroviárias.
Saída: HTML pronto para impressão / exportação como PDF via Ctrl+P.
"""
import datetime
import pandas as pd

# ---------------------------------------------------------------------------
# METADADOS DE CONDIÇÃO (NBR 9452)
# ---------------------------------------------------------------------------

COND_META = {
    0: dict(
        label="Emergencial", bg="#8E44AD", fg="#ffffff",
        prazo="Imediato – interdição",
        urgencia="CRÍTICA",
        resumo="Risco iminente à integridade estrutural e segurança dos usuários. Interdição obrigatória.",
        intervencao=[
            "Interdição imediata ao tráfego ferroviário",
            "Comunicação imediata à autoridade competente e equipe de engenharia sênior",
            "Contratação emergencial de inspeção especial com engenheiro especialista em estruturas",
            "Implantação de reforço estrutural provisório de emergência",
            "Monitoramento contínuo com instrumentação (inclinômetros, extensômetros)",
            "Elaboração de projeto de recuperação/reforço estrutural definitivo",
        ],
        normas="NBR 9452, NBR 6118, NBR 14931",
    ),
    1: dict(
        label="Crítico", bg="#C0392B", fg="#ffffff",
        prazo="Até 30 dias",
        urgencia="MUITO ALTA",
        resumo="Comprometimento estrutural grave. Intervenção urgente para evitar colapso ou agravamento.",
        intervencao=[
            "Elaboração de projeto de reforço e/ou recuperação estrutural",
            "Tratamento de fissuras ativas (injeção de resina epóxi ou poliuretano)",
            "Reforço de elementos danificados: pilares, vigas, longarinas, aparelhos de apoio",
            "Inspeção especial completa com emissão de laudo técnico",
            "Monitoramento periódico (trimestral) após intervenção",
            "Restrição de carga máxima por tráfego, se aplicável",
        ],
        normas="NBR 9452, NBR 6118, NBR 9778",
    ),
    2: dict(
        label="Ruim", bg="#E67E22", fg="#ffffff",
        prazo="Até 90 dias",
        urgencia="ALTA",
        resumo="Deterioração significativa. Recuperação estrutural programada necessária.",
        intervencao=[
            "Recuperação superficial do concreto deteriorado (carbonatação / contaminação por cloretos)",
            "Tratamento anticorrosivo de armaduras expostas (limpeza, primer, selante)",
            "Selagem e injeção de fissuras passivas",
            "Recomposição de revestimentos e impermeabilização",
            "Pintura de proteção superficial com tinta inibidora de corrosão",
            "Revisão do sistema de drenagem (drenos, calhas, pingadeiras)",
        ],
        normas="NBR 9452, NBR 6118, NBR 12655",
    ),
    3: dict(
        label="Regular", bg="#F4D03F", fg="#1a1a1a",
        prazo="Até 180 dias",
        urgencia="MÉDIA",
        resumo="Deterioração incipiente. Manutenção corretiva preventiva necessária.",
        intervencao=[
            "Impermeabilização de lajes, vigas e juntas de dilatação",
            "Recuperação e desobstrução do sistema de drenagem",
            "Tratamento preventivo de fissuras superficiais",
            "Limpeza geral de pichações, vegetação e depósitos",
            "Pintura de proteção e sinalização",
            "Inspeção rotineira semestral com registro fotográfico",
        ],
        normas="NBR 9452, NBR 14931",
    ),
    4: dict(
        label="Bom", bg="#58D68D", fg="#1a1a1a",
        prazo="Ciclo anual",
        urgencia="BAIXA",
        resumo="Pequenos reparos pontuais. Manutenção rotineira suficiente.",
        intervencao=[
            "Manutenção rotineira conforme Plano de Manutenção Estrutural",
            "Limpeza de drenos, calhas e dispositivos de drenagem",
            "Inspeção visual semestral com registro fotográfico",
            "Verificação de aparelhos de apoio e juntas de dilatação",
            "Retoques de pintura e sinalização",
        ],
        normas="NBR 9452",
    ),
    5: dict(
        label="Excelente", bg="#1E8449", fg="#ffffff",
        prazo="Plano de Manutenção",
        urgencia="MÍNIMA",
        resumo="Estrutura em ótimas condições. Manutenção preventiva periódica.",
        intervencao=[
            "Inspeção visual semestral conforme Plano de Manutenção",
            "Limpeza geral periódica",
            "Registro fotográfico de referência para histórico",
            "Manutenção preventiva programada (aparelhos de apoio, drenagem)",
        ],
        normas="NBR 9452",
    ),
}

RAAE_BG   = {"Baixo": "#d5f5e3", "Médio": "#fef9e7", "Alto": "#fdebd0",
             "Muito Alto": "#fadbd8", "Extremo": "#e8daef"}
RAAE_FG   = {"Baixo": "#1e8449", "Médio": "#9a7d0a", "Alto": "#a04000",
             "Muito Alto": "#922b21", "Extremo": "#6c3483"}
RAAE_RANK = {"Extremo": 5, "Muito Alto": 4, "Alto": 3, "Médio": 2, "Baixo": 1}


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _v(val, nd="N/D") -> str:
    s = str(val).strip()
    return nd if s in ("nan", "None", "", "S.I.", "nat") else s


def _cond_badge(val) -> str:
    s = str(val).strip()
    if s in ("nan", "None", "", "S.I."):
        return '<span style="background:#7f0000;color:#fff;padding:2px 8px;border-radius:4px;font-weight:700;">S.I.</span>'
    try:
        n = int(float(s))
        m = COND_META.get(n, {})
        bg, fg, lbl = m.get("bg", "#ccc"), m.get("fg", "#000"), m.get("label", str(n))
        return (f'<span style="background:{bg};color:{fg};padding:2px 8px;'
                f'border-radius:4px;font-weight:700;">{n} – {lbl}</span>')
    except (ValueError, TypeError):
        return f'<span>{s}</span>'


def _cond_td(val) -> str:
    s = str(val).strip()
    if s in ("nan", "None", "", "S.I."):
        return '<td style="background:#7f0000;color:#fff;font-weight:700;text-align:center;padding:5px;">S.I.</td>'
    try:
        n = int(float(s))
        m = COND_META.get(n, {})
        bg, fg, lbl = m.get("bg", "#eee"), m.get("fg", "#000"), m.get("label", str(n))
        return (f'<td style="background:{bg};color:{fg};font-weight:700;'
                f'text-align:center;padding:5px;">{n}<br><small>{lbl}</small></td>')
    except (ValueError, TypeError):
        return f'<td style="padding:5px;">{s}</td>'


def _priority_score(row) -> int:
    try:
        cond = int(float(row.get("insp_geral", 5)))
    except (TypeError, ValueError):
        cond = 5
    return (5 - cond) * 70 + RAAE_RANK.get(str(row.get("raae", "")).strip(), 1) * 30


# ---------------------------------------------------------------------------
# GERADOR PRINCIPAL
# ---------------------------------------------------------------------------

def generate_report(df: pd.DataFrame, condition_levels: list) -> bytes:
    """
    Gera relatório técnico em HTML para as OAEs nos níveis de condição
    selecionados. Retorna bytes UTF-8.
    """
    geral_num = pd.to_numeric(df["insp_geral"], errors="coerce")
    df_sel = df[geral_num.isin(condition_levels)].copy()

    if df_sel.empty:
        return "<html><body><p>Nenhuma OAE encontrada para os critérios selecionados.</p></body></html>".encode("utf-8")

    df_sel["_priority"] = df_sel.apply(_priority_score, axis=1)
    df_sel = df_sel.sort_values("_priority", ascending=False).reset_index(drop=True)

    today     = datetime.date.today()
    date_str  = today.strftime("%d/%m/%Y")
    total_sel = len(df_sel)
    total_all = len(df)

    # ── Contagem por nível ────────────────────────────────────────────────────
    gn = pd.to_numeric(df_sel["insp_geral"], errors="coerce")
    counts_cond = {lvl: int((gn == lvl).sum()) for lvl in sorted(condition_levels)}

    # ── Resumo por RAAE ───────────────────────────────────────────────────────
    raae_summary = df_sel["raae"].value_counts().to_dict()

    # ── Cabeçalho CSS ─────────────────────────────────────────────────────────
    css = """
    <style>
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 11pt;
             color: #2c3e50; background: #fff; }
      h1 { font-size: 17pt; }
      h2 { font-size: 13pt; border-bottom: 2px solid #2c3e50;
           padding-bottom: 4px; margin: 22px 0 10px; }
      h3 { font-size: 11pt; margin: 14px 0 6px; }
      table { width: 100%; border-collapse: collapse; font-size: 10pt; margin-bottom: 12px; }
      th { background: #2c3e50; color: #fff; padding: 7px 8px;
           text-align: left; font-size: 9.5pt; }
      td { padding: 6px 8px; border-bottom: 1px solid #e0e0e0; vertical-align: top; }
      tr:nth-child(even) td { background: #f7f9fc; }
      .cover { background: linear-gradient(135deg,#1e2a38,#2c3e50);
               color: #fff; padding: 40px 48px; margin-bottom: 28px;
               border-radius: 8px; }
      .cover .org { font-size: 9pt; opacity:.7; margin-bottom:6px; letter-spacing:1px; text-transform:uppercase; }
      .cover h1  { font-size: 20pt; line-height:1.25; margin-bottom:8px; }
      .cover .sub{ font-size: 11pt; opacity:.8; }
      .cover .meta{ margin-top:20px; font-size:9.5pt; opacity:.75; }
      .badge-cond { display:inline-block; padding:3px 10px; border-radius:4px;
                    font-weight:700; font-size:9.5pt; }
      .badge-raae { display:inline-block; padding:3px 10px; border-radius:4px;
                    font-weight:600; font-size:9.5pt; }
      .oae-card { border:1px solid #d0d7de; border-radius:8px;
                  margin-bottom:24px; page-break-inside: avoid; overflow:hidden; }
      .oae-card-head { padding:10px 16px; display:flex; align-items:center;
                       justify-content:space-between; }
      .oae-card-body { padding:14px 16px; }
      .row-2 { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
      .row-3 { display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; }
      .field label { font-size:8.5pt; color:#7f8c8d; text-transform:uppercase;
                     letter-spacing:.5px; display:block; margin-bottom:2px; }
      .field .val  { font-size:10.5pt; font-weight:600; }
      .intervencoes li { margin-bottom:5px; }
      .section-tag { display:inline-block; background:#eaf4fb; color:#1a5276;
                     font-size:8.5pt; font-weight:700; padding:2px 8px;
                     border-radius:3px; margin-bottom:6px; letter-spacing:.5px; }
      .priority-bar { height:8px; border-radius:4px; }
      .footer { margin-top:28px; border-top:1px solid #ddd; padding-top:10px;
                font-size:8.5pt; color:#95a5a6; text-align:center; }
      @media print {
        .oae-card { page-break-inside: avoid; }
        body { font-size: 10pt; }
      }
    </style>
    """

    # ── Capa ──────────────────────────────────────────────────────────────────
    niveis_str = ", ".join(
        f"{lvl} – {COND_META[lvl]['label']}"
        for lvl in sorted(condition_levels)
        if lvl in COND_META
    )
    cover_html = f"""
    <div class="cover">
      <div class="org">Gestão de OAEs Ferroviárias · Relatório Técnico</div>
      <h1>Relatório de Obras de Adequação<br>de Obras de Arte Especiais</h1>
      <div class="sub">Planejamento de Intervenções Estruturais por Parâmetro de Condição</div>
      <div class="meta">
        <b>Data de Emissão:</b> {date_str} &nbsp;|&nbsp;
        <b>Parâmetros de Condição Tratados:</b> {niveis_str}<br>
        <b>OAEs Selecionadas:</b> {total_sel} de {total_all} &nbsp;|&nbsp;
        <b>Referência:</b> ABNT NBR 9452:2019
      </div>
    </div>
    """

    # ── Resumo Executivo ──────────────────────────────────────────────────────
    cond_rows = "".join(
        f'<tr><td>{lvl}</td>'
        f'<td><span class="badge-cond" style="background:{COND_META[lvl]["bg"]};'
        f'color:{COND_META[lvl]["fg"]};">{COND_META[lvl]["label"]}</span></td>'
        f'<td style="text-align:center;font-weight:700;">{counts_cond.get(lvl,0)}</td>'
        f'<td style="color:#7f8c8d;font-size:9pt;">{COND_META[lvl]["prazo"]}</td>'
        f'<td style="color:#7f8c8d;font-size:9pt;">{COND_META[lvl]["resumo"]}</td>'
        f'</tr>'
        for lvl in sorted(condition_levels)
        if lvl in COND_META
    )

    raae_rows = "".join(
        f'<tr><td><span class="badge-raae" style="background:{RAAE_BG.get(r,"#eee")};'
        f'color:{RAAE_FG.get(r,"#333")};">{r}</span></td>'
        f'<td style="text-align:center;font-weight:700;">{raae_summary.get(r,0)}</td></tr>'
        for r in ["Extremo", "Muito Alto", "Alto", "Médio", "Baixo"]
        if raae_summary.get(r, 0) > 0
    )

    summary_html = f"""
    <h2>1. Resumo Executivo</h2>
    <div class="row-2" style="margin-bottom:18px;">
      <div>
        <div class="section-tag">DISTRIBUIÇÃO POR CONDIÇÃO</div>
        <table>
          <thead><tr>
            <th style="width:40px;">Nível</th><th>Classificação</th>
            <th style="width:60px;">OAEs</th><th>Prazo</th><th>Síntese</th>
          </tr></thead>
          <tbody>{cond_rows}</tbody>
        </table>
      </div>
      <div>
        <div class="section-tag">DISTRIBUIÇÃO POR RAAE</div>
        <table>
          <thead><tr><th>Zona RAAE</th><th style="width:60px;">OAEs</th></tr></thead>
          <tbody>{raae_rows}</tbody>
        </table>
        <div style="margin-top:14px;padding:12px;background:#fef9e7;border-left:4px solid #f39c12;border-radius:4px;font-size:9.5pt;">
          <b>⚠️ Critério de Priorização:</b><br>
          Score = (5 – Condição) × 70 + Ranking RAAE × 30<br>
          Condição 0 + RAAE Extremo = maior prioridade (Score 410)
        </div>
      </div>
    </div>
    """

    # ── Tabela de Prioridades ─────────────────────────────────────────────────
    max_score = df_sel["_priority"].max() if not df_sel.empty else 1
    prio_rows = ""
    for idx, (_, row) in enumerate(df_sel.iterrows(), 1):
        score   = row["_priority"]
        pct     = int(score / max_score * 100)
        raae    = _v(row.get("raae", ""))
        rbg     = RAAE_BG.get(raae, "#eee")
        rfg     = RAAE_FG.get(raae, "#333")
        tipo    = _v(row.get("tipo", ""))
        cidade  = _v(row.get("cidade", ""))
        pat     = _v(row.get("patologia", ""), "—")
        prio_rows += (
            f'<tr>'
            f'<td style="text-align:center;font-weight:700;">{idx}</td>'
            f'<td><b>{_v(row["nome"])}</b></td>'
            f'<td>{tipo}</td>'
            f'<td>{cidade}</td>'
            f'<td>{_cond_td(row.get("insp_geral",""))}</td>'
            f'<td><span class="badge-raae" style="background:{rbg};color:{rfg};">{raae}</span></td>'
            f'<td style="min-width:80px;">'
            f'<div class="priority-bar" style="background:#e0e0e0;">'
            f'<div class="priority-bar" style="background:#c0392b;width:{pct}%;"></div>'
            f'</div><small style="color:#7f8c8d;">{score}</small>'
            f'</td>'
            f'<td style="font-size:9pt;color:#555;">{pat[:40]}</td>'
            f'</tr>'
        )

    priority_html = f"""
    <h2>2. Matriz de Priorização de Intervenções</h2>
    <table>
      <thead><tr>
        <th style="width:35px;">#</th><th>OAE</th><th>Tipo</th><th>Município</th>
        <th style="width:90px;">Condição</th><th>RAAE</th>
        <th style="width:100px;">Prioridade</th><th>Patologia Principal</th>
      </tr></thead>
      <tbody>{prio_rows}</tbody>
    </table>
    """

    # ── Fichas Individuais por OAE ────────────────────────────────────────────
    oae_cards_html = "<h2>3. Fichas Técnicas Individuais</h2>\n"

    for _, row in df_sel.iterrows():
        nome   = _v(row.get("nome", ""))
        tipo   = _v(row.get("tipo", ""))
        carac  = _v(row.get("caracteristica", ""))
        estat  = _v(row.get("estaticidade", ""))
        tab    = _v(row.get("tabuleiro", ""))
        cidade = _v(row.get("cidade", ""))
        ano    = _v(row.get("ano", ""))
        vaos   = _v(row.get("qtd_vaos", ""))
        vao_m  = _v(row.get("comp_maior_vao", ""))
        alt_p  = _v(row.get("altura_pilar", ""))
        caa_c  = _v(row.get("caa_concreto", ""))
        caa_a  = _v(row.get("caa_aco", ""))
        lat    = _v(row.get("latitude", ""))
        lon    = _v(row.get("longitude", ""))
        raae   = _v(row.get("raae", ""))

        # Inspeção Rotineira
        i_ano  = _v(row.get("insp_ano", ""))
        i_ger  = row.get("insp_geral", "")
        i_e    = _v(row.get("insp_E", ""))
        i_d    = _v(row.get("insp_D", ""))
        i_f    = _v(row.get("insp_F", ""))
        i_obs  = _v(row.get("insp_obs", ""), "")
        pat    = _v(row.get("patologia", ""), "Não registrada")

        # Inspeção Especial
        e_ano  = _v(row.get("esp_ano", ""))
        e_ger  = row.get("esp_geral", "")
        e_e    = _v(row.get("esp_E", ""))
        e_d    = _v(row.get("esp_D", ""))
        e_f    = _v(row.get("esp_F", ""))
        e_obs  = _v(row.get("esp_obs", ""), "")

        # Classificação de condição
        try:
            cond_int = int(float(str(i_ger)))
        except (TypeError, ValueError):
            cond_int = None

        meta      = COND_META.get(cond_int, COND_META[5]) if cond_int is not None else COND_META[5]
        head_bg   = meta["bg"]
        head_fg   = meta["fg"]
        urgencia  = meta["urgencia"]
        prazo     = meta["prazo"]
        interv    = meta["intervencao"]
        normas    = meta["normas"]

        rbg = RAAE_BG.get(raae, "#eee")
        rfg = RAAE_FG.get(raae, "#333")

        li_items = "".join(f"<li>{it}</li>" for it in interv)

        coord_link = (
            f'<a href="https://www.google.com/maps?q={lat},{lon}" target="_blank" '
            f'style="color:#2980b9;font-size:9pt;">📍 Ver no mapa</a>'
            if lat not in ("N/D", "") and lon not in ("N/D", "") else ""
        )

        obs_rot  = f'<div style="font-size:9pt;color:#555;margin-top:4px;"><i>Obs: {i_obs}</i></div>' if i_obs else ""
        obs_esp  = f'<div style="font-size:9pt;color:#555;margin-top:4px;"><i>Obs: {e_obs}</i></div>' if e_obs else ""

        oae_cards_html += f"""
        <div class="oae-card">
          <!-- Cabeçalho da ficha -->
          <div class="oae-card-head" style="background:{head_bg};color:{head_fg};">
            <div>
              <div style="font-size:10pt;font-weight:900;letter-spacing:.3px;">{nome}</div>
              <div style="font-size:9pt;opacity:.85;">{tipo} · {carac} · {cidade}</div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:9pt;font-weight:700;opacity:.85;">Urgência: {urgencia}</div>
              <div style="font-size:9pt;opacity:.85;">Prazo: {prazo}</div>
            </div>
          </div>

          <div class="oae-card-body">
            <!-- Linha 1: dados básicos -->
            <div class="row-3" style="margin-bottom:14px;">
              <div>
                <div class="section-tag">DADOS DA ESTRUTURA</div>
                <table style="font-size:9.5pt;margin-bottom:0;">
                  <tr><td style="color:#7f8c8d;padding:3px 6px;">Estaticidade</td><td style="padding:3px 6px;font-weight:600;">{estat}</td></tr>
                  <tr><td style="color:#7f8c8d;padding:3px 6px;">Tabuleiro</td><td style="padding:3px 6px;font-weight:600;">{tab}</td></tr>
                  <tr><td style="color:#7f8c8d;padding:3px 6px;">Ano construção</td><td style="padding:3px 6px;font-weight:600;">{ano}</td></tr>
                  <tr><td style="color:#7f8c8d;padding:3px 6px;">Qtd. vãos</td><td style="padding:3px 6px;font-weight:600;">{vaos}</td></tr>
                  <tr><td style="color:#7f8c8d;padding:3px 6px;">Maior vão (m)</td><td style="padding:3px 6px;font-weight:600;">{vao_m}</td></tr>
                  <tr><td style="color:#7f8c8d;padding:3px 6px;">Alt. pilar (m)</td><td style="padding:3px 6px;font-weight:600;">{alt_p}</td></tr>
                </table>
              </div>
              <div>
                <div class="section-tag">AMBIENTE / RAAE</div>
                <div style="margin-bottom:8px;">
                  <span class="badge-raae" style="background:{rbg};color:{rfg};font-size:11pt;">{raae}</span>
                </div>
                <table style="font-size:9.5pt;margin-bottom:0;">
                  <tr><td style="color:#7f8c8d;padding:3px 6px;">CAA Concreto</td><td style="padding:3px 6px;font-weight:600;">{caa_c}</td></tr>
                  <tr><td style="color:#7f8c8d;padding:3px 6px;">CAA Aço</td><td style="padding:3px 6px;font-weight:600;">{caa_a}</td></tr>
                  <tr><td style="color:#7f8c8d;padding:3px 6px;">Coordenadas</td><td style="padding:3px 6px;font-size:8.5pt;">{lat}, {lon}<br>{coord_link}</td></tr>
                </table>
              </div>
              <div>
                <div class="section-tag">MANIFESTAÇÃO PATOLÓGICA</div>
                <div style="background:#fef9e7;border:1px solid #f0c060;border-radius:4px;
                            padding:8px 10px;font-size:9.5pt;font-weight:600;">{pat}</div>
              </div>
            </div>

            <!-- Linha 2: inspeções -->
            <div class="row-2" style="margin-bottom:14px;">
              <div>
                <div class="section-tag">INSPEÇÃO ROTINEIRA – ANO {i_ano}</div>
                <table style="font-size:10pt;">
                  <thead><tr>
                    <th style="width:33%;">Geral</th>
                    <th style="width:22%;">Estru. (E)</th>
                    <th style="width:22%;">Durabilidade (D)</th>
                    <th style="width:22%;">Funcional (F)</th>
                  </tr></thead>
                  <tbody><tr>
                    {_cond_td(i_ger)}{_cond_td(i_e)}{_cond_td(i_d)}{_cond_td(i_f)}
                  </tr></tbody>
                </table>
                {obs_rot}
              </div>
              <div>
                <div class="section-tag">INSPEÇÃO ESPECIAL – ANO {e_ano}</div>
                <table style="font-size:10pt;">
                  <thead><tr>
                    <th style="width:33%;">Geral</th>
                    <th style="width:22%;">Estru. (E)</th>
                    <th style="width:22%;">Durabilidade (D)</th>
                    <th style="width:22%;">Funcional (F)</th>
                  </tr></thead>
                  <tbody><tr>
                    {_cond_td(e_ger)}{_cond_td(e_e)}{_cond_td(e_d)}{_cond_td(e_f)}
                  </tr></tbody>
                </table>
                {obs_esp}
              </div>
            </div>

            <!-- Intervenções recomendadas -->
            <div>
              <div class="section-tag">INTERVENÇÕES RECOMENDADAS</div>
              <div style="display:grid;grid-template-columns:1fr auto;gap:12px;align-items:start;">
                <ul class="intervencoes" style="padding-left:18px;font-size:9.5pt;">{li_items}</ul>
                <div style="background:#f7f9fc;border:1px solid #d0d7de;border-radius:6px;
                            padding:10px 12px;font-size:8.5pt;min-width:170px;">
                  <div style="font-weight:700;color:#2c3e50;margin-bottom:4px;">Referências Normativas</div>
                  <div style="color:#555;">{normas}</div>
                </div>
              </div>
            </div>

          </div><!-- /oae-card-body -->
        </div><!-- /oae-card -->
        """

    # ── Rodapé ────────────────────────────────────────────────────────────────
    footer_html = f"""
    <div class="footer">
      Relatório gerado automaticamente em {date_str} pelo Dashboard OAE – Gestão Estrutural Ferroviária.
      Para impressão em PDF: Ctrl+P → Salvar como PDF. Referência normativa principal: ABNT NBR 9452:2019.
    </div>
    """

    # ── Monta HTML final ──────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Relatório Técnico OAE – {date_str}</title>
  {css}
</head>
<body style="padding:28px 36px;max-width:1100px;margin:0 auto;">
  {cover_html}
  {summary_html}
  {priority_html}
  {oae_cards_html}
  {footer_html}
</body>
</html>"""

    return html.encode("utf-8")
