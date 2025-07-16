import streamlit as st
import pandas as pd
import PyPDF2
import re
import time
import openai
from io import BytesIO
import traceback

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
    """Identifica e extrai APENAS cláusulas numeradas (ignora cláusulas principais)."""
    clauses = []
    
    # REGEX SIMPLIFICADO - APENAS CLÁUSULAS NUMERADAS
    # Padrões como: 1.1, 1.1.1, 1.1.1.1, 2.1, 3.2.1, etc.
    # Ignora completamente "CLÁUSULA PRIMEIRA", "CLÁUSULA SEGUNDA", etc.
    pattern = re.compile(
        r"^(\d{1,2}(?:\.\d{1,2}){1,4}\.?)\s+([A-ZÁÉÍÓÚÇÃÔÊ])",
        re.MULTILINE
    )

    # Encontra todas as correspondências (matches) e suas posições no texto
    matches = list(pattern.finditer(text))

    if not matches:
        return []

    # Itera sobre as correspondências para fatiar o texto
    for i, match in enumerate(matches):
        # O início da cláusula atual é o início da correspondência
        start_pos = match.start()

        # O fim da cláusula atual é o início da próxima cláusula
        # Se for a última, vai até o final do texto
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        # Extrai o bloco de texto completo da cláusula
        clause_block = text[start_pos:end_pos].strip()

        # Extrai o número da cláusula (grupo 1 do regex)
        clause_number = match.group(1).strip()
        
        # Remove o número da cláusula do início do conteúdo
        clause_content = clause_block
        
        # Remove o número do início do conteúdo
        clause_content = re.sub(rf'^{re.escape(clause_number)}\s*', '', clause_content).strip()
        
        # Substitui quebras de linha por espaços
        clause_content = clause_content.replace('\n', ' ').strip()
        
        # Remove espaços múltiplos
        clause_content = re.sub(r'\s+', ' ', clause_content).strip()

        # Adiciona à lista se o conteúdo for relevante
        if clause_content and len(clause_content) > 10:
            clauses.append({
                'numero': clause_number,
                'conteudo': clause_content
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
    st.info("🔍 Identificando cláusulas numeradas (ignorando cláusulas principais)...")
    clauses = identify_clauses(text)
    
    if not clauses:
        st.warning("⚠️ Nenhuma cláusula numerada foi encontrada no documento.")
        st.info("Texto extraído para depuração:")
        st.text_area("Texto", text[:5000], height=300)
        return None
    
    st.success(f"✅ {len(clauses)} cláusulas numeradas encontradas!")
    
    # Processar cláusulas
    processed_clauses = []
    
    if api_key:
        st.info("🤖 Gerando resumos com IA...")
        progress_bar = st.progress(0)
        
        for i, clause in enumerate(clauses):
            # Gerar resumo
            summary = generate_summary(clause['conteudo'], api_key)
            
            processed_clauses.append({
                'Clausula': clause['numero'],  # Apenas o número
                'Transcricao': clause['conteudo'],  # Texto completo limpo
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
                'Clausula': clause['numero'],  # Apenas o número
                'Transcricao': clause['conteudo'],  # Texto completo limpo
                'Resumo': ''
            })
    
    return processed_clauses

def create_excel_file(processed_clauses):
    """Cria arquivo Excel com as cláusulas processadas e autofit das colunas"""
    df = pd.DataFrame(processed_clauses)
    
    # Criar arquivo Excel em memória
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Clausulas', index=False)
        
        # Formatação
        workbook = writer.book
        worksheet = writer.sheets['Clausulas']
        
        # Formatação do cabeçalho
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D7E4BC',
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
        
        # AUTOFIT DAS COLUNAS baseado no conteúdo
        
        # Calcular largura ideal para coluna A (Clausula)
        max_clausula_len = max([len(str(row['Clausula'])) for row in processed_clauses]) + 2
        max_clausula_len = min(max_clausula_len, 20)  # Máximo de 20 caracteres para números
        worksheet.set_column('A:A', max_clausula_len, number_format)
        
        # Para coluna B (Transcricao) - usar largura fixa otimizada para leitura
        worksheet.set_column('B:B', 80, wrap_format)
        
        # Para coluna C (Resumo) - usar largura fixa otimizada
        worksheet.set_column('C:C', 60, wrap_format)
        
        # Ajustar altura das linhas para melhor visualização
        for row_num in range(1, len(df) + 1):
            # Calcular altura baseada no conteúdo da transcrição
            content_length = len(str(df.iloc[row_num-1]['Transcricao']))
            estimated_height = max(30, min(content_length // 80 * 15, 200))  # Entre 30 e 200
            worksheet.set_row(row_num, estimated_height)
    
    output.seek(0)
    return output

# Interface principal
def main():
    st.title("📄 Processador de Cláusulas Contratuais")
    st.markdown("**Plataforma para extração e resumo de cláusulas numeradas de contratos NTS, TAG e TBG**")
    
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
        st.markdown("**Foco:** Apenas cláusulas numeradas (ex: 1.1, 1.1.1)")
    
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
                        file_name="clausulas_numeradas.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
            except Exception as e:
                st.error(f"❌ Erro durante o processamento: {str(e)}")
                st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
