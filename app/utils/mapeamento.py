# app/utils/mapeamento.py

# Dicionário que traduz sinônimos das planilhas para as colunas oficiais do Banco
MAPA_COLUNAS_PROFESSOR = {
    'NOME': 'nome',
    'NOME COMPLETO': 'nome',
    'PROFESSOR': 'nome',
    'NOME DO PROFESSOR': 'nome',
    'SERVIDOR': 'nome',
    
    'CPF': 'cpf',
    'NUMERO CPF': 'cpf',
    
    'MATRICULA': 'matricula',
    'MATRÍCULA': 'matricula',
    'MAT': 'matricula',
    
    'DISCIPLINA': 'componente_curricular',
    'COMPONENTE CURRICULAR': 'componente_curricular',
    'MATERIA': 'componente_curricular',
    'MATÉRIA': 'componente_curricular',
    
    'CARGA HORARIA': 'carga_horaria',
    'CARGA HORÁRIA': 'carga_horaria',
    'CH': 'carga_horaria',
    'CH ALOCADA': 'carga_horaria',
    
    'EMAIL': 'email',
    'E-MAIL': 'email',
    
    'TELEFONE': 'telefone',
    'CELULAR': 'telefone',
    'CONTATO': 'telefone',
    
    'VINCULO': 'vinculo',
    'VÍNCULO': 'vinculo',
    'TIPO DE VÍNCULO': 'vinculo',
    'SITUAÇÃO': 'situacao',
    'SITUACAO': 'situacao'
}

def normalizar_coluna(coluna_str):
    """Remove acentos e espaços extras para buscar no dicionário de mapeamento."""
    if not coluna_str:
        return ""
    txt = str(coluna_str).strip().upper()
    return MAPA_COLUNAS_PROFESSOR.get(txt, txt.lower().replace(' ', '_'))