"""
Administração do conteúdo do site (/api/v1/admin/site/). Só administradores (EAdministrador).

- GET    ''                         rascunho, publicado_em, alterado_em, ha_alteracoes, manutencao, contagens
- PATCH  topo/ | precos/ | definicoes/   (devolvem o mesmo formato do GET)
- GET/POST           numeros/ | empresas/ | servicos/ | perguntas/
- PATCH/DELETE       <lista>/<id>/
- POST               <lista>/ordem/  {ids}
- POST/DELETE        empresas/<id>/logo/   (multipart "logo": PNG ou WebP até 1 MB)
- POST publicar/ | descartar/ | manutencao/ {activa, mensagem, volta_em|null}
"""
import logging
import re
import uuid
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.core.permissions import EAdministrador
from apps.users.admin_api.servicos import erro, erro_validacao, registar

from . import conteudo as ct
from .models import ConfiguracaoSite, Empresa, Numero, Pergunta, Servico

logger = logging.getLogger(__name__)

MB = 1024 * 1024
LOGO_MAX = 1 * MB
PASTA_LOGOS = 'site/empresas/'
LIMITES = {'numeros': 12, 'empresas': 40, 'servicos': 12, 'perguntas': 30}

RE_HREF = re.compile(r'^(/(?![/\\])[^\s\\]*|#[A-Za-z0-9_-]+|https://[^\s\\@]+)$')
RE_GA = re.compile(r'^G-[A-Z0-9]{4,12}$')
RE_PIXEL = re.compile(r'^\d{5,20}$')
RE_TELEFONE = re.compile(r'^\+?[0-9][0-9 ]{7,18}[0-9]$')
REDES = {
    'instagram': ('instagram.com',),
    'linkedin': ('linkedin.com',),
    'facebook': ('facebook.com', 'fb.com'),
}


# ---------------------------------------------------------------------------
# Ajudas
# ---------------------------------------------------------------------------

def _agora_iso():
    return timezone.now().isoformat()


def _tocar(cfg, *seccoes):
    alterado = dict(cfg.alterado_em or {})
    for s in seccoes:
        alterado[s] = _agora_iso()
    cfg.alterado_em = alterado


def _tocar_lista(seccao):
    with transaction.atomic():
        cfg = ConfiguracaoSite.obter(bloquear=True)
        _tocar(cfg, seccao)
        cfg.save(update_fields=['alterado_em'])


def _dados(request):
    return request.data if isinstance(request.data, dict) else {}


class Erros(dict):
    def add(self, campo, msg):
        self.setdefault(campo, []).append(msg)


def _texto(d, campo, erros, maximo, obrigatorio=True, nulo=False, rotulo=None):
    """Lê um texto (aparado). Devolve (presente, valor)."""
    if campo not in d:
        return False, None
    v = d.get(campo)
    rotulo = rotulo or campo
    if v is None:
        if nulo:
            return True, None
        v = ''
    if not isinstance(v, str):
        erros.add(campo, f'O campo «{rotulo}» tem de ser texto.')
        return True, None
    v = v.strip()
    if not v:
        if obrigatorio:
            erros.add(campo, f'Preencha o campo «{rotulo}».')
            return True, None
        return True, (None if nulo else '')
    if len(v) > maximo:
        erros.add(campo, f'O campo «{rotulo}» tem no máximo {maximo} caracteres.')
        return True, None
    return True, v


def _booleano(d, campo, erros):
    if campo not in d:
        return False, None
    v = d.get(campo)
    if isinstance(v, bool):
        return True, v
    if v in ('true', 'false'):
        return True, v == 'true'
    erros.add(campo, 'Use verdadeiro ou falso.')
    return True, None


def _href(v):
    return isinstance(v, str) and len(v) <= 200 and bool(RE_HREF.match(v.strip()))


