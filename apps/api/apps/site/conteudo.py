"""
Regras do conteúdo do site: fotografia do rascunho, versão pública, números automáticos,
preços, áreas, testemunhos, nota média e manutenção.

As funções `foto_*` só usam atributos dos modelos, para poderem ser usadas também na migração
de dados (com os modelos históricos).
"""
import logging
import re

from django.core.cache import cache
from django.db.models import Avg, Count
from django.utils import timezone

logger = logging.getLogger(__name__)

CHAVE_CACHE = 'site:publico:v1'
DURACAO_CACHE = 120  # 2 minutos; mudanças em planos, testemunhos, cursos e contas limpam antes (sinais.py)

SECCOES = ('topo', 'numeros', 'empresas', 'servicos', 'precos', 'perguntas', 'definicoes')
MINIMO_OPINIOES_NOTA = 5
MAX_TESTEMUNHOS = 3
# Áreas que não contam como "área profissional" no número automático "areas".
AREAS_NAO_PROFISSIONAIS = {'Geral', 'Inglês com IA'}

MENSAGEM_MANUTENCAO = 'Estamos a fazer melhorias no site. Voltamos dentro de pouco tempo.'

TEXTOS_PLANO = {
    'FREE': {'subtitulo': 'Para começar sem pagar', 'etiqueta': None, 'botao': 'Começar grátis',
             'nota_angola': None},
    'PREMIUM': {'subtitulo': 'Para quem estuda todos os dias', 'etiqueta': None, 'botao': 'Escolher Premium',
                'nota_angola': 'Pague em kwanzas por Multicaixa Express.'},
    'PREMIUM_PLUS': {'subtitulo': 'Todos os cursos, incluindo os Premium Plus', 'etiqueta': None,
                     'botao': 'Escolher Premium Plus',
                     'nota_angola': 'Pague em kwanzas por Multicaixa Express.'},
}
TEXTOS_PLANO_OMISSAO = {'subtitulo': '', 'etiqueta': None, 'botao': 'Escolher plano', 'nota_angola': None}
CAMPOS_TEXTO_PLANO = ('subtitulo', 'etiqueta', 'botao', 'nota_angola')


# ---------------------------------------------------------------------------
# Fotografia (rascunho -> publicado)
# ---------------------------------------------------------------------------

def foto_numero(n):
    return {'id': n.id, 'valor': n.valor, 'texto': n.texto, 'onde': n.onde, 'fonte': n.fonte,
            'mostrar': n.mostrar, 'ordem': n.ordem}


def foto_empresa(e):
    return {'id': e.id, 'nome': e.nome, 'area': e.area, 'logo_url': e.logo_url or None,
            'no_topo': e.no_topo, 'na_faixa': e.na_faixa, 'ordem': e.ordem}


def foto_servico(s):
    return {'id': s.id, 'titulo': s.titulo, 'texto': s.texto, 'icone': s.icone,
            'leva_a': s.leva_a or None, 'ordem': s.ordem}


def foto_pergunta(p):
    return {'id': p.id, 'pergunta': p.pergunta, 'resposta': p.resposta, 'ordem': p.ordem}


def foto(cfg, Numero, Empresa, Servico, Pergunta):
    """O rascunho todo, no formato guardado em ConfiguracaoSite.publicado."""
    return {
        'topo': dict(cfg.topo or {}),
        'precos': dict(cfg.precos or {}),
        'definicoes': dict(cfg.definicoes or {}),
        'numeros': [foto_numero(n) for n in Numero.objects.order_by('ordem', 'id')],
        'empresas': [foto_empresa(e) for e in Empresa.objects.order_by('ordem', 'id')],
        'servicos': [foto_servico(s) for s in Servico.objects.order_by('ordem', 'id')],
        'perguntas': [foto_pergunta(p) for p in Pergunta.objects.order_by('ordem', 'id')],
    }


def foto_rascunho(cfg):
    from .models import Empresa, Numero, Pergunta, Servico
    return foto(cfg, Numero, Empresa, Servico, Pergunta)


CHAVE_GERACAO = 'site:publico:geracao'


def limpar_cache():
    """Muda a geração: a próxima leitura reconstrói (planos, testemunhos, cursos e contas mudaram)."""
    try:
        cache.incr(CHAVE_GERACAO)
    except ValueError:
        cache.set(CHAVE_GERACAO, 1, None)


def _chave(cfg):
    # A data de publicação faz parte da chave: um pedido que leu a versão antiga nunca a guarda
    # por cima da nova (corrida entre a leitura pública e Publicar).
    pub = cfg.publicado_em.timestamp() if cfg.publicado_em else 0
    return f'{CHAVE_CACHE}:{pub}:{cache.get(CHAVE_GERACAO, 0)}'


# ---------------------------------------------------------------------------
# Manutenção (desliga-se sozinha depois de volta_em, ao ler)
# ---------------------------------------------------------------------------

