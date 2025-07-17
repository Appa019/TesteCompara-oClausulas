import streamlit as st
import pandas as pd
import PyPDF2
import re
import time
import openai
from io import BytesIO
import traceback

def set_page_config():
    """Configuração da página com cores da CSN"""
    st.set_page_config(
        page_title="Processador de Cláusulas - CSN GÁS NATURAL",
        page_icon="📄",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # CSS customizado com cores da CSN
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

def extract_text_from_pdf(pdf_file):
    """Extrai texto do PDF com melhor tratamento de quebras de linha"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        total_pages = len(pdf_reader.pages)
        
        # Começar da página 4 (índice 3) para pular sumário e páginas iniciais
        start_page = min(3, total_pages - 1)
        
        for page_num in range(start_page, total_pages):
            page_text = pdf_reader.pages[page_num].extract_text()
            if page_text:
                # Tratar quebras de linha e hifenização
                page_text = fix_text_breaks(page_text)
                text += page_text + "\n"
                
        return text
    except Exception as e:
        st.error(f"Erro ao extrair texto do PDF: {str(e)}")
        return None

def fix_text_breaks(text):
    """Corrige quebras de linha e reconstitui palavras quebradas"""
    # Corrigir palavras quebradas por hífen no final da linha
    text = re.sub(r'-\s*\n\s*', '', text)
    
    # Corrigir quebras de linha no meio de frases
    text = re.sub(r'([a-z,;])\n([a-z])', r'\1 \2', text)
    
    # Normalizar múltiplas quebras de linha para apenas uma
    text = re.sub(r'\n{2,}', '\n', text)
    
    # Corrigir espaços múltiplos
    text = re.sub(r' {2,}', ' ', text)
    
    return text

def identify_clauses(text):
    """Identifica e extrai cláusulas numeradas"""
    clauses = []
    
    pattern = re.compile(
        r"^(\d{1,2}(?:\.\d{1,2}){1,4}\.?)\s+([A-ZÁÉÍÓÚÇÃÔÊ])",
        re.MULTILINE
    )

    matches = list(pattern.finditer(text))

    if not matches:
        return []

    for i, match in enumerate(matches):
        start_pos = match.start()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        clause_block = text[start_pos:end_pos].strip()
        clause_number = match.group(1).strip()
        
        # Remove o número da cláusula do início do conteúdo
        clause_content = clause_block
        clause_content = re.sub(rf'^{re.escape(clause_number)}\s*', '', clause_content).strip()
        
        # Remove qualquer padrão de cláusula que apareça no final do texto
        end_pattern = re.search(r'\s+(\d{1,2}(?:\.\d{1,2}){1,4}\.?)\s+([A-ZÁÉÍÓÚÇÃÔÊ].*?)$', clause_content, re.DOTALL)
        
        if end_pattern:
            clause_content = clause_content[:clause_content.rfind(end_pattern.group(0))].strip()
        
        # Substitui quebras de linha por espaços
        clause_content = clause_content.replace('\n', ' ').strip()
        
        # Remove espaços múltiplos
        clause_content = re.sub(r'\s+', ' ', clause_content).strip()
        
        # Remove fragmentos como "Página X de Y"
        clause_content = re.sub(r'\s*Página\s+\d+\s+de\s+\d+\s*', ' ', clause_content)
        clause_content = re.sub(r'\s+', ' ', clause_content).strip()

        if clause_content and len(clause_content) > 10:
            clauses.append({
                'numero': clause_number,
                'conteudo': clause_content
            })

    return clauses

def generate_summary(clause_text, api_key):
    """Gera resumo da cláusula usando OpenAI GPT-4.1-nano"""
    if not api_key:
        return ""
    
    try:
        client = openai.OpenAI(api_key=api_key)
        
        prompt = f"""Esta cláusula é parte de um contrato de transporte de gás natural. 
        Faça um resumo geral completo do conteúdo em um parágrafo, explicando do que trata esta cláusula:

        {clause_text}

        Resumo:"""
        
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        return f"Erro no resumo: {str(e)}"

def process_contract(pdf_file, api_key=None):
    """Processa o contrato completo"""
    
    # Extrair texto do PDF
    st.info("Extraindo texto do PDF...")
    text = extract_text_from_pdf(pdf_file)
    
    if not text:
        return None
    
    # Identificar cláusulas
    st.info("Identificando cláusulas numeradas...")
    clauses = identify_clauses(text)
    
    if not clauses:
        st.warning("Nenhuma cláusula numerada foi encontrada no documento.")
        return None
    
    st.success(f"{len(clauses)} cláusulas numeradas encontradas!")
    
    # Processar cláusulas
    processed_clauses = []
    
    if api_key:
        st.info("Gerando resumos com IA...")
        progress_bar = st.progress(0)
        
        for i, clause in enumerate(clauses):
            summary = generate_summary(clause['conteudo'], api_key)
            
            processed_clauses.append({
                'Clausula': clause['numero'],
                'Transcricao': clause['conteudo'],
                'Resumo': summary
            })
            
            progress = (i + 1) / len(clauses)
            progress_bar.progress(progress)
            time.sleep(0.2)
            
        progress_bar.empty()
    else:
        st.info("Processando sem resumos...")
        for clause in clauses:
            processed_clauses.append({
                'Clausula': clause['numero'],
                'Transcricao': clause['conteudo'],
                'Resumo': ''
            })
    
    return processed_clauses

def create_excel_file(processed_clauses):
    """Cria arquivo Excel com as cláusulas processadas"""
    df = pd.DataFrame(processed_clauses)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Clausulas', index=False)
        
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
        
        # Configurar colunas
        max_clausula_len = max([len(str(row['Clausula'])) for row in processed_clauses]) + 2
        max_clausula_len = min(max_clausula_len, 20)
        worksheet.set_column('A:A', max_clausula_len, number_format)
        worksheet.set_column('B:B', 80, wrap_format)
        worksheet.set_column('C:C', 60, wrap_format)
        
        # Ajustar altura das linhas
        for row_num in range(1, len(df) + 1):
            content_length = len(str(df.iloc[row_num-1]['Transcricao']))
            estimated_height = max(30, min(content_length // 80 * 15, 200))
            worksheet.set_row(row_num, estimated_height)
    
    output.seek(0)
    return output

def main():
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
        else:
            st.info("Processamento sem resumos")
        
        st.markdown("---")
        st.markdown("**Formatos suportados:** PDF")
        st.markdown("**Tipos de contrato:** NTS, TAG, TBG")
    
    # Upload do arquivo
    st.header("Upload do Contrato")
    uploaded_file = st.file_uploader(
        "Selecione o arquivo PDF do contrato",
        type=['pdf']
    )
    
    if uploaded_file is not None:
        st.info(f"Arquivo: {uploaded_file.name} ({uploaded_file.size:,} bytes)")
        
        if st.button("Processar Contrato", type="primary"):
            try:
                with st.spinner("Processando contrato..."):
                    processed_clauses = process_contract(uploaded_file, api_key)
                
                if processed_clauses:
                    st.success("Processamento concluído!")
                    
                    # Preview dos dados
                    st.header("Preview dos Resultados")
                    df_preview = pd.DataFrame(processed_clauses)
                    st.dataframe(df_preview.head(10), use_container_width=True)
                    
                    if len(processed_clauses) > 10:
                        st.info(f"Mostrando 10 de {len(processed_clauses)} cláusulas encontradas.")
                    
                    # Download do Excel
                    excel_file = create_excel_file(processed_clauses)
                    
                    st.header("Download")
                    st.download_button(
                        label="Baixar Excel com Cláusulas",
                        data=excel_file,
                        file_name="clausulas_numeradas.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
            except Exception as e:
                st.error(f"Erro durante o processamento: {str(e)}")

if __name__ == "__main__":
    main()
