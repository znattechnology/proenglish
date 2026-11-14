"""
Revisão de hoje (só alunos). Montado em /api/v1/student/revisao/.

  GET  resumo/      {para_rever, minutos, feitas_hoje}         cartões do laboratório e do painel
  GET  hoje/        sessão de hoje (até 12 exercícios)
  POST responder/   {exercicio_id, forma, resposta, segundos, pistas}
  POST falar/       multipart {exercicio_id, audio, segundos}   análise de pronúncia + resposta
  POST terminar/    {inicio}                                    resumo do fim
"""
import asyncio
import io
import logging
from types import SimpleNamespace

from django.conf import settings
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from . import revisao

logger = logging.getLogger(__name__)


class SoAlunos(BasePermission):
    message = 'A revisão é só para alunos.'

    def has_permission(self, request, view):
        return getattr(request.user, 'role', None) == 'student'


class LimiteRevisao(UserRateThrottle):
    rate = '60/minute'
    scope = 'revisao'


class Base(APIView):
    permission_classes = [IsAuthenticated, SoAlunos]


def _invalido():
    return Response({'codigo': 'exercicio_invalido', 'mensagem': 'Este exercício já não existe.'},
                    status=status.HTTP_404_NOT_FOUND)


class Resumo(Base):
    def get(self, request):
        return Response(revisao.resumo_de_hoje(request.user))


class Hoje(Base):
    def get(self, request):
        return Response(revisao.sessao_de_hoje(request.user))


class Responder(Base):
    throttle_classes = [LimiteRevisao]

    def post(self, request):
        d = request.data
        try:
            r = revisao.responder(request.user, d.get('exercicio_id'), d.get('forma'),
                                  str(d.get('resposta') or '')[:300], d.get('segundos'), d.get('pistas'))
        except revisao.ExercicioInvalido:
            return _invalido()
        return Response(r)


def _analisar(audio_bytes, frase):
    """Resultado da análise (o mesmo serviço e o mesmo modo simulado das lições)."""
    simulada = bool(getattr(settings, 'PRONUNCIA_SIMULADA', False) and settings.DEBUG)
    if simulada:
        ok = audio_bytes.getbuffer().nbytes > 2048
        return SimpleNamespace(
            transcribed_text=frase if ok else '', expected_text=frase, pronunciation_score=82 if ok else 20,
            fluency_score=80 if ok else 20, clarity_score=84 if ok else 20, overall_score=82 if ok else 20,
            is_acceptable=ok, feedback='Análise simulada (desenvolvimento sem IA).' if ok else 'Não ouvimos nada. Grave outra vez.',
            problematic_words=[], suggestions=[], indisponivel=False), True
    from apps.practice.services.ai_pronunciation import AIPronunciationAnalyzer
    loop = asyncio.new_event_loop()
    try:
        r = loop.run_until_complete(AIPronunciationAnalyzer().analyze_pronunciation(
            audio_file=audio_bytes, expected_text=frase, difficulty_level='intermediate'))
    finally:
        loop.close()
    return r, False


def _guardar_tentativa(user, result, simulada):
    from apps.practice.models import TentativaPronuncia
    from apps.practice.views_ai import _lista_textos, _nota
    return TentativaPronuncia.objects.create(
        user=user, challenge=None, resposta=None,
        texto_esperado=str(result.expected_text or '')[:2000], transcricao=str(result.transcribed_text or '')[:2000],
        nota_pronuncia=_nota(result.pronunciation_score), nota_fluencia=_nota(result.fluency_score),
        nota_clareza=_nota(result.clarity_score), nota_geral=_nota(result.overall_score),
        palavras_problematicas=_lista_textos(result.problematic_words, chars=60),
        sugestoes=_lista_textos(result.suggestions, maximo=10), feedback=str(result.feedback or '')[:2000],
        aceite=bool(result.is_acceptable),
        fonte=TentativaPronuncia.FONTE_SIMULADA if simulada else TentativaPronuncia.FONTE_IA)


def _indisponivel():
    return Response({'codigo': 'analise_indisponivel', 'pode_saltar': True,
                     'mensagem': 'Não conseguimos analisar a gravação agora. Pode saltar este exercício.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE)


class Falar(Base):
    def get_throttles(self):
        from apps.practice.views_ai import AIAnaliseThrottle
        return [AIAnaliseThrottle()]

    def post(self, request):
        from apps.subscriptions.models import UserSubscription
        from apps.practice.views_ai import _lista_textos, _nota

        exercicio_id = request.data.get('exercicio_id')
        try:
            d = revisao.definicao(request.user, exercicio_id, revisao.OUVIR)
        except revisao.ExercicioInvalido:
            return _invalido()
        audio = request.FILES.get('audio')
        if not audio:
            return Response({'codigo': 'audio_em_falta', 'mensagem': 'Grave a frase antes de enviar.'},
                            status=status.HTTP_400_BAD_REQUEST)
        frase = d['texto']

        sub = UserSubscription.objects.select_related('plan').filter(user=request.user).first()
        if sub is not None and sub.is_active() and not sub.can_use_ai_analysis():
            return Response({'codigo': 'limite_analises', 'pode_saltar': True,
                             'mensagem': 'Já usou as análises de pronúncia de hoje. Pode saltar este exercício.'},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
        try:
            dados = io.BytesIO(audio.read())
            dados.name = audio.name
            result, simulada = _analisar(dados, frase)
        except Exception:
            logger.exception('revisão: análise de pronúncia falhou')
            return _indisponivel()
        if getattr(result, 'indisponivel', False):
            return _indisponivel()
        try:
            _guardar_tentativa(request.user, result, simulada)
        except Exception:
            logger.exception('revisão: falha ao guardar a tentativa de pronúncia')
        if sub is not None and sub.is_active():
            try:
                sub.use_ai_analysis()
            except Exception:
                logger.exception('revisão: falha ao contar a análise')

        nota_geral = _nota(result.overall_score)
        r = revisao.registar_fala(request.user, d, exercicio_id, bool(result.is_acceptable), nota_geral,
                                  request.data.get('segundos'))
        r['analise'] = {'nota': nota_geral, 'aceite': bool(result.is_acceptable),
                        'transcricao': str(result.transcribed_text or '')[:500],
                        'palavras': _lista_textos(result.problematic_words, chars=60),
                        'mensagem': str(result.feedback or '')[:500] or None}
        return Response(r)


class Terminar(Base):
    def post(self, request):
        inicio = parse_datetime(str(request.data.get('inicio') or '')) if request.data.get('inicio') else None
        if inicio is not None and inicio.tzinfo is None:
            inicio = None
        return Response(revisao.terminar(request.user, inicio))