def manutencao(cfg=None, publico=False):
    from .models import ConfiguracaoSite
    cfg = cfg or ConfiguracaoSite.obter()
    if cfg.manutencao_activa and cfg.manutencao_volta_em and cfg.manutencao_volta_em <= timezone.now():
        ConfiguracaoSite.objects.filter(pk=cfg.pk, manutencao_activa=True,
                                        manutencao_volta_em__lte=timezone.now()).update(
            manutencao_activa=False, manutencao_volta_em=None)
        cfg.manutencao_activa = False
        cfg.manutencao_volta_em = None
        limpar_cache()
    return {
        'activa': cfg.manutencao_activa,
        # Fora da manutenção, a mensagem guardada é só para a administração.
        'mensagem': (cfg.manutencao_mensagem or MENSAGEM_MANUTENCAO) if cfg.manutencao_activa
        else ('' if publico else (cfg.manutencao_mensagem or '')),
        'volta_em': cfg.manutencao_volta_em.isoformat() if cfg.manutencao_volta_em else None,
    }


# ---------------------------------------------------------------------------
# Dados vivos
# ---------------------------------------------------------------------------

def formatar_numero(n):
    """1234567 -> '1 234 567' (pt-PT: espaço inseparável a separar os milhares)."""
    return f'{int(n):,}'.replace(',', ' ')


def _slug(texto):
    import unicodedata
    t = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii').lower()
    return re.sub(r'[^a-z0-9]+', '-', t).strip('-')


def areas():
    """Áreas com pelo menos um curso publicado e visível no catálogo: [{valor, nome, cursos}]."""
    from apps.courses import ciclo
    from apps.courses.models import Course

    contagem = {}
    for r in Course.objects.filter(ciclo.q_catalogo()).values('category').annotate(n=Count('id')):
        nome = ciclo.area_pt(r['category'])
        if nome:
            contagem[nome] = contagem.get(nome, 0) + r['n']
    lista = [{'valor': _slug(nome), 'nome': nome, 'cursos': n} for nome, n in contagem.items()
             if nome not in AREAS_NAO_PROFISSIONAIS]
    lista.sort(key=lambda a: (-a['cursos'], a['nome']))
    return lista


def utilizadores_activos():
    """Contas de alunos registadas (sem apagadas nem suspensas)."""
    from apps.users.models import User
    return (User.objects.filter(role='student', is_active=True)
            .exclude(email__endswith='@apagado.invalid').count())


def alunos_activos_semana():
    from datetime import timedelta

    from apps.courses.api.admin_painel_cursos import _hoje, _inicio_dia, _pares_activos
    pares = _pares_activos(_inicio_dia(_hoje() - timedelta(days=6)))
    return len({u for u, _ in pares})


def cursos_publicados():
    from apps.courses import ciclo
    from apps.courses.models import Course
    return Course.objects.filter(ciclo.q_catalogo()).count()


class Vivos:
    """Calcula cada valor vivo uma só vez por pedido."""

    def __init__(self):
        self._v = {}

    def _obter(self, chave, fn):
        if chave not in self._v:
            try:
                self._v[chave] = fn()
            except Exception:
                logger.exception('Falha ao calcular %s para o site', chave)
                self._v[chave] = None
        return self._v[chave]

    def areas(self):
        return self._obter('areas', areas) or []

    def valor(self, fonte):
        if fonte == 'utilizadores':
            return self._obter('utilizadores', utilizadores_activos)
        if fonte == 'alunos_activos_semana':
            return self._obter('alunos_activos_semana', alunos_activos_semana)
        if fonte == 'cursos':
            return self._obter('cursos', cursos_publicados)
        if fonte == 'areas':
            return len(self.areas())
        return None


def valor_numero(n, vivos):
    """Texto mostrado no site para um número (dict da fotografia)."""
    if n['fonte'] == 'manual':
        return n['valor']
    v = vivos.valor(n['fonte'])
    return formatar_numero(v) if v is not None else None  # falhou: o número não aparece


def nota_media():
    from apps.users.models import UserFeedback
    r = (UserFeedback.objects.filter(estado=UserFeedback.APROVADA, rating__isnull=False, user__is_active=True)
         .exclude(user__email__endswith='@apagado.invalid')
         .aggregate(m=Avg('rating'), n=Count('id')))
    if not r['n'] or r['n'] < MINIMO_OPINIOES_NOTA:
        return None
    return {'media': round(float(r['m']), 1), 'total': r['n']}


def testemunhos():
    from apps.users.admin_api.opinioes import area_de, no_site_qs, nome_curto
    saida = []
    for f in no_site_qs().select_related('user').order_by('ordem', '-created_at')[:MAX_TESTEMUNHOS]:
        saida.append({'id': len(saida) + 1, 'nome': nome_curto(f.user.name), 'area': area_de(f.user),
                      'texto': f.comment, 'nota': f.rating})
    return saida


def testemunhos_no_site():
    from apps.users.admin_api.opinioes import no_site_qs
    return min(no_site_qs().count(), MAX_TESTEMUNHOS)