def _url_rede(v, dominios):
    # "\" e "@" fazem o browser abrir outro domínio ("https://mau.com\@instagram.com").
    if not isinstance(v, str) or any(c in v for c in '\\@') or any(c.isspace() or ord(c) < 32 for c in v):
        return False
    try:
        u = urlparse(v)
    except ValueError:
        return False
    host = (u.hostname or '').lower()
    if u.username is not None or u.password is not None:
        return False
    return u.scheme == 'https' and any(host == d or host.endswith('.' + d) for d in dominios)


# ---------------------------------------------------------------------------
# Representação
# ---------------------------------------------------------------------------

def numero_admin(n, vivos):
    f = ct.foto_numero(n)
    return {**f, 'valor_mostrado': ct.valor_numero(f, vivos)}


def empresa_admin(e):
    return ct.foto_empresa(e)


def servico_admin(s):
    return ct.foto_servico(s)


def pergunta_admin(p):
    return ct.foto_pergunta(p)


def topo_admin(topo):
    t = ct.topo_publico(topo or {})
    t.pop('nota')
    return t


def estado_admin(cfg=None):
    cfg = cfg or ConfiguracaoSite.obter()
    vivos = ct.Vivos()
    try:
        nota_prevista = ct.nota_media()
    except Exception:
        nota_prevista = None
    rascunho = {
        'topo': {**topo_admin(cfg.topo), 'nota_prevista': nota_prevista},
        'numeros': [numero_admin(n, vivos) for n in Numero.objects.order_by('ordem', 'id')],
        'empresas': [empresa_admin(e) for e in Empresa.objects.order_by('ordem', 'id')],
        'servicos': [servico_admin(s) for s in Servico.objects.order_by('ordem', 'id')],
        'precos': ct.precos_dict(cfg.precos, com_id=True),
        'perguntas': [pergunta_admin(p) for p in Pergunta.objects.order_by('ordem', 'id')],
        'definicoes': ct.definicoes_dict(cfg.definicoes),
    }
    alterado = cfg.alterado_em or {}
    return {
        'rascunho': rascunho,
        'publicado_em': cfg.publicado_em.isoformat() if cfg.publicado_em else None,
        'alterado_em': {s: alterado.get(s) for s in ct.SECCOES},
        'ha_alteracoes': ct.foto_rascunho(cfg) != (cfg.publicado or {}),
        'manutencao': ct.manutencao(cfg),
        'contagens': {
            'numeros': len(rascunho['numeros']),
            'empresas': len(rascunho['empresas']),
            'servicos': len(rascunho['servicos']),
            'perguntas': len(rascunho['perguntas']),
            'testemunhos_no_site': ct.testemunhos_no_site(),
        },
    }


@api_view(['GET'])
@permission_classes([EAdministrador])
def estado(request):
    return Response(estado_admin())


# ---------------------------------------------------------------------------
# Secções simples: topo, preços, definições
# ---------------------------------------------------------------------------

def _botao(v, campo, erros, nulo):
    if v is None:
        if nulo:
            return None
        erros.add(campo, 'Preencha o texto e a ligação do botão.')
        return None
    if not isinstance(v, dict):
        erros.add(campo, 'O botão tem de ter {texto, href}.')
        return None
    texto = v.get('texto')
    href = v.get('href')
    texto = texto.strip() if isinstance(texto, str) else ''
    href = href.strip() if isinstance(href, str) else ''
    if not texto:
        erros.add(campo, 'Escreva o texto do botão.')
    elif len(texto) > 30:
        erros.add(campo, 'O texto do botão tem no máximo 30 caracteres.')
    if not _href(href):
        erros.add(campo, 'A ligação tem de começar por "/", "#" ou "https://".')
    return {'texto': texto, 'href': href}


