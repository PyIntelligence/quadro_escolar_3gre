import os
import pandas as pd
from app.extensions import db
from app.models.escola import EscolaGestao
from app.models.professor import Professor
from app.models.atuacao import Atuacao
from app.utils.helpers import limpar_float

# Mapeamento de colunas para tratar variações de nomes do relatório do SIAGE
ALIAS_COLUNAS = {
    'inep': ['INEP', 'CODIGO INEP', 'CÓDIGO INEP', 'COD_INEP', 'CODIGO_INEP'],
    'escola': ['ESCOLA', 'UNIDADE ESCOLAR', 'NOME DA ESCOLA', 'ESCOLA_NOME', 'UNIDADE_ESCOLAR'],
    'municipio': ['MUNICIPIO', 'MUNICÍPIO', 'CIDADE'],
    'matricula': ['MATRICULA', 'MATRÍCULA', 'MAT_PROF', 'MATRICULA_DOCENTE'],
    'cpf': ['CPF', 'CPF_DOCENTE', 'CPF_PROFESSOR'],
    'nome': ['NOME', 'NOME DO PROFESSOR', 'NOME_DOCENTE', 'PROFESSOR', 'DOCENTE'],
    'ch_original': ['CH', 'CARGA HORÁRIA', 'CARGA_HORARIA', 'CH_ORIGINAL', 'JORNADA'],
    'componente': ['DISCIPLINA', 'COMPONENTE', 'COMPONENTE CURRICULAR', 'COMPONENTE_CURRICULAR'],
    'turmas': ['TURMA', 'TURMAS', 'TURMAS_ATENDIDAS', 'SERIE'],
    'turno': ['TURNO', 'TURNO_FUNCIONAMENTO']
}

def identificar_coluna(df, chaves_busca):
    """Localiza o nome real da coluna no arquivo independente da variação do SIAGE."""
    for chave in chaves_busca:
        for col_real in df.columns:
            if str(col_real).strip().upper() == chave:
                return col_real
    return None

def carregar_dados_siage(caminho_arquivo):
    """
    Processa um arquivo Excel ou CSV exportado do SIAGE e salva/atualiza
    os registros de Escolas, Professores e Atuações no banco de dados.
    """
    if not os.path.exists(caminho_arquivo):
        msg = f"[ERRO] Arquivo não encontrado: {caminho_arquivo}"
        print(msg)
        return False, msg

    print(f"📂 [IMPORTAÇÃO] Lendo arquivo: {caminho_arquivo}...")

    try:
        if caminho_arquivo.endswith('.csv'):
            df = pd.read_csv(caminho_arquivo, dtype=str)
        else:
            df = pd.read_excel(caminho_arquivo, dtype=str)
    except Exception as e:
        msg = f"[ERRO] Falha na leitura da planilha: {e}"
        print(msg)
        return False, msg

    # Identificação flexível das colunas presentes
    col_inep = identificar_coluna(df, ALIAS_COLUNAS['inep'])
    col_escola = identificar_coluna(df, ALIAS_COLUNAS['escola'])
    col_municipio = identificar_coluna(df, ALIAS_COLUNAS['municipio'])
    col_mat = identificar_coluna(df, ALIAS_COLUNAS['matricula'])
    col_cpf = identificar_coluna(df, ALIAS_COLUNAS['cpf'])
    col_nome = identificar_coluna(df, ALIAS_COLUNAS['nome'])
    col_ch = identificar_coluna(df, ALIAS_COLUNAS['ch_original'])
    col_comp = identificar_coluna(df, ALIAS_COLUNAS['componente'])
    col_turmas = identificar_coluna(df, ALIAS_COLUNAS['turmas'])
    col_turno = identificar_coluna(df, ALIAS_COLUNAS['turno'])

    if not col_mat or not col_nome:
        msg = "[ERRO] Não foi possível identificar as colunas obrigatórias 'MATRÍCULA' e 'NOME' na planilha."
        print(msg)
        return False, msg

    total_escolas = 0
    total_professores = 0
    total_atuacoes = 0

    for _, row in df.iterrows():
        # 1. TRATAMENTO DA ESCOLA
        val_inep = str(row[col_inep]).strip() if col_inep and pd.notna(row[col_inep]) else '25000000'
        val_escola = str(row[col_escola]).strip().upper() if col_escola and pd.notna(row[col_escola]) else 'ESCOLA NÃO INFORMADA'
        val_muni = str(row[col_municipio]).strip().upper() if col_municipio and pd.notna(row[col_municipio]) else 'MUNICÍPIO MODELO'

        escola = EscolaGestao.query.filter_by(codigo_inep=val_inep).first()
        if not escola:
            escola = EscolaGestao(
                codigo_inep=val_inep,
                unidade_escolar=val_escola,
                municipio=val_muni
            )
            db.session.add(escola)
            db.session.flush()
            total_escolas += 1

        # 2. TRATAMENTO DO PROFESSOR
        val_mat = str(row[col_mat]).strip()
        val_nome = str(row[col_nome]).strip().upper()
        val_cpf = str(row[col_cpf]).strip() if col_cpf and pd.notna(row[col_cpf]) else ''
        val_ch = limpar_float(row[col_ch] if col_ch and pd.notna(row[col_ch]) else 40.0, padrao=40.0)

        prof = Professor.query.filter_by(escola_id=escola.id, matricula=val_mat).first()
        if not prof:
            prof = Professor(
                escola_id=escola.id,
                matricula=val_mat,
                nome=val_nome,
                cpf=val_cpf,
                carga_horaria_original=val_ch,
                carga_horaria_autorizada=val_ch
            )
            db.session.add(prof)
            db.session.flush()
            total_professores += 1

        # 3. TRATAMENTO DA ATUAÇÃO / COMPONENTE
        if col_comp and pd.notna(row[col_comp]):
            val_comp = str(row[col_comp]).strip().upper()
            val_turmas = str(row[col_turmas]).strip().upper() if col_turmas and pd.notna(row[col_turmas]) else ''
            val_turno = str(row[col_turno]).strip().upper() if col_turno and pd.notna(row[col_turno]) else ''

            atuacao_existente = Atuacao.query.filter_by(
                professor_id=prof.id,
                componente_curricular=val_comp
            ).first()

            if not atuacao_existente:
                nova_atuacao = Atuacao(
                    escola_id=escola.id,
                    professor_id=prof.id,
                    componente_curricular=val_comp,
                    turmas_atendidas=val_turmas,
                    turno=val_turno,
                    ch_semanal=0.0
                )
                db.session.add(nova_atuacao)
                total_atuacoes += 1

    try:
        db.session.commit()
        resumo = {
            "escolas_criadas": total_escolas,
            "professores_importados": total_professores,
            "atuacoes_vinculadas": total_atuacoes
        }
        print("\n=== RESUMO DA CARGA SIAGE ===")
        print(f"Escolas criadas: {total_escolas}")
        print(f"Professores importados: {total_professores}")
        print(f"Atuações vinculadas: {total_atuacoes}")
        return True, resumo
    except Exception as e:
        db.session.rollback()
        msg = f"❌ Erro ao salvar dados no banco: {e}"
        print(msg)
        return False, msg