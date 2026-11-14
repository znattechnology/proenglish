"""
Certificados de conclusão de curso: número, emissão, verificação pública e PDF.

Regras:
- Só planos com `certificates=True` (Premium, Premium Plus) e subscrição activa.
- O aluno tem de estar inscrito, ter 100% do curso concluído e cumprir os requisitos
  do GradeCalculatorService (inclui a nota final mínima, 70% por omissão, e passar no exame
  oral do curso: fase 6).
- O certificado mostra o nível de fala atingido no exame oral ("Nível de fala B1 em situações de
  trabalho de <área>") e as notas por competência (PDF e verificação pública).
- Número PE-C-<YYYY>-<NNNNNN>, sequencial por ano na hora de Angola (como os recibos
  PE-R-... de apps.pagamentos).
- A emissão é automática (signals: nota guardada elegível ou progresso a 100%) e também
  pode ser pedida pelo aluno (POST .../<courseId>/certificado/). É idempotente.
"""
import logging
import uuid
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

FUSO_ANGOLA = ZoneInfo('Africa/Luanda')
CAMINHO_VERIFICACAO = '/certificados/verificar/'


class CertificadoIndisponivel(Exception):
    """O certificado não pode ser emitido; `codigo` e `status` vão para a resposta da API."""

    def __init__(self, codigo, mensagem, status=400, detalhes=None):
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem
        self.status = status
        self.detalhes = detalhes or {}


def gerar_numero_certificado(quando=None):
    """PE-C-<YYYY>-<NNNNNN>, sequencial por ano (hora de Angola). Chamar dentro de atomic."""
    from apps.courses.models import SequenciaCertificado

    ano = timezone.localtime(quando or timezone.now(), FUSO_ANGOLA).year
    try:
        with transaction.atomic():
            SequenciaCertificado.objects.get_or_create(ano=ano)
    except IntegrityError:
        pass  # criado em paralelo
    seq = SequenciaCertificado.objects.select_for_update().get(ano=ano)
    seq.ultimo += 1
    seq.save(update_fields=['ultimo'])
    return f'PE-C-{ano}-{seq.ultimo:06d}'


def ligacao_verificacao(certificado):
    return f"{settings.FRONTEND_URL.rstrip('/')}{CAMINHO_VERIFICACAO}{certificado.certificate_number}"


def plano_inclui_certificados(user):
    from apps.subscriptions.models import UserSubscription

    sub = UserSubscription.objects.select_related('plan').filter(user=user).first()
    return bool(sub and sub.plan and sub.is_active() and sub.plan.certificates)


def progresso_actual(user, course):
    """
    % de capítulos concluídos calculado agora (capítulos concluídos que ainda existem / capítulos
    do curso). Não depende do overallProgress guardado, que podia ficar desactualizado quando o
    professor acrescentava ou apagava capítulos.
    """
    from apps.courses.ciclo import q_aula_visivel
    from apps.courses.models import Chapter, ChapterProgress

    # Só as aulas visíveis aos alunos: uma aula nova ainda sem vídeo não baixa o progresso.
    total = Chapter.objects.filter(q_aula_visivel(), section__course=course).count()
    if not total:
        return 0.0
    feitos = ChapterProgress.objects.filter(
        q_aula_visivel('chapter__'),
        user_progress__user=user, user_progress__course=course, completed=True,
        chapter__section__course=course).values('chapter_id').distinct().count()
    return min(100.0, feitos * 100.0 / total)


def _progresso(user, course):
    return progresso_actual(user, course)


def requisitos_em_falta(grade, progresso):
    """Lista do que falta para o certificado (formato estável para o frontend)."""
    em_falta = []
    if progresso < 100.0:
        em_falta.append({
            'requisito': 'conclusao_curso',
            'mensagem': f'Concluir todos os capítulos: {progresso:.0f}% concluído (necessário: 100%)',
            'necessario': 100,
            'atual': round(progresso, 1),
        })
    if grade is not None and not grade.is_eligible_for_certificate:
        for r in grade.get_missing_requirements():
            em_falta.append({
                'requisito': r['requirement'],
                'mensagem': r['message'],
                'necessario': r['required'],
                'atual': r['actual'],
            })
    return em_falta