@api_view(['PATCH'])
@permission_classes([EAdministrador])
def topo(request):
    d = _dados(request)
    erros = Erros()
    novo = {}
    for campo, maximo, obrig, nulo, rotulo in (('etiqueta', 60, False, True, 'etiqueta'),
                                                ('titulo', 80, True, False, 'título'),
                                                ('texto', 240, True, False, 'texto')):
        presente, v = _texto(d, campo, erros, maximo, obrig, nulo, rotulo)
        if presente:
            novo[campo] = v
    if 'botao_principal' in d:
        novo['botao_principal'] = _botao(d.get('botao_principal'), 'botao_principal', erros, nulo=False)
    if 'botao_secundario' in d:
        novo['botao_secundario'] = _botao(d.get('botao_secundario'), 'botao_secundario', erros, nulo=True)
    presente, v = _booleano(d, 'mostrar_nota', erros)
    if presente:
        novo['mostrar_nota'] = v
    if erros:
        return erro_validacao(erros)
    with transaction.atomic():
        cfg = ConfiguracaoSite.obter(bloquear=True)
        cfg.topo = {**(cfg.topo or {}), **novo}
        _tocar(cfg, 'topo')
        cfg.save(update_fields=['topo', 'alterado_em'])
    return Response(estado_admin(cfg))


@api_view(['PATCH'])
@permission_classes([EAdministrador])
def precos(request):
    from apps.subscriptions.models import SubscriptionPlan
    d = _dados(request)
    erros = Erros()
    tipos = {t for t, _ in SubscriptionPlan.PLAN_TYPES}
    presente, mostrar_anual = _booleano(d, 'mostrar_anual', erros)
    planos_novos = {}
    if 'planos' in d:
        planos = d.get('planos')
        if not isinstance(planos, list):
            erros.add('planos', 'Envie a lista de planos.')
            planos = []
        for i, p in enumerate(planos):
            if not isinstance(p, dict) or p.get('tipo') not in tipos:
                erros.add('planos', f'O plano {i + 1} não tem um tipo válido (FREE, PREMIUM ou PREMIUM_PLUS).')
                continue
            e = Erros()
            textos = {}
            for campo, maximo, obrig, nulo, rotulo in (('subtitulo', 80, False, False, 'subtítulo'),
                                                        ('etiqueta', 30, False, True, 'etiqueta'),
                                                        ('botao', 30, True, False, 'botão'),
                                                        ('nota_angola', 120, False, True, 'nota para Angola')):
                pres, v = _texto(p, campo, e, maximo, obrig, nulo, rotulo)
                if pres:
                    textos[campo] = v
            for campo, msgs in e.items():
                for m in msgs:
                    erros.add(f'planos.{p["tipo"]}.{campo}', m)
            planos_novos[p['tipo']] = textos
    if erros:
        return erro_validacao(erros)
    with transaction.atomic():
        cfg = ConfiguracaoSite.obter(bloquear=True)
        pr = dict(cfg.precos or {})
        if presente:
            pr['mostrar_anual'] = mostrar_anual
        guardados = dict(pr.get('planos') or {})
        for tipo, textos in planos_novos.items():
            guardados[tipo] = {**ct.textos_plano(pr, tipo), **textos}
        pr['planos'] = guardados
        cfg.precos = pr
        _tocar(cfg, 'precos')
        cfg.save(update_fields=['precos', 'alterado_em'])
    return Response(estado_admin(cfg))


