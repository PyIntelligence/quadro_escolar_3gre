import re
import unicodedata

def normalizar_texto(texto):
    """
    Remove acentos, caracteres especiais e converte o texto para maiúsculas.
    """
    if not texto:
        return ""
    texto = unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('utf-8')
    return re.sub(r'\s+', ' ', texto).strip().upper()

def limpar_float(valor, padrao=0.0):
    """
    Converte strings formatadas com vírgulas ou pontos para float seguro.
    """
    if valor is None:
        return padrao
    try:
        if isinstance(valor, str):
            valor = valor.replace(',', '.').strip()
        return float(valor)
    except (ValueError, TypeError):
        return padrao

def obter_peso_diretoria(cargo):
    """
    Retorna a ordem de prioridade/peso para ordenação do corpo diretivo.
    """
    cargo_norm = normalizar_texto(cargo)
    pesos = {
        'DIRETOR': 1,
        'VICE-DIRETOR': 2,
        'VICE DIRETOR': 2,
        'COORDENADOR PEDAGOGICO': 3,
        'COORDENADOR': 3,
        'ORIENTADOR EDUCACIONAL': 4,
        'SECRETARIO': 5,
        'SECRETARIO ESCOLAR': 5
    }
    return pesos.get(cargo_norm, 99)

def encontrar_lista_oculta(obj, profundidade=0):
    """
    Percorre a árvore do JSON da API do SIAGE para localizar a lista de dados
    independentemente de variações no nó raiz ('data', 'rows', 'content', etc).
    """
    if profundidade > 6:
        return []
    if isinstance(obj, list):
        if len(obj) > 0 and isinstance(obj[0], dict):
            return obj
        return []
    if isinstance(obj, dict):
        chaves_alvo = ['data', 'salas', 'itens', 'result', 'lista', 'rows', 'content', 'turmas']
        for k in chaves_alvo:
            if k in obj and isinstance(obj[k], list):
                lista = obj[k]
                if len(lista) > 0 and isinstance(lista[0], dict):
                    return lista
                elif len(lista) == 0:
                    return []
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                res = encontrar_lista_oculta(v, profundidade + 1)
                if res:
                    return res
    return []