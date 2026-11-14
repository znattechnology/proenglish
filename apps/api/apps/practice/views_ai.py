"""
AI Views for Practice App

Contains AI-powered endpoints for:
- Translation validation and suggestions
- Pronunciation analysis and reference audio generation

These views use external AI services (OpenAI, etc.) for intelligent analysis.
"""

import io
import logging
import uuid
import asyncio

from django.utils import timezone
from django.http import HttpResponse
from django.conf import settings

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .permissions import IsTeacher
from rest_framework import status as status_module
from rest_framework.throttling import UserRateThrottle
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import PracticeChallenge, UserProgress, ChallengeProgress

logger = logging.getLogger(__name__)


# =============================================================================
# AI TRANSLATION ENDPOINTS
# =============================================================================

class AIAnaliseThrottle(UserRateThrottle):
    """Análises com IA (pronúncia e tradução) custam dinheiro: no máximo 20 por minuto por pessoa."""
    rate = '20/minute'
    scope = 'ai_analise'


class AIGeracaoThrottle(UserRateThrottle):
    """Geração de conteúdo com IA para professores (sugestões, exercícios, áudio): 30 por hora por pessoa."""
    rate = '30/hour'
    scope = 'ai_geracao'


NIVEIS = ('beginner', 'intermediate', 'advanced')
VOZES = ('alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer')
TIPOS_EXERCICIO_PRONUNCIA = ('word', 'sentence', 'paragraph')


def _erro(codigo, mensagem, estado=status_module.HTTP_400_BAD_REQUEST, detalhes=None):
    return Response({'error': codigo, 'message': mensagem, 'code': codigo, 'details': detalhes or []},
                    status=estado)


def _texto(request, campo, maximo):
    valor = request.data.get(campo) if hasattr(request.data, 'get') else None
    if valor is None:
        return ''
    if not isinstance(valor, str):
        return None
    valor = valor.strip()
    return valor if len(valor) <= maximo else None


def _nivel(request):
    nivel = request.data.get('difficulty_level', 'intermediate') if hasattr(request.data, 'get') else 'intermediate'
    return nivel if nivel in NIVEIS else None


def _exercicio_do_aluno(challenge_id, tipo, user=None):
    """
    O exercício `challenge_id`, se for do tipo `tipo` e o aluno o puder abrir no ecrã da lição
    (a mesma regra do jogar/: a lição tem de ser de um curso publicado).
    Devolve (exercicio, None) ou (None, Response de erro).
    """
    if not challenge_id:
        return None, Response({'error': 'challenge_required', 'message': 'Indique o exercício.'},
                              status=status_module.HTTP_400_BAD_REQUEST)
    try:
        exercicio = (PracticeChallenge.objects
                     .select_related('lesson', 'lesson__unit', 'lesson__unit__course')
                     .prefetch_related('options')
                     .get(id=challenge_id, lesson__unit__course__status__in=('Published', 'Archived')))
    except (PracticeChallenge.DoesNotExist, ValueError, DjangoValidationError):
        return None, Response({'error': 'challenge_not_found', 'message': 'Não encontrámos este exercício.'},
                              status=status_module.HTTP_404_NOT_FOUND)
    if exercicio.type != tipo:
        return None, Response({'error': 'challenge_type', 'message': 'Este exercício não é deste tipo.'},
                              status=status_module.HTTP_400_BAD_REQUEST)
    if user is not None:
        # Ordem do trilho e plano do curso (como jogar/ e challenge-progress/).
        from .acesso_licoes import erro_acesso_licao
        erro = erro_acesso_licao(user, exercicio.lesson)
        if erro:
            return None, Response(erro, status=status_module.HTTP_403_FORBIDDEN)
    return exercicio, None


def _analise_indisponivel(user, challenge):
    """
    503 quando a análise de pronúncia não está disponível. Não tira vidas nem conta como erro;
    traz um token para saltar o exercício (POST challenge-progress/ com saltar=true).
    """
    from .saltar_pronuncia import gerar_token
    return Response(
        {'codigo': 'analise_indisponivel',
         'error': 'analysis_unavailable',
         'mensagem': 'Não conseguimos analisar a gravação agora. Tente outra vez ou salte este exercício.',
         'message': 'Não conseguimos analisar a gravação agora. Tente outra vez ou salte este exercício.',
         'pode_saltar': True,
         'token_saltar': gerar_token(user, challenge)},
        status=status_module.HTTP_503_SERVICE_UNAVAILABLE,
    )