@api_view(['PATCH'])
@permission_classes([EAdministrador])
def definicoes(request):
    d = _dados(request)
    erros = Erros()
    novo = {}
    for campo, maximo, obrig, rotulo in (('titulo', 70, True, 'título'), ('descricao', 160, True, 'descrição'),
                                         ('palavras_chave', 255, False, 'palavras-chave')):
        presente, v = _texto(d, campo, erros, maximo, obrig, False, rotulo)
        if presente:
            novo[campo] = v
    presente, v = _texto(d, 'ga_id', erros, 20, False, True, 'Google Analytics')
    if presente and v is not None:
        v = v.upper()
        if not RE_GA.match(v):
            erros.add('ga_id', 'O identificador do Google Analytics tem o formato G-XXXXXXX.')
    if presente:
        novo['ga_id'] = v
    presente, v = _texto(d, 'pixel_id', erros, 20, False, True, 'Pixel')
    if presente and v is not None and not RE_PIXEL.match(v):
        erros.add('pixel_id', 'O identificador do Pixel tem só algarismos.')
    if presente:
        novo['pixel_id'] = v
    presente, v = _texto(d, 'email', erros, 254, False, True, 'email')
    if presente and v is not None:
        try:
            validate_email(v)
            v = v.lower()
        except DjangoValidationError:
            erros.add('email', 'Escreva um email válido.')
    if presente:
        novo['email'] = v
    presente, v = _texto(d, 'telefone', erros, 20, False, True, 'telefone')
    if presente and v is not None and not RE_TELEFONE.match(v):
        erros.add('telefone', 'Escreva um telefone válido (ex.: +244 923 000 000).')
    if presente:
        novo['telefone'] = v
    for rede, dominios in REDES.items():
        presente, v = _texto(d, rede, erros, 200, False, True, rede)
        if presente and v is not None and not _url_rede(v, dominios):
            erros.add(rede, f'Escreva o endereço completo, começado por https://, de {dominios[0]}.')
        if presente:
            novo[rede] = v
    if erros:
        return erro_validacao(erros)
    with transaction.atomic():
        cfg = ConfiguracaoSite.obter(bloquear=True)
        cfg.definicoes = {**(cfg.definicoes or {}), **novo}
        _tocar(cfg, 'definicoes')
        cfg.save(update_fields=['definicoes', 'alterado_em'])
    return Response(estado_admin(cfg))


# ---------------------------------------------------------------------------
# Listas: números, empresas, serviços, perguntas
# ---------------------------------------------------------------------------

def _ler_numero(d, n=None):
    erros = Erros()
    campos = {}
    pres, v = _texto(d, 'texto', erros, 60, True, False, 'texto')
    if pres:
        campos['texto'] = v
    if 'onde' in d:
        if d['onde'] not in dict(Numero.ONDE):
            erros.add('onde', 'Escolha onde aparece: topo, sobre ou rodape.')
        else:
            campos['onde'] = d['onde']
    if 'fonte' in d:
        if d['fonte'] not in dict(Numero.FONTES):
            erros.add('fonte', 'Escolha a origem do número: manual, utilizadores, alunos_activos_semana, '
                               'areas ou cursos.')
        else:
            campos['fonte'] = d['fonte']
    pres, v = _booleano(d, 'mostrar', erros)
    if pres:
        campos['mostrar'] = v
    fonte = campos.get('fonte', n.fonte if n else 'manual')
    if fonte == 'manual':
        pres, v = _texto(d, 'valor', erros, 20, True, False, 'valor')
        if pres:
            campos['valor'] = v
        elif not (n and n.valor):
            erros.add('valor', 'Escreva o valor (ex.: 15 min).')
    else:
        campos['valor'] = ''
    if n is None and 'texto' not in campos and 'texto' not in erros:
        erros.add('texto', 'Preencha o campo «texto».')
    return campos, erros


def _ler_empresa(d, e=None):
    erros = Erros()
    campos = {}
    pres, v = _texto(d, 'nome', erros, 80, True, False, 'nome')
    if pres:
        campos['nome'] = v
    pres, v = _texto(d, 'area', erros, 60, False, False, 'área')
    if pres:
        campos['area'] = v
    for b in ('no_topo', 'na_faixa'):
        pres, v = _booleano(d, b, erros)
        if pres:
            campos[b] = v
    if e is None and 'nome' not in campos and 'nome' not in erros:
        erros.add('nome', 'Preencha o campo «nome».')
    return campos, erros