def nota_minima(course):
    from apps.courses.models import CourseGradingConfig
    try:
        return course.grading_config.min_final_grade
    except CourseGradingConfig.DoesNotExist:
        return CourseGradingConfig._meta.get_field('min_final_grade').default


def estado_certificado(user, course, grade, progresso=None, plano_ok=None):
    """
    Fonte única do "pode ter certificado?" para as notas, a lista de certificados e a emissão:
    progresso a 100% + requisitos da nota (requisitos_em_falta) e o plano.

    - cumpre_requisitos: conclusão do curso e todos os requisitos da nota cumpridos
    - pode_emitir: cumpre_requisitos e o plano inclui certificados
    """
    progresso = _progresso(user, course) if progresso is None else progresso
    plano_ok = plano_inclui_certificados(user) if plano_ok is None else plano_ok
    em_falta = requisitos_em_falta(grade, progresso)
    return {
        'cumpre_requisitos': not em_falta,
        'pode_emitir': bool(plano_ok and not em_falta),
        'em_falta': em_falta,
        'progresso': round(progresso, 1),
        'nota_minima': nota_minima(course),
        'plano_inclui_certificados': bool(plano_ok),
    }


def emitir_certificado(user, course, grade=None):
    """
    Emite (ou devolve o existente) certificado. Devolve (certificado, criado).
    Levanta CertificadoIndisponivel se não for possível.

    `grade`: StudentCourseGrade já calculada (os signals passam-na para não recalcular e
    não entrar em recursão); sem ela a nota é recalculada aqui.
    """
    from apps.courses.models import CourseCertificate, CourseEnrollment
    from apps.courses.services.grade_calculator import GradeCalculatorService

    existente = CourseCertificate.objects.filter(user=user, course=course).first()
    if existente:
        return existente, False

    if not plano_inclui_certificados(user):
        raise CertificadoIndisponivel(
            'CERTIFICADOS_NAO_INCLUIDOS',
            'Os certificados estão incluídos nos planos Premium e Premium Plus.',
            status=403,
        )
    if not CourseEnrollment.objects.filter(user=user, course=course).exists():
        raise CertificadoIndisponivel('NAO_INSCRITO', 'Não está inscrito neste curso.', status=404)

    progresso = _progresso(user, course)
    if grade is None:
        grade = GradeCalculatorService(user, course).calculate_and_save(change_reason='certificate_check')
        # O signal da nota pode já ter emitido o certificado durante este cálculo.
        existente = CourseCertificate.objects.filter(user=user, course=course).first()
        if existente:
            return existente, True

    em_falta = requisitos_em_falta(grade, progresso)
    if em_falta:
        raise CertificadoIndisponivel(
            'REQUISITOS_EM_FALTA',
            'Ainda não cumpre os requisitos para o certificado.',
            status=400,
            detalhes={
                'nota_final': grade.final_grade_percentage,
                'em_falta': em_falta,
            },
        )

    try:
        with transaction.atomic():
            certificado = CourseCertificate.objects.create(
                user=user,
                course=course,
                completion_percentage=progresso,
                final_grade=grade.final_grade_percentage,
                final_grade_letter=grade.final_grade_letter,
                verification_code=uuid.uuid4().hex[:12].upper(),
                **dados_fala(user, course),
            )
    except IntegrityError:  # emitido em paralelo
        return CourseCertificate.objects.get(user=user, course=course), False

    logger.info('Certificado %s emitido (user=%s, course=%s)', certificado.certificate_number, user.pk, course.pk)
    _notificar(certificado)
    return certificado, True


def emitir_se_elegivel(user, course, grade=None):
    """
    Versão silenciosa para os signals: devolve o certificado ou None.
    Se o professor desligou o certificado automático (definição certificado_automatico),
    não emite aqui: o aluno pede-o com POST .../<courseId>/certificado/.
    """
    from apps.courses.ciclo import definicao
    if not definicao(course, 'certificado_automatico'):
        return None
    try:
        certificado, _ = emitir_certificado(user, course, grade=grade)
        return certificado
    except CertificadoIndisponivel as e:
        logger.debug('Certificado não emitido (user=%s, course=%s): %s', user.pk, course.pk, e.codigo)
        return None


