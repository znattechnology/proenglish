"""
Conversa com o tutor (IA de voz via Vapi + OpenAI).

Contrato servido em /api/v1/practice/conversa/ (ver views.py). Regras de confiança:
- o início e a duração da sessão são medidos no servidor (started_at);
- a quota diária é verificada e descontada no servidor;
- o nome do aluno vem da conta, não do cliente;
- notas calculadas a partir da transcrição (OpenAI ou regras determinísticas no modo simulado);
- a pronúncia não é medida (só há texto): fica null e não entra na nota geral.
"""
