"""
data_loader.py
Responsável por ler e processar o arquivo Excel com dados das OAEs.
"""

import pandas as pd
import numpy as np
from pathlib import Path


# ---------------------------------------------------------------------------
# CONFIGURAÇÕES DE LEITURA DO EXCEL
# ---------------------------------------------------------------------------

# Mapeamento das colunas da aba "Dados Fixos" (índices base-0)
# B=1,C=2,D=3,E=4,F=5,G=6,H=7,I=8,J=9,K=10,L=11,M=12,N=13,O=14,P=15,Q=16,R=17,S=18
FIXED_COLS = {
    "nome":         2,   # C - Nome da OAE
    "tipo":         3,   # D - Tipo de OAE
    "caracteristica": 4, # E - Característica
    "latitude":     6,   # G
    "longitude":    7,   # H
    "cidade":       8,   # I
    "raae":         9,   # J - Risco de Agressividade Ambiental
    "caa_concreto": 10,  # K
    "caa_aco":      11,  # L
    "ano":          12,  # M
    "qtd_vaos":     13,  # N
    "comp_maior_vao": 14,# O
    "altura_pilar": 15,  # P
    "estaticidade": 17,  # R
    "tabuleiro":    18,  # S
}

# Estrutura da aba "Inspeção Rotineira"
# Para cada ano há um bloco de colunas: Data, ABnt (Condição Geral), E, D, F, Obs
# Os índices exatos dependem do layout real; este mapeamento é ajustável.
ROTINEIRA_NAME_COL = 2  # C - Nome da OAE

# Blocos por ano: { ano: (col_data, col_geral, col_E, col_D, col_F, col_obs) }
# Baseado na descrição: 2025 usa H(7),I(8),J(9),K(10)
# 2024 tem estrutura equivalente, estimativa a partir do layout visual
ROTINEIRA_YEAR_BLOCKS = {
    2025: {"data": 7,  "geral": 7,  "E": 8,  "D": 9,  "F": 10, "obs": 11},
    2024: {"data": 13, "geral": 13, "E": 14, "D": 15, "F": 16, "obs": 17},
    2023: {"data": 19, "geral": 19, "E": 20, "D": 21, "F": 22, "obs": 23},
    2022: {"data": 25, "geral": 25, "E": 26, "D": 27, "F": 28, "obs": 29},
    2021: {"data": 31, "geral": 31, "E": 32, "D": 33, "F": 34, "obs": 35},
}

ROTINEIRA_PATOLOGIA_COL = 36  # AK (~coluna 36) - Manifestação Patológica

# Cores dos marcadores no mapa
RAAE_COLORS = {
    "Baixo":       "#2ecc71",   # verde
    "Médio":       "#f1c40f",   # amarelo
    "Alto":        "#e67e22",   # laranja
    "Muito Alto":  "#e74c3c",   # vermelho
    "Extremo":     "#8e44ad",   # roxo
}

CONDITION_COLORS = {
    1: "#2ecc71",
    2: "#f1c40f",
    3: "#e67e22",
    4: "#e74c3c",
    5: "#8e44ad",
    "S.I.": "#7f0000",   # vermelho escuro para sem inspeção
}


# ---------------------------------------------------------------------------
# FUNÇÕES AUXILIARES
# ---------------------------------------------------------------------------

