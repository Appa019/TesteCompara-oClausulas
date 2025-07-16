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
        
        # Limpar texto para melhor processamento
        text = re.sub(r'\s+', ' ', text)
        
        # 1. Padrão para cláusulas principais: CLÁUSULA PRIMEIRA – NOME DA CLÁUSULA
        main_clause_pattern = r'CLÁUSULA\s+(PRIMEIRA|SEGUNDA|TERCEIRA|QUARTA|QUINTA|SEXTA|SÉTIMA|OITAVA|NONA|DÉCIMA|ONZE|DOZE|TREZE|QUATORZE|QUINZE|DEZESSEIS|DEZESSETE|DEZOITO|DEZENOVE|VINTE|VINTE\s+E\s+UM|VINTE\s+E\s+DOIS|VINTE\s+E\s+TRÊS)\s*[–-]\s*([^§]+?)(?=CLÁUSULA\s+(?:PRIMEIRA|SEGUNDA|TERCEIRA|QUARTA|QUINTA|SEXTA|SÉTIMA|OITAVA|NONA|DÉCIMA|ONZE|DOZE|TREZE|QUATORZE|QUINZE|DEZESSEIS|DEZESSETE|DEZOITO|DEZENOVE|VINTE|VINTE\s+E\s+UM|VINTE\s+E\s+DOIS|VINTE\s+E\s+TRÊS)|ANEXO|APÊNDICE|$)'
        
        # 2. Padrão para anexos e apêndices
        annex_pattern = r'(ANEXO\s+[I-V]+(?:-[A-Z])?|APÊNDICE\s+[I-V]+)\s*[–-]\s*([^§]+?)(?=(?:ANEXO|APÊNDICE|CLÁUSULA)\s+|$)'
        
        # 3. Padrão para subcláusulas de todos os níveis (1.1, 1.1.1, 1.1.1.1, etc.)
        subclause_pattern = r'(\d+\.\d+(?:\.\d+)*)\s*([A-Z][^§]+?)(?=\d+\.\d+(?:\.\d+)*\s+[A-Z]|CLÁUSULA|ANEXO|APÊNDICE|$)'
        
        # 4. Padrão para itens com letras (a), (b), (c), etc.
        letter_item_pattern = r'\(([a-z])\)\s*([^§]+?)(?=\([a-z]\)|CLÁUSULA|ANEXO|APÊNDICE|\d+\.\d+|$)'
        
        # 5. Padrão para itens com números romanos (i), (ii), (iii), etc.
        roman_item_pattern = r'\(([ivx]+)\)\s*([^§]+?)(?=\([ivx]+\)|CLÁUSULA|ANEXO|APÊNDICE|\d+\.\d+|$)'
        
        # Extrair cláusulas principais
        main_matches = re.finditer(main_clause_pattern, text, re.DOTALL | re.IGNORECASE)
        for match in main_matches:
            clause_number = match.group(1).strip()
            clause_content = match.group(2).strip()
            
            # Extrair o título da cláusula (primeira linha geralmente)
            title_match = re.match(r'^([^\.]+?)(?:\s*\.\s*|\s*$)', clause_content)
            if title_match:
                clause_title = title_match.group(1).strip()
                clause_id = f"CLÁUSULA {clause_number} – {clause_title}"
            else:
                clause_id = f"CLÁUSULA {clause_number}"
            
            # Limitar tamanho do conteúdo
            if len(clause_content) > 4000:
                clause_content = clause_content[:4000] + "..."
            
            clauses[clause_id] = clause_content
        
        # Extrair anexos e apêndices
        annex_matches = re.finditer(annex_pattern, text, re.DOTALL | re.IGNORECASE)
        for match in annex_matches:
            annex_id = match.group(1).strip()
            annex_content = match.group(2).strip()
            
            # Extrair título do anexo/apêndice
            title_match = re.match(r'^([^\.]+?)(?:\s*\.\s*|\s*$)', annex_content)
            if title_match:
                annex_title = title_match.group(1).strip()
                full_annex_id = f"{annex_id} – {annex_title}"
            else:
                full_annex_id = annex_id
            
            # Limitar tamanho do conteúdo
            if len(annex_content) > 4000:
                annex_content = annex_content[:4000] + "..."
            
            clauses[full_annex_id] = annex_content
        
        # Extrair subcláusulas numeradas (TODOS os níveis: 1.1, 1.1.1, 1.1.1.1, etc.)
        subclause_matches = re.finditer(subclause_pattern, text, re.DOTALL | re.IGNORECASE)
        for match in subclause_matches:
            subclause_id = match.group(1).strip()
            subclause_content = match.group(2).strip()
            
            # Verificar se é uma subcláusula substancial (mais de 80 caracteres)
            if len(subclause_content) > 80:
                # Limitar tamanho do conteúdo
                if len(subclause_content) > 3000:
                    subclause_content = subclause_content[:3000] + "..."
                
                clauses[f"Item {subclause_id}"] = subclause_content
        
        # Extrair itens com letras (a), (b), (c)
        letter_matches = re.finditer(letter_item_pattern, text, re.DOTALL | re.IGNORECASE)
        for match in letter_matches:
            letter_id = match.group(1).strip()
            letter_content = match.group(2).strip()
            
            # Verificar se é um item substancial
            if len(letter_content) > 60:
                # Limitar tamanho do conteúdo
                if len(letter_content) > 2000:
                    letter_content = letter_content[:2000] + "..."
                
                clauses[f"Item ({letter_id})"] = letter_content
        
        # Extrair itens com números romanos (i), (ii), (iii)
        roman_matches = re.finditer(roman_item_pattern, text, re.DOTALL | re.IGNORECASE)
        for match in roman_matches:
            roman_id = match.group(1).strip()
            roman_content = match.group(2).strip()
            
            # Verificar se é um item substancial
            if len(roman_content) > 60:
                # Limitar tamanho do conteúdo
                if len(roman_content) > 2000:
                    roman_content = roman_content[:2000] + "..."
                
                clauses[f"Item ({roman_id})"] = roman_content
        
        # Extrair seções específicas importantes que podem não seguir padrões anteriores
        # Padrão para seções com títulos em maiúsculas
        section_pattern = r'([A-Z][A-Z\s]{10,})\s*([^§]+?)(?=[A-Z][A-Z\s]{10,}|CLÁUSULA|ANEXO|APÊNDICE|$)'
        section_matches = re.finditer(section_pattern, text, re.DOTALL)
        for match in section_matches:
            section_title = match.group(1).strip()
            section_content = match.group(2).strip()
            
            # Filtrar seções substanciais e relevantes
            if (len(section_content) > 100 and 
                not section_title.startswith("CLÁUSULA") and
                not section_title.startswith("ANEXO") and
                not section_title.startswith("APÊNDICE")):
                
                # Limitar tamanho do conteúdo
                if len(section_content) > 3000:
                    section_content = section_content[:3000] + "..."
                
                clauses[f"Seção: {section_title}"] = section_content
        
        return clauses
    
    def compare_clauses_with_ai(self, clause_id: str, clauses: Dict[str, str], contract_names: List[str]) -> Dict:
        """Compara cláusulas usando o modelo GPT-4.1 nano da OpenAI"""
        
        # Preparar o prompt com contexto específico para contratos jurídicos
        prompt = f"""
        Analise as seguintes versões da seção "{clause_id}" de três contratos jurídicos diferentes e identifique APENAS diferenças significativas que alterem o sentido legal ou impacto contratual:

        """
        
        for i, (name, content) in enumerate(zip(contract_names, clauses.values())):
            prompt += f"\n**{name}:**\n{content}\n"
        
        prompt += """
        
        CRITÉRIOS para identificar diferenças SIGNIFICATIVAS:
        1. Alterações em obrigações ou direitos das partes
        2. Mudanças em valores monetários, percentuais ou prazos
        3. Alterações em penalidades, multas ou sanções
        4. Modificações em condições de rescisão ou término
        5. Diferenças em procedimentos ou requisitos legais
        6. Alterações em definições que impactem outras cláusulas
        7. Mudanças em jurisdição ou lei aplicável
        8. Diferenças em garantias ou responsabilidades
        
        IGNORE:
        - Diferenças meramente estilísticas ou de redação
        - Alterações na ordem das palavras sem mudança de significado
        - Variações em formatação ou pontuação
        - Pequenas diferenças gramaticais
        
        Se houver diferenças SIGNIFICATIVAS, retorne:
        {
            "tem_diferenca": true,
            "diferenca_encontrada": "Descrição precisa e concisa da diferença legal encontrada, focando no impacto prático"
        }
        
        Se NÃO houver diferenças significativas, retorne:
        {
            "tem_diferenca": false,
            "diferenca_encontrada": ""
        }
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[
                    {"role": "system", "content": "Você é um advogado especialista em análise comparativa de contratos. Foque apenas em diferenças que tenham impacto legal real e prático."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
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
        
        # Encontrar cláusulas comuns e organizar por importância
        status_text.text("Identificando e organizando cláusulas...")
        all_clause_ids = set()
        for clauses in contracts_clauses.values():
            all_clause_ids.update(clauses.keys())
        
        # Priorizar cláusulas principais (ordenar por importância)
        def clause_priority(clause_id):
            if clause_id.startswith("CLÁUSULA"):
                # Extrair número da cláusula para ordenação
                if "PRIMEIRA" in clause_id:
                    return 1
                elif "SEGUNDA" in clause_id:
                    return 2
                elif "TERCEIRA" in clause_id:
                    return 3
                elif "QUARTA" in clause_id:
                    return 4
                elif "QUINTA" in clause_id:
                    return 5
                elif "SEXTA" in clause_id:
                    return 6
                elif "SÉTIMA" in clause_id:
                    return 7
                elif "OITAVA" in clause_id:
                    return 8
                elif "NONA" in clause_id:
                    return 9
                elif "DÉCIMA" in clause_id:
                    return 10
                elif "ONZE" in clause_id:
                    return 11
                elif "DOZE" in clause_id:
                    return 12
                elif "TREZE" in clause_id:
                    return 13
                elif "QUATORZE" in clause_id:
                    return 14
                elif "QUINZE" in clause_id:
                    return 15
                elif "DEZESSEIS" in clause_id:
                    return 16
                elif "DEZESSETE" in clause_id:
                    return 17
                elif "DEZOITO" in clause_id:
                    return 18
                elif "DEZENOVE" in clause_id:
                    return 19
                elif "VINTE" in clause_id:
                    if "UM" in clause_id:
                        return 21
                    elif "DOIS" in clause_id:
                        return 22
                    elif "TRÊS" in clause_id:
                        return 23
                    else:
                        return 20
                else:
                    return 100
            elif clause_id.startswith("ANEXO"):
                return 200
            elif clause_id.startswith("APÊNDICE"):
                return 300
            elif clause_id.startswith("Item") and "." in clause_id:
                # Ordenar subcláusulas numeradas (1.1, 1.1.1, etc.)
                numbers = clause_id.replace("Item ", "").split(".")
                try:
                    return 400 + int(numbers[0]) + int(numbers[1])/100 + (int(numbers[2])/10000 if len(numbers) > 2 else 0)
                except:
                    return 450
            elif clause_id.startswith("Item ("):
                # Itens com letras ou números romanos
                return 500
            elif clause_id.startswith("Seção:"):
                return 600
            else:
                return 700
        
        # Ordenar cláusulas por prioridade
        sorted_clause_ids = sorted(all_clause_ids, key=clause_priority)
        
        # Mostrar estatísticas de extração
        st.info(f"📊 **Cláusulas extraídas:** {len(all_clause_ids)} seções identificadas para análise")
        
        # Mostrar preview das cláusulas encontradas
        with st.expander("🔍 Preview das cláusulas encontradas"):
            for i, clause_id in enumerate(sorted_clause_ids[:10]):  # Mostrar primeiras 10
                st.write(f"**{i+1}.** {clause_id}")
            if len(sorted_clause_ids) > 10:
                st.write(f"... e mais {len(sorted_clause_ids) - 10} cláusulas")
        
        # Preparar dados para comparação
        results = []
        contract_names = list(contracts_clauses.keys())
        
        total_clauses = len(sorted_clause_ids)
        processed_clauses = 0
        
        for clause_id in sorted_clause_ids:
            status_text.text(f"Comparando: {clause_id[:50]}...")
            
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
                    
                    # Adicionar conteúdo de cada contrato (limitado para visualização)
                    for contract_name in contract_names:
                        content = clause_contents[contract_name]
                        if len(content) > 800:
                            content = content[:800] + "..."
                        row[contract_name] = content
                    
                    results.append(row)
            
            processed_clauses += 1
            progress_bar.progress(0.3 + (processed_clauses / total_clauses) * 0.7)
            
            # Pequena pausa para evitar rate limiting
            time.sleep(0.2)
        
        status_text.text("✅ Análise concluída!")
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
            help="Insira sua chave da API OpenAI para usar o modelo GPT-4.1 nano"
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
        
        **Modelo de IA:** OpenAI GPT-4.1 nano
        """)

if __name__ == "__main__":
    main()
