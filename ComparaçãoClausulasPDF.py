import streamlit as st
import pandas as pd
import PyPDF2
import re
import os
from openai import OpenAI
import json
from typing import List, Dict, Tuple
import time
from io import BytesIO

# Configuração da página
st.set_page_config(
    page_title="Comparador de Contratos",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

class ContractComparator:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        
    def extract_text_from_pdf(self, pdf_file) -> str:
        """Extrai texto de um arquivo PDF"""
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            st.error(f"Erro ao extrair texto do PDF: {e}")
            return ""
    
    def extract_clauses(self, text: str) -> Dict[str, str]:
        """Extrai cláusulas e subcláusulas do texto do contrato"""
        clauses = {}
        
        # Padrões para identificar cláusulas
        patterns = [
            r'CLÁUSULA\s+([A-Z]+(?:\s+E\s+[A-Z]+)*)\s*[–-]\s*([^§]+?)(?=CLÁUSULA\s+[A-Z]+|$)',
            r'(\d+\.\d+(?:\.\d+)*)\s*[–-]?\s*([^§]+?)(?=\d+\.\d+(?:\.\d+)*\s*[–-]?|CLÁUSULA|$)',
            r'(\d+\.\d+(?:\.\d+)*)\s+([^§]+?)(?=\d+\.\d+(?:\.\d+)*|CLÁUSULA|$)',
            r'([A-Z][^:]*:)\s*([^§]+?)(?=[A-Z][^:]*:|CLÁUSULA|$)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.DOTALL | re.IGNORECASE)
            for match in matches:
                clause_id = match.group(1).strip()
                clause_content = match.group(2).strip()
                
                # Limpar conteúdo da cláusula
                clause_content = re.sub(r'\s+', ' ', clause_content)
                clause_content = clause_content[:2000]  # Limitar tamanho
                
                if len(clause_content) > 50:  # Filtrar cláusulas muito pequenas
                    clauses[clause_id] = clause_content
        
        return clauses
    
    def compare_clauses_with_ai(self, clause_id: str, clauses: Dict[str, str], contract_names: List[str]) -> Dict:
        """Compara cláusulas usando o modelo o3-mini da OpenAI"""
        
        # Preparar o prompt
        prompt = f"""
        Analise as seguintes cláusulas da seção "{clause_id}" de três contratos diferentes e identifique APENAS diferenças significativas que afetam o sentido legal:

        """
        
        for i, (name, content) in enumerate(zip(contract_names, clauses.values())):
            prompt += f"\n**{name}:**\n{content}\n"
        
        prompt += """
        
        Retorne APENAS se houver diferenças significativas que alterem:
        - Obrigações das partes
        - Valores, percentuais ou datas
        - Prazos ou condições
        - Penalidades ou consequências legais
        - Direitos ou responsabilidades
        
        Se houver diferenças significativas, retorne um JSON com:
        {
            "tem_diferenca": true,
            "diferenca_encontrada": "descrição clara da diferença legal encontrada"
        }
        
        Se NÃO houver diferenças significativas, retorne:
        {
            "tem_diferenca": false,
            "diferenca_encontrada": ""
        }
        """
        
        try:
            response = self.client.chat.completions.create(
                model="o3-mini",
                messages=[
                    {"role": "system", "content": "Você é um especialista em análise jurídica de contratos. Analise apenas diferenças que tenham impacto legal significativo."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content
            
            # Tentar extrair JSON da resposta
            try:
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return result
                else:
                    return {"tem_diferenca": False, "diferenca_encontrada": ""}
            except:
                return {"tem_diferenca": False, "diferenca_encontrada": ""}
                
        except Exception as e:
            st.error(f"Erro na API OpenAI: {e}")
            return {"tem_diferenca": False, "diferenca_encontrada": ""}
    
    def process_contracts(self, pdf_files: List, progress_bar, status_text) -> pd.DataFrame:
        """Processa os contratos e gera a tabela de diferenças"""
        
        # Extrair texto dos PDFs
        status_text.text("Extraindo texto dos PDFs...")
        contracts_text = {}
        contracts_clauses = {}
        
        for i, pdf_file in enumerate(pdf_files):
            contract_name = pdf_file.name.replace('.pdf', '')
            text = self.extract_text_from_pdf(pdf_file)
            contracts_text[contract_name] = text
            
            # Extrair cláusulas
            clauses = self.extract_clauses(text)
            contracts_clauses[contract_name] = clauses
            
            progress_bar.progress((i + 1) / len(pdf_files) * 0.3)
        
        # Encontrar cláusulas comuns
        status_text.text("Identificando cláusulas comuns...")
        all_clause_ids = set()
        for clauses in contracts_clauses.values():
            all_clause_ids.update(clauses.keys())
        
        # Preparar dados para comparação
        results = []
        contract_names = list(contracts_clauses.keys())
        
        total_clauses = len(all_clause_ids)
        processed_clauses = 0
        
        for clause_id in all_clause_ids:
            status_text.text(f"Comparando cláusula: {clause_id}")
            
            # Coletar cláusulas dos 3 contratos
            clause_contents = {}
            for contract_name in contract_names:
                clause_contents[contract_name] = contracts_clauses[contract_name].get(clause_id, "")
            
            # Verificar se pelo menos 2 contratos têm esta cláusula
            non_empty_clauses = [content for content in clause_contents.values() if content.strip()]
            
            if len(non_empty_clauses) >= 2:
                # Comparar com IA
                comparison_result = self.compare_clauses_with_ai(clause_id, clause_contents, contract_names)
                
                if comparison_result.get("tem_diferenca", False):
                    # Criar linha na tabela
                    row = {
                        "Cláusula": clause_id,
                        "Diferença": comparison_result.get("diferenca_encontrada", "")
                    }
                    
                    # Adicionar conteúdo de cada contrato
                    for contract_name in contract_names:
                        row[contract_name] = clause_contents[contract_name][:500] + "..." if len(clause_contents[contract_name]) > 500 else clause_contents[contract_name]
                    
                    results.append(row)
            
            processed_clauses += 1
            progress_bar.progress(0.3 + (processed_clauses / total_clauses) * 0.7)
            
            # Pequena pausa para evitar rate limiting
            time.sleep(0.1)
        
        status_text.text("Concluído!")
        return pd.DataFrame(results)

def main():
    st.title("📄 Comparador de Contratos")
    st.markdown("### Identifique diferenças significativas entre cláusulas de contratos")
    
    # Sidebar para configurações
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        # Campo para API Key
        api_key = st.text_input(
            "Chave da API OpenAI",
            type="password",
            help="Insira sua chave da API OpenAI para usar o modelo o3-mini"
        )
        
        # Opção para usar variável de ambiente
        use_env_key = st.checkbox("Usar chave da variável de ambiente OPENAI_API_KEY")
        
        if use_env_key:
            api_key = os.getenv("OPENAI_API_KEY")
    
    # Verificar se a API key está disponível
    if not api_key:
        st.error("⚠️ Por favor, insira sua chave da API OpenAI ou configure a variável de ambiente.")
        st.stop()
    
    # Upload de arquivos
    st.header("📁 Upload dos Contratos")
    uploaded_files = st.file_uploader(
        "Selecione exatamente 3 arquivos PDF para comparar",
        type=['pdf'],
        accept_multiple_files=True,
        help="Carregue 3 contratos em formato PDF com texto selecionável"
    )
    
    if uploaded_files:
        if len(uploaded_files) != 3:
            st.warning(f"⚠️ Você carregou {len(uploaded_files)} arquivo(s). São necessários exatamente 3 arquivos.")
        else:
            st.success(f"✅ {len(uploaded_files)} contratos carregados com sucesso!")
            
            # Mostrar nomes dos arquivos
            for i, file in enumerate(uploaded_files, 1):
                st.write(f"**Contrato {i}:** {file.name}")
    
    # Botão para iniciar comparação
    if uploaded_files and len(uploaded_files) == 3:
        if st.button("🔍 Comparar Contratos", type="primary"):
            
            # Inicializar o comparador
            comparator = ContractComparator(api_key)
            
            # Barras de progresso
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # Processar contratos
                with st.spinner("Processando contratos..."):
                    df_results = comparator.process_contracts(uploaded_files, progress_bar, status_text)
                
                progress_bar.empty()
                status_text.empty()
                
                if not df_results.empty:
                    st.success(f"✅ Comparação concluída! Encontradas {len(df_results)} diferenças significativas.")
                    
                    # Mostrar tabela
                    st.header("📊 Resultados da Comparação")
                    st.dataframe(df_results, use_container_width=True)
                    
                    # Gerar arquivo Excel
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_results.to_excel(writer, sheet_name='Comparação de Contratos', index=False)
                        
                        # Formatação
                        workbook = writer.book
                        worksheet = writer.sheets['Comparação de Contratos']
                        
                        # Formato para headers
                        header_format = workbook.add_format({
                            'bold': True,
                            'text_wrap': True,
                            'valign': 'top',
                            'fg_color': '#D7E4BC',
                            'border': 1
                        })
                        
                        # Aplicar formato aos headers
                        for col_num, value in enumerate(df_results.columns.values):
                            worksheet.write(0, col_num, value, header_format)
                        
                        # Ajustar largura das colunas
                        worksheet.set_column('A:A', 20)  # Cláusula
                        worksheet.set_column('B:B', 50)  # Diferença
                        worksheet.set_column('C:Z', 40)  # Contratos
                    
                    # Botão de download
                    st.download_button(
                        label="📥 Baixar Resultados (Excel)",
                        data=output.getvalue(),
                        file_name="comparacao_contratos.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                    # Estatísticas
                    st.header("📈 Estatísticas")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Total de Diferenças", len(df_results))
                    
                    with col2:
                        st.metric("Contratos Analisados", len(uploaded_files))
                    
                    with col3:
                        if len(df_results) > 0:
                            avg_diff_length = df_results['Diferença'].str.len().mean()
                            st.metric("Média de Caracteres por Diferença", f"{avg_diff_length:.0f}")
                
                else:
                    st.info("ℹ️ Nenhuma diferença significativa foi encontrada entre os contratos.")
                    
            except Exception as e:
                st.error(f"❌ Erro durante o processamento: {e}")
                progress_bar.empty()
                status_text.empty()
    
    # Informações sobre o uso
    with st.expander("ℹ️ Informações sobre o uso"):
        st.markdown("""
        **Como usar:**
        1. Insira sua chave da API OpenAI
        2. Carregue exatamente 3 arquivos PDF
        3. Clique em "Comparar Contratos"
        4. Aguarde o processamento (pode demorar alguns minutos)
        5. Baixe os resultados em Excel
        
        **O que é analisado:**
        - Diferenças em obrigações das partes
        - Alterações em valores, percentuais e datas
        - Mudanças em prazos e condições
        - Variações em penalidades
        - Alterações em direitos e responsabilidades
        
        **Modelo de IA:** OpenAI o3-mini
        """)

if __name__ == "__main__":
    main()
