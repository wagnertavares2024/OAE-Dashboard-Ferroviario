"""
column_detector.py
Detecta automaticamente as posições das colunas nas abas do Excel,
usando os rótulos do cabeçalho como ponto de partida.
Se os rótulos não forem encontrados, usa os índices posicionais como fallback.
"""

import re
import pandas as pd
import numpy as np


def find_header_row(raw: pd.DataFrame, search_col: int, keyword: str, max_rows: int = 10) -> int:
    """Retorna o índice da primeira linha que contém `keyword` na coluna `search_col`."""
    for i in range(min(max_rows, len(raw))):
        val = str(raw.iloc[i, search_col] if search_col < raw.shape[1] else "")
        if keyword.lower() in val.lower():
            return i
    return 0


def detect_year_blocks(raw: pd.DataFrame, header_row: int) -> dict:
    """
    Varre o cabeçalho multi-linha da aba de inspeção e retorna um dicionário
    mapeando cada ano aos índices posicionais de suas colunas.

    Retorna:
        { 2025: {data, geral, E, D, F, obs}, 2024: {...}, ... }
    """
    # Linha com os anos (costuma ter '2025', '2024', etc.)
    year_row_idx   = max(0, header_row - 2)
    subfield_row_idx = header_row - 1 if header_row > 0 else 0

    year_row    = raw.iloc[year_row_idx]   if year_row_idx < len(raw)    else pd.Series()
    subfield_row = raw.iloc[subfield_row_idx] if subfield_row_idx < len(raw) else pd.Series()
    field_row    = raw.iloc[header_row]    if header_row < len(raw)      else pd.Series()

    blocks: dict[int, dict] = {}
    current_year = None

    for col_i in range(len(year_row)):
        y_val = str(year_row.iloc[col_i]).strip() if col_i < len(year_row) else ""
        # Detecta ano (4 dígitos 20xx)
        m = re.fullmatch(r"(20\d{2})", y_val)
        if m:
            current_year = int(m.group(1))
            blocks[current_year] = {"data": col_i, "geral": col_i, "E": -1, "D": -1, "F": -1, "obs": -1}

        if current_year is None:
            continue

        # Detecta sub-campos dentro do bloco do ano
        sf = str(subfield_row.iloc[col_i] if col_i < len(subfield_row) else "").strip().upper()
        ff = str(field_row.iloc[col_i]    if col_i < len(field_row)    else "").strip().upper()

        label = sf or ff
        if re.search(r"\bE\b|ESTRUTURAL", label):
            blocks[current_year]["E"] = col_i
        elif re.search(r"\bD\b|DURABILIDADE", label):
            blocks[current_year]["D"] = col_i
        elif re.search(r"\bF\b|FUNCIONAL", label):
            blocks[current_year]["F"] = col_i
        elif re.search(r"OBS|OBSERV", label):
            blocks[current_year]["obs"] = col_i
        elif re.search(r"DATA|DAT", label):
            blocks[current_year]["data"] = col_i
        elif re.search(r"GERAL|ABN|CONDI", label):
            blocks[current_year]["geral"] = col_i

    return {yr: blk for yr, blk in blocks.items() if yr >= 2021}


def detect_patologia_col(raw: pd.DataFrame, header_row: int) -> int:
    """Retorna o índice da coluna 'Manifestação Patológica' ou AK (~36)."""
    if header_row < len(raw):
        header = raw.iloc[header_row]
        for i, val in enumerate(header):
            if "patol" in str(val).lower() or "manifest" in str(val).lower():
                return i
    # fallback: coluna AK = índice 36
    return 36
