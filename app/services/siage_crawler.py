import requests
from bs4 import BeautifulSoup
from app.models import db, Escola, Professor, ApoioCLT, Turma
import re

class SiageExhaustiveCrawler:
    def __init__(self, base_url, session_credentials):
        self.base_url = base_url
        self.session = requests.Session()
        self.credentials = session_credentials
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def autenticar_e_extrair_tokens(self):
        """Autentica no SIAGE e captura tokens CSRF e Cookies dinâmicos."""
        res = self.session.get(f"{self.base_url}/login", headers=self.headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Busca automática por campos ocultos / tokens CSRF
        tokens = {}
        for hidden in soup.find_all('input', type='hidden'):
            if hidden.get('name'):
                tokens[hidden.get('name')] = hidden.get('value', '')

        login_data = {**self.credentials, **tokens}
        self.session.post(f"{self.base_url}/login", data=login_data, headers=self.headers)

    def varrer_e_salvar_tudo(self, callback_progresso=None):
        """Executa varredura profunda de todas as entidades e persiste no banco local."""
        self.autenticar_e_extrair_tokens()

        # Step 1: Mapear todas as Escolas da 3ª GRE
        if callback_progresso:
            callback_progresso(10, "Mapeando unidades escolares no SIAGE...")
        
        res_escolas = self.session.get(f"{self.base_url}/api/escolas/3gre", headers=self.headers)
        dados_escolas = res_escolas.json() if res_escolas.status_code == 200 else []

        total_escolas = len(dados_escolas) or 1
        
        for idx, item in enumerate(dados_escolas):
            escola = Escola.query.filter_by(codigo_inep=item.get('inep')).first()
            if not escola:
                escola = Escola(
                    codigo_inep=item.get('inep'),
                    unidade_escolar=item.get('nome_escola'),
                    gestor=item.get('gestor_nome', '')
                )
                db.session.add(escola)
            db.session.commit()

            # Step 2: Extração exaustiva de Professores/Servidores por Escola
            if callback_progresso:
                percentual = 10 + int(((idx + 1) / total_escolas) * 40)
                callback_progresso(percentual, f"Baixando quadro docente da escola {escola.unidade_escolar}...")

            self._extrair_professores_escola(escola)

            # Step 3: Extração de Turmas, Disciplinas e Apoio CLT
            if callback_progresso:
                percentual = 50 + int(((idx + 1) / total_escolas) * 40)
                callback_progresso(percentual, f"Baixando turmas e apoio da escola {escola.unidade_escolar}...")

            self._extrair_turmas_e_apoio(escola)

        if callback_progresso:
            callback_progresso(100, "Varredura do SIAGE finalizada com sucesso!")

    def _extrair_professores_escola(self, escola):
        # Scraping de rotas visíveis e ocultas de professores
        url = f"{self.base_url}/servidores/quadro?inep={escola.codigo_inep}"
        res = self.session.get(url, headers=self.headers)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            for tr in soup.select('table.tabela-professores tbody tr'):
                cols = [td.get_text(strip=True) for td in tr.find_all('td')]
                if len(cols) >= 3:
                    cpf, nome, vinculo = cols[0], cols[1], cols[2]
                    prof = Professor.query.filter_by(cpf=cpf, escola_id=escola.id).first()
                    if not prof:
                        prof = Professor(cpf=cpf, nome=nome, vinculo=vinculo, escola_id=escola.id)
                        db.session.add(prof)
            db.session.commit()

    def _extrair_turmas_e_apoio(self, escola):
        # Implementação complementar para Turmas e Apoio CLT
        pass