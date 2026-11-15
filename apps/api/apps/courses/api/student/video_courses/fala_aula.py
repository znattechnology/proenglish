"""
Falar depois do vídeo de uma aula (fase 5). Montado em /api/v1/student/video-courses/.

  GET  chapters/<id>/fala/                       {frases:[...], conversa:{disponivel, motivo, mensagem, max_segundos}}
  POST chapters/<id>/frases/<frase>/falar/       multipart {audio, segundos} -> análise de pronúncia
  POST chapters/<id>/conversa/                   começa a conversa de 3 minutos com o tutor

As mesmas regras de acesso do detalhe da aula (inscrição activa, plano, aula visível, curso aberto).
Só as frases aprovadas pelo professor (FraseAula.APROVADA) chegam aqui.

"Repetir em voz alta": a análise é a da revisão (views_revisao._analisar: Whisper + nota, ou o modo
simulado em desenvolvimento), conta para o limite diário de análises do plano e fica em
TentativaPronuncia (com as métricas de fluência e, dentro do limite do plano, a avaliação detalhada).
Gravação aceite -> a frase fica 'com_ajuda' no banco (o aluno repetiu-a com o
modelo do vídeo: ainda não a disse sozinho).

A conversa usa o serviço normal (conversa/servico.criar_sessao) com a situação "aula-<hex>"
(conversa/aula.py): gasta os minutos de conversa do dia; sem minutos responde 403 com
alternativa "revisao" (o ecrã propõe a revisão de hoje). Termina-se com
POST /practice/conversa/sessoes/<id>/terminar/, como as outras.
"""
import io
import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses import ciclo, frases_aula
from apps.courses.models import Chapter, FraseAula

from .views import EnrollmentRequiredMixin

logger = logging.getLogger(__name__)


