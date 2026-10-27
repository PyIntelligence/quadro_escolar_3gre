# app/services/google_sheets_sync.py

import pandas as pd
from app.extensions import db
from app.models.escola import EscolaGestao
from app.models.professor import Professor
from app.utils.smart_merge import preencher_campo_se_vazio

# Mapeamento flexível de cabeçalhos das planilhas da 3ª GRE
MAPA_COLUNAS_SHEETS = {
    'inep': ['INEP', 'CODIGO INEP', 'CÓDIGO INEP', 'COD_INEP'],
    'escola': ['ESCOLA', 'NOME ESCOLA', 'UNIDADE ESCOLAR'],
    'gestor': ['GESTOR', 'DIRETOR', 'NOME GESTOR'],
    'secretario': ['SECRETARIO', 'SECRETÁRIO', 'NOME SECRETARIO'],
    'mat_secretario': ['MATRICULA SECRETARIO', 'MAT_SECRETARIO'],
    'tel_secretario': ['TELEFONE SECRETARIO', 'TEL_SECRETARIO'],
    'coord1': ['COORDENADOR 1', 'COORD_1', 'COORDENADOR PEDAGOGICO 1'],
    'mat_coord1': ['MATRICULA COORD 1', 'MAT_COORD_1'],
    'tel_coord1': ['TELEFONE COORD 1', 'TEL_COORD_1'],
    'caf': ['CAF', 'NOME CAF', 'ASSESSOR FINANCEIRO'],
    'rpp': ['RPP', 'NOME RPP', 'COORDENADOR RPP'],
    'lideres': ['LIDERES DE TURMA', 'LIDERES_TURMA'],
    'gremio': ['GREMIO ESTUDANTIL', 'GREMIO'],
    'eja': ['OFERTA EJA', 'EJA']
}

def localizar_coluna(df, chaves):
    for chave in chaves:
        for col in df.columns:
            if str(col).strip().upper() == chave:
                return col
    return None

def sincronizar_via_google_sheets(url_ou_id_sheet, callback_progresso=None):
    """
    Importa dados de uma planilha pública ou compartilhada do Google Sheets
    e preenche os dados ausentes sem apagar os existentes.
    """
    # Converte link normal do Google Sheets em link direto de exportação CSV
    if 'docs.google.com/spreadsheets' in url_ou_id_sheet:
        sheet_id = url_ou_id_sheet.split('/d/')[1].split('/')[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    else:
        csv_url = url_ou_id_sheet

    if callback_progresso:
        callback_progresso(10, "Baixando dados da planilha do Google Sheets...")

    try:
        df = pd.read_csv(csv_url, dtype=str)
    except Exception as e:
        return False, f"Falha ao ler Google Sheets: {e}"

    col_inep = localizar_coluna(df, MAPA_COLUNAS_SHEETS['inep'])
    if not col_inep:
        return False, "Coluna 'INEP' não encontrada no Google Sheets."

    total = len(df)
    atualizados = 0

    for idx, row in df.iterrows():
        inep = str(row[col_inep]).strip()
        if not inep or inep.upper() in ['NAN', 'NONE']:
            continue

        escola = EscolaGestao.query.filter_by(codigo_inep=inep).first()
        if not escola:
            col_nome = localizar_coluna(df, MAPA_COLUNAS_SHEETS['escola'])
            nome = str(row[col_nome]).strip().upper() if col_nome and pd.notna(row[col_nome]) else "ESCOLA IMPORTADA"
            escola = EscolaGestao(codigo_inep=inep, unidade_escolar=nome, gre="3ª GRE")
            db.session.add(escola)
            db.session.flush()

        # Mapeamento incremental de todos os campos
        campos_mapa = [
            ('gestor', 'gestor'),
            ('secretario', 'nome_secretario'),
            ('mat_secretario', 'matricula_secretario'),
            ('tel_secretario', 'telefone_secretario'),
            ('coord1', 'coord_ped_1_nome'),
            ('mat_coord1', 'coord_ped_1_mat'),
            ('tel_coord1', 'coord_ped_1_tel'),
            ('caf', 'nome_caf'),
            ('rpp', 'nome_rpp'),
            ('lideres', 'lideres_turma'),
            ('gremio', 'gremio_estudantil'),
            ('eja', 'oferta_eja')
        ]

        modificado = False
        for chave_sheet, campo_model in campos_mapa:
            col = localizar_coluna(df, MAPA_COLUNAS_SHEETS[chave_sheet])
            if col and pd.notna(row[col]):
                modificado |= preencher_campo_se_vazio(escola, campo_model, str(row[col]).strip().upper())

        if modificado:
            atualizados += 1

        if callback_progresso:
            pct = 10 + int(((idx + 1) / total) * 85)
            callback_progresso(pct, f"Processando Google Sheets ({idx+1}/{total})...")

    try:
        db.session.commit()
        if callback_progresso:
            callback_progresso(100, "Google Sheets processado com sucesso!")
        return True, f"Total de escolas atualizadas via Google Sheets: {atualizados}"
    except Exception as e:
        db.session.rollback()
        return False, f"Erro ao salvar dados do Google Sheets: {e}"