def _ler_servico(d, s=None):
    erros = Erros()
    campos = {}
    pres, v = _texto(d, 'titulo', erros, 60, True, False, 'título')
    if pres:
        campos['titulo'] = v
    pres, v = _texto(d, 'texto', erros, 300, True, False, 'texto')
    if pres:
        campos['texto'] = v
    if 'icone' in d:
        if d['icone'] not in dict(Servico.ICONES):
            erros.add('icone', 'Escolha um ícone: bot, microfone, balao, livro, certificado ou laboratorio.')
        else:
            campos['icone'] = d['icone']
    pres, v = _texto(d, 'leva_a', erros, 200, False, True, 'leva a')
    if pres:
        if v is not None and not _href(v):
            erros.add('leva_a', 'A ligação tem de começar por "/", "#" ou "https://".')
        else:
            campos['leva_a'] = v or ''
    if s is None:
        for c, rot in (('titulo', 'título'), ('texto', 'texto')):
            if c not in campos and c not in erros:
                erros.add(c, f'Preencha o campo «{rot}».')
    return campos, erros


def _ler_pergunta(d, p=None):
    erros = Erros()
    campos = {}
    pres, v = _texto(d, 'pergunta', erros, 200, True, False, 'pergunta')
    if pres:
        campos['pergunta'] = v
    pres, v = _texto(d, 'resposta', erros, 1000, True, False, 'resposta')
    if pres:
        campos['resposta'] = v
    if p is None:
        for c in ('pergunta', 'resposta'):
            if c not in campos and c not in erros:
                erros.add(c, f'Preencha o campo «{c}».')
    return campos, erros


LISTAS = {
    'numeros': (Numero, _ler_numero, 'Este número'),
    'empresas': (Empresa, _ler_empresa, 'Esta empresa'),
    'servicos': (Servico, _ler_servico, 'Este serviço'),
    'perguntas': (Pergunta, _ler_pergunta, 'Esta pergunta'),
}


def _repr(seccao, obj, vivos=None):
    if seccao == 'numeros':
        return numero_admin(obj, vivos or ct.Vivos())
    return {'empresas': empresa_admin, 'servicos': servico_admin, 'perguntas': pergunta_admin}[seccao](obj)


def _lista(seccao):
    modelo = LISTAS[seccao][0]
    vivos = ct.Vivos()
    return [_repr(seccao, o, vivos) for o in modelo.objects.order_by('ordem', 'id')]


def _vista_lista(seccao):
    @api_view(['GET', 'POST'])
    @permission_classes([EAdministrador])
    def vista(request):
        modelo, ler, _ = LISTAS[seccao]
        if request.method == 'GET':
            return Response(_lista(seccao))
        campos, erros = ler(_dados(request))
        if erros:
            return erro_validacao(erros)
        from django.db.models import Max
        with transaction.atomic():
            ConfiguracaoSite.obter(bloquear=True)  # dois pedidos ao mesmo tempo não passam o limite
            if modelo.objects.count() >= LIMITES[seccao]:
                return erro(f'Pode ter no máximo {LIMITES[seccao]} itens nesta lista.', 'limite_atingido')
            ultima = modelo.objects.aggregate(m=Max('ordem'))['m'] or 0
            obj = modelo.objects.create(ordem=ultima + 1, **campos)
        _tocar_lista(seccao)
        return Response(_repr(seccao, obj), status=201)
    vista.__name__ = f'lista_{seccao}'
    return vista


def _vista_item(seccao):
    @api_view(['PATCH', 'DELETE'])
    @permission_classes([EAdministrador])
    def vista(request, pk):
        modelo, ler, nome = LISTAS[seccao]
        obj = modelo.objects.filter(pk=pk).first()
        if obj is None:
            return erro(f'{nome} já não existe.', 'nao_encontrado', 404)
        if request.method == 'DELETE':
            logo = getattr(obj, 'logo_url', '')
            obj.delete()
            _tocar_lista(seccao)
            if logo:
                _apagar_logos_livres([logo])
            return Response(status=204)
        campos, erros = ler(_dados(request), obj)
        if erros:
            return erro_validacao(erros)
        for k, v in campos.items():
            setattr(obj, k, v)
        if campos:
            obj.save()
            _tocar_lista(seccao)
        return Response(_repr(seccao, obj))
    vista.__name__ = f'item_{seccao}'
    return vista