def kz(valor):
    return int(round(float(valor))) if valor is not None else None


def planos_activos():
    from apps.subscriptions.models import SubscriptionPlan
    return list(SubscriptionPlan.objects.filter(is_active=True).order_by('sort_order', 'monthly_price'))


def caracteristicas(plano):
    from apps.subscriptions.serializers import SubscriptionPlanSerializer
    return SubscriptionPlanSerializer().get_features(plano)


def textos_plano(precos, tipo):
    base = dict(TEXTOS_PLANO.get(tipo, TEXTOS_PLANO_OMISSAO))
    guardado = ((precos or {}).get('planos') or {}).get(tipo) or {}
    for campo in CAMPOS_TEXTO_PLANO:
        if campo in guardado:
            base[campo] = guardado[campo]
    return base


def plano_dict(p, precos, com_id=False):
    d = {
        'tipo': p.plan_type,
        'nome': p.name,
        'preco_mensal_kz': kz(p.monthly_price) or 0,
        'preco_anual_kz': kz(p.yearly_price) if p.yearly_price else None,
        'dias_teste': p.dias_teste if p.plan_type != 'FREE' else 0,
        'destaque': p.destaque,
        **textos_plano(precos, p.plan_type),
        'caracteristicas': caracteristicas(p),
    }
    if com_id:
        d = {'id': str(p.id), **d}
    return d


def precos_dict(precos, com_id=False):
    return {
        'mostrar_anual': bool((precos or {}).get('mostrar_anual', True)),
        'planos': [plano_dict(p, precos, com_id) for p in planos_activos()],
    }


def _ou_nulo(v):
    return v if v not in ('', None) else None


def topo_publico(topo, nota=None):
    sec = topo.get('botao_secundario')
    return {
        'etiqueta': _ou_nulo(topo.get('etiqueta')),
        'titulo': topo.get('titulo', ''),
        'texto': topo.get('texto', ''),
        'botao_principal': dict(topo.get('botao_principal') or {'texto': '', 'href': '/signup'}),
        'botao_secundario': dict(sec) if sec else None,
        'mostrar_nota': bool(topo.get('mostrar_nota', False)),
        'nota': nota,
    }


CAMPOS_DEFINICOES = ('titulo', 'descricao', 'palavras_chave', 'ga_id', 'pixel_id', 'email', 'telefone',
                     'instagram', 'linkedin', 'facebook')
CAMPOS_DEFINICOES_TEXTO = ('titulo', 'descricao', 'palavras_chave')


def definicoes_dict(d):
    d = d or {}
    return {c: (d.get(c) or '') if c in CAMPOS_DEFINICOES_TEXTO else _ou_nulo(d.get(c))
            for c in CAMPOS_DEFINICOES}


# ---------------------------------------------------------------------------
# Versão pública
# ---------------------------------------------------------------------------

def construir_publico(cfg):
    p = cfg.publicado or {}
    vivos = Vivos()
    topo = p.get('topo') or {}
    nota = None
    if topo.get('mostrar_nota'):
        try:
            nota = nota_media()
        except Exception:
            logger.exception('Falha ao calcular a nota média do site')
    try:
        lista_testemunhos = testemunhos()
    except Exception:
        logger.exception('Falha ao ler os testemunhos do site')
        lista_testemunhos = []
    return {
        'topo': topo_publico(topo, nota),
        'numeros': [{'id': n['id'], 'valor': v, 'texto': n['texto'], 'onde': n['onde']}
                    for n in p.get('numeros', []) if n.get('mostrar')
                    for v in [valor_numero(n, vivos)] if v is not None],
        'empresas': [{'id': e['id'], 'nome': e['nome'], 'area': e.get('area') or '',
                      'logo_url': e.get('logo_url') or None, 'no_topo': e['no_topo'], 'na_faixa': e['na_faixa']}
                     for e in p.get('empresas', [])],
        'servicos': [{'id': s['id'], 'titulo': s['titulo'], 'texto': s['texto'], 'icone': s['icone'],
                      'leva_a': s.get('leva_a') or None} for s in p.get('servicos', [])],
        'areas': vivos.areas(),
        'precos': precos_dict(p.get('precos') or {}),
        'testemunhos': lista_testemunhos,
        'perguntas': [{'id': q['id'], 'pergunta': q['pergunta'], 'resposta': q['resposta']}
                      for q in p.get('perguntas', [])],
        'definicoes': definicoes_dict(p.get('definicoes')),
        'publicado_em': cfg.publicado_em.isoformat() if cfg.publicado_em else None,
    }


def publico():
    """GET /api/v1/site/: o conteúdo fica 5 minutos em cache; a manutenção é lida sempre."""
    from .models import ConfiguracaoSite
    cfg = ConfiguracaoSite.obter()
    chave = _chave(cfg)
    dados = cache.get(chave)
    if dados is None:
        dados = construir_publico(cfg)
        cache.set(chave, dados, DURACAO_CACHE)
    return {**dados, 'manutencao': manutencao(cfg, publico=True)}
