import streamlit as st
import pandas as pd
import PyPDF2
import re
import time
import openai
from io import BytesIO
import traceback

# Configuração da página
st.set_page_config(
    page_title="Processador de Cláusulas - NTS/TAG/TBG",
    page_icon="📄",
    layout="wide"
)

def extract_text_from_pdf(pdf_file):
    """Extrai texto do PDF a partir da página 4 (onde começam as cláusulas reais)"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        # Começar da página 4 (índice 3) para pular sumário e páginas iniciais
        for page_num in range(3, len(pdf_reader.pages)):  # Página 4 em diante
            text += pdf_reader.pages[page_num].extract_text() + "\n"
        return text
    except Exception as e:
        st.error(f"Erro ao extrair texto do PDF: {str(e)}")
        return None

def identify_clauses(text):
    """Identifica e extrai todas as cláusulas e subcláusulas, ignorando sumários"""
    clauses = []
    
    # Padrões para identificar cláusulas
    patterns = [
        # CLÁUSULA PRIMEIRA, SEGUNDA, etc.
        r'CLÁUSULA\s+(?:PRIMEIRA|SEGUNDA|TERCEIRA|QUARTA|QUINTA|SEXTA|SÉTIMA|OITAVA|NONA|DÉCIMA|ONZE|DOZE|TREZE|QUATORZE|QUINZE|DEZESSEIS|DEZESSETE|DEZOITO|DEZENOVE|VINTE|VINTE\s+E\s+UM|VINTE\s+E\s+DOIS|VINTE\s+E\s+TRÊS)(?:\s*[-–]\s*[A-ZÁÊÔÕÇ\s]+)?',
        # Numeração decimal: 1.1, 1.1.1, 1.1.1.1, etc.
        r'^\d+\.(?:\d+\.)*\d*\s',
        # Letras com parênteses: a), b), i), ii), etc.
        r'^[a-z]\)\s',
        r'^[ivx]+\)\s'
    ]
    
    # Palavras que indicam sumário/índice (para filtrar)
    sumario_keywords = ['sumário', 'índice', 'página', 'de 199', 'anexo i', 'anexo ii', 'anexo iii', 'anexo iv', 'apêndice']
    
    lines = text.split('\n')
    current_clause = None
    current_content = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Filtrar linhas que parecem ser do sumário
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in sumario_keywords):
            continue
            
        # Verificar se a linha é uma nova cláusula
        is_clause = False
        clause_match = None
        
        for pattern in patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                is_clause = True
                clause_match = match
                break
        
        if is_clause:
            # Salvar cláusula anterior se existir
            if current_clause and current_content:
                content = ' '.join(current_content).strip()
                if content and len(content) > 20:  # Filtrar conteúdos muito curtos
                    clauses.append({
                        'numero': current_clause,
                        'conteudo': content
                    })
            
            # Iniciar nova cláusula
            current_clause = line
            current_content = []
            
            # Se a linha tem conteúdo após o número/identificador, incluir
            remaining_text = line[clause_match.end():].strip()
            if remaining_text:
                current_content.append(remaining_text)
        else:
            # Adicionar linha ao conteúdo da cláusula atual
            if current_clause:
                current_content.append(line)
    
    # Adicionar última cláusula
    if current_clause and current_content:
        content = ' '.join(current_content).strip()
        if content and len(content) > 20:  # Filtrar conteúdos muito curtos
            clauses.append({
                'numero': current_clause,
                'conteudo': content
            })
    
    return clauses

def generate_summary(clause_text, api_key):
    """Gera resumo da cláusula usando OpenAI"""
    if not api_key:
        return ""
    
    try:
        client = openai.OpenAI(api_key=api_key)
        
        prompt = f"""Esta cláusula é parte de um contrato de transporte de gás natural. 
        Faça um resumo geral completo do conteúdo em um parágrafo, explicando do que trata esta cláusula:

        {clause_text}

        Resumo:"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
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
    st.info("📄 Extraindo texto do PDF (a partir da página 4)...")
    text = extract_text_from_pdf(pdf_file)
    
    if not text:
        return None
    
    # Identificar cláusulas
    st.info("🔍 Identificando cláusulas...")
    clauses = identify_clauses(text)
    
    if not clauses:
        st.warning("⚠️ Nenhuma cláusula foi encontrada no documento.")
        return None
    
    st.success(f"✅ {len(clauses)} cláusulas encontradas!")
    
    # Processar cláusulas
    processed_clauses = []
    
    if api_key:
        st.info("🤖 Gerando resumos com IA...")
        progress_bar = st.progress(0)
        
        for i, clause in enumerate(clauses):
            # Gerar resumo
            summary = generate_summary(clause['conteudo'], api_key)
            
            processed_clauses.append({
                'Clausula': clause['numero'],
                'Transcricao': clause['conteudo'],
                'Resumo': summary
            })
            
            # Atualizar progresso
            progress = (i + 1) / len(clauses)
            progress_bar.progress(progress)
            
            # Rate limiting
            time.sleep(0.5)
            
        progress_bar.empty()
    else:
        st.info("📝 Processando sem resumos (chave API não fornecida)...")
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
    
    # Criar arquivo Excel em memória
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Clausulas', index=False)
        
        # Formatação
        workbook = writer.book
        worksheet = writer.sheets['Clausulas']
        
        # Definir larguras das colunas
        worksheet.set_column('A:A', 20)  # Clausula
        worksheet.set_column('B:B', 80)  # Transcricao
        worksheet.set_column('C:C', 50)  # Resumo
        
        # Formatação do cabeçalho
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D7E4BC',
            'border': 1
        })
        
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
    
    output.seek(0)
    return output

