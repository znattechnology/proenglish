"""
Requisito dos cursos de sector: o nível básico.

Um curso de sector (Petróleo e Gás, Banca, Tecnologia...) pede, no mínimo, o nível básico do curso
geral (English Communication Skills). Tem-no quem:
- concluiu um curso geral com certificado; ou
- foi aprovado no teste do nível básico (este módulo).

Quem já estava inscrito ou já fazia um curso de sector continua; a regra vale para entradas novas.
O teste é corrigido no servidor: 20 perguntas sorteadas do banco, 70% para aprovar, 20 minutos.
Quem reprova (ou deixa o tempo acabar) pode repetir ao fim de 24 horas.

O mesmo teste existe para cada nível (A1, A2, B1 e B2): é o teste de colocação do curso geral
(apps/courses/colocacao.py). O "teste do nível básico" é o do A2. Os bancos do A1 ao B2 vêm dos
questionários das unidades (bancos_colocacao.json, gerado por manage.py gerar_bancos_colocacao).
"""
import json
import os
import random
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

N_PERGUNTAS = 20
PERCENTAGEM_APROVACAO = 70
DURACAO = timedelta(minutes=20)
TOLERANCIA_ENTREGA = timedelta(seconds=30)   # rede lenta ao entregar no último segundo
ESPERA_REPETIR = timedelta(hours=24)

CODIGO = 'requisito_basico'
MENSAGEM = ('Os cursos de sector pedem, no mínimo, o nível básico de inglês. '
            'Faça o teste do nível básico ou comece pelo curso geral.')
AREAS_GERAIS = {'Geral'}
NIVEL_BASICO = 'A2'
NIVEIS_TESTE = ('A1', 'A2', 'B1', 'B2')

# (id, enunciado, [opções; a primeira é a certa]). Níveis A1 e A2: o que o nível básico ensina.
BANCO = [
    ('b01', 'Hello, my name ___ Ana.', ['is', 'are', 'am']),
    ('b02', '___ are you from? — I am from Luanda.', ['Where', 'Who', 'When']),
    ('b03', 'She ___ in a bank.', ['works', 'work', 'working']),
    ('b04', 'How do you say 15 in English?', ['fifteen', 'fifty', 'five']),
    ('b05', 'They ___ my colleagues.', ['are', 'is', 'am']),
    ('b06', 'I ___ coffee every morning.', ['drink', 'drinks', 'drinking']),
    ('b07', '___ you speak English? — Yes, a little.', ['Do', 'Does', 'Are']),
    ('b08', 'He ___ not work on Sundays.', ['does', 'do', 'is']),
    ('b09', 'What time is it? — It is ___ o\'clock.', ['nine', 'ninth', 'nineteenth day']),
    ('b10', 'The meeting is ___ Monday.', ['on', 'in', 'at']),
    ('b11', 'I start work ___ eight o\'clock.', ['at', 'on', 'in']),
    ('b12', 'My birthday is ___ March.', ['in', 'on', 'at']),
    ('b13', 'This is my manager. ___ name is Paulo.', ['His', 'He', 'Him']),
    ('b14', 'These are Ana and Rui. ___ office is on the second floor.', ['Their', 'They', 'Them']),
    ('b15', 'There ___ two computers on the desk.', ['are', 'is', 'be']),
    ('b16', 'Is there a printer here? — Yes, there ___.', ['is', 'are', 'has']),
    ('b17', 'I ___ to the office yesterday.', ['went', 'go', 'goes']),
    ('b18', 'She ___ the report last week.', ['finished', 'finish', 'finishes']),
    ('b19', '___ you call the client yesterday?', ['Did', 'Do', 'Were']),
    ('b20', 'I am ___ an email right now.', ['writing', 'write', 'wrote']),
    ('b21', 'Look! It ___ raining.', ['is', 'does', 'are']),
    ('b22', 'Can you ___ me, please?', ['help', 'helps', 'to help']),
    ('b23', 'I ___ swim, but I can not drive.', ['can', 'am', 'do']),
    ('b24', 'Which word is a job?', ['nurse', 'table', 'Tuesday']),
    ('b25', 'Which word is a day of the week?', ['Thursday', 'March', 'morning']),
    ('b26', 'What is the opposite of "expensive"?', ['cheap', 'big', 'late']),
    ('b27', 'What is the opposite of "early"?', ['late', 'slow', 'old']),
    ('b28', 'How ___ is this phone? — It is 90 000 kwanzas.', ['much', 'many', 'old']),
    ('b29', 'How ___ people work in your team?', ['many', 'much', 'long']),
    ('b30', 'I would like ___ water, please.', ['some', 'a', 'many']),
    ('b31', 'This office is ___ than the old one.', ['bigger', 'big', 'more big']),
    ('b32', 'Luanda is the ___ city in Angola.', ['biggest', 'bigger', 'most big']),
    ('b33', 'Nice to meet you. — ___', ['Nice to meet you too.', 'I am fine, thanks.', 'See you later.']),
    ('b34', 'How are you? — ___', ['I am fine, thank you.', 'I am Ana.', 'I am from Benguela.']),
    ('b35', 'Could you repeat that, please? — ___', ['Sure, no problem.', 'Yes, I am.', 'Nice to meet you.']),
    ('b36', 'Tomorrow I ___ visit a client.', ['am going to', 'went to', 'going']),
    ('b37', 'Ana: "I work at a hospital. I help the doctors." What is Ana\'s job?', ['A nurse', 'A pilot', 'A lawyer']),
    ('b38', 'Rui: "My train leaves at seven. I arrive at work at eight." When does Rui arrive at work?',
     ['At eight', 'At seven', 'At nine']),
    ('b39', 'We ___ got a meeting at ten.', ['have', 'has', 'are']),
    ('b40', 'I do not have ___ questions.', ['any', 'some', 'much']),
]