class _BaseAula(EnrollmentRequiredMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def aula(self):
        chapter = get_object_or_404(
            Chapter.objects.filter(ciclo.q_conteudo_aluno('section__course__'), ciclo.q_aula_visivel(),
                                   section__course__course_type='video').select_related('section__course'),
            id=self.kwargs['chapterId'])
        self.check_enrollment(self.get_course_from_chapter(chapter))
        return chapter


def _estados_banco(user, frases):
    from apps.perfil.models import ItemBanco
    from apps.perfil.servico import normalizar
    chaves = {normalizar(f.texto): f.pk for f in frases}
    return {chaves[c]: e for c, e in ItemBanco.objects.filter(user=user, chave__in=list(chaves))
            .values_list('chave', 'estado')}


def _estado_conversa(user, chapter, frases):
    from apps.practice.conversa.quota import MENSAGENS, estado_quota
    if not any(f.tipo == FraseAula.TIPO_FRASE for f in frases):
        return {'disponivel': False, 'motivo': 'sem_frases', 'mensagem': 'Esta aula ainda não tem frases para usar numa conversa.',
                'max_segundos': 0}
    try:
        q = estado_quota(user)
    except Exception:
        logger.exception('aula: falha ao ler a quota de conversa')
        return {'disponivel': True, 'motivo': None, 'mensagem': None,
                'max_segundos': settings.CONVERSA_AULA_MAX_SEGUNDOS}
    if not q['pode_comecar']:
        return {'disponivel': False, 'motivo': q['motivo'], 'mensagem': MENSAGENS.get(q['motivo']), 'max_segundos': 0}
    return {'disponivel': True, 'motivo': None, 'mensagem': None,
            'max_segundos': min(settings.CONVERSA_AULA_MAX_SEGUNDOS, q['max_minutos_sessao'] * 60)}


class FalaDaAula(_BaseAula):
    def get(self, request, chapterId):
        chapter = self.aula()
        frases = frases_aula.aprovadas(chapter)
        estados = _estados_banco(request.user, frases)
        return Response({
            'frases': [{'id': f.pk, 'texto': f.texto, 'traducao': f.traducao, 'tipo': f.tipo,
                        'inicio': f.inicio, 'fim': f.fim, 'estado': estados.get(f.pk)} for f in frases],
            'conversa': _estado_conversa(request.user, chapter, frases),
        })


class FalarFrase(_BaseAula):
    def get_throttles(self):
        from apps.practice.views_ai import AIAnaliseThrottle
        return [AIAnaliseThrottle()]

    def post(self, request, chapterId, fraseId):
        from apps.perfil.models import ItemBanco
        from apps.perfil.servico import registar_item
        from apps.perfil.views_revisao import (_analisar, _guardar_tentativa, _indisponivel, analise_publica,
                                               contar_analise, estado_analises, oferta_analises)
        from apps.practice.services import gravacao

        chapter = self.aula()
        frase = FraseAula.objects.filter(pk=fraseId, chapter=chapter, estado=FraseAula.APROVADA).first()
        if frase is None:
            return Response({'codigo': 'frase_invalida', 'mensagem': 'Esta frase já não existe.'},
                            status=status.HTTP_404_NOT_FOUND)
        audio = request.FILES.get('audio')
        if not audio:
            return Response({'codigo': 'audio_em_falta', 'mensagem': 'Grave a frase antes de enviar.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if gravacao.demasiado_grande(audio):
            return gravacao.resposta_grande()
        # Limite diário de análises (sem assinatura activa: o do Gratuito). Atingido: a frase pode
        # ser saltada (não há progresso nem vidas a perder; passa-se à seguinte).
        pode, sub = estado_analises(request.user)
        if not pode:
            return Response({'codigo': 'limite_analises', 'pode_saltar': True,
                             'mensagem': 'Já usou as análises de pronúncia de hoje. Pode passar à frase seguinte '
                                         'sem perder nada; amanhã há mais.',
                             'oferta': oferta_analises(request.user, sub)},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
        try:
            dados = io.BytesIO(audio.read())
            dados.name = audio.name
            result, simulada = _analisar(dados, frase.texto, request.user, getattr(audio, 'content_type', None))
        except Exception:
            logger.exception('aula: análise de pronúncia falhou')
            return _indisponivel()
        if getattr(result, 'indisponivel', False) is True:
            return _indisponivel()
        sem_avaliacao = gravacao.resposta_do_resultado(result)
        if sem_avaliacao is not None:
            return sem_avaliacao
        tentativa = None
        try:
            tentativa = _guardar_tentativa(request.user, result, simulada, origem='aula')
        except Exception:
            logger.exception('aula: falha ao guardar a tentativa de pronúncia')
        contar_analise(sub, 'aula')

        aceite = bool(result.is_acceptable)
        item = registar_item(request.user, frase.texto, frase.traducao,
                             estado=ItemBanco.COM_AJUDA if aceite else ItemBanco.VISTA, origem='aula',
                             capitulo_id=chapter.pk, curso_id=chapter.section.course_id)
        return Response({
            'analise': analise_publica(result, tentativa),
            'estado': item.estado if item is not None else None,
        })


class ConversaDaAula(_BaseAula):
    def get_throttles(self):
        from apps.practice.conversa.views import LimiteSessoes
        return [LimiteSessoes()]

    def post(self, request, chapterId):
        from apps.courses.api.student.practice_courses.conversa_licao import _preferencias
        from apps.practice.conversa import aula as conversa_aula
        from apps.practice.conversa import servico
        from apps.practice.conversa.servico import ErroConversa

        chapter = self.aula()
        frases = conversa_aula.frases_da_aula(chapter)
        if not frases:
            return Response({'codigo': 'sem_frases', 'alternativa': 'revisao',
                             'mensagem': 'Esta aula ainda não tem frases para usar numa conversa.'},
                            status=status.HTTP_409_CONFLICT)
        try:
            frases_aula.registar_vistas(request.user, chapter)  # origem 'aula' antes da conversa as semear
        except Exception:
            logger.exception('aula: falha ao registar as frases antes da conversa')
        try:
            sessao = servico.criar_sessao(
                request.user, _preferencias(request.user),
                situacao=conversa_aula.situacao_da_aula(chapter),
                objectivos=conversa_aula.objectivos(request.user, chapter, frases),
                max_segundos=settings.CONVERSA_AULA_MAX_SEGUNDOS,
                config_extra={'capitulo_id': str(chapter.pk)},
            )
        except ErroConversa as e:
            return Response({'codigo': e.codigo, 'mensagem': e.mensagem, 'alternativa': 'revisao'}, status=e.status)
        vapi = servico.config_vapi()
        return Response({'sessao': sessao, 'modo': servico.modo(), 'chave_publica': vapi['public_key'] if vapi else None},
                        status=status.HTTP_201_CREATED)