# Interface principal
def main():
    st.title("📄 Processador de Cláusulas Contratuais")
    st.markdown("**Plataforma para extração e resumo de cláusulas de contratos NTS, TAG e TBG**")
    
    # Sidebar para configurações
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        # Campo para API Key
        api_key = st.text_input(
            "🔑 Chave API OpenAI (opcional)",
            type="password",
            help="Necessária apenas para gerar resumos. Deixe vazio para processar sem resumos."
        )
        
        if api_key:
            st.success("✅ Chave API fornecida - resumos serão gerados")
        else:
            st.info("ℹ️ Sem chave API - processamento sem resumos")
        
        st.markdown("---")
        st.markdown("**Formatos suportados:** PDF")
        st.markdown("**Tipos de contrato:** NTS, TAG, TBG")
    
    # Upload do arquivo
    st.header("📤 Upload do Contrato")
    uploaded_file = st.file_uploader(
        "Selecione o arquivo PDF do contrato",
        type=['pdf'],
        help="Faça upload de um contrato em formato PDF"
    )
    
    if uploaded_file is not None:
        # Mostrar informações do arquivo
        st.info(f"📁 Arquivo: {uploaded_file.name} ({uploaded_file.size:,} bytes)")
        
        # Botão para processar
        if st.button("🚀 Processar Contrato", type="primary"):
            try:
                with st.spinner("Processando contrato..."):
                    processed_clauses = process_contract(uploaded_file, api_key)
                
                if processed_clauses:
                    st.success("✅ Processamento concluído!")
                    
                    # Mostrar preview dos dados
                    st.header("👀 Preview dos Resultados")
                    df_preview = pd.DataFrame(processed_clauses)
                    st.dataframe(df_preview.head(10), use_container_width=True)
                    
                    if len(processed_clauses) > 10:
                        st.info(f"Mostrando 10 de {len(processed_clauses)} cláusulas encontradas.")
                    
                    # Gerar e oferecer download do Excel
                    excel_file = create_excel_file(processed_clauses)
                    
                    st.header("💾 Download")
                    st.download_button(
                        label="📥 Baixar Excel com Cláusulas",
                        data=excel_file,
                        file_name="resumoclausulas.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
            except Exception as e:
                st.error(f"❌ Erro durante o processamento: {str(e)}")
                st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
