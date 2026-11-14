"""
Avaliação pelo texto (a de sempre): fala -> texto (transcricao_fala) e o texto dito comparado com o
esperado (Claude), em services/ai_pronunciation.py. Também o modo simulado de desenvolvimento.
Nunca levanta ErroProvedor: uma falha técnica vem como indisponivel=True (503 sem tirar vidas).
"""
import asyncio
import io

from .base import Provedor, ResultadoPronuncia


def de_pronunciation_result(r, fonte='texto'):
    """PronunciationResult (ou objecto parecido) -> ResultadoPronuncia."""
    g = lambda nome, omissao=None: getattr(r, nome, omissao)  # noqa: E731
    return ResultadoPronuncia(
        # Valores como vieram (quem grava arredonda com views_ai._nota).
        nota=g('overall_score', 0) or 0, fluencia=g('fluency_score', 0) or 0,
        fonte=fonte, transcricao=str(g('transcribed_text', '') or ''), texto_esperado=str(g('expected_text', '') or ''),
        aceite=bool(g('is_acceptable', False)), mensagem=str(g('feedback', '') or ''),
        sugestoes=list(g('suggestions', []) or []), palavras_problematicas=list(g('problematic_words', []) or []),
        nota_pronuncia=g('pronunciation_score', 0) or 0, nota_clareza=g('clarity_score', 0) or 0,
        credito=g('partial_credit', 0) or 0, confianca=g('confidence_level', 0.5),
        indisponivel=bool(g('indisponivel', False)), tempos=g('transcricao_fala'),
    )


class ProvedorTexto(Provedor):
    nome = 'texto'

    def avaliar(self, audio_bytes, mime, texto_esperado=None, idioma='en-US', modo='lido', nivel='intermediate',
                nome=None):
        from apps.practice.services.ai_pronunciation import AIPronunciationAnalyzer
        audio = io.BytesIO(audio_bytes)
        audio.name = nome or 'gravacao.webm'
        loop = asyncio.new_event_loop()
        try:
            r = loop.run_until_complete(AIPronunciationAnalyzer().analyze_pronunciation(
                audio_file=audio, expected_text=texto_esperado or '', difficulty_level=nivel))
        finally:
            loop.close()
        return de_pronunciation_result(r)


class ProvedorSimulado(Provedor):
    """Desenvolvimento sem IA (PRONUNCIA_SIMULADA com DEBUG): aceita qualquer gravação com som (> 2 KB)."""
    nome = 'simulada'

    def avaliar(self, audio_bytes, mime, texto_esperado=None, idioma='en-US', modo='lido', nivel='intermediate',
                nome=None):
        ok = len(audio_bytes or b'') > 2048
        frase = texto_esperado or ''
        n = 82 if ok else 20
        return ResultadoPronuncia(
            nota=n, fluencia=80 if ok else 20, fonte='simulada', transcricao=frase if ok else '',
            texto_esperado=frase, aceite=ok, nota_pronuncia=n, nota_clareza=84 if ok else 20,
            credito=10 if ok else 0, confianca='simulado',
            mensagem='Análise simulada (desenvolvimento sem IA).' if ok else 'Não ouvimos nada. Grave outra vez.',
        )