def _carregar_bancos():
    caminho = os.path.join(os.path.dirname(__file__), 'bancos_colocacao.json')
    bancos = {n: [] for n in NIVEIS_TESTE}
    if os.path.exists(caminho):
        with open(caminho, encoding='utf-8') as f:
            for nivel, perguntas in json.load(f).items():
                if nivel in bancos:
                    bancos[nivel] = [tuple(p) for p in perguntas]
    bancos[NIVEL_BASICO] = list(BANCO) + bancos[NIVEL_BASICO]
    return bancos


BANCOS = _carregar_bancos()
_POR_ID = {p[0]: p for banco in BANCOS.values() for p in banco}


def _indice(nivel):
    from apps.courses import niveis
    return niveis.indice(nivel)


def nivel_valido(nivel):
    return nivel if nivel in NIVEIS_TESTE and len(BANCOS.get(nivel) or []) >= N_PERGUNTAS else None


def aprovado_no_nivel(user, nivel):
    """True se foi aprovado no teste deste nível ou de um acima (quem passa no B1 também sabe o A1)."""
    from apps.courses.models import TesteNivelBasico
    acima = [n for n in NIVEIS_TESTE if _indice(n) >= _indice(nivel)]
    return TesteNivelBasico.objects.filter(user=user, aprovado=True, nivel__in=acima).exists()


def curso_de_sector(course):
    """True se o curso é de um sector (tem área e não é a geral)."""
    from apps.courses import ciclo
    area = ciclo.area_pt(course.category)
    return bool(area) and area not in AREAS_GERAIS


def tem_nivel_basico(user):
    from apps.courses.models import CourseCertificate
    if aprovado_no_nivel(user, NIVEL_BASICO):
        return True
    from apps.courses import ciclo
    gerais = [valor for valor, rotulo in ciclo.AREAS.items() if rotulo in AREAS_GERAIS]
    return CourseCertificate.objects.filter(user=user, revoked_at__isnull=True,
                                            course__category__in=gerais).exists()


def falta_requisito(user, course):
    """True se o curso é de sector e a pessoa ainda não tem o nível básico."""
    if not curso_de_sector(course):
        return False
    return not tem_nivel_basico(user)


def _fechar_expirada(t, agora):
    """Uma tentativa que ficou por entregar conta como reprovada (senão via-se as perguntas à vontade)."""
    if t.submetido_em is None and agora > t.expira_em + TOLERANCIA_ENTREGA:
        t.submetido_em = t.expira_em
        t.total = len(t.perguntas)
        t.save(update_fields=['submetido_em', 'total', 'updated_at'])


def _perguntas_cliente(t):
    saida = []
    for item in t.perguntas:
        _, enunciado, opcoes = _POR_ID[item['id']]
        saida.append({'id': item['id'], 'enunciado': enunciado, 'opcoes': [opcoes[i] for i in item['ordem']]})
    return saida


def _tentativa_dict(t, com_perguntas=False):
    d = {
        'id': str(t.id),
        'nivel': t.nivel,
        'iniciado_em': t.created_at.isoformat(),
        'expira_em': t.expira_em.isoformat(),
        'submetido_em': t.submetido_em.isoformat() if t.submetido_em else None,
        'certas': t.certas if t.submetido_em else None,
        'total': t.total or len(t.perguntas),
        'aprovado': t.aprovado if t.submetido_em else None,
    }
    if com_perguntas:
        d['perguntas'] = _perguntas_cliente(t)
    return d


def ultima_tentativa(user, nivel):
    from apps.courses.models import TesteNivelBasico
    ultima = TesteNivelBasico.objects.filter(user=user, nivel=nivel).first()
    if ultima:
        _fechar_expirada(ultima, timezone.now())
    return ultima


