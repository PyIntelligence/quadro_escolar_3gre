# -*- coding: utf-8 -*-
## Funções utilitárias para dar mais robustez à automação.
import time
import logging
from io import StringIO
import pandas as pd
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from selenium.webdriver.support import expected_conditions as EC

# Configuração básica de log para exibir mensagens formatadas no terminal.
# No futuro, você pode apontar isso para um arquivo de texto (ex: filename="automacao.log")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')

def clicar_elemento_resiliente(navegador: WebDriver, wait: WebDriverWait, by: str, value: str, attempts: int = 5) -> bool:
    """
    Tenta clicar em um elemento de forma resiliente, com retries em caso de
    StaleElementReferenceException e TimeoutException.

    Args:
        navegador: Objeto do driver Selenium.
        wait: Objeto WebDriverWait para esperas explícitas.
        by: O seletor (ex: By.XPATH).
        value: O valor do seletor.
        attempts: Número de tentativas de clique.

    Returns:
        True se o clique foi bem-sucedido, False caso contrário.
    """
    for attempt in range(attempts):
        try:
            element = wait.until(EC.element_to_be_clickable((by, value)))
            element.click()
            logging.info(f"✅ Elemento '{value}' clicado com sucesso na tentativa {attempt + 1}.")
            return True
        except StaleElementReferenceException:
            logging.warning(f"🔄 Tentativa {attempt + 1}/{attempts}: Elemento se tornou obsoleto. Tentando novamente...")
            time.sleep(1)
        except TimeoutException:
            logging.error(f"❌ Tentativa {attempt + 1}/{attempts}: Elemento '{value}' não foi encontrado a tempo.")
            return False
        except Exception as e:
            logging.error(f"❌ Erro inesperado ao tentar clicar em '{value}': {e}")
            return False
            
    return False

def extrair_dados_tabela_por_xpath(navegador: WebDriver, wait: WebDriverWait, xpath: str) -> pd.DataFrame:
    """
    Extrai dados de uma tabela HTML e retorna um DataFrame do pandas.
    """
    try:
        # Espera a tabela estar presente na estrutura da página
        tabela = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        
        # Extrai o HTML bruto da tabela
        html_tabela = tabela.get_attribute('outerHTML')
        
        # O uso do StringIO evita FutureWarnings em versões mais recentes do Pandas
        df = pd.read_html(StringIO(html_tabela))[0]
        
        return df

    except TimeoutException:
        logging.error(f"❌ Tabela não encontrada no XPATH: {xpath}")
        return pd.DataFrame() # Retorna DataFrame vazio em caso de erro
        
    except ValueError as e:
        # Captura erros específicos do Pandas, como a ausência de tabelas válidas
        if "No tables found" in str(e): 
            logging.warning("⚠️ Nenhuma tabela de dados encontrada no HTML extraído.")
        else:
            logging.error(f"❌ Erro de valor ao extrair dados da tabela no XPATH {xpath}: {e}")
        return pd.DataFrame()
        
    except Exception as e:
        logging.error(f"❌ Erro inesperado ao extrair dados da tabela no XPATH {xpath}: {e}")
        return pd.DataFrame()