def _vista_ordem(seccao):
    @api_view(['POST'])
    @permission_classes([EAdministrador])
    def vista(request):
        modelo = LISTAS[seccao][0]
        ids = _dados(request).get('ids')
        existentes = set(modelo.objects.values_list('id', flat=True))
        if (not isinstance(ids, list) or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids)
                or len(ids) != len(set(ids)) or set(ids) != existentes):
            return erro_validacao({'ids': ['Envie todos os ids da lista, uma vez cada, pela nova ordem.']})
        with transaction.atomic():
            for i, pk in enumerate(ids, start=1):
                modelo.objects.filter(pk=pk).update(ordem=i)
        _tocar_lista(seccao)
        return Response(_lista(seccao))
    vista.__name__ = f'ordem_{seccao}'
    return vista


VISTAS_LISTA = {s: _vista_lista(s) for s in LISTAS}
VISTAS_ITEM = {s: _vista_item(s) for s in LISTAS}
VISTAS_ORDEM = {s: _vista_ordem(s) for s in LISTAS}


# ---------------------------------------------------------------------------
# Logótipos (PNG ou WebP, até 1 MB; SVG recusado)
# ---------------------------------------------------------------------------

def _tipo_imagem(cabeca):
    if cabeca.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png', 'image/png'
    if len(cabeca) >= 12 and cabeca[:4] == b'RIFF' and cabeca[8:12] == b'WEBP':
        return 'webp', 'image/webp'
    return None, None


def _usa_s3():
    return bool(getattr(settings, 'USE_S3', False))


def _guardar_logo(request, empresa, conteudo, ext, mime):
    from apps.courses.api.teacher import envios
    chave = f'{PASTA_LOGOS}{empresa.pk}-{uuid.uuid4().hex[:12]}.{ext}'
    if _usa_s3():
        envios._s3().put_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=chave, Body=conteudo,
                                ContentType=mime, CacheControl='max-age=31536000, immutable')
        return envios.url_publico(chave)
    caminho = envios._caminho_local(chave)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(conteudo)
    return envios.url_local(request, chave)


def _logos_em_uso():
    usados = set(Empresa.objects.exclude(logo_url='').values_list('logo_url', flat=True))
    cfg = ConfiguracaoSite.objects.filter(pk=1).first()
    for e in ((cfg.publicado or {}).get('empresas') or []) if cfg else []:
        if e.get('logo_url'):
            usados.add(e['logo_url'])
    return usados


def _apagar_logo(url):
    from apps.courses.api.teacher import envios
    for base in envios._bases_s3():
        if url.startswith(base):
            chave = unquote(url[len(base):].split('?')[0])
            if chave.startswith(PASTA_LOGOS) and _usa_s3():
                try:
                    envios._s3().delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=chave)
                except Exception:
                    logger.exception('Não foi possível apagar o logótipo %s do S3', chave)
            return
    caminho = unquote(urlparse(url).path)
    prefixo = settings.MEDIA_URL if settings.MEDIA_URL.startswith('/') else urlparse(settings.MEDIA_URL).path
    if caminho.startswith(prefixo) and caminho[len(prefixo):].startswith(PASTA_LOGOS):
        try:
            envios._caminho_local(caminho[len(prefixo):]).unlink(missing_ok=True)
        except (ValueError, OSError):
            logger.warning('Não foi possível apagar o logótipo local %s', url)