def estado(user, nivel=NIVEL_BASICO):
    """O que o ecrã do teste precisa: se já tem o nível, se pode tentar e quando."""
    agora = timezone.now()
    ultima = ultima_tentativa(user, nivel)
    tem = tem_nivel_basico(user) if nivel == NIVEL_BASICO else aprovado_no_nivel(user, nivel)
    em_curso = ultima if ultima and ultima.submetido_em is None else None
    proxima = None
    if not tem and ultima and ultima.submetido_em is not None and not ultima.aprovado:
        quando = ultima.created_at + ESPERA_REPETIR
        if quando > agora:
            proxima = quando
    return {
        'nivel': nivel,
        'aprovado_no_nivel': tem,
        'tem_nivel_basico': tem if nivel == NIVEL_BASICO else tem_nivel_basico(user),
        'pode_iniciar': not tem and proxima is None,
        'proxima_tentativa_em': proxima.isoformat() if proxima else None,
        'em_curso': _tentativa_dict(em_curso, com_perguntas=True) if em_curso else None,
        'ultima': _tentativa_dict(ultima) if ultima and ultima.submetido_em else None,
        'regras': {'perguntas': N_PERGUNTAS, 'aprovacao': PERCENTAGEM_APROVACAO,
                   'minutos': int(DURACAO.total_seconds() // 60),
                   'espera_horas': int(ESPERA_REPETIR.total_seconds() // 3600)},
    }


class ErroTeste(Exception):
    def __init__(self, codigo, mensagem, status=400):
        super().__init__(mensagem)
        self.codigo, self.mensagem, self.status = codigo, mensagem, status


def iniciar(user, nivel=NIVEL_BASICO):
    """Abre uma tentativa (ou devolve a que está em curso). Lança ErroTeste se não pode."""
    from django.contrib.auth import get_user_model
    from apps.courses.models import TesteNivelBasico
    if not nivel_valido(nivel):
        raise ErroTeste('validation_error', 'Não há teste para este nível.')
    with transaction.atomic():
        get_user_model().objects.select_for_update().filter(pk=user.pk).first()
        e = estado(user, nivel)
        if e['aprovado_no_nivel']:
            raise ErroTeste('ja_aprovado', 'Já tem o nível básico: pode inscrever-se em qualquer curso de sector.'
                            if nivel == NIVEL_BASICO else f'Já foi aprovado no teste do nível {nivel}.')
        if e['em_curso']:
            return TesteNivelBasico.objects.filter(user=user, nivel=nivel).first()
        if not e['pode_iniciar']:
            raise ErroTeste('espera', 'Pode repetir o teste 24 horas depois da última tentativa.', 429)
        sorteadas = random.sample(BANCOS[nivel], N_PERGUNTAS)
        perguntas = []
        for pid, _, opcoes in sorteadas:
            ordem = list(range(len(opcoes)))
            random.shuffle(ordem)
            perguntas.append({'id': pid, 'ordem': ordem})
        return TesteNivelBasico.objects.create(user=user, nivel=nivel, perguntas=perguntas, total=len(perguntas),
                                               expira_em=timezone.now() + DURACAO)


def submeter(user, teste_id, respostas):
    """
    respostas: {id da pergunta: índice da opção escolhida, pela ordem mostrada}. O que faltar conta
    como errado. Devolve a tentativa corrigida.
    """
    from apps.courses.models import TesteNivelBasico
    if not isinstance(respostas, dict):
        raise ErroTeste('validation_error', 'Envie as respostas como {pergunta: opção}.')
    with transaction.atomic():
        t = TesteNivelBasico.objects.select_for_update().filter(pk=teste_id, user=user).first()
        if t is None:
            raise ErroTeste('not_found', 'Teste não encontrado.', 404)
        if t.submetido_em is not None:
            raise ErroTeste('ja_entregue', 'Este teste já foi entregue.', 409)
        agora = timezone.now()
        if agora > t.expira_em + TOLERANCIA_ENTREGA:
            _fechar_expirada(t, agora)
            raise ErroTeste('tempo_esgotado', 'O tempo do teste acabou. Pode repetir daqui a 24 horas.', 410)
        certas = 0
        for item in t.perguntas:
            escolha = respostas.get(item['id'])
            if isinstance(escolha, bool) or not isinstance(escolha, int):
                continue
            if 0 <= escolha < len(item['ordem']) and item['ordem'][escolha] == 0:
                certas += 1
        t.certas = certas
        t.total = len(t.perguntas)
        t.aprovado = certas * 100 >= PERCENTAGEM_APROVACAO * t.total
        t.submetido_em = agora
        t.save(update_fields=['certas', 'total', 'aprovado', 'submetido_em', 'updated_at'])
        return t