def _safe_numeric(val):
    """Converte valor para numérico; retorna NaN em caso de falha."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return np.nan


def _is_blank(val) -> bool:
    """Retorna True se o valor for nulo, vazio ou apenas espaços."""
    if val is None:
        return True
    if isinstance(val, float) and np.isnan(val):
        return True
    return str(val).strip() == ""


# ---------------------------------------------------------------------------
# LEITURA DA ABA "DADOS FIXOS"
# ---------------------------------------------------------------------------

def load_fixed_data(xl: pd.ExcelFile, sheet_name: str = "Dados Fixos") -> pd.DataFrame:
    """
    Lê a aba de parâmetros fixos e retorna um DataFrame limpo.
    A leitura começa na linha 4 (header=3, base-0) para pular o título e
    o cabeçalho duplo visível no print.
    """
    raw = xl.parse(
        sheet_name,
        header=2,       # linha 3 (0-indexed) como cabeçalho
        usecols=None,
    )

    # Seleciona apenas as colunas de interesse pelo índice posicional
    col_indices = list(FIXED_COLS.values())
    col_names   = list(FIXED_COLS.keys())

    # Garante que o número de colunas disponível é suficiente
    max_idx = max(col_indices)
    if raw.shape[1] <= max_idx:
        raise ValueError(
            f"A aba '{sheet_name}' tem apenas {raw.shape[1]} colunas, "
            f"mas esperamos pelo menos {max_idx + 1}."
        )

    df = raw.iloc[:, col_indices].copy()
    df.columns = col_names

    # Remove linhas sem nome de OAE
    df = df[df["nome"].notna() & (df["nome"].astype(str).str.strip() != "")]
    df["nome"] = df["nome"].astype(str).str.strip()

    # Converte tipos
    df["latitude"]  = df["latitude"].apply(_safe_numeric)
    df["longitude"] = df["longitude"].apply(_safe_numeric)
    df["ano"]       = pd.to_numeric(df["ano"], errors="coerce").astype("Int64")

    # Normaliza RAAE para uniformizar capitalização
    df["raae"] = df["raae"].astype(str).str.strip()

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# LEITURA DA ABA "INSPEÇÃO ROTINEIRA"
# ---------------------------------------------------------------------------

def load_rotineira_data(xl: pd.ExcelFile, sheet_name: str = "Inspeção Rotineira") -> pd.DataFrame:
    """
    Lê a aba de inspeção rotineira.
    Por causa do cabeçalho multi-linha no Excel, usamos header=None e
    identificamos as colunas pelos índices posicionais configurados acima.
    """
    raw = xl.parse(sheet_name, header=None)

    # A primeira linha com dados reais costuma estar na linha 4 (índice 3)
    # Buscamos a linha onde a coluna C começa a ter 'OAE'
    data_start = 0
    for i, val in enumerate(raw.iloc[:, ROTINEIRA_NAME_COL]):
        if isinstance(val, str) and val.strip().startswith("OAE"):
            data_start = i
            break

    df_raw = raw.iloc[data_start:].copy()
    df_raw = df_raw.reset_index(drop=True)

    # Extrai o nome da OAE
    rows = []
    for _, row in df_raw.iterrows():
        nome = str(row.iloc[ROTINEIRA_NAME_COL]).strip() if not _is_blank(row.iloc[ROTINEIRA_NAME_COL]) else None
        if not nome or not nome.startswith("OAE"):
            continue

        record = {"nome": nome}

        # Extrai patologia (coluna AK)
        if ROTINEIRA_PATOLOGIA_COL < len(row):
            record["patologia"] = str(row.iloc[ROTINEIRA_PATOLOGIA_COL]).strip() if not _is_blank(row.iloc[ROTINEIRA_PATOLOGIA_COL]) else ""
        else:
            record["patologia"] = ""

        # Extrai dados por ano
        for year, cols in ROTINEIRA_YEAR_BLOCKS.items():
            for field in ["data", "geral", "E", "D", "F", "obs"]:
                col_idx = cols[field]
                val = row.iloc[col_idx] if col_idx < len(row) else np.nan
                record[f"{year}_{field}"] = val

        rows.append(record)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# LÓGICA DE FALLBACK: INSPEÇÃO MAIS RECENTE
# ---------------------------------------------------------------------------

def get_latest_inspection(df_rot: pd.DataFrame) -> pd.DataFrame:
    """
    Para cada OAE, aplica a lógica de fallback para encontrar a inspeção mais
    recente com dados válidos entre 2025 e 2022.

    Retorna um DataFrame com as colunas:
        nome, insp_ano, insp_data, insp_geral, insp_E, insp_D, insp_F,
        insp_obs, patologia, sem_inspecao (bool)
    """
    anos_ordem = [2025, 2024, 2023, 2022, 2021]
    results = []

    for _, row in df_rot.iterrows():
        found = False
        for year in anos_ordem:
            geral = row.get(f"{year}_geral", np.nan)
            E     = row.get(f"{year}_E",     np.nan)
            D     = row.get(f"{year}_D",     np.nan)
            F     = row.get(f"{year}_F",     np.nan)

            # Considera o ano válido se pelo menos a nota geral não for nula
            if not _is_blank(geral):
                results.append({
                    "nome":          row["nome"],
                    "insp_ano":      year,
                    "insp_data":     row.get(f"{year}_data", ""),
                    "insp_geral":    _safe_numeric(geral),
                    "insp_E":        _safe_numeric(E),
                    "insp_D":        _safe_numeric(D),
                    "insp_F":        _safe_numeric(F),
                    "insp_obs":      str(row.get(f"{year}_obs", "")).strip(),
                    "patologia":     str(row.get("patologia", "")).strip(),
                    "sem_inspecao":  False,
                })
                found = True
                break

        # Nenhum dado encontrado no período → S.I.
        if not found:
            results.append({
                "nome":         row["nome"],
                "insp_ano":     None,
                "insp_data":    "S.I.",
                "insp_geral":   "S.I.",
                "insp_E":       "S.I.",
                "insp_D":       "S.I.",
                "insp_F":       "S.I.",
                "insp_obs":     "",
                "patologia":    str(row.get("patologia", "")).strip(),
                "sem_inspecao": True,
            })

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# MERGE FINAL
# ---------------------------------------------------------------------------

def build_master_df(excel_path: str | Path) -> pd.DataFrame:
    """
    Carrega o Excel, processa as duas abas e retorna o DataFrame consolidado.
    """
    xl = pd.ExcelFile(excel_path, engine="openpyxl")

    # Detecta nomes reais das abas (ignora maiúsculas/minúsculas e espaços extras)
    sheet_map = {s.strip().lower(): s for s in xl.sheet_names}

    fixed_sheet    = sheet_map.get("dados fixos",          xl.sheet_names[0])
    rotineira_sheet = sheet_map.get("inspeção rotineira",  xl.sheet_names[1] if len(xl.sheet_names) > 1 else None)

    df_fixed = load_fixed_data(xl, fixed_sheet)

    if rotineira_sheet:
        df_rot   = load_rotineira_data(xl, rotineira_sheet)
        df_insp  = get_latest_inspection(df_rot)
        df_master = df_fixed.merge(df_insp, on="nome", how="left")
    else:
        df_master = df_fixed.copy()
        for col in ["insp_ano","insp_data","insp_geral","insp_E","insp_D","insp_F","insp_obs","patologia","sem_inspecao"]:
            df_master[col] = "S.I." if col in ("insp_geral","insp_E","insp_D","insp_F","insp_data") else None

    # OAEs sem correspondência na aba de inspeção também ficam S.I.
    df_master["sem_inspecao"] = df_master["sem_inspecao"].fillna(True)
    for col in ["insp_geral","insp_E","insp_D","insp_F"]:
        df_master[col] = df_master[col].where(df_master[col].notna(), other="S.I.")

    return df_master