def frase_para_dizer(exercicio):
    """A frase de um exercício SPEAKING: a pergunta (ou a 1.ª opção, em exercícios antigos), como no jogar/."""
    if (exercicio.question or '').strip():
        return exercicio.question.strip()
    opcoes = sorted(exercicio.options.all(), key=lambda o: o.order)
    return (opcoes[0].text or '').strip() if opcoes else ''


class AITranslationValidationView(APIView):
    """
    POST /api/v1/practice/validate-ai-translation/  {challenge_id, user_translation}

    Dá a opinião da IA sobre uma tradução de um exercício TRANSLATION. Só devolve o veredicto:
    não mexe em vidas, pontos nem no progresso. A resposta conta (e dá pontos/vidas segundo as
    regras normais) quando é enviada para challenge-progress/.

    O texto de partida é sempre o do exercício na base de dados; `source_text` enviado pelo
    cliente é ignorado.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [AIAnaliseThrottle]

    def post(self, request):
        from .services.ai_translation import AITranslationValidator

        user_translation = str(request.data.get('user_translation') or '').strip()[:2000]
        difficulty_level = request.data.get('difficulty_level', 'intermediate')
        if difficulty_level not in ('beginner', 'intermediate', 'advanced'):
            difficulty_level = 'intermediate'

        challenge, erro = _exercicio_do_aluno(request.data.get('challenge_id'), 'TRANSLATION', request.user)
        if erro:
            return erro
        source_text = (challenge.question or '').strip()
        if not user_translation or not source_text:
            return Response({'error': 'translation_required', 'message': 'Escreva a sua tradução.'},
                            status=status_module.HTTP_400_BAD_REQUEST)

        try:
            validator = AITranslationValidator()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    validator.validate_translation(
                        source_text=source_text,
                        user_translation=user_translation,
                        difficulty_level=difficulty_level
                    )
                )
            finally:
                loop.close()
        except Exception as e:
            print(f"AI Translation validation error: {e}")
            return Response({'error': 'analysis_unavailable',
                             'message': 'Não conseguimos analisar a tradução agora. Tente outra vez.'},
                            status=status_module.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({
            'success': True,
            'ai_validation': {
                'semantic_score': result.semantic_score,
                'fluency_score': result.fluency_score,
                'fidelity_score': result.fidelity_score,
                'overall_score': result.overall_score,
                'is_acceptable': result.is_acceptable,
                'partial_credit': result.partial_credit
            },
            'feedback': {
                'message': result.feedback,
                'explanation': result.explanation,
                'suggestions': result.suggestions
            },
            'user_answer': user_translation,
            'source_text': source_text,
        }, status=status_module.HTTP_200_OK)


class GenerateTranslationSuggestionsView(APIView):
    """
    POST /api/v1/practice/generate-translation-suggestions/

    Generate multiple correct translation alternatives for teachers
    """
    permission_classes = [IsAuthenticated, IsTeacher]  # só professores e administradores
    throttle_classes = [AIGeracaoThrottle]

    def post(self, request):
        """Generate translation alternatives using AI"""
        from .services.ai_translation import AITranslationValidator

        # Validar tudo antes de chamar a IA (custa dinheiro).
        source_text = _texto(request, 'source_text', 1000)
        if not source_text:
            return _erro('dados_invalidos', 'Indique o texto a traduzir (até 1000 caracteres).',
                         detalhes=[{'campo': 'source_text', 'mensagem': 'Obrigatório, até 1000 caracteres.'}])
        difficulty_level = _nivel(request)
        if difficulty_level is None:
            return _erro('dados_invalidos', 'Nível inválido.',
                         detalhes=[{'campo': 'difficulty_level', 'mensagem': 'Use beginner, intermediate ou advanced.'}])
        try:
            count = int(request.data.get('count', 3))
        except (TypeError, ValueError):
            count = 0
        if not 1 <= count <= 5:
            return _erro('dados_invalidos', 'Pode pedir entre 1 e 5 sugestões.',
                         detalhes=[{'campo': 'count', 'mensagem': 'Entre 1 e 5.'}])

        try:
            validator = AITranslationValidator()

            # Run async operation in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                suggestions = loop.run_until_complete(
                    validator.generate_translation_suggestions(
                        source_text=source_text,
                        difficulty_level=difficulty_level,
                        count=count
                    )
                )
            finally:
                loop.close()

            return Response({
                'success': True,
                'source_text': source_text,
                'suggestions': suggestions,
                'difficulty_level': difficulty_level
            })

        except Exception as e:
            logger.exception("Erro a gerar sugestões de tradução: %s", e)
            return _erro('ia_indisponivel', 'Não conseguimos gerar sugestões agora. Tente outra vez.',
                         estado=status_module.HTTP_503_SERVICE_UNAVAILABLE)


# =============================================================================
# AI PRONUNCIATION ENDPOINTS
# =============================================================================

class GeneratePronunciationExerciseView(APIView):
    """
    POST /api/v1/practice/generate-pronunciation-exercise/

    Generate pronunciation exercise with AI
    """
    permission_classes = [IsAuthenticated, IsTeacher]  # só professores e administradores
    throttle_classes = [AIGeracaoThrottle]

    def post(self, request):
        """Generate pronunciation exercise using AI"""
        from .services.ai_pronunciation import AIPronunciationAnalyzer

        # Validar tudo antes de chamar a IA (custa dinheiro); corpo vazio -> 400.
        topic = _texto(request, 'topic', 200)
        if not topic:
            return _erro('dados_invalidos', 'Indique o tema do exercício (até 200 caracteres).',
                         detalhes=[{'campo': 'topic', 'mensagem': 'Obrigatório, até 200 caracteres.'}])
        difficulty_level = _nivel(request)
        if difficulty_level is None:
            return _erro('dados_invalidos', 'Nível inválido.',
                         detalhes=[{'campo': 'difficulty_level', 'mensagem': 'Use beginner, intermediate ou advanced.'}])
        exercise_type = request.data.get('exercise_type', 'sentence')
        if exercise_type not in TIPOS_EXERCICIO_PRONUNCIA:
            return _erro('dados_invalidos', 'Tipo de exercício inválido.',
                         detalhes=[{'campo': 'exercise_type', 'mensagem': 'Use word, sentence ou paragraph.'}])

        try:
            analyzer = AIPronunciationAnalyzer()

            # Run async operation in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                exercise_data = loop.run_until_complete(
                    analyzer.generate_pronunciation_exercise(
                        topic=topic,
                        difficulty_level=difficulty_level,
                        exercise_type=exercise_type
                    )
                )
            finally:
                loop.close()

            return Response({
                'success': True,
                'exercise': exercise_data,
                'generated_at': timezone.now(),
                'parameters': {
                    'topic': topic,
                    'difficulty_level': difficulty_level,
                    'exercise_type': exercise_type
                }
            })

        except Exception as e:
            logger.exception("Erro a gerar exercício de pronúncia: %s", e)
            return _erro('ia_indisponivel', 'Não conseguimos gerar o exercício agora. Tente outra vez.',
                         estado=status_module.HTTP_503_SERVICE_UNAVAILABLE)


class GenerateReferenceAudioView(APIView):
    """
    POST /api/v1/practice/generate-reference-audio/

    Generate reference audio pronunciation using TTS.
    If save_to_s3=true, uploads to S3 and returns URL.
    Otherwise returns audio binary directly.
    """
    permission_classes = [IsAuthenticated, IsTeacher]  # só professores e administradores
    throttle_classes = [AIGeracaoThrottle]

    def post(self, request):
        """Generate reference audio for pronunciation practice"""
        import boto3
        from .services.ai_pronunciation import AIPronunciationAnalyzer

        # Validar tudo antes de chamar o TTS (custa dinheiro); corpo vazio -> 400.
        text = _texto(request, 'text', 1000)
        if not text:
            return _erro('dados_invalidos', 'Indique o texto a ler (até 1000 caracteres).',
                         detalhes=[{'campo': 'text', 'mensagem': 'Obrigatório, até 1000 caracteres.'}])
        voice = request.data.get('voice', 'alloy')
        if voice not in VOZES:
            return _erro('dados_invalidos', 'Voz inválida.',
                         detalhes=[{'campo': 'voice', 'mensagem': 'Use ' + ', '.join(VOZES) + '.'}])
        save_to_s3 = request.data.get('save_to_s3', False) in (True, 'true', '1', 1)
        # Só entra no nome do ficheiro: letras, números e hífenes (o editor pode mandar ids temporários).
        import re
        challenge_id = re.sub(r'[^A-Za-z0-9-]', '', str(request.data.get('challenge_id') or ''))[:64]

        try:
            analyzer = AIPronunciationAnalyzer()

            # Use sync version directly to avoid async issues
            audio_bytes = analyzer.generate_reference_audio_sync(text=text, voice=voice)

            if not audio_bytes or len(audio_bytes) == 0:
                print(f"TTS returned empty audio bytes for text: {text[:50]}...")
                return Response(
                    {'error': 'Failed to generate audio - empty response from TTS'},
                    status=status_module.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # If save_to_s3 is requested, upload to S3 and return URL
            if save_to_s3:
                try:
                    s3_client = boto3.client(
                        's3',
                        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                        region_name=settings.AWS_S3_REGION_NAME
                    )

                    # Generate unique filename
                    unique_id = uuid.uuid4().hex[:8]
                    filename = f"reference-audio/{challenge_id or 'general'}/{unique_id}.mp3"

                    # Upload to S3
                    s3_client.put_object(
                        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                        Key=filename,
                        Body=audio_bytes,
                        ContentType='audio/mpeg'
                    )

                    # Generate a presigned URL for reading (valid for 1 year)
                    audio_url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={
                            'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                            'Key': filename
                        },
                        ExpiresIn=31536000  # 1 year in seconds
                    )

                    return Response({
                        'success': True,
                        'audio_url': audio_url,
                        'message': 'Reference audio generated and saved to S3'
                    })

                except Exception as s3_error:
                    print(f"S3 upload error: {s3_error}")
                    return _erro('armazenamento_indisponivel', 'Não conseguimos guardar o áudio agora. Tente outra vez.',
                                 estado=status_module.HTTP_503_SERVICE_UNAVAILABLE)

            # Return audio file directly (original behavior)
            response = HttpResponse(audio_bytes, content_type='audio/mpeg')
            response['Content-Disposition'] = f'attachment; filename="reference_{hash(text)}.mp3"'
            return response

        except Exception as e:
            logger.exception("Erro a gerar áudio de referência: %s", e)
            return _erro('ia_indisponivel', 'Não conseguimos gerar o áudio agora. Tente outra vez.',
                         estado=status_module.HTTP_503_SERVICE_UNAVAILABLE)


class AIPronunciationAnalysisView(APIView):
    """
    POST /api/v1/practice/analyze-ai-pronunciation/

    Analyze student pronunciation using AI (Whisper + GPT-4).

    Request:
        - audio: Audio file (multipart/form-data)
        - challenge_id: SPEAKING challenge (required); the sentence comes from the DB
        - expected_text: ignored (kept for older clients)
        - difficulty_level: 'beginner', 'intermediate', or 'advanced'

    Response:
        - ai_analysis: Detailed pronunciation analysis scores
        - feedback: Suggestions and problematic words
        - user_progress: Updated hearts and points
        - ai_analyses_remaining: Remaining AI analyses for today
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [AIAnaliseThrottle]

    def post(self, request):
        """Analyze pronunciation using AI with detailed feedback"""
        from .services.ai_pronunciation import AIPronunciationAnalyzer
        from apps.subscriptions.models import UserSubscription

        # Extract request data
        # Support both 'audio' and 'audio_file' for compatibility
        audio_file = request.FILES.get('audio') or request.FILES.get('audio_file')
        difficulty_level = request.data.get('difficulty_level', 'intermediate')
        if difficulty_level not in ('beginner', 'intermediate', 'advanced'):
            difficulty_level = 'intermediate'

        # A frase vem sempre do exercício na base de dados (o `expected_text` que o cliente
        # envia é ignorado) e o exercício tem de ser SPEAKING de uma lição que o aluno pode abrir.
        challenge, erro = _exercicio_do_aluno(request.data.get('challenge_id'), 'SPEAKING', request.user)
        if erro:
            return erro
        expected_text = frase_para_dizer(challenge)
        if not audio_file:
            return Response({'error': 'audio_required', 'message': 'Grave a frase antes de enviar.'},
                            status=status_module.HTTP_400_BAD_REQUEST)
        if not expected_text:
            return Response({'error': 'challenge_type', 'message': 'Este exercício não tem frase para dizer.'},
                            status=status_module.HTTP_400_BAD_REQUEST)

        # Check AI analyses limit from subscription
        ai_analyses_remaining = -1  # -1 = unlimited
        try:
            subscription = UserSubscription.objects.select_related('plan').get(user=request.user)
            if subscription.is_active():
                if not subscription.can_use_ai_analysis():
                    return Response(
                        {
                            'error': 'ai_limit',
                            'message': 'Limite diário de análises AI atingido',
                            'ai_analyses_remaining': 0,
                            'limit': subscription.plan.daily_ai_analyses_limit
                        },
                        status=status_module.HTTP_429_TOO_MANY_REQUESTS
                    )
                ai_analyses_remaining = subscription.get_ai_analyses_remaining()
        except UserSubscription.DoesNotExist:
            # No subscription - use default limit of 5
            pass

        # Get user progress for hearts/points management
        user_progress, created = UserProgress.objects.get_or_create(
            user=request.user,
            defaults={'hearts': 5, 'points': 0}
        )

        # Check if this is practice mode (challenge already completed)
        existing_progress = ChallengeProgress.objects.filter(
            user=request.user,
            challenge=challenge
        ).first()
        is_practice = existing_progress is not None

        # Check hearts for new challenges
        if not is_practice and user_progress.hearts == 0:
            return Response(
                {'error': 'hearts', 'message': 'No hearts remaining'},
                status=status_module.HTTP_400_BAD_REQUEST
            )

        try:
            # Convert uploaded file to BytesIO
            audio_bytes = io.BytesIO(audio_file.read())
            audio_bytes.name = audio_file.name

            from django.conf import settings as dj_settings
            if getattr(dj_settings, 'PRONUNCIA_SIMULADA', False) and dj_settings.DEBUG:
                # Desenvolvimento sem OpenAI: aceita qualquer gravação com som (> 2 KB).
                from types import SimpleNamespace
                aceitavel = audio_bytes.getbuffer().nbytes > 2048
                result = SimpleNamespace(
                    transcribed_text=expected_text if aceitavel else '',
                    expected_text=expected_text,
                    pronunciation_score=82 if aceitavel else 20,
                    fluency_score=80 if aceitavel else 20,
                    clarity_score=84 if aceitavel else 20,
                    overall_score=82 if aceitavel else 20,
                    is_acceptable=aceitavel,
                    partial_credit=10 if aceitavel else 0,
                    confidence_level='simulado',
                    feedback='Análise simulada (desenvolvimento sem IA).' if aceitavel else 'Não ouvimos nada. Grave outra vez.',
                    problematic_words=[],
                    suggestions=[],
                )
            else:
                # Analyze pronunciation using AI
                analyzer = AIPronunciationAnalyzer()

                # Run async analysis in sync context
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(
                        analyzer.analyze_pronunciation(
                            audio_file=audio_bytes,
                            expected_text=expected_text,
                            difficulty_level=difficulty_level
                        )
                    )
                finally:
                    loop.close()

            # Sem transcrição não houve avaliação: é uma falha técnica, não tira vidas nem conta como erro.
            if getattr(result, 'indisponivel', False):
                return _analise_indisponivel(request.user, challenge)

            # Process results and update progress
            response_data = {
                'success': True,
                'ai_analysis': {
                    'transcribed_text': result.transcribed_text,
                    'expected_text': result.expected_text,
                    'pronunciation_score': result.pronunciation_score,
                    'fluency_score': result.fluency_score,
                    'clarity_score': result.clarity_score,
                    'overall_score': result.overall_score,
                    'is_acceptable': result.is_acceptable,
                    'partial_credit': result.partial_credit,
                    'confidence_level': result.confidence_level
                },
                'feedback': {
                    'message': result.feedback,
                    'problematic_words': result.problematic_words,
                    'suggestions': result.suggestions
                }
            }

            # Update challenge progress if challenge provided
            if challenge and result.is_acceptable:
                if existing_progress:
                    existing_progress.completed = True
                    existing_progress.save()
                    progress = existing_progress
                else:
                    progress = ChallengeProgress.objects.create(
                        user=request.user,
                        challenge=challenge,
                        completed=True
                    )

                response_data['challenge_progress'] = {
                    'id': str(progress.id),
                    'completed': progress.completed,
                    'completed_at': progress.completed_at
                }

            # Update user progress based on AI result
            if result.is_acceptable:
                # Prática repetida: sem pontos nem vidas por exercício (a recompensa é dada
                # uma vez por lição em complete-lesson/).
                points_earned = 0 if is_practice else result.partial_credit
                if points_earned:
                    user_progress.add_points(points_earned, reason='ai_practice')

                response_data['points_earned'] = points_earned
                response_data['explicacao'] = (challenge.explanation or None) if challenge else None
            else:
                # Incorrect pronunciation: reduce hearts if not practice
                if not is_practice and user_progress.hearts > 0:
                    user_progress.reduce_hearts()

                response_data['points_earned'] = 0
                response_data['dica'] = (challenge.hint or None) if challenge else None

            # Add current user progress to response
            response_data['user_progress'] = {
                'hearts': user_progress.hearts,
                'points': user_progress.points
            }

            # Use one AI analysis and update remaining count
            try:
                subscription = UserSubscription.objects.select_related('plan').get(user=request.user)
                if subscription.is_active():
                    subscription.use_ai_analysis()
                    ai_analyses_remaining = subscription.get_ai_analyses_remaining()
            except UserSubscription.DoesNotExist:
                pass

            # Add AI analyses remaining to response
            response_data['ai_analyses_remaining'] = ai_analyses_remaining

            return Response(response_data, status=status_module.HTTP_200_OK)

        except Exception as e:
            logger.exception("AI Pronunciation analysis error: %s", e)
            return _analise_indisponivel(request.user, challenge)