def _apagar_logos_livres(urls):
    """Depois do commit, apaga os logótipos que nem o rascunho nem a versão publicada usam."""
    urls = [u for u in dict.fromkeys(urls or []) if u]
    if not urls:
        return

    def apagar():
        usados = _logos_em_uso()
        for u in urls:
            if u not in usados:
                _apagar_logo(u)
    transaction.on_commit(apagar)


@api_view(['POST', 'DELETE'])
@permission_classes([EAdministrador])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def logo(request, pk):
    empresa = Empresa.objects.filter(pk=pk).first()
    if empresa is None:
        return erro('Esta empresa já não existe.', 'nao_encontrado', 404)
    antigo = empresa.logo_url
    if request.method == 'DELETE':
        empresa.logo_url = ''
        empresa.save(update_fields=['logo_url'])
        _tocar_lista('empresas')
        _apagar_logos_livres([antigo])
        return Response(empresa_admin(empresa))
    ficheiro = request.FILES.get('logo') or request.FILES.get('ficheiro')
    if ficheiro is None:
        return erro_validacao({'logo': ['Escolha o ficheiro do logótipo (PNG ou WebP).']})
    if ficheiro.size > LOGO_MAX:
        return erro_validacao({'logo': ['O logótipo tem no máximo 1 MB.']})
    conteudo = ficheiro.read(LOGO_MAX + 1)
    if len(conteudo) > LOGO_MAX:
        return erro_validacao({'logo': ['O logótipo tem no máximo 1 MB.']})
    ext, mime = _tipo_imagem(conteudo[:16])
    if ext is None:
        return erro_validacao({'logo': ['Envie o logótipo em PNG ou WebP (SVG não é aceite).']})
    if not _usa_s3():
        from apps.courses.api.teacher import envios
        if not envios.envios_locais_permitidos():
            return erro('O envio de ficheiros não está disponível neste servidor (armazenamento não '
                        'configurado).', 'armazenamento_indisponivel', 503)
    try:
        url = _guardar_logo(request, empresa, conteudo, ext, mime)
    except Exception:
        logger.exception('Falha ao guardar o logótipo da empresa %s', empresa.pk)
        return erro('Não foi possível guardar o logótipo. Tente outra vez.', 'erro_envio', 502)
    empresa.logo_url = url
    empresa.save(update_fields=['logo_url'])
    _tocar_lista('empresas')
    _apagar_logos_livres([antigo])
    return Response(empresa_admin(empresa))


# ---------------------------------------------------------------------------
# Publicar, descartar, manutenção
# ---------------------------------------------------------------------------

def _seccoes_diferentes(a, b):
    return [s for s in ct.SECCOES if (a or {}).get(s) != (b or {}).get(s)]


@api_view(['POST'])
@permission_classes([EAdministrador])
def publicar(request):
    with transaction.atomic():
        cfg = ConfiguracaoSite.obter(bloquear=True)
        nova = ct.foto_rascunho(cfg)
        mudou = _seccoes_diferentes(nova, cfg.publicado)
        if not mudou and cfg.publicado_em:
            return erro('Não há alterações por publicar.', 'sem_alteracoes', 400)
        logos_antigos = [e.get('logo_url') for e in (cfg.publicado or {}).get('empresas', [])]
        cfg.publicado = nova
        cfg.publicado_em = timezone.now()
        cfg.publicado_por = request.user
        cfg.save(update_fields=['publicado', 'publicado_em', 'publicado_por'])
        registar(request, 'site_publicar', alvo_tipo='site', alvo_id='1', detalhes={'seccoes': mudou})
        _apagar_logos_livres(logos_antigos)
        transaction.on_commit(ct.limpar_cache)
    ct.limpar_cache()
    return Response(estado_admin(cfg))


