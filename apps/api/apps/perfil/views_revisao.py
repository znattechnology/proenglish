"""
Revisão de hoje (só alunos). Montado em /api/v1/student/revisao/.

  GET  resumo/      {para_rever, minutos, feitas_hoje}         cartões do laboratório e do painel
  GET  hoje/        sessão de hoje (até 12 exercícios)
  POST responder/   {exercicio_id, forma, resposta, segundos, pistas}
  POST falar/       multipart {exercicio_id, audio, segundos}   análise de pronúncia + resposta
  POST saltar/      {exercicio_id}                              saltar um exercício falado (sem pontos)
  POST terminar/    {inicio}                                    resumo do fim

As gravações (falar/ aqui e o "Repetir em voz alta" das aulas) contam para o limite diário de
análises com IA do plano (sem assinatura activa: o do plano Gratuito, contado pelas gravações de
hoje). Com o limite atingido, a análise em baixo ou sem microfone, o exercício pode ser saltado
(saltar/): sem pontos e sem nota.
"""
import io
import logging

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


def estado_analises(user):
    """
    (pode_analisar, assinatura_activa_ou_None) para a revisão e o "Repetir em voz alta" das aulas.
    Sem assinatura activa (sem registo, ou expirada) aplica-se o limite do plano Gratuito, contado
    pelas gravações de hoje (Luanda) da revisão e das aulas.
    """
    from apps.practice.limite_licoes import hoje_luanda, inicio_do_dia
    from apps.practice.models import TentativaPronuncia
    from apps.subscriptions.models import SubscriptionPlan, UserSubscription
    sub = UserSubscription.objects.select_related('plan').filter(user=user).first()
    if sub is not None and sub.is_active():
        return sub.can_use_ai_analysis(), sub
    limite = SubscriptionPlan.objects.filter(plan_type='FREE').values_list('daily_ai_analyses_limit', flat=True).first()
    if not limite:  # ilimitado (a convenção do plano), ou sem plano Gratuito configurado
        return True, None
    usadas = TentativaPronuncia.objects.filter(
        user=user, origem__in=(TentativaPronuncia.ORIGEM_REVISAO, TentativaPronuncia.ORIGEM_AULA),
        criada_em__gte=inicio_do_dia(hoje_luanda())).count()
    return usadas < limite, None


def contar_analise(sub, onde='revisão'):
    if sub is None:
        return  # sem assinatura activa: conta a própria TentativaPronuncia
    try:
        sub.use_ai_analysis()
    except Exception:
        logger.exception('%s: falha ao contar a análise', onde)


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


def _analisar(audio_bytes, frase, user=None, mime='audio/webm'):
    """(resultado, simulada): services/pronuncia (detalhada dentro do limite do plano, senão pelo
    texto; o mesmo modo simulado das lições)."""
    from apps.practice.services import pronuncia
    r = pronuncia.avaliar(audio_bytes, mime or 'audio/webm', frase, user=user)
    return r, r.fonte == 'simulada'


def _guardar_tentativa(user, result, simulada, origem='revisao'):
    from apps.practice.models import TentativaPronuncia
    from apps.practice.services.pronuncia import campos_tentativa
    from apps.practice.views_ai import _lista_textos, _nota
    return TentativaPronuncia.objects.create(
        user=user, challenge=None, resposta=None,
        texto_esperado=str(result.expected_text or '')[:2000], transcricao=str(result.transcribed_text or '')[:2000],
        nota_pronuncia=_nota(result.pronunciation_score), nota_fluencia=_nota(result.fluency_score),
        nota_clareza=_nota(result.clarity_score), nota_geral=_nota(result.overall_score),
        palavras_problematicas=_lista_textos(result.problematic_words, chars=60),
        sugestoes=_lista_textos(result.suggestions, maximo=10), feedback=str(result.feedback or '')[:2000],
        aceite=bool(result.is_acceptable),
        fonte=TentativaPronuncia.FONTE_SIMULADA if simulada else TentativaPronuncia.FONTE_IA,
        origem=origem, **campos_tentativa(result))


