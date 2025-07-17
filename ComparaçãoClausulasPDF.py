import streamlit as st
import pandas as pd
import PyPDF2
import re
import time
import openai
from io import BytesIO
import traceback
import logging
import sys
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('debug_processor.log')
    ]
)

logger = logging.getLogger(__name__)

def set_page_config():
    """Configuração da página com cores da CSN"""
    logger.info("Iniciando configuração da página")
    
    try:
        st.set_page_config(
            page_title="Processador de Cláusulas - CSN GÁS NATURAL",
            page_icon="📄",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        logger.info("Configuração da página concluída com sucesso")
    except Exception as e:
        logger.error(f"Erro na configuração da página: {str(e)}")
        logger.error(traceback.format_exc())
    
    # CSS customizado com cores da CSN
    logger.debug("Aplicando CSS customizado")
    st.markdown("""
    <style>
    .main {
        padding-top: 2rem;
    }
    
    .stApp > header {
        background-color: transparent;
    }
    
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* Header principal */
    .main-header {
        background: linear-gradient(90deg, #00529C 0%, #1e6bb8 100%);
        padding: 1.5rem 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .logo-container {
        display: flex;
        align-items: center;
        gap: 20px;
    }
    
    .logo-img {
        height: 80px;
        width: auto;
        background-color: white;
        padding: 10px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    .header-text h1 {
        color: white;
        font-size: 2.2rem;
        font-weight: 700;
        margin: 0;
    }
    
    .header-text p {
        color: #e8f4fd;
        font-size: 1.1rem;
        margin: 0.5rem 0 0 0;
    }
    
    .header-text small {
        font-size: 0.9rem;
        color: #d1ecf1;
    }
    
    /* Botões */
    .stButton > button {
        background-color: #00529C;
        color: white;
        border: none;
        border-radius: 5px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: background-color 0.3s;
    }
    
    .stButton > button:hover {
        background-color: #1e6bb8;
    }
    
    /* Sidebar */
    .css-1d391kg {
        background-color: #f8f9fa;
    }
    
    /* Upload area */
    .uploadedFile {
        border: 2px dashed #00529C;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        background-color: white;
    }
    
    /* Success/Info messages */
    .stSuccess {
        background-color: #d4edda;
        border-color: #c3e6cb;
        color: #155724;
    }
    
    .stInfo {
        background-color: #d1ecf1;
        border-color: #bee5eb;
        color: #0c5460;
    }
    
    /* Dataframe */
    .stDataFrame {
        border: 1px solid #dee2e6;
        border-radius: 5px;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Responsivo */
    @media (max-width: 768px) {
        .logo-container {
            flex-direction: column;
            text-align: center;
        }
        
        .header-text h1 {
            font-size: 1.8rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    logger.debug("CSS aplicado com sucesso")

def extract_text_from_pdf(pdf_file):
    """Extrai texto do PDF com melhor tratamento de quebras de linha"""
    logger.info(f"Iniciando extração de texto do PDF: {pdf_file.name}")
    
    try:
        # Reset do ponteiro do arquivo
        pdf_file.seek(0)
        logger.debug("Ponteiro do arquivo resetado")
        
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        total_pages = len(pdf_reader.pages)
        logger.info(f"PDF carregado com sucesso. Total de páginas: {total_pages}")
        
        text = ""
        
        # Começar da página 4 (índice 3) para pular sumário e páginas iniciais
        start_page = min(3, total_pages - 1)
        logger.info(f"Iniciando extração da página {start_page + 1} até {total_pages}")
        
        for page_num in range(start_page, total_pages):
            logger.debug(f"Processando página {page_num + 1}/{total_pages}")
            
            try:
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                
                if page_text:
                    original_length = len(page_text)
                    logger.debug(f"Página {page_num + 1}: {original_length} caracteres extraídos")
                    
                    # Tratar quebras de linha e hifenização
                    page_text = fix_text_breaks(page_text)
                    processed_length = len(page_text)
                    logger.debug(f"Página {page_num + 1}: {processed_length} caracteres após processamento")
                    
                    text += page_text + "\n"
                else:
                    logger.warning(f"Página {page_num + 1} está vazia ou não foi possível extrair texto")
                    
            except Exception as e:
                logger.error(f"Erro ao processar página {page_num + 1}: {str(e)}")
                logger.error(traceback.format_exc())
                continue
        
        total_text_length = len(text)
        logger.info(f"Extração concluída. Total de caracteres: {total_text_length}")
        
        if total_text_length < 100:
            logger.warning("Texto extraído muito curto, pode indicar problema na extração")
        
        # Salvar uma amostra do texto extraído para debug
        logger.debug(f"Primeiros 500 caracteres do texto extraído: {text[:500]}")
        
        return text
        
    except Exception as e:
        logger.error(f"Erro crítico ao extrair texto do PDF: {str(e)}")
        logger.error(traceback.format_exc())
        st.error(f"Erro ao extrair texto do PDF: {str(e)}")
        return None

def fix_text_breaks(text):
    """Corrige quebras de linha e reconstitui palavras quebradas"""
    logger.debug("Iniciando correção de quebras de texto")
    
    original_length = len(text)
    
    # Corrigir palavras quebradas por hífen no final da linha
    text = re.sub(r'-\s*\n\s*', '', text)
    logger.debug(f"Correção de hífen: {original_length} -> {len(text)} caracteres")
    
    # Corrigir quebras de linha no meio de frases
    text = re.sub(r'([a-z,;])\n([a-z])', r'\1 \2', text)
    logger.debug(f"Correção de quebras de linha: {len(text)} caracteres")
    
    # Normalizar múltiplas quebras de linha para apenas uma
    text = re.sub(r'\n{2,}', '\n', text)
    logger.debug(f"Normalização de quebras múltiplas: {len(text)} caracteres")
    
    # Corrigir espaços múltiplos
    text = re.sub(r' {2,}', ' ', text)
    final_length = len(text)
    logger.debug(f"Correção de espaços múltiplos: {final_length} caracteres")
    
    logger.debug(f"Correção de texto concluída: {original_length} -> {final_length} caracteres")
    
    return text

def identify_clauses(text):
    """Identifica e extrai cláusulas numeradas"""
    logger.info("Iniciando identificação de cláusulas")
    
    clauses = []
    
    # Padrão para identificar cláusulas numeradas
    pattern = re.compile(
        r"^(\d{1,2}(?:\.\d{1,2}){1,4}\.?)\s+([A-ZÁÉÍÓÚÇÃÔÊ])",
        re.MULTILINE
    )
    
    logger.debug(f"Padrão de busca: {pattern.pattern}")
    logger.debug(f"Texto a ser analisado tem {len(text)} caracteres")
    
    matches = list(pattern.finditer(text))
    logger.info(f"Encontradas {len(matches)} possíveis cláusulas")
    
    if not matches:
        logger.warning("Nenhuma cláusula encontrada com o padrão atual")
        # Tentar padrão alternativo
        alternative_pattern = re.compile(r"^(\d{1,2}\.?\d*)\s+([A-ZÁÉÍÓÚÇÃÔÊ])", re.MULTILINE)
        matches = list(alternative_pattern.finditer(text))
        logger.info(f"Padrão alternativo encontrou {len(matches)} cláusulas")
        
        if not matches:
            logger.error("Nenhuma cláusula encontrada com nenhum padrão")
            return []

    for i, match in enumerate(matches):
        logger.debug(f"Processando cláusula {i+1}/{len(matches)}")
        
        start_pos = match.start()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        
        clause_block = text[start_pos:end_pos].strip()
        clause_number = match.group(1).strip()
        
        logger.debug(f"Cláusula {clause_number}: posição {start_pos}-{end_pos}")
        logger.debug(f"Bloco bruto tem {len(clause_block)} caracteres")
        
        # Remove o número da cláusula do início do conteúdo
        clause_content = clause_block
        clause_content = re.sub(rf'^{re.escape(clause_number)}\s*', '', clause_content).strip()
        
        logger.debug(f"Após remoção do número: {len(clause_content)} caracteres")
        
        # Remove qualquer padrão de cláusula que apareça no final do texto
        end_pattern = re.search(r'\s+(\d{1,2}(?:\.\d{1,2}){1,4}\.?)\s+([A-ZÁÉÍÓÚÇÃÔÊ].*?)$', clause_content, re.DOTALL)
        
        if end_pattern:
            clause_content = clause_content[:clause_content.rfind(end_pattern.group(0))].strip()
            logger.debug(f"Padrão de fim removido: {len(clause_content)} caracteres")
        
        # Substitui quebras de linha por espaços
        clause_content = clause_content.replace('\n', ' ').strip()
        
        # Remove espaços múltiplos
        clause_content = re.sub(r'\s+', ' ', clause_content).strip()
        
        # Remove fragmentos como "Página X de Y"
        clause_content = re.sub(r'\s*Página\s+\d+\s+de\s+\d+\s*', ' ', clause_content)
        clause_content = re.sub(r'\s+', ' ', clause_content).strip()
        
        logger.debug(f"Conteúdo final: {len(clause_content)} caracteres")
        
        if clause_content and len(clause_content) > 10:
            clauses.append({
                'numero': clause_number,
                'conteudo': clause_content
            })
            logger.debug(f"Cláusula {clause_number} adicionada com sucesso")
            logger.debug(f"Primeiros 100 caracteres: {clause_content[:100]}")
        else:
            logger.warning(f"Cláusula {clause_number} descartada (muito curta ou vazia)")

    logger.info(f"Identificação concluída: {len(clauses)} cláusulas válidas encontradas")
    return clauses

def generate_summary(clause_text, api_key):
    """Gera resumo da cláusula usando OpenAI GPT-4.1-nano"""
    logger.info("Iniciando geração de resumo")
    
    if not api_key:
        logger.warning("API key não fornecida")
        return ""
    
    try:
        logger.debug(f"Texto da cláusula tem {len(clause_text)} caracteres")
        
        client = openai.OpenAI(api_key=api_key)
        logger.debug("Cliente OpenAI inicializado")
        
        prompt = f"""Esta cláusula é parte de um contrato de transporte de gás natural. 
        Faça um resumo geral completo do conteúdo em um parágrafo, explicando do que trata esta cláusula:

        {clause_text}

        Resumo:"""
        
        logger.debug(f"Prompt criado com {len(prompt)} caracteres")
        
        start_time = time.time()
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.3
        )
        end_time = time.time()
        
        logger.info(f"Resposta da API recebida em {end_time - start_time:.2f} segundos")
        
        summary = response.choices[0].message.content.strip()
        logger.debug(f"Resumo gerado com {len(summary)} caracteres")
        logger.debug(f"Resumo: {summary[:100]}...")
        
        return summary
        
    except Exception as e:
        logger.error(f"Erro ao gerar resumo: {str(e)}")
        logger.error(traceback.format_exc())
        return f"Erro no resumo: {str(e)}"

def process_contract(pdf_file, api_key=None):
    """Processa o contrato completo"""
    logger.info("Iniciando processamento do contrato")
    
    start_time = time.time()
    
    # Extrair texto do PDF
    st.info("Extraindo texto do PDF...")
    logger.info("Fase 1: Extração de texto")
    text = extract_text_from_pdf(pdf_file)
    
    if not text:
        logger.error("Falha na extração de texto")
        return None
    
    extraction_time = time.time()
    logger.info(f"Extração concluída em {extraction_time - start_time:.2f} segundos")
    
    # Identificar cláusulas
    st.info("Identificando cláusulas numeradas...")
    logger.info("Fase 2: Identificação de cláusulas")
    clauses = identify_clauses(text)
    
    if not clauses:
        logger.error("Nenhuma cláusula identificada")
        st.warning("Nenhuma cláusula numerada foi encontrada no documento.")
        return None
    
    identification_time = time.time()
    logger.info(f"Identificação concluída em {identification_time - extraction_time:.2f} segundos")
    
    st.success(f"{len(clauses)} cláusulas numeradas encontradas!")
    
    # Processar cláusulas
    processed_clauses = []
    
    if api_key:
        logger.info("Fase 3: Geração de resumos com IA")
        st.info("Gerando resumos com IA...")
        progress_bar = st.progress(0)
        
        for i, clause in enumerate(clauses):
            logger.debug(f"Processando cláusula {i+1}/{len(clauses)}: {clause['numero']}")
            
            summary = generate_summary(clause['conteudo'], api_key)
            
            processed_clauses.append({
                'Clausula': clause['numero'],
                'Transcricao': clause['conteudo'],
                'Resumo': summary
            })
            
            progress = (i + 1) / len(clauses)
            progress_bar.progress(progress)
            logger.debug(f"Progresso: {progress:.1%}")
            
            time.sleep(0.2)
            
        progress_bar.empty()
        summary_time = time.time()
        logger.info(f"Resumos gerados em {summary_time - identification_time:.2f} segundos")
    else:
        logger.info("Fase 3: Processamento sem resumos")
        st.info("Processando sem resumos...")
        
        for i, clause in enumerate(clauses):
            logger.debug(f"Processando cláusula {i+1}/{len(clauses)}: {clause['numero']}")
            
            processed_clauses.append({
                'Clausula': clause['numero'],
                'Transcricao': clause['conteudo'],
                'Resumo': ''
            })
    
    end_time = time.time()
    total_time = end_time - start_time
    
    logger.info(f"Processamento concluído em {total_time:.2f} segundos")
    logger.info(f"Total de cláusulas processadas: {len(processed_clauses)}")
    
    return processed_clauses

def create_excel_file(processed_clauses):
    """Cria arquivo Excel com as cláusulas processadas"""
    logger.info("Iniciando criação do arquivo Excel")
    
    try:
        df = pd.DataFrame(processed_clauses)
        logger.debug(f"DataFrame criado com {len(df)} linhas e {len(df.columns)} colunas")
        
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            logger.debug("ExcelWriter inicializado")
            
            df.to_excel(writer, sheet_name='Clausulas', index=False)
            logger.debug("Dados escritos na planilha")
            
            workbook = writer.book
            worksheet = writer.sheets['Clausulas']
            
            # Formatação do cabeçalho
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#00529C',
                'font_color': 'white',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })
            
            # Formatação para quebra de texto
            wrap_format = workbook.add_format({
                'text_wrap': True, 
                'valign': 'top',
                'border': 1
            })
            
            # Formatação para a coluna de número da cláusula
            number_format = workbook.add_format({
                'align': 'center',
                'valign': 'vcenter',
                'border': 1,
                'bold': True
            })
            
            # Escrever cabeçalhos
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            logger.debug("Cabeçalhos formatados")
            
            # Configurar colunas
            max_clausula_len = max([len(str(row['Clausula'])) for row in processed_clauses]) + 2
            max_clausula_len = min(max_clausula_len, 20)
            
            worksheet.set_column('A:A', max_clausula_len, number_format)
            worksheet.set_column('B:B', 80, wrap_format)
            worksheet.set_column('C:C', 60, wrap_format)
            
            logger.debug(f"Colunas configuradas - A: {max_clausula_len}, B: 80, C: 60")
            
            # Ajustar altura das linhas
            for row_num in range(1, len(df) + 1):
                content_length = len(str(df.iloc[row_num-1]['Transcricao']))
                estimated_height = max(30, min(content_length // 80 * 15, 200))
                worksheet.set_row(row_num, estimated_height)
            
            logger.debug("Alturas das linhas configuradas")
        
        output.seek(0)
        file_size = len(output.getvalue())
        logger.info(f"Arquivo Excel criado com sucesso - Tamanho: {file_size} bytes")
        
        return output
        
    except Exception as e:
        logger.error(f"Erro ao criar arquivo Excel: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def main():
    logger.info("Iniciando aplicação principal")
    
    try:
        set_page_config()
        
        # Cabeçalho principal com logo da CSN
        st.markdown("""
        <div class="main-header">
            <div class="logo-container">
                <img src="https://upload.wikimedia.org/wikipedia/pt/e/eb/Companhia_Sider%C3%BArgica_Nacional.png" 
                     alt="Logo CSN" class="logo-img">
                <div class="header-text">
                    <h1>Processador de Cláusulas Contratuais-Transportadoras Gás</h1>
                    <p>Extração e resumo de cláusulas numeradas de contratos</p>
                    <p><small>NTS | TAG | TBG | Processamento Automatizado</small></p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Sidebar para configurações
        with st.sidebar:
            st.header("Configurações")
            
            api_key = st.text_input(
                "Chave API OpenAI (opcional)",
                type="password",
                help="Necessária apenas para gerar resumos"
            )
            
            if api_key:
                st.success("Chave API fornecida")
                logger.info("API key fornecida pelo usuário")
            else:
                st.info("Processamento sem resumos")
                logger.info("Processamento sem API key")
            
            st.markdown("---")
            st.markdown("**Formatos suportados:** PDF")
            st.markdown("**Tipos de contrato:** NTS, TAG, TBG")
            
            # Informações de debug
            st.markdown("---")
            st.markdown("**Debug Info:**")
            st.markdown(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Upload do arquivo
        st.header("Upload do Contrato")
        uploaded_file = st.file_uploader(
            "Selecione o arquivo PDF do contrato",
            type=['pdf']
        )
        
        if uploaded_file is not None:
            file_details = {
                'name': uploaded_file.name,
                'size': uploaded_file.size,
                'type': uploaded_file.type
            }
            
            logger.info(f"Arquivo carregado: {file_details}")
            st.info(f"Arquivo: {uploaded_file.name} ({uploaded_file.size:,} bytes)")
            
            if st.button("Processar Contrato", type="primary"):
                logger.info("Botão 'Processar Contrato' clicado")
                
                try:
                    with st.spinner("Processando contrato..."):
                        processed_clauses = process_contract(uploaded_file, api_key)
                    
                    if processed_clauses:
                        st.success("Processamento concluído!")
                        logger.info("Processamento concluído com sucesso")
                        
                        # Preview dos dados
                        st.header("Preview dos Resultados")
                        df_preview = pd.DataFrame(processed_clauses)
                        st.dataframe(df_preview.head(10), use_container_width=True)
                        
                        if len(processed_clauses) > 10:
                            st.info(f"Mostrando 10 de {len(processed_clauses)} cláusulas encontradas.")
                        
                        # Download do Excel
                        logger.info("Criando arquivo Excel para download")
                        excel_file = create_excel_file(processed_clauses)
                        
                        st.header("Download")
                        st.download_button(
                            label="Baixar Excel com Cláusulas",
                            data=excel_file,
                            file_name="clausulas_numeradas.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                        
                        logger.info("Arquivo Excel disponibilizado para download")
                    else:
                        logger.error("Processamento falhou - nenhuma cláusula retornada")
                
                except Exception as e:
                    logger.error(f"Erro durante o processamento: {str(e)}")
                    logger.error(traceback.format_exc())
                    st.error(f"Erro durante o processamento: {str(e)}")
        
        logger.debug("Execução principal concluída")
        
    except Exception as e:
        logger.error(f"Erro crítico na aplicação: {str(e)}")
        logger.error(traceback.format_exc())
        st.error(f"Erro crítico: {str(e)}")

if __name__ == "__main__":
    main()