@api_view(['POST'])
@permission_classes([EAdministrador])
def descartar(request):
    with transaction.atomic():
        cfg = ConfiguracaoSite.obter(bloquear=True)
        pub = cfg.publicado or {}
        logos_rascunho = list(Empresa.objects.exclude(logo_url='').values_list('logo_url', flat=True))
        mudou = _seccoes_diferentes(ct.foto_rascunho(cfg), pub)
        cfg.topo = dict(pub.get('topo') or {})
        cfg.precos = dict(pub.get('precos') or {})
        cfg.definicoes = dict(pub.get('definicoes') or {})
        cfg.alterado_em = {}
        cfg.save(update_fields=['topo', 'precos', 'definicoes', 'alterado_em'])
        Numero.objects.all().delete()
        Empresa.objects.all().delete()
        Servico.objects.all().delete()
        Pergunta.objects.all().delete()
        Numero.objects.bulk_create([Numero(id=n['id'], valor=n['valor'], texto=n['texto'], onde=n['onde'],
                                           fonte=n['fonte'], mostrar=n['mostrar'], ordem=n['ordem'])
                                    for n in pub.get('numeros', [])])
        Empresa.objects.bulk_create([Empresa(id=e['id'], nome=e['nome'], area=e.get('area') or '',
                                             logo_url=e.get('logo_url') or '', no_topo=e['no_topo'],
                                             na_faixa=e['na_faixa'], ordem=e['ordem'])
                                     for e in pub.get('empresas', [])])
        Servico.objects.bulk_create([Servico(id=s['id'], titulo=s['titulo'], texto=s['texto'], icone=s['icone'],
                                             leva_a=s.get('leva_a') or '', ordem=s['ordem'])
                                     for s in pub.get('servicos', [])])
        Pergunta.objects.bulk_create([Pergunta(id=p['id'], pergunta=p['pergunta'], resposta=p['resposta'],
                                               ordem=p['ordem'])
                                      for p in pub.get('perguntas', [])])
        registar(request, 'site_descartar', alvo_tipo='site', alvo_id='1', detalhes={'seccoes': mudou})
        _apagar_logos_livres(logos_rascunho)
    return Response(estado_admin(cfg))


@api_view(['POST'])
@permission_classes([EAdministrador])
def manutencao(request):
    d = _dados(request)
    erros = Erros()
    pres, activa = _booleano(d, 'activa', erros)
    if not pres and 'activa' not in erros:
        erros.add('activa', 'Diga se o modo de manutenção fica ligado ou desligado.')
    _, mensagem = _texto(d, 'mensagem', erros, 300, False, False, 'mensagem')
    volta_em = None
    v = d.get('volta_em')
    if v not in (None, ''):
        try:
            volta_em = parse_datetime(v) if isinstance(v, str) else None
        except ValueError:  # formato certo, data inexistente (30 de Fevereiro)
            volta_em = None
        if volta_em is None:
            erros.add('volta_em', 'Use uma data e hora válidas (ISO 8601).')
        else:
            if timezone.is_naive(volta_em):
                from apps.users.admin_api.servicos import FUSO_LUANDA
                volta_em = volta_em.replace(tzinfo=FUSO_LUANDA)
            if activa and volta_em <= timezone.now():
                erros.add('volta_em', 'A hora de regresso tem de ser no futuro.')
    if erros:
        return erro_validacao(erros)
    with transaction.atomic():
        cfg = ConfiguracaoSite.obter(bloquear=True)
        cfg.manutencao_activa = activa
        if mensagem is not None:
            cfg.manutencao_mensagem = mensagem
        cfg.manutencao_volta_em = volta_em if activa else None
        cfg.save(update_fields=['manutencao_activa', 'manutencao_mensagem', 'manutencao_volta_em'])
        registar(request, 'site_manutencao', alvo_tipo='site', alvo_id='1',
                 detalhes={'activa': activa, 'volta_em': volta_em.isoformat() if volta_em and activa else None})
        transaction.on_commit(ct.limpar_cache)
    ct.limpar_cache()
    return Response(estado_admin(cfg))
