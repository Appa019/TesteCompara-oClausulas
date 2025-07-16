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
    """Extrai texto do PDF com melhor tratamento de quebras de linha"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        total_pages = len(pdf_reader.pages)
        
        # Começar da página 4 (índice 3) para pular sumário e páginas iniciais
        start_page = min(3, total_pages - 1)
        
        for page_num in range(start_page, total_pages):
            page_text = pdf_reader.pages[page_num].extract_text()
            if page_text.strip():
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
    
    # Corrigir quebras de linha no meio de palavras (sem hífen)
    # Detectar quando uma linha termina com letra minúscula e a próxima começa com minúscula
    text = re.sub(r'([a-zçãôêáéíóú])\s*\n\s*([a-zçãôêáéíóú])', r'\1\2', text)
    
    # Corrigir quebras entre palavras onde uma linha termina com minúscula
    # e a próxima começa com maiúscula (provável continuação de frase)
    text = re.sub(r'([a-zçãôêáéíóú.,;:])\s*\n\s*([A-ZÇÃÔÊÁÉÍÓÚ])', r'\1 \2', text)
    
    # Normalizar múltiplas quebras de linha
    text = re.sub(r'\n\s*\n\s*', '\n\n', text)
    
    # Corrigir espaços múltiplos
    text = re.sub(r' {2,}', ' ', text)
    
    return text

def identify_clauses(text):
    """Identifica e extrai todas as cláusulas e subcláusulas, ignorando sumários"""
    clauses = []
    
    # Limpar texto e remover quebras de página
    text_clean = re.sub(r'Página \d+ de \d+', '', text)
    text_clean = re.sub(r'\s+', ' ', text_clean)  # Normalizar espaços
    
    # Padrões melhorados para identificar cláusulas
    clause_patterns = [
        # CLÁUSULA PRIMEIRA, SEGUNDA, etc.
        r'CLÁUSULA\s+(?:PRIMEIRA|SEGUNDA|TERCEIRA|QUARTA|QUINTA|SEXTA|SÉTIMA|OITAVA|NONA|DÉCIMA|DÉCIMA\s+PRIMEIRA|DÉCIMA\s+SEGUNDA|DÉCIMA\s+TERCEIRA|DÉCIMA\s+QUARTA|DÉCIMA\s+QUINTA|DÉCIMA\s+SEXTA|DÉCIMA\s+SÉTIMA|DÉCIMA\s+OITAVA|DÉCIMA\s+NONA|VIGÉSIMA|VINTE|VINTE\s+E\s+UM|VINTE\s+E\s+DOIS|VINTE\s+E\s+TRÊS)\s*[-–]\s*[A-ZÁÊÔÕÇÃÍ]',
        # Numeração com pontos: 1.1, 1.1.1, etc.
        r'\b\d+\.\d+(?:\.\d+)*\s+[A-ZÁÊÔÕÇÃÍ]',
        # Letras com parênteses: a), b), c), etc.
        r'\b[a-z]\)\s+[a-záêôõçãí]',
        # Números romanos: i), ii), iii), etc.
        r'\b[ivx]+\)\s+[a-záêôõçãí]',
        # Números simples com parênteses: (1), (2), etc.
        r'\(\d+\)\s+[A-ZÁÊÔÕÇÃÍ]'
    ]
    
    # Indicadores de sumário para filtrar
    sumario_indicators = [
        r'\.{3,}',  # Pontos de continuação
        r'\b\d+\s*$',  # Números de página isolados
        r'anexo [iv]+\s*[-–]',
        r'apêndice [iv]+\s*[-–]',
        r'página \d+',
        r'cep \d+',
        r'cnpj',
    ]
    
    # Dividir texto em blocos maiores para melhor identificação
    # Primeiro, vamos procurar por todas as cláusulas principais
    main_clauses = re.finditer(
        r'CLÁUSULA\s+(?:PRIMEIRA|SEGUNDA|TERCEIRA|QUARTA|QUINTA|SEXTA|SÉTIMA|OITAVA|NONA|DÉCIMA|DÉCIMA\s+PRIMEIRA|DÉCIMA\s+SEGUNDA|DÉCIMA\s+TERCEIRA|DÉCIMA\s+QUARTA|DÉCIMA\s+QUINTA|DÉCIMA\s+SEXTA|DÉCIMA\s+SÉTIMA|DÉCIMA\s+OITAVA|DÉCIMA\s+NONA|VIGÉSIMA|VINTE|VINTE\s+E\s+UM|VINTE\s+E\s+DOIS|VINTE\s+E\s+TRÊS)\s*[-–]\s*([^\n]{10,100})',
        text_clean, re.IGNORECASE
    )
    
    clause_positions = []
    for match in main_clauses:
        start_pos = match.start()
        end_pos = match.end()
        title = match.group().strip()
        clause_positions.append((start_pos, end_pos, title))
    
    # Extrair conteúdo de cada cláusula
    for i, (start_pos, title_end_pos, title) in enumerate(clause_positions):
        # Determinar onde termina o conteúdo desta cláusula
        if i + 1 < len(clause_positions):
            next_start = clause_positions[i + 1][0]
            content_end = next_start
        else:
            content_end = len(text_clean)
        
        # Extrair conteúdo da cláusula
        full_content = text_clean[start_pos:content_end].strip()
        
        # Separar título do conteúdo
        content = text_clean[title_end_pos:content_end].strip()
        
        # Verificar se não é sumário
        is_sumario = any(re.search(indicator, content.lower()) for indicator in sumario_indicators)
        
        if not is_sumario and len(content) > 50:  # Conteúdo mínimo
            # Limpar título
            clean_title = re.sub(r'\s+', ' ', title).strip()
            
            # Limitar o conteúdo se for muito longo (primeiras 2000 caracteres)
            if len(content) > 2000:
                content = content[:2000] + "..."
            
            clauses.append({
                'numero': clean_title,
                'conteudo': content
            })
    
    # Se não encontrou cláusulas principais, tentar subcláusulas
    if not clauses:
        # Buscar por padrões de numeração
        subsection_pattern = r'(\d+\.\d+(?:\.\d+)*)\s+([A-ZÁÊÔÕÇÃÍ][^\n]{20,200})'
        subsections = re.finditer(subsection_pattern, text_clean)
        
        subsection_positions = []
        for match in subsections:
            start_pos = match.start()
            number = match.group(1)
            title_part = match.group(2)
            subsection_positions.append((start_pos, number, title_part))
        
        for i, (start_pos, number, title_part) in enumerate(subsection_positions):
            # Encontrar o final desta subseção
            if i + 1 < len(subsection_positions):
                next_start = subsection_positions[i + 1][0]
                content_end = next_start
            else:
                content_end = min(start_pos + 1000, len(text_clean))  # Limitar o conteúdo
            
            content = text_clean[start_pos:content_end].strip()
            
            # Verificar se não é sumário
            is_sumario = any(re.search(indicator, content.lower()) for indicator in sumario_indicators)
            
            if not is_sumario and len(content) > 50:
                clean_title = f"{number} - {title_part[:100]}"
                
                clauses.append({
                    'numero': clean_title,
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
    
    # Mostrar uma amostra do texto extraído para debug
    st.info(f"📝 Primeiros 500 caracteres do texto extraído:")
    st.text(text[:500])
    
    # Identificar cláusulas
    st.info("🔍 Identificando cláusulas...")
    clauses = identify_clauses(text)
    
    if not clauses:
        st.warning("⚠️ Nenhuma cláusula foi encontrada no documento.")
        st.info("🔍 Tentando busca mais ampla...")
        
        # Busca alternativa mais ampla
        lines = text.split('\n')
        potential_clauses = []
        
        for line in lines:
            line = line.strip()
            if (len(line) > 20 and 
                (re.search(r'CLÁUSULA|CLAUSULA', line, re.IGNORECASE) or
                 re.search(r'\d+\.\d+', line) or
                 re.search(r'ANEXO|APÊNDICE', line, re.IGNORECASE))):
                potential_clauses.append(line)
        
        if potential_clauses:
            st.info(f"🔍 Encontradas {len(potential_clauses)} possíveis cláusulas:")
            for clause in potential_clauses[:10]:  # Mostrar apenas as primeiras 10
                st.text(clause)
        
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