def exame_do_certificado(user, course):
    """O exame oral aprovado com a melhor nota efectiva (a revista ganha), ou None."""
    from apps.courses.models import ExameOral
    exames = [e for e in ExameOral.objects.filter(user=user, course=course, estado=ExameOral.AVALIADO, aprovado=True)]
    return max(exames, key=lambda e: (e.nota_efectiva or 0, e.created_at), default=None)


def dados_fala(user, course):
    """Campos do certificado sobre a fala (nivel_fala, area_fala, notas_fala); vazios sem exame."""
    from apps.courses import ciclo
    exame = exame_do_certificado(user, course)
    if exame is None:
        return {}
    notas = {k: (round(v) if v is not None else None) for k, v in exame.notas().items()}
    notas['exame'] = round(exame.nota_efectiva) if exame.nota_efectiva is not None else None
    return {'nivel_fala': exame.nivel_cefr or '', 'area_fala': ciclo.area_pt(course.category) or '',
            'notas_fala': notas}


def frase_nivel_fala(certificado):
    """'Nível de fala B1 em situações de trabalho de Petróleo e Gás' (ou None sem exame)."""
    if not certificado.nivel_fala:
        return None
    area = (certificado.area_fala or '').strip()
    if area and area != 'Geral':
        return f'Nível de fala {certificado.nivel_fala} em situações de trabalho de {area}'
    return f'Nível de fala {certificado.nivel_fala} em situações de trabalho'


NOMES_NOTAS_FALA = (('fluencia', 'Fluência'), ('gramatica', 'Gramática'), ('vocabulario', 'Vocabulário'),
                    ('tarefa', 'Tarefas'), ('pronuncia', 'Pronúncia'))


def notas_fala_lista(certificado):
    notas = certificado.notas_fala if isinstance(certificado.notas_fala, dict) else {}
    return [{'chave': k, 'nome': nome, 'nota': notas.get(k)} for k, nome in NOMES_NOTAS_FALA
            if notas.get(k) is not None]


def _notificar(certificado):
    try:
        from apps.users.models import Notification
        Notification.notify(
            certificado.user,
            Notification.KIND_CERTIFICATE,
            title='Certificado emitido',
            body=(f'Parabéns! Concluiu "{certificado.course.title}". '
                  f'Já pode descarregar o certificado n.º {certificado.certificate_number}.'),
            link='/user/certificates',
            dedupe_key=f'certificado:{certificado.pk}',
        )
    except Exception:  # nunca bloquear a emissão por causa da notificação
        logger.exception('Falha ao notificar certificado %s', certificado.pk)


def dados_verificacao_publica(certificado):
    """Só campos não sensíveis: sem e-mail, sem ids, sem motivo de revogação."""
    revogado = certificado.is_revoked
    return {
        'valido': not revogado,
        'estado': 'revogado' if revogado else 'valido',
        'numero': certificado.certificate_number,
        'nome_aluno': (certificado.user.name or '').strip() or 'Aluno ProEnglish',
        'curso': certificado.course.title,
        'emitido_em': timezone.localtime(certificado.issued_at, FUSO_ANGOLA).date().isoformat(),
        'nota_final': round(certificado.final_grade, 1) if certificado.final_grade is not None else None,
        'nivel_fala': certificado.nivel_fala or None,
        'nivel_fala_texto': frase_nivel_fala(certificado),
        'nota_exame_oral': (certificado.notas_fala or {}).get('exame') if isinstance(certificado.notas_fala, dict) else None,
        'notas_fala': notas_fala_lista(certificado),
        'revogado_em': (
            timezone.localtime(certificado.revoked_at, FUSO_ANGOLA).date().isoformat() if revogado else None
        ),
    }


def gerar_pdf(certificado):
    """Bytes do PDF (reportlab, gerado na hora; não fica guardado em media/)."""
    from apps.courses.services.certificate_service import CertificateGenerationService

    pdf_bytes, _ = CertificateGenerationService(certificado).generate_pdf()
    return pdf_bytes, f'certificado-{certificado.certificate_number}.pdf'