def analise_publica(result, tentativa=None):
    """O bloco 'analise' das respostas da revisão e da aula (com as notas por palavra, se houver)."""
    from apps.practice.services import pronuncia
    from apps.practice.views_ai import _lista_textos, _nota
    return {'nota': _nota(result.overall_score), 'aceite': bool(result.is_acceptable),
            'transcricao': str(result.transcribed_text or '')[:500],
            'palavras': _lista_textos(result.problematic_words, chars=60),
            'mensagem': str(result.feedback or '')[:500] or None,
            # 'texto': análise aproximada (só as palavras ouvidas); 'azure': detalhada; 'simulada'.
            'fonte': getattr(result, 'fonte', 'texto'),
            'detalhe': pronuncia.detalhe_publico(result),
            'fala': pronuncia.fala_publica(tentativa)}


def _indisponivel():
    return Response({'codigo': 'analise_indisponivel', 'pode_saltar': True,
                     'mensagem': 'Não conseguimos analisar a gravação agora. Pode saltar este exercício.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE)


class Falar(Base):
    def get_throttles(self):
        from apps.practice.views_ai import AIAnaliseThrottle
        return [AIAnaliseThrottle()]

    def post(self, request):
        from apps.practice.services import gravacao
        from apps.practice.views_ai import _nota

        exercicio_id = request.data.get('exercicio_id')
        try:
            d = revisao.definicao(request.user, exercicio_id, revisao.OUVIR)
        except revisao.ExercicioInvalido:
            return _invalido()
        audio = request.FILES.get('audio')
        if not audio:
            return Response({'codigo': 'audio_em_falta', 'mensagem': 'Grave a frase antes de enviar.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if gravacao.demasiado_grande(audio):
            return gravacao.resposta_grande()
        frase = d['texto']

        pode, sub = estado_analises(request.user)
        if not pode:
            return Response({'codigo': 'limite_analises', 'pode_saltar': True,
                             'mensagem': 'Já usou as análises de pronúncia de hoje. Pode saltar este exercício: '
                                         'não perde nada e a frase volta amanhã.'},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
        try:
            dados = io.BytesIO(audio.read())
            dados.name = audio.name
            result, simulada = _analisar(dados, frase, request.user, getattr(audio, 'content_type', None))
        except Exception:
            logger.exception('revisão: análise de pronúncia falhou')
            return _indisponivel()
        if getattr(result, 'indisponivel', False) is True:
            return _indisponivel()
        sem_avaliacao = gravacao.resposta_do_resultado(result)
        if sem_avaliacao is not None:
            return sem_avaliacao
        tentativa = None
        try:
            tentativa = _guardar_tentativa(request.user, result, simulada)
        except Exception:
            logger.exception('revisão: falha ao guardar a tentativa de pronúncia')
        contar_analise(sub)

        nota_geral = _nota(result.overall_score)
        r = revisao.registar_fala(request.user, d, exercicio_id, bool(result.is_acceptable), nota_geral,
                                  request.data.get('segundos'))
        r['analise'] = analise_publica(result, tentativa)
        return Response(r)


class Saltar(Base):
    """Saltar um exercício falado (sem microfone, sem análises, análise em baixo): sem pontos."""
    throttle_classes = [LimiteRevisao]

    def post(self, request):
        try:
            return Response(revisao.saltar(request.user, request.data.get('exercicio_id')))
        except revisao.ExercicioInvalido:
            return _invalido()


class Terminar(Base):
    def post(self, request):
        inicio = parse_datetime(str(request.data.get('inicio') or '')) if request.data.get('inicio') else None
        if inicio is not None and inicio.tzinfo is None:
            inicio = None
        return Response(revisao.terminar(request.user, inicio